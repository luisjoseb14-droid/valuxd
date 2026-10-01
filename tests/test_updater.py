# -*- coding: utf-8 -*-
import unittest
import os
import json
import tempfile
import shutil

from core.updater import get_local_version_info, bump_version, check_for_updates


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


if __name__ == '__main__':
    unittest.main()
