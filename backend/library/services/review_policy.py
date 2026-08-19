from __future__ import annotations

from library.contracts.analysis import (
    BookRead,
    MatchCandidate,
    MatchResult,
    ReaderStatus,
    RegionType,
    ReviewDecision,
)


# Conservative initial policy from current shelf evidence. These are adjustment points,
# not calibrated production truth.
HIGH_CONFIDENCE_SCORE = 90.0
HIGH_CONFIDENCE_MARGIN = 10.0
VISIBLE_SUGGESTION_SCORE = 80.0
VISIBLE_SUGGESTION_TITLE_SCORE = 80.0


def user_visible_suggestion(
    book_read: BookRead | None,
    match: MatchResult | None,
) -> MatchCandidate | None:
    """Return the raw best candidate only when it is useful product guidance."""
    if (
        book_read is None
        or book_read.readability == 'unreadable'
        or match is None
        or match.best_candidate is None
        or match.combined_score is None
        or match.combined_score < VISIBLE_SUGGESTION_SCORE
    ):
        return None
    if (
        _has_usable_text(book_read.title)
        and (
            match.title_score is None
            or match.title_score < VISIBLE_SUGGESTION_TITLE_SCORE
        )
    ):
        return None
    return match.best_candidate


def decide_review(
    book_read: BookRead | None,
    match: MatchResult | None,
    *,
    reader_status: ReaderStatus = 'ok',
    region_type: RegionType | None = None,
) -> ReviewDecision:
    """Turn reader quality and matcher evidence into a product review status."""
    if reader_status == 'error':
        return ReviewDecision('unmatched', ('read_failed',))
    if region_type == 'non_book':
        return ReviewDecision('unmatched', ('non_book',))
    if book_read is None:
        return ReviewDecision('unmatched', ('no_evidence',))
    if book_read.readability == 'unreadable':
        return ReviewDecision('unmatched', ('unreadable',))
    if not _has_usable_text(book_read.title) and not _has_usable_text(book_read.author):
        return ReviewDecision('unmatched', ('no_evidence',))
    if match is None or match.best_candidate is None:
        return ReviewDecision('unmatched', ('no_candidate',))

    score_is_high = (
        match.combined_score is not None
        and match.combined_score >= HIGH_CONFIDENCE_SCORE
    )
    margin_is_high = (
        match.margin is not None and match.margin >= HIGH_CONFIDENCE_MARGIN
    )
    if book_read.readability == 'readable' and score_is_high and margin_is_high:
        return ReviewDecision('high_confidence', ('high_confidence',))

    reasons: list[str] = []
    if book_read.readability == 'partial':
        reasons.append('partial_read')
    if not score_is_high:
        reasons.append('low_score')
    if not margin_is_high:
        reasons.append('small_margin')
    if user_visible_suggestion(book_read, match) is None:
        reasons.append('candidate_not_reliable_enough_to_show')
    return ReviewDecision('review_required', tuple(reasons))


def _has_usable_text(value: str | None) -> bool:
    return bool(value and value.strip())
