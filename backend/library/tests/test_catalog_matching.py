from django.test import SimpleTestCase

from library.contracts.analysis import BookRead
from library.services.catalog_matching import load_catalog, match_catalog


class CatalogMatchingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catalog = load_catalog()

    def match(self, title: str, author: str | None = None):
        return match_catalog(BookRead(title=title, author=author), self.catalog)

    def test_exact_match(self):
        result = self.match('The Hobbit', 'J. R. R. Tolkien')
        self.assertEqual(result.best_candidate.entry.catalog_id, 'CAT009')
        self.assertEqual(result.combined_score, 100.0)

    def test_punctuation_and_case(self):
        result = self.match('thinking fast & SLOW', 'daniel kahneman')
        self.assertEqual(result.best_candidate.entry.catalog_id, 'CAT081')

    def test_us_uk_alternate_title(self):
        result = self.match('The Golden Compass', 'Philip Pullman')
        self.assertEqual(result.best_candidate.entry.catalog_id, 'CAT151')
        self.assertEqual(result.best_candidate.title_evidence, 'alternate')

    def test_initials_full_author_and_lastname_firstname(self):
        initials = self.match('The Hobbit', 'JRR Tolkien')
        reversed_name = self.match('The Hobbit', 'Tolkien, J. R. R.')
        self.assertEqual(initials.best_candidate.entry.catalog_id, 'CAT009')
        self.assertEqual(reversed_name.best_candidate.entry.catalog_id, 'CAT009')

    def test_unicode_accented_form(self):
        result = self.match('One Hundred Years of Solitude', 'Gabriel Garcia Marquez')
        self.assertEqual(result.best_candidate.entry.catalog_id, 'CAT102')

    def test_translated_non_english_alternate(self):
        result = self.match('ノルウェイの森', '村上春樹')
        self.assertEqual(result.best_candidate.entry.catalog_id, 'CAT111')
        self.assertEqual(result.title_score, 100.0)

    def test_same_title_different_author(self):
        result = self.match('Home', 'Marilynne Robinson')
        self.assertEqual(result.best_candidate.entry.catalog_id, 'CAT050')
        self.assertEqual(result.second_candidate.entry.catalog_id, 'CAT049')

    def test_substring_collision(self):
        result = self.match('It', 'Stephen King')
        self.assertEqual(result.best_candidate.entry.catalog_id, 'CAT042')
        self.assertNotEqual(result.second_candidate.entry.catalog_id, 'CAT043')

    def test_multiple_editions_have_small_margin(self):
        result = self.match('Pride and Prejudice', 'Jane Austen')
        self.assertEqual(result.best_candidate.entry.catalog_id, 'CAT026')
        self.assertEqual(result.second_candidate.entry.catalog_id, 'CAT027')
        self.assertEqual(result.margin, 0.0)

    def test_omnibus_contained_title_prefers_individual_volume(self):
        result = self.match('The Fellowship of the Ring', 'JRR Tolkien')
        self.assertEqual(result.best_candidate.entry.catalog_id, 'CAT011')
        self.assertEqual(result.second_candidate.entry.catalog_id, 'CAT014')
        self.assertEqual(result.second_candidate.title_evidence, 'contained')

    def test_missing_author_uses_title_only(self):
        result = self.match('The Silent Patient')
        self.assertEqual(result.best_candidate.entry.catalog_id, 'CAT059')
        self.assertIsNone(result.author_score)

    def test_partial_title(self):
        result = self.match('Fellowship Ring', 'Tolkien')
        self.assertEqual(result.best_candidate.entry.catalog_id, 'CAT011')

    def test_nonsense_returns_no_match(self):
        result = self.match('zqxjv impossible shelf token', 'nobody qqq')
        self.assertIsNone(result.best_candidate)
        self.assertIsNone(result.combined_score)

    def test_same_work_publication_titles_exposes_small_margin(self):
        result = self.match("Harry Potter and the Sorcerer's Stone", 'J. K. Rowling')
        self.assertEqual(
            {result.best_candidate.entry.catalog_id, result.second_candidate.entry.catalog_id},
            {'CAT001', 'CAT002'},
        )
        self.assertEqual(result.margin, 0.0)
