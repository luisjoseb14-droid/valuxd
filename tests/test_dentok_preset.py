# -*- coding: utf-8 -*-
import unittest
import os
import json
import tempfile
import shutil

from core.dual_styler import DualStyler
from core.capcut_draft import CapCutProject
from core.preset_matcher import detect_preset_from_name


class TestDentokPreset(unittest.TestCase):
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
                        "content": json.dumps({"text": "cosas que no recomendaría ni haría versión higiene", "styles": []}),
                        "recognize_text": "cosas que no recomendaría ni haría versión higiene",
                        "type": "subtitle",
                        "words": {
                            "start_time": [0, 360, 520, 720, 1480, 1880, 2480, 3000],
                            "end_time": [320, 520, 640, 1400, 1680, 2280, 2800, 3640],
                            "text": ["cosas", "que", "no", "recomendaría", "ni", "haría", "versión", "higiene"]
                        }
                    },
                    {
                        "id": "MAT_1",
                        "content": json.dumps({"text": "si eres esa persona que guarda el cepillo", "styles": []}),
                        "recognize_text": "si eres esa persona que guarda el cepillo",
                        "type": "subtitle",
                        "words": {
                            "start_time": [0, 240, 480, 760, 960, 1360, 1560],
                            "end_time": [240, 480, 760, 960, 1360, 1560, 2600],
                            "text": ["si", "eres", "esa", "persona", "que", "guarda", "el cepillo"]
                        }
                    },
                    {
                        "id": "MAT_2",
                        "content": json.dumps({"text": "en", "styles": []}),
                        "recognize_text": "en",
                        "type": "subtitle",
                        "words": {
                            "start_time": [0],
                            "end_time": [300],
                            "text": ["en"]
                        }
                    },
                    {
                        "id": "MAT_3",
                        "content": json.dumps({"text": "el vaso del lavabo", "styles": []}),
                        "recognize_text": "el vaso del lavabo",
                        "type": "subtitle",
                        "words": {
                            "start_time": [0, 400, 800],
                            "end_time": [350, 750, 1100],
                            "text": ["el", "vaso", "del lavabo"]
                        }
                    }
                ]
            },
            "tracks": [
                {
                    "id": "TRK_TEXT",
                    "type": "text",
                    "flag": 1,
                    "segments": [
                        {"id": "SEG_0", "material_id": "MAT_0", "target_timerange": {"start": 100000, "duration": 3400000}},
                        {"id": "SEG_1", "material_id": "MAT_1", "target_timerange": {"start": 3530000, "duration": 2570000}},
                        {"id": "SEG_2", "material_id": "MAT_2", "target_timerange": {"start": 6200000, "duration": 300000}},
                        {"id": "SEG_3", "material_id": "MAT_3", "target_timerange": {"start": 6500000, "duration": 1100000}}
                    ]
                }
            ]
        }

        with open(self.draft_file, 'w', encoding='utf-8') as f:
            json.dump(draft_content, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dentok_preset_loading(self):
        aliases = [
            "dentok",
            "letra dentok",
            "letra_dentok",
            "dr dentok",
            "dr. dentok",
            "doctor dentok",
            "sep dentok",
            "sep_dentok"
        ]
        for alias in aliases:
            styler = DualStyler.from_preset(alias)
            self.assertEqual(styler.layout, "dentok", f"Preset {alias} must have layout 'dentok'")
            self.assertIn("Helvetica", styler.general_cfg.get("font_name", ""))
            self.assertIn("Playfair", styler.escalera_cfg.get("font_name", ""))
            self.assertAlmostEqual(styler.general_cfg.get("font_size", 0), 6.2, places=1)
            self.assertAlmostEqual(styler.escalera_cfg.get("font_size", 0), 14.08, places=1)
            self.assertAlmostEqual(styler.escalera_cfg.get("font_size_punchline", 0), 18.08, places=1)

    def test_preset_matcher(self):
        sample_names = [
            "SEP Dentok 7",
            "sep dentok 3",
            "0709 DENTOK 6",
            "Dr. Dentok - Implantes",
            "Doctor Dentok 2.0",
            "C:\\CapCut\\Projects\\SEP Dentok 8.0"
        ]
        for name in sample_names:
            detected = detect_preset_from_name(name)
            self.assertEqual(detected, "dentok", f"Failed to detect dentok in '{name}'")

    def test_chunk_dentok_escalera(self):
        chunks_hook1 = DualStyler._chunk_dentok_escalera("cosas que no recomendaría ni haría versión higiene")
        self.assertGreaterEqual(len(chunks_hook1), 2)
        self.assertLessEqual(len(chunks_hook1), 4)
        # Ensure last chunk has strong punchline
        self.assertIn("higiene", chunks_hook1[-1].lower())

        chunks_hook2 = DualStyler._chunk_dentok_escalera("no te hagas un diseño de sonrisa en el 2026")
        self.assertEqual(len(chunks_hook2), 4)
        self.assertEqual(chunks_hook2[0].lower(), "no te hagas")
        self.assertEqual(chunks_hook2[1].lower(), "un diseño")
        self.assertEqual(chunks_hook2[2].lower(), "de sonrisa")
        self.assertEqual(chunks_hook2[3].lower(), "en el 2026")

        chunks_short = DualStyler._chunk_dentok_escalera("Morderte las uñas")
        self.assertIn(len(chunks_short), (2, 3))

    def test_auto_dentok_process_flow(self):
        proj = CapCutProject(self.draft_file)
        styler = DualStyler.from_preset("dentok")
        total_items, hl_count = styler.auto_dentok_process(proj)

        # Mat_2 ('en') is an orphan and should be merged with Mat_3 ('el vaso del lavabo')
        # Total initial = 4 -> Merged = 3
        self.assertEqual(total_items, 3)
        self.assertGreaterEqual(hl_count, 1)

        # Check tracks in project
        text_tracks = [t for t in proj.data['tracks'] if t.get('type') == 'text']
        self.assertGreaterEqual(len(text_tracks), 5)

        # Track 0 is General with flag=1
        gen_track = text_tracks[0]
        self.assertEqual(gen_track.get('flag'), 1)
        self.assertEqual(len(gen_track.get('segments', [])), 2)

        # Tracks 1..4 are Escalera tracks with flag=0
        for i in range(1, 5):
            e_track = text_tracks[i]
            self.assertEqual(e_track.get('flag'), 0)

        # Check font and styling in materials
        texts = proj.data['materials']['texts']
        # Find general subtitles
        gen_mats = [m for m in texts if 'Helvetica' in m.get('font_title', '') or 'Helvetica' in m.get('font_path', '')]
        self.assertTrue(len(gen_mats) > 0, "Helvetica must be used for general subtitles")

        # Find escalera subtitles
        esc_mats = [m for m in texts if 'Playfair' in m.get('font_title', '') or 'Playfair' in m.get('font_path', '')]
        self.assertTrue(len(esc_mats) > 0, "Playfair Display must be used for escalera")

        # Check punchline font size
        sizes = [m.get('font_size') for m in esc_mats]
        self.assertIn(18.08, sizes, "At least one escalera step must have punchline size 18.08")

        # Ensure all escalera segments end at the exact same timestamp (hook end = 3500000 us)
        e_segs_end_times = []
        for i in range(1, 5):
            segs = text_tracks[i].get('segments', [])
            if segs:
                tr = segs[0]['target_timerange']
                e_segs_end_times.append(tr['start'] + tr['duration'])

        self.assertTrue(all(et == e_segs_end_times[0] for et in e_segs_end_times),
                        "All escalera steps must finish simultaneously at segment end")


if __name__ == '__main__':
    unittest.main()
