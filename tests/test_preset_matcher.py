# -*- coding: utf-8 -*-
import unittest
from core.preset_matcher import detect_preset_from_name


class TestPresetMatcher(unittest.TestCase):
    def test_cuidus_detection(self):
        self.assertEqual(detect_preset_from_name("CUIDUS 2"), "cuidus")
        self.assertEqual(detect_preset_from_name("CUIDUS 17-18"), "cuidus")
        self.assertEqual(detect_preset_from_name(r"C:\Users\WINDOWS\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft\CUIDUS 2"), "cuidus")
        self.assertEqual(detect_preset_from_name("Letra Cuidus"), "cuidus")

    def test_laura_burgos_detection(self):
        self.assertEqual(detect_preset_from_name("0630 Laura 10"), "laura burgos")
        self.assertEqual(detect_preset_from_name("Laura Burgos Reel 1"), "laura burgos")
        self.assertEqual(detect_preset_from_name("Laura_Burgos_5"), "laura burgos")
        self.assertEqual(detect_preset_from_name("Dra. Burgos"), "laura burgos")

    def test_laura_pediatra_detection(self):
        self.assertEqual(detect_preset_from_name("Dra. Laura Pediatra"), "laura")
        self.assertEqual(detect_preset_from_name("Laura Pediatra 2"), "laura")
        self.assertEqual(detect_preset_from_name("Pediatria caso clinico"), "laura")
        self.assertEqual(detect_preset_from_name("Laura consejos"), "laura")

    def test_other_doctors_detection(self):
        self.assertEqual(detect_preset_from_name("Dr. Gerardo Reel"), "gerardo")
        self.assertEqual(detect_preset_from_name("Gerardo_12"), "gerardo")

        self.assertEqual(detect_preset_from_name("Dra. Gala Tips"), "gala")
        self.assertEqual(detect_preset_from_name("Gala 03"), "gala")

        self.assertEqual(detect_preset_from_name("Ana Otorrino 0922"), "ana")
        self.assertEqual(detect_preset_from_name("Dra Ana"), "ana")
        self.assertEqual(detect_preset_from_name("Otorrino Consulta"), "ana")

        self.assertEqual(detect_preset_from_name("Dr. Jose Podologo"), "jose")
        self.assertEqual(detect_preset_from_name("Jose Podólogo"), "jose")
        self.assertEqual(detect_preset_from_name("Podologia Clinica"), "jose")

        self.assertEqual(detect_preset_from_name("Deditos Barefoot"), "deditos")
        self.assertEqual(detect_preset_from_name("Barefoot Zapatos"), "deditos")

        self.assertEqual(detect_preset_from_name("Emilia Reel 1"), "emilia")

        self.assertEqual(detect_preset_from_name("Dr Alvaro Cirugia"), "alvaro")
        self.assertEqual(detect_preset_from_name("Dr. Álvaro"), "alvaro")

        self.assertEqual(detect_preset_from_name("Pequeños Cuidados"), "pequenos")
        self.assertEqual(detect_preset_from_name("Pequenos Cuidados Bebe"), "pequenos")

        self.assertEqual(detect_preset_from_name("Dra. Alharilla Salud"), "alharilla")
        self.assertEqual(detect_preset_from_name("Alharilla"), "alharilla")

        self.assertEqual(detect_preset_from_name("Enfocavision 1"), "enfocavision")
        self.assertEqual(detect_preset_from_name("Doctores Enfocavisión 2"), "enfocavision")
        self.assertEqual(detect_preset_from_name("Enfocavision_5"), "enfocavision")

        self.assertEqual(detect_preset_from_name("Juan 1-2"), "juan")
        self.assertEqual(detect_preset_from_name("Juan 3-4"), "juan")
        self.assertEqual(detect_preset_from_name("Letra Juan"), "juan")
        self.assertEqual(detect_preset_from_name(r"B:\capc\Juan 1-2"), "juan")

        self.assertEqual(detect_preset_from_name("Carillo 6-7-8"), "carrillo")
        self.assertEqual(detect_preset_from_name("Carillo 5etc"), "carrillo")
        self.assertEqual(detect_preset_from_name("Dr Carrillo"), "carrillo")
        self.assertEqual(detect_preset_from_name("SEP Carillo 1"), "carrillo")
        self.assertEqual(detect_preset_from_name(r"B:\capc\Carillo 6-7-8"), "carrillo")

    def test_unmatched_returns_none(self):
        self.assertIsNone(detect_preset_from_name("Mi Video de Vacaciones"))
        self.assertIsNone(detect_preset_from_name("Proyecto 123"))
        self.assertIsNone(detect_preset_from_name("Semana 3 rutina"))
        self.assertIsNone(detect_preset_from_name(""))
        self.assertIsNone(detect_preset_from_name(None))

    def test_gui_auto_preset_behavior(self):
        import tkinter as tk
        from gui import CCSubsProGUI
        try:
            app = CCSubsProGUI()
            app.withdraw()

            # 1. CUIDUS
            app.projects = [{'name': 'CUIDUS 2', 'path': r'C:\CapCut\CUIDUS 2', 'subtitle_count': 10, 'duration_us': 5000000}]
            app.proj_combo['values'] = ['CUIDUS 2 (10 subs, 5.0s)']
            app.proj_combo.current(0)
            app._on_project_selected(None)
            self.assertEqual(app.doctor_preset.get(), 'cuidus')

            # 2. Gerardo
            app.projects = [{'name': 'Dr. Gerardo 01', 'path': r'C:\CapCut\Dr. Gerardo 01', 'subtitle_count': 15, 'duration_us': 10000000}]
            app.proj_combo['values'] = ['Dr. Gerardo 01 (15 subs, 10.0s)']
            app.proj_combo.current(0)
            app._on_project_selected(None)
            self.assertEqual(app.doctor_preset.get(), 'gerardo')

            # 3. Laura Burgos
            app.projects = [{'name': '0630 Laura 10', 'path': r'C:\CapCut\0630 Laura 10', 'subtitle_count': 20, 'duration_us': 15000000}]
            app.proj_combo['values'] = ['0630 Laura 10 (20 subs, 15.0s)']
            app.proj_combo.current(0)
            app._on_project_selected(None)
            self.assertEqual(app.doctor_preset.get(), 'laura burgos')

            # 4. Laura Pediatra
            app.projects = [{'name': 'Laura Pediatra 02', 'path': r'C:\CapCut\Laura Pediatra 02', 'subtitle_count': 20, 'duration_us': 15000000}]
            app.proj_combo['values'] = ['Laura Pediatra 02 (20 subs, 15.0s)']
            app.proj_combo.current(0)
            app._on_project_selected(None)
            self.assertEqual(app.doctor_preset.get(), 'laura')

            app.destroy()
        except tk.TclError:
            pass


if __name__ == '__main__':
    unittest.main()
