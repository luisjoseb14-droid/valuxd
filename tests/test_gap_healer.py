# -*- coding: utf-8 -*-
import unittest
import os
import json
import wave
import math
import struct
import tempfile
import shutil

from core.capcut_draft import CapCutProject
from core.dual_styler import DualStyler
from core.gap_healer import (
    find_subtitle_gaps,
    verify_gap_audio_energy,
    extract_gap_audio_snippet,
    insert_healed_subtitles,
    auto_heal_project_gaps,
    SubtitleGap
)
from ai.transcriber import AudioTranscriber

class TestGapHealer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.draft_file = os.path.join(self.test_dir, 'draft_content.json')

        # Generate a synthetic WAV file: 2 seconds of loud audio tone, 2 seconds of silence
        self.media_file = os.path.join(self.test_dir, 'media.wav')
        with wave.open(self.media_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            # 2 sec audio (approx -10 dB)
            samples = [int(10000 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(32000)]
            # 2 sec silence
            samples.extend([0] * 32000)
            wf.writeframes(struct.pack(f'<{len(samples)}h', *samples))

        # Synthetic CapCut draft with a gap between 1.0s and 2.5s (duration 1.5s)
        draft_content = {
            "canvas_config": {"height": 1920, "ratio": "original", "width": 1080},
            "duration": 4000000,
            "fps": 30.0,
            "materials": {
                "videos": [
                    {
                        "id": "VID_0",
                        "path": self.media_file,
                        "duration": 4000000
                    }
                ],
                "texts": [
                    {
                        "id": "MAT_0",
                        "content": json.dumps({"text": "primera frase", "styles": []}),
                        "type": "subtitle"
                    },
                    {
                        "id": "MAT_1",
                        "content": json.dumps({"text": "tercera frase", "styles": []}),
                        "type": "subtitle"
                    }
                ]
            },
            "tracks": [
                {
                    "id": "TRK_VID",
                    "type": "video",
                    "segments": [
                        {
                            "id": "VSEG_0",
                            "material_id": "VID_0",
                            "target_timerange": {"start": 0, "duration": 4000000},
                            "source_timerange": {"start": 0, "duration": 4000000}
                        }
                    ]
                },
                {
                    "id": "TRK_TEXT",
                    "type": "text",
                    "segments": [
                        {"id": "SEG_0", "material_id": "MAT_0", "target_timerange": {"start": 0, "duration": 1000000}},
                        # Gap here: 1,000,000 to 2,500,000 (1.5 seconds)
                        {"id": "SEG_1", "material_id": "MAT_1", "target_timerange": {"start": 2500000, "duration": 1500000}}
                    ]
                }
            ]
        }

        with open(self.draft_file, 'w', encoding='utf-8') as f:
            json.dump(draft_content, f)

        self.project = CapCutProject(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_find_subtitle_gaps(self):
        gaps = find_subtitle_gaps(self.project, min_gap_sec=0.5, max_gap_sec=5.0)
        self.assertEqual(len(gaps), 1)
        gap = gaps[0]
        self.assertEqual(gap.start_us, 1000000)
        self.assertEqual(gap.end_us, 2500000)
        self.assertEqual(gap.duration_us, 1500000)
        self.assertEqual(gap.prev_text, "primera frase")
        self.assertEqual(gap.next_text, "tercera frase")
        self.assertEqual(gap.media_path, self.media_file)
        self.assertAlmostEqual(gap.file_start_sec, 1.0, places=2)
        self.assertAlmostEqual(gap.duration_sec, 1.5, places=2)

    def test_verify_gap_audio_energy(self):
        gaps = find_subtitle_gaps(self.project)
        gap = gaps[0]
        # In our media file, 0..2.0s has tone, so 1.0..2.5s has active audio
        has_voice, max_v, mean_v = verify_gap_audio_energy(gap, threshold_db=-40.0)
        self.assertTrue(has_voice)
        self.assertGreater(max_v, -30.0)

        # Now test a gap in pure silence (2.5s..3.5s)
        silent_gap = SubtitleGap(
            index=99,
            start_us=2500000,
            end_us=3500000,
            duration_us=1000000,
            media_path=self.media_file,
            file_start_sec=2.5,
            duration_sec=1.0
        )
        has_voice_silence, max_v_sil, _ = verify_gap_audio_energy(silent_gap, threshold_db=-40.0)
        self.assertFalse(has_voice_silence)
        self.assertLess(max_v_sil, -80.0)

    def test_extract_gap_audio_snippet(self):
        gaps = find_subtitle_gaps(self.project)
        out_wav = os.path.join(self.test_dir, 'snippet.wav')
        ok = extract_gap_audio_snippet(gaps[0], out_wav)
        self.assertTrue(ok)
        self.assertTrue(os.path.isfile(out_wav))
        self.assertGreater(os.path.getsize(out_wav), 1000)

    def test_insert_healed_subtitles(self):
        styler = DualStyler.from_preset("cuidus")
        healed_items = [
            {
                "start_us": 1000000,
                "duration_us": 1500000,
                "text": "palabra intermedia, con comas y puntos."
            }
        ]
        count = insert_healed_subtitles(self.project, healed_items, styler)
        self.assertEqual(count, 1)

        # Verify project subtitles now have 3 segments
        text_track = [t for t in self.project.data['tracks'] if t.get('type') == 'text'][0]
        self.assertEqual(len(text_track['segments']), 3)

        # Verify order
        starts = [s['target_timerange']['start'] for s in text_track['segments']]
        self.assertEqual(starts, [0, 1000000, 2500000])

        # Verify punctuation rule (0 commas, 0 dots)
        texts_by_id = {t['id']: t for t in self.project.data['materials']['texts']}
        healed_seg = text_track['segments'][1]
        healed_mat = texts_by_id[healed_seg['material_id']]
        c = json.loads(healed_mat['content'])
        self.assertNotIn(",", c['text'])
        self.assertNotIn(".", c['text'])
        self.assertEqual(c['text'], "palabra intermedia con comas y puntos")

        # Verify shadow diffuse integrity
        styles = c.get('styles', [])
        shadow = styles[0]['shadows'][0]
        self.assertEqual(shadow['diffuse'], 0.02500000037252903)

    def test_auto_heal_project_gaps(self):
        class MockTranscriber:
            def is_configured(self):
                return True
            def transcribe(self, path):
                return "frase recuperada con IA, y sin puntos."

        styler = DualStyler.from_preset("laura burgos")
        # Run auto_heal_project_gaps on self.project (has 1 gap of 1.5s with loud tone)
        count, unhealed = auto_heal_project_gaps(
            self.project,
            styler=styler,
            transcriber=MockTranscriber()
        )
        self.assertEqual(count, 1)
        self.assertEqual(len(unhealed), 0)

        # Verify the healed segment was inserted
        text_track = [t for t in self.project.data['tracks'] if t.get('type') == 'text'][0]
        self.assertEqual(len(text_track['segments']), 3)

        texts_by_id = {t['id']: t for t in self.project.data['materials']['texts']}
        healed_seg = text_track['segments'][1]
        healed_mat = texts_by_id[healed_seg['material_id']]
        c = json.loads(healed_mat['content'])
        self.assertNotIn(",", c['text'])
        self.assertNotIn(".", c['text'])
        self.assertEqual(c['text'], "frase recuperada con IA y sin puntos")

if __name__ == '__main__':
    unittest.main()
