import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from ai.openrouter_client import OpenRouterClient, validate_step_numbers_response
from core.capcut_draft import CapCutProject
from core.dual_styler import (
    DualStyler,
    STEP_AUDIO_TRACK_NAME,
    STEP_BADGE_POS_X,
    STEP_BADGE_POS_Y,
    STEP_BADGE_TRACK_NAME,
    STEP_MINI_ZOOM_ANIM,
)
from core.platform_paths import get_step_enter_sound_path


class _DummyHTTPResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _load_preset(filename: str) -> dict:
    styles_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "styles")
    with open(os.path.join(styles_dir, filename), "r", encoding="utf-8") as f:
        return json.load(f)


def _create_draft_with_lines(tmp_dir: str, lines) -> CapCutProject:
    texts = []
    segs = []
    max_end = 0
    for idx, (st_us, dur_us, text_str) in enumerate(lines):
        mat_id = f"MAT_{idx}"
        words_list = text_str.split()
        step = max(1, (dur_us // 1000) // max(1, len(words_list)))
        st_ms = [i * step for i in range(len(words_list))]
        en_ms = [(i + 1) * step for i in range(len(words_list))]
        texts.append({
            "id": mat_id,
            "type": "subtitle",
            "recognize_task_id": "asr_1",
            "recognize_text": text_str,
            "content": json.dumps(
                {"text": text_str, "styles": [{"range": [0, len(text_str)], "size": 10.0}]},
                ensure_ascii=False,
            ),
            "words": {"start_time": st_ms, "end_time": en_ms, "text": words_list},
        })
        segs.append({
            "id": f"SEG_{idx}",
            "material_id": mat_id,
            "target_timerange": {"start": st_us, "duration": dur_us},
            "source_timerange": None,
            "render_timerange": {"start": 0, "duration": 0},
            "clip": {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": 0.0}, "rotation": 0.0, "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0},
            "extra_material_refs": [],
            "uniform_scale": {"on": True, "value": 1.0},
            "state": 0,
            "speed": 1.0,
            "visible": True,
        })
        max_end = max(max_end, st_us + dur_us)

    draft = {
        "duration": max_end + 1000000,
        "fps": 30.0,
        "materials": {"texts": texts, "audios": [], "material_animations": []},
        "tracks": [{"id": "TRK_0", "type": "text", "flag": 1, "attribute": 0, "name": "", "segments": segs}],
    }
    draft_path = os.path.join(tmp_dir, "draft_content.json")
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False)
    return CapCutProject(tmp_dir)


class TestStepNumberValidation(unittest.TestCase):
    def _sample_segments(self):
        return [
            {"index": 0, "start": 0, "end": 1500000, "text": "Mi método tiene 3 pasos"},
            {"index": 1, "start": 1500000, "end": 3000000, "text": "Primero usa exfoliante"},
            {"index": 2, "start": 3000000, "end": 4800000, "text": "una o 2 veces por semana"},
            {"index": 3, "start": 4800000, "end": 6200000, "text": "Segundo retinol nocturno"},
            {"index": 4, "start": 6200000, "end": 8000000, "text": "para mejorar la piel"},
            {"index": 5, "start": 8000000, "end": 9800000, "text": "Y por último protector solar"},
            {"index": 6, "start": 9800000, "end": 11500000, "text": "Sígueme para más consejos"},
        ]

    def test_valid_sequential_steps_accepted(self):
        segs = self._sample_segments()
        parsed = {
            "is_ordered_steps": True,
            "reason": "Tres pasos secuenciales (Primero, Segundo, Y por último).",
            "steps": [
                {"number": 1, "start_index": 1, "end_index": 2},
                {"number": 2, "start_index": 3, "end_index": 4},
                {"number": 3, "start_index": 5, "end_index": 5},
            ],
        }
        res = validate_step_numbers_response(parsed, segs)
        self.assertEqual([r["number"] for r in res], [1, 2, 3])
        self.assertEqual(res[0]["start_index"], 1)
        self.assertEqual(res[0]["end_index"], 2)
        self.assertEqual(res[2]["end_index"], 5)

    def test_rejects_false_flag_and_non_sequential_numbers(self):
        segs = self._sample_segments()
        self.assertEqual(
            validate_step_numbers_response(
                {"is_ordered_steps": False, "steps": [{"number": 1, "start_index": 1, "end_index": 2}]},
                segs,
            ),
            [],
        )
        # Rejects discontinuous jumps such as [1, 112]
        self.assertEqual(
            validate_step_numbers_response(
                {
                    "is_ordered_steps": True,
                    "steps": [
                        {"number": 1, "start_index": 1, "end_index": 2},
                        {"number": 112, "start_index": 3, "end_index": 4},
                    ],
                },
                segs,
            ),
            [],
        )
        # Rejects single casual number without a multi-step list
        self.assertEqual(
            validate_step_numbers_response(
                {"is_ordered_steps": True, "steps": [{"number": 1, "start_index": 1, "end_index": 2}]},
                segs,
            ),
            [],
        )

    def test_detect_step_numbers_requires_openrouter_key(self):
        client = OpenRouterClient(api_key="")
        self.assertIsNone(client.detect_step_numbers(self._sample_segments()))

    def test_detect_step_numbers_parses_openrouter_json(self):
        segs = self._sample_segments()
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "is_ordered_steps": True,
                                "reason": "Secuencia de 3 pasos",
                                "steps": [
                                    {"number": 1, "start_index": 1, "end_index": 2},
                                    {"number": 2, "start_index": 3, "end_index": 4},
                                    {"number": 3, "start_index": 5, "end_index": 5},
                                ],
                            }
                        )
                    }
                }
            ]
        }
        client = OpenRouterClient(api_key="test-key")
        with patch("urllib.request.urlopen", return_value=_DummyHTTPResponse(payload)):
            res = client.detect_step_numbers(segs)
        self.assertIsNotNone(res)
        self.assertEqual([r["number"] for r in res], [1, 2, 3])


class TestStepBadgePlacementAndAudio(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_step_audio_asset_is_bundled(self):
        snd_path = get_step_enter_sound_path()
        self.assertTrue(os.path.isfile(snd_path), f"Missing step sound asset at {snd_path}")

    def test_duration_chains_to_next_step_and_stops_on_topic_gap_or_cta(self):
        raw_items = [
            {"index": 0, "start": 5000000, "end": 7500000, "text": "Primero exfoliante"},
            {"index": 1, "start": 7500000, "end": 10000000, "text": "para evitar que vuelva"},
            {"index": 2, "start": 10200000, "end": 13000000, "text": "Segundo retinol"},
            # Gap > 2.5s before step 3 starts at 20.00s
            {"index": 3, "start": 13000000, "end": 19500000, "text": "historia clínica aparte"},
            {"index": 4, "start": 20000000, "end": 23000000, "text": "Tercero protector solar"},
            {"index": 5, "start": 23000000, "end": 25000000, "text": "Sígueme para más"},
        ]
        detections = [
            {"number": 1, "start_index": 0, "end_index": 1, "start_pos": 0, "end_pos": 1},
            {"number": 2, "start_index": 2, "end_index": 2, "start_pos": 2, "end_pos": 2},
            {"number": 3, "start_index": 4, "end_index": 4, "start_pos": 4, "end_pos": 4},
        ]
        plan = DualStyler._build_step_badge_plan(raw_items, detections)
        self.assertEqual(len(plan), 3)
        # Step 1 bridges small 200ms gap directly up to Step 2 start (10.20s)
        self.assertEqual(plan[0]["start"], 5000000)
        self.assertEqual(plan[0]["end"], 10200000)
        # Step 2 does NOT bridge 7s off-topic gap; ends at end of Step 2 (13.00s)
        self.assertEqual(plan[1]["start"], 10200000)
        self.assertEqual(plan[1]["end"], 13000000)
        # Step 3 ends at end of its explanation before CTA (23.00s)
        self.assertEqual(plan[2]["start"], 20000000)
        self.assertEqual(plan[2]["end"], 23000000)

    def test_auto_dual_process_places_top_left_steps_with_doctor_style_minizoom_and_enter_sfx(self):
        lines = [
            (0, 2000000, "Mi rutina tiene 3 pasos"),
            (2000000, 1500000, "Primero exfoliante"),
            (3500000, 1500000, "1 o 2 veces"),
            (5000000, 2000000, "Segundo retinol"),
            (7000000, 1800000, "Tercero ácido salicílico"),
            (8800000, 1500000, "Sígueme para más"),
        ]
        proj = _create_draft_with_lines(self.tmp_dir, lines)
        styler = DualStyler(preset_data=_load_preset("alvaro.json"))

        with patch.object(
            OpenRouterClient,
            "process_subtitles",
            return_value={
                "corrected_subtitles": [{"index": i, "text": t} for i, (_, _, t) in enumerate(lines)],
                "highlights": [{"target_index": 1, "phrase": "Primero", "tone": "normal"}],
            },
        ), patch.object(
            OpenRouterClient,
            "detect_step_numbers",
            return_value=[
                {"number": 1, "start_index": 1, "end_index": 2, "start_pos": 1, "end_pos": 2},
                {"number": 2, "start_index": 3, "end_index": 3, "start_pos": 3, "end_pos": 3},
                {"number": 3, "start_index": 4, "end_index": 4, "start_pos": 4, "end_pos": 4},
            ],
        ):
            styler.auto_dual_process(proj, openrouter_key="test-key", min_pacing_sec=1.0)

        # Verify Pasos track exists and contains 1, 2, 3 in top-left corner
        pasos_tracks = [t for t in proj.data["tracks"] if t.get("type") == "text" and t.get("name") == STEP_BADGE_TRACK_NAME]
        self.assertEqual(len(pasos_tracks), 1)
        p_segs = pasos_tracks[0]["segments"]
        self.assertEqual(len(p_segs), 3)

        texts_by_id = {m["id"]: m for m in proj.data["materials"]["texts"]}
        anims_by_id = {m["id"]: m for m in proj.data["materials"]["material_animations"]}
        for idx, expected_num in enumerate(["1", "2", "3"]):
            seg = p_segs[idx]
            mat = texts_by_id[seg["material_id"]]
            self.assertEqual(json.loads(mat["content"])["text"], expected_num)
            self.assertEqual(mat["text_color"], "#FDB2A0")
            self.assertTrue(mat["font_path"].endswith("GC GRIND.otf"))
            self.assertAlmostEqual(seg["clip"]["transform"]["x"], STEP_BADGE_POS_X, places=3)
            self.assertAlmostEqual(seg["clip"]["transform"]["y"], STEP_BADGE_POS_Y, places=3)
            self.assertEqual(seg["target_timerange"]["start"], lines[idx + 1 + (1 if idx >= 1 else 0)][0])

            # Check Mini zoom entrance animation attached
            self.assertTrue(seg["extra_material_refs"])
            anim_mat = anims_by_id[seg["extra_material_refs"][0]]
            self.assertEqual(anim_mat["animations"][0]["resource_id"], STEP_MINI_ZOOM_ANIM["resource_id"])
            self.assertEqual(anim_mat["animations"][0]["name"], "Mini zoom")

        # Step 1 lasts until Step 2 starts, Step 2 lasts until Step 3 starts, Step 3 ends before CTA
        self.assertEqual(p_segs[0]["target_timerange"]["start"] + p_segs[0]["target_timerange"]["duration"], p_segs[1]["target_timerange"]["start"])
        self.assertEqual(p_segs[1]["target_timerange"]["start"] + p_segs[1]["target_timerange"]["duration"], p_segs[2]["target_timerange"]["start"])
        self.assertEqual(p_segs[2]["target_timerange"]["start"] + p_segs[2]["target_timerange"]["duration"], 8800000)

        # Verify dedicated Pasos Audio track with Enter / Click / Select sound synced to steps
        pasos_audio_tracks = [t for t in proj.data["tracks"] if t.get("type") == "audio" and t.get("name") == STEP_AUDIO_TRACK_NAME]
        self.assertEqual(len(pasos_audio_tracks), 1)
        aud_segs = pasos_audio_tracks[0]["segments"]
        self.assertEqual([s["target_timerange"]["start"] for s in aud_segs], [s["target_timerange"]["start"] for s in p_segs])
        aud_mats = {m["id"]: m for m in proj.data["materials"]["audios"]}
        self.assertEqual(aud_mats[aud_segs[0]["material_id"]]["name"], "Enter / Click / Select sound")

        # Verify step badges are excluded from spoken subtitles and survive idempotent re-run
        self.assertTrue(all(json.loads(s.text_material["content"])["text"] not in {"1", "2", "3"} for s in proj.subtitles))

        # Re-run should keep exactly 1 Pasos track and 1 Pasos Audio track without duplication
        with patch.object(
            OpenRouterClient,
            "process_subtitles",
            return_value={
                "corrected_subtitles": [{"index": i, "text": t} for i, (_, _, t) in enumerate(lines)],
                "highlights": [{"target_index": 1, "phrase": "Primero", "tone": "normal"}],
            },
        ), patch.object(
            OpenRouterClient,
            "detect_step_numbers",
            return_value=[
                {"number": 1, "start_index": 1, "end_index": 2, "start_pos": 1, "end_pos": 2},
                {"number": 2, "start_index": 3, "end_index": 3, "start_pos": 3, "end_pos": 3},
                {"number": 3, "start_index": 4, "end_index": 4, "start_pos": 4, "end_pos": 4},
            ],
        ):
            styler.auto_dual_process(proj, openrouter_key="test-key", min_pacing_sec=1.0)
        self.assertEqual(len([t for t in proj.data["tracks"] if t.get("name") == STEP_BADGE_TRACK_NAME]), 1)
        self.assertEqual(len([t for t in proj.data["tracks"] if t.get("name") == STEP_AUDIO_TRACK_NAME]), 1)

    def test_no_step_badges_when_no_openrouter_key_or_only_normal_numbers(self):
        lines = [
            (0, 1500000, "Toma 2 litros de agua"),
            (1500000, 1500000, "durante 10 días"),
            (3000000, 1500000, "para mejorar al 80%"),
        ]
        proj = _create_draft_with_lines(self.tmp_dir, lines)
        styler = DualStyler(preset_data=_load_preset("alvaro.json"))
        # Ensure env var / local config doesn't leak a real API key during test
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=False), patch.object(
            styler, "_resolve_openrouter_client", return_value=None
        ):
            styler.auto_dual_process(proj, openrouter_key=None)
        self.assertEqual([t for t in proj.data["tracks"] if t.get("name") == STEP_BADGE_TRACK_NAME], [])
        self.assertEqual([t for t in proj.data["tracks"] if t.get("name") == STEP_AUDIO_TRACK_NAME], [])

        # Even WITH OpenRouter key, returning [] must leave 0 step tracks
        with patch.object(
            OpenRouterClient,
            "process_subtitles",
            return_value={
                "corrected_subtitles": [{"index": i, "text": t} for i, (_, _, t) in enumerate(lines)],
                "highlights": [],
            },
        ), patch.object(OpenRouterClient, "detect_step_numbers", return_value=[]):
            styler.auto_dual_process(proj, openrouter_key="test-key")
        self.assertEqual([t for t in proj.data["tracks"] if t.get("name") == STEP_BADGE_TRACK_NAME], [])
        self.assertEqual([t for t in proj.data["tracks"] if t.get("name") == STEP_AUDIO_TRACK_NAME], [])

    def test_template_and_dentok_layouts_also_use_active_doctor_highlight_style(self):
        lines = [
            (0, 1500000, "Primero haz esto"),
            (1500000, 1500000, "Segundo haz aquello"),
        ]
        # Template preset (Ana)
        proj_ana = _create_draft_with_lines(self.tmp_dir, lines)
        styler_ana = DualStyler(preset_data=_load_preset("ana.json"))
        with patch.object(
            OpenRouterClient,
            "process_subtitles",
            return_value={"corrected_subtitles": [], "highlights": []},
        ), patch.object(
            OpenRouterClient,
            "detect_step_numbers",
            return_value=[
                {"number": 1, "start_index": 0, "end_index": 0, "start_pos": 0, "end_pos": 0},
                {"number": 2, "start_index": 1, "end_index": 1, "start_pos": 1, "end_pos": 1},
            ],
        ):
            styler_ana.auto_dual_process(proj_ana, openrouter_key="test-key")

        pasos_ana = [t for t in proj_ana.data["tracks"] if t.get("name") == STEP_BADGE_TRACK_NAME]
        self.assertEqual(len(pasos_ana), 1)
        texts_ana = {m["id"]: m for m in proj_ana.data["materials"]["texts"]}
        first_mat = texts_ana[pasos_ana[0]["segments"][0]["material_id"]]
        self.assertEqual(first_mat["text_color"], "#FDE69A")
        self.assertTrue(first_mat["font_path"].endswith("Liliana-Black.otf"))

        # Dentok preset
        tmp2 = tempfile.mkdtemp()
        try:
            proj_den = _create_draft_with_lines(tmp2, lines)
            styler_den = DualStyler(preset_data=_load_preset("dentok.json"))
            with patch.object(
                OpenRouterClient,
                "process_subtitles",
                return_value={"corrected_subtitles": [], "highlights": []},
            ), patch.object(
                OpenRouterClient,
                "detect_step_numbers",
                return_value=[
                    {"number": 1, "start_index": 0, "end_index": 0, "start_pos": 0, "end_pos": 0},
                    {"number": 2, "start_index": 1, "end_index": 1, "start_pos": 1, "end_pos": 1},
                ],
            ):
                styler_den.auto_dual_process(proj_den, openrouter_key="test-key")
            pasos_den = [t for t in proj_den.data["tracks"] if t.get("name") == STEP_BADGE_TRACK_NAME]
            self.assertEqual(len(pasos_den), 1)
            texts_den = {m["id"]: m for m in proj_den.data["materials"]["texts"]}
            den_mat = texts_den[pasos_den[0]["segments"][0]["material_id"]]
            self.assertTrue(den_mat["font_path"].endswith("PlayfairDisplay-Italic.ttf"))
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
