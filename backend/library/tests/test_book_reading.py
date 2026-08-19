import json
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase
from PIL import Image

from library.contracts.analysis import BookRead, BoundingBox, CropReadResult
from library.services.book_reading import (
    CORE_PROMPT,
    DEFAULT_MAX_WORKERS,
    MAX_BOOKS_PER_CROP,
    MODEL_ID,
    OPENROUTER_PROVIDER_PREFERENCES,
    MissingApiKeyError,
    read_book_crop,
    read_book_crops,
)
from library.services.crop_processing import SpineCrop


def crop(detection_index: int = 1) -> SpineCrop:
    box = BoundingBox(0.0, 0.0, 20.0, 30.0)
    return SpineCrop(
        detection_index=detection_index,
        source_box=box,
        crop_box=box,
        confidence=0.9,
        image=Image.new('RGB', (20, 30), color='navy'),
    )


def extraction(
    *,
    crop_type='single_book',
    region_type='book',
    region_text=None,
    readability='readable',
    books=None,
    notes='',
):
    resolved_books = books
    if resolved_books is None:
        resolved_books = [
            {
                'title': 'The Hobbit',
                'author': 'J. R. R. Tolkien',
                'language': 'en',
                'raw_text': 'THE HOBBIT J. R. R. TOLKIEN',
            }
        ]
    return {
        'crop_type': crop_type,
        'region_type': region_type,
        'region_text': region_text,
        'readability': readability,
        'books': [
            {'volume': None, **book}
            for book in resolved_books
        ],
        'notes': notes,
    }


def openrouter_response(extracted=None, **overrides):
    body = {
        'model': MODEL_ID,
        'provider': 'Test Provider',
        'choices': [
            {
                'message': {
                    'content': json.dumps(
                        extracted if extracted is not None else extraction(),
                        ensure_ascii=False,
                    )
                }
            }
        ],
        'usage': {
            'prompt_tokens': 101,
            'completion_tokens': 42,
            'total_tokens': 143,
            'cost': 0.00012345,
        },
    }
    body.update(overrides)
    response = Mock(status_code=200)
    response.json.return_value = body
    return response


def successful_result(detection_index: int, *, cost=0.001) -> CropReadResult:
    return CropReadResult(
        detection_index=detection_index,
        crop_type='single_book',
        region_type='book',
        region_text=None,
        readability='readable',
        books=(BookRead(title='The Hobbit'),),
        status='ok',
        error_code=None,
        error_message=None,
        latency_seconds=0.25,
        cost_usd=cost,
        model_id=MODEL_ID,
        provider='Test Provider',
    )


class BookReadingTests(SimpleTestCase):
    @patch('library.services.book_reading.requests.post')
    def test_valid_single_english_book_and_request_shape(self, post):
        post.return_value = openrouter_response()

        result = read_book_crop(crop(), api_key='test-key')

        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.crop_type, 'single_book')
        self.assertEqual(result.region_type, 'book')
        self.assertEqual(result.books[0].title, 'The Hobbit')
        self.assertEqual(result.books[0].author, 'J. R. R. Tolkien')
        request = post.call_args.kwargs
        self.assertEqual(request['timeout'], 90)
        self.assertEqual(request['json']['model'], MODEL_ID)
        self.assertFalse(request['json']['stream'])
        self.assertEqual(request['json']['temperature'], 0)
        self.assertEqual(
            request['json']['provider'],
            OPENROUTER_PROVIDER_PREFERENCES,
        )
        self.assertTrue(request['json']['provider']['require_parameters'])
        self.assertEqual(request['json']['provider']['sort'], 'latency')
        self.assertTrue(request['json']['response_format']['json_schema']['strict'])
        content = request['json']['messages'][0]['content']
        self.assertEqual(content[0], {'type': 'text', 'text': CORE_PROMPT})
        self.assertTrue(content[1]['image_url']['url'].startswith('data:image/jpeg;base64,'))
        self.assertIn('non_book', CORE_PROMPT)
        self.assertIn('volume 21', CORE_PROMPT)

    @patch('library.services.book_reading.requests.post')
    def test_valid_korean_result_preserves_unicode(self, post):
        post.return_value = openrouter_response(
            extraction(
                books=[
                    {
                        'title': '土地',
                        'author': '박경리',
                        'language': '한국어',
                        'raw_text': '12土地 박경리',
                    }
                ]
            )
        )

        result = read_book_crop(crop(12), api_key='test-key')

        self.assertEqual(result.books[0].title, '土地')
        self.assertEqual(result.books[0].author, '박경리')
        self.assertEqual(result.books[0].raw_text, '12土地 박경리')
        self.assertIsNone(result.books[0].volume)

    @patch('library.services.book_reading.requests.post')
    def test_valid_multiple_book_crop(self, post):
        books = [
            {
                'title': 'The Lean Startup',
                'author': 'Eric Ries',
                'language': 'en',
                'raw_text': 'THE LEAN STARTUP ERIC RIES',
            },
            {
                'title': "Nature's Law",
                'author': 'R. N. Elliott',
                'language': 'en',
                'raw_text': "NATURE'S LAW R. N. ELLIOTT",
            },
        ]
        post.return_value = openrouter_response(
            extraction(crop_type='multiple_books', books=books)
        )

        result = read_book_crop(crop(42), api_key='test-key')

        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.crop_type, 'multiple_books')
        self.assertEqual([book.title for book in result.books], [
            'The Lean Startup',
            "Nature's Law",
        ])

    @patch('library.services.book_reading.requests.post')
    def test_valid_unreadable_crop(self, post):
        post.return_value = openrouter_response(
            extraction(
                crop_type='unreadable',
                region_type='uncertain',
                readability='unreadable',
                books=[],
                notes='No usable book text.',
            )
        )

        result = read_book_crop(crop(), api_key='test-key')

        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.crop_type, 'unreadable')
        self.assertEqual(result.books, ())
        self.assertEqual(result.notes, 'No usable book text.')

    @patch('library.services.book_reading.requests.post')
    def test_valid_non_book_region_preserves_visible_text_without_books(self, post):
        post.return_value = openrouter_response(
            extraction(
                crop_type=None,
                region_type='non_book',
                region_text='DURABLE AVERY',
                readability='readable',
                books=[],
            )
        )

        result = read_book_crop(crop(28), api_key='test-key')

        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.region_type, 'non_book')
        self.assertEqual(result.region_text, 'DURABLE AVERY')
        self.assertEqual(result.books, ())

    @patch('library.services.book_reading.requests.post')
    def test_non_book_region_cannot_manufacture_book_entries(self, post):
        post.return_value = openrouter_response(
            extraction(
                crop_type=None,
                region_type='non_book',
                region_text='DURABLE AVERY',
            )
        )

        result = read_book_crop(crop(28), api_key='test-key')

        self.assertEqual(result.status, 'error')
        self.assertEqual(result.error_code, 'invalid_schema')

    @patch('library.services.book_reading.requests.post')
    def test_cleans_only_terminal_standalone_korean_author_marker(self, post):
        post.return_value = openrouter_response(
            extraction(
                books=[
                    {
                        'title': '엘리어트 파동이론 마스터',
                        'author': '글렌 닐리 지음',
                        'volume': None,
                        'language': 'ko',
                        'raw_text': '글렌 닐리 지음',
                    },
                    {
                        'title': 'Example',
                        'author': '한글',
                        'volume': None,
                        'language': 'ko',
                        'raw_text': '한글',
                    },
                ],
                crop_type='multiple_books',
                region_type='multiple_books',
            )
        )

        result = read_book_crop(crop(41), api_key='test-key')

        self.assertEqual(result.books[0].author, '글렌 닐리')
        self.assertEqual(result.books[1].author, '한글')

    @patch('library.services.book_reading.requests.post')
    def test_serializes_explicit_volume_separately_from_title(self, post):
        post.return_value = openrouter_response(
            extraction(
                books=[
                    {
                        'title': '土地',
                        'author': '박경리 지음',
                        'volume': '21',
                        'language': 'ko',
                        'raw_text': '21 土地 박경리 지음',
                    }
                ]
            )
        )

        result = read_book_crop(crop(17), api_key='test-key')

        self.assertEqual(result.books[0].title, '土地')
        self.assertEqual(result.books[0].volume, '21')
        self.assertEqual(result.books[0].author, '박경리')

    @patch('library.services.book_reading.requests.post')
    def test_rejects_edition_and_title_text_as_false_volumes(self, post):
        post.return_value = openrouter_response(
            extraction(
                crop_type='multiple_books',
                region_type='multiple_books',
                books=[
                    {
                        'title': 'GETTING STARTED IN CHART PATTERNS',
                        'author': 'BULKOWSKI',
                        'volume': 'SECOND EDITION',
                        'language': 'en',
                        'raw_text': 'SECOND EDITION',
                    },
                    {
                        'title': '1등의 통찰',
                        'author': None,
                        'volume': '1',
                        'language': 'ko',
                        'raw_text': '1등의 통찰',
                    },
                    {
                        'title': '1984',
                        'author': 'George Orwell',
                        'volume': '1984',
                        'language': 'en',
                        'raw_text': '1984 George Orwell',
                    },
                ],
            )
        )

        result = read_book_crop(crop(), api_key='test-key')

        self.assertEqual([book.volume for book in result.books], [None, None, None])

    @patch('library.services.book_reading.requests.post')
    def test_http_non_200(self, post):
        post.return_value = Mock(status_code=429)

        result = read_book_crop(crop(), api_key='test-key')

        self.assertEqual(result.status, 'error')
        self.assertEqual(result.error_code, 'http_error')
        self.assertEqual(result.error_message, 'The hosted reader returned HTTP 429.')

    @patch('library.services.book_reading.requests.post')
    def test_timeout(self, post):
        post.side_effect = requests.Timeout('details must not escape')

        result = read_book_crop(crop(), api_key='test-key')

        self.assertEqual(result.status, 'error')
        self.assertEqual(result.error_code, 'timeout')
        self.assertNotIn('details', result.error_message)

    @patch('library.services.book_reading.requests.post')
    def test_http_200_with_choice_provider_error(self, post):
        post.return_value = openrouter_response(
            choices=[
                {
                    'error': {
                        'message': 'private upstream detail',
                        'metadata': {'error_type': 'rate_limit_exceeded'},
                    },
                    'message': {'content': '{"crop_type":'},
                }
            ]
        )

        result = read_book_crop(crop(58), api_key='test-key')

        self.assertEqual(result.status, 'error')
        self.assertEqual(result.error_code, 'provider_error')
        self.assertNotIn('private upstream detail', result.error_message)

    @patch('library.services.book_reading.requests.post')
    def test_malformed_assistant_json(self, post):
        post.return_value = openrouter_response(
            choices=[{'message': {'content': '{not-json'}}]
        )

        result = read_book_crop(crop(), api_key='test-key')

        self.assertEqual(result.status, 'error')
        self.assertEqual(result.error_code, 'malformed_response')

    @patch('library.services.book_reading.requests.post')
    def test_structurally_invalid_schema(self, post):
        invalid = extraction()
        invalid.pop('readability')
        post.return_value = openrouter_response(invalid)

        result = read_book_crop(crop(), api_key='test-key')

        self.assertEqual(result.status, 'error')
        self.assertEqual(result.error_code, 'invalid_schema')

    @patch('library.services.book_reading.requests.post')
    def test_enforces_maximum_books(self, post):
        books = [
            {
                'title': f'Book {index}',
                'author': None,
                'language': 'en',
                'raw_text': f'Book {index}',
            }
            for index in range(MAX_BOOKS_PER_CROP + 1)
        ]
        post.return_value = openrouter_response(
            extraction(crop_type='multiple_books', books=books)
        )

        result = read_book_crop(crop(), api_key='test-key')

        self.assertEqual(result.status, 'error')
        self.assertEqual(result.error_code, 'invalid_schema')

    @patch('library.services.book_reading.requests.post')
    def test_empty_book_strings_become_none(self, post):
        post.return_value = openrouter_response(
            extraction(
                readability='partial',
                books=[
                    {
                        'title': '  ',
                        'author': '',
                        'language': '\t',
                        'raw_text': ' visible fragment ',
                    }
                ],
            )
        )

        result = read_book_crop(crop(), api_key='test-key')

        self.assertEqual(
            result.books[0],
            BookRead(
                title=None,
                author=None,
                language=None,
                raw_text='visible fragment',
                readability='partial',
            ),
        )

    @patch('library.services.book_reading.time.perf_counter', side_effect=[10.0, 11.25])
    @patch('library.services.book_reading.requests.post')
    def test_captures_cost_latency_and_safe_metadata(self, post, _perf_counter):
        post.return_value = openrouter_response()

        result = read_book_crop(crop(), api_key='test-key')

        self.assertEqual(result.latency_seconds, 1.25)
        self.assertEqual(result.cost_usd, 0.00012345)
        self.assertEqual(result.model_id, MODEL_ID)
        self.assertEqual(result.provider, 'Test Provider')
        self.assertEqual(result.prompt_tokens, 101)
        self.assertEqual(result.completion_tokens, 42)
        self.assertEqual(result.total_tokens, 143)


class BookReadingBatchTests(SimpleTestCase):
    @patch(
        'library.services.book_reading.ThreadPoolExecutor',
        wraps=ThreadPoolExecutor,
    )
    @patch('library.services.book_reading.read_book_crop')
    def test_default_worker_count_is_bounded_at_eight(
        self,
        read_book_crop,
        thread_pool_executor,
    ):
        read_book_crop.side_effect = lambda item, *, api_key: successful_result(
            item.detection_index
        )

        result = read_book_crops(
            tuple(crop(index) for index in range(1, DEFAULT_MAX_WORKERS + 2)),
            api_key='test-key',
        )

        self.assertEqual(DEFAULT_MAX_WORKERS, 8)
        thread_pool_executor.assert_called_once_with(max_workers=8)
        self.assertEqual(result.attempted_crops, 9)

    @patch('library.services.book_reading.read_book_crop')
    def test_isolates_failure_orders_results_and_summarizes(self, read_book_crop):
        def result_for(item, *, api_key):
            if item.detection_index == 2:
                raise RuntimeError('one worker failed')
            return successful_result(item.detection_index, cost=0.00125)

        read_book_crop.side_effect = result_for

        result = read_book_crops(
            (crop(3), crop(1), crop(2)),
            api_key='test-key',
            max_workers=2,
        )

        self.assertEqual(
            [item.detection_index for item in result.results],
            [1, 2, 3],
        )
        self.assertEqual([item.status for item in result.results], ['ok', 'error', 'ok'])
        self.assertEqual(result.attempted_crops, 3)
        self.assertEqual(result.successful_crops, 2)
        self.assertEqual(result.failed_crops, 1)
        self.assertEqual(result.total_cost_usd, 0.0025)
        self.assertGreaterEqual(result.wall_seconds, 0.0)

    def test_missing_api_key_raises_before_hosted_work(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MissingApiKeyError):
                read_book_crops((crop(),))

    def test_zero_crops_needs_no_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            result = read_book_crops(())

        self.assertEqual(result.attempted_crops, 0)
        self.assertEqual(result.results, ())
