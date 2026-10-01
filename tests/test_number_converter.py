import unittest
from core.text_utils import (
    convert_spanish_numbers_to_digits,
    clean_subtitle_text,
    parse_spanish_number_tokens
)
from core.dual_styler import DualStyler

class TestSpanishNumberConverter(unittest.TestCase):
    def test_single_numbers(self):
        self.assertEqual(convert_spanish_numbers_to_digits("cero"), "0")
        self.assertEqual(convert_spanish_numbers_to_digits("dos"), "2")
        self.assertEqual(convert_spanish_numbers_to_digits("diez"), "10")
        self.assertEqual(convert_spanish_numbers_to_digits("quince"), "15")
        self.assertEqual(convert_spanish_numbers_to_digits("dieciocho"), "18")
        self.assertEqual(convert_spanish_numbers_to_digits("veintitrés"), "23")
        self.assertEqual(convert_spanish_numbers_to_digits("treinta"), "30")
        self.assertEqual(convert_spanish_numbers_to_digits("ochenta"), "80")
        self.assertEqual(convert_spanish_numbers_to_digits("cien"), "100")
        self.assertEqual(convert_spanish_numbers_to_digits("mil"), "1000")

    def test_compound_tens_and_units(self):
        self.assertEqual(convert_spanish_numbers_to_digits("treinta y nueve"), "39")
        self.assertEqual(convert_spanish_numbers_to_digits("cuarenta y cinco"), "45")
        self.assertEqual(convert_spanish_numbers_to_digits("cincuenta y ocho"), "58")
        self.assertEqual(convert_spanish_numbers_to_digits("noventa y nueve"), "99")
        self.assertEqual(convert_spanish_numbers_to_digits("veintiún días"), "21 días")
        self.assertEqual(convert_spanish_numbers_to_digits("treinta y un casos"), "31 casos")

    def test_hundreds_thousands_millions(self):
        self.assertEqual(convert_spanish_numbers_to_digits("ciento cincuenta"), "150")
        self.assertEqual(convert_spanish_numbers_to_digits("doscientos treinta y cuatro"), "234")
        self.assertEqual(convert_spanish_numbers_to_digits("dos mil"), "2000")
        self.assertEqual(convert_spanish_numbers_to_digits("dos mil quinientos"), "2500")
        self.assertEqual(convert_spanish_numbers_to_digits("diez mil quinientos"), "10500")
        self.assertEqual(convert_spanish_numbers_to_digits("ciento veinte mil"), "120000")
        self.assertEqual(convert_spanish_numbers_to_digits("un millón"), "1000000")
        self.assertEqual(convert_spanish_numbers_to_digits("dos millones"), "2000000")
        self.assertEqual(convert_spanish_numbers_to_digits("tres millones quinientos mil"), "3500000")

    def test_indefinite_articles_preservation(self):
        # Standalone 'un' / 'una' should NEVER become digits
        self.assertEqual(convert_spanish_numbers_to_digits("un paciente"), "un paciente")
        self.assertEqual(convert_spanish_numbers_to_digits("una paciente"), "una paciente")
        self.assertEqual(convert_spanish_numbers_to_digits("hace un año"), "hace un año")
        self.assertEqual(convert_spanish_numbers_to_digits("sufre una molestia"), "sufre una molestia")

    def test_punctuation_and_questions(self):
        self.assertEqual(
            convert_spanish_numbers_to_digits("¿Significa que tengo treinta y nueve de fiebre?"),
            "¿Significa que tengo 39 de fiebre?"
        )
        self.assertEqual(
            convert_spanish_numbers_to_digits("¡Son ochenta personas!"),
            "¡Son 80 personas!"
        )
        self.assertEqual(
            convert_spanish_numbers_to_digits('"ciento cincuenta"'),
            '"150"'
        )

    def test_timeline_consolidation_two_segments(self):
        styler = DualStyler()
        raw_items = [
            {'index': 0, 'text': 'treinta', 'start': 1000000, 'end': 1500000, 'duration': 500000, 'words': None},
            {'index': 1, 'text': 'y nueve', 'start': 1500000, 'end': 2100000, 'duration': 600000, 'words': None}
        ]
        consolidated = styler._consolidate_number_segments(raw_items, max_chars=18, max_words=3)
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(consolidated[0]['text'], '39')
        self.assertEqual(consolidated[0]['start'], 1000000)
        self.assertEqual(consolidated[0]['end'], 2100000)
        self.assertEqual(consolidated[0]['duration'], 1100000)

    def test_timeline_consolidation_three_segments(self):
        styler = DualStyler()
        raw_items = [
            {'index': 0, 'text': 'ciento', 'start': 1000000, 'end': 1300000, 'duration': 300000, 'words': None},
            {'index': 1, 'text': 'veinte', 'start': 1300000, 'end': 1600000, 'duration': 300000, 'words': None},
            {'index': 2, 'text': 'mil', 'start': 1600000, 'end': 2000000, 'duration': 400000, 'words': None}
        ]
        consolidated = styler._consolidate_number_segments(raw_items, max_chars=18, max_words=3)
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(consolidated[0]['text'], '120000')
        self.assertEqual(consolidated[0]['start'], 1000000)
        self.assertEqual(consolidated[0]['end'], 2000000)

    def test_timeline_consolidation_context_words(self):
        styler = DualStyler()
        raw_items = [
            {'index': 0, 'text': 'tiene treinta', 'start': 1000000, 'end': 1500000, 'duration': 500000, 'words': None},
            {'index': 1, 'text': 'y ocho años', 'start': 1500000, 'end': 2100000, 'duration': 600000, 'words': None}
        ]
        consolidated = styler._consolidate_number_segments(raw_items, max_chars=18, max_words=3)
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(consolidated[0]['text'], 'tiene 38 años')
        self.assertEqual(consolidated[0]['start'], 1000000)
        self.assertEqual(consolidated[0]['end'], 2100000)

    def test_non_number_segments_not_consolidated(self):
        styler = DualStyler()
        raw_items = [
            {'index': 0, 'text': 'este es', 'start': 1000000, 'end': 1500000, 'duration': 500000, 'words': None},
            {'index': 1, 'text': 'un paciente', 'start': 1500000, 'end': 2100000, 'duration': 600000, 'words': None}
        ]
        consolidated = styler._consolidate_number_segments(raw_items, max_chars=18, max_words=3)
        self.assertEqual(len(consolidated), 2)
        self.assertEqual(consolidated[0]['text'], 'este es')
        self.assertEqual(consolidated[1]['text'], 'un paciente')

    def test_percentage_conversions(self):
        self.assertEqual(convert_spanish_numbers_to_digits("7 por 100"), "7%")
        self.assertEqual(convert_spanish_numbers_to_digits("7 por ciento"), "7%")
        self.assertEqual(convert_spanish_numbers_to_digits("7 por cien"), "7%")
        self.assertEqual(convert_spanish_numbers_to_digits("7 porciento"), "7%")
        self.assertEqual(convert_spanish_numbers_to_digits("siete por ciento"), "7%")
        self.assertEqual(convert_spanish_numbers_to_digits("diez por ciento"), "10%")
        self.assertEqual(convert_spanish_numbers_to_digits("cien por ciento"), "100%")
        self.assertEqual(convert_spanish_numbers_to_digits("veinticinco por cien"), "25%")
        self.assertEqual(convert_spanish_numbers_to_digits("cincuenta por ciento"), "50%")
        self.assertEqual(convert_spanish_numbers_to_digits("¿un siete por ciento?"), "¿un 7%?")
        self.assertEqual(convert_spanish_numbers_to_digits("¡cien por ciento!"), "¡100%!")

    def test_split_percentage_boundary_clean_split(self):
        styler = DualStyler()
        # The user's exact case: Segment 3: 'en un 7 por', Segment 4: '100 en la velocidad'
        raw_items = [
            {'index': 0, 'text': 'en un 7 por', 'start': 1000000, 'end': 2000000, 'duration': 1000000, 'words': None},
            {'index': 1, 'text': '100 en la velocidad', 'start': 2000000, 'end': 3500000, 'duration': 1500000, 'words': None}
        ]
        consolidated = styler._consolidate_number_segments(raw_items, max_chars=18, max_words=3)
        self.assertEqual(len(consolidated), 2)
        self.assertEqual(consolidated[0]['text'], 'en un 7%')
        self.assertEqual(consolidated[1]['text'], 'en la velocidad')

    def test_split_percentage_merge_single_segment(self):
        styler = DualStyler()
        raw_items = [
            {'index': 0, 'text': 'un siete por', 'start': 1000000, 'end': 2000000, 'duration': 1000000, 'words': None},
            {'index': 1, 'text': 'ciento', 'start': 2000000, 'end': 3000000, 'duration': 1000000, 'words': None}
        ]
        consolidated = styler._consolidate_number_segments(raw_items, max_chars=18, max_words=3)
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(consolidated[0]['text'], 'un 7%')
        self.assertEqual(consolidated[0]['start'], 1000000)
        self.assertEqual(consolidated[0]['end'], 3000000)

if __name__ == '__main__':
    unittest.main()
