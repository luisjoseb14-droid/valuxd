import unittest
from core.text_utils import align_ai_corrections_to_raw_items, clean_subtitle_text, convert_spanish_numbers_to_digits


class TestSyncAlignment(unittest.TestCase):
    def test_align_ai_corrections_prevents_index_shift(self):
        """
        Tests that when an AI model splits a word (e.g. 'sí') into an extra segment,
        the sequence alignment binds all words to their original acoustic slots
        and prevents a domino-effect index shift across subsequent segments.
        """
        raw_items = [
            {'index': 0, 'text': 'podemos operar'},
            {'index': 1, 'text': 'un bebé antes'},
            {'index': 2, 'text': 'de que nazca en'},
            {'index': 3, 'text': 'algunas'},
            {'index': 4, 'text': 'enfermedades sí'},
            {'index': 5, 'text': 'se llama'},
            {'index': 6, 'text': 'cirugía fetal'},
            {'index': 7, 'text': 'y es uno de los'}
        ]

        # AI hallucinated an extra segment by isolating 'Sí'
        ai_corrected = [
            {'index': 0, 'text': '¿Podemos operar'},
            {'index': 1, 'text': 'un bebé antes'},
            {'index': 2, 'text': 'de que nazca en'},
            {'index': 3, 'text': 'algunas'},
            {'index': 4, 'text': 'enfermedades'},
            {'index': 5, 'text': 'Sí se'},
            {'index': 6, 'text': 'llama cirugía'},
            {'index': 7, 'text': 'fetal y'},
            {'index': 8, 'text': 'es 1 de los'}
        ]

        align_ai_corrections_to_raw_items(raw_items, ai_corrected)

        # Segment 0 must have question mark
        self.assertEqual(raw_items[0]['text'], '¿Podemos operar')
        # Segment 4 must retain 'sí' (with capitalization/closing mark)
        self.assertIn('sí', raw_items[4]['text'].lower())
        self.assertIn('enfermedades', raw_items[4]['text'].lower())
        # Segment 5 must retain 'se llama', NEVER displaced to 'sí' or 'llama cirugía'
        self.assertEqual(raw_items[5]['text'].lower(), 'se llama')
        # Segment 6 must retain 'cirugía fetal'
        self.assertEqual(raw_items[6]['text'].lower(), 'cirugía fetal')
        # Segment 7 must retain 'y es 1 de los'
        self.assertEqual(raw_items[7]['text'].lower(), 'y es 1 de los')

    def test_unpaired_question_mark_closing(self):
        """
        Tests that an unclosed opening question mark (¿) is properly closed with (?)
        before an affirmative reply or new sentence.
        """
        raw_items = [
            {'index': 0, 'text': 'podemos operar'},
            {'index': 1, 'text': 'un bebé'},
            {'index': 2, 'text': 'enfermedades sí'}
        ]
        ai_corrected = [
            {'index': 0, 'text': '¿Podemos operar'},
            {'index': 1, 'text': 'un bebé'},
            {'index': 2, 'text': 'enfermedades Sí'}
        ]

        align_ai_corrections_to_raw_items(raw_items, ai_corrected)
        self.assertTrue(raw_items[0]['text'].startswith('¿'))
        # The question before 'Sí' should be closed with '?'
        self.assertIn('?', raw_items[2]['text'])
        self.assertIn('Sí', raw_items[2]['text'])

    def test_empty_or_none_safeguards(self):
        """
        Tests that passing empty or None lists does not raise exceptions.
        """
        raw_items = [{'index': 0, 'text': 'hola mundo'}]
        align_ai_corrections_to_raw_items(raw_items, [])
        self.assertEqual(raw_items[0]['text'], 'hola mundo')

        align_ai_corrections_to_raw_items([], [{'index': 0, 'text': 'hola'}])
        align_ai_corrections_to_raw_items(raw_items, None)
        self.assertEqual(raw_items[0]['text'], 'hola mundo')


if __name__ == '__main__':
    unittest.main()
