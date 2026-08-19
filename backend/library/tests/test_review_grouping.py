from django.test import SimpleTestCase

from library.contracts.analysis import (
    AnalyzedBook,
    BookRead,
    CatalogEntry,
    MatchCandidate,
    MatchResult,
    OrdinaryReviewGroup,
    ReviewDecision,
    ReviewItem,
    SeriesReviewGroup,
)
from library.services.review_grouping import group_review_items


def review_item(
    detection_index: int,
    title: str,
    author: str | None,
    *,
    volume: str | None = None,
    item_id: str | None = None,
    status='review_required',
    catalog_id: str | None = None,
    catalog_title: str | None = None,
    source_detection_indices: tuple[int, ...] | None = None,
    duplicate_count: int = 1,
) -> ReviewItem:
    suggestion = None
    match = None
    if catalog_id:
        candidate_title = catalog_title or title
        suggestion = MatchCandidate(
            entry=CatalogEntry(
                catalog_id,
                candidate_title,
                author or 'Canonical Author',
            ),
            matched_title=title,
            matched_author=author,
            title_evidence='canonical',
            title_score=100.0,
            author_score=100.0,
            combined_score=100.0,
        )
        match = MatchResult(
            best_candidate=suggestion,
            second_candidate=None,
            title_score=100.0,
            author_score=100.0,
            combined_score=100.0,
            second_score=70.0,
            margin=30.0,
            candidate_floor=60.0,
        )
    analyzed = AnalyzedBook(
        detection_index=detection_index,
        book_index=0,
        read=BookRead(
            title=title,
            author=author,
            volume=volume,
            readability='readable',
        ),
        match=match,
        review=ReviewDecision(status, (status,)),
        suggested_match=suggestion,
        region_type='book',
    )
    return ReviewItem(
        item_id or f'review-{detection_index}-0',
        analyzed,
        source_detection_indices or (detection_index,),
        duplicate_count,
    )


class ReviewGroupingTests(SimpleTestCase):
    def test_three_explicit_volumes_form_one_sorted_series(self):
        items = (
            review_item(1, '土地', '박경리', volume='12'),
            review_item(2, '土地', '박경리', volume='10'),
            review_item(3, '土地', '박경리', volume='11'),
        )

        groups = group_review_items(items)

        self.assertEqual(len(groups), 1)
        self.assertIsInstance(groups[0], SeriesReviewGroup)
        self.assertEqual(
            [bucket.volume for bucket in groups[0].volumes],
            ['10', '11', '12'],
        )

    def test_repeated_explicit_volume_uses_one_bucket_and_two_detections(self):
        items = (
            review_item(1, '土地', '박경리', volume='10'),
            review_item(2, '土地', '박경리', volume='10'),
        )

        group = group_review_items(items)[0]

        self.assertIsInstance(group, SeriesReviewGroup)
        self.assertEqual(len(group.volumes), 1)
        self.assertEqual(group.volumes[0].detection_count, 2)
        self.assertEqual(group.volumes[0].item_count, 2)

    def test_different_explicit_volumes_remain_separate_buckets(self):
        items = (
            review_item(1, '土地', '박경리', volume='10'),
            review_item(2, '土地', '박경리', volume='11'),
        )

        group = group_review_items(items)[0]

        self.assertIsInstance(group, SeriesReviewGroup)
        self.assertEqual(len(group.volumes), 2)
        self.assertEqual(group.volumes[0].items[0].item_id, 'review-1-0')
        self.assertEqual(group.volumes[1].items[0].item_id, 'review-2-0')

    def test_non_numeric_volumes_use_lexical_order_after_numeric_values(self):
        items = (
            review_item(1, '土地', '박경리', volume='Special B'),
            review_item(2, '土地', '박경리', volume='2'),
            review_item(3, '土地', '박경리', volume='Special A'),
        )

        group = group_review_items(items)[0]

        self.assertEqual(
            [bucket.volume for bucket in group.volumes],
            ['2', 'Special A', 'Special B'],
        )

    def test_missing_volume_stays_in_unknown_section_of_series(self):
        explicit = review_item(1, '土地', '박경리', volume='10')
        unknown = review_item(2, '土地', '박경리')

        group = group_review_items((explicit, unknown))[0]

        self.assertIsInstance(group, SeriesReviewGroup)
        self.assertEqual(group.volumes[0].items, (explicit,))
        self.assertEqual(group.unknown_volume_items, (unknown,))
        self.assertIsNone(group.unknown_volume_items[0].representative.read.volume)

    def test_two_unknown_volume_items_remain_individually_accessible(self):
        items = (
            review_item(1, '土地', '박경리', volume='10'),
            review_item(2, '土地', '박경리'),
            review_item(3, '土地', '박경리'),
        )

        group = group_review_items(items)[0]

        self.assertIsInstance(group, SeriesReviewGroup)
        self.assertEqual(
            [item.item_id for item in group.unknown_volume_items],
            ['review-2-0', 'review-3-0'],
        )

    def test_numeric_title_without_volume_is_not_a_series(self):
        items = (
            review_item(1, '1984', 'George Orwell'),
            review_item(2, '1984', 'George Orwell'),
        )

        group = group_review_items(items)[0]

        self.assertIsInstance(group, OrdinaryReviewGroup)
        self.assertEqual(group.item_count, 2)

    def test_ordinary_fellowship_duplicates_form_one_group(self):
        items = (
            review_item(1, 'The Fellowship of the Ring', 'J. R. R. Tolkien'),
            review_item(2, 'the fellowship of the ring', 'J.R.R. Tolkien'),
        )

        groups = group_review_items(items)

        self.assertEqual(len(groups), 1)
        self.assertIsInstance(groups[0], OrdinaryReviewGroup)
        self.assertEqual(groups[0].detection_count, 2)
        self.assertEqual(groups[0].total_entries, 2)

    def test_conflicting_authors_separate_without_shared_strong_catalog(self):
        items = (
            review_item(1, 'Shared Title', 'First Author'),
            review_item(2, 'Shared Title', 'Second Author'),
        )

        self.assertEqual(len(group_review_items(items)), 2)

    def test_shared_supported_catalog_identity_can_resolve_author_conflict(self):
        items = (
            review_item(
                1,
                'Shared Title',
                'First Author',
                catalog_id='CAT999',
            ),
            review_item(
                2,
                'Shared Title',
                'Second Author',
                catalog_id='CAT999',
            ),
        )

        self.assertEqual(len(group_review_items(items)), 1)

    def test_conflicting_visible_catalog_identities_remain_separate(self):
        items = (
            review_item(1, 'Shared Title', 'Same Author', catalog_id='CAT001'),
            review_item(2, 'Shared Title', 'Same Author', catalog_id='CAT002'),
        )

        self.assertEqual(len(group_review_items(items)), 2)

    def test_unrelated_books_remain_separate(self):
        items = (
            review_item(1, 'The Fellowship of the Ring', 'J. R. R. Tolkien'),
            review_item(2, 'The Hobbit', 'J. R. R. Tolkien'),
        )

        self.assertEqual(len(group_review_items(items)), 2)

    def test_raw_review_items_are_not_mutated(self):
        items = (
            review_item(1, '土地', '박경리', volume='10'),
            review_item(2, '土地', '박경리'),
        )
        before = [item.as_dict() for item in items]

        group_review_items(items)

        self.assertEqual([item.as_dict() for item in items], before)

    def test_source_indices_and_raw_ids_remain_traceable(self):
        items = (
            review_item(
                4,
                'The Fellowship of the Ring',
                'J. R. R. Tolkien',
                item_id='raw-review-a',
                source_detection_indices=(2, 4),
                duplicate_count=2,
            ),
            review_item(
                8,
                'The Fellowship of the Ring',
                'J. R. R. Tolkien',
                item_id='raw-review-b',
            ),
        )

        group = group_review_items(items)[0]

        self.assertEqual(group.source_detection_indices, (2, 4, 8))
        self.assertEqual(group.detection_count, 3)
        self.assertEqual(group.total_entries, 3)
        self.assertEqual([item.item_id for item in group.items], [
            'raw-review-a',
            'raw-review-b',
        ])

    def test_representative_selection_is_deterministic(self):
        items = (
            review_item(9, 'Dune', 'Frank Herbert'),
            review_item(
                3,
                'Dune',
                'Frank Herbert',
                status='high_confidence',
                catalog_id='CAT003',
            ),
        )

        forward = group_review_items(items)[0]
        reversed_input = group_review_items(reversed(items))[0]

        self.assertEqual(forward.representative_item_id, 'review-3-0')
        self.assertEqual(
            forward.representative_item_id,
            reversed_input.representative_item_id,
        )
