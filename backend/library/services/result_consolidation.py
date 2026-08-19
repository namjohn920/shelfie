from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from library.contracts.analysis import (
    AnalyzedBook,
    BoundingBox,
    ReviewItem,
    SpineDetection,
)
from library.services.text_normalization import normalize_text


DUPLICATE_IOU_THRESHOLD = 0.35
DUPLICATE_CONTAINMENT_THRESHOLD = 0.70
DUPLICATE_STRONG_TITLE_SCORE = 90.0

_STATUS_RANK = {
    'high_confidence': 0,
    'review_required': 1,
    'unmatched': 2,
}
_READABILITY_RANK = {
    'readable': 0,
    'partial': 1,
    'unreadable': 2,
}


def consolidate_review_items(
    books: Iterable[AnalyzedBook],
    detections: Iterable[SpineDetection],
) -> tuple[ReviewItem, ...]:
    """Build a smaller traceable review list without changing raw book evidence."""
    ordered_books = sorted(
        books,
        key=lambda book: (book.detection_index, book.book_index),
    )
    boxes = {
        detection.detection_index: detection.box for detection in detections
    }
    groups: list[list[AnalyzedBook]] = []

    for book in ordered_books:
        for group in groups:
            if all(_can_merge(book, member, boxes) for member in group):
                group.append(book)
                break
        else:
            groups.append([book])

    review_items: list[ReviewItem] = []
    for group in groups:
        representative = _representative_with_preserved_volume(group)
        source_indices = tuple(
            sorted({book.detection_index for book in group})
        )
        review_items.append(
            ReviewItem(
                item_id=(
                    f'review-{representative.detection_index}-'
                    f'{representative.book_index}'
                ),
                representative=representative,
                source_detection_indices=source_indices,
                duplicate_count=len(group),
            )
        )
    return tuple(review_items)


def _can_merge(
    first: AnalyzedBook,
    second: AnalyzedBook,
    boxes: dict[int, BoundingBox],
) -> bool:
    first_box = boxes.get(first.detection_index)
    second_box = boxes.get(second.detection_index)
    if (
        first.detection_index == second.detection_index
        or first_box is None
        or second_box is None
        or not _boxes_are_spatial_duplicates(first_box, second_box)
        or not _volumes_are_compatible(first, second)
    ):
        return False

    first_title = normalize_text(first.read.title if first.read else None)
    second_title = normalize_text(second.read.title if second.read else None)
    same_extracted_title = bool(first_title and first_title == second_title)
    return same_extracted_title or _same_strong_catalog_identity(first, second)


def _volumes_are_compatible(first: AnalyzedBook, second: AnalyzedBook) -> bool:
    first_volume = normalize_text(first.read.volume if first.read else None)
    second_volume = normalize_text(second.read.volume if second.read else None)
    if not first_volume and not second_volume:
        return True
    if not first_volume or not second_volume:
        return True
    return first_volume == second_volume


def _same_strong_catalog_identity(
    first: AnalyzedBook,
    second: AnalyzedBook,
) -> bool:
    first_candidate = first.match.best_candidate if first.match else None
    second_candidate = second.match.best_candidate if second.match else None
    return bool(
        first.review.status == 'high_confidence'
        and second.review.status == 'high_confidence'
        and first_candidate is not None
        and second_candidate is not None
        and first_candidate.entry.catalog_id == second_candidate.entry.catalog_id
        and first.match is not None
        and second.match is not None
        and first.match.title_score is not None
        and second.match.title_score is not None
        and first.match.title_score >= DUPLICATE_STRONG_TITLE_SCORE
        and second.match.title_score >= DUPLICATE_STRONG_TITLE_SCORE
    )


def _boxes_are_spatial_duplicates(
    first: BoundingBox,
    second: BoundingBox,
) -> bool:
    intersection = _intersection_area(first, second)
    union = first.area + second.area - intersection
    intersection_over_union = intersection / union if union > 0.0 else 0.0
    smaller_area = min(first.area, second.area)
    intersection_over_smaller_area = (
        intersection / smaller_area if smaller_area > 0.0 else 0.0
    )
    return (
        intersection_over_union >= DUPLICATE_IOU_THRESHOLD
        or intersection_over_smaller_area >= DUPLICATE_CONTAINMENT_THRESHOLD
    )


def _intersection_area(first: BoundingBox, second: BoundingBox) -> float:
    intersection_width = max(
        0.0,
        min(first.right, second.right) - max(first.left, second.left),
    )
    intersection_height = max(
        0.0,
        min(first.bottom, second.bottom) - max(first.top, second.top),
    )
    return intersection_width * intersection_height


def _representative_with_preserved_volume(
    group: list[AnalyzedBook],
) -> AnalyzedBook:
    representative = min(group, key=_representative_key)
    if representative.read is None or normalize_text(representative.read.volume):
        return representative

    explicit_volume_sources = [
        book
        for book in group
        if book.read is not None and normalize_text(book.read.volume)
    ]
    if not explicit_volume_sources:
        return representative

    volume_source = min(explicit_volume_sources, key=_representative_key)
    return replace(
        representative,
        read=replace(representative.read, volume=volume_source.read.volume),
    )


def _representative_key(book: AnalyzedBook) -> tuple[object, ...]:
    title_score = (
        book.match.title_score
        if book.match and book.match.title_score is not None
        else -1.0
    )
    combined_score = (
        book.match.combined_score
        if book.match and book.match.combined_score is not None
        else -1.0
    )
    readability = book.read.readability if book.read else None
    has_explicit_volume = bool(book.read and normalize_text(book.read.volume))
    return (
        _STATUS_RANK[book.review.status],
        _READABILITY_RANK.get(readability, 3),
        0 if has_explicit_volume else 1,
        0 if book.suggested_match is not None else 1,
        -title_score,
        -combined_score,
        book.detection_index,
        book.book_index,
    )
