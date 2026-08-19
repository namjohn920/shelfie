from django.test import SimpleTestCase

from library.contracts.analysis import (
    BookRead,
    CatalogEntry,
    MatchCandidate,
    MatchResult,
)
from library.services.review_policy import decide_review, user_visible_suggestion


def match_result(
    score: float,
    margin: float,
    *,
    title_score: float | None = None,
) -> MatchResult:
    resolved_title_score = score if title_score is None else title_score
    candidate = MatchCandidate(
        entry=CatalogEntry('CAT086', 'The Lean Startup', 'Eric Ries'),
        matched_title='The Lean Startup',
        matched_author='Eric Ries',
        title_evidence='canonical',
        title_score=resolved_title_score,
        author_score=score,
        combined_score=score,
    )
    return MatchResult(
        best_candidate=candidate,
        second_candidate=None,
        title_score=resolved_title_score,
        author_score=score,
        combined_score=score,
        second_score=score - margin,
        margin=margin,
        candidate_floor=60.0,
    )


class ReviewPolicyTests(SimpleTestCase):
    def test_readable_strong_separated_match_is_high_confidence(self):
        decision = decide_review(
            BookRead('The Lean Startup', 'Eric Ries'),
            match_result(100.0, 26.5),
        )

        self.assertEqual(decision.status, 'high_confidence')
        self.assertEqual(decision.reasons, ('high_confidence',))

    def test_score_90_is_the_inclusive_high_confidence_boundary(self):
        read = BookRead('The Lean Startup', 'Eric Ries')

        at_threshold = decide_review(
            read,
            match_result(90.0, 10.0),
        )
        below_threshold = decide_review(
            read,
            match_result(89.9, 10.0),
        )

        self.assertEqual(at_threshold.status, 'high_confidence')
        self.assertEqual(below_threshold.status, 'review_required')
        self.assertIn('low_score', below_threshold.reasons)

    def test_margin_10_is_the_inclusive_high_confidence_boundary(self):
        read = BookRead('The Lean Startup', 'Eric Ries')

        at_threshold = decide_review(
            read,
            match_result(90.0, 10.0),
        )
        below_threshold = decide_review(
            read,
            match_result(90.0, 9.9),
        )

        self.assertEqual(at_threshold.status, 'high_confidence')
        self.assertEqual(below_threshold.status, 'review_required')
        self.assertIn('small_margin', below_threshold.reasons)

    def test_low_score_and_small_margin_require_review(self):
        decision = decide_review(
            BookRead('HOLY BIBLE CONCORDANCE'),
            match_result(67.5, 7.5),
        )

        self.assertEqual(decision.status, 'review_required')
        self.assertEqual(
            decision.reasons,
            (
                'low_score',
                'small_margin',
                'candidate_not_reliable_enough_to_show',
            ),
        )

    def test_high_score_with_small_margin_requires_review(self):
        decision = decide_review(
            BookRead('Pride and Prejudice', 'Jane Austen'),
            match_result(100.0, 0.0),
        )

        self.assertEqual(decision.status, 'review_required')
        self.assertEqual(decision.reasons, ('small_margin',))

    def test_partial_read_with_strong_match_requires_review(self):
        decision = decide_review(
            BookRead(
                'The Lean Startup',
                'Eric Ries',
                readability='partial',
            ),
            match_result(100.0, 26.5),
        )

        self.assertEqual(decision.status, 'review_required')
        self.assertEqual(decision.reasons, ('partial_read',))

    def test_no_candidate_is_unmatched(self):
        decision = decide_review(BookRead('Visible unknown title'), None)

        self.assertEqual(decision.status, 'unmatched')
        self.assertEqual(decision.reasons, ('no_candidate',))

    def test_unreadable_is_unmatched(self):
        decision = decide_review(
            BookRead(None, readability='unreadable'),
            None,
        )

        self.assertEqual(decision.status, 'unmatched')
        self.assertEqual(decision.reasons, ('unreadable',))

    def test_failed_reader_result_is_unmatched(self):
        decision = decide_review(None, None, reader_status='error')

        self.assertEqual(decision.status, 'unmatched')
        self.assertEqual(decision.reasons, ('read_failed',))

    def test_visible_suggestion_threshold_is_separate_from_high_confidence(self):
        read = BookRead('The Fellowship of the Ring', 'J. R. R. Tolkien')
        match = match_result(100.0, 8.0, title_score=100.0)

        decision = decide_review(read, match)

        self.assertEqual(decision.status, 'review_required')
        self.assertIs(user_visible_suggestion(read, match), match.best_candidate)

    def test_title_contradiction_hides_author_rescued_candidate(self):
        read = BookRead("THE CANADIAN'S GUIDE TO STOCK", 'J. R. R. Tolkien')
        match = match_result(82.0, 12.0, title_score=74.0)

        decision = decide_review(read, match)

        self.assertIsNone(user_visible_suggestion(read, match))
        self.assertIn(
            'candidate_not_reliable_enough_to_show',
            decision.reasons,
        )

    def test_known_weak_candidates_are_not_user_visible(self):
        examples = (
            ('Kamus ya Kiswahili Kikorea', 60.0, 42.0),
            ('GETTING STARTED IN CHART PATTERNS', 69.3, 56.1),
            ('DURABLE', 60.4, 43.5),
        )
        for title, score, title_score in examples:
            with self.subTest(title=title):
                self.assertIsNone(
                    user_visible_suggestion(
                        BookRead(title),
                        match_result(score, 5.0, title_score=title_score),
                    )
                )

    def test_non_book_is_visible_as_unmatched_review_item(self):
        decision = decide_review(
            BookRead(None, raw_text='DURABLE AVERY'),
            None,
            region_type='non_book',
        )

        self.assertEqual(decision.status, 'unmatched')
        self.assertEqual(decision.reasons, ('non_book',))
