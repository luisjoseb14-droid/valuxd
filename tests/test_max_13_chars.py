import json
import os
import sys
import tempfile
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.capcut_draft import CapCutProject
from core.dual_styler import DualStyler
from core.text_utils import (
    HARD_MAX_LINE_CHARS,
    rebalance_subtitle_segments,
    segment_exceeds_line_budget,
    split_wide_segment_for_safe_margins,
)


def _make_words(pairs):
    texts, starts, ends = [], [], []
    for idx, (word, s_ms, e_ms) in enumerate(pairs):
        if idx > 0:
            prev_e = ends[-1]
            texts.append(" ")
            starts.append(prev_e)
            ends.append(s_ms)
        texts.append(word)
        starts.append(s_ms)
        ends.append(e_ms)
    return {"text": texts, "start_time": starts, "end_time": ends}


def _make_project(tmpdir, segments_spec):
    texts = []
    segs = []
    for idx, spec in enumerate(segments_spec):
        mat_id = f"MAT_{idx}"
        txt = spec["text"]
        t_entry = {
            "id": mat_id,
            "type": "subtitle",
            "content": json.dumps({
                "text": txt,
                "styles": [{"range": [0, len(txt)], "size": 10.0}],
            }, ensure_ascii=False),
            "words": spec.get("words") or _make_words(
                [(w, i * 250, (i + 1) * 250) for i, w in enumerate(txt.split())]
            ),
        }
        texts.append(t_entry)
        segs.append({
            "id": f"SEG_{idx}",
            "material_id": mat_id,
            "target_timerange": {
                "start": spec["start"],
                "duration": spec["end"] - spec["start"],
            },
            "clip": {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": 0.0}},
            "extra_material_refs": [],
        })

    draft = {
        "canvas_config": {"width": 1080, "height": 1920},
        "tracks": [
            {"id": "VID_0", "type": "video", "segments": []},
            {"id": "TXT_0", "type": "text", "segments": segs},
        ],
        "materials": {
            "texts": texts,
            "audios": [],
            "material_animations": [],
            "canvases": [],
            "effects": [],
            "stickers": [],
            "transitions": [],
            "videos": [],
        },
    }
    path = os.path.join(tmpdir, "draft_content.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False)
    return CapCutProject(tmpdir)


class TestMax13CharsLineLimit(unittest.TestCase):
    def test_hard_limit_splits_multi_word_phrases_in_half_but_preserves_single_long_words(self):
        self.assertEqual(HARD_MAX_LINE_CHARS, 13)

        # User screenshot case: "son muy populares" (17 chars) -> ["son muy", "populares"]
        seg_pop = {
            "index": 0, "start": 0, "end": 1200000, "duration": 1200000,
            "text": "son muy populares",
            "words": _make_words([("son", 0, 300), ("muy", 300, 550), ("populares", 550, 1200)]),
        }
        pieces_pop = [p["text"] for p in split_wide_segment_for_safe_margins(seg_pop)]
        self.assertEqual(pieces_pop, ["son muy", "populares"])
        self.assertTrue(all(len(p) <= 13 for p in pieces_pop))

        # "para proteger tu piel" (21 chars) -> ["para proteger", "tu piel"]
        seg_prot = {
            "index": 1, "start": 0, "end": 1300000, "duration": 1300000,
            "text": "para proteger tu piel",
            "words": _make_words([("para", 0, 300), ("proteger", 300, 700), ("tu", 700, 900), ("piel", 900, 1300)]),
        }
        pieces_prot = [p["text"] for p in split_wide_segment_for_safe_margins(seg_prot)]
        self.assertEqual(pieces_prot, ["para proteger", "tu piel"])
        self.assertTrue(all(len(p) <= 13 for p in pieces_prot))

        # "sacar el máximo" (15 chars) -> ["sacar", "el máximo"]
        seg_max = {
            "index": 2, "start": 0, "end": 1000000, "duration": 1000000,
            "text": "sacar el máximo",
            "words": _make_words([("sacar", 0, 350), ("el", 350, 500), ("máximo", 500, 1000)]),
        }
        pieces_max = [p["text"] for p in split_wide_segment_for_safe_margins(seg_max)]
        self.assertEqual(pieces_max, ["sacar", "el máximo"])
        self.assertTrue(all(len(p) <= 13 for p in pieces_max))

        # Punctuation & spaces count toward the 13-char cap: "¿cómo estás hoy?" (16 chars)
        seg_q = {
            "index": 3, "start": 0, "end": 1000000, "duration": 1000000,
            "text": "¿cómo estás hoy?",
            "words": _make_words([("¿cómo", 0, 350), ("estás", 350, 700), ("hoy?", 700, 1000)]),
        }
        pieces_q = [p["text"] for p in split_wide_segment_for_safe_margins(seg_q)]
        self.assertGreater(len(pieces_q), 1)
        self.assertTrue(all(len(p) <= 13 for p in pieces_q if len(p.split()) > 1))

        # Single very long word > 13 chars MUST stay intact
        seg_single = {"index": 4, "start": 0, "end": 1000000, "duration": 1000000, "text": "otorrinolaringología"}
        self.assertFalse(segment_exceeds_line_budget(["otorrinolaringología"]))
        self.assertEqual([p["text"] for p in split_wide_segment_for_safe_margins(seg_single)], ["otorrinolaringología"])

        # Bridge + single very long word (26 chars) splits before long word, leaving single word intact
        seg_mix = {
            "index": 5, "start": 0, "end": 1500000, "duration": 1500000,
            "text": "en la otorrinolaringología",
            "words": _make_words([("en", 0, 200), ("la", 200, 400), ("otorrinolaringología", 400, 1500)]),
        }
        pieces_mix = [p["text"] for p in split_wide_segment_for_safe_margins(seg_mix)]
        self.assertEqual(pieces_mix, ["en la", "otorrinolaringología"])

        # Lone tiny/functional words (y, el, lo, al, es) must NEVER be left alone on a line
        for phrase in ["y neurofibroma", "el otorrinolaringólogo", "al neurofibroma", "lo importante es"]:
            seg_tiny = {"index": 6, "start": 0, "end": 1200000, "duration": 1200000, "text": phrase}
            pieces_tiny = [p["text"] for p in split_wide_segment_for_safe_margins(seg_tiny)]
            self.assertEqual(pieces_tiny, [phrase], f"Should not isolate tiny functional word in {phrase!r}: {pieces_tiny}")

    def test_rebalance_subtitle_segments_respects_13_chars_default(self):
        raw_items = [
            {
                "index": 0, "start": 0, "end": 350000, "duration": 350000,
                "text": "son",
                "words": _make_words([("son", 0, 350)]),
            },
            {
                "index": 1, "start": 380000, "end": 650000, "duration": 270000,
                "text": "muy",
                "words": _make_words([("muy", 0, 270)]),
            },
            {
                "index": 2, "start": 680000, "end": 1200000, "duration": 520000,
                "text": "populares",
                "words": _make_words([("populares", 0, 520)]),
            },
            {
                "index": 3, "start": 1250000, "end": 2250000, "duration": 1000000,
                "text": "otorrinolaringología",
                "words": _make_words([("otorrinolaringología", 0, 1000)]),
            },
        ]
        rebalanced = rebalance_subtitle_segments(raw_items)
        texts = [it["text"] for it in rebalanced]
        self.assertIn("otorrinolaringología", texts)
        for t in texts:
            if len(t.split()) > 1:
                self.assertLessEqual(len(t), 13, f"Multi-word line {t!r} exceeds 13 chars ({len(t)})")

    def test_e2e_inline_jose_and_dual_gerardo_never_exceed_13_chars_on_multi_word(self):
        specs = [
            {
                "text": "son muy populares",
                "start": 0, "end": 1200000,
                "words": _make_words([("son", 0, 300), ("muy", 300, 550), ("populares", 550, 1200)]),
            },
            {
                "text": "para proteger tu piel",
                "start": 1300000, "end": 2600000,
                "words": _make_words([("para", 0, 300), ("proteger", 300, 700), ("tu", 700, 900), ("piel", 900, 1300)]),
            },
            {
                "text": "otorrinolaringología",
                "start": 2700000, "end": 3800000,
                "words": _make_words([("otorrinolaringología", 0, 1100)]),
            },
        ]

        for preset_name in ("jose", "gerardo"):
            with tempfile.TemporaryDirectory() as tmpdir:
                proj = _make_project(tmpdir, specs)
                styler = DualStyler.from_preset(preset_name)
                styler.auto_dual_process(proj, openrouter_key=None)
                mats = {m["id"]: m for m in proj.data["materials"]["texts"]}
                output_texts = []
                for trk in proj.data["tracks"]:
                    if trk.get("type") == "text":
                        for seg in trk.get("segments", []):
                            txt = json.loads(mats[seg["material_id"]]["content"])["text"]
                            output_texts.append(txt)
                            if len(txt.split()) > 1:
                                self.assertLessEqual(
                                    len(txt),
                                    13,
                                    f"[{preset_name}] Multi-word subtitle {txt!r} exceeds 13 chars ({len(txt)})",
                                )
                self.assertTrue(
                    any("otorrinolaringología" in t.lower() for t in output_texts),
                    f"[{preset_name}] Single long word should remain intact: {output_texts}",
                )


if __name__ == "__main__":
    unittest.main()
