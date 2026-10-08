# -*- coding: utf-8 -*-
import unittest
import os
import json
import tempfile
import shutil

from core.dual_styler import DualStyler
from core.capcut_draft import CapCutProject


class MockHighlighter:
    def suggest_highlights(self, text, count=10):
        return ["PEQUEÑO", "DE UN 50%", "PARA SU PIE"]


class TestCarrilloPreset(unittest.TestCase):
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
                        "content": json.dumps({"text": "seis de cada diez", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 500000], "end_time": [500000, 1000000], "text": ["seis", "de cada diez"]}
                    },
                    {
                        "id": "MAT_1",
                        "content": json.dumps({"text": "llevan un zapato", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 800000], "end_time": [800000, 1500000], "text": ["llevan", "un zapato"]}
                    },
                    {
                        "id": "MAT_2",
                        "content": json.dumps({"text": "pequeño para su pie", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 700000], "end_time": [700000, 1500000], "text": ["pequeño", "para su pie"]}
                    },
                    {
                        "id": "MAT_3",
                        "content": json.dumps({"text": "más de un 50%", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 600000], "end_time": [600000, 1200000], "text": ["más de", "un 50%"]}
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

    def test_carrillo_preset_loading(self):
        aliases = [
            "carrillo",
            "carillo",
            "dr carrillo",
            "dr. carrillo",
            "dr carillo",
            "letra carrillo",
            "letra dr carrillo"
        ]
        for name in aliases:
            styler = DualStyler.from_preset(name)
            self.assertEqual(styler.preset_name, "Letra Dr Carrillo")
            self.assertEqual(styler.layout, "dual")
            self.assertIn("Gotham Book.otf", styler.default_style["font_path"])
            self.assertIn("Gotham Bold.otf", styler.highlight_style["font_path"])
            self.assertEqual(styler.default_style["font_size"], 10.0)
            self.assertEqual(styler.highlight_style["font_size"], 9.0)
            self.assertEqual(styler.highlight_style["color"].lower(), "#ccc3b1")
            self.assertFalse(styler.highlight_style.get("animation", {}).get("enabled", True))
            self.assertEqual(styler.sound_fx["name"], "Click_Mouse_Click_02(864360)")
            self.assertTrue(styler.sound_fx["enabled"])
            self.assertEqual(styler.sound_fx["volume"], 0.55)
            self.assertTrue(styler.default_style.get("uppercase", False))
            self.assertTrue(styler.highlight_style.get("uppercase", False))

    def test_carrillo_auto_dual_process(self):
        styler = DualStyler.from_preset("carrillo")
        proj = CapCutProject(self.test_dir)
        top_c, bot_c = styler.auto_dual_process(proj, highlighter=MockHighlighter(), min_pacing_sec=0.1)

        self.assertGreater(top_c, 0)
        self.assertGreater(bot_c, 0)

        # Verify dual tracks
        text_tracks = [t for t in proj.data['tracks'] if t.get('type') == 'text']
        self.assertEqual(len(text_tracks), 2)
        top_track, bot_track = text_tracks[0], text_tracks[1]
        self.assertGreater(len(top_track['segments']), 0)
        self.assertGreater(len(bot_track['segments']), 0)

        # Check fonts, colors, and uppercase
        texts = {m['id']: m for m in proj.data['materials']['texts']}

        # Check top segments have Gotham Book, color #FFFFFF, uppercase
        for seg in top_track['segments']:
            t_mat = texts[seg['material_id']]
            self.assertTrue(
                "Gotham Book.otf" in t_mat['font_path'] or
                "Gotham Bold.otf" in t_mat['font_path']
            )
            c = json.loads(t_mat['content'])
            self.assertEqual(c['text'], c['text'].upper())
            self.assertNotIn(",", c['text'])
            self.assertNotIn(".", c['text'])

        # Check bottom segments have Gotham Bold and color #CCC3B1
        for seg in bot_track['segments']:
            t_mat = texts[seg['material_id']]
            self.assertIn("Gotham Bold.otf", t_mat['font_path'])
            self.assertEqual(t_mat['text_color'].lower(), "#ccc3b1")
            c = json.loads(t_mat['content'])
            self.assertEqual(c['text'], c['text'].upper())
            self.assertNotIn(",", c['text'])
            self.assertNotIn(".", c['text'])

        # Check animation disabled on bottom
        for seg in bot_track['segments']:
            self.assertEqual(len(seg.get('extra_material_refs', [])), 0)

        # Check audio click sound effect track
        audio_tracks = [t for t in proj.data['tracks'] if t.get('type') == 'audio']
        self.assertTrue(len(audio_tracks) > 0)
        click_track = audio_tracks[-1]
        self.assertGreaterEqual(len(click_track['segments']), bot_c)


if __name__ == '__main__':
    unittest.main()
