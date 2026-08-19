from __future__ import annotations

from collections.abc import Iterable

from library.contracts.analysis import (
    OrdinaryReviewGroup,
    ReviewGroup,
    ReviewItem,
    ReviewStatus,
    ReviewVolumeBucket,
    SeriesReviewGroup,
)
from library.services.text_normalization import normalize_author, normalize_text


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


def group_review_items(
    review_items: Iterable[ReviewItem],
) -> tuple[ReviewGroup, ...]:
    """Group review items for display without changing their raw evidence."""
    ordered_items = sorted(review_items, key=_stable_item_key)
    identity_groups: list[list[ReviewItem]] = []

    for item in ordered_items:
        for group in identity_groups:
            if all(_share_book_identity(item, member) for member in group):
                group.append(item)
                break
        else:
            identity_groups.append([item])

    return tuple(_build_group(group) for group in identity_groups)


def _share_book_identity(first: ReviewItem, second: ReviewItem) -> bool:
    first_catalog_id = _suggested_catalog_id(first)
    second_catalog_id = _suggested_catalog_id(second)

    if first_catalog_id and second_catalog_id:
        if first_catalog_id != second_catalog_id:
            return False
        if _title_supports_suggestion(first) and _title_supports_suggestion(second):
            return True

    first_title = normalize_text(
        first.representative.read.title if first.representative.read else None
    )
    second_title = normalize_text(
        second.representative.read.title if second.representative.read else None
    )
    if not first_title or first_title != second_title:
        return False

    first_author = normalize_author(
        first.representative.read.author if first.representative.read else None
    )
    second_author = normalize_author(
        second.representative.read.author if second.representative.read else None
    )
    return not first_author or not second_author or first_author == second_author


def _suggested_catalog_id(item: ReviewItem) -> str | None:
    suggestion = item.representative.suggested_match
    return suggestion.entry.catalog_id if suggestion else None


def _title_supports_suggestion(item: ReviewItem) -> bool:
    read = item.representative.read
    suggestion = item.representative.suggested_match
    title = normalize_text(read.title if read else None)
    if not title or suggestion is None:
        return False
    supported_titles = {
        normalize_text(suggestion.entry.title),
        normalize_text(suggestion.matched_title),
    }
    return title in supported_titles


def _build_group(items: list[ReviewItem]) -> ReviewGroup:
    ordered_items = tuple(sorted(items, key=_representative_key))
    representative = ordered_items[0]
    title, author = _display_identity(representative, ordered_items)
    source_indices, item_count, total_entries, detection_count = _counts(
        ordered_items
    )
    common = {
        'group_id': f'review-group-{representative.item_id}',
        'title': title,
        'author': author,
        'review_status': _group_status(ordered_items),
        'representative_item_id': representative.item_id,
        'source_detection_indices': source_indices,
        'item_count': item_count,
        'total_entries': total_entries,
        'detection_count': detection_count,
    }

    has_explicit_volume = any(_normalized_volume(item) for item in ordered_items)
    if len(ordered_items) < 2 or not has_explicit_volume:
        return OrdinaryReviewGroup(items=ordered_items, **common)

    explicit_buckets: dict[str, list[ReviewItem]] = {}
    unknown_volume_items: list[ReviewItem] = []
    for item in ordered_items:
        volume = _normalized_volume(item)
        if volume:
            explicit_buckets.setdefault(volume, []).append(item)
        else:
            unknown_volume_items.append(item)

    volumes = tuple(
        _build_volume_bucket(explicit_buckets[volume])
        for volume in sorted(explicit_buckets, key=_volume_sort_key)
    )
    return SeriesReviewGroup(
        volumes=volumes,
        unknown_volume_items=tuple(unknown_volume_items),
        **common,
    )


def _build_volume_bucket(items: list[ReviewItem]) -> ReviewVolumeBucket:
    ordered_items = tuple(sorted(items, key=_representative_key))
    representative = ordered_items[0]
    source_indices, item_count, total_entries, detection_count = _counts(
        ordered_items
    )
    volume = representative.representative.read.volume
    assert volume is not None
    return ReviewVolumeBucket(
        bucket_id=f'volume-group-{representative.item_id}',
        volume=volume.strip(),
        representative_item_id=representative.item_id,
        items=ordered_items,
        source_detection_indices=source_indices,
        item_count=item_count,
        total_entries=total_entries,
        detection_count=detection_count,
    )


def _counts(
    items: tuple[ReviewItem, ...],
) -> tuple[tuple[int, ...], int, int, int]:
    source_indices = tuple(
        sorted(
            {
                detection_index
                for item in items
                for detection_index in item.source_detection_indices
            }
        )
    )
    return (
        source_indices,
        len(items),
        sum(item.duplicate_count for item in items),
        len(source_indices),
    )


def _display_identity(
    representative: ReviewItem,
    items: tuple[ReviewItem, ...],
) -> tuple[str | None, str | None]:
    suggestion = representative.representative.suggested_match
    read = representative.representative.read
    title = suggestion.entry.title if suggestion else read.title if read else None
    author = suggestion.entry.author if suggestion else read.author if read else None

    if not title:
        title = next(
            (
                item.representative.read.title
                for item in items
                if item.representative.read and item.representative.read.title
            ),
            None,
        )
    if not author:
        author = next(
            (
                item.representative.read.author
                for item in items
                if item.representative.read and item.representative.read.author
            ),
            None,
        )
    return title, author


def _group_status(items: tuple[ReviewItem, ...]) -> ReviewStatus:
    statuses = {item.representative.review.status for item in items}
    if statuses == {'high_confidence'}:
        return 'high_confidence'
    if statuses == {'unmatched'}:
        return 'unmatched'
    return 'review_required'


def _normalized_volume(item: ReviewItem) -> str:
    read = item.representative.read
    return normalize_text(read.volume if read else None)


def _volume_sort_key(volume: str) -> tuple[object, ...]:
    if volume.isdecimal():
        return (0, int(volume), volume)
    return (1, volume)


def _stable_item_key(item: ReviewItem) -> tuple[object, ...]:
    book = item.representative
    return (book.detection_index, book.book_index, item.item_id)


def _representative_key(item: ReviewItem) -> tuple[object, ...]:
    book = item.representative
    read = book.read
    suggestion = book.suggested_match
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
    return (
        _STATUS_RANK[book.review.status],
        _READABILITY_RANK.get(read.readability if read else None, 3),
        0 if suggestion is not None else 1,
        0 if read and normalize_text(read.title) else 1,
        0 if read and normalize_author(read.author) else 1,
        -title_score,
        -combined_score,
        book.detection_index,
        book.book_index,
        item.item_id,
    )
