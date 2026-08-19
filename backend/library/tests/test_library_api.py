from unittest.mock import patch

from django.db import DatabaseError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from library.models import LibraryBook
from library.services.catalog_matching import load_catalog


class LibraryApiTests(APITestCase):
    def test_get_empty_library(self):
        response = self.client.get(reverse('library:library'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'books': []})

    def test_post_catalog_id_persists_canonical_fields(self):
        response = self.client.post(
            reverse('library:library'),
            {
                'catalog_id': 'CAT086',
                'title': 'Do not trust this copy',
                'author': 'Wrong author',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        book = LibraryBook.objects.get()
        self.assertEqual(book.catalog_id, 'CAT086')
        self.assertEqual(book.title, 'The Lean Startup')
        self.assertEqual(book.author, 'Eric Ries')
        self.assertEqual(book.source, LibraryBook.Source.CATALOG)
        self.assertEqual(response.json()['book']['title'], 'The Lean Startup')

    def test_post_unknown_catalog_id_is_rejected(self):
        response = self.client.post(
            reverse('library:library'),
            {'catalog_id': 'CAT999'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'error': 'Unknown catalog ID.'})
        self.assertFalse(LibraryBook.objects.exists())

    def test_post_manual_correction_trims_and_persists_fields(self):
        response = self.client.post(
            reverse('library:library'),
            {'title': '  Corrected title  ', 'author': '  Corrected author  '},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        book = LibraryBook.objects.get()
        self.assertIsNone(book.catalog_id)
        self.assertEqual(book.title, 'Corrected title')
        self.assertEqual(book.author, 'Corrected author')
        self.assertEqual(book.source, LibraryBook.Source.MANUAL)

    def test_manual_title_is_required(self):
        response = self.client.post(
            reverse('library:library'),
            {'title': '   ', 'author': 'Someone'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {'error': 'A title is required for a manual book.'},
        )

    def test_manual_author_is_optional(self):
        response = self.client.post(
            reverse('library:library'),
            {'title': 'Unknown-author book'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.json()['book']['author'])
        self.assertIsNone(LibraryBook.objects.get().author)

    def test_get_returns_persisted_entries_in_stable_order(self):
        first = LibraryBook.objects.create(
            title='First saved',
            source=LibraryBook.Source.MANUAL,
        )
        second = LibraryBook.objects.create(
            catalog_id='CAT086',
            title='The Lean Startup',
            author='Eric Ries',
            source=LibraryBook.Source.CATALOG,
        )

        response = self.client.get(reverse('library:library'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [book['id'] for book in response.json()['books']],
            [first.id, second.id],
        )

    def test_delete_populated_library_returns_count_and_clears_database(self):
        LibraryBook.objects.create(
            title='First saved',
            source=LibraryBook.Source.MANUAL,
        )
        LibraryBook.objects.create(
            catalog_id='CAT086',
            title='The Lean Startup',
            author='Eric Ries',
            source=LibraryBook.Source.CATALOG,
        )

        response = self.client.delete(reverse('library:library'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'deleted': 2})
        self.assertFalse(LibraryBook.objects.exists())

    def test_delete_empty_library_returns_zero(self):
        response = self.client.delete(reverse('library:library'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'deleted': 0})

    def test_delete_library_does_not_affect_catalog_csv(self):
        catalog_before = load_catalog()
        LibraryBook.objects.create(
            catalog_id='CAT086',
            title='The Lean Startup',
            author='Eric Ries',
            source=LibraryBook.Source.CATALOG,
        )

        response = self.client.delete(reverse('library:library'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(load_catalog(), catalog_before)

    def test_catalog_confirmation_requires_no_raw_ai_data(self):
        response = self.client.post(
            reverse('library:library'),
            {'catalog_id': 'CAT086'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(LibraryBook.objects.count(), 1)

    def test_malformed_json_is_rejected(self):
        response = self.client.generic(
            'POST',
            reverse('library:library'),
            b'{',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {'error': 'Request body must be valid JSON.'},
        )

    @patch(
        'library.serializers.LibraryBook.objects.create',
        side_effect=DatabaseError,
    )
    def test_database_write_failure_returns_concise_json(self, _create):
        response = self.client.post(
            reverse('library:library'),
            {'title': 'A valid manual book'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {'error': 'The book could not be saved.'})

    @patch(
        'django.db.models.query.QuerySet.delete',
        side_effect=DatabaseError,
    )
    def test_database_delete_failure_returns_concise_json(self, _delete):
        response = self.client.delete(reverse('library:library'))

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(
            response.json(),
            {'error': 'The library could not be cleared.'},
        )
