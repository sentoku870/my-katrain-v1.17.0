# tests/test_review_session.py
"""Tests for katrain.core.study.review_session module (Phase 94).

Tests cover:
- GuessResult dataclass and properties
- SessionSummary calculations
- ReviewSession lifecycle management
- Pending state handling
- Retry/Hint tracking
"""

import logging
import pytest
from datetime import datetime
from unittest.mock import patch

from katrain.core.study.active_review import GuessEvaluation, GuessGrade
from katrain.core.study.review_session import (
    GuessResult,
    ReviewSession,
    SessionSummary,
)


# =============================================================================
# Test Fixtures
# =============================================================================


def make_evaluation(
    grade: GuessGrade,
    user_move: str = "D4",
    ai_best: str = "Q16",
    score_loss: float = 2.0,
    matches_game: bool = False,
) -> GuessEvaluation:
    """Create a GuessEvaluation for testing."""
    # For NOT_IN_CANDIDATES, score_loss should be None
    if grade == GuessGrade.NOT_IN_CANDIDATES:
        score_loss = None
    return GuessEvaluation(
        user_move=user_move,
        ai_best_move=ai_best,
        score_loss=score_loss,
        policy_rank=1 if grade == GuessGrade.PERFECT else 2,
        grade=grade,
        matches_game_move=matches_game,
    )


# =============================================================================
# TestGuessResult
# =============================================================================


class TestGuessResult:
    """Tests for GuessResult dataclass."""

    def test_basic_properties(self):
        """GuessResult delegates properties from evaluation."""
        evaluation = make_evaluation(GuessGrade.GOOD, user_move="E5", score_loss=1.5)
        result = GuessResult(move_number=45, evaluation=evaluation)

        assert result.grade == GuessGrade.GOOD
        assert result.score_loss == 1.5
        assert result.user_move == "E5"
        assert result.matches_game_move is False

    def test_is_ai_best_move_perfect(self):
        """is_ai_best_move returns True for PERFECT grade."""
        evaluation = make_evaluation(GuessGrade.PERFECT, score_loss=0.0)
        result = GuessResult(move_number=10, evaluation=evaluation)

        assert result.is_ai_best_move is True

    def test_is_ai_best_move_non_perfect(self):
        """is_ai_best_move returns False for non-PERFECT grades."""
        for grade in [GuessGrade.EXCELLENT, GuessGrade.GOOD, GuessGrade.BLUNDER]:
            evaluation = make_evaluation(grade)
            result = GuessResult(move_number=10, evaluation=evaluation)
            assert result.is_ai_best_move is False, f"Failed for {grade}"

    def test_retry_count_default(self):
        """retry_count defaults to 0."""
        evaluation = make_evaluation(GuessGrade.GOOD)
        result = GuessResult(move_number=10, evaluation=evaluation)
        assert result.retry_count == 0

    def test_hint_used_default(self):
        """hint_used defaults to False."""
        evaluation = make_evaluation(GuessGrade.GOOD)
        result = GuessResult(move_number=10, evaluation=evaluation)
        assert result.hint_used is False

    def test_timestamp_auto_set(self):
        """timestamp is automatically set to current time."""
        before = datetime.now()
        evaluation = make_evaluation(GuessGrade.GOOD)
        result = GuessResult(move_number=10, evaluation=evaluation)
        after = datetime.now()

        assert before <= result.timestamp <= after


# =============================================================================
# TestReviewSession - Basic Operations
# =============================================================================


class TestReviewSessionBasic:
    """Tests for ReviewSession basic operations."""

    def test_empty_session_summary(self):
        """Empty session: total_guesses=0, average=None."""
        session = ReviewSession()
        summary = session.get_summary()

        assert summary.total_guesses == 0
        assert summary.perfect_count == 0
        assert summary.average_score_loss is None
        assert summary.ai_best_match_rate == 0.0
        assert summary.worst_misses == ()

    def test_record_single_guess(self):
        """Single guess: results has 1 item."""
        session = ReviewSession()
        session.begin_position(45)
        evaluation = make_evaluation(GuessGrade.GOOD)
        result = session.record_final_guess(evaluation)

        assert result is True
        assert len(session.results) == 1
        assert session.results[0].move_number == 45

    def test_record_without_begin_returns_false(self):
        """record_final_guess without begin_position returns False."""
        session = ReviewSession()
        evaluation = make_evaluation(GuessGrade.GOOD)

        result = session.record_final_guess(evaluation)

        assert result is False
        assert len(session.results) == 0

    def test_clear_resets_all_state(self):
        """clear() resets results and pending state."""
        session = ReviewSession()
        session.begin_position(10)
        session.mark_retry()
        session.mark_hint_used()
        evaluation = make_evaluation(GuessGrade.GOOD)
        session.record_final_guess(evaluation)

        session.clear()

        assert len(session.results) == 0
        assert session.has_pending is False
        assert session._pending_retry_count == 0
        assert session._pending_hint_used is False


# =============================================================================
# TestReviewSession - Pending State
# =============================================================================


class TestReviewSessionPending:
    """Tests for ReviewSession pending state management."""

    def test_has_pending_property_true(self):
        """has_pending returns True after begin_position."""
        session = ReviewSession()
        session.begin_position(20)

        assert session.has_pending is True

    def test_has_pending_property_false_initially(self):
        """has_pending returns False initially."""
        session = ReviewSession()

        assert session.has_pending is False

    def test_has_pending_false_after_record(self):
        """has_pending returns False after record_final_guess."""
        session = ReviewSession()
        session.begin_position(20)
        evaluation = make_evaluation(GuessGrade.GOOD)
        session.record_final_guess(evaluation)

        assert session.has_pending is False

    def test_abort_pending_clears_state(self):
        """abort_pending clears pending state."""
        session = ReviewSession()
        session.begin_position(30)
        session.mark_retry()
        session.mark_hint_used()

        session.abort_pending()

        assert session.has_pending is False
        assert session._pending_retry_count == 0
        assert session._pending_hint_used is False

    def test_abort_pending_logs_debug(self, caplog):
        """abort_pending logs debug message."""
        with caplog.at_level(logging.DEBUG):
            session = ReviewSession()
            session.begin_position(40)
            session.mark_retry()

            session.abort_pending()

        assert "Aborting pending review for move 40" in caplog.text


# =============================================================================
# TestReviewSession - Retry/Hint Tracking
# =============================================================================


class TestReviewSessionRetryHint:
    """Tests for ReviewSession retry and hint tracking."""

    def test_retry_count_accumulation(self):
        """mark_retry increments pending_retry_count."""
        session = ReviewSession()
        session.begin_position(50)
        session.mark_retry()
        session.mark_retry()
        session.mark_retry()

        evaluation = make_evaluation(GuessGrade.GOOD)
        session.record_final_guess(evaluation)

        assert session.results[0].retry_count == 3

    def test_hint_used_flag(self):
        """mark_hint_used sets pending_hint_used to True."""
        session = ReviewSession()
        session.begin_position(60)
        session.mark_hint_used()

        evaluation = make_evaluation(GuessGrade.GOOD)
        session.record_final_guess(evaluation)

        assert session.results[0].hint_used is True

    def test_mark_retry_without_pending_is_noop(self, caplog):
        """mark_retry without pending is no-op with debug log."""
        with caplog.at_level(logging.DEBUG):
            session = ReviewSession()
            session.mark_retry()

        assert "mark_retry() called without pending position" in caplog.text

    def test_mark_hint_used_without_pending_is_noop(self, caplog):
        """mark_hint_used without pending is no-op with debug log."""
        with caplog.at_level(logging.DEBUG):
            session = ReviewSession()
            session.mark_hint_used()

        assert "mark_hint_used() called without pending position" in caplog.text

    def test_multiple_retries_then_record(self):
        """3 retries then record: result.retry_count=3."""
        session = ReviewSession()
        session.begin_position(70)
        session.mark_retry()
        session.mark_retry()
        session.mark_retry()

        evaluation = make_evaluation(GuessGrade.EXCELLENT)
        session.record_final_guess(evaluation)

        assert session.results[0].retry_count == 3
        assert session.results[0].grade == GuessGrade.EXCELLENT


# =============================================================================
# TestReviewSession - Summary Calculations
# =============================================================================


class TestReviewSessionSummary:
    """Tests for SessionSummary calculations."""

    def test_worst_misses_sorted_by_loss(self):
        """worst_misses sorted by score_loss descending."""
        session = ReviewSession()

        # Add guesses with different losses
        losses = [3.0, 8.0, 1.0, 5.0, 2.0]
        for i, loss in enumerate(losses):
            session.begin_position(i)
            evaluation = make_evaluation(GuessGrade.SLACK, score_loss=loss)
            session.record_final_guess(evaluation)

        summary = session.get_summary()

        # Worst 3 should be 8.0, 5.0, 3.0
        assert len(summary.worst_misses) == 3
        assert summary.worst_misses[0].score_loss == 8.0
        assert summary.worst_misses[1].score_loss == 5.0
        assert summary.worst_misses[2].score_loss == 3.0

    def test_worst_misses_excludes_none_loss(self):
        """worst_misses excludes score_loss=None (NOT_IN_CANDIDATES)."""
        session = ReviewSession()

        # Add mix of normal and NOT_IN_CANDIDATES
        session.begin_position(1)
        session.record_final_guess(make_evaluation(GuessGrade.SLACK, score_loss=3.0))

        session.begin_position(2)
        session.record_final_guess(make_evaluation(GuessGrade.NOT_IN_CANDIDATES))

        session.begin_position(3)
        session.record_final_guess(make_evaluation(GuessGrade.BLUNDER, score_loss=6.0))

        summary = session.get_summary()

        # Only 2 results have loss values
        assert len(summary.worst_misses) == 2
        assert all(r.score_loss is not None for r in summary.worst_misses)

    def test_worst_misses_is_tuple(self):
        """worst_misses is a Tuple (immutable)."""
        session = ReviewSession()
        session.begin_position(1)
        session.record_final_guess(make_evaluation(GuessGrade.SLACK, score_loss=2.0))

        summary = session.get_summary()

        assert isinstance(summary.worst_misses, tuple)

    def test_ai_best_match_rate_from_perfect_grade(self):
        """ai_best_match_rate calculated from PERFECT grade count."""
        session = ReviewSession()

        # 2 PERFECT, 3 others = 40%
        session.begin_position(1)
        session.record_final_guess(make_evaluation(GuessGrade.PERFECT, score_loss=0.0))
        session.begin_position(2)
        session.record_final_guess(make_evaluation(GuessGrade.PERFECT, score_loss=0.0))
        session.begin_position(3)
        session.record_final_guess(make_evaluation(GuessGrade.GOOD, score_loss=1.0))
        session.begin_position(4)
        session.record_final_guess(make_evaluation(GuessGrade.SLACK, score_loss=3.0))
        session.begin_position(5)
        session.record_final_guess(make_evaluation(GuessGrade.BLUNDER, score_loss=6.0))

        summary = session.get_summary()

        assert summary.ai_best_match_rate == 40.0

    def test_game_move_match_rate_calculation(self):
        """game_move_match_rate calculated from matches_game_move."""
        session = ReviewSession()

        # 3 match game, 2 don't = 60%
        session.begin_position(1)
        session.record_final_guess(make_evaluation(GuessGrade.GOOD, matches_game=True))
        session.begin_position(2)
        session.record_final_guess(make_evaluation(GuessGrade.GOOD, matches_game=True))
        session.begin_position(3)
        session.record_final_guess(make_evaluation(GuessGrade.GOOD, matches_game=True))
        session.begin_position(4)
        session.record_final_guess(make_evaluation(GuessGrade.SLACK, matches_game=False))
        session.begin_position(5)
        session.record_final_guess(make_evaluation(GuessGrade.SLACK, matches_game=False))

        summary = session.get_summary()

        assert summary.game_move_match_rate == 60.0

    def test_average_loss_excludes_not_in_candidates(self):
        """average_score_loss excludes score_loss=None."""
        session = ReviewSession()

        # 2 with loss (2.0, 4.0), 1 NOT_IN_CANDIDATES
        session.begin_position(1)
        session.record_final_guess(make_evaluation(GuessGrade.GOOD, score_loss=2.0))
        session.begin_position(2)
        session.record_final_guess(make_evaluation(GuessGrade.SLACK, score_loss=4.0))
        session.begin_position(3)
        session.record_final_guess(make_evaluation(GuessGrade.NOT_IN_CANDIDATES))

        summary = session.get_summary()

        # Average of 2.0 and 4.0 = 3.0
        assert summary.average_score_loss == 3.0

    def test_average_loss_all_not_in_candidates(self):
        """average_score_loss is None when all are NOT_IN_CANDIDATES."""
        session = ReviewSession()

        session.begin_position(1)
        session.record_final_guess(make_evaluation(GuessGrade.NOT_IN_CANDIDATES))
        session.begin_position(2)
        session.record_final_guess(make_evaluation(GuessGrade.NOT_IN_CANDIDATES))

        summary = session.get_summary()

        assert summary.average_score_loss is None

    def test_total_retries_sum(self):
        """total_retries is sum of all retry_counts."""
        session = ReviewSession()

        # First: 2 retries
        session.begin_position(1)
        session.mark_retry()
        session.mark_retry()
        session.record_final_guess(make_evaluation(GuessGrade.GOOD))

        # Second: 1 retry
        session.begin_position(2)
        session.mark_retry()
        session.record_final_guess(make_evaluation(GuessGrade.EXCELLENT))

        # Third: 0 retries
        session.begin_position(3)
        session.record_final_guess(make_evaluation(GuessGrade.PERFECT, score_loss=0.0))

        summary = session.get_summary()

        assert summary.total_retries == 3

    def test_hints_used_count(self):
        """hints_used_count is count of hint_used=True."""
        session = ReviewSession()

        # First: hint used
        session.begin_position(1)
        session.mark_hint_used()
        session.record_final_guess(make_evaluation(GuessGrade.GOOD))

        # Second: no hint
        session.begin_position(2)
        session.record_final_guess(make_evaluation(GuessGrade.EXCELLENT))

        # Third: hint used
        session.begin_position(3)
        session.mark_hint_used()
        session.record_final_guess(make_evaluation(GuessGrade.SLACK))

        summary = session.get_summary()

        assert summary.hints_used_count == 2
