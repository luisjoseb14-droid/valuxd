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
        return ["profesionales", "cada familia", "preocupa", "abordaje"]

class TestLauraBurgosPreset(unittest.TestCase):
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
                        "content": json.dumps({"text": "lo que los", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 500000], "end_time": [500000, 1000000], "text": ["lo", "que los"]}
                    },
                    {
                        "id": "MAT_1",
                        "content": json.dumps({"text": "profesionales debemos", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 800000], "end_time": [800000, 1500000], "text": ["profesionales", "debemos"]}
                    },
                    {
                        "id": "MAT_2",
                        "content": json.dumps({"text": "transmitir a", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 700000], "end_time": [700000, 1500000], "text": ["transmitir", "a"]}
                    },
                    {
                        "id": "MAT_3",
                        "content": json.dumps({"text": "cada familia", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 600000], "end_time": [600000, 1200000], "text": ["cada", "familia"]}
                    },
                    {
                        "id": "MAT_4",
                        "content": json.dumps({"text": "es calma y", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 600000], "end_time": [600000, 1300000], "text": ["es", "calma y"]}
                    },
                    {
                        "id": "MAT_5",
                        "content": json.dumps({"text": "seguridad total", "styles": []}),
                        "type": "subtitle",
                        "words": {"start_time": [0, 700000], "end_time": [700000, 1500000], "text": ["seguridad", "total"]}
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
                        {"id": "SEG_3", "material_id": "MAT_3", "target_timerange": {"start": 4000000, "duration": 1200000}},
                        {"id": "SEG_4", "material_id": "MAT_4", "target_timerange": {"start": 5200000, "duration": 1300000}},
                        {"id": "SEG_5", "material_id": "MAT_5", "target_timerange": {"start": 6500000, "duration": 1500000}}
                    ]
                }
            ]
        }

        with open(self.draft_file, 'w', encoding='utf-8') as f:
            json.dump(draft_content, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_laura_burgos_preset_loading(self):
        for name in ["laura burgos", "letra laura burgos", "laura_burgos", "dra. laura burgos", "laura 10"]:
            styler = DualStyler.from_preset(name)
            self.assertEqual(styler.preset_name, "Letra Laura Burgos")
            self.assertEqual(styler.layout, "dual")
            self.assertIn("fonnts.com-Indivisible.otf", styler.default_style["font_path"])
            self.assertIn("fonnts.com-Indivisible_Bold.otf", styler.highlight_style["font_path"])
            self.assertEqual(styler.highlight_style["color"].lower(), "#abc8cc")
            self.assertEqual(styler.highlight_style["animation"]["name"], "Aparición progresiva")
            self.assertEqual(styler.highlight_style["animation"]["resource_id"], "7646371244257955092")
            self.assertEqual(styler.sound_fx["name"], "Click_Mouse_Click_02(864360)")
            self.assertTrue(styler.sound_fx["enabled"])

    def test_laura_burgos_auto_dual_process(self):
        styler = DualStyler.from_preset("laura burgos")
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

        # Check fonts and colors
        texts = {m['id']: m for m in proj.data['materials']['texts']}
        
        # Check top segments have Indivisible Regular
        for seg in top_track['segments']:
            t_mat = texts[seg['material_id']]
            self.assertIn("fonnts.com-Indivisible.otf", t_mat['font_path'])
            c = json.loads(t_mat['content'])
            self.assertNotIn(",", c['text'])
            self.assertNotIn(".", c['text'])

        # Check bottom segments have Indivisible Bold and color #ABC8CC
        for seg in bot_track['segments']:
            t_mat = texts[seg['material_id']]
            self.assertIn("fonnts.com-Indivisible_Bold.otf", t_mat['font_path'])
            self.assertEqual(t_mat['text_color'].lower(), "#abc8cc")
            c = json.loads(t_mat['content'])
            self.assertNotIn(",", c['text'])
            self.assertNotIn(".", c['text'])

        # Check animation on bottom segments
        anims = {m['id']: m for m in proj.data['materials'].get('material_animations', [])}
        for seg in bot_track['segments']:
            self.assertTrue(len(seg['extra_material_refs']) > 0)
            anim_id = seg['extra_material_refs'][0]
            self.assertIn(anim_id, anims)
            self.assertEqual(anims[anim_id]['animations'][0]['name'], "Aparición progresiva")

        # Check audio click sound effect track
        audio_tracks = [t for t in proj.data['tracks'] if t.get('type') == 'audio']
        self.assertTrue(len(audio_tracks) > 0)
        click_track = audio_tracks[-1]
        self.assertEqual(len(click_track['segments']), bot_c)

if __name__ == '__main__':
    unittest.main()
