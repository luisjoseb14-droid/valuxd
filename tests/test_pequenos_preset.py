# -*- coding: utf-8 -*-
import unittest
import json
from core.capcut_draft import SubtitleItem
from core.dual_styler import DualStyler
from cc_subs_pro import resolve_preset
from core.text_utils import clean_subtitle_text

class TestPequenosPreset(unittest.TestCase):
    def test_preset_resolution(self):
        preset = resolve_preset("pequenos")
        self.assertTrue(preset, "Preset pequenos should resolve properly")
        self.assertEqual(preset.get("name"), "Letra de Pequeños Cuidados")
        
        # Verify fonts
        self.assertIn("Parafina", preset["top"]["font_name"])
        self.assertEqual(preset["top"]["font_path"], "Parafina Bold S.ttf")
        self.assertIn("Chewy", preset["bottom"]["font_name"])
        self.assertEqual(preset["bottom"]["font_path"], "Chewy-Regular.ttf")
        
        # Verify colors and positions
        self.assertEqual(preset["top"]["color"], "#FFFFFF")
        self.assertAlmostEqual(preset["top"]["y"], -0.1163, places=3)
        self.assertEqual(preset["bottom"]["color"], "#fee872")
        self.assertAlmostEqual(preset["bottom"]["y"], -0.2392, places=3)
        
        # Verify animation and audio click
        self.assertIn("animation", preset["bottom"])
        self.assertEqual(preset["bottom"]["animation"].get("name"), "Mini zoom")
        self.assertEqual(preset["bottom"]["animation"].get("resource_id"), "6763469998330483213")
        self.assertTrue(preset.get("sound_fx", {}).get("enabled"))
        self.assertEqual(preset["sound_fx"].get("name"), "Click_Mouse_Click_02(864360)")

    def test_preset_alias_resolution(self):
        aliases = [
            "pequenos_cuidados",
            "pequenos cuidados",
            "letra de pequenos cuidados",
            "letra de pequeños cuidados",
            "letra pequenos cuidados"
        ]
        for alias in aliases:
            p = resolve_preset(alias)
            self.assertTrue(p, f"Failed to resolve alias: {alias}")
            self.assertEqual(p.get("name"), "Letra de Pequeños Cuidados")

    def test_zero_forbidden_punctuation(self):
        preset = resolve_preset("pequenos")
        for text in [preset.get("name", ""), preset.get("description", "")]:
            cleaned = clean_subtitle_text(text)
            self.assertNotIn(",", cleaned)
            self.assertNotIn(".", cleaned)
            self.assertNotIn(":", cleaned)

    def test_dual_process_pequenos(self):
        styler = DualStyler.from_preset("pequenos")
        self.assertAlmostEqual(styler.y_top, -0.1163, places=3)
        self.assertAlmostEqual(styler.y_bottom, -0.2392, places=3)
        self.assertTrue(styler.sound_fx.get("enabled"))

        data = {
            "materials": {
                "texts": [
                    {
                        "id": "M1",
                        "content": json.dumps({"text": "fruta triturada", "styles": [{"range": [0, 15]}]}),
                        "words": {"start_time": [0, 400], "end_time": [350, 950], "text": ["fruta", "triturada"]}
                    }
                ]
            },
            "tracks": [
                {
                    "id": "T1",
                    "type": "text",
                    "segments": [
                        {"id": "S1", "material_id": "M1", "target_timerange": {"start": 0, "duration": 1000000}, "extra_material_refs": []}
                    ]
                }
            ]
        }

        class MockProject:
            def __init__(self, d):
                self.data = d
                self.subtitles = []
                texts = {t["id"]: t for t in d["materials"]["texts"]}
                for seg in d["tracks"][0]["segments"]:
                    self.subtitles.append(SubtitleItem(0, seg, texts[seg["material_id"]]))
            def _parse_subtitles(self):
                pass

        class MockHighlighter:
            def suggest_highlights(self, text, count=10):
                return ["triturada"]

        proj = MockProject(data)
        top_c, bot_c = styler.auto_dual_process(proj, highlighter=MockHighlighter(), min_pacing_sec=0.1)

        self.assertEqual(bot_c, 1)

        tracks = data["tracks"]
        text_tracks = [t for t in tracks if t["type"] == "text"]
        audio_tracks = [t for t in tracks if t.get("type") == "audio"]

        self.assertEqual(len(text_tracks), 2, "Should have 2 text tracks")
        self.assertEqual(len(audio_tracks), 1, "Should have 1 audio track for click sound")

        for mat in data["materials"]["texts"]:
            content = json.loads(mat["content"])
            self.assertNotIn(",", content.get("text", ""))
            self.assertNotIn(".", content.get("text", ""))
            self.assertNotIn(":", content.get("text", ""))

    def test_spanish_casing_corrections(self):
        # Glitch 1: Random title-casing mid-sentence
        self.assertEqual(clean_subtitle_text("y por qué Evita", is_sentence_start=False), "y por qué evita")
        self.assertEqual(clean_subtitle_text("para tu Pueblo", is_sentence_start=False), "para tu pueblo")
        
        # Glitch 2: Random ALL-CAPS words mid-sentence
        self.assertEqual(clean_subtitle_text("que DEBERÍAS", is_sentence_start=False), "que deberías")
        self.assertEqual(clean_subtitle_text("la gente ESTÁN hablando", is_sentence_start=False), "la gente están hablando")
        
        # Glitch 3: Sentence start capitalization & official acronym preservation
        self.assertEqual(clean_subtitle_text("ESTÁN en la UCI", is_sentence_start=True), "Están en la UCI")
        self.assertEqual(clean_subtitle_text("prueba de ADN", is_sentence_start=False), "prueba de ADN")
        self.assertEqual(clean_subtitle_text("pacientes con TDAH o COVID", is_sentence_start=False), "pacientes con TDAH o COVID")

    def test_highlight_margin_safeguards(self):
        from core.text_utils import sanitize_highlight_phrase
        # Overly long phrases with negative determiners stripped down to core punchy keyword
        self.assertEqual(sanitize_highlight_phrase("ningún beneficio", max_chars=12), "beneficio")
        self.assertEqual(sanitize_highlight_phrase("no aportan ningún beneficio", max_chars=12), "beneficio")
        self.assertEqual(sanitize_highlight_phrase("mucho dolor", max_chars=12), "dolor")
        self.assertEqual(sanitize_highlight_phrase("tan grave", max_chars=12), "grave")
        
        # Multi-word phrase exceeding 12 chars extracted to most informative single keyword
        self.assertEqual(sanitize_highlight_phrase("diagnósticos prenatales", max_chars=12), "diagnósticos")
        
        # Stopwords and short words strictly rejected
        self.assertEqual(sanitize_highlight_phrase("no", max_chars=12), "")
        self.assertEqual(sanitize_highlight_phrase("el", max_chars=12), "")
        self.assertEqual(sanitize_highlight_phrase("porque", max_chars=12), "")

    def test_pequenos_highlight_auto_scale(self):
        # Verifies that when a single long word (e.g. 14 chars) is highlighted,
        # its scale is automatically reduced to prevent breaking safe screen margins.
        styler = DualStyler.from_preset("pequenos")
        
        class MockProj:
            def __init__(self):
                self.data = {"tracks": [], "materials": {"texts": []}}
            def _parse_subtitles(self):
                pass

        plan = [
            {
                "top": {"text": "médicos", "start": 0, "end": 1000000},
                "bot": {"text": "especializados", "start": 300000, "end": 1000000}
            }
        ]
        proj = MockProj()
        styler.apply_plan(proj, plan)
        
        bot_track = proj.data["tracks"][1]
        bot_seg = bot_track["segments"][0]
        # Base scale in pequenos is 1.3550004042363974.
        # For 'especializados' (14 chars > 11), scale must be shrunk proportionally: 1.355 * (11/14) ≈ 1.0646
        bot_scale_x = bot_seg["clip"]["scale"]["x"]
        self.assertLess(bot_scale_x, 1.355)
        self.assertAlmostEqual(bot_scale_x, 1.3550004042363974 * (11.0 / 14.0), places=2)

if __name__ == "__main__":
    unittest.main()
