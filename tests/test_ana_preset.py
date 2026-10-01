# -*- coding: utf-8 -*-
import unittest
import json
from core.capcut_draft import SubtitleItem
from core.dual_styler import DualStyler
from cc_subs_pro import resolve_preset
from core.text_utils import clean_subtitle_text

class TestAnaPreset(unittest.TestCase):
    def test_preset_resolution(self):
        preset = resolve_preset("ana")
        self.assertTrue(preset, "Preset ana should resolve properly")
        self.assertEqual(preset.get("name"), "Letra Ana Otorrino")
        self.assertEqual(preset.get("layout"), "template")
        
        # Verify fonts
        self.assertIn("Liliana", preset["top"]["font_name"])
        self.assertEqual(preset["top"]["font_path"], "Liliana-Bold.otf")
        self.assertIn("Liliana", preset["highlight"]["font_name"])
        self.assertEqual(preset["highlight"]["font_path"], "Liliana-Black.otf")
        
        # Verify colors, sizes and positions
        self.assertEqual(preset["top"]["color"], "#FFFFFF")
        self.assertEqual(preset["top"]["font_size"], 9.0)
        self.assertAlmostEqual(preset["top"]["y"], -0.0499, places=3)
        self.assertEqual(preset["highlight"]["color"], "#FDE69A")
        self.assertEqual(preset["highlight"]["font_size"], 11.0)
        
        # Verify template and loop animation
        self.assertEqual(preset["template"].get("effect_id"), "7331663549263023366")
        self.assertEqual(preset["template"].get("layer_name"), "D6B3869B-42B9-43ED-8435-C814651D7122")
        self.assertEqual(preset["animation"].get("resource_id"), "7258195155394499074")
        self.assertEqual(preset["animation"].get("type"), "loop")

    def test_preset_alias_resolution(self):
        aliases = [
            "ana",
            "ana_otorrino",
            "ana otorrino",
            "letra ana",
            "letra ana otorrino",
            "letra_ana",
            "letra_ana_otorrino"
        ]
        for alias in aliases:
            p = resolve_preset(alias)
            self.assertTrue(p, f"Failed to resolve alias: {alias}")
            self.assertEqual(p.get("name"), "Letra Ana Otorrino")

    def test_zero_forbidden_punctuation(self):
        preset = resolve_preset("ana")
        for text in [preset.get("name", ""), preset.get("description", "")]:
            cleaned = clean_subtitle_text(text)
            self.assertNotIn(",", cleaned)
            self.assertNotIn(".", cleaned)
            self.assertNotIn(":", cleaned)

    def test_template_process_ana(self):
        styler = DualStyler.from_preset("ana")
        self.assertEqual(styler.layout, "template")

        data = {
            "materials": {
                "texts": [
                    {
                        "id": "M1",
                        "recognize_task_id": "test_task",
                        "content": json.dumps({"text": "escuchas un pitido en el oido", "styles": [{"range": [0, 29]}]}),
                        "words": {"start_time": [0, 200, 400, 600, 800, 1000], "end_time": [200, 400, 600, 800, 1000, 1200], "text": ["escuchas", "un", "pitido", "en", "el", "oido"]}
                    }
                ],
                "text_templates": [],
                "material_animations": []
            },
            "tracks": [
                {
                    "id": "T1",
                    "type": "text",
                    "segments": [
                        {"id": "S1", "material_id": "M1", "target_timerange": {"start": 0, "duration": 2000000}, "extra_material_refs": [], "clip": {}}
                    ]
                }
            ]
        }

        class MockProject:
            def __init__(self, d):
                self.data = d
                self.subtitles = []
                self._parse_subtitles()

            def clean_all_subtitles(self):
                pass

            def _parse_subtitles(self):
                self.subtitles = []
                texts = {t["id"]: t for t in self.data["materials"].get("texts", [])}
                templates = {t["id"]: t for t in self.data["materials"].get("text_templates", [])}
                for seg in self.data["tracks"][0]["segments"]:
                    mat_id = seg["material_id"]
                    t_mat = None
                    if mat_id in texts:
                        t_mat = texts[mat_id]
                    elif mat_id in templates:
                        t_mat_id = templates[mat_id]["text_info_resources"][0]["text_material_id"]
                        t_mat = texts.get(t_mat_id)
                    if t_mat:
                        self.subtitles.append(SubtitleItem(0, seg, t_mat))

        class MockHighlighter:
            def suggest_highlights(self, text, count=10):
                return ["un pitido"]

        proj = MockProject(data)
        processed_c, hl_c = styler.auto_dual_process(proj, highlighter=MockHighlighter(), min_pacing_sec=0.1)

        self.assertEqual(processed_c, 1)
        self.assertEqual(hl_c, 1)

        # Check template materials generated
        self.assertEqual(len(data["materials"]["text_templates"]), 1)
        tmpl = data["materials"]["text_templates"][0]
        self.assertEqual(tmpl["effect_id"], "7331663549263023366")
        self.assertEqual(tmpl["type"], "text_template_subtitle")

        # Check animation materials generated
        self.assertEqual(len(data["materials"]["material_animations"]), 1)
        anim = data["materials"]["material_animations"][0]
        self.assertEqual(anim["animations"][0]["resource_id"], "7258195155394499074")
        self.assertEqual(anim["animations"][0]["type"], "loop")

        # Check text material layer name and rich styles
        self.assertEqual(len(data["materials"]["texts"]), 1)
        t_mat = data["materials"]["texts"][0]
        self.assertEqual(t_mat["name"], "D6B3869B-42B9-43ED-8435-C814651D7122")
        
        parsed = json.loads(t_mat["content"])
        self.assertIn("styles", parsed)
        self.assertGreaterEqual(len(parsed["styles"]), 2, "Should have base and highlight style ranges")
        
        # Verify zero forbidden punctuation in all generated texts
        for mat in data["materials"]["texts"]:
            c = json.loads(mat["content"])
            self.assertNotIn(",", c.get("text", ""))
            self.assertNotIn(".", c.get("text", ""))
            self.assertNotIn(":", c.get("text", ""))

if __name__ == "__main__":
    unittest.main()
