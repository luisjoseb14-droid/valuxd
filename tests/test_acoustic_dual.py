import unittest
import json
from core.capcut_draft import CapCutProject, SubtitleItem
from core.dual_styler import DualStyler

class TestAcousticDual(unittest.TestCase):
    def test_zero_anticipation_and_exact_timestamps(self):
        styler = DualStyler.from_preset('gerardo')
        
        # Create dummy CapCut project data
        data = {
            'materials': {
                'texts': [
                    {
                        'id': 'M1',
                        'content': json.dumps({'text': 'Ponte', 'styles': [{'range': [0, 5]}]}),
                        'words': {'start_time': [0], 'end_time': [200], 'text': ['Ponte']}
                    },
                    {
                        'id': 'M2',
                        'content': json.dumps({'text': 'en situacion', 'styles': [{'range': [0, 12]}]}),
                        'words': {'start_time': [0, 40, 80], 'end_time': [40, 40, 800], 'text': ['en', ' ', 'situacion']}
                    },
                    {
                        'id': 'M3',
                        'content': json.dumps({'text': 'vas', 'styles': [{'range': [0, 3]}]}),
                        'words': {'start_time': [0], 'end_time': [160], 'text': ['vas']}
                    },
                    {
                        'id': 'M4',
                        'content': json.dumps({'text': 'a un congreso', 'styles': [{'range': [0, 13]}]}),
                        'words': {'start_time': [0, 120, 120, 200, 200], 'end_time': [120, 120, 200, 200, 1020], 'text': ['a', ' ', 'un', ' ', 'congreso']}
                    }
                ]
            },
            'tracks': [
                {
                    'id': 'T1',
                    'type': 'text',
                    'segments': [
                        {'id': 'S1', 'material_id': 'M1', 'target_timerange': {'start': 30000, 'duration': 200000}, 'extra_material_refs': []},
                        {'id': 'S2', 'material_id': 'M2', 'target_timerange': {'start': 230000, 'duration': 570000}, 'extra_material_refs': []},
                        {'id': 'S3', 'material_id': 'M3', 'target_timerange': {'start': 830000, 'duration': 170000}, 'extra_material_refs': []},
                        {'id': 'S4', 'material_id': 'M4', 'target_timerange': {'start': 1000000, 'duration': 1033333}, 'extra_material_refs': []}
                    ]
                }
            ]
        }
        
        class MockProject:
            def __init__(self, d):
                self.data = d
                self.subtitles = []
                texts = {t['id']: t for t in d['materials']['texts']}
                for seg in d['tracks'][0]['segments']:
                    self.subtitles.append(SubtitleItem(0, seg, texts[seg['material_id']]))
            def _parse_subtitles(self):
                pass
                
        proj = MockProject(data)
        
        # Test auto_dual_process with highlight 'un congreso'
        class MockHighlighter:
            def suggest_highlights(self, text, count=10):
                return ['un congreso']
                
        top_c, bot_c = styler.auto_dual_process(proj, highlighter=MockHighlighter(), min_pacing_sec=0.5)
        
        self.assertEqual(bot_c, 1)
        tracks = data['tracks']
        text_tracks = [t for t in tracks if t['type'] == 'text']
        self.assertEqual(len(text_tracks), 2)
        
        top_segs = text_tracks[0]['segments']
        bot_segs = text_tracks[1]['segments']
        
        # Check that Ponte and en situacion were NOT merged and did NOT anticipate words!
        self.assertEqual(top_segs[0]['target_timerange']['start'], 30000)
        self.assertEqual(top_segs[0]['target_timerange']['duration'], 200000)
        
        self.assertEqual(top_segs[1]['target_timerange']['start'], 230000)
        self.assertEqual(top_segs[1]['target_timerange']['duration'], 570000)
        
        self.assertEqual(top_segs[2]['target_timerange']['start'], 830000)
        self.assertEqual(top_segs[2]['target_timerange']['duration'], 170000)
        
        # Check highlight 'un congreso' start timestamp: 1000000 + 120ms = 1120000 us!
        self.assertEqual(bot_segs[0]['target_timerange']['start'], 1120000)
        self.assertEqual(bot_segs[0]['target_timerange']['duration'], 913333) # 2033333 - 1120000 (ends with curr_end)

    def test_highlight_never_spills_into_next_segment(self):
        """Verify that a highlight inside a short segment terminates strictly at curr_end and does not spill over."""
        styler = DualStyler.from_preset('laura')
        data = {
            'materials': {
                'texts': [
                    {'id': 'M1', 'content': json.dumps({'text': 'sobre la boca'}), 'words': {}},
                    {'id': 'M2', 'content': json.dumps({'text': 'del niño'}), 'words': {}}
                ]
            },
            'tracks': [
                {
                    'id': 'T1',
                    'type': 'text',
                    'segments': [
                        {'id': 'S1', 'material_id': 'M1', 'target_timerange': {'start': 30800000, 'duration': 600000}, 'extra_material_refs': []},
                        {'id': 'S2', 'material_id': 'M2', 'target_timerange': {'start': 31400000, 'duration': 533333}, 'extra_material_refs': []}
                    ]
                }
            ]
        }

        class MockProject:
            def __init__(self, d):
                self.data = d
                self.subtitles = []
                texts = {t['id']: t for t in d['materials']['texts']}
                for seg in d['tracks'][0]['segments']:
                    self.subtitles.append(SubtitleItem(0, seg, texts[seg['material_id']]))
            def _parse_subtitles(self):
                pass

        class MockHighlighter:
            def suggest_highlights(self, text, count=10):
                return ['boca']

        proj = MockProject(data)
        top_c, bot_c = styler.auto_dual_process(proj, highlighter=MockHighlighter(), min_pacing_sec=0.1)

        text_tracks = [t for t in data['tracks'] if t['type'] == 'text']
        top_segs = text_tracks[0]['segments']
        bot_segs = text_tracks[1]['segments']

        self.assertEqual(len(bot_segs), 1)
        bot_end = bot_segs[0]['target_timerange']['start'] + bot_segs[0]['target_timerange']['duration']
        next_top_start = top_segs[1]['target_timerange']['start']

        # Highlight MUST end at or before next_top_start (curr_end of first segment: 31400000)
        self.assertLessEqual(bot_end, next_top_start)
        self.assertEqual(bot_end, 31400000)

if __name__ == '__main__':
    unittest.main()
