import json
import os
import sys
import tempfile
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.capcut_draft import CapCutProject
from core.dual_styler import DualStyler
from core.font_installer import FONT_REGISTRY_MAP
from core.preset_matcher import detect_preset_from_name


class TestCostaCalidaPreset(unittest.TestCase):
    def test_preset_matcher_detects_costa_calida(self):
        self.assertEqual(detect_preset_from_name("Costa calida 1"), "costa_calida")
        self.assertEqual(detect_preset_from_name("Costa Cálida - Sofás"), "costa_calida")
        self.assertEqual(detect_preset_from_name(r"B:\Descargas MEGA\costa calida\video.mov"), "costa_calida")

    def test_preset_loads_and_assets_exist(self):
        for alias in ["costa_calida", "costa calida", "costa cálida", "letra costa calida"]:
            styler = DualStyler.from_preset(alias)
            self.assertEqual(styler.preset_data["layout"], "dual")
            self.assertEqual(styler.default_style["font_path"], "Montserrat-Medium.ttf")
            self.assertEqual(styler.default_style["font_title"], "Montserrat Medium")
            self.assertEqual(styler.default_style["color"].upper(), "#FFFFFF")
            self.assertAlmostEqual(float(styler.default_style["font_size"]), 10.0, places=2)
            self.assertAlmostEqual(float(styler.y_top), -0.10956492293459096, places=5)
            self.assertFalse(styler.default_style.get("uppercase", False))

            self.assertEqual(styler.highlight_style["font_path"], "PT Serif Regular.ttf")
            self.assertEqual(styler.highlight_style["font_title"], "PT Serif")
            self.assertEqual(styler.highlight_style["color"].upper(), "#F5D90E")
            self.assertAlmostEqual(float(styler.highlight_style["font_size"]), 14.0, places=2)
            self.assertAlmostEqual(float(styler.y_bottom), -0.1771712328005064, places=5)
            self.assertFalse(styler.highlight_style.get("uppercase", False))
            self.assertTrue(styler.highlight_style.get("useLetterColor", False))
            self.assertEqual(styler.highlight_style["animation"]["name"], "Aparición progresiva")
            self.assertEqual(styler.highlight_style["animation"]["resource_id"], "7646371244257955092")
            self.assertEqual(styler.highlight_style["animation"]["duration"], 333333)
            self.assertEqual(styler.sound_fx["filename"], "click_mouse_02.mp3")

        self.assertIn("Montserrat-Medium.ttf", FONT_REGISTRY_MAP)
        self.assertIn("PT Serif Regular.ttf", FONT_REGISTRY_MAP)
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "assets", "fonts", "Montserrat-Medium.ttf")))
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "assets", "fonts", "PT Serif Regular.ttf")))
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "assets", "audio", "click_mouse_02.mp3")))

    def test_apply_plan_preserves_mixed_case_yellow_pt_serif_and_animation(self):
        styler = DualStyler.from_preset("costa_calida")
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
                "top": {"text": "sacar el máximo", "start": 0, "end": 1200000},
                "bot": {"text": "provecho", "start": 550000, "end": 1200000},
            },
            {
                "top": {"text": "un sofá", "start": 1300000, "end": 2300000},
                "bot": {"text": "comodidad", "start": 1700000, "end": 2300000},
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "draft_content.json"), "w", encoding="utf-8") as f:
                json.dump(draft_data, f)
            project = CapCutProject(tmpdir)
            styler.apply_plan(project, plan)
            data = project.data

            text_mats = {m["id"]: m for m in data["materials"]["texts"]}
            anims_by_id = {a["id"]: a for a in data["materials"]["material_animations"]}
            text_tracks = [t for t in data["tracks"] if t.get("type") == "text"]
            audio_tracks = [t for t in data["tracks"] if t.get("type") == "audio"]

            self.assertEqual(len(text_tracks[0]["segments"]), 2)
            self.assertEqual(len(text_tracks[1]["segments"]), 2)

            for seg in text_tracks[0]["segments"]:
                c = json.loads(text_mats[seg["material_id"]]["content"])
                self.assertEqual(c["styles"][0]["size"], 10.0)
                self.assertIn("Montserrat-Medium.ttf", c["styles"][0]["font"]["path"])
                self.assertTrue(c["styles"][0]["shadows"])
                self.assertAlmostEqual(seg["clip"]["scale"]["x"], 1.355, places=3)

            for seg in text_tracks[1]["segments"]:
                mat = text_mats[seg["material_id"]]
                c = json.loads(mat["content"])
                self.assertEqual(c["styles"][0]["size"], 14.0)
                self.assertIn("PT Serif Regular.ttf", c["styles"][0]["font"]["path"])
                self.assertEqual(mat["text_color"].upper(), "#F5D90E")
                self.assertTrue(c["styles"][0]["shadows"])
                self.assertNotEqual(c["text"], c["text"].upper())
                self.assertAlmostEqual(seg["clip"]["scale"]["x"], 1.355, places=3)
                anim_ids = [ref for ref in seg.get("extra_material_refs", []) if ref in anims_by_id]
                self.assertTrue(anim_ids)
                self.assertEqual(anims_by_id[anim_ids[0]]["animations"][0]["name"], "Aparición progresiva")

            self.assertTrue(any(len(t["segments"]) >= 2 for t in audio_tracks))


if __name__ == "__main__":
    unittest.main()
