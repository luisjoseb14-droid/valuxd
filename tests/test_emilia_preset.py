import unittest
import json
from core.capcut_draft import SubtitleItem
from core.dual_styler import DualStyler
from cc_subs_pro import resolve_preset
from core.text_utils import clean_subtitle_text

class TestEmiliaPreset(unittest.TestCase):
    def test_preset_resolution(self):
        preset = resolve_preset("emilia")
        self.assertTrue(preset, "Preset emilia should resolve properly")
        self.assertEqual(preset.get("name"), "Letra Emilia")
        
        # Verify fonts
        self.assertIn("Neue Helvena", preset["top"]["font_name"])
        self.assertIn("Karelle", preset["bottom"]["font_name"])
        
        # Verify animation and audio click
        self.assertIn("animation", preset["bottom"])
        self.assertEqual(preset["bottom"]["animation"].get("name"), "Mini zoom")
        self.assertTrue(preset.get("sound_fx", {}).get("enabled"))
        
        # Verify stickers configuration
        stickers_cfg = preset.get("stickers", {})
        self.assertTrue(stickers_cfg.get("enabled"))
        pool = stickers_cfg.get("pool", [])
        self.assertEqual(len(pool), 2)
        self.assertEqual(pool[0]["resource_id"], "7562803730404609285")
        self.assertEqual(pool[1]["resource_id"], "7468646543625588021")

    def test_zero_forbidden_punctuation(self):
        preset = resolve_preset("letra emilia")
        # Ensure default and highlight sample or metadata texts have no , . :
        for text in [preset.get("name", ""), preset.get("description", "")]:
            cleaned = clean_subtitle_text(text)
            self.assertNotIn(",", cleaned)
            self.assertNotIn(".", cleaned)
            self.assertNotIn(":", cleaned)

    def test_dual_process_with_stickers(self):
        styler = DualStyler.from_preset("emilia")
        self.assertIsNotNone(styler.stickers_cfg)
        self.assertEqual(len(styler.stickers_cfg.get('pool', [])), 2)

        data = {
            'materials': {
                'texts': [
                    {
                        'id': 'M1',
                        'content': json.dumps({'text': 'Hola a todos', 'styles': [{'range': [0, 12]}]}),
                        'words': {'start_time': [0, 100, 200], 'end_time': [100, 200, 400], 'text': ['Hola', 'a', 'todos']}
                    },
                    {
                        'id': 'M2',
                        'content': json.dumps({'text': 'este es un video especial', 'styles': [{'range': [0, 26]}]}),
                        'words': {'start_time': [0, 80, 160, 250, 400], 'end_time': [80, 160, 250, 400, 900], 'text': ['este', 'es', 'un', 'video', 'especial']}
                    }
                ]
            },
            'tracks': [
                {
                    'id': 'T1',
                    'type': 'text',
                    'segments': [
                        {'id': 'S1', 'material_id': 'M1', 'target_timerange': {'start': 0, 'duration': 1000000}, 'extra_material_refs': []},
                        {'id': 'S2', 'material_id': 'M2', 'target_timerange': {'start': 1000000, 'duration': 1500000}, 'extra_material_refs': []}
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
                return ['especial']

        proj = MockProject(data)
        top_c, bot_c = styler.auto_dual_process(proj, highlighter=MockHighlighter(), min_pacing_sec=0.1)

        self.assertEqual(bot_c, 1)

        # Check tracks created
        tracks = data['tracks']
        text_tracks = [t for t in tracks if t['type'] == 'text']
        sticker_tracks = [t for t in tracks if t.get('type') == 'sticker']
        audio_tracks = [t for t in tracks if t.get('type') == 'audio']

        self.assertEqual(len(text_tracks), 2, "Should have 2 text tracks")
        self.assertEqual(len(sticker_tracks), 1, "Should have 1 sticker track")
        self.assertEqual(len(audio_tracks), 1, "Should have 1 audio track for click sound")

        # Check sticker segment alignment
        stk_segs = sticker_tracks[0]['segments']
        self.assertEqual(len(stk_segs), 1)
        stk_seg = stk_segs[0]

        bot_seg = text_tracks[1]['segments'][0]
        self.assertEqual(stk_seg['target_timerange']['start'], bot_seg['target_timerange']['start'])
        self.assertEqual(stk_seg['target_timerange']['duration'], bot_seg['target_timerange']['duration'])

        # Check sticker material
        stk_mat_id = stk_seg['material_id']
        stk_mats = {m['id']: m for m in data['materials']['stickers']}
        self.assertIn(stk_mat_id, stk_mats)
        self.assertEqual(stk_mats[stk_mat_id]['resource_id'], '7562803730404609285')

        # Check clean text rule on generated texts
        for mat in data['materials']['texts']:
            content = json.loads(mat['content'])
            self.assertNotIn(",", content.get('text', ''))
            self.assertNotIn(".", content.get('text', ''))
            self.assertNotIn(":", content.get('text', ''))

if __name__ == '__main__':
    unittest.main()
