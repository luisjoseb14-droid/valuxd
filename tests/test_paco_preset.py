# -*- coding: utf-8 -*-
import unittest
import os
import json
import tempfile
import shutil

from core.dual_styler import DualStyler
from core.capcut_draft import CapCutProject
from core.preset_matcher import detect_preset_from_name
from core.platform_paths import get_base_dir


class MockHighlighter:
    def suggest_highlights(self, text, count=10):
        return ["accidente", "golpe", "neurológicos"]


class TestPacoPreset(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.draft_file = os.path.join(self.test_dir, 'draft_content.json')

        draft_content = {
            "canvas_config": {"height": 1920, "ratio": "original", "width": 1080},
            "duration": 15000000,
            "fps": 30.0,
            "materials": {
                "texts": [
                    {
                        "id": "MAT_0",
                        "content": json.dumps({"text": "Con diecisiete años", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 500000], "end_time": [500000, 1000000], "text": ["Con", "diecisiete", "años"]}
                    },
                    {
                        "id": "MAT_1",
                        "content": json.dumps({"text": "tuvo un accidente", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 800000], "end_time": [800000, 1500000], "text": ["tuvo", "un", "accidente"]}
                    },
                    {
                        "id": "MAT_2",
                        "content": json.dumps({"text": "tenía un golpe", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 700000], "end_time": [700000, 1500000], "text": ["tenía", "un", "golpe"]}
                    },
                    {
                        "id": "MAT_3",
                        "content": json.dumps({"text": "problemas neurológicos", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 600000], "end_time": [600000, 1200000], "text": ["problemas", "neurológicos"]}
                    }
                ]
            },
            "tracks": [
                {
                    "id": "TRK_TEXT",
                    "type": "text",
                    "segments": [
                        {"id": "SEG_0", "material_id": "MAT_0", "target_timerange": {"start": 0, "duration": 1000000}},
                        {"id": "SEG_1", "material_id": "MAT_1", "target_timerange": {"start": 1000000, "duration": 1500000}},
                        {"id": "SEG_2", "material_id": "MAT_2", "target_timerange": {"start": 2500000, "duration": 1500000}},
                        {"id": "SEG_3", "material_id": "MAT_3", "target_timerange": {"start": 4000000, "duration": 1200000}}
                    ]
                }
            ]
        }

        with open(self.draft_file, 'w', encoding='utf-8') as f:
            json.dump(draft_content, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_paco_preset_matching(self):
        self.assertEqual(detect_preset_from_name("Paco 6"), "paco")
        self.assertEqual(detect_preset_from_name("Letra Paco"), "paco")
        self.assertEqual(detect_preset_from_name("Proyecto Paco final"), "paco")
        self.assertEqual(detect_preset_from_name(r"B:\capc\Paco 6"), "paco")

    def test_paco_preset_loading(self):
        aliases = [
            "paco",
            "letra paco",
            "letra_paco",
            "preset paco",
            "preset_paco",
            "dr paco"
        ]
        for name in aliases:
            styler = DualStyler.from_preset(name)
            self.assertEqual(styler.preset_name, "Letra Paco")
            self.assertEqual(styler.layout, "dual")
            self.assertIn("Gotham Light.otf", styler.default_style["font_path"])
            self.assertIn("Anton-Regular.ttf", styler.highlight_style["font_path"])
            self.assertEqual(styler.default_style["font_size"], 10.0)
            self.assertEqual(styler.highlight_style["font_size"], 20.0)
            self.assertEqual(styler.default_style["color"].upper(), "#FFFFFF")
            self.assertEqual(styler.highlight_style["color"].upper(), "#FFFFFF")
            self.assertFalse(styler.highlight_style.get("animation", {}).get("enabled", True))
            self.assertEqual(styler.sound_fx["name"], "Click_Mouse_Click_02(864360)")
            self.assertTrue(styler.sound_fx["enabled"])
            self.assertEqual(styler.sound_fx["volume"], 0.52)
            self.assertFalse(styler.default_style.get("uppercase", False))
            self.assertFalse(styler.highlight_style.get("uppercase", False))

    def test_paco_assets_exist(self):
        base_dir = get_base_dir()
        gotham_font = os.path.join(base_dir, "assets", "fonts", "Gotham Light.otf")
        anton_font = os.path.join(base_dir, "assets", "fonts", "Anton-Regular.ttf")
        click_sound = os.path.join(base_dir, "assets", "audio", "click_mouse_02.mp3")

        self.assertTrue(os.path.isfile(gotham_font), f"Gotham Light.otf not found at {gotham_font}")
        self.assertTrue(os.path.isfile(anton_font), f"Anton-Regular.ttf not found at {anton_font}")
        self.assertTrue(os.path.isfile(click_sound), f"click_mouse_02.mp3 not found at {click_sound}")

    def test_paco_auto_dual_process(self):
        styler = DualStyler.from_preset("paco")
        proj = CapCutProject(self.test_dir)
        highlighter = MockHighlighter()

        top_c, bot_c = styler.auto_dual_process(proj, highlighter=highlighter, min_pacing_sec=0.1)

        self.assertGreater(top_c, 0)
        self.assertGreater(bot_c, 0)

        # Verify dual tracks
        text_tracks = [t for t in proj.data['tracks'] if t.get('type') == 'text']
        self.assertEqual(len(text_tracks), 2)
        top_track, bot_track = text_tracks[0], text_tracks[1]
        self.assertGreater(len(top_track['segments']), 0)
        self.assertGreater(len(bot_track['segments']), 0)

        texts = {m['id']: m for m in proj.data['materials']['texts']}

        # Check top segments have Gotham Light
        for seg in top_track['segments']:
            t_mat = texts[seg['material_id']]
            self.assertTrue(
                "Gotham Light.otf" in t_mat['font_path'] or
                "Anton-Regular.ttf" in t_mat['font_path']
            )

        # Check bottom segments have Anton-Regular and color #FFFFFF
        for seg in bot_track['segments']:
            t_mat = texts[seg['material_id']]
            self.assertIn("Anton-Regular.ttf", t_mat['font_path'])
            self.assertEqual(t_mat['text_color'].upper(), "#FFFFFF")

        # Check that animation is disabled (no extra material animation references)
        for seg in bot_track['segments']:
            self.assertEqual(len(seg.get('extra_material_refs', [])), 0)

        # Check audio click sound effect track
        audio_tracks = [t for t in proj.data['tracks'] if t.get('type') == 'audio']
        self.assertTrue(len(audio_tracks) > 0)
        click_track = audio_tracks[-1]
        self.assertGreaterEqual(len(click_track['segments']), bot_c)
        for cs in click_track['segments']:
            self.assertAlmostEqual(cs.get("volume", 0.0), 0.52, places=2)


if __name__ == '__main__':
    unittest.main()
