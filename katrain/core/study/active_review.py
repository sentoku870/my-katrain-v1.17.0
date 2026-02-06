# katrain/core/study/active_review.py
"""Active Review Mode core logic for next-move prediction.

This module provides:
- Data models for evaluation results (GuessGrade, GuessEvaluation, ReviewReadyResult)
- is_review_ready() to check if a node has sufficient analysis
- ActiveReviewer class for evaluating user guesses against AI candidates
- get_hint_for_best_move() for generating position-based hints (Phase 94)
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode

_log = logging.getLogger(__name__)

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


# =============================================================================
# Hint Generation (Phase 94)
# =============================================================================

# Hint text mapping by reason tag
# Maps tactical reason_tags to i18n keys for hints
_HINT_KEYS_BY_REASON_TAG: Dict[str, str] = {
    "atari": "active_review:hint:atari",
    "low_liberties": "active_review:hint:liberties",
    "need_connect": "active_review:hint:connection",
    "cut_risk": "active_review:hint:connection",
    "capture_possible": "active_review:hint:capture",
    "can_save": "active_review:hint:save",
    "endgame_hint": "active_review:hint:endgame",
    "chase_mode": "active_review:hint:attack",
}

# Priority order for reason tags (lower index = higher priority)
_HINT_PRIORITY: List[str] = [
    "atari",
    "low_liberties",
    "need_connect",
    "cut_risk",
    "capture_possible",
    "can_save",
    "chase_mode",
    "endgame_hint",
]


def get_hint_for_best_move(
    node: Optional["GameNode"],
    lang: str = "jp",
) -> Optional[str]:
    """Generate a position-based hint for the AI's best move.

    Uses the node's analysis data (reason_tags, position type) to provide
    a tactical hint about what kind of move to look for.

    Args:
        node: GameNode with analysis (uses parent's analysis for context)
        lang: Language code ("jp" or "en")

    Returns:
        Hint text string, or None if no relevant hint available

    Note:
        - Uses i18n keys that map to hint text in .po files
        - Falls back to MeaningTag description if the node has meaning_tag_id
        - Returns None if:
          - Node has no analysis
          - No tactical context detected
          - UNCERTAIN MeaningTag
    """
    from katrain.core.lang import i18n

    if node is None:
        return None

    # Check if node has sufficient analysis
    if not node.analysis_exists:
        return None

    # Try to get hint from reason tags on the current position
    # First check if there's any tactical context we can use
    hint_key = _get_hint_key_from_analysis(node)
    if hint_key:
        hint = i18n._(hint_key)
        # Check if i18n returned the key itself (untranslated)
        if hint != hint_key:
            return hint

    # Fallback: Check if node has meaning_tag_id from batch analysis
    meaning_tag_id = getattr(node, "meaning_tag_id", None)
    if meaning_tag_id is not None:
        return _get_hint_from_meaning_tag(meaning_tag_id, lang)

    # No hint available
    return None


def _get_hint_key_from_analysis(node: "GameNode") -> Optional[str]:
    """Extract i18n key for hint from node's analysis data.

    Checks the position for tactical indicators and returns an appropriate
    hint key based on priority order.

    Args:
        node: GameNode with analysis

    Returns:
        i18n key string, or None if no relevant hint
    """
    # Get the analysis info to look for tactical patterns
    analysis = node.analysis

    if not analysis:
        return None

    # Check for rootInfo which may contain position indicators
    root_info = analysis.get("rootInfo", {})

    # Try to infer tactical context from candidate moves' characteristics
    candidates = node.candidate_moves
    if not candidates:
        return None

    # Look at the best move and see if we can determine its purpose
    best = candidates[0]
    best_move = best.get("move", "")

    # Check if this is an endgame position based on score closeness
    score_stdev = root_info.get("scoreStdev", 0)
    if score_stdev < 3.0 and node.depth > 150:
        return "active_review:hint:endgame"

    # Check for life/death situations based on ownership uncertainty
    ownership = root_info.get("ownership", [])
    if ownership:
        # High ownership variance suggests tactical fighting
        if any(abs(o) < 0.3 for o in ownership[:50]):  # Early cells
            return "active_review:hint:fighting"

    # Default: no specific hint available
    return None


def _get_hint_from_meaning_tag(
    meaning_tag_id: str,
    lang: str,
) -> Optional[str]:
    """Get hint from MeaningTag description.

    Args:
        meaning_tag_id: MeaningTagId.value string (e.g., "overplay")
        lang: Language code ("jp" or "en")

    Returns:
        Description text, or None if UNCERTAIN or invalid
    """
    from katrain.core.analysis.meaning_tags import (
        MeaningTagId,
        get_tag_description,
        normalize_lang,
    )

    # Skip UNCERTAIN - not useful as a hint
    if meaning_tag_id == MeaningTagId.UNCERTAIN.value:
        return None

    try:
        tag_id = MeaningTagId(meaning_tag_id)
    except ValueError:
        _log.debug("Unknown meaning_tag_id: %s", meaning_tag_id)
        return None

    # Normalize language (jp -> ja for MeaningTags registry)
    normalized_lang = normalize_lang(lang)
    description = get_tag_description(tag_id, normalized_lang)

    # Return None if description is empty
    return description if description else None
