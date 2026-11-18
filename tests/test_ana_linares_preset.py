import json
import os
import sys
import tempfile
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.capcut_draft import CapCutProject
from core.dual_styler import DualStyler, get_effective_font_size
from core.font_installer import FONT_REGISTRY_MAP
from core.preset_matcher import detect_preset_from_name


class TestAnaLinaresPreset(unittest.TestCase):
    def test_preset_matcher_prioritizes_ana_linares_over_ana(self):
        self.assertEqual(detect_preset_from_name("Ana Linares 1"), "ana_linares")
        self.assertEqual(detect_preset_from_name("Ana López-Linares (1)"), "ana_linares")
        self.assertEqual(detect_preset_from_name("Dra Ana Linares - Quistes"), "ana_linares")
        self.assertEqual(detect_preset_from_name("Linares Párpado"), "ana_linares")
        self.assertEqual(detect_preset_from_name("Dra Ana Visedo"), "ana_visedo")
        self.assertEqual(detect_preset_from_name("Ana Otorrino"), "ana")

    def test_preset_loads_and_assets_exist(self):
        for alias in ["ana_linares", "ana linares", "dra. ana linares", "linares", "letra ana linares", "ana lópez linares"]:
            styler = DualStyler.from_preset(alias)
            self.assertEqual(styler.preset_data["layout"], "dual")
            self.assertFalse(styler.preset_data.get("allow_solo_highlights", True))
            self.assertEqual(styler.default_style["font_path"], "PlayfairDisplay-Bold.ttf")
            self.assertEqual(styler.default_style["font_title"], "Playfair Display Bold")
            self.assertEqual(styler.default_style["color"].upper(), "#FFFFFF")
            self.assertAlmostEqual(float(styler.default_style["font_size"]), 14.0, places=2)
            self.assertTrue(styler.default_style.get("fixed_scale"))
            self.assertFalse(styler.default_style.get("uppercase", False))

            self.assertEqual(styler.highlight_style["font_path"], "Montserrat-Medium.ttf")
            self.assertEqual(styler.highlight_style["font_title"], "Montserrat Medium")
            self.assertEqual(styler.highlight_style["color"].upper(), "#ACB1EC")
            self.assertTrue(styler.highlight_style.get("uppercase"))
            self.assertEqual(styler.highlight_style["animation"]["name"], "Mini zoom")
            self.assertEqual(styler.highlight_style["animation"]["resource_id"], "6763469998330483213")
            self.assertEqual(styler.sound_fx["filename"], "click_mouse_02.mp3")

        self.assertIn("PlayfairDisplay-Bold.ttf", FONT_REGISTRY_MAP)
        self.assertIn("Montserrat-Medium.ttf", FONT_REGISTRY_MAP)
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "assets", "fonts", "PlayfairDisplay-Bold.ttf")))
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "assets", "fonts", "Montserrat-Medium.ttf")))
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "assets", "audio", "click_mouse_02.mp3")))

    def test_dynamic_font_size_for_short_vs_long_highlight_words(self):
        styler = DualStyler.from_preset("ana_linares")
        # Top general font size must stay fixed regardless of phrase length
        self.assertAlmostEqual(get_effective_font_size(styler.default_style, "Esto es un"), 14.0)
        self.assertAlmostEqual(get_effective_font_size(styler.default_style, "También puede ser"), 14.0)

        # Short highlight word like example "QUISTE" (6 chars) uses 25.0
        self.assertAlmostEqual(get_effective_font_size(styler.highlight_style, "QUISTE"), 25.0)
        self.assertAlmostEqual(get_effective_font_size(styler.highlight_style, "NEVUS"), 25.0)
        self.assertAlmostEqual(get_effective_font_size(styler.highlight_style, "HERPES"), 25.0)

        # Medium highlight words (7-9 chars) scale down to 21.0
        self.assertAlmostEqual(get_effective_font_size(styler.highlight_style, "VERRUGA"), 21.0)
        self.assertAlmostEqual(get_effective_font_size(styler.highlight_style, "HEMATOMA"), 21.0)

        # Long highlight words (10+ chars) scale down to 17.5
        self.assertAlmostEqual(get_effective_font_size(styler.highlight_style, "NEUROFIBROMA"), 17.5)
        self.assertAlmostEqual(get_effective_font_size(styler.highlight_style, "BLEFAROPLASTIA"), 17.5)

    def test_apply_plan_preserves_top_scale_and_styles_bottom_highlights(self):
        styler = DualStyler.from_preset("ana_linares")
        draft_data = {
            "tracks": [
                {"id": "T_TOP", "type": "text", "segments": []},
                {"id": "T_BOT", "type": "text", "segments": []},
                {"id": "T_SFX", "type": "audio", "segments": []},
            ],
            "materials": {
                "texts": [],
                "audios": [],
                "material_animations": [],
                "canvases": [],
                "effects": [],
                "stickers": [],
                "transitions": [],
                "videos": [],
            },
        }
        plan = [
            {
                "top": {"text": "Esto es un", "start": 0, "end": 1400000},
                "bot": {"text": "quiste", "start": 767000, "end": 1400000},
            },
            {
                "top": {"text": "También parece", "start": 1600000, "end": 3000000},
                "bot": {"text": "verruga", "start": 2100000, "end": 3000000},
            },
            {
                "top": {"text": "O incluso un", "start": 3200000, "end": 4800000},
                "bot": {"text": "neurofibroma", "start": 3800000, "end": 4800000},
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            draft_path = os.path.join(tmpdir, "draft_content.json")
            with open(draft_path, "w", encoding="utf-8") as f:
                json.dump(draft_data, f)
            project = CapCutProject(tmpdir)
            styler.apply_plan(project, plan)
            data = project.data

            text_mats = {m["id"]: m for m in data["materials"]["texts"]}
            text_tracks = [t for t in data["tracks"] if t.get("type") == "text"]
            audio_tracks = [t for t in data["tracks"] if t.get("type") == "audio"]
            top_segs = text_tracks[0]["segments"]
            bot_segs = text_tracks[1]["segments"]
            self.assertEqual(len(top_segs), 3)
            self.assertEqual(len(bot_segs), 3)

            for seg in top_segs:
                self.assertAlmostEqual(seg["clip"]["scale"]["x"], 1.0, places=3)
                self.assertAlmostEqual(seg["clip"]["scale"]["y"], 1.0, places=3)
                content = json.loads(text_mats[seg["material_id"]]["content"])
                self.assertEqual(content["styles"][0]["size"], 14.0)
                self.assertTrue(content["styles"][0]["shadows"])
                self.assertNotEqual(content["text"], content["text"].upper())

            sizes_by_word = {}
            for seg in bot_segs:
                content = json.loads(text_mats[seg["material_id"]]["content"])
                sizes_by_word[content["text"]] = content["styles"][0]["size"]
                self.assertTrue(content["styles"][0]["shadows"])
                self.assertTrue(seg["extra_material_refs"])

            self.assertEqual(sizes_by_word["QUISTE"], 25.0)
            self.assertEqual(sizes_by_word["VERRUGA"], 21.0)
            self.assertEqual(sizes_by_word["NEUROFIBROMA"], 17.5)
            self.assertTrue(any(len(t["segments"]) >= 3 for t in audio_tracks))


if __name__ == "__main__":
    unittest.main()
