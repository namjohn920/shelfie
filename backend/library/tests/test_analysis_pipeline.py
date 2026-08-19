import os
from unittest.mock import patch

from django.test import SimpleTestCase
from PIL import Image

from library.contracts.analysis import (
    BookRead,
    BoundingBox,
    CatalogEntry,
    CropReadResult,
    DetectionResult,
    DetectorTiming,
    MatchResult,
    MatchCandidate,
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
    region_type=None,
    region_text=None,
    readability=None,
) -> CropReadResult:
    if region_type is None:
        region_type = 'multiple_books' if crop_type == 'multiple_books' else 'book'
    return CropReadResult(
        detection_index=detection_index,
        crop_type=crop_type,
        region_type=region_type,
        region_text=region_text,
        readability=(
            readability
            if readability is not None
            else books[0].readability if books else 'unreadable'
        ),
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


def catalog_match(
    *,
    score: float,
    title_score: float,
    margin: float,
    catalog_id: str = 'CAT086',
    title: str = 'The Lean Startup',
    author: str = 'Eric Ries',
) -> MatchResult:
    candidate = MatchCandidate(
        entry=CatalogEntry(catalog_id, title, author),
        matched_title=title,
        matched_author=author,
        title_evidence='canonical',
        title_score=title_score,
        author_score=100.0,
        combined_score=score,
    )
    return MatchResult(
        best_candidate=candidate,
        second_candidate=None,
        title_score=title_score,
        author_score=100.0,
        combined_score=score,
        second_score=score - margin,
        margin=margin,
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
        self.assertEqual(result.books[0].review.status, 'unmatched')
        self.assertEqual(result.books[0].review.reasons, ('no_candidate',))

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
        self.assertEqual(result.books[0].review.status, 'unmatched')
        self.assertEqual(result.books[0].review.reasons, ('unreadable',))

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
    def test_partial_hosted_failure_preserves_success_and_surfaces_failure(
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

        self.assertEqual(len(result.books), 2)
        self.assertEqual(result.books[0].detection_index, 1)
        self.assertEqual(result.books[1].detection_index, 2)
        self.assertIsNone(result.books[1].read)
        self.assertEqual(result.books[1].review.status, 'unmatched')
        self.assertEqual(result.books[1].review.reasons, ('read_failed',))
        self.assertEqual(
            result.warnings,
            ('Detection 2: The hosted reader timed out for this crop.',),
        )

    @patch('library.services.analysis_pipeline.read_book_crops')
    @patch('library.services.analysis_pipeline.detect_book_spines')
    def test_unreadable_crop_without_book_entries_reaches_review(
        self,
        detect_book_spines,
        read_book_crops,
    ):
        detect_book_spines.return_value = detection_result(1)
        read_book_crops.return_value = batch(crop_read_result(1, ()))

        result = analyze_image(Image.new('RGB', (20, 20)), api_key='test-key')

        self.assertEqual(len(result.books), 1)
        self.assertEqual(result.books[0].read.readability, 'unreadable')
        self.assertEqual(result.books[0].review.status, 'unmatched')
        self.assertEqual(result.books[0].review.reasons, ('unreadable',))

    @patch('library.services.analysis_pipeline.detect_book_spines')
    def test_zero_detections_needs_no_hosted_key(self, detect_book_spines):
        detect_book_spines.return_value = detection_result()

        with patch.dict(os.environ, {}, clear=True):
            result = analyze_image(Image.new('RGB', (20, 20)))

        self.assertEqual(result.hosted_reader.attempted_crops, 0)
        self.assertEqual(result.books, ())
        self.assertEqual(result.review_items, ())
        self.assertEqual(result.review_groups, ())
        self.assertEqual(result.crop_thumbnails, ())
        self.assertEqual(result.warnings, ())

    @patch('library.services.analysis_pipeline.match_catalog')
    @patch('library.services.analysis_pipeline.load_catalog')
    @patch('library.services.analysis_pipeline.read_book_crops')
    @patch('library.services.analysis_pipeline.detect_book_spines')
    def test_non_book_skips_matching_and_remains_reviewable(
        self,
        detect_book_spines,
        read_book_crops,
        load_catalog,
        match_catalog,
    ):
        detect_book_spines.return_value = detection_result(28)
        read_book_crops.return_value = batch(
            crop_read_result(
                28,
                (),
                crop_type=None,
                region_type='non_book',
                region_text='DURABLE AVERY',
                readability='readable',
            )
        )

        result = analyze_image(Image.new('RGB', (20, 20)), api_key='test-key')

        load_catalog.assert_not_called()
        match_catalog.assert_not_called()
        self.assertEqual(result.books[0].region_type, 'non_book')
        self.assertEqual(result.books[0].region_text, 'DURABLE AVERY')
        self.assertEqual(result.books[0].review.status, 'unmatched')
        self.assertEqual(result.books[0].review.reasons, ('non_book',))
        self.assertEqual(result.review_items[0].duplicate_count, 1)

    @patch('library.services.analysis_pipeline.match_catalog')
    @patch('library.services.analysis_pipeline.load_catalog', return_value=(object(),))
    @patch('library.services.analysis_pipeline.read_book_crops')
    @patch('library.services.analysis_pipeline.detect_book_spines')
    def test_raw_match_is_preserved_when_weak_candidate_is_hidden(
        self,
        detect_book_spines,
        read_book_crops,
        _load_catalog,
        match_catalog,
    ):
        book_read = BookRead('GETTING STARTED IN CHART PATTERNS', 'BULKOWSKI')
        weak_match = catalog_match(
            score=69.3,
            title_score=56.1,
            margin=0.9,
            catalog_id='CAT082',
            title='Quiet',
            author='Susan Cain',
        )
        detect_book_spines.return_value = detection_result(34)
        read_book_crops.return_value = batch(crop_read_result(34, (book_read,)))
        match_catalog.return_value = weak_match

        result = analyze_image(Image.new('RGB', (20, 20)), api_key='test-key')

        self.assertIs(result.books[0].match, weak_match)
        self.assertIsNone(result.books[0].suggested_match)
        self.assertIn(
            'candidate_not_reliable_enough_to_show',
            result.books[0].review.reasons,
        )
        self.assertIs(result.review_items[0].representative.match, weak_match)

    @patch('library.services.analysis_pipeline.match_catalog')
    @patch('library.services.analysis_pipeline.load_catalog', return_value=(object(),))
    @patch('library.services.analysis_pipeline.read_book_crops')
    @patch('library.services.analysis_pipeline.detect_book_spines')
    def test_lean_startup_remains_high_confidence_with_visible_suggestion(
        self,
        detect_book_spines,
        read_book_crops,
        _load_catalog,
        match_catalog,
    ):
        book_read = BookRead('The Lean Startup', 'Eric Ries')
        strong_match = catalog_match(score=100.0, title_score=100.0, margin=26.5)
        detect_book_spines.return_value = detection_result(42)
        read_book_crops.return_value = batch(crop_read_result(42, (book_read,)))
        match_catalog.return_value = strong_match

        result = analyze_image(Image.new('RGB', (20, 20)), api_key='test-key')

        self.assertEqual(result.books[0].review.status, 'high_confidence')
        self.assertEqual(
            result.books[0].suggested_match.entry.catalog_id,
            'CAT086',
        )
        self.assertEqual(len(result.review_groups), 1)
        self.assertEqual(result.review_groups[0].representative_item_id, 'review-42-0')
        self.assertEqual(len(result.crop_thumbnails), 1)
