# katrain/core/study/review_session.py
"""Active Review session tracking for statistics accumulation.

This module provides:
- GuessResult: Record of a single position's final answer
- SessionSummary: Aggregated statistics for an Active Review session
- ReviewSession: Manager for tracking guesses and generating summaries

Part of Phase 94: Active Review Extension.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from katrain.core.study.active_review import GuessEvaluation, GuessGrade

_log = logging.getLogger(__name__)


@dataclass
class GuessResult:
    """Record of a single position's final answer.

    Important: This record captures only the final answer.
    - If the user gave a bad answer, retried, then gave a good answer,
      only the good answer is recorded.
    - Therefore worst_misses contains only cases where the final answer was bad.
    - retry_count and hint_used show the process leading to the final answer.

    Label mapping:
    - NOT_IN_CANDIDATES (score_loss=None) -> UI: "Unusual" / "珍しい手"
    """

    move_number: int  # Which move was being predicted
    evaluation: GuessEvaluation  # Final evaluation result
    retry_count: int = 0  # Number of retries for this position (cumulative)
    hint_used: bool = False  # Whether hint was used (True if used at least once)
    timestamp: datetime = field(default_factory=datetime.now)

    # Convenience properties (delegated from evaluation)
    @property
    def grade(self) -> GuessGrade:
        return self.evaluation.grade

    @property
    def score_loss(self) -> Optional[float]:
        return self.evaluation.score_loss

    @property
    def matches_game_move(self) -> bool:
        return self.evaluation.matches_game_move

    @property
    def user_move(self) -> str:
        return self.evaluation.user_move

    @property
    def is_ai_best_move(self) -> bool:
        """Whether user's answer was AI's best move (order=0).

        Invariant: GuessGrade.PERFECT is assigned only when order==0.
        See active_review.py _determine_grade().
        """
        return self.evaluation.grade == GuessGrade.PERFECT


@dataclass
class SessionSummary:
    """Session statistics.

    Note: All statistics are based on "final answers".
    - If the user retried and got a correct answer, that correct answer is counted.
    - worst_misses contains only cases where the final answer was bad.
    """

    total_guesses: int

    # Grade counts
    perfect_count: int
    excellent_count: int
    good_count: int
    slack_count: int
    blunder_count: int
    not_in_candidates_count: int  # UI: "Unusual" / "珍しい手"

    # Match rates
    ai_best_match_rate: float  # is_ai_best_move==True / total_guesses * 100
    game_move_match_rate: float  # matches_game_move==True percentage * 100

    # Loss statistics
    average_score_loss: Optional[float]  # NOT_IN_CANDIDATES excluded

    # Worst 3 moves (score_loss descending, final answers only)
    worst_misses: Tuple["GuessResult", ...]  # Tuple for immutability

    # Retry/Hint statistics
    total_retries: int
    hints_used_count: int


class ReviewSession:
    """Session manager for Active Review.

    Recording model:
    - For each position (move_number), only the final answer is recorded.
    - retry_count: Number of retries before the final answer.
    - hint_used: Whether hint was used before the final answer.

    Pending state interruption:
    - When the node changes, pending state is cleared (abort_pending()).
    - This prevents recording to the wrong position.
    """

    def __init__(self, skill_preset: str = "standard"):
        """Initialize session with skill preset.

        Args:
            skill_preset: One of "beginner", "standard", "advanced", "pro"
        """
        self.skill_preset = skill_preset
        self.results: List[GuessResult] = []
        # Current position's pending state
        self._pending_move_number: Optional[int] = None
        self._pending_retry_count: int = 0
        self._pending_hint_used: bool = False

    @property
    def has_pending(self) -> bool:
        """Whether there is a pending position."""
        return self._pending_move_number is not None

    def begin_position(self, move_number: int) -> None:
        """Start answering for a new position.

        Args:
            move_number: The move number being predicted
        """
        self._pending_move_number = move_number
        self._pending_retry_count = 0
        self._pending_hint_used = False

    def abort_pending(self) -> None:
        """Abort pending state (called on node change).

        When the user navigates to a different node during retry,
        clear pending state to prevent recording to the wrong position.
        """
        if self._pending_move_number is not None:
            _log.debug(
                "Aborting pending review for move %d (retry=%d, hint=%s)",
                self._pending_move_number,
                self._pending_retry_count,
                self._pending_hint_used,
            )
        self._pending_move_number = None
        self._pending_retry_count = 0
        self._pending_hint_used = False

    def mark_retry(self) -> None:
        """Mark a retry for the current position.

        Note: No-op if has_pending==False (logs debug message).
        """
        if not self.has_pending:
            _log.debug("mark_retry() called without pending position - ignored")
            return
        self._pending_retry_count += 1

    def mark_hint_used(self) -> None:
        """Mark hint usage for the current position.

        Note: No-op if has_pending==False (logs debug message).
        """
        if not self.has_pending:
            _log.debug("mark_hint_used() called without pending position - ignored")
            return
        self._pending_hint_used = True

    def record_final_guess(self, evaluation: GuessEvaluation) -> bool:
        """Record the final answer (once per position).

        Args:
            evaluation: Evaluation result

        Returns:
            True: Successfully recorded
            False: No pending state, not recorded (begin_position not called)

        Note:
            If pending_move_number is None, returns False and logs a warning.
            This is a safeguard to detect event ordering issues.
        """
        if self._pending_move_number is None:
            _log.warning(
                "record_final_guess() called without begin_position() - "
                "possible event ordering issue"
            )
            return False

        result = GuessResult(
            move_number=self._pending_move_number,
            evaluation=evaluation,
            retry_count=self._pending_retry_count,
            hint_used=self._pending_hint_used,
        )
        self.results.append(result)
        # Clear pending state
        self._pending_move_number = None
        self._pending_retry_count = 0
        self._pending_hint_used = False
        return True

    def get_summary(self) -> SessionSummary:
        """Generate statistics summary.

        Returns:
            SessionSummary with aggregated statistics
        """
        total = len(self.results)

        # Grade counts
        perfect_count = sum(1 for r in self.results if r.grade == GuessGrade.PERFECT)
        excellent_count = sum(
            1 for r in self.results if r.grade == GuessGrade.EXCELLENT
        )
        good_count = sum(1 for r in self.results if r.grade == GuessGrade.GOOD)
        slack_count = sum(1 for r in self.results if r.grade == GuessGrade.SLACK)
        blunder_count = sum(1 for r in self.results if r.grade == GuessGrade.BLUNDER)
        not_in_candidates_count = sum(
            1 for r in self.results if r.grade == GuessGrade.NOT_IN_CANDIDATES
        )

        # AI best match rate (PERFECT grade count)
        ai_best_match_rate = (perfect_count / total * 100) if total > 0 else 0.0

        # Game move match rate
        game_move_matches = sum(1 for r in self.results if r.matches_game_move)
        game_move_match_rate = (game_move_matches / total * 100) if total > 0 else 0.0

        # Average score loss (exclude NOT_IN_CANDIDATES)
        losses = [r.score_loss for r in self.results if r.score_loss is not None]
        average_score_loss = sum(losses) / len(losses) if losses else None

        # Worst misses (top 3 by score_loss, exclude None)
        results_with_loss = [r for r in self.results if r.score_loss is not None]
        sorted_by_loss = sorted(
            results_with_loss, key=lambda r: r.score_loss or 0, reverse=True
        )
        worst_misses = tuple(sorted_by_loss[:3])

        # Retry/Hint statistics
        total_retries = sum(r.retry_count for r in self.results)
        hints_used_count = sum(1 for r in self.results if r.hint_used)

        return SessionSummary(
            total_guesses=total,
            perfect_count=perfect_count,
            excellent_count=excellent_count,
            good_count=good_count,
            slack_count=slack_count,
            blunder_count=blunder_count,
            not_in_candidates_count=not_in_candidates_count,
            ai_best_match_rate=ai_best_match_rate,
            game_move_match_rate=game_move_match_rate,
            average_score_loss=average_score_loss,
            worst_misses=worst_misses,
            total_retries=total_retries,
            hints_used_count=hints_used_count,
        )

    def clear(self) -> None:
        """Reset session."""
        self.results.clear()
        self._pending_move_number = None
        self._pending_retry_count = 0
        self._pending_hint_used = False
