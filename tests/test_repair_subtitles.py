import unittest
import copy
from core.capcut_draft import CapCutProject
from core.dual_styler import DualStyler

class TestRepairSubtitles(unittest.TestCase):
    def test_repair_does_not_alter_timings_or_text(self):
        mock_data = {
            'materials': {
                'texts': [
                    {'id': 'T1', 'content': '{"text":"Hola mundo","styles":[]}', 'font_path': 'bad.ttf', 'font_size': 20.0},
                    {'id': 'T2', 'content': '{"text":"CLAVE","styles":[]}', 'font_path': 'bad2.ttf', 'font_size': 30.0}
                ]
            },
            'tracks': [
                {
                    'type': 'text',
                    'segments': [
                        {'id': 'S1', 'material_id': 'T1', 'target_timerange': {'start': 100000, 'duration': 500000}, 'source_timerange': {'start': 0, 'duration': 500000}, 'clip': {'transform': {'x': 0.5, 'y': -0.8}, 'scale': {'x': 0.9, 'y': 0.9}}}
                    ]
                },
                {
                    'type': 'text',
                    'segments': [
                        {'id': 'S2', 'material_id': 'T2', 'target_timerange': {'start': 200000, 'duration': 300000}, 'source_timerange': {'start': 0, 'duration': 300000}, 'clip': {'transform': {'x': 0.2, 'y': -0.4}, 'scale': {'x': 0.9, 'y': 0.9}}}
                    ]
                }
            ]
        }

        project = CapCutProject.__new__(CapCutProject)
        project.project_path = 'mock'
        project.data = copy.deepcopy(mock_data)
        project.materials = project.data['materials']
        project.tracks = project.data['tracks']
        project.subtitles = []

        styler = DualStyler.from_preset('gala')
        top_c, bot_c = styler.repair_project_subtitles(project)

        self.assertEqual(top_c, 1)
        self.assertEqual(bot_c, 1)

        s1 = project.data['tracks'][0]['segments'][0]
        self.assertEqual(s1['target_timerange'], {'start': 100000, 'duration': 500000})
        self.assertEqual(s1['source_timerange'], {'start': 0, 'duration': 500000})

        s2 = project.data['tracks'][1]['segments'][0]
        self.assertEqual(s2['target_timerange'], {'start': 200000, 'duration': 300000})
        self.assertEqual(s2['source_timerange'], {'start': 0, 'duration': 300000})

        t1 = next(t for t in project.data['materials']['texts'] if t['id'] == 'T1')
        self.assertIn('Hola mundo', t1['content'])
        self.assertEqual(t1['font_title'], 'Helvetica')
        self.assertEqual(t1['font_size'], 8.0)

        t2 = next(t for t in project.data['materials']['texts'] if t['id'] == 'T2')
        self.assertIn('CLAVE', t2['content'])
        self.assertEqual(t2['font_title'], 'Things')
        self.assertAlmostEqual(t2['font_size'], 19.246334, places=2)

        self.assertEqual(s1['clip']['transform']['x'], 0.0)
        self.assertAlmostEqual(s1['clip']['transform']['y'], -0.109564922934591, places=4)
        self.assertAlmostEqual(s1['clip']['scale']['x'], 1.3550004042363974, places=4)

        self.assertEqual(s2['clip']['transform']['x'], 0.0)
        self.assertAlmostEqual(s2['clip']['transform']['y'], -0.208030396080371, places=4)
        self.assertAlmostEqual(s2['clip']['scale']['x'], 1.3550004042363974, places=4)

if __name__ == '__main__':
    unittest.main()
