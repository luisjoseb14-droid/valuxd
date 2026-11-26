# -*- coding: utf-8 -*-
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from ai.openrouter_client import OpenRouterClient
from core.capcut_draft import CapCutProject
from core.dual_styler import DualStyler, STEP_BADGE_TRACK_NAME
from core.grammar_checker import check_project_grammar, collect_grammar_segments
from core.text_utils import (
    HARD_MAX_LINE_CHARS,
    rebalance_subtitle_segments,
    sanitize_highlight_phrase,
    split_wide_segment_for_safe_margins,
)


def _make_words(pairs):
    texts, starts, ends = [], [], []
    for idx, (word, s_ms, e_ms) in enumerate(pairs):
        if idx > 0:
            prev_e = ends[-1]
            texts.append(" ")
            starts.append(prev_e)
            ends.append(s_ms)
        texts.append(word)
        starts.append(s_ms)
        ends.append(e_ms)
    return {"text": texts, "start_time": starts, "end_time": ends}


def _create_project(tmpdir, tracks, texts, duration=68_370_000):
    draft = {
        "canvas_config": {"width": 1080, "height": 1920, "ratio": "original"},
        "duration": duration,
        "fps": 30.0,
        "materials": {
            "texts": texts,
            "audios": [],
            "material_animations": [],
            "text_templates": [],
            "canvases": [],
            "effects": [],
            "stickers": [],
            "transitions": [],
            "videos": [],
        },
        "tracks": tracks,
    }
    with open(os.path.join(tmpdir, "draft_content.json"), "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False)
    return CapCutProject(tmpdir)


class _DummyHTTPResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestAuditFixes(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _build_overlay_draft(self, sub_specs):
        texts = []
        sub_segs = []
        for idx, spec in enumerate(sub_specs):
            mat_id = f"SUB_MAT_{idx}"
            txt = spec["text"]
            texts.append({
                "id": mat_id,
                "type": "subtitle",
                "recognize_task_id": "asr_1",
                "recognize_text": txt,
                "content": json.dumps({"text": txt, "styles": [{"range": [0, len(txt)], "size": 10.0}]}, ensure_ascii=False),
                "words": spec.get("words") or _make_words(
                    [(w, i * 250, (i + 1) * 250) for i, w in enumerate(txt.split())]
                ),
            })
            sub_segs.append({
                "id": f"SUB_SEG_{idx}",
                "material_id": mat_id,
                "target_timerange": {"start": spec["start"], "duration": spec["end"] - spec["start"]},
                "clip": {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": -0.118}},
                "extra_material_refs": [],
            })

        overlay_specs = [
            ("Ranking - Título Superior (Subtítulo)", "OV_RANK_TITLE", " para tus hijos"),
            ("Ranking Puesto #1", "OV_RANK_1", "1"),
            ("Ranking Puesto #2", "OV_RANK_2", "2"),
            ("Puntuación - Título Superior (Subtítulo)", "OV_SCORE_TITLE", " PARA PESOS ALTOS"),
        ]
        tracks = [{"id": "VID_0", "type": "video", "segments": []}]
        for idx, (trk_name, mat_id, ov_text) in enumerate(overlay_specs):
            texts.append({
                "id": mat_id,
                "type": "text",
                "recognize_task_id": "",
                "recognize_text": "",
                "content": json.dumps({"text": ov_text, "styles": [{"range": [0, len(ov_text)], "size": 12.0}]}, ensure_ascii=False),
                "words": {"start_time": [], "end_time": [], "text": []},
            })
            tracks.append({
                "id": f"OV_TRK_{idx}",
                "type": "text",
                "flag": 0,
                "is_default_name": False,
                "name": trk_name,
                "segments": [{
                    "id": f"OV_SEG_{idx}",
                    "material_id": mat_id,
                    "target_timerange": {"start": 0, "duration": 68_370_000},
                    "extra_material_refs": [],
                }],
            })

        # Also add main speech track AFTER overlay tracks to verify track selection ignores overlays
        tracks.append({
            "id": "SPEECH_TRK",
            "type": "text",
            "flag": 1,
            "is_default_name": True,
            "name": "",
            "segments": sub_segs,
        })
        return _create_project(self.tmp_dir, tracks, texts, duration=68_370_000)

    def test_overlay_tracks_survive_dual_inline_repair_and_grammar(self):
        sub_specs = [
            {"text": " estas zapatillas", "start": 100_000, "end": 1_200_000},
            {"text": "tienen soporte clínico ", "start": 1_250_000, "end": 2_500_000},
        ]

        # 1. Dual preset (costa_calida) + collect_grammar_segments
        proj_dual = self._build_overlay_draft(sub_specs)
        grammar_segs = collect_grammar_segments(proj_dual)
        grammar_texts = [g["text"] for g in grammar_segs]
        self.assertEqual(len(grammar_segs), 2)
        self.assertNotIn("1", grammar_texts)
        self.assertNotIn(" PARA PESOS ALTOS", grammar_texts)

        styler_dual = DualStyler.from_preset("costa_calida")
        styler_dual.auto_dual_process(proj_dual, openrouter_key=None)
        trk_by_name = {t.get("name"): t for t in proj_dual.data["tracks"] if t.get("type") == "text"}
        mats = {m["id"]: m for m in proj_dual.data["materials"]["texts"]}
        for ov_name in (
            "Ranking - Título Superior (Subtítulo)",
            "Ranking Puesto #1",
            "Ranking Puesto #2",
            "Puntuación - Título Superior (Subtítulo)",
        ):
            self.assertIn(ov_name, trk_by_name, f"Overlay track '{ov_name}' was deleted!")
            seg = trk_by_name[ov_name]["segments"][0]
            self.assertIn(seg["material_id"], mats, f"Material for '{ov_name}' was deleted!")

        # Ensure speech subtitles have zero leading/trailing whitespace
        speech_top_segs = [t for t in proj_dual.data["tracks"] if t.get("type") == "text" and t.get("name", "") == ""][0]["segments"]
        for s in speech_top_segs:
            txt = json.loads(mats[s["material_id"]]["content"])["text"]
            self.assertEqual(txt, txt.strip(), f"Stray outer whitespace in '{txt!r}'")

        # 2. Repair preserves overlay uppercase/spaces while trimming speech tracks
        # Inject stray space into speech track then run repair_project_subtitles
        first_mat = mats[speech_top_segs[0]["material_id"]]
        c_obj = json.loads(first_mat["content"])
        c_obj["text"] = "  estas zapatillas  "
        first_mat["content"] = json.dumps(c_obj, ensure_ascii=False)
        styler_carrillo = DualStyler.from_preset("carrillo")  # uppercase=True
        styler_carrillo.repair_project_subtitles(proj_dual)
        repaired_first = json.loads(first_mat["content"])["text"]
        self.assertEqual(repaired_first, "ESTAS ZAPATILLAS")
        self.assertEqual(json.loads(mats["OV_RANK_TITLE"]["content"])["text"], " para tus hijos")

        # 3. Inline preset (jose)
        tmpdir2 = tempfile.mkdtemp()
        try:
            proj_inline = self._build_overlay_draft(sub_specs)
            proj_inline.project_path = tmpdir2
            styler_inline = DualStyler.from_preset("jose")
            styler_inline.auto_dual_process(proj_inline, openrouter_key=None)
            trk_inline = {t.get("name"): t for t in proj_inline.data["tracks"] if t.get("type") == "text"}
            mats_inline = {m["id"]: m for m in proj_inline.data["materials"]["texts"]}
            for ov_name in ("Ranking - Título Superior (Subtítulo)", "Ranking Puesto #1", "Puntuación - Título Superior (Subtítulo)"):
                self.assertIn(ov_name, trk_inline)
                self.assertEqual(len(trk_inline[ov_name]["segments"]), 1)
                self.assertIn(trk_inline[ov_name]["segments"][0]["material_id"], mats_inline)
        finally:
            shutil.rmtree(tmpdir2, ignore_errors=True)

    def test_orphan_rescue_token_steal_intra_prefix_and_post_step_y(self):
        # A. ['para', 'que puedas', 'elegir'] under HARD_MAX_LINE_CHARS=13 rebalances to ['para que', 'puedas elegir']
        raw_para = [
            {"index": 0, "start": 20_070_000, "end": 20_330_000, "duration": 260_000, "text": "para", "words": _make_words([("para", 0, 260)])},
            {"index": 1, "start": 20_330_000, "end": 20_670_000, "duration": 340_000, "text": "que puedas", "words": _make_words([("que", 0, 140), ("puedas", 140, 340)])},
            {"index": 2, "start": 20_670_000, "end": 21_130_000, "duration": 460_000, "text": "elegir", "words": _make_words([("elegir", 0, 460)])},
        ]
        reb_para = rebalance_subtitle_segments(raw_para, max_chars=HARD_MAX_LINE_CHARS, max_words=3)
        self.assertEqual([it["text"] for it in reb_para], ["para que", "puedas elegir"])

        # B. 'Y 4' + 'Las famosas' with step 4 merges residual 'Y' into 'Y las famosas' on Top
        # C. Intra-segment 'actuar sobre 2 problemas' with highlight '2 problemas' keeps 'actuar sobre' together on Top
        specs = [
            {"text": "1 primer paso", "start": 1_000_000, "end": 2_000_000},
            {"text": "actuar sobre 2 problemas", "start": 14_000_000, "end": 15_500_000, "words": _make_words([("actuar", 0, 350), ("sobre", 350, 650), ("2", 650, 850), ("problemas", 850, 1500)])},
            {"text": "y 4", "start": 48_030_000, "end": 48_600_000, "words": _make_words([("y", 0, 200), ("4", 200, 570)])},
            {"text": "Las famosas", "start": 48_650_000, "end": 49_400_000, "words": _make_words([("Las", 0, 300), ("famosas", 300, 750)])},
        ]
        proj = _create_project(
            self.tmp_dir,
            [{
                "id": "TXT_0", "type": "text", "flag": 1, "name": "",
                "segments": [
                    {
                        "id": f"S_{i}", "material_id": f"M_{i}",
                        "target_timerange": {"start": s["start"], "duration": s["end"] - s["start"]},
                        "extra_material_refs": [],
                    }
                    for i, s in enumerate(specs)
                ],
            }],
            [
                {
                    "id": f"M_{i}", "type": "subtitle", "recognize_task_id": "asr",
                    "content": json.dumps({"text": s["text"], "styles": [{"range": [0, len(s["text"])]}]}),
                    "words": s.get("words") or _make_words([(w, k * 250, (k + 1) * 250) for k, w in enumerate(s["text"].split())]),
                }
                for i, s in enumerate(specs)
            ],
            duration=55_000_000,
        )

        styler = DualStyler.from_preset("gala")
        ai_payload = {
            "corrected_subtitles": [],
            "highlights": [{"phrase": "2 problemas", "tone": "normal"}],
        }
        step_dets = [
            {"number": 1, "start_index": 0, "end_index": 1},
            {"number": 4, "start_index": 2, "end_index": 3},
        ]
        with patch.object(OpenRouterClient, "process_subtitles", return_value=ai_payload), \
             patch.object(OpenRouterClient, "detect_step_numbers", return_value=step_dets):
            styler.auto_dual_process(proj, openrouter_key="test-key", min_pacing_sec=0.5, max_pacing_sec=100.0)

        mats = {m["id"]: json.loads(m["content"])["text"] for m in proj.data["materials"]["texts"]}
        text_tracks = [t for t in proj.data["tracks"] if t.get("type") == "text" and t.get("name") != STEP_BADGE_TRACK_NAME]
        top_texts = [mats[s["material_id"]] for s in text_tracks[0]["segments"]]
        bot_texts = [mats[s["material_id"]] for s in text_tracks[1]["segments"]]

        self.assertIn("actuar sobre", top_texts)
        self.assertIn("2 problemas", bot_texts)
        self.assertNotIn("y", [t.lower() for t in top_texts])
        self.assertTrue(any(t.lower() == "y las famosas" for t in top_texts), f"Expected merged 'y las famosas' in {top_texts}")

    def test_elastic_2_word_pairs_and_cross_segment_clauses(self):
        # 2-word natural pairs up to 16 chars stay intact; 3+ words > 13 still split
        for pair in ("quiero hablarte", "energía térmica", "muchas gracias", "podemos trabajar"):
            seg = {"index": 0, "start": 0, "end": 1_200_000, "duration": 1_200_000, "text": pair}
            pieces = [p["text"] for p in split_wide_segment_for_safe_margins(seg)]
            self.assertEqual(pieces, [pair], f"2-word pair '{pair}' ({len(pair)}c) should stay unsplit")

        for dense3 in ("son muy populares", "sacar el máximo"):
            seg = {"index": 1, "start": 0, "end": 1_200_000, "duration": 1_200_000, "text": dense3}
            pieces = [p["text"] for p in split_wide_segment_for_safe_margins(seg)]
            self.assertGreater(len(pieces), 1, f"3-word line '{dense3}' must still split")
            for p in pieces:
                if len(p.split()) > 1:
                    self.assertLessEqual(len(p), 13)

        # Compound relative opener: 'causas por las' + 'que un niño' -> ['causas', 'por las que', 'un niño']
        raw_rel = [
            {"index": 0, "start": 0, "end": 800_000, "duration": 800_000, "text": "causas por las", "words": _make_words([("causas", 0, 350), ("por", 350, 550), ("las", 550, 800)])},
            {"index": 1, "start": 800_000, "end": 1_600_000, "duration": 800_000, "text": "que un niño", "words": _make_words([("que", 0, 200), ("un", 200, 400), ("niño", 400, 800)])},
        ]
        self.assertEqual([it["text"] for it in rebalance_subtitle_segments(raw_rel)], ["causas", "por las que", "un niño"])

        # Verbal periphrasis: 'los que tienen' + 'que trabajar' -> ['los que', 'tienen que', 'trabajar']
        raw_peri = [
            {"index": 0, "start": 0, "end": 900_000, "duration": 900_000, "text": "los que tienen", "words": _make_words([("los", 0, 250), ("que", 250, 450), ("tienen", 450, 900)])},
            {"index": 1, "start": 900_000, "end": 1_800_000, "duration": 900_000, "text": "que trabajar", "words": _make_words([("que", 0, 250), ("trabajar", 250, 900)])},
        ]
        self.assertEqual([it["text"] for it in rebalance_subtitle_segments(raw_peri)], ["los que", "tienen que", "trabajar"])

    def test_highlight_weak_filter_allows_intentional_repeat(self):
        for weak in ("bastante", "montón", "diferentes", "intentar"):
            self.assertEqual(sanitize_highlight_phrase(weak), "", f"Weak word '{weak}' must be rejected")
        self.assertEqual(sanitize_highlight_phrase("diferentes accesorios"), "accesorios")

        # Intentional AI-chosen repeat of 'sofá' within <20s must be allowed without forced cooldown
        specs = [
            {"text": "en tu sofá", "start": 500_000, "end": 1_500_000},
            {"text": "con este sofá", "start": 10_000_000, "end": 11_000_000},
        ]
        proj = _create_project(
            self.tmp_dir,
            [{
                "id": "TXT_0", "type": "text", "flag": 1, "name": "",
                "segments": [
                    {"id": f"S_{i}", "material_id": f"M_{i}", "target_timerange": {"start": s["start"], "duration": s["end"] - s["start"]}, "extra_material_refs": []}
                    for i, s in enumerate(specs)
                ],
            }],
            [
                {
                    "id": f"M_{i}", "type": "subtitle", "recognize_task_id": "asr",
                    "content": json.dumps({"text": s["text"], "styles": [{"range": [0, len(s["text"])]}]}),
                    "words": _make_words([(w, k * 300, (k + 1) * 300) for k, w in enumerate(s["text"].split())]),
                }
                for i, s in enumerate(specs)
            ],
            duration=20_000_000,
        )
        styler = DualStyler.from_preset("costa_calida")
        ai_payload = {
            "corrected_subtitles": [],
            "highlights": [
                {"phrase": "sofá", "tone": "normal"},
            ],
        }
        with patch.object(OpenRouterClient, "process_subtitles", return_value=ai_payload), \
             patch.object(OpenRouterClient, "detect_step_numbers", return_value=[]):
            styler.auto_dual_process(proj, openrouter_key="test-key", min_pacing_sec=1.0, max_pacing_sec=100.0)

        mats = {m["id"]: json.loads(m["content"])["text"] for m in proj.data["materials"]["texts"]}
        text_tracks = [t for t in proj.data["tracks"] if t.get("type") == "text"]
        bot_texts = [mats[s["material_id"]] for s in text_tracks[1]["segments"]]
        self.assertEqual([t.lower() for t in bot_texts], ["sofá", "sofá"])

    def test_step_headers_preserve_subject_ordinal_but_strip_standalone_ordinal_and_y_numero(self):
        raw_items = [
            {"index": 0, "start": 2_470_000, "end": 3_170_000, "duration": 700_000, "text": "El primero", "words": _make_words([("El", 0, 200), ("primero", 200, 700)])},
            {"index": 1, "start": 3_170_000, "end": 3_770_000, "duration": 600_000, "text": "es el típico"},
            {"index": 2, "start": 18_530_000, "end": 19_070_000, "duration": 540_000, "text": "Segundo", "words": _make_words([("Segundo", 0, 540)])},
            {"index": 3, "start": 19_070_000, "end": 20_070_000, "duration": 1_000_000, "text": "comprar el set"},
            {"index": 4, "start": 48_030_000, "end": 48_600_000, "duration": 570_000, "text": "Y número cuatro", "words": _make_words([("Y", 0, 120), ("número", 120, 320), ("cuatro", 320, 570)])},
            {"index": 5, "start": 48_600_000, "end": 49_400_000, "duration": 800_000, "text": "las famosas"},
        ]
        detections = [
            {"number": 1, "start_index": 0, "end_index": 1},
            {"number": 2, "start_index": 2, "end_index": 3},
            {"number": 4, "start_index": 4, "end_index": 5},
        ]
        cleaned, step_plan, _ = DualStyler._prepare_step_numbers_and_clean_items(raw_items, detections)
        texts = [it["text"] for it in cleaned]

        self.assertIn("El primero", texts)
        self.assertNotIn("Segundo", texts)
        self.assertIn("Comprar el set", texts)
        self.assertNotIn("Y número cuatro", texts)
        self.assertIn("Las famosas", texts)
        self.assertEqual([s["start"] for s in step_plan], [2_470_000, 18_530_000, 48_350_000])

    def test_grammar_checker_ignores_outer_whitespace_only_diff(self):
        proj = _create_project(
            self.tmp_dir,
            [{
                "id": "T_0", "type": "text", "flag": 1, "name": "",
                "segments": [{
                    "id": "S_0", "material_id": "M_0",
                    "target_timerange": {"start": 0, "duration": 1_000_000},
                    "extra_material_refs": [],
                }],
            }],
            [{
                "id": "M_0", "type": "subtitle", "recognize_task_id": "asr",
                "content": json.dumps({"text": "que yo ", "styles": [{"range": [0, 7]}]}),
                "words": {"start_time": [0, 400], "end_time": [400, 1000], "text": ["que", "yo"]},
            }],
        )
        mock_reply = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "corrections": [{"index": 0, "corrected_text": "que yo", "reason": "Espacio extra al final"}]
                    })
                }
            }]
        }
        client = OpenRouterClient(api_key="test-key")
        with patch("urllib.request.urlopen", return_value=_DummyHTTPResponse(mock_reply)):
            fixes = check_project_grammar(proj, client=client, preset_name="gerardo")
        self.assertEqual(fixes, [])


if __name__ == "__main__":
    unittest.main()
