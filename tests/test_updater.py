# -*- coding: utf-8 -*-
import unittest
import os
import io
import json
import zipfile
import tempfile
import shutil
from unittest.mock import patch

from core.updater import (
    get_local_version_info,
    bump_version,
    check_for_updates,
    download_and_apply_update,
    ensure_ai_modules_up_to_date,
)


class TestUpdater(unittest.TestCase):
    def test_local_version_info(self):
        info = get_local_version_info()
        self.assertIn("version", info)
        self.assertIn("version_code", info)
        self.assertIn("repo_url", info)
        self.assertEqual(info.get("repo_url"), "https://github.com/luisjoseb14-droid/valuxd")

    def test_bump_version(self):
        test_dir = tempfile.mkdtemp()
        vfile = os.path.join(test_dir, 'version.json')
        initial_data = {
            "version": "1.0.0",
            "version_code": 1,
            "date": "2026-09-30",
            "description": "Initial test",
            "repo_url": "https://github.com/luisjoseb14-droid/valuxd"
        }
        with open(vfile, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f)

        import core.updater as up_mod
        orig_get_base_dir = up_mod.get_base_dir
        up_mod.get_base_dir = lambda: test_dir

        try:
            new_info = bump_version("Prueba de incremento")
            self.assertEqual(new_info["version_code"], 2)
            self.assertEqual(new_info["version"], "1.0.1")
            self.assertEqual(new_info["description"], "Prueba de incremento")

            with open(vfile, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            self.assertEqual(saved["version_code"], 2)
            self.assertEqual(saved["version"], "1.0.1")
        finally:
            up_mod.get_base_dir = orig_get_base_dir
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_check_for_updates_offline_resilience(self):
        # Even with an unpushed / offline repo, it should not raise an unhandled exception
        has_update, info = check_for_updates()
        self.assertIsInstance(has_update, bool)
        self.assertIsInstance(info, dict)

    def test_download_and_apply_update_copies_ai_and_core_and_clears_pyc(self):
        test_dir = tempfile.mkdtemp()
        try:
            ai_dir = os.path.join(test_dir, 'ai')
            pycache_ai = os.path.join(ai_dir, '__pycache__')
            os.makedirs(pycache_ai, exist_ok=True)
            stale_pyc = os.path.join(pycache_ai, 'openrouter_client.cpython-312.pyc')
            with open(stale_pyc, 'wb') as f:
                f.write(b'stale')
            with open(os.path.join(ai_dir, 'openrouter_client.py'), 'w', encoding='utf-8') as f:
                f.write('class OpenRouterClient:\n    pass\n')

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('valuxd-main/ai/openrouter_client.py', 'def get_system_prompt_grammar(): return ""\nclass OpenRouterClient:\n    def check_grammar(self, s): return []\n')
                zf.writestr('valuxd-main/ai/highlighter.py', '# new highlighter\n')
                zf.writestr('valuxd-main/core/updater.py', '# new updater\n')
                zf.writestr('valuxd-main/styles/presets.json', '{"paco": {}}')
                zf.writestr('valuxd-main/gui.py', '# new gui\n')
                zf.writestr('valuxd-main/version.json', json.dumps({"version": "1.0.23", "version_code": 24, "description": "fix ai updater"}))
            zip_bytes = buf.getvalue()

            class DummyResp:
                def __init__(self, data):
                    self._bio = io.BytesIO(data)
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
                def getheader(self, name):
                    return str(len(zip_bytes)) if name.lower() == 'content-length' else None
                def read(self, n=-1):
                    return self._bio.read(n)

            import core.updater as up_mod
            with patch.object(up_mod, 'get_base_dir', return_value=test_dir), \
                 patch.object(up_mod, '_safe_urlopen', return_value=DummyResp(zip_bytes)), \
                 patch.object(up_mod, 'install_all_assets', return_value={"fonts": [], "errors": []}):
                res = download_and_apply_update(force=True)

            self.assertTrue(res["success"])
            self.assertEqual(res["new_version"], "1.0.23")
            with open(os.path.join(ai_dir, 'openrouter_client.py'), 'r', encoding='utf-8') as f:
                self.assertIn('def check_grammar(', f.read())
            self.assertTrue(os.path.isfile(os.path.join(ai_dir, 'highlighter.py')))
            self.assertTrue(os.path.isfile(os.path.join(test_dir, 'core', 'updater.py')))
            self.assertFalse(os.path.exists(stale_pyc))
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_ensure_ai_modules_up_to_date_repairs_legacy_ai(self):
        test_dir = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(test_dir, 'ai', '__pycache__'), exist_ok=True)
            with open(os.path.join(test_dir, 'ai', 'openrouter_client.py'), 'w', encoding='utf-8') as f:
                f.write('class OpenRouterClient:\n    def process_subtitles(self, s): return None\n')
            stale_pyc = os.path.join(test_dir, 'ai', '__pycache__', 'openrouter_client.cpython-312.pyc')
            with open(stale_pyc, 'wb') as f:
                f.write(b'stale')

            valid_orc = (
                'DEFAULT_MODEL = "google/gemini-2.5-flash"\n'
                'def get_system_prompt_grammar(keep_punctuation=False):\n'
                '    return "ok"\n'
                'class OpenRouterClient:\n'
                '    def __init__(self, api_key="", model=DEFAULT_MODEL):\n'
                '        self.api_key = api_key\n'
                '        self.model = model\n'
                '    def check_grammar(self, segments, keep_punctuation=False):\n'
                '        return []\n'
                '# padding ' + ('x' * 80) + '\n'
            )
            valid_other = '# valid module ' + ('x' * 120) + '\n'

            def fake_fetch(rel_path, timeout=15):
                return valid_orc if rel_path.endswith('openrouter_client.py') else valid_other

            import core.updater as up_mod
            with patch.object(up_mod, 'get_base_dir', return_value=test_dir), \
                 patch.object(up_mod, '_fetch_github_text', side_effect=fake_fetch), \
                 patch.object(up_mod, '_reload_ai_modules') as mock_reload:
                repaired, files = ensure_ai_modules_up_to_date()

            self.assertTrue(repaired)
            self.assertEqual(files, ['ai/openrouter_client.py', 'ai/highlighter.py', 'ai/transcriber.py'])
            mock_reload.assert_called_once()
            self.assertFalse(os.path.exists(stale_pyc))
            with open(os.path.join(test_dir, 'ai', 'openrouter_client.py'), 'r', encoding='utf-8') as f:
                self.assertIn('def check_grammar(', f.read())

            # Second check with healthy disk + loaded module requires no network sync
            with patch.object(up_mod, 'get_base_dir', return_value=test_dir), \
                 patch.object(up_mod, '_fetch_github_text') as mock_fetch:
                repaired2, files2 = ensure_ai_modules_up_to_date()
            self.assertFalse(repaired2)
            self.assertEqual(files2, [])
            mock_fetch.assert_not_called()
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
