from django.test import SimpleTestCase

from library.services.text_normalization import normalize_author, normalize_text


class TextNormalizationTests(SimpleTestCase):
    def test_nfkc_casefold_punctuation_and_whitespace(self):
        self.assertEqual(
            normalize_text('  THE  Handmaid’s\tTale! '),
            'the handmaid s tale',
        )

    def test_preserves_non_latin_and_accented_text(self):
        self.assertEqual(normalize_text('百年孤独'), '百年孤独')
        self.assertEqual(normalize_text('García Márquez'), 'garcía márquez')

    def test_reorders_lastname_firstname_author_form(self):
        self.assertEqual(normalize_author('Tolkien, J. R. R.'), 'j r r tolkien')
