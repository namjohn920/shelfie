import csv
from pathlib import Path

from django.test import SimpleTestCase

from library.services.catalog_matching import (
    REQUIRED_CATALOG_COLUMNS,
    load_catalog,
)


CATALOG_PATH = Path(__file__).resolve().parents[3] / 'catalog.csv'


class CatalogValidationTests(SimpleTestCase):
    def test_catalog_has_required_shape_and_unique_complete_rows(self):
        header = CATALOG_PATH.read_text(encoding='utf-8').splitlines()[0].split(',')
        entries = load_catalog(CATALOG_PATH)
        with CATALOG_PATH.open(encoding='utf-8', newline='') as catalog_file:
            rows = tuple(csv.DictReader(catalog_file))

        self.assertTrue(REQUIRED_CATALOG_COLUMNS.issubset(header))
        self.assertTrue(all(None not in row for row in rows))
        self.assertGreaterEqual(len(entries), 100)
        self.assertEqual(len(entries), len({entry.catalog_id for entry in entries}))
        self.assertTrue(all(entry.title and entry.author for entry in entries))

    def test_catalog_explicitly_covers_every_required_ambiguity(self):
        entries = load_catalog(CATALOG_PATH)
        tags = {tag for entry in entries for tag in entry.ambiguity_tags}

        self.assertTrue(
            {
                'separate_edition',
                'publication_title',
                'shared_title',
                'omnibus',
                'substring_title',
                'author_forms',
                'translated_title',
            }.issubset(tags)
        )

        editions = [entry for entry in entries if 'separate_edition' in entry.ambiguity_tags]
        self.assertLess(len({(entry.title, entry.author) for entry in editions}), len(editions))

        shared_titles = [entry for entry in entries if 'shared_title' in entry.ambiguity_tags]
        self.assertLess(len({entry.title for entry in shared_titles}), len(shared_titles))
        self.assertGreater(len({entry.author for entry in shared_titles}), 1)

        omnibus = next(entry for entry in entries if 'omnibus' in entry.ambiguity_tags)
        canonical_titles = {entry.title for entry in entries}
        self.assertTrue(set(omnibus.contains_titles).issubset(canonical_titles))

        substring_titles = [
            entry.title.casefold()
            for entry in entries
            if 'substring_title' in entry.ambiguity_tags
        ]
        self.assertTrue(
            any(
                first != second and first in second
                for first in substring_titles
                for second in substring_titles
            )
        )

        self.assertTrue(
            any(
                entry.alternate_titles
                for entry in entries
                if 'publication_title' in entry.ambiguity_tags
            )
        )
        self.assertTrue(
            all(
                entry.author_aliases
                for entry in entries
                if 'author_forms' in entry.ambiguity_tags
            )
        )

    def test_unicode_survives_utf8_csv_parsing(self):
        entries = {entry.catalog_id: entry for entry in load_catalog(CATALOG_PATH)}

        self.assertEqual(entries['CAT102'].author, 'Gabriel García Márquez')
        self.assertIn('百年孤独', entries['CAT102'].alternate_titles)
        self.assertIn('채식주의자', entries['CAT113'].alternate_titles)
