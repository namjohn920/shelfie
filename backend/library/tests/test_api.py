from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from library.contracts.analysis import (
    AnalysisPipelineResult,
    AnalyzedBook,
    BookRead,
    BoundingBox,
    CatalogEntry,
    CropReadResult,
    DetectionResult,
    DetectorTiming,
    MatchCandidate,
    MatchResult,
    ReaderBatchResult,
    SpineDetection,
)
from library.services.book_reading import MODEL_ID, MissingApiKeyError
from library.services.spine_detection import SpineDetectionError


def fake_detection_result(
    detections: tuple[SpineDetection, ...] = (),
) -> DetectionResult:
    return DetectionResult(
        detections=detections,
        checkpoint='test-checkpoint',
        threshold=0.30,
        image_width=48,
        image_height=32,
        timing=DetectorTiming(
            model_load_seconds=0.0,
            preprocess_seconds=0.01,
            inference_seconds=0.02,
            postprocess_seconds=0.01,
            total_seconds=0.04,
            model_was_cached=True,
        ),
    )


def fake_analysis_result(
    *,
    detections: tuple[SpineDetection, ...] = (),
    crop_results: tuple[CropReadResult, ...] = (),
    books: tuple[AnalyzedBook, ...] = (),
    warnings: tuple[str, ...] = (),
) -> AnalysisPipelineResult:
    successful = sum(result.status == 'ok' for result in crop_results)
    return AnalysisPipelineResult(
        detection=fake_detection_result(detections),
        hosted_reader=ReaderBatchResult(
            results=crop_results,
            model_id=MODEL_ID,
            attempted_crops=len(crop_results),
            successful_crops=successful,
            failed_crops=len(crop_results) - successful,
            wall_seconds=0.4 if crop_results else 0.0,
            total_cost_usd=sum(result.cost_usd or 0.0 for result in crop_results),
        ),
        books=books,
        warnings=warnings,
    )


def uploaded_jpeg() -> SimpleUploadedFile:
    image_bytes = BytesIO()
    Image.new('RGB', (48, 32), color='navy').save(image_bytes, format='JPEG')
    return SimpleUploadedFile(
        'bookshelf.jpg',
        image_bytes.getvalue(),
        content_type='image/jpeg',
    )


class ShelfieApiTests(APITestCase):
    def test_health_returns_ok(self):
        response = self.client.get(reverse('library:health'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_analyze_rejects_missing_image(self):
        response = self.client.post(
            reverse('library:analyze'),
            {},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'error': 'No image was provided.'})

    @patch('library.api.analyze.analyze_image')
    def test_zero_detections_returns_metadata_and_empty_results(self, analyze_image):
        analyze_image.return_value = fake_analysis_result()

        response = self.client.post(
            reverse('library:analyze'),
            {'image': uploaded_jpeg()},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                'status': 'received',
                'filename': 'bookshelf.jpg',
                'content_type': 'image/jpeg',
                'width': 48,
                'height': 32,
                'detection_count': 0,
                'detections': [],
                'detector': {
                    'checkpoint': 'test-checkpoint',
                    'threshold': 0.3,
                    'coordinate_space': 'upright_image_pixels',
                    'image_width': 48,
                    'image_height': 32,
                    'timing': {
                        'model_load_seconds': 0.0,
                        'preprocess_seconds': 0.01,
                        'inference_seconds': 0.02,
                        'postprocess_seconds': 0.01,
                        'total_seconds': 0.04,
                        'model_was_cached': True,
                    },
                },
                'hosted_reader': {
                    'model': MODEL_ID,
                    'attempted_crops': 0,
                    'successful_crops': 0,
                    'failed_crops': 0,
                    'wall_seconds': 0.0,
                    'total_cost_usd': 0.0,
                    'crop_results': [],
                },
                'books': [],
                'warnings': [],
            },
        )
        analyze_image.assert_called_once()

    @patch('library.api.analyze.analyze_image')
    def test_analyze_serializes_fake_detection(self, analyze_image):
        detection = SpineDetection(
            detection_index=1,
            box=BoundingBox(1.25, 2.5, 20.75, 30.0),
            confidence=0.87654321,
        )
        analyze_image.return_value = fake_analysis_result(detections=(detection,))

        response = self.client.post(
            reverse('library:analyze'),
            {'image': uploaded_jpeg()},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['detection_count'], 1)
        self.assertEqual(
            response.json()['detections'],
            [
                {
                    'detection_index': 1,
                    'label': 'book',
                    'confidence': 0.876543,
                    'box': {
                        'left': 1.25,
                        'top': 2.5,
                        'right': 20.75,
                        'bottom': 30.0,
                    },
                }
            ],
        )

    @patch('library.api.analyze.analyze_image')
    def test_partial_hosted_failure_returns_successful_books(self, analyze_image):
        readable = BookRead(
            title='The Hobbit',
            author='J. R. R. Tolkien',
            raw_text='THE HOBBIT',
            language='en',
        )
        success = CropReadResult(
            detection_index=1,
            crop_type='single_book',
            readability='readable',
            books=(readable,),
            status='ok',
            error_code=None,
            error_message=None,
            latency_seconds=0.2,
            cost_usd=0.0001,
            model_id=MODEL_ID,
            provider='Test Provider',
        )
        failure = CropReadResult(
            detection_index=2,
            crop_type=None,
            readability=None,
            books=(),
            status='error',
            error_code='timeout',
            error_message='The hosted reader timed out for this crop.',
            latency_seconds=90.0,
            cost_usd=None,
            model_id=MODEL_ID,
        )
        best_candidate = MatchCandidate(
            entry=CatalogEntry('CAT009', 'The Hobbit', 'J. R. R. Tolkien'),
            matched_title='The Hobbit',
            matched_author='J. R. R. Tolkien',
            title_evidence='canonical',
            title_score=100.0,
            author_score=100.0,
            combined_score=100.0,
        )
        second_candidate = MatchCandidate(
            entry=CatalogEntry('CAT010', 'The Silmarillion', 'J. R. R. Tolkien'),
            matched_title='The Silmarillion',
            matched_author='J. R. R. Tolkien',
            title_evidence='canonical',
            title_score=60.0,
            author_score=100.0,
            combined_score=72.0,
        )
        match = MatchResult(
            best_candidate=best_candidate,
            second_candidate=second_candidate,
            title_score=100.0,
            author_score=100.0,
            combined_score=100.0,
            second_score=72.0,
            margin=28.0,
            candidate_floor=60.0,
        )
        analyze_image.return_value = fake_analysis_result(
            crop_results=(success, failure),
            books=(AnalyzedBook(1, 0, readable, match),),
            warnings=('Detection 2: The hosted reader timed out for this crop.',),
        )

        response = self.client.post(
            reverse('library:analyze'),
            {'image': uploaded_jpeg()},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body['hosted_reader']['successful_crops'], 1)
        self.assertEqual(body['hosted_reader']['failed_crops'], 1)
        self.assertEqual(body['hosted_reader']['crop_results'][1]['error_code'], 'timeout')
        self.assertEqual(body['books'][0]['detection_index'], 1)
        self.assertEqual(body['books'][0]['book_index'], 0)
        self.assertEqual(body['books'][0]['read']['title'], 'The Hobbit')
        serialized_match = body['books'][0]['match']
        self.assertEqual(
            serialized_match['best_candidate']['catalog']['catalog_id'],
            'CAT009',
        )
        self.assertEqual(
            serialized_match['second_candidate']['catalog']['catalog_id'],
            'CAT010',
        )
        self.assertEqual(serialized_match['title_score'], 100.0)
        self.assertEqual(serialized_match['author_score'], 100.0)
        self.assertEqual(serialized_match['combined_score'], 100.0)
        self.assertEqual(serialized_match['second_score'], 72.0)
        self.assertEqual(serialized_match['margin'], 28.0)
        self.assertEqual(serialized_match['candidate_floor'], 60.0)
        self.assertEqual(
            body['warnings'],
            ['Detection 2: The hosted reader timed out for this crop.'],
        )

    @patch('library.api.analyze.analyze_image')
    def test_analyze_translates_detector_failure(self, analyze_image):
        analyze_image.side_effect = SpineDetectionError('model failed')

        response = self.client.post(
            reverse('library:analyze'),
            {'image': uploaded_jpeg()},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.json(),
            {'error': 'The local book detector is temporarily unavailable.'},
        )

    @patch('library.api.analyze.analyze_image')
    def test_missing_api_key_maps_cleanly(self, analyze_image):
        analyze_image.side_effect = MissingApiKeyError('do not expose config details')

        response = self.client.post(
            reverse('library:analyze'),
            {'image': uploaded_jpeg()},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.json(),
            {'error': 'The hosted book reader is not configured.'},
        )

    def test_analyze_rejects_invalid_image_bytes(self):
        upload = SimpleUploadedFile(
            'not-an-image.jpg',
            b'this is not an image',
            content_type='image/jpeg',
        )

        response = self.client.post(
            reverse('library:analyze'),
            {'image': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {'error': 'The uploaded file is not a valid image.'},
        )
