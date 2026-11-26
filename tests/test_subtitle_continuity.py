import json
import unittest

from core.capcut_draft import SubtitleItem
from core.dual_styler import DualStyler
from core.text_utils import fix_question_marks_and_broken_tokens, rebalance_subtitle_segments


def _make_mock_project(segments_spec):
    """Creates a minimal CapCut-like project dict + wrapper from (text, start_us, dur_us) tuples."""
    texts = []
    segs = []
    for idx, (text, start_us, dur_us) in enumerate(segments_spec):
        mat_id = f"M{idx}"
        words_list = text.split()
        step_ms = max(50, int((dur_us // 1000) / max(1, len(words_list))))
        w_texts = []
        w_starts = []
        w_ends = []
        for k, w in enumerate(words_list):
            if k > 0:
                w_texts.append(" ")
                w_starts.append(k * step_ms)
                w_ends.append(k * step_ms)
            w_texts.append(w)
            w_starts.append(k * step_ms)
            w_ends.append((k + 1) * step_ms if k < len(words_list) - 1 else int(dur_us // 1000))
        texts.append(
            {
                "id": mat_id,
                "content": json.dumps({"text": text, "styles": [{"range": [0, len(text)]}]}),
                "words": {"text": w_texts, "start_time": w_starts, "end_time": w_ends},
            }
        )
        segs.append(
            {
                "id": f"S{idx}",
                "material_id": mat_id,
                "target_timerange": {"start": start_us, "duration": dur_us},
                "extra_material_refs": [],
            }
        )

    data = {
        "materials": {"texts": texts, "text_animations": [], "stickers": [], "audios": []},
        "tracks": [{"id": "T1", "type": "text", "segments": segs}],
    }

    class MockProject:
        def __init__(self, d):
            self.data = d
            self.subtitles = []
            t_map = {t["id"]: t for t in d["materials"]["texts"]}
            for s in d["tracks"][0]["segments"]:
                self.subtitles.append(SubtitleItem(0, s, t_map[s["material_id"]]))

        def _parse_subtitles(self):
            pass

    return MockProject(data), data


def _extract_track_texts(data):
    texts_by_id = {t["id"]: t for t in data["materials"]["texts"]}
    out = []
    for trk in data["tracks"]:
        if trk.get("type") != "text":
            continue
        for seg in trk.get("segments", []):
            t_mat = texts_by_id.get(seg["material_id"], {})
            try:
                txt = json.loads(t_mat.get("content", "{}")).get("text", "")
            except Exception:
                txt = ""
            out.append((txt, seg["target_timerange"]["start"], seg["target_timerange"]["duration"]))
    return out


class TestSubtitleContinuity(unittest.TestCase):
    def test_dermatitis_sentence_continuity(self):
        """User's exact example: rebalances broken clauses into coherent lines."""
        raw_items = [
            {"index": 0, "text": "la dermatitis", "start": 0, "end": 800000, "duration": 800000, "words": None},
            {"index": 1, "text": "es completamente", "start": 800000, "end": 1600000, "duration": 800000, "words": None},
            {"index": 2, "text": "curable en clinica", "start": 1600000, "end": 2500000, "duration": 900000, "words": None},
            {"index": 3, "text": "gala la curamos sigueme", "start": 2500000, "end": 3700000, "duration": 1200000, "words": None},
            {"index": 4, "text": "para mas", "start": 3700000, "end": 4300000, "duration": 600000, "words": None},
        ]
        rebalanced = rebalance_subtitle_segments(raw_items, max_chars=22, max_words=4)
        texts = [it["text"] for it in rebalanced]
        self.assertEqual(
            texts,
            [
                "la dermatitis",
                "es completamente curable",
                "en clínica Gala",
                "la curamos",
                "Sígueme para más",
            ],
        )
        # Ensure timestamps are strictly monotonic and non-overlapping
        for k in range(len(rebalanced) - 1):
            self.assertLess(rebalanced[k]["start"], rebalanced[k]["end"])
            self.assertLessEqual(rebalanced[k]["end"], rebalanced[k + 1]["start"] + 1000)

    def test_no_split_s_word_in_highlight(self):
        """Never slices singular highlight inside plural word leaving 's' on its own line."""
        proj, data = _make_mock_project(
            [
                ("la dermatitis", 0, 900000),
                ("teniendo escapes", 1200000, 900000),
            ]
        )

        class MockHL:
            def suggest_highlights(self, text, count=10):
                return ["dermatiti", "escape"]

        styler = DualStyler.from_preset("gerardo")
        styler.auto_dual_process(proj, highlighter=MockHL(), min_pacing_sec=0.2)
        rendered = _extract_track_texts(data)
        rendered_texts = [t for t, _, _ in rendered]

        self.assertNotIn("s", [t.strip().lower() for t in rendered_texts])
        self.assertTrue(any("dermatitis" in t.lower() for t in rendered_texts), f"Got: {rendered_texts}")
        self.assertTrue(any("escapes" in t.lower() for t in rendered_texts), f"Got: {rendered_texts}")

    def test_no_detached_question_marks(self):
        """Question marks ¿ and ? must stay attached and never become standalone lines."""
        # Case A: CapCut already split into "¿tienes este", "problema", "?"
        raw_items = [
            {"index": 0, "text": "¿tienes este", "start": 0, "end": 600000, "duration": 600000, "words": None},
            {"index": 1, "text": "problema", "start": 600000, "end": 1100000, "duration": 500000, "words": None},
            {"index": 2, "text": "?", "start": 1100000, "end": 1250000, "duration": 150000, "words": None},
        ]
        rebalanced = fix_question_marks_and_broken_tokens(raw_items)
        self.assertEqual([x["text"] for x in rebalanced], ["¿Tienes este", "problema?"])

        # Case B: Highlighting last word of "¿Tienes este problema?" must not put "?" on a 3rd line
        proj, data = _make_mock_project([("¿Tienes este problema?", 0, 1200000)])

        class MockHL:
            def suggest_highlights(self, text, count=10):
                return ["problema"]

        styler = DualStyler.from_preset("gerardo")
        styler.auto_dual_process(proj, highlighter=MockHL(), min_pacing_sec=0.1)
        rendered = [t for t, _, _ in _extract_track_texts(data)]

        self.assertNotIn("?", [t.strip() for t in rendered])
        self.assertNotIn("¿", [t.strip() for t in rendered])
        self.assertTrue(any(t.startswith("¿Tienes") for t in rendered), f"Got: {rendered}")
        self.assertTrue(any(t.lower().endswith("problema?") for t in rendered), f"Got: {rendered}")

    def test_unify_imperceptible_short_words(self):
        """Short orphan words ('que', 'la', 'el', 'es') must unify into adjacent lines."""
        raw_items = [
            {"index": 0, "text": "es", "start": 0, "end": 150000, "duration": 150000, "words": None},
            {"index": 1, "text": "el mejor momento", "start": 180000, "end": 900000, "duration": 720000, "words": None},
            {"index": 2, "text": "para", "start": 950000, "end": 1100000, "duration": 150000, "words": None},
            {"index": 3, "text": "empezar hoy", "start": 1120000, "end": 1800000, "duration": 680000, "words": None},
        ]
        rebalanced = rebalance_subtitle_segments(raw_items, max_chars=22, max_words=4)
        texts = [x["text"] for x in rebalanced]
        self.assertTrue(all(len(t.split()) >= 2 for t in texts), f"Orphan short line remained: {texts}")
        self.assertIn("empezar", " ".join(texts).lower())

        # Also ensure a post-highlight orphan suffix ('sabías que' -> highlight 'sabías') pushes 'que' forward
        proj, data = _make_mock_project(
            [
                ("sabías que", 0, 700000),
                ("el alcohol afecta", 720000, 1100000),
            ]
        )

        class MockHL2:
            def suggest_highlights(self, text, count=10):
                return ["sabías"]

        styler = DualStyler.from_preset("gerardo")
        styler.auto_dual_process(proj, highlighter=MockHL2(), min_pacing_sec=0.1)
        rendered = [t for t, _, _ in _extract_track_texts(data)]
        self.assertNotIn("que", [t.strip().lower() for t in rendered], f"Orphan 'que' emitted alone: {rendered}")
        self.assertTrue(any("que el" in t.lower() for t in rendered), f"Got: {rendered}")


if __name__ == "__main__":
    unittest.main()
