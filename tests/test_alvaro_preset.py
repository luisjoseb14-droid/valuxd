# -*- coding: utf-8 -*-
import unittest
import json
from core.capcut_draft import SubtitleItem
from core.dual_styler import DualStyler
from cc_subs_pro import resolve_preset
from core.text_utils import clean_subtitle_text

class TestAlvaroPreset(unittest.TestCase):
    def test_preset_resolution(self):
        preset = resolve_preset("alvaro")
        self.assertTrue(preset, "Preset alvaro should resolve properly")
        self.assertEqual(preset.get("name"), "Letra Alvaro")
        
        # Verify fonts
        self.assertIn("GC GRIND", preset["top"]["font_name"])
        self.assertEqual(preset["top"]["font_path"], "GC GRIND.otf")
        self.assertIn("GC GRIND", preset["bottom"]["font_name"])
        self.assertEqual(preset["bottom"]["font_path"], "GC GRIND.otf")
        
        # Verify colors and positions
        self.assertEqual(preset["top"]["color"], "#FFFFFF")
        self.assertEqual(preset["top"]["y"], 0.0)
        self.assertEqual(preset["bottom"]["color"], "#FDB2A0")
        self.assertAlmostEqual(preset["bottom"]["y"], -0.0994, places=3)
        
        # Verify animation and audio click
        self.assertIn("animation", preset["bottom"])
        self.assertEqual(preset["bottom"]["animation"].get("name"), "Corte con láser")
        self.assertEqual(preset["bottom"]["animation"].get("resource_id"), "7229621702668325378")
        self.assertTrue(preset.get("sound_fx", {}).get("enabled"))
        self.assertEqual(preset["sound_fx"].get("name"), "Click_Mouse_Click_02(864360)")

    def test_preset_alias_resolution(self):
        preset_alias = resolve_preset("letra alvaro")
        self.assertTrue(preset_alias)
        self.assertEqual(preset_alias.get("name"), "Letra Alvaro")

    def test_zero_forbidden_punctuation(self):
        preset = resolve_preset("alvaro")
        for text in [preset.get("name", ""), preset.get("description", "")]:
            cleaned = clean_subtitle_text(text)
            self.assertNotIn(",", cleaned)
            self.assertNotIn(".", cleaned)
            self.assertNotIn(":", cleaned)

    def test_dual_process_alvaro(self):
        styler = DualStyler.from_preset("alvaro")
        self.assertEqual(styler.y_top, 0.0)
        self.assertAlmostEqual(styler.y_bottom, -0.0994, places=3)
        self.assertTrue(styler.sound_fx.get("enabled"))

        data = {
            "materials": {
                "texts": [
                    {
                        "id": "M1",
                        "content": json.dumps({"text": "Hola bienvenidos a consulta", "styles": [{"range": [0, 27]}]}),
                        "words": {"start_time": [0, 100, 200, 300], "end_time": [100, 200, 300, 500], "text": ["Hola", "bienvenidos", "a", "consulta"]}
                    },
                    {
                        "id": "M2",
                        "content": json.dumps({"text": "tenemos un tratamiento excelente", "styles": [{"range": [0, 32]}]}),
                        "words": {"start_time": [0, 100, 200, 350], "end_time": [100, 200, 350, 700], "text": ["tenemos", "un", "tratamiento", "excelente"]}
                    }
                ]
            },
            "tracks": [
                {
                    "id": "T1",
                    "type": "text",
                    "segments": [
                        {"id": "S1", "material_id": "M1", "target_timerange": {"start": 0, "duration": 1000000}, "extra_material_refs": []},
                        {"id": "S2", "material_id": "M2", "target_timerange": {"start": 1000000, "duration": 1500000}, "extra_material_refs": []}
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
                return ["excelente"]

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

if __name__ == "__main__":
    unittest.main()
