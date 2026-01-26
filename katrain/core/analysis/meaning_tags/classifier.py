# -*- coding: utf-8 -*-
"""Meaning Tags Classifier.

This module implements the deterministic rule-based classification system
for assigning meaning tags to MoveEval objects.

Part of Phase 46: Meaning Tags System Core - PR-2.

Public API:
    - ClassificationContext: Additional context for classification
    - classify_meaning_tag(): Main classification function
    - resolve_lexicon_anchor(): Lexicon anchor resolution
    - Helper functions: get_loss_value, classify_gtp_move, is_classifiable_move,
                       compute_move_distance, is_endgame
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Protocol

from .models import MeaningTag, MeaningTagId
from .registry import MEANING_TAG_REGISTRY

if TYPE_CHECKING:
    from katrain.core.analysis.models import MoveEval


# =============================================================================
# Classification Thresholds
# NOTE: These thresholds are provisional and may be tuned in later phases.
#       Keep determinism: do not use random or time-based values.
# =============================================================================

# Loss thresholds (in points)
THRESHOLD_LOSS_SIGNIFICANT = 0.5  # Below this = no significant mistake
THRESHOLD_LOSS_SMALL = 1.0  # Small loss boundary
THRESHOLD_LOSS_MEDIUM = 2.0  # Medium loss boundary
THRESHOLD_LOSS_CUT_RISK = 3.0  # cut_risk connection miss threshold
THRESHOLD_LOSS_LARGE = 5.0  # Large loss boundary
THRESHOLD_LOSS_HUGE = 8.0  # Huge loss (life/death territory)
THRESHOLD_LOSS_CATASTROPHIC = 15.0  # Catastrophic (pure life/death)

# Ownership flux thresholds
THRESHOLD_OWNERSHIP_FLUX_LIFE_DEATH = 15.0  # Indicates life/death change

# Policy thresholds
THRESHOLD_POLICY_VERY_LOW = 0.001  # Extremely unlikely move (bad shape)
THRESHOLD_POLICY_LOW = 0.005  # Low but non-zero (direction error)
THRESHOLD_POLICY_ACTUAL_LOW = 0.05  # Actual move was not considered
THRESHOLD_POLICY_TRAP = 0.10  # High enough to be a "trap" (reading failure)
THRESHOLD_POLICY_BEST_HIGH = 0.30  # Best move is obvious

# Score stdev threshold
THRESHOLD_SCORE_STDEV_HIGH = 15.0  # Complex/volatile position

# Move distance thresholds
THRESHOLD_DISTANCE_CLOSE = 5  # Moves close (slow move)
THRESHOLD_DISTANCE_FAR = 8  # Moves far apart (direction error)

# Move number thresholds
THRESHOLD_MOVE_EARLY_GAME = 80  # Early/mid game boundary
THRESHOLD_MOVE_ENDGAME_ABSOLUTE = 150  # Absolute endgame threshold
THRESHOLD_ENDGAME_RATIO = 0.7  # Endgame if move_number > total * ratio


# =============================================================================
# ClassificationContext
# =============================================================================


@dataclass(frozen=True)
class ClassificationContext:
    """Additional context for classification.

    Contains only information NOT in MoveEval.
    All fields are Optional; None means the related rule is skipped.

    Attributes:
        best_move_policy: Policy value of the best move (0.0-1.0)
        actual_move_policy: Policy value of the actual move played (0.0-1.0)
        move_distance: Manhattan distance between best and actual move
        ownership_flux: Ownership change magnitude
        score_stdev: KataGo's scoreStdev value
        total_moves: Total moves in the game (for endgame detection)
    """

    best_move_policy: Optional[float] = None
    actual_move_policy: Optional[float] = None
    move_distance: Optional[int] = None
    ownership_flux: Optional[float] = None
    score_stdev: Optional[float] = None
    total_moves: Optional[int] = None


# =============================================================================
# LexiconStore Protocol (for type hints without importing)
# =============================================================================


class LexiconStoreLike(Protocol):
    """Protocol for LexiconStore-like objects."""

    def get(self, entry_id: str) -> Optional[object]:
        """Get an entry by ID."""
        ...


# =============================================================================
# Helper Functions
# =============================================================================


def get_loss_value(move_eval: "MoveEval") -> Optional[float]:
    """Extract loss value from MoveEval.

    Priority:
        1. score_loss (KataGo)
        2. leela_loss_est (Leela)
        3. points_lost (fallback)
        4. None (no loss data)

    Args:
        move_eval: The MoveEval to extract loss from

    Returns:
        float: The loss value, or None if no loss data exists
    """
    if move_eval.score_loss is not None:
        return move_eval.score_loss
    if move_eval.leela_loss_est is not None:
        return move_eval.leela_loss_est
    if move_eval.points_lost is not None:
        return move_eval.points_lost
    return None


def classify_gtp_move(gtp: Optional[str]) -> str:
    """Classify GTP move into categories.

    Args:
        gtp: GTP coordinate string, or None

    Returns:
        "missing": gtp is None (data not available, e.g., root node)
        "empty": gtp is "" (parse error or uninitialized)
        "pass": gtp is "pass" (intentional pass)
        "resign": gtp is "resign" (resignation)
        "normal": gtp is a coordinate (e.g., "D4")
    """
    if gtp is None:
        return "missing"
    if gtp == "":
        return "empty"
    normalized = gtp.strip().lower()
    if normalized == "pass":
        return "pass"
    if normalized == "resign":
        return "resign"
    return "normal"


def is_classifiable_move(gtp: Optional[str]) -> bool:
    """Check if a move can be classified.

    Args:
        gtp: GTP coordinate string, or None

    Returns:
        True if the move is a normal board coordinate (not pass/resign/missing/empty)
    """
    return classify_gtp_move(gtp) == "normal"


def compute_move_distance(
    best_gtp: Optional[str], actual_gtp: Optional[str]
) -> Optional[int]:
    """Compute Manhattan distance between two GTP coordinates.

    Uses existing Move.from_gtp() which handles:
        - GTP column convention: "I" is skipped (A-H, J-T for 19x19)
        - Case normalization (uppercase internally)
        - Pass detection via Move.is_pass property

    Args:
        best_gtp: Best move in GTP format (e.g., "D4", "Q16"), or None
        actual_gtp: Actual move in GTP format, or None

    Returns:
        int: Manhattan distance |x1-x2| + |y1-y2|
        None: If either move is None/pass/resign/invalid

    Examples:
        >>> compute_move_distance("D4", "D4")
        0
        >>> compute_move_distance("D4", "Q16")
        24
        >>> compute_move_distance("A1", "T19")
        36
        >>> compute_move_distance(None, "D4")
        None
    """
    # is_classifiable_move handles None → returns False
    if not is_classifiable_move(best_gtp) or not is_classifiable_move(actual_gtp):
        return None

    try:
        from katrain.core.sgf_parser import Move

        best_move = Move.from_gtp(best_gtp)  # type: ignore  # gtp is str here
        actual_move = Move.from_gtp(actual_gtp)  # type: ignore
    except (ValueError, AttributeError):
        return None

    if best_move.is_pass or actual_move.is_pass:
        return None

    bx, by = best_move.coords
    ax, ay = actual_move.coords
    return abs(bx - ax) + abs(by - ay)


def is_endgame(
    move_number: int, total_moves: Optional[int], has_endgame_hint: bool
) -> bool:
    """Determine if the position is in the endgame phase.

    Criteria (OR):
        1. has_endgame_hint == True (from reason_tags)
        2. total_moves is not None and move_number > total_moves * THRESHOLD_ENDGAME_RATIO
        3. move_number > THRESHOLD_MOVE_ENDGAME_ABSOLUTE

    Args:
        move_number: Current move number
        total_moves: Total moves in the game (None if unknown)
        has_endgame_hint: Whether "endgame_hint" is in reason_tags

    Returns:
        True if the position is in the endgame
    """
    if has_endgame_hint:
        return True
    if total_moves is not None and move_number > total_moves * THRESHOLD_ENDGAME_RATIO:
        return True
    return move_number > THRESHOLD_MOVE_ENDGAME_ABSOLUTE


# =============================================================================
# Lexicon Anchor Resolution
# =============================================================================


def resolve_lexicon_anchor(
    tag_id: MeaningTagId,
    lexicon_store: Optional[LexiconStoreLike],
    validate_anchor: bool,
) -> Optional[str]:
    """Resolve lexicon_anchor_id for a tag.

    Args:
        tag_id: The meaning tag ID
        lexicon_store: LexiconStore instance for validation (optional)
        validate_anchor: If True, validate anchors exist; if False, use defaults

    Returns:
        The anchor ID if valid, or None
    """
    definition = MEANING_TAG_REGISTRY[tag_id]
    default_anchor = definition.default_lexicon_anchor

    if default_anchor is None:
        return None

    if not validate_anchor:
        return default_anchor

    if lexicon_store is None:
        return None

    entry = lexicon_store.get(default_anchor)
    return default_anchor if entry is not None else None


# =============================================================================
# Main Classification Function
# =============================================================================


def classify_meaning_tag(
    move_eval: "MoveEval",
    *,
    context: Optional[ClassificationContext] = None,
    lexicon_store: Optional[LexiconStoreLike] = None,
    validate_anchor: bool = True,
) -> MeaningTag:
    """Classify a MoveEval into a meaning tag (deterministic).

    This function applies a series of rules in priority order to determine
    the most appropriate semantic tag for a move. The classification is
    completely deterministic: the same inputs always produce the same output.

    Args:
        move_eval: The MoveEval to classify (required)
        context: Additional context (optional, MoveEval-only classification if omitted)
        lexicon_store: Lexicon store for anchor validation (optional)
        validate_anchor: If True, validate anchors; if False, use defaults as-is

    Returns:
        MeaningTag: Classification result (never None, UNCERTAIN as fallback)

    Example:
        >>> from katrain.core.analysis.models import MoveEval
        >>> move_eval = MoveEval(move_number=45, player="B", gtp="D4",
        ...                      score_loss=12.0, is_reliable=True,
        ...                      reason_tags=["atari", "low_liberties"])
        >>> tag = classify_meaning_tag(move_eval)
        >>> tag.id
        <MeaningTagId.CAPTURE_RACE_LOSS: 'capture_race_loss'>
    """
    # =========================================================================
    # Early Return Conditions
    # =========================================================================

    # 1. GTP classification
    gtp_class = classify_gtp_move(move_eval.gtp)

    # 1a. Data missing → UNCERTAIN
    if gtp_class == "missing":
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="gtp_missing")

    # 1b. Empty string → UNCERTAIN
    if gtp_class == "empty":
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="gtp_empty")

    # 1c. Pass move → UNCERTAIN
    if gtp_class == "pass":
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="pass_move")

    # 1d. Resign → UNCERTAIN
    if gtp_class == "resign":
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="resign_move")

    # 2. Unreliable → UNCERTAIN
    if not move_eval.is_reliable:
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="unreliable_visits")

    # 3. No loss data → UNCERTAIN
    loss = get_loss_value(move_eval)
    if loss is None:
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="loss_data_missing")

    # 4. Insignificant loss → UNCERTAIN
    if loss < THRESHOLD_LOSS_SIGNIFICANT:
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="no_significant_loss")

    # =========================================================================
    # Derive Boolean Flags from reason_tags
    # =========================================================================

    reason_tags = set(move_eval.reason_tags) if move_eval.reason_tags else set()

    has_atari = "atari" in reason_tags
    has_low_liberties = "low_liberties" in reason_tags
    has_need_connect = "need_connect" in reason_tags
    has_cut_risk = "cut_risk" in reason_tags
    has_reading_failure = "reading_failure" in reason_tags
    has_endgame_hint = "endgame_hint" in reason_tags
    has_heavy_loss = "heavy_loss" in reason_tags
    has_chase_mode = "chase_mode" in reason_tags

    # Composite conditions
    is_urgent = has_atari or has_low_liberties or has_cut_risk
    has_tactical_tags = (
        has_atari
        or has_low_liberties
        or has_cut_risk
        or has_need_connect
        or has_chase_mode
    )
    has_semeai_pattern = has_atari and has_low_liberties

    # =========================================================================
    # Priority-based Classification
    # Design principle: More specific tags take priority
    # =========================================================================

    def _make_tag(tag_id: MeaningTagId) -> MeaningTag:
        """Create a MeaningTag with optional lexicon anchor."""
        anchor = resolve_lexicon_anchor(tag_id, lexicon_store, validate_anchor)
        return MeaningTag(id=tag_id, lexicon_anchor_id=anchor)

    # Priority 1: CAPTURE_RACE_LOSS (semeai pattern - most specific)
    if loss >= THRESHOLD_LOSS_LARGE and has_semeai_pattern:
        return _make_tag(MeaningTagId.CAPTURE_RACE_LOSS)

    # Priority 2: LIFE_DEATH_ERROR
    # Condition A: Huge loss + large ownership flux
    if (
        loss >= THRESHOLD_LOSS_HUGE
        and context is not None
        and context.ownership_flux is not None
        and context.ownership_flux >= THRESHOLD_OWNERSHIP_FLUX_LIFE_DEATH
    ):
        return _make_tag(MeaningTagId.LIFE_DEATH_ERROR)

    # Condition B: Catastrophic loss + (atari OR low_liberties) BUT NOT both
    if (
        loss >= THRESHOLD_LOSS_CATASTROPHIC
        and (has_atari or has_low_liberties)
        and not has_semeai_pattern
    ):
        return _make_tag(MeaningTagId.LIFE_DEATH_ERROR)

    # Priority 3: CONNECTION_MISS
    if has_need_connect and loss >= THRESHOLD_LOSS_MEDIUM:
        return _make_tag(MeaningTagId.CONNECTION_MISS)

    if has_cut_risk and loss >= THRESHOLD_LOSS_CUT_RISK:
        return _make_tag(MeaningTagId.CONNECTION_MISS)

    # Priority 4: READING_FAILURE
    if has_reading_failure:
        return _make_tag(MeaningTagId.READING_FAILURE)

    if (
        context is not None
        and context.actual_move_policy is not None
        and context.actual_move_policy >= THRESHOLD_POLICY_TRAP
        and loss >= THRESHOLD_LOSS_LARGE
    ):
        return _make_tag(MeaningTagId.READING_FAILURE)

    # Priority 5: SHAPE_MISTAKE
    if (
        context is not None
        and context.actual_move_policy is not None
        and context.actual_move_policy < THRESHOLD_POLICY_VERY_LOW
        and loss >= THRESHOLD_LOSS_MEDIUM
    ):
        return _make_tag(MeaningTagId.SHAPE_MISTAKE)

    # Priority 6: DIRECTION_ERROR
    if (
        context is not None
        and context.move_distance is not None
        and context.actual_move_policy is not None
        and move_eval.move_number < THRESHOLD_MOVE_EARLY_GAME
        and context.move_distance >= THRESHOLD_DISTANCE_FAR
        and context.actual_move_policy >= THRESHOLD_POLICY_LOW
        and loss >= THRESHOLD_LOSS_MEDIUM
    ):
        return _make_tag(MeaningTagId.DIRECTION_ERROR)

    # Priority 7: OVERPLAY
    if (
        context is not None
        and context.score_stdev is not None
        and loss >= THRESHOLD_LOSS_LARGE
        and context.score_stdev >= THRESHOLD_SCORE_STDEV_HIGH
    ):
        return _make_tag(MeaningTagId.OVERPLAY)

    if has_heavy_loss and has_chase_mode:
        return _make_tag(MeaningTagId.OVERPLAY)

    # Priority 8: ENDGAME_SLIP
    _is_endgame = is_endgame(
        move_eval.move_number,
        context.total_moves if context else None,
        has_endgame_hint,
    )
    if _is_endgame and THRESHOLD_LOSS_SMALL < loss < THRESHOLD_LOSS_HUGE:
        return _make_tag(MeaningTagId.ENDGAME_SLIP)

    # Priority 9: SLOW_MOVE
    if (
        context is not None
        and context.move_distance is not None
        and THRESHOLD_LOSS_SMALL <= loss < THRESHOLD_LOSS_LARGE
        and context.move_distance < THRESHOLD_DISTANCE_CLOSE
        and not is_urgent
    ):
        return _make_tag(MeaningTagId.SLOW_MOVE)

    # Priority 10: MISSED_TESUJI
    if (
        context is not None
        and context.best_move_policy is not None
        and context.actual_move_policy is not None
        and context.best_move_policy >= THRESHOLD_POLICY_BEST_HIGH
        and context.actual_move_policy < THRESHOLD_POLICY_ACTUAL_LOW
        and loss >= THRESHOLD_LOSS_MEDIUM
    ):
        return _make_tag(MeaningTagId.MISSED_TESUJI)

    # Priority 11: TERRITORIAL_LOSS
    # Re-compute _is_endgame with latest context (already done above)
    if loss >= THRESHOLD_LOSS_MEDIUM and not has_tactical_tags and not _is_endgame:
        return _make_tag(MeaningTagId.TERRITORIAL_LOSS)

    # Priority 11b: Single-tag fallbacks (Phase 66)
    # These catch tactical tags that didn't match higher-priority combination rules.
    #
    # Semantic notes:
    # - READING_FAILURE: single low_liberties implies the player didn't read
    #   the liberty situation correctly.
    # - CAPTURE_RACE_LOSS: single atari implies missed atari awareness.
    # - ENDGAME_SLIP: single endgame_hint in non-endgame-detected positions.
    #
    # Loss thresholds: Using same scale for KataGo (points) and Leela (K-scaled).
    if loss >= THRESHOLD_LOSS_MEDIUM:  # 2.0
        # Single low_liberties (no need_connect, no atari, no cut_risk)
        if (
            has_low_liberties
            and not has_need_connect
            and not has_atari
            and not has_cut_risk
        ):
            return _make_tag(MeaningTagId.READING_FAILURE)

        # Single atari (no low_liberties, no need_connect, no cut_risk)
        if (
            has_atari
            and not has_low_liberties
            and not has_need_connect
            and not has_cut_risk
        ):
            return _make_tag(MeaningTagId.CAPTURE_RACE_LOSS)

    # Single endgame_hint (lower threshold, only if not already detected as endgame)
    if has_endgame_hint and loss >= THRESHOLD_LOSS_SMALL:  # 1.0
        if (
            not has_atari
            and not has_low_liberties
            and not has_need_connect
            and not has_cut_risk
            and not _is_endgame
        ):
            return _make_tag(MeaningTagId.ENDGAME_SLIP)

    # Priority 12: UNCERTAIN (fallback)
    return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="no_match")
