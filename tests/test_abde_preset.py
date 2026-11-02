# -*- coding: utf-8 -*-
import os
import sys
import json
import unittest

# Ensure repo root is on path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from core.preset_matcher import detect_preset_from_name
from core.text_utils import clean_subtitle_text
from core.dual_styler import DualStyler
from core.platform_paths import resolve_font_path, get_default_click_sound_path, resolve_effect_path
from core.font_installer import install_all_assets


class TestAbdePreset(unittest.TestCase):

    def test_preset_matcher(self):
        self.assertEqual(detect_preset_from_name("Abde"), "abde")
        self.assertEqual(detect_preset_from_name("Proyecto Abde 1"), "abde")
        self.assertEqual(detect_preset_from_name("Adbe final"), "abde")
        self.assertEqual(detect_preset_from_name(r"C:\CapCut\Projects\Abde"), "abde")

    def test_preset_json_structure(self):
        style_path = os.path.join(repo_root, "styles", "abde.json")
        self.assertTrue(os.path.isfile(style_path))
        with open(style_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        self.assertEqual(cfg.get("name"), "Letra Abde")
        self.assertEqual(cfg.get("layout"), "dual")
        self.assertTrue(cfg.get("keep_punctuation"))

        # Top layer
        top = cfg.get("top", {})
        self.assertIn("Akzidenz", top.get("font_name"))
        self.assertEqual(top.get("font_size"), 9.0)
        self.assertEqual(top.get("color"), "#FFFFFF")
        self.assertAlmostEqual(top.get("y", 0.0), 0.0)
        self.assertAlmostEqual(top.get("x", 0.0), 0.0504032258, places=4)

        # Bottom layer
        bot = cfg.get("bottom", {})
        self.assertIn("Akzidenz", bot.get("font_name"))
        self.assertEqual(bot.get("font_size"), 11.0)
        self.assertEqual(bot.get("color"), "#6D94FF")
        self.assertAlmostEqual(bot.get("y", 0.0), -0.079038, places=4)
        self.assertAlmostEqual(bot.get("x", 0.0), 0.032762, places=4)
        self.assertEqual(bot.get("animation", {}).get("name"), "Descenso")
        self.assertEqual(bot.get("animation", {}).get("resource_id"), "7648941380408053013")
        self.assertEqual(bot.get("animation", {}).get("duration"), 200000)

        # Sound fx
        snd = cfg.get("sound_fx", {})
        self.assertTrue(snd.get("enabled"))
        self.assertEqual(snd.get("name"), "鼠标单击1")
        self.assertEqual(snd.get("variation"), "intermittent")
        self.assertEqual(snd.get("duration"), 496000)

    def test_presets_json_registration(self):
        presets_path = os.path.join(repo_root, "styles", "presets.json")
        with open(presets_path, "r", encoding="utf-8") as f:
            presets = json.load(f)

        self.assertIn("abde", presets)
        self.assertIn("letra abde", presets)
        self.assertIn("preset abde", presets)
        self.assertTrue(presets["abde"].get("keep_punctuation"))

    def test_styler_initialization(self):
        styler = DualStyler.from_preset("abde")
        self.assertTrue(styler.keep_punctuation)
        self.assertAlmostEqual(styler.y_top, 0.0)
        self.assertAlmostEqual(styler.y_bottom, -0.079038, places=4)
        self.assertAlmostEqual(styler.x_top, 0.050403, places=4)
        self.assertAlmostEqual(styler.x_bottom, 0.032762, places=4)
        self.assertEqual(styler.sound_fx.get("name"), "鼠标单击1")
        self.assertEqual(styler.sound_fx.get("variation"), "intermittent")

    def test_punctuation_preservation_only_for_abde(self):
        # 1. Standard text cleaning (default for other doctors) strips commas & periods
        text_with_punct = "Si veo a esta paciente, el hígado falla y tiene ictericia."
        cleaned_standard = clean_subtitle_text(text_with_punct, keep_punctuation=False)
        self.assertNotIn(",", cleaned_standard)
        self.assertNotIn(".", cleaned_standard)
        self.assertEqual(cleaned_standard, "Si veo a esta paciente el hígado falla y tiene ictericia")

        # 2. Abde preset preserves commas and periods
        cleaned_abde = clean_subtitle_text(text_with_punct, keep_punctuation=True)
        self.assertIn(",", cleaned_abde)
        self.assertIn(".", cleaned_abde)
        self.assertEqual(cleaned_abde, "Si veo a esta paciente, el hígado falla y tiene ictericia.")

    def test_bundled_assets(self):
        # Font
        font_file = os.path.join(repo_root, "assets", "fonts", "Akzidenz-grotesk-black.ttf")
        self.assertTrue(os.path.isfile(font_file), "Akzidenz font must exist in assets/fonts")

        # Audio click
        audio_file = os.path.join(repo_root, "assets", "audio", "25b5bc6c42f453173fbf056859eec22b.mp3")
        self.assertTrue(os.path.isfile(audio_file), "鼠标单击1 audio must exist in assets/audio")

        # Animation effect
        effect_dir = os.path.join(repo_root, "assets", "effects", "7648941380408053013")
        self.assertTrue(os.path.isdir(effect_dir), "Descenso effect must exist in assets/effects")

    def test_chinese_click_sound_resolution(self):
        sound_path = get_default_click_sound_path(sound_name="鼠标单击1", filename="25b5bc6c42f453173fbf056859eec22b.mp3")
        self.assertTrue(os.path.isfile(sound_path))
        self.assertIn("25b5bc6c42f453173fbf056859eec22b", sound_path)

    def test_align_ai_corrections_with_punctuation(self):
        from core.text_utils import align_ai_corrections_to_raw_items
        raw_items = [
            {"index": 0, "text": "cada vez mas niñas", "start": 0, "end": 1000000, "duration": 1000000, "words": None},
            {"index": 1, "text": "entran en pubertad", "start": 1000000, "end": 2000000, "duration": 1000000, "words": None}
        ]
        corrected_ai = [
            {"index": 0, "text": "Cada vez más niñas,"},
            {"index": 1, "text": "entran en pubertad."}
        ]
        # With keep_punctuation=True, periods and commas are preserved in alignment
        align_ai_corrections_to_raw_items(raw_items, corrected_ai, keep_punctuation=True)
        self.assertIn(",", raw_items[0]["text"])
        self.assertIn(".", raw_items[1]["text"])
        self.assertEqual(raw_items[0]["text"], "Cada vez más niñas,")
        self.assertEqual(raw_items[1]["text"], "entran en pubertad.")

    def test_heuristic_punctuation_fallback(self):
        from core.text_utils import heuristic_punctuation_fallback
        raw_items = [
            {"index": 0, "text": "cada vez mas niñas", "start": 0, "end": 1000000, "duration": 1000000},
            {"index": 1, "text": "esto afecta su crecimiento", "start": 1400000, "end": 2500000, "duration": 1100000}
        ]
        # gap is 400ms (1400000 - 1000000), which should trigger sentence end period
        heuristic_punctuation_fallback(raw_items)
        self.assertTrue(raw_items[0]["text"].endswith("."))
        self.assertTrue(raw_items[1]["text"].endswith("."))

    def test_openrouter_prompt_punctuation_rule(self):
        from ai.openrouter_client import get_system_prompt_subtitles
        prompt_with_punc = get_system_prompt_subtitles(keep_punctuation=True)
        self.assertIn("REGLA DE PUNTUACIÓN (PUNTOS Y COMAS ACTIVADOS)", prompt_with_punc)
        self.assertIn("Coloca puntos (.) y comas (,)", prompt_with_punc)

        prompt_without_punc = get_system_prompt_subtitles(keep_punctuation=False)
        self.assertIn("REGLA ESTRICTA DE PUNTUACIÓN", prompt_without_punc)
        self.assertIn("NUNCA coloques comas", prompt_without_punc)
        self.assertIn("NUNCA coloques puntos", prompt_without_punc)

    def test_intermittent_click_filtering(self):
        styler = DualStyler.from_preset("abde")
        self.assertEqual(styler.sound_fx.get("variation"), "intermittent")

        # 7 highlights spaced ~2.5s apart (like in Abde 1)
        starts = [1466666, 4200000, 6933333, 9800000, 13300000, 15666666, 18300000]
        filtered = styler.filter_sound_fx_timestamps(starts)

        # Must NOT play on all highlights: should be an intermittent subset (~40-60%)
        self.assertLess(len(filtered), len(starts), "Intermittent variation must NOT play on all highlights")
        self.assertGreaterEqual(len(filtered), 2, "Must keep at least 2 highlights")
        self.assertIn(len(filtered), (3, 4), f"Expected 3 or 4 highlights for 7 inputs, got {len(filtered)}")

    def test_intermittent_burst_preservation(self):
        styler = DualStyler.from_preset("abde")
        # 3 rapid list items (e.g. 'zanahoria, mango, calabaza') separated by 400ms
        starts = [2000000, 10000000, 10400000, 10800000, 18000000]
        filtered = styler.filter_sound_fx_timestamps(starts)
        # All 3 burst items must be preserved
        self.assertIn(10000000, filtered)
        self.assertIn(10400000, filtered)
        self.assertIn(10800000, filtered)

    def test_intermittent_avoids_existing_sfx(self):
        styler = DualStyler.from_preset("abde")
        starts = [1466666, 4200000, 6933333, 9800000, 13300000, 15666666, 18300000]
        mock_draft = {
            "tracks": [
                {
                    "type": "audio",
                    "name": "Chimes",
                    "segments": [
                        {"target_timerange": {"start": 18300000, "duration": 700000}} # Glocken on 18.30s
                    ]
                }
            ]
        }
        filtered = styler.filter_sound_fx_timestamps(starts, draft_data=mock_draft)
        # 18.30s must NOT be included because a chime already exists there
        self.assertNotIn(18300000, filtered)


if __name__ == "__main__":
    unittest.main()
