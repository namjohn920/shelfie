import os
from unittest.mock import patch

from django.test import SimpleTestCase
from PIL import Image

from library.contracts.analysis import (
    BookRead,
    BoundingBox,
    CropReadResult,
    DetectionResult,
    DetectorTiming,
    MatchResult,
    ReaderBatchResult,
    SpineDetection,
)
from library.services.analysis_pipeline import analyze_image
from library.services.book_reading import MODEL_ID


def detection_result(*indices: int) -> DetectionResult:
    return DetectionResult(
        detections=tuple(
            SpineDetection(
                detection_index=index,
                box=BoundingBox(1.0, 1.0, 12.0, 18.0),
                confidence=0.9,
            )
            for index in indices
        ),
        checkpoint='test-checkpoint',
        threshold=0.3,
        image_width=20,
        image_height=20,
        timing=DetectorTiming(0.0, 0.01, 0.02, 0.01, 0.04, True),
    )


def crop_read_result(
    detection_index: int,
    books: tuple[BookRead, ...],
    *,
    crop_type='single_book',
) -> CropReadResult:
    return CropReadResult(
        detection_index=detection_index,
        crop_type=crop_type,
        readability=books[0].readability if books else 'unreadable',
        books=books,
        status='ok',
        error_code=None,
        error_message=None,
        latency_seconds=0.2,
        cost_usd=0.0001,
        model_id=MODEL_ID,
    )


def failed_crop(detection_index: int) -> CropReadResult:
    return CropReadResult(
        detection_index=detection_index,
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


def batch(*results: CropReadResult) -> ReaderBatchResult:
    successful = sum(result.status == 'ok' for result in results)
    return ReaderBatchResult(
        results=results,
        model_id=MODEL_ID,
        attempted_crops=len(results),
        successful_crops=successful,
        failed_crops=len(results) - successful,
        wall_seconds=0.4,
        total_cost_usd=sum(result.cost_usd or 0.0 for result in results),
    )


NO_CANDIDATE_MATCH = MatchResult(
    best_candidate=None,
    second_candidate=None,
    title_score=None,
    author_score=None,
    combined_score=None,
    second_score=None,
    margin=None,
    candidate_floor=60.0,
)


class AnalysisPipelineTests(SimpleTestCase):
    @patch('library.services.analysis_pipeline.match_catalog')
    @patch('library.services.analysis_pipeline.load_catalog')
    @patch('library.services.analysis_pipeline.read_book_crops')
    @patch('library.services.analysis_pipeline.detect_book_spines')
    def test_successful_read_is_passed_to_matcher(
        self,
        detect_book_spines,
        read_book_crops,
        load_catalog,
        match_catalog,
    ):
        book_read = BookRead(title='The Hobbit', author='J. R. R. Tolkien')
        detect_book_spines.return_value = detection_result(1)
        read_book_crops.return_value = batch(crop_read_result(1, (book_read,)))
        catalog = (object(),)
        load_catalog.return_value = catalog
        match_catalog.return_value = NO_CANDIDATE_MATCH

        result = analyze_image(Image.new('RGB', (20, 20)), api_key='test-key')

        match_catalog.assert_called_once_with(book_read, catalog)
        self.assertEqual(result.books[0].read, book_read)
        self.assertIs(result.books[0].match, NO_CANDIDATE_MATCH)

    @patch('library.services.analysis_pipeline.match_catalog')
    @patch('library.services.analysis_pipeline.load_catalog')
    @patch('library.services.analysis_pipeline.read_book_crops')
    @patch('library.services.analysis_pipeline.detect_book_spines')
    def test_unreadable_read_does_not_force_match(
        self,
        detect_book_spines,
        read_book_crops,
        load_catalog,
        match_catalog,
    ):
        unreadable = BookRead(
            title='Untrusted guess',
            readability='unreadable',
        )
        detect_book_spines.return_value = detection_result(1)
        read_book_crops.return_value = batch(crop_read_result(1, (unreadable,)))

        result = analyze_image(Image.new('RGB', (20, 20)), api_key='test-key')

        match_catalog.assert_not_called()
        load_catalog.assert_not_called()
        self.assertIsNone(result.books[0].match)

    @patch('library.services.analysis_pipeline.match_catalog')
    @patch('library.services.analysis_pipeline.load_catalog', return_value=(object(),))
    @patch('library.services.analysis_pipeline.read_book_crops')
    @patch('library.services.analysis_pipeline.detect_book_spines')
    def test_multiple_books_from_one_detection_are_matched_separately(
        self,
        detect_book_spines,
        read_book_crops,
        _load_catalog,
        match_catalog,
    ):
        books = (
            BookRead(title='The Lean Startup', author='Eric Ries'),
            BookRead(title="Nature's Law", author='R. N. Elliott'),
        )
        detect_book_spines.return_value = detection_result(42)
        read_book_crops.return_value = batch(
            crop_read_result(42, books, crop_type='multiple_books')
        )
        match_catalog.return_value = NO_CANDIDATE_MATCH

        result = analyze_image(Image.new('RGB', (20, 20)), api_key='test-key')

        self.assertEqual(match_catalog.call_count, 2)
        self.assertEqual(
            [(book.detection_index, book.book_index) for book in result.books],
            [(42, 0), (42, 1)],
        )

    @patch('library.services.analysis_pipeline.match_catalog', return_value=NO_CANDIDATE_MATCH)
    @patch('library.services.analysis_pipeline.load_catalog', return_value=(object(),))
    @patch('library.services.analysis_pipeline.read_book_crops')
    @patch('library.services.analysis_pipeline.detect_book_spines')
    def test_partial_hosted_failure_preserves_successful_books(
        self,
        detect_book_spines,
        read_book_crops,
        _load_catalog,
        _match_catalog,
    ):
        detect_book_spines.return_value = detection_result(1, 2)
        read_book_crops.return_value = batch(
            crop_read_result(1, (BookRead(title='The Hobbit'),)),
            failed_crop(2),
        )

        result = analyze_image(Image.new('RGB', (20, 20)), api_key='test-key')

        self.assertEqual(len(result.books), 1)
        self.assertEqual(result.books[0].detection_index, 1)
        self.assertEqual(
            result.warnings,
            ('Detection 2: The hosted reader timed out for this crop.',),
        )

    @patch('library.services.analysis_pipeline.detect_book_spines')
    def test_zero_detections_needs_no_hosted_key(self, detect_book_spines):
        detect_book_spines.return_value = detection_result()

        with patch.dict(os.environ, {}, clear=True):
            result = analyze_image(Image.new('RGB', (20, 20)))

        self.assertEqual(result.hosted_reader.attempted_crops, 0)
        self.assertEqual(result.books, ())
        self.assertEqual(result.warnings, ())
