# -*- coding: utf-8 -*-
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from ai.openrouter_client import OpenRouterClient
from core.capcut_draft import CapCutProject
from core.dual_styler import DualStyler
from core.text_utils import (
    measure_visual_width_ratio,
    rebalance_subtitle_segments,
    split_wide_segment_for_safe_margins,
)


def _make_words_block(word_specs):
    """Build CapCut words dict from list of (word, rel_start_ms, rel_end_ms)."""
    w_text, w_start, w_end = [], [], []
    for i, (w, st, et) in enumerate(word_specs):
        if i > 0:
            prev_et = word_specs[i - 1][2]
            w_text.append(" ")
            w_start.append(prev_et)
            w_end.append(st)
        w_text.append(w)
        w_start.append(st)
        w_end.append(et)
    return {"text": w_text, "start_time": w_start, "end_time": w_end}


class TestGala12Regressions(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_draft(self, segments_spec, duration=30000000):
        texts = []
        segs = []
        for idx, spec in enumerate(segments_spec):
            mat_id = f"MAT_{idx}"
            mat = {
                "id": mat_id,
                "content": json.dumps({"text": spec["text"], "styles": []}),
                "type": "subtitle",
            }
            if spec.get("words"):
                mat["words"] = spec["words"]
            texts.append(mat)
            segs.append({
                "id": f"SEG_{idx}",
                "material_id": mat_id,
                "target_timerange": {
                    "start": spec["start"],
                    "duration": spec["end"] - spec["start"],
                },
            })
        draft = {
            "canvas_config": {"height": 1920, "ratio": "9:16", "width": 1080},
            "duration": duration,
            "fps": 30.0,
            "materials": {"texts": texts, "audios": [], "sound_channel_mappings": [], "speeds": []},
            "tracks": [{"id": "TRK_0", "type": "text", "segments": segs}],
        }
        with open(os.path.join(self.tmp_dir, "draft_content.json"), "w", encoding="utf-8") as f:
            json.dump(draft, f, ensure_ascii=False)
        return CapCutProject(self.tmp_dir)

    def test_digits_never_merge_into_adjacent_segments(self):
        raw_items = [
            {"index": 0, "start": 4333000, "end": 5066000, "duration": 733000, "text": "de las señales"},
            {"index": 1, "start": 5066000, "end": 5267000, "duration": 201000, "text": "1"},
            {"index": 2, "start": 5300000, "end": 6500000, "duration": 1200000, "text": "notas un bulto"},
            {"index": 3, "start": 18300000, "end": 18466000, "duration": 166000, "text": "hidratar"},
            {"index": 4, "start": 18466000, "end": 18600000, "duration": 134000, "text": "4"},
            {"index": 5, "start": 18650000, "end": 19500000, "duration": 850000, "text": "tienes bolsas"},
        ]
        rebalanced = rebalance_subtitle_segments(raw_items, max_chars=18, max_words=3)
        texts = [it["text"] for it in rebalanced]
        self.assertIn("1", texts)
        self.assertIn("4", texts)
        self.assertNotIn("de las señales 1", texts)
        self.assertNotIn("hidratar 4", texts)

    def test_orphan_merge_blocks_aunque_hayas_dormido_exceeding_max_chars(self):
        raw_items = [
            {"index": 0, "start": 11067000, "end": 11500000, "duration": 433000, "text": "aunque"},
            {"index": 1, "start": 11500000, "end": 12900000, "duration": 1400000, "text": "hayas dormido"},
        ]
        rebalanced = rebalance_subtitle_segments(raw_items, max_chars=18, max_words=3)
        self.assertEqual([it["text"] for it in rebalanced], ["aunque", "hayas dormido"])

    def test_split_wide_segment_for_safe_margins_preserves_word_timings(self):
        seg_que_no = {
            "index": 0,
            "start": 21633000,
            "end": 22900000,
            "duration": 1267000,
            "text": "que no desaparecen",
            "words": _make_words_block([
                ("que", 0, 180),
                ("no", 180, 367),
                ("desaparecen", 367, 1267),
            ]),
        }
        split_q = split_wide_segment_for_safe_margins(seg_que_no, max_chars=18, font_path="Helvetica Regular.otf")
        self.assertEqual([p["text"] for p in split_q], ["que no", "desaparecen"])
        self.assertEqual(split_q[0]["start"], 21633000)
        self.assertEqual(split_q[1]["start"], 21633000 + 367000)
        self.assertEqual(split_q[1]["end"], 22900000)

        seg_aunque = {
            "index": 1,
            "start": 11067000,
            "end": 12900000,
            "duration": 1833000,
            "text": "aunque hayas dormido",
            "words": _make_words_block([
                ("aunque", 0, 350),
                ("hayas", 350, 700),
                ("dormido", 700, 1833),
            ]),
        }
        split_a = split_wide_segment_for_safe_margins(seg_aunque, max_chars=18, font_path="Helvetica Regular.otf")
        self.assertEqual([p["text"] for p in split_a], ["aunque hayas", "dormido"])
        self.assertEqual(split_a[1]["start"], 11067000 + 700000)

        seg_blefa = {"index": 2, "start": 0, "end": 1000000, "duration": 1000000, "text": "una blefaroplastia"}
        self.assertEqual(
            [p["text"] for p in split_wide_segment_for_safe_margins(seg_blefa, max_chars=18, font_path="Helvetica Regular.otf")],
            ["una blefaroplastia"],
        )

    def test_step_number_stripping_exact_onset_and_text_delay(self):
        raw_items = [
            {
                "index": 0, "start": 4333000, "end": 5267000, "duration": 934000,
                "text": "de las señales 1",
                "words": _make_words_block([("de", 0, 150), ("las", 150, 320), ("señales", 320, 733), ("1", 733, 934)]),
            },
            {"index": 1, "start": 5300000, "end": 6500000, "duration": 1200000, "text": "notas un bulto"},
            {
                "index": 2, "start": 9967000, "end": 11067000, "duration": 1100000,
                "text": "2 siempre",
                "words": _make_words_block([("2", 0, 200), ("siempre", 720, 1080)]),
            },
            {
                "index": 3, "start": 14267000, "end": 16200000, "duration": 1933000,
                "text": "3 te cuesta",
                "words": _make_words_block([("3", 0, 160), ("te", 760, 800), ("cuesta", 800, 1933)]),
            },
            {
                "index": 4, "start": 18300000, "end": 18466000, "duration": 166000,
                "text": "hidratar",
            },
            {"index": 5, "start": 18466000, "end": 18600000, "duration": 134000, "text": "4"},
            {"index": 6, "start": 18650000, "end": 19500000, "duration": 850000, "text": "tienes bolsas"},
            {
                "index": 7, "start": 24133000, "end": 25000000, "duration": 867000,
                "text": "y 5",
                "words": _make_words_block([("y", 0, 300), ("5", 450, 867)]),
            },
            {"index": 8, "start": 25000000, "end": 26500000, "duration": 1500000, "text": "quieres verte mejor"},
        ]
        detections = [
            # Even if AI puts start_index on 'de las señales 1', token onset is 5.066s;
            # Even if AI puts start_index on 'hidratar' before '4', snaps to '4' at 18.466s.
            {"number": 1, "start_index": 0, "end_index": 1},
            {"number": 2, "start_index": 2, "end_index": 2},
            {"number": 3, "start_index": 3, "end_index": 3},
            {"number": 4, "start_index": 4, "end_index": 6},
            {"number": 5, "start_index": 7, "end_index": 8},
        ]

        cleaned, step_plan, stripped = DualStyler._prepare_step_numbers_and_clean_items(raw_items, detections)
        self.assertEqual([s["number"] for s in step_plan], ["1", "2", "3", "4", "5"])
        self.assertEqual(step_plan[0]["start"], 5066000)
        self.assertEqual(step_plan[1]["start"], 9967000)
        self.assertEqual(step_plan[2]["start"], 14267000)
        self.assertEqual(step_plan[3]["start"], 18466000)
        self.assertEqual(step_plan[2]["end"], 18466000)  # Step 3 chains right up to Step 4 token onset
        self.assertEqual(step_plan[4]["start"], 24133000 + 450000)

        by_text = {it["text"]: it for it in cleaned}
        self.assertIn("de las señales", by_text)
        self.assertEqual(by_text["de las señales"]["end"], 5066000)
        self.assertIn("Notas un bulto", by_text)
        self.assertIn("Siempre", by_text)
        self.assertEqual(by_text["Siempre"]["start"], 10687000)
        self.assertIn("Te cuesta", by_text)
        self.assertEqual(by_text["Te cuesta"]["start"], 15027000)
        self.assertNotIn("4", by_text)
        self.assertIn("Tienes bolsas", by_text)
        self.assertIn("y", by_text)
        # Word right after proclitic 'y' must remain lowercase
        self.assertIn("quieres verte mejor", by_text)
        self.assertTrue({"1", "2", "3", "4", "5"}.issubset(stripped))

    def test_step_guards_never_strip_ordinals_or_quantities(self):
        raw_items = [
            {"index": 0, "start": 0, "end": 1000000, "duration": 1000000, "text": "Primero exfoliante"},
            {"index": 1, "start": 1000000, "end": 2000000, "duration": 1000000, "text": "1 o 2 veces"},
            {"index": 2, "start": 2000000, "end": 3000000, "duration": 1000000, "text": "Paso 2 hidratar"},
            {"index": 3, "start": 3000000, "end": 4000000, "duration": 1000000, "text": "Tercero protector"},
        ]
        detections = [
            {"number": 1, "start_index": 0, "end_index": 1},
            {"number": 2, "start_index": 2, "end_index": 2},
            {"number": 3, "start_index": 3, "end_index": 3},
        ]
        cleaned, _, stripped = DualStyler._prepare_step_numbers_and_clean_items(raw_items, detections)
        self.assertEqual([it["text"] for it in cleaned], [it["text"] for it in raw_items])
        self.assertEqual(stripped, set())

    def test_end_to_end_gala_preset_safe_margins_step_delay_and_orphan_bot_y(self):
        proj = self._create_draft([
            {
                "text": "de las señales 1", "start": 4333000, "end": 5267000,
                "words": _make_words_block([("de", 0, 150), ("las", 150, 320), ("señales", 320, 733), ("1", 733, 934)]),
            },
            {"text": "notas un bulto", "start": 5300000, "end": 6500000},
            {
                "text": "2 siempre", "start": 9967000, "end": 11067000,
                "words": _make_words_block([("2", 0, 200), ("siempre", 720, 1080)]),
            },
            {
                "text": "aunque hayas dormido", "start": 11067000, "end": 12900000,
                "words": _make_words_block([("aunque", 0, 350), ("hayas", 350, 700), ("dormido", 700, 1833)]),
            },
            {
                "text": "3 te cuesta", "start": 14267000, "end": 15567000,
                "words": _make_words_block([("3", 0, 160), ("te", 760, 800), ("cuesta", 800, 1300)]),
            },
            {
                "text": "que no desaparecen", "start": 21633000, "end": 22900000,
                "words": _make_words_block([("que", 0, 180), ("no", 180, 367), ("desaparecen", 367, 1267)]),
            },
            {
                "text": "y 5", "start": 23500000, "end": 24100000,
                "words": _make_words_block([("y", 0, 180), ("5", 300, 600)]),
            },
            # Gap > 300ms before 'quieres verte' so 'y' does not extend under it
            {"text": "quieres verte", "start": 24500000, "end": 25500000},
            {"text": "en clínica", "start": 26500000, "end": 27000000},
            {"text": "Gala Unique", "start": 27000000, "end": 27800000},
        ])

        ai_payload = {
            "corrected_subtitles": [],
            "highlights": [
                {"phrase": "quieres verte", "tone": "normal"},
            ],
        }
        step_detections = [
            {"number": 1, "start_index": 0, "end_index": 1},
            {"number": 2, "start_index": 2, "end_index": 3},
            {"number": 3, "start_index": 4, "end_index": 5},
            {"number": 5, "start_index": 6, "end_index": 7},
        ]

        styler = DualStyler.from_preset("gala")
        with patch.object(OpenRouterClient, "process_subtitles", return_value=ai_payload), \
             patch.object(OpenRouterClient, "detect_step_numbers", return_value=step_detections):
            styler.auto_dual_process(proj, openrouter_key="test-key", min_pacing_sec=0.1, max_pacing_sec=100.0)

        texts = {m["id"]: json.loads(m["content"])["text"] for m in proj.data["materials"]["texts"]}
        tracks = {t.get("name"): t for t in proj.data["tracks"]}
        text_tracks = [t for t in proj.data["tracks"] if t.get("type") == "text"]
        top_segs = text_tracks[0]["segments"]
        bot_segs = text_tracks[1]["segments"]
        pasos_segs = tracks["Pasos"]["segments"]

        top_texts = [texts[s["material_id"]] for s in top_segs]
        bot_texts = [texts[s["material_id"]] for s in bot_segs]

        self.assertEqual([texts[s["material_id"]] for s in pasos_segs], ["1", "2", "3", "5"])
        self.assertEqual(pasos_segs[0]["target_timerange"]["start"], 5066000)

        self.assertIn("Siempre", top_texts)
        self.assertIn("Te cuesta", top_texts)
        self.assertNotIn("2 siempre", top_texts)
        self.assertNotIn("3 te cuesta", top_texts)

        # Delayed start verification
        siempre_seg = next(s for s in top_segs if texts[s["material_id"]] == "Siempre")
        self.assertEqual(siempre_seg["target_timerange"]["start"], 10687000)
        te_cuesta_seg = next(s for s in top_segs if texts[s["material_id"]] == "Te cuesta")
        self.assertEqual(te_cuesta_seg["target_timerange"]["start"], 15027000)

        # Safe margin splits verification
        self.assertIn("aunque hayas", top_texts)
        self.assertIn("dormido", top_texts)
        self.assertIn("que no", top_texts)
        self.assertIn("desaparecen", top_texts)
        for tt in top_texts:
            self.assertLessEqual(
                measure_visual_width_ratio(tt, "Helvetica Regular.otf", 18),
                1.085,
                f"Segment '{tt}' still exceeds visual safe margin",
            )

        # Orphan bot highlight ('quieres verte') moves to y_top while paired 'Gala Unique' stays y_bottom
        quieres_seg = next(s for s in bot_segs if texts[s["material_id"]] == "quieres verte")
        gala_seg = next(s for s in bot_segs if texts[s["material_id"]] == "Gala Unique")
        self.assertAlmostEqual(quieres_seg["clip"]["transform"]["y"], styler.y_top, places=5)
        self.assertAlmostEqual(gala_seg["clip"]["transform"]["y"], styler.y_bottom, places=5)
        self.assertIn("quieres verte", bot_texts)
        self.assertIn("Gala Unique", bot_texts)

    def test_contiguous_bare_y_does_not_trap_orphan_bot_and_giant_single_word_scales(self):
        proj = self._create_draft([
            {"text": "1 señales", "start": 1000000, "end": 2000000},
            {
                "text": "y 2", "start": 23330000, "end": 24400000,
                "words": _make_words_block([("y", 0, 180), ("2", 300, 1070)]),
            },
            # Contiguous 0ms after 'y 2' just like Gala meta 12
            {"text": "quieres verte", "start": 24400000, "end": 25000000},
            {"text": "esternocleidomastoideolargo", "start": 25200000, "end": 26500000},
        ])
        ai_payload = {
            "corrected_subtitles": [],
            "highlights": [{"phrase": "quieres verte", "tone": "normal"}],
        }
        step_detections = [
            {"number": 1, "start_index": 0, "end_index": 0},
            {"number": 2, "start_index": 1, "end_index": 2},
        ]
        styler = DualStyler.from_preset("gala")
        with patch.object(OpenRouterClient, "process_subtitles", return_value=ai_payload), \
             patch.object(OpenRouterClient, "detect_step_numbers", return_value=step_detections):
            styler.auto_dual_process(proj, openrouter_key="test-key", min_pacing_sec=0.1, max_pacing_sec=100.0)

        texts = {m["id"]: json.loads(m["content"])["text"] for m in proj.data["materials"]["texts"]}
        text_tracks = [t for t in proj.data["tracks"] if t.get("type") == "text"]
        top_segs = text_tracks[0]["segments"]
        bot_segs = text_tracks[1]["segments"]

        quieres_seg = next(s for s in bot_segs if texts[s["material_id"]] == "quieres verte")
        self.assertAlmostEqual(quieres_seg["clip"]["transform"]["y"], styler.y_top, places=5)

        giant_seg = next(s for s in top_segs if texts[s["material_id"]] == "esternocleidomastoideolargo")
        self.assertLess(giant_seg["clip"]["scale"]["x"], styler.top_scale["x"])

    def test_balanced_max_three_words_and_long_phrase_splitting(self):
        # 4+ word long phrases split cleanly without stranding functional clitics
        seg_proteger = {
            "index": 0, "start": 25990000, "end": 27270000, "duration": 1280000,
            "text": "para proteger tu piel",
            "words": _make_words_block([("para", 0, 380), ("proteger", 380, 580), ("tu", 740, 900), ("piel", 900, 1280)]),
        }
        self.assertEqual(
            [p["text"] for p in split_wide_segment_for_safe_margins(seg_proteger, max_chars=18, max_words=3, font_path="Helvetica Regular.otf")],
            ["para proteger", "tu piel"],
        )
        self.assertEqual(
            [p["text"] for p in split_wide_segment_for_safe_margins(seg_proteger, max_chars=18, max_words=3, font_path="GC GRIND.otf")],
            ["para proteger", "tu piel"],
        )

        # Heavy 3-word lines split down to 2, while compact 3/4-word lines keep natural pacing
        seg_heavy3 = {"index": 1, "start": 0, "end": 1200000, "duration": 1200000, "text": "Cuando no duermes"}
        self.assertEqual(
            [p["text"] for p in split_wide_segment_for_safe_margins(seg_heavy3, max_chars=18, max_words=3, font_path="GC GRIND.otf")],
            ["Cuando no", "duermes"],
        )

        seg_ok3 = {"index": 2, "start": 0, "end": 1000000, "duration": 1000000, "text": "no es importante"}
        self.assertEqual(
            [p["text"] for p in split_wide_segment_for_safe_margins(seg_ok3, max_chars=18, max_words=3, font_path="GC GRIND.otf")],
            ["no es importante"],
        )

        seg_ok4 = {"index": 3, "start": 0, "end": 1000000, "duration": 1000000, "text": "Esto sí que es"}
        self.assertEqual(
            [p["text"] for p in split_wide_segment_for_safe_margins(seg_ok4, max_chars=18, max_words=3, font_path="GC GRIND.otf")],
            ["Esto sí que es"],
        )

    def test_alvaro_callo_solar_para_proteger_tu_piel_and_mid_sentence_esto(self):
        proj = self._create_draft([
            {
                "text": "poco a poco Esto", "start": 21900000, "end": 23800000,
                "words": _make_words_block([("poco", 0, 160), ("a", 160, 280), ("poco", 320, 520), ("Esto", 520, 1900)]),
            },
            {
                "text": "sí que es importante", "start": 23800000, "end": 24830000,
                "words": _make_words_block([("sí", 0, 150), ("que", 150, 300), ("es", 300, 450), ("importante", 450, 1030)]),
            },
            {
                "text": "callo solar para", "start": 25467000, "end": 26367000,
                "words": _make_words_block([("callo", 0, 200), ("solar", 240, 520), ("para", 640, 900)]),
            },
            {
                "text": "proteger tu piel", "start": 26367000, "end": 27270000,
                "words": _make_words_block([("proteger", 0, 200), ("tu", 360, 440), ("piel", 440, 880)]),
            },
            {"text": "eso es", "start": 27270000, "end": 28000000},
        ])
        ai_payload = {
            "corrected_subtitles": [],
            "highlights": [
                {"phrase": "importante", "tone": "normal"},
                {"phrase": "solar", "tone": "normal"},
            ],
        }
        styler = DualStyler.from_preset("alvaro")
        with patch.object(OpenRouterClient, "process_subtitles", return_value=ai_payload), \
             patch.object(OpenRouterClient, "detect_step_numbers", return_value=[]):
            styler.auto_dual_process(proj, openrouter_key="test-key", min_pacing_sec=0.1, max_pacing_sec=100.0)

        texts = {m["id"]: json.loads(m["content"])["text"] for m in proj.data["materials"]["texts"]}
        text_tracks = [t for t in proj.data["tracks"] if t.get("type") == "text"]
        top_texts = [texts[s["material_id"]] for s in text_tracks[0]["segments"]]

        self.assertIn("poco a poco", top_texts)
        self.assertIn("para proteger", top_texts)
        self.assertIn("tu piel", top_texts)
        self.assertNotIn("para proteger tu piel", top_texts)
        self.assertIn("eso es", top_texts)
        self.assertLess(top_texts.index("para proteger"), top_texts.index("tu piel"))
        self.assertLess(top_texts.index("tu piel"), top_texts.index("eso es"))

    def test_rejects_weak_filler_highlights_like_creo_and_prefers_meaningful_terms(self):
        from ai.highlighter import AIHighlighter
        from core.text_utils import sanitize_highlight_phrase

        for weak in ("creo", "yo creo", "francamente", "en este caso", "bueno", "poquito", "debido", "usar", "palabra"):
            self.assertEqual(sanitize_highlight_phrase(weak, max_chars=18), "", f"Weak filler '{weak}' should be rejected")

        for strong in ("lifting", "piel", "destrozado", "anatomía", "perforación", "médico", "desastre", "clave", "Primero", "sabías"):
            self.assertTrue(sanitize_highlight_phrase(strong, max_chars=18), f"Valid keyword '{strong}' should stay allowed")

        hl = AIHighlighter(provider="heuristic")
        suggested = hl.suggest_highlights("bueno en este caso francamente yo creo que es un lifting muy exagerado con mucha piel lateral y han destrozado el ojo", count=8)
        suggested_low = {s.lower() for s in suggested}
        self.assertFalse(suggested_low & {"creo", "bueno", "caso", "francamente", "este", "mucha"})
        self.assertTrue(suggested_low & {"lifting", "destrozado", "piel", "exagerado"})

        # End-to-end Gala 18 opening: both offline fallback and sanitized AI must never highlight 'creo'
        for bad_ai in (
            None,
            {"corrected_subtitles": [], "highlights": [{"phrase": "creo", "tone": "normal"}, {"phrase": "destrozado", "tone": "negative"}]},
        ):
            proj = self._create_draft([
                {"text": "bueno", "start": 230000, "end": 470000},
                {"text": "en este caso", "start": 470000, "end": 1170000},
                {"text": "francamente", "start": 1170000, "end": 1970000},
                {"text": "yo creo que", "start": 1970000, "end": 2270000},
                {"text": "es un lifting", "start": 2700000, "end": 3570000},
                {"text": "y han destrozado", "start": 9470000, "end": 10800000},
            ])
            styler = DualStyler.from_preset("gala")
            if bad_ai is None:
                styler.auto_dual_process(proj)
            else:
                with patch.object(OpenRouterClient, "process_subtitles", return_value=bad_ai), \
                     patch.object(OpenRouterClient, "detect_step_numbers", return_value=[]):
                    styler.auto_dual_process(proj, openrouter_key="test-key")

            texts = {m["id"]: json.loads(m["content"])["text"].lower() for m in proj.data["materials"]["texts"]}
            text_tracks = [t for t in proj.data["tracks"] if t.get("type") == "text"]
            bot_texts = [texts[s["material_id"]] for s in text_tracks[1]["segments"]]
            all_render_texts = [texts[s["material_id"]] for tr in text_tracks for s in tr["segments"] if tr is not text_tracks[0]]
            self.assertNotIn("creo", bot_texts)
            self.assertNotIn("creo", all_render_texts)
            self.assertTrue(any("destrozado" in bt or "lifting" in bt for bt in bot_texts), f"Expected meaningful highlight, got {bot_texts}")


if __name__ == "__main__":
    unittest.main()
