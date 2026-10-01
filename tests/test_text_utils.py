import unittest
import json
from core.text_utils import clean_subtitle_text
from core.dual_styler import DualStyler
from core.styler import Styler
from core.capcut_draft import SubtitleItem, CapCutProject
from ai.highlighter import AIHighlighter

class TestSubtitlePunctuation(unittest.TestCase):
    def test_clean_subtitle_text_cases(self):
        # Commas
        self.assertEqual(clean_subtitle_text('que ha ejecutado,'), 'que ha ejecutado')
        self.assertEqual(clean_subtitle_text('primeros errores, y más'), 'primeros errores y más')
        
        # Periods and ellipsis
        self.assertEqual(clean_subtitle_text('como eso.'), 'como eso')
        self.assertEqual(clean_subtitle_text('el carril bici...'), 'el carril bici')
        self.assertEqual(clean_subtitle_text('una orografía...'), 'una orografía')
        
        # Colons
        self.assertEqual(clean_subtitle_text('Ponte en situación:'), 'Ponte en situación')
        self.assertEqual(clean_subtitle_text('clara: yo quiero'), 'clara yo quiero')
        self.assertEqual(clean_subtitle_text('Pues muy fácil:'), 'Pues muy fácil')
        
        # Combined and whitespace
        self.assertEqual(clean_subtitle_text('  hola,  mundo.  bien:  '), 'hola mundo bien')
        self.assertEqual(clean_subtitle_text('...al 100%...'), 'al 100%')
        self.assertEqual(clean_subtitle_text('¿por qué no funciona?'), '¿por qué no funciona?')
        self.assertEqual(clean_subtitle_text('¡increíble proyecto!'), '¡increíble proyecto!')

    def test_dual_styler_material_sanitization(self):
        styler = DualStyler.from_preset('gerardo')
        dummy_draft = {'materials': {'texts': []}}
        mat_id = styler._create_text_material(dummy_draft, 'Hola, mundo: prueba...', styler.default_style)
        
        mat = dummy_draft['materials']['texts'][0]
        inner = json.loads(mat['content'])
        self.assertEqual(inner['text'], 'Hola mundo prueba')
        self.assertEqual(inner['styles'][0]['range'], [0, len('Hola mundo prueba')])
        self.assertEqual(mat['words']['text'], ['Hola mundo prueba'])
        self.assertNotIn(',', inner['text'])
        self.assertNotIn('.', inner['text'])
        self.assertNotIn(':', inner['text'])

    def test_styler_sanitization(self):
        styler = Styler('styles/default.json', 'styles/highlight.json')
        seg = {'id': 'S1', 'material_id': 'M1', 'extra_material_refs': []}
        inner = {'text': 'Texto con, comas. Y dos puntos: aqui', 'styles': [{'range': [0, 36]}]}
        mat = {'id': 'M1', 'content': json.dumps(inner)}
        item = SubtitleItem(0, seg, mat)
        
        dummy_draft = {'materials': {'texts': [mat]}}
        styler.apply_default_style_to_item(item, dummy_draft)
        
        updated_text = item.text
        self.assertEqual(updated_text, 'Texto con comas Y dos puntos aqui')
        self.assertNotIn(',', updated_text)
        self.assertNotIn('.', updated_text)
        self.assertNotIn(':', updated_text)

    def test_subtitle_item_clean_text(self):
        seg = {'id': 'S2', 'material_id': 'M2', 'extra_material_refs': []}
        inner = {'text': 'Ponte en situación:', 'styles': [{'range': [0, 19]}]}
        mat = {'id': 'M2', 'content': json.dumps(inner), 'words': {'text': ['Ponte en situación:']}}
        item = SubtitleItem(0, seg, mat)
        
        cleaned = item.clean_text()
        self.assertEqual(cleaned, 'Ponte en situación')
        self.assertEqual(item.text, 'Ponte en situación')
        self.assertEqual(item.parsed_content['styles'][0]['range'], [0, 18])
        self.assertEqual(mat['words']['text'], ['Ponte en situación'])

    def test_highlighter_suggest_highlights_cleaned(self):
        hl = AIHighlighter(provider='heuristic')
        script = 'Ponte en situación: vamos a un congreso, de otro pueblo... y aquí empiezan los primeros errores.'
        highlights = hl.suggest_highlights(script, count=5)
        for h in highlights:
            self.assertNotIn(',', h)
            self.assertNotIn('.', h)
            self.assertNotIn(':', h)

if __name__ == '__main__':
    unittest.main()
