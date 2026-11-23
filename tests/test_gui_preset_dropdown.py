import os
import sys
import tkinter as tk
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import gui
from core.dual_styler import DualStyler


class TestGuiPresetDropdown(unittest.TestCase):
    def test_all_dropdown_presets_load_in_dual_styler(self):
        self.assertGreaterEqual(len(gui.PRESET_OPTIONS), 24)
        for opt in gui.PRESET_OPTIONS:
            styler = DualStyler.from_preset(opt["value"])
            self.assertIsNotNone(styler, f"Failed to load preset {opt['value']}")

    def test_searchable_dropdown_filter_selection_auto_detect_and_layout(self):
        try:
            app = gui.CCSubsProGUI()
            app.withdraw()
            app.update_idletasks()
        except tk.TclError:
            self.skipTest("Tkinter display not available")
            return

        try:
            # 1. Accent-insensitive, partial, and font-based search
            self.assertEqual(len(app._filter_preset_options("")), len(gui.PRESET_OPTIONS))
            self.assertEqual([o["value"] for o in app._filter_preset_options("ana lin")], ["ana_linares"])
            self.assertIn("alvaro", [o["value"] for o in app._filter_preset_options("alvaro")])
            self.assertIn("pequenos", [o["value"] for o in app._filter_preset_options("pequenos")])
            ana_vals = [o["value"] for o in app._filter_preset_options("ana")]
            self.assertIn("ana", ana_vals)
            self.assertIn("ana_visedo", ana_vals)
            self.assertIn("ana_linares", ana_vals)
            playfair_vals = [o["value"] for o in app._filter_preset_options("playfair")]
            self.assertIn("ana_linares", playfair_vals)
            self.assertIn("dentok", playfair_vals)
            self.assertEqual([o["value"] for o in app._filter_preset_options("pt serif")], ["costa_calida"])
            self.assertEqual(app._filter_preset_options("zzzz_no_existe"), [])

            # 2. Open popup, verify mapped & positioned right under trigger, filter, and select
            app.deiconify()
            app.update()
            app._open_preset_dropdown()
            app.update()
            self.assertIsNotNone(app._preset_popup)
            self.assertEqual(app._preset_popup.winfo_ismapped(), 1)
            self.assertEqual(app._preset_popup.winfo_viewable(), 1)
            self.assertGreaterEqual(app._preset_popup.winfo_width(), 420)
            self.assertGreaterEqual(app._preset_popup.winfo_height(), 200)
            self.assertEqual(app._preset_listbox.size(), len(gui.PRESET_OPTIONS))

            app.preset_search_var.set("linares")
            app.update_idletasks()
            self.assertEqual(len(app._preset_filtered_options), 1)
            self.assertEqual(app._preset_filtered_options[0]["value"], "ana_linares")

            app._on_preset_listbox_click()
            app.update_idletasks()
            self.assertIsNone(app._preset_popup)
            self.assertEqual(app.doctor_preset.get(), "ana_linares")
            self.assertIn("Dra. Ana Linares", app._preset_display_var.get())
            self.assertIn("Playfair Display Bold", app.lbl_preset_detail.cget("text"))

            # 3. Project name auto-detection stays intact and syncs the dropdown label
            app.projects = [{"name": "CUIDUS 2", "path": r"C:\CapCut\CUIDUS 2", "subtitle_count": 10, "duration_us": 5000000}]
            app.proj_combo["values"] = ["CUIDUS 2 (10 subs, 5.0s)"]
            app.proj_combo.current(0)
            app._on_project_selected(None)
            self.assertEqual(app.doctor_preset.get(), "cuidus")
            self.assertIn("CUIDUS", app._preset_display_var.get())

            app.projects = [{"name": "Ana López-Linares 1", "path": r"C:\CapCut\Ana López-Linares 1", "subtitle_count": 20, "duration_us": 10000000}]
            app.proj_combo["values"] = ["Ana López-Linares 1 (20 subs, 10.0s)"]
            app.proj_combo.current(0)
            app._on_project_selected(None)
            self.assertEqual(app.doctor_preset.get(), "ana_linares")
            self.assertIn("Dra. Ana Linares", app._preset_display_var.get())

            app.projects = [{"name": "Costa calida 1", "path": r"C:\CapCut\Costa calida 1", "subtitle_count": 67, "duration_us": 125800000}]
            app.proj_combo["values"] = ["Costa calida 1 (67 subs, 125.8s)"]
            app.proj_combo.current(0)
            app._on_project_selected(None)
            self.assertEqual(app.doctor_preset.get(), "costa_calida")
            self.assertIn("Costa Cálida", app._preset_display_var.get())

            # 4. Layout fit check: all action buttons and log fit comfortably inside 700px height
            req_h = app.winfo_reqheight()
            self.assertLessEqual(req_h, 700, f"Requested GUI height {req_h}px exceeds 700px window height!")
        finally:
            app._close_preset_dropdown()
            app.destroy()


if __name__ == "__main__":
    unittest.main()
