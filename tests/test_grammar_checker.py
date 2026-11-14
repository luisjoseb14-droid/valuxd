import json
import os
import tempfile
import shutil
import unittest
from unittest.mock import patch

from ai.openrouter_client import OpenRouterClient, get_system_prompt_grammar
from core.capcut_draft import CapCutProject
from core.grammar_checker import (
    apply_grammar_fixes,
    check_project_grammar,
    collect_grammar_segments,
    normalize_grammar_correction,
    remap_rich_styles,
)


class _DummyHTTPResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestGrammarChecker(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.draft_path = os.path.join(self.tmp_dir, "draft_content.json")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_sample_project(self):
        draft = {
            "duration": 6000000,
            "fps": 30.0,
            "materials": {
                "texts": [
                    {
                        "id": "M_TOP_0",
                        "type": "subtitle",
                        "content": json.dumps(
                            {
                                "text": "En la clinica",
                                "styles": [{"range": [0, 13], "size": 9.0}],
                            },
                            ensure_ascii=False,
                        ),
                        "recognize_text": "En la clinica",
                        "words": {
                            "text": ["En", " ", "la", " ", "clinica"],
                            "start_time": [0, 200, 200, 350, 350],
                            "end_time": [200, 200, 350, 350, 900],
                        },
                    },
                    {
                        "id": "M_BOT_0",
                        "type": "text",
                        "content": json.dumps(
                            {
                                "text": "RAPIDO Y FACIL",
                                "styles": [{"range": [0, 14], "size": 14.0}],
                            },
                            ensure_ascii=False,
                        ),
                        "words": {
                            "text": ["RAPIDO", " ", "Y", " ", "FACIL"],
                            "start_time": [0, 300, 300, 450, 450],
                            "end_time": [300, 300, 450, 450, 900],
                        },
                    },
                    {
                        "id": "M_INLINE_1",
                        "type": "subtitle",
                        "content": json.dumps(
                            {
                                "text": "para su esposicion diaria",
                                "styles": [
                                    {"range": [0, 8], "size": 9.0},
                                    {"range": [8, 18], "size": 9.0, "useLetterColor": True},
                                    {"range": [18, 25], "size": 9.0},
                                ],
                            },
                            ensure_ascii=False,
                        ),
                        "recognize_text": "para su esposicion diaria",
                        "words": {
                            "text": ["para", " ", "su", " ", "esposicion", " ", "diaria"],
                            "start_time": [0, 150, 150, 300, 300, 700, 700],
                            "end_time": [150, 150, 300, 300, 700, 700, 1100],
                        },
                    },
                ],
                "text_templates": [],
            },
            "tracks": [
                {
                    "id": "TRK_0",
                    "type": "text",
                    "segments": [
                        {
                            "id": "SEG_0",
                            "material_id": "M_TOP_0",
                            "target_timerange": {"start": 100000, "duration": 900000},
                            "extra_material_refs": ["ANIM_1"],
                        },
                        {
                            "id": "SEG_2",
                            "material_id": "M_INLINE_1",
                            "target_timerange": {"start": 2500000, "duration": 1100000},
                            "extra_material_refs": [],
                        },
                    ],
                },
                {
                    "id": "TRK_1",
                    "type": "text",
                    "segments": [
                        {
                            "id": "SEG_1",
                            "material_id": "M_BOT_0",
                            "target_timerange": {"start": 1100000, "duration": 900000},
                            "extra_material_refs": ["ANIM_2"],
                        }
                    ],
                },
            ],
        }
        with open(self.draft_path, "w", encoding="utf-8") as f:
            json.dump(draft, f, ensure_ascii=False)
        return CapCutProject(self.draft_path)

    def test_grammar_prompt_formats_cleanly(self):
        p_no = get_system_prompt_grammar(keep_punctuation=False)
        p_yes = get_system_prompt_grammar(keep_punctuation=True)
        self.assertIn("corrections", p_no)
        self.assertIn("NO agregues comas ni puntos nuevos", p_no)
        self.assertIn("Mantén puntos (.) y comas (,)", p_yes)
        self.assertIn("Gala Unique", p_no)
        self.assertNotIn("Gala" + "unick", p_no)

    def test_normalize_preserves_caps_and_multiline(self):
        # Uppercase segment retains uppercase even if AI returned title/lowercase
        self.assertEqual(
            normalize_grammar_correction("ATENCION MEDICA", "Atención médica"),
            "ATENCIÓN MÉDICA",
        )
        # Multi-line segment keeps line break if AI flattened it
        self.assertEqual(
            normalize_grammar_correction("en la clinica\nmas cercana", "en la clínica más cercana"),
            "en la clínica\nmás cercana",
        )
        # Does not invent trailing periods when original had none
        self.assertEqual(
            normalize_grammar_correction("esto es asi", "esto es así.", allow_commas_periods=False),
            "esto es así",
        )
        # Preserves periods when allow_commas_periods=True (Abde)
        self.assertEqual(
            normalize_grammar_correction("esto es asi.", "esto es así.", allow_commas_periods=True),
            "esto es así.",
        )

    def test_remap_rich_styles_keeps_highlight_aligned(self):
        orig = "porqe duele mucho"
        new = "porque duele mucho"
        styles = [
            {"range": [0, 6], "color": "white"},
            {"range": [6, 11], "color": "yellow"},
            {"range": [11, 17], "color": "white"},
        ]
        remapped = remap_rich_styles(orig, new, styles)
        self.assertEqual([new[r["range"][0] : r["range"][1]] for r in remapped], ["porque ", "duele", " mucho"])

    def test_check_and_apply_grammar_fixes_mocked_openrouter(self):
        proj = self._write_sample_project()
        collected = collect_grammar_segments(proj)
        self.assertEqual(len(collected), 3)

        mock_api_reply = {
            "choices": [
                {
                    "message": {
                        "content": "```json\n"
                        + json.dumps(
                            {
                                "corrections": [
                                    {"index": 0, "corrected_text": "En la clínica", "reason": "Falta tilde en 'clínica'"},
                                    {"index": 1, "corrected_text": "rápido y fácil", "reason": "Faltan tildes en 'rápido' y 'fácil'"},
                                    {"index": 2, "corrected_text": "para su exposición diaria", "reason": "Ortografía y tilde: 'esposicion' -> 'exposición'"},
                                ]
                            },
                            ensure_ascii=False,
                        )
                        + "\n```"
                    }
                }
            ]
        }

        client = OpenRouterClient(api_key="test-key-123")
        with patch("urllib.request.urlopen", return_value=_DummyHTTPResponse(mock_api_reply)):
            fixes = check_project_grammar(proj, client=client, preset_name="gerardo")

        self.assertIsNotNone(fixes)
        self.assertEqual(len(fixes), 3)
        self.assertEqual(fixes[0]["corrected_text"], "En la clínica")
        # Track 1 original was ALL CAPS -> stays ALL CAPS with tildes!
        self.assertEqual(fixes[1]["corrected_text"], "RÁPIDO Y FÁCIL")
        self.assertEqual(fixes[2]["corrected_text"], "para su exposición diaria")

        applied = apply_grammar_fixes(proj, fixes)
        self.assertEqual(applied, 3)
        proj.save(create_backup=False)

        reloaded = CapCutProject(self.draft_path)
        subs_by_id = {s.segment_id: s for s in reloaded.subtitles}

        self.assertEqual(subs_by_id["SEG_0"].text, "En la clínica")
        self.assertEqual(subs_by_id["SEG_0"].start_us, 100000)
        self.assertEqual(subs_by_id["SEG_0"].duration_us, 900000)
        self.assertEqual(subs_by_id["SEG_0"].extra_material_refs, ["ANIM_1"])

        self.assertEqual(subs_by_id["SEG_1"].text, "RÁPIDO Y FÁCIL")
        self.assertEqual(subs_by_id["SEG_1"].start_us, 1100000)
        self.assertEqual(subs_by_id["SEG_1"].text_material["words"]["text"], ["RÁPIDO", " ", "Y", " ", "FÁCIL"])

        # Inline rich-text segment retains highlight color on "exposición"
        inline_sub = subs_by_id["SEG_2"]
        self.assertEqual(inline_sub.text, "para su exposición diaria")
        styles = inline_sub.parsed_content["styles"]
        self.assertEqual(len(styles), 3)
        hl_span = inline_sub.text[styles[1]["range"][0] : styles[1]["range"][1]]
        self.assertEqual(hl_span, "exposición")
        self.assertEqual(inline_sub.text_material["words"]["text"], ["para", " ", "su", " ", "exposición", " ", "diaria"])

    def test_openrouter_check_grammar_batching(self):
        segments = [{"index": i, "start": i * 1000000, "text": f"clinica {i}"} for i in range(90)]
        calls = []

        def fake_urlopen(req, timeout=45):
            body = json.loads(req.data.decode("utf-8"))
            user_msg = body["messages"][1]["content"]
            calls.append(user_msg)
            batch_corr = []
            if '"index": 0,' in user_msg:
                batch_corr.append({"index": 0, "corrected_text": "clínica 0", "reason": "tilde"})
            if '"index": 80,' in user_msg:
                batch_corr.append({"index": 80, "corrected_text": "clínica 80", "reason": "tilde"})
            return _DummyHTTPResponse({"choices": [{"message": {"content": json.dumps({"corrections": batch_corr})}}]})

        client = OpenRouterClient(api_key="test-key-123")
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            res = client.check_grammar(segments, batch_size=75)

        self.assertEqual(len(calls), 2)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["index"], 0)
        self.assertEqual(res[1]["index"], 80)

    def test_check_grammar_recovers_legacy_client_without_method(self):
        proj = self._write_sample_project()

        class LegacyOpenRouterClient:
            def __init__(self, api_key="k", model="m"):
                self.api_key = api_key
                self.model = model

        legacy_client = LegacyOpenRouterClient(api_key="test-key-123", model="google/gemini-2.5-flash")
        mock_api_reply = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "corrections": [
                                {"index": 0, "corrected_text": "En la clínica", "reason": "tilde"}
                            ]
                        })
                    }
                }
            ]
        }

        logs = []
        with patch("core.updater.ensure_ai_modules_up_to_date", return_value=(True, ["ai/openrouter_client.py"])) as mock_sync, \
             patch("urllib.request.urlopen", return_value=_DummyHTTPResponse(mock_api_reply)):
            fixes = check_project_grammar(proj, client=legacy_client, log_fn=logs.append)

        mock_sync.assert_called_once_with(force=True)
        self.assertIsNotNone(fixes)
        self.assertEqual(len(fixes), 1)
        self.assertEqual(fixes[0]["corrected_text"], "En la clínica")
        self.assertTrue(any("ai/openrouter_client.py" in line for line in logs))

    def test_gui_has_grammar_button_and_compiles(self):
        gui_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gui.py")
        with open(gui_path, "r", encoding="utf-8") as f:
            src = f.read()
        compile(src, gui_path, "exec")
        self.assertIn("COMPROBAR GRAMÁTICA", src)
        self.assertIn("_start_grammar_check", src)
        self.assertIn("GrammarReviewDialog", src)


if __name__ == "__main__":
    unittest.main()
