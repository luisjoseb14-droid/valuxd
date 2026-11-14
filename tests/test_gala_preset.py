import json
import unittest

from core.capcut_draft import SubtitleItem
from core.dual_styler import DualStyler


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


def _extract_dual_layers(data):
    """Returns (top_segments, bottom_segments, audio_starts_us) from styled project data."""
    texts_by_id = {t["id"]: t for t in data.get("materials", {}).get("texts", [])}
    text_tracks = [t for t in data.get("tracks", []) if t.get("type") == "text"]

    def _read_track(idx):
        if idx >= len(text_tracks):
            return []
        res = []
        for seg in text_tracks[idx].get("segments", []):
            mat = texts_by_id.get(seg["material_id"], {})
            try:
                content_obj = json.loads(mat.get("content", "{}"))
                txt = content_obj.get("text", "")
                font_path = ""
                if content_obj.get("styles"):
                    font_path = content_obj["styles"][0].get("font", {}).get("path", "")
            except Exception:
                txt = ""
                font_path = ""
            res.append(
                {
                    "text": txt,
                    "start": seg["target_timerange"]["start"],
                    "end": seg["target_timerange"]["start"] + seg["target_timerange"]["duration"],
                    "duration": seg["target_timerange"]["duration"],
                    "font_path": font_path,
                }
            )
        return res

    audio_starts = []
    for trk in data.get("tracks", []):
        if trk.get("type") == "audio":
            for seg in trk.get("segments", []):
                audio_starts.append(seg["target_timerange"]["start"])

    return _read_track(0), _read_track(1), audio_starts


class TestGalaPresetForcedHighlight(unittest.TestCase):
    def test_en_clinica_gala_unique_single_segment(self):
        """'En clínica Gala Unique' renders 'En clínica' on top and 'Gala Unique' highlighted below with click FX."""
        proj, data = _make_mock_project([("En clínica Gala Unique", 0, 1400000)])

        class EmptyHL:
            def suggest_highlights(self, text, count=10):
                return []

        styler = DualStyler.from_preset("gala")
        self.assertIn("Gala Unique", styler.always_highlight_phrases)
        styler.auto_dual_process(proj, highlighter=EmptyHL())

        top, bot, clicks = _extract_dual_layers(data)
        self.assertEqual([t["text"] for t in top], ["En clínica"])
        self.assertEqual([b["text"] for b in bot], ["Gala Unique"])
        self.assertTrue(bot[0]["font_path"].lower().endswith("things.otf"), f"Got font: {bot[0]['font_path']}")
        self.assertEqual(top[0]["end"], bot[0]["end"])
        self.assertIn(bot[0]["start"], clicks)

    def test_en_clinica_gala_unique_two_segments_ignores_cooldown(self):
        """Even < 3.0s after another highlight, 'En clínica' stays general top and 'Gala Unique' is highlighted below."""
        proj, data = _make_mock_project(
            [
                ("Descubre este tratamiento", 0, 1100000),
                ("En clínica", 1200000, 500000),
                ("Gala Unique", 1720000, 800000),
            ]
        )

        class MockHL:
            def suggest_highlights(self, text, count=10):
                return ["tratamiento", "clínica"]

        styler = DualStyler.from_preset("gala")
        styler.auto_dual_process(proj, highlighter=MockHL(), min_pacing_sec=3.0)

        top, bot, clicks = _extract_dual_layers(data)
        top_texts = [t["text"] for t in top]
        bot_texts = [b["text"] for b in bot]

        self.assertIn("tratamiento", bot_texts)
        self.assertIn("Gala Unique", bot_texts)
        self.assertFalse(any("clínica" in b.lower() for b in bot_texts), f"Lead-in highlighted unexpectedly: {bot_texts}")
        self.assertTrue(any(t["text"] == "En clínica" for t in top), f"Top texts: {top_texts}")
        clinica_top = next(t for t in top if t["text"] == "En clínica")
        gala_bot = next(b for b in bot if b["text"] == "Gala Unique")
        self.assertGreaterEqual(clinica_top["end"], gala_bot["end"])
        self.assertFalse(any(t["text"] == "Gala Unique" for t in top), f"Unexpected solo/duplicate top: {top_texts}")
        self.assertIn(gala_bot["start"], clicks)

    def test_split_gala_and_unique_regrouped_across_segments(self):
        """Split 'En clínica Gala' + 'Unique es ideal' regroups 'Gala Unique' intact on bottom."""
        proj, data = _make_mock_project(
            [
                ("En clínica Gala", 0, 900000),
                ("Unique es ideal", 920000, 900000),
            ]
        )

        class EmptyHL:
            def suggest_highlights(self, text, count=10):
                return []

        styler = DualStyler.from_preset("gala")
        styler.auto_dual_process(proj, highlighter=EmptyHL())

        top, bot, clicks = _extract_dual_layers(data)
        top_texts = [t["text"] for t in top]
        bot_texts = [b["text"] for b in bot]

        self.assertEqual(bot_texts, ["Gala Unique"])
        self.assertIn("En clínica", top_texts)
        self.assertTrue(any("es ideal" in t.lower() for t in top_texts), f"Got top: {top_texts}")
        self.assertEqual(len(clicks), 1)

    def test_preserves_gala_unique_casing_from_lowercase(self):
        """Lowercase/mismatched 'gala unique' or 'Gala unique' normalizes strictly to 'Gala Unique'."""
        proj, data = _make_mock_project(
            [
                ("en clínica gala unique", 0, 1200000),
                ("solo en Gala unique", 1500000, 1100000),
                ("visita GALA UNIQUE hoy", 3000000, 1200000),
            ]
        )

        class EmptyHL:
            def suggest_highlights(self, text, count=10):
                return []

        styler = DualStyler.from_preset("gala")
        styler.auto_dual_process(proj, highlighter=EmptyHL())

        top, bot, clicks = _extract_dual_layers(data)
        self.assertEqual([t["text"] for t in top], ["en clínica", "solo en", "visita", "hoy"])
        self.assertEqual([b["text"] for b in bot], ["Gala Unique", "Gala Unique", "Gala Unique"])
        self.assertEqual(len(clicks), 3)


if __name__ == "__main__":
    unittest.main()
