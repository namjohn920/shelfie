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
    CropThumbnail,
    CropReadResult,
    DetectionResult,
    DetectorTiming,
    MatchCandidate,
    MatchResult,
    ReaderBatchResult,
    ReviewDecision,
    ReviewGroup,
    ReviewItem,
    SpineDetection,
)
from library.services.book_reading import MODEL_ID, MissingApiKeyError
from library.services.review_grouping import group_review_items
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
    review_items: tuple[ReviewItem, ...] = (),
    review_groups: tuple[ReviewGroup, ...] | None = None,
    crop_thumbnails: tuple[CropThumbnail, ...] = (),
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
        review_items=review_items,
        review_groups=(
            group_review_items(review_items)
            if review_groups is None
            else review_groups
        ),
        crop_thumbnails=crop_thumbnails,
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
                'review_items': [],
                'review_groups': [],
                'crop_thumbnails': [],
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
    def test_analyze_serializes_one_thumbnail_per_detection(self, analyze_image):
        detections = (
            SpineDetection(1, BoundingBox(0, 0, 20, 30), 0.9),
            SpineDetection(2, BoundingBox(20, 0, 40, 30), 0.8),
        )
        analyze_image.return_value = fake_analysis_result(
            detections=detections,
            crop_thumbnails=(
                CropThumbnail(1, 'data:image/jpeg;base64,b25l'),
                CropThumbnail(2, 'data:image/jpeg;base64,dHdv'),
            ),
        )

        response = self.client.post(
            reverse('library:analyze'),
            {'image': uploaded_jpeg()},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        thumbnails = response.json()['crop_thumbnails']
        self.assertEqual([item['detection_index'] for item in thumbnails], [1, 2])
        self.assertEqual(len({item['detection_index'] for item in thumbnails}), 2)

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
            region_type='book',
            region_text=None,
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
            region_type=None,
            region_text=None,
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
        analyzed_book = AnalyzedBook(
            1,
            0,
            readable,
            match,
            ReviewDecision('high_confidence', ('high_confidence',)),
            suggested_match=best_candidate,
            crop_type='single_book',
            region_type='book',
        )
        analyze_image.return_value = fake_analysis_result(
            crop_results=(success, failure),
            books=(analyzed_book,),
            review_items=(
                ReviewItem('review-1-0', analyzed_book, (1,), 1),
            ),
            crop_thumbnails=(CropThumbnail(1, 'data:image/jpeg;base64,dGVzdA=='),),
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
        self.assertIsNone(body['books'][0]['read']['volume'])
        self.assertEqual(
            body['books'][0]['suggested_match']['catalog']['catalog_id'],
            'CAT009',
        )
        self.assertEqual(
            body['books'][0]['review'],
            {'status': 'high_confidence', 'reasons': ['high_confidence']},
        )
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
        self.assertEqual(body['review_items'][0]['id'], 'review-1-0')
        self.assertEqual(body['review_items'][0]['source_detection_indices'], [1])
        self.assertEqual(body['review_items'][0]['duplicate_count'], 1)
        self.assertEqual(body['review_groups'][0]['group_type'], 'ordinary')
        self.assertEqual(
            body['review_groups'][0]['representative_item_id'],
            'review-1-0',
        )
        self.assertEqual(
            body['review_groups'][0]['items'][0]['id'],
            'review-1-0',
        )
        self.assertEqual(
            body['crop_thumbnails'],
            [{'detection_index': 1, 'data_url': 'data:image/jpeg;base64,dGVzdA=='}],
        )
        self.assertEqual(
            body['warnings'],
            ['Detection 2: The hosted reader timed out for this crop.'],
        )

    @patch('library.api.analyze.analyze_image')
    def test_raw_match_remains_when_suggested_match_is_null(self, analyze_image):
        read = BookRead('GETTING STARTED IN CHART PATTERNS', 'BULKOWSKI')
        candidate = MatchCandidate(
            entry=CatalogEntry('CAT082', 'Quiet', 'Susan Cain'),
            matched_title='Quiet',
            matched_author='Susan Cain',
            title_evidence='canonical',
            title_score=56.1,
            author_score=42.0,
            combined_score=69.3,
        )
        match = MatchResult(
            candidate,
            None,
            56.1,
            42.0,
            69.3,
            68.4,
            0.9,
            60.0,
        )
        analyzed_book = AnalyzedBook(
            34,
            0,
            read,
            match,
            ReviewDecision(
                'review_required',
                (
                    'low_score',
                    'small_margin',
                    'candidate_not_reliable_enough_to_show',
                ),
            ),
            region_type='book',
        )
        analyze_image.return_value = fake_analysis_result(
            books=(analyzed_book,),
            review_items=(
                ReviewItem('review-34-0', analyzed_book, (34,), 1),
            ),
        )

        response = self.client.post(
            reverse('library:analyze'),
            {'image': uploaded_jpeg()},
            format='multipart',
        )

        body = response.json()
        self.assertEqual(
            body['books'][0]['match']['best_candidate']['catalog']['title'],
            'Quiet',
        )
        self.assertIsNone(body['books'][0]['suggested_match'])
        self.assertIsNone(body['review_items'][0]['suggested_match'])

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
