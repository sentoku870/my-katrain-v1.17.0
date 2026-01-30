# katrain/core/study/active_review.py
"""Active Review Mode core logic for next-move prediction.

This module provides:
- Data models for evaluation results (GuessGrade, GuessEvaluation, ReviewReadyResult)
- is_review_ready() to check if a node has sufficient analysis
- ActiveReviewer class for evaluating user guesses against AI candidates
"""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode

# =============================================================================
# Constants
# =============================================================================

MIN_RELIABLE_VISITS = 100  # Minimum visits for reliable analysis

GRADE_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "beginner": {"excellent": 1.5, "good": 4.0, "blunder": 8.0},
    "standard": {"excellent": 0.5, "good": 2.0, "blunder": 5.0},
    "advanced": {"excellent": 0.3, "good": 1.0, "blunder": 3.0},
    "pro": {"excellent": 0.2, "good": 0.5, "blunder": 2.0},
}

# =============================================================================
# Enums
# =============================================================================


class GuessGrade(Enum):
    """Grade for user's move guess."""

    PERFECT = "perfect"  # AI best move (order=0)
    EXCELLENT = "excellent"  # pointsLost < threshold_excellent
    GOOD = "good"  # pointsLost < threshold_good
    SLACK = "slack"  # threshold_good <= pointsLost < threshold_blunder
    BLUNDER = "blunder"  # pointsLost >= threshold_blunder
    NOT_IN_CANDIDATES = "not_in_candidates"  # Not in candidate list


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ReviewReadyResult:
    """Result of is_review_ready() check."""

    ready: bool
    message_key: str = ""
    visits: int = 0


@dataclass
class GuessEvaluation:
    """Evaluation result for a user's guess.

    Attributes:
        user_move: User's guessed move in GTP format (e.g., "D4")
        ai_best_move: AI's best move in GTP format
        score_loss: Points lost compared to best move (None if NOT_IN_CANDIDATES)
        policy_rank: Rank among candidates (1-indexed), None if not found
        grade: Grade classification
        matches_game_move: Whether the guess matches the actual game continuation
    """

    user_move: str
    ai_best_move: str
    score_loss: Optional[float]  # None for NOT_IN_CANDIDATES
    policy_rank: Optional[int]  # 1-indexed, None if not found
    grade: GuessGrade
    matches_game_move: bool


# =============================================================================
# Helper Functions
# =============================================================================


def _is_pass_move(move_str: Optional[str]) -> bool:
    """Check if move is a pass (case-insensitive)."""
    return move_str is not None and move_str.lower() == "pass"


# =============================================================================
# Core Functions
# =============================================================================


def is_review_ready(node: Optional["GameNode"]) -> ReviewReadyResult:
    """Check if node has sufficient analysis for Active Review.

    The current node's candidate_moves are used to evaluate predictions,
    so the current node must have sufficient analysis data.

    Args:
        node: Current GameNode to check

    Returns:
        ReviewReadyResult with ready status and message key for i18n
    """
    if not node:
        return ReviewReadyResult(False, "active_review:no_node")

    # Check if analysis exists on current node
    if not node.analysis_exists:
        return ReviewReadyResult(False, "active_review:analysis_required")

    visits = node.root_visits
    if visits < MIN_RELIABLE_VISITS:
        return ReviewReadyResult(False, "active_review:analysis_low_visits", visits)

    candidates = node.candidate_moves
    if not candidates:
        return ReviewReadyResult(False, "active_review:no_candidates")

    # Check if best move is pass (can't be predicted via board click)
    best = min(candidates, key=lambda c: c.get("order", float("inf")))
    if _is_pass_move(best.get("move")):
        return ReviewReadyResult(False, "active_review:best_is_pass")

    return ReviewReadyResult(True, "", visits)


# =============================================================================
# ActiveReviewer Class
# =============================================================================


class ActiveReviewer:
    """Evaluates user guesses against AI candidate moves."""

    def __init__(self, skill_preset: str = "standard"):
        """Initialize with skill preset for grade thresholds.

        Args:
            skill_preset: One of "beginner", "standard", "advanced", "pro"
        """
        self.thresholds = GRADE_THRESHOLDS.get(
            skill_preset, GRADE_THRESHOLDS["standard"]
        )

    def evaluate_guess(
        self,
        coords: Tuple[int, int],
        node: "GameNode",
    ) -> GuessEvaluation:
        """Evaluate user's guess against AI candidates.

        Args:
            coords: Board coordinates (col, row)
            node: Current GameNode (uses this node's candidate_moves)

        Returns:
            GuessEvaluation with grade and details

        Precondition:
            is_review_ready(node).ready == True
        """
        from katrain.core.sgf_parser import Move

        # Convert user coords to GTP format
        user_move = Move(coords, node.next_player)
        user_move_gtp = user_move.gtp()

        # Get candidate moves (pointsLost is pre-computed)
        candidates = node.candidate_moves

        # Get AI best move
        best_candidate = candidates[0] if candidates else None
        ai_best_move = best_candidate["move"] if best_candidate else "?"

        # Find user's move in candidates
        user_candidate = next(
            (c for c in candidates if c["move"] == user_move_gtp),
            None,
        )

        # Check if user's move matches actual game continuation
        game_move_gtp = None
        if node.ordered_children:
            mainline_child = node.ordered_children[0]
            if mainline_child.move:
                game_move_gtp = mainline_child.move.gtp()
        matches_game = game_move_gtp is not None and user_move_gtp == game_move_gtp

        # Handle NOT_IN_CANDIDATES case
        if user_candidate is None:
            return GuessEvaluation(
                user_move=user_move_gtp,
                ai_best_move=ai_best_move,
                score_loss=None,  # None, not inf
                policy_rank=None,
                grade=GuessGrade.NOT_IN_CANDIDATES,
                matches_game_move=matches_game,
            )

        # Extract pre-computed pointsLost
        score_loss = user_candidate["pointsLost"]
        policy_rank = user_candidate["order"] + 1  # 1-indexed

        grade = self._determine_grade(score_loss, user_candidate["order"])

        return GuessEvaluation(
            user_move=user_move_gtp,
            ai_best_move=ai_best_move,
            score_loss=score_loss,
            policy_rank=policy_rank,
            grade=grade,
            matches_game_move=matches_game,
        )

    def _determine_grade(self, score_loss: float, order: int) -> GuessGrade:
        """Determine grade based on score loss and order.

        Args:
            score_loss: Points lost compared to best move
            order: Candidate order (0 = best)

        Returns:
            GuessGrade enum value
        """
        if order == 0:
            return GuessGrade.PERFECT
        if score_loss < self.thresholds["excellent"]:
            return GuessGrade.EXCELLENT
        if score_loss < self.thresholds["good"]:
            return GuessGrade.GOOD
        if score_loss < self.thresholds["blunder"]:
            return GuessGrade.SLACK
        return GuessGrade.BLUNDER
