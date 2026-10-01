import unittest
import json
from core.text_utils import clean_subtitle_text, find_phrase_timing

class TestAcousticLock(unittest.TestCase):
    def test_phrase_timing_with_capcut_words(self):
        # Segment 3 from Sep Gerardo 5: 'a un congreso'
        seg_start_us = 1000000
        seg_dur_us = 1033333
        words_data = {
            'start_time': [0, 120, 120, 200, 200],
            'end_time': [120, 120, 200, 200, 1020],
            'text': ['a', ' ', 'un', ' ', 'congreso']
        }
        full_text = 'a un congreso'
        
        # Test full match
        st, et = find_phrase_timing(seg_start_us, seg_dur_us, words_data, full_text, 'a un congreso')
        self.assertEqual(st, 1000000)
        self.assertEqual(et, 2020000)
        
        # Test sub-phrase match 'un congreso'
        st, et = find_phrase_timing(seg_start_us, seg_dur_us, words_data, full_text, 'un congreso')
        self.assertEqual(st, 1120000)
        self.assertEqual(et, 2020000)
        
        # Test single word 'congreso'
        st, et = find_phrase_timing(seg_start_us, seg_dur_us, words_data, full_text, 'congreso')
        self.assertEqual(st, 1200000)
        self.assertEqual(et, 2020000)

    def test_phrase_timing_fallback_proportional(self):
        seg_start_us = 2000000
        seg_dur_us = 1000000
        full_text = 'hola mundo'
        
        st, et = find_phrase_timing(seg_start_us, seg_dur_us, None, full_text, 'mundo')
        self.assertGreaterEqual(st, 2000000)
        self.assertLessEqual(et, 3000000)
        self.assertTrue(st < et)

if __name__ == '__main__':
    unittest.main()
