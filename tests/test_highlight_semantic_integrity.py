# -*- coding: utf-8 -*-
import unittest
import os
import json
import tempfile
import shutil

from core.text_utils import sanitize_highlight_phrase, clean_subtitle_text
from core.dual_styler import DualStyler
from core.capcut_draft import CapCutProject


class TestHighlightSemanticIntegrity(unittest.TestCase):
    def test_sanitize_highlight_phrase(self):
        # 1. Invalid trailing verbs must be stripped
        self.assertEqual(sanitize_highlight_phrase("lingual forman"), "lingual")
        self.assertEqual(sanitize_highlight_phrase("bebé come"), "bebé")
        self.assertEqual(sanitize_highlight_phrase("paciente siente"), "paciente")
        self.assertEqual(sanitize_highlight_phrase("niño duerme"), "niño")
        self.assertEqual(sanitize_highlight_phrase("madre llora"), "madre")
        self.assertEqual(sanitize_highlight_phrase("lengua tienen"), "lengua")

        # 2. Invalid trailing connectors, conjunctions, relatives, prepositions must be stripped
        self.assertEqual(sanitize_highlight_phrase("dolor cuando"), "dolor")
        self.assertEqual(sanitize_highlight_phrase("problema que"), "problema")
        self.assertEqual(sanitize_highlight_phrase("cirugía pero"), "cirugía")
        self.assertEqual(sanitize_highlight_phrase("tratamiento para"), "tratamiento")
        self.assertEqual(sanitize_highlight_phrase("ojo si"), "ojo")
        self.assertEqual(sanitize_highlight_phrase("artrosis porque"), "artrosis")

        # 3. Leading articles in valid phrases must be preserved
        self.assertEqual(sanitize_highlight_phrase("un congreso"), "un congreso")
        self.assertEqual(sanitize_highlight_phrase("la movilidad"), "la movilidad")
        self.assertEqual(sanitize_highlight_phrase("un problema"), "un problema")

        # 4. Valid multi-word noun / adjective compounds must be PRESERVED
        self.assertEqual(sanitize_highlight_phrase("suelo pélvico"), "suelo pélvico")
        self.assertEqual(sanitize_highlight_phrase("movilidad lingual"), "movilidad lingual")
        self.assertEqual(sanitize_highlight_phrase("alta demanda"), "alta demanda")
        self.assertEqual(sanitize_highlight_phrase("primeros meses"), "primeros meses")
        self.assertEqual(sanitize_highlight_phrase("frenillo corto"), "frenillo corto")

        # 5. Single words must be preserved
        self.assertEqual(sanitize_highlight_phrase("lingual"), "lingual")
        self.assertEqual(sanitize_highlight_phrase("dolor"), "dolor")

        # 6. Connectors and conjunctions must be completely rejected if alone
        self.assertEqual(sanitize_highlight_phrase("porque"), "")
        self.assertEqual(sanitize_highlight_phrase("Porque"), "")
        self.assertEqual(sanitize_highlight_phrase("pero"), "")
        self.assertEqual(sanitize_highlight_phrase("cuando"), "")
        self.assertEqual(sanitize_highlight_phrase("donde"), "")
        self.assertEqual(sanitize_highlight_phrase("mientras"), "")
        self.assertEqual(sanitize_highlight_phrase("pues"), "")
        self.assertEqual(sanitize_highlight_phrase("y"), "")

        # 7. Short/empty words ('no', 'el', 'o', 'asi', etc.) must NEVER be highlighted alone
        self.assertEqual(sanitize_highlight_phrase("no"), "")
        self.assertEqual(sanitize_highlight_phrase("No"), "")
        self.assertEqual(sanitize_highlight_phrase("el"), "")
        self.assertEqual(sanitize_highlight_phrase("la"), "")
        self.assertEqual(sanitize_highlight_phrase("o"), "")
        self.assertEqual(sanitize_highlight_phrase("asi"), "")
        self.assertEqual(sanitize_highlight_phrase("así"), "")
        self.assertEqual(sanitize_highlight_phrase("de"), "")
        self.assertEqual(sanitize_highlight_phrase("en"), "")
        self.assertEqual(sanitize_highlight_phrase("un"), "")
        self.assertEqual(sanitize_highlight_phrase("se"), "")

        # 8. Leading connectors and negations must be stripped from multi-word phrases
        self.assertEqual(sanitize_highlight_phrase("porque una madre"), "una madre")
        self.assertEqual(sanitize_highlight_phrase("pero un gran dolor"), "un gran dolor")
        self.assertEqual(sanitize_highlight_phrase("cuando el bebé"), "el bebé")
        self.assertEqual(sanitize_highlight_phrase("no improvisas"), "improvisas")

        # 9. Punctuation must be stripped
        self.assertEqual(sanitize_highlight_phrase("lingual, forman."), "lingual")


class TestDualStylerHighlightSeparation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.draft_file = os.path.join(self.test_dir, 'draft_content.json')

        draft_content = {
            "canvas_config": {"height": 1920, "ratio": "original", "width": 1080},
            "duration": 5000000,
            "fps": 30.0,
            "materials": {
                "texts": [
                    {
                        "id": "MAT_0",
                        "content": json.dumps({"text": "la movilidad", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 400], "end_time": [400, 1000], "text": ["la", "movilidad"]}
                    },
                    {
                        "id": "MAT_1",
                        "content": json.dumps({"text": "lingual forman", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 500], "end_time": [500, 1200], "text": ["lingual", "forman"]}
                    },
                    {
                        "id": "MAT_2",
                        "content": json.dumps({"text": "parte del equilibrio", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 400, 800], "end_time": [400, 800, 1500], "text": ["parte", "del", "equilibrio"]}
                    }
                ]
            },
            "tracks": [
                {
                    "id": "TRK_TEXT",
                    "type": "text",
                    "segments": [
                        {"id": "SEG_0", "material_id": "MAT_0", "target_timerange": {"start": 0, "duration": 1000000}},
                        {"id": "SEG_1", "material_id": "MAT_1", "target_timerange": {"start": 1000000, "duration": 1200000}},
                        {"id": "SEG_2", "material_id": "MAT_2", "target_timerange": {"start": 2200000, "duration": 1500000}}
                    ]
                }
            ]
        }

        with open(self.draft_file, 'w', encoding='utf-8') as f:
            json.dump(draft_content, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_auto_dual_process_never_swallows_suffix(self):
        class MockHL:
            def suggest_highlights(self, text, count=10):
                # Even if the highlighter returned 'lingual', or someone suggested 'lingual'
                return ["lingual"]

        styler = DualStyler.from_preset("cuidus")
        proj = CapCutProject(self.test_dir)
        top_c, bot_c = styler.auto_dual_process(proj, highlighter=MockHL(), min_pacing_sec=0.1)

        text_tracks = [t for t in proj.data['tracks'] if t.get('type') == 'text']
        self.assertEqual(len(text_tracks), 2)
        top_track, bot_track = text_tracks[0], text_tracks[1]
        texts = {m['id']: m for m in proj.data['materials']['texts']}

        # Verify bottom track has ONLY 'lingual', NEVER 'lingual forman'
        bot_texts = [json.loads(texts[seg['material_id']]['content'])['text'] for seg in bot_track['segments']]
        self.assertIn("lingual", bot_texts)
        self.assertNotIn("lingual forman", bot_texts)
        for bt in bot_texts:
            self.assertNotEqual(bt.lower(), "lingual forman")

        # Verify top track has 'la movilidad' and 'forman'
        top_texts = [json.loads(texts[seg['material_id']]['content'])['text'] for seg in top_track['segments']]
        self.assertIn("la movilidad", top_texts)
        self.assertIn("forman", top_texts)
        self.assertIn("parte del equilibrio", top_texts)

        # Verify no punctuation violations
        for t in list(texts.values()):
            c = json.loads(t['content'])['text']
            self.assertNotIn(",", c)
            self.assertNotIn(".", c)
            self.assertNotIn(":", c)

    def test_auto_dual_process_with_prefix_and_suffix(self):
        # Test segment: 'un gran dolor hoy' with highlight 'dolor'
        draft_content = {
            "canvas_config": {"height": 1920, "ratio": "original", "width": 1080},
            "duration": 3000000,
            "fps": 30.0,
            "materials": {
                "texts": [
                    {
                        "id": "MAT_0",
                        "content": json.dumps({"text": "un gran dolor hoy", "styles": []}),
                        "type": "subtitle",
                        "words": {
                            "start_time": [0, 300, 700, 1100],
                            "end_time": [300, 700, 1100, 1500],
                            "text": ["un gran", "dolor", "hoy"]
                        }
                    }
                ]
            },
            "tracks": [
                {
                    "id": "TRK_TEXT",
                    "type": "text",
                    "segments": [
                        {"id": "SEG_0", "material_id": "MAT_0", "target_timerange": {"start": 0, "duration": 1500000}}
                    ]
                }
            ]
        }

        with open(self.draft_file, 'w', encoding='utf-8') as f:
            json.dump(draft_content, f)

        class MockHL:
            def suggest_highlights(self, text, count=10):
                return ["dolor"]

        styler = DualStyler.from_preset("cuidus")
        proj = CapCutProject(self.test_dir)
        top_c, bot_c = styler.auto_dual_process(proj, highlighter=MockHL(), min_pacing_sec=0.1)

        text_tracks = [t for t in proj.data['tracks'] if t.get('type') == 'text']
        texts = {m['id']: m for m in proj.data['materials']['texts']}

        bot_texts = [json.loads(texts[seg['material_id']]['content'])['text'] for seg in text_tracks[1]['segments']]
        self.assertEqual(bot_texts, ["dolor"])

        top_texts = [json.loads(texts[seg['material_id']]['content'])['text'] for seg in text_tracks[0]['segments']]
        self.assertIn("un gran", top_texts)
        self.assertIn("hoy", top_texts)
        self.assertNotIn("un gran hoy", top_texts)

    def test_auto_dual_process_never_stretches_previous_sentence_across_boundary(self):
        # Scenario: Segment 0 is 'el bebé' (ends at 1.0s)
        # Segment 1 is 'porque una madre' (1.0s to 2.2s)
        draft_content = {
            "canvas_config": {"height": 1920, "ratio": "original", "width": 1080},
            "duration": 3000000,
            "fps": 30.0,
            "materials": {
                "texts": [
                    {
                        "id": "MAT_0",
                        "content": json.dumps({"text": "el bebé", "styles": []}),
                        "type": "subtitle",
                        "words": {
                            "start_time": [0, 400],
                            "end_time": [400, 1000],
                            "text": ["el", "bebé"]
                        }
                    },
                    {
                        "id": "MAT_1",
                        "content": json.dumps({"text": "porque una madre", "styles": []}),
                        "type": "subtitle",
                        "words": {
                            "start_time": [0, 400, 700],
                            "end_time": [400, 700, 1200],
                            "text": ["porque", "una", "madre"]
                        }
                    }
                ]
            },
            "tracks": [
                {
                    "id": "TRK_TEXT",
                    "type": "text",
                    "segments": [
                        {"id": "SEG_0", "material_id": "MAT_0", "target_timerange": {"start": 0, "duration": 1000000}},
                        {"id": "SEG_1", "material_id": "MAT_1", "target_timerange": {"start": 1000000, "duration": 1200000}}
                    ]
                }
            ]
        }

        with open(self.draft_file, 'w', encoding='utf-8') as f:
            json.dump(draft_content, f)

        class MockHL:
            def suggest_highlights(self, text, count=10):
                # Even if highlighter errantly suggested 'porque'
                return ["porque", "madre"]

        styler = DualStyler.from_preset("cuidus")
        proj = CapCutProject(self.test_dir)
        top_c, bot_c = styler.auto_dual_process(proj, highlighter=MockHL(), min_pacing_sec=0.1)

        text_tracks = [t for t in proj.data['tracks'] if t.get('type') == 'text']
        texts = {m['id']: m for m in proj.data['materials']['texts']}

        top_track = text_tracks[0]
        bot_track = text_tracks[1]

        # 1. 'porque' must NEVER be in bottom track
        bot_texts = [json.loads(texts[seg['material_id']]['content'])['text'] for seg in bot_track['segments']]
        self.assertNotIn("porque", bot_texts)
        self.assertNotIn("porque una", bot_texts)

        # 2. Segment 0 ('el bebé') on top track must NOT be stretched into segment 1!
        # It must end at or before 1000000 us (1.0s).
        seg0_top = top_track['segments'][0]
        seg0_content = json.loads(texts[seg0_top['material_id']]['content'])['text']
        self.assertEqual(seg0_content, "el bebé")
        seg0_end = seg0_top['target_timerange']['start'] + seg0_top['target_timerange']['duration']
        self.assertLessEqual(seg0_end, 1000000)

    def test_auto_dual_process_start_highlight_goes_to_top_track(self):
        # Scenario: Segment with highlight at the very start (no prefix)
        # e.g., 'pediatra amorosa' with highlight 'pediatra'
        draft_content = {
            "canvas_config": {"height": 1920, "ratio": "original", "width": 1080},
            "duration": 2000000,
            "fps": 30.0,
            "materials": {
                "texts": [
                    {
                        "id": "MAT_0",
                        "content": json.dumps({"text": "pediatra amorosa", "styles": []}),
                        "type": "subtitle",
                        "words": {
                            "start_time": [0, 600],
                            "end_time": [600, 1200],
                            "text": ["pediatra", "amorosa"]
                        }
                    }
                ]
            },
            "tracks": [
                {
                    "id": "TRK_TEXT",
                    "type": "text",
                    "segments": [
                        {"id": "SEG_0", "material_id": "MAT_0", "target_timerange": {"start": 0, "duration": 1200000}}
                    ]
                }
            ]
        }

        with open(self.draft_file, 'w', encoding='utf-8') as f:
            json.dump(draft_content, f)

        class MockHL:
            def suggest_highlights(self, text, count=10):
                return ["pediatra"]

        styler = DualStyler.from_preset("laura_burgos")
        proj = CapCutProject(self.test_dir)
        top_c, bot_c = styler.auto_dual_process(proj, highlighter=MockHL(), min_pacing_sec=0.1)

        text_tracks = [t for t in proj.data['tracks'] if t.get('type') == 'text']
        texts = {m['id']: m for m in proj.data['materials']['texts']}

        top_track = text_tracks[0]
        bot_track = text_tracks[1]

        # Bottom track should have 0 segments because highlight is at the start and placed on TOP track (solo)
        self.assertEqual(len(bot_track['segments']), 0)

        # Top track should have 'pediatra' (highlighted) and 'amorosa' (suffix)
        top_texts = [json.loads(texts[seg['material_id']]['content'])['text'] for seg in top_track['segments']]
        self.assertIn("pediatra", top_texts)
        self.assertIn("amorosa", top_texts)


if __name__ == '__main__':
    unittest.main()
