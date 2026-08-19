from django.test import SimpleTestCase

from library.contracts.analysis import (
    AnalyzedBook,
    BookRead,
    BoundingBox,
    CatalogEntry,
    MatchCandidate,
    MatchResult,
    ReviewDecision,
    SpineDetection,
)
from library.services.result_consolidation import consolidate_review_items


def detection(index: int, box: BoundingBox) -> SpineDetection:
    return SpineDetection(index, box, 0.9)


def match(score: float = 100.0, title_score: float = 100.0) -> MatchResult:
    candidate = MatchCandidate(
        CatalogEntry('CAT011', 'The Fellowship of the Ring', 'J. R. R. Tolkien'),
        'The Fellowship of the Ring',
        'J. R. R. Tolkien',
        'canonical',
        title_score,
        100.0,
        score,
    )
    return MatchResult(
        candidate,
        None,
        title_score,
        100.0,
        score,
        score - 20.0,
        20.0,
        60.0,
    )


def analyzed(
    detection_index: int,
    title: str,
    *,
    book_index: int = 0,
    volume: str | None = None,
    status='review_required',
    readability='partial',
    score: float = 80.0,
    title_score: float = 100.0,
    has_suggestion: bool = False,
) -> AnalyzedBook:
    matched = match(score, title_score) if status == 'high_confidence' else None
    return AnalyzedBook(
        detection_index=detection_index,
        book_index=book_index,
        read=BookRead(title, volume=volume, readability=readability),
        match=matched,
        review=ReviewDecision(status, (status,)),
        suggested_match=(
            matched.best_candidate if matched and has_suggestion else None
        ),
    )


OVERLAPPING_BOXES = (
    BoundingBox(0, 0, 100, 100),
    BoundingBox(20, 0, 120, 100),
)
THIN_NESTED_BOXES = (
    BoundingBox(20, 0, 30, 100),
    BoundingBox(0, 0, 40, 100),
)


class ResultConsolidationTests(SimpleTestCase):
    def test_thin_nested_same_title_merges_with_low_iou_high_containment(self):
        books = (analyzed(1, 'The Hobbit'), analyzed(2, 'the hobbit'))
        detections = (
            detection(1, THIN_NESTED_BOXES[0]),
            detection(2, THIN_NESTED_BOXES[1]),
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_detection_indices, (1, 2))
        self.assertEqual(items[0].duplicate_count, 2)

    def test_non_overlapping_same_title_stays_as_two_physical_copies(self):
        books = (analyzed(1, 'The Hobbit'), analyzed(2, 'The Hobbit'))
        detections = (
            detection(1, BoundingBox(0, 0, 100, 100)),
            detection(2, BoundingBox(200, 0, 300, 100)),
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(len(items), 2)

    def test_thin_nested_different_titles_stay_separate(self):
        books = (analyzed(1, 'The Hobbit'), analyzed(2, 'Dune'))
        detections = (
            detection(1, THIN_NESTED_BOXES[0]),
            detection(2, THIN_NESTED_BOXES[1]),
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(len(items), 2)

    def test_same_high_confidence_catalog_identity_can_merge_title_variants(self):
        books = (
            analyzed(
                1,
                'Fellowship Ring',
                status='high_confidence',
                readability='readable',
                score=100.0,
            ),
            analyzed(
                2,
                'The Fellowship of the Ring',
                status='high_confidence',
                readability='readable',
                score=100.0,
            ),
        )
        detections = (
            detection(1, OVERLAPPING_BOXES[0]),
            detection(2, OVERLAPPING_BOXES[1]),
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].duplicate_count, 2)

    def test_same_catalog_id_with_weak_title_evidence_does_not_merge(self):
        books = (
            analyzed(
                1,
                'Fellowship Ring',
                status='high_confidence',
                readability='readable',
                score=100.0,
                title_score=89.9,
            ),
            analyzed(
                2,
                'The Fellowship of the Ring',
                status='high_confidence',
                readability='readable',
                score=100.0,
                title_score=89.9,
            ),
        )
        detections = (
            detection(1, OVERLAPPING_BOXES[0]),
            detection(2, OVERLAPPING_BOXES[1]),
        )

        self.assertEqual(len(consolidate_review_items(books, detections)), 2)

    def test_same_land_volume_and_overlapping_geometry_merge(self):
        books = (
            analyzed(1, '土地', volume='21'),
            analyzed(2, '土地', volume='21'),
        )
        detections = (
            detection(1, OVERLAPPING_BOXES[0]),
            detection(2, OVERLAPPING_BOXES[1]),
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].representative.read.volume, '21')

    def test_different_explicit_volumes_are_never_merged(self):
        books = (
            analyzed(1, '土地', volume='20'),
            analyzed(2, '土地', volume='21'),
        )
        detections = (
            detection(1, OVERLAPPING_BOXES[0]),
            detection(2, OVERLAPPING_BOXES[1]),
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(len(items), 2)

    def test_missing_volume_merges_with_explicit_and_preserves_explicit_volume(self):
        books = (
            analyzed(1, '土地', readability='readable'),
            analyzed(2, '土地', volume='21', readability='partial'),
        )
        detections = (
            detection(1, OVERLAPPING_BOXES[0]),
            detection(2, OVERLAPPING_BOXES[1]),
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].representative.detection_index, 1)
        self.assertEqual(items[0].representative.read.volume, '21')

    def test_multi_book_crop_keeps_distinct_second_book(self):
        books = (
            analyzed(1, 'Book X', book_index=0),
            analyzed(1, 'Book Y', book_index=1),
            analyzed(2, 'Book X'),
        )
        detections = (
            detection(1, OVERLAPPING_BOXES[0]),
            detection(2, OVERLAPPING_BOXES[1]),
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(len(items), 2)
        self.assertEqual(
            sorted(item.representative.read.title for item in items),
            ['Book X', 'Book Y'],
        )
        book_x = next(
            item for item in items if item.representative.read.title == 'Book X'
        )
        self.assertEqual(book_x.source_detection_indices, (1, 2))
        self.assertEqual(book_x.duplicate_count, 2)

    def test_representative_selection_is_deterministic_by_evidence_quality(self):
        books = (
            analyzed(1, 'The Fellowship of the Ring', score=100.0),
            analyzed(
                2,
                'The Fellowship of the Ring',
                status='high_confidence',
                readability='readable',
                score=95.0,
            ),
        )
        detections = (
            detection(1, OVERLAPPING_BOXES[0]),
            detection(2, OVERLAPPING_BOXES[1]),
        )

        forward = consolidate_review_items(books, detections)
        reversed_input = consolidate_review_items(reversed(books), detections)

        self.assertEqual(forward[0].representative.detection_index, 2)
        self.assertEqual(
            forward[0].representative,
            reversed_input[0].representative,
        )

    def test_higher_match_score_precedes_detection_index_tiebreak(self):
        books = (
            analyzed(
                1,
                'The Fellowship of the Ring',
                status='high_confidence',
                readability='readable',
                score=92.0,
            ),
            analyzed(
                2,
                'The Fellowship of the Ring',
                status='high_confidence',
                readability='readable',
                score=99.0,
            ),
        )
        detections = (
            detection(1, OVERLAPPING_BOXES[0]),
            detection(2, OVERLAPPING_BOXES[1]),
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(items[0].representative.detection_index, 2)

    def test_visible_suggestion_precedes_scores_and_detection_index(self):
        books = (
            analyzed(
                1,
                'The Fellowship of the Ring',
                status='high_confidence',
                readability='readable',
                score=100.0,
            ),
            analyzed(
                2,
                'The Fellowship of the Ring',
                status='high_confidence',
                readability='readable',
                score=95.0,
                has_suggestion=True,
            ),
        )
        detections = (
            detection(1, OVERLAPPING_BOXES[0]),
            detection(2, OVERLAPPING_BOXES[1]),
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(items[0].representative.detection_index, 2)

    def test_explicit_volume_precedes_suggestion_and_scores(self):
        books = (
            analyzed(
                1,
                '土地',
                status='high_confidence',
                readability='readable',
                score=100.0,
                has_suggestion=True,
            ),
            analyzed(
                2,
                '土地',
                volume='21',
                status='high_confidence',
                readability='readable',
                score=92.0,
            ),
        )
        detections = (
            detection(1, OVERLAPPING_BOXES[0]),
            detection(2, OVERLAPPING_BOXES[1]),
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(items[0].representative.detection_index, 2)
        self.assertEqual(items[0].representative.read.volume, '21')

    def test_title_score_precedes_combined_score_then_lower_detection_index(self):
        books = (
            analyzed(
                1,
                'The Fellowship of the Ring',
                status='high_confidence',
                readability='readable',
                score=100.0,
                title_score=90.0,
            ),
            analyzed(
                2,
                'The Fellowship of the Ring',
                status='high_confidence',
                readability='readable',
                score=95.0,
                title_score=98.0,
            ),
            analyzed(
                3,
                'The Fellowship of the Ring',
                status='high_confidence',
                readability='readable',
                score=95.0,
                title_score=98.0,
            ),
        )
        detections = tuple(
            detection(index, BoundingBox(0, 0, 100, 100))
            for index in (1, 2, 3)
        )

        items = consolidate_review_items(books, detections)

        self.assertEqual(items[0].representative.detection_index, 2)
