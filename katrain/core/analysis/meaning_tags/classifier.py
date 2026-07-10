"""Meaning Tags Classifier.

This module implements the deterministic rule-based classification system
for assigning meaning tags to MoveEval objects.

Part of Phase 46: Meaning Tags System Core - PR-2.

Public API:
    - ClassificationContext: Additional context for classification
    - classify_meaning_tag(): Main classification function
    - Helper functions: get_loss_value, classify_gtp_move, is_classifiable_move,
                       compute_move_distance, is_endgame
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import MeaningTag, MeaningTagId

if TYPE_CHECKING:
    from katrain.core.analysis.models import MoveEval


# =============================================================================
# Phase C-2: Pre-computed flags (Phase 66 follow-up) extracted to a frozen
# dataclass so the 11-priority chain in :func:`classify_meaning_tag` can
# read pre-computed booleans instead of repeating the same
# ``"foo" in reason_tags`` checks at every priority.
# =============================================================================


@dataclass(frozen=True)
class ClassificationFlags:
    """Boolean flags derived from :attr:`MoveEval.reason_tags`.

    Pre-computed once per call to :func:`classify_meaning_tag` and
    threaded through the priority rules. The composite flags
    (``is_urgent``, ``has_tactical_tags``, ``has_semeai_pattern``) are
    derived from the individual ones so the priority rules only need
    to know the composite.
    """

    has_atari: bool
    has_low_liberties: bool
    has_need_connect: bool
    has_cut_risk: bool
    has_reading_failure: bool
    has_endgame_hint: bool
    has_heavy_loss: bool
    has_chase_mode: bool
    is_urgent: bool
    has_tactical_tags: bool
    has_semeai_pattern: bool


def _extract_classification_flags(reason_tags: list[str] | None) -> ClassificationFlags:
    """Build a :class:`ClassificationFlags` from a reason_tags list.

    The composite flags are derived here so the priority rules do
    not repeat the boolean algebra at every step.
    """
    tags = set(reason_tags) if reason_tags else set()
    has_atari = "atari" in tags
    has_low_liberties = "low_liberties" in tags
    has_need_connect = "need_connect" in tags
    has_cut_risk = "cut_risk" in tags
    has_reading_failure = "reading_failure" in tags
    has_endgame_hint = "endgame_hint" in tags
    has_heavy_loss = "heavy_loss" in tags
    has_chase_mode = "chase_mode" in tags

    return ClassificationFlags(
        has_atari=has_atari,
        has_low_liberties=has_low_liberties,
        has_need_connect=has_need_connect,
        has_cut_risk=has_cut_risk,
        has_reading_failure=has_reading_failure,
        has_endgame_hint=has_endgame_hint,
        has_heavy_loss=has_heavy_loss,
        has_chase_mode=has_chase_mode,
        is_urgent=has_atari or has_low_liberties or has_cut_risk,
        has_tactical_tags=has_atari or has_low_liberties or has_cut_risk or has_need_connect or has_chase_mode,
        has_semeai_pattern=has_atari and has_low_liberties,
    )


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

    best_move_policy: float | None = None
    actual_move_policy: float | None = None
    move_distance: int | None = None
    ownership_flux: float | None = None
    score_stdev: float | None = None
    total_moves: int | None = None


# =============================================================================
# Helper Functions
# =============================================================================


def get_loss_value(move_eval: "MoveEval") -> float | None:
    """Extract loss value from MoveEval.

    Priority (Phase 171: KataGo-only):
        1. score_loss (KataGo)
        2. points_lost (fallback)
        3. None (no loss data)

    Args:
        move_eval: The MoveEval to extract loss from

    Returns:
        float: The loss value, or None if no loss data exists
    """
    if move_eval.score_loss is not None:
        return move_eval.score_loss
    if move_eval.points_lost is not None:
        return move_eval.points_lost
    return None


def classify_gtp_move(gtp: str | None) -> str:
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


def is_classifiable_move(gtp: str | None) -> bool:
    """Check if a move can be classified.

    Args:
        gtp: GTP coordinate string, or None

    Returns:
        True if the move is a normal board coordinate (not pass/resign/missing/empty)
    """
    return classify_gtp_move(gtp) == "normal"


def compute_move_distance(best_gtp: str | None, actual_gtp: str | None) -> int | None:
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

    # coords is (x, y) for placed stones, None for pass (checked above)
    if best_move.coords is None or actual_move.coords is None:
        return None
    bx, by = best_move.coords
    ax, ay = actual_move.coords
    return int(abs(bx - ax) + abs(by - ay))


def is_endgame(move_number: int, total_moves: int | None, has_endgame_hint: bool) -> bool:
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
# Main Classification Function
# =============================================================================


def classify_meaning_tag(
    move_eval: "MoveEval",
    *,
    context: ClassificationContext | None = None,
) -> MeaningTag:
    """Classify a MoveEval into a meaning tag (deterministic).

    This function applies a series of rules in priority order to determine
    the most appropriate semantic tag for a move. The classification is
    completely deterministic: the same inputs always produce the same output.

    Phase C-2: refactored into a 3-step pipeline. The early-return
    gate (``_classify_early_uncertains``), the pre-computed flags
    (``_extract_classification_flags``), and the priority chain
    (``_classify_by_priority``) are now independently testable. Each
    priority rule is a small standalone function returning
    ``Optional[MeaningTag]``.

    Args:
        move_eval: The MoveEval to classify (required)
        context: Additional context (optional, MoveEval-only classification if omitted)

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
    early = _classify_early_uncertains(move_eval)
    if early is not None:
        return early

    loss = get_loss_value(move_eval)
    assert loss is not None  # _classify_early_uncertains verified loss >= significant
    flags = _extract_classification_flags(move_eval.reason_tags)
    endgame_position = is_endgame(
        move_eval.move_number,
        context.total_moves if context else None,
        flags.has_endgame_hint,
    )

    return _classify_by_priority(
        move_eval=move_eval,
        context=context,
        flags=flags,
        loss=loss,
        is_endgame=endgame_position,
    )


# ---------------------------------------------------------------------------
# Phase C-2: helpers extracted from the original 227-line classify_meaning_tag.
# ---------------------------------------------------------------------------


def _classify_early_uncertains(move_eval: "MoveEval") -> MeaningTag | None:
    """Return a UNCERTAIN tag if the move should skip the priority chain.

    Five early-out conditions: missing/empty/pass/resign GTP,
    unreliable analysis, missing loss, and insignificant loss.
    Returns ``None`` when the priority chain should run.
    """
    gtp_class = classify_gtp_move(move_eval.gtp)
    if gtp_class == "missing":
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="gtp_missing")
    if gtp_class == "empty":
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="gtp_empty")
    if gtp_class == "pass":
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="pass_move")
    if gtp_class == "resign":
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="resign_move")

    if not move_eval.is_reliable:
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="unreliable_visits")

    loss = get_loss_value(move_eval)
    if loss is None:
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="loss_data_missing")
    if loss < THRESHOLD_LOSS_SIGNIFICANT:
        return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="no_significant_loss")
    return None


def _classify_by_priority(
    *,
    move_eval: "MoveEval",
    context: ClassificationContext | None,
    flags: ClassificationFlags,
    loss: float,
    is_endgame: bool,
) -> MeaningTag:
    """Run the 11-priority chain. First match wins; falls back to UNCERTAIN.

    Each priority is a small function that returns ``Optional[MeaningTag]``.
    The list is the canonical ordering (most specific to least).
    """
    rules = (
        lambda: _pri_capture_race_loss(loss, flags),
        lambda: _pri_life_death_error(loss, flags, context),
        lambda: _pri_connection_miss(loss, flags),
        lambda: _pri_reading_failure(flags, context, loss),
        lambda: _pri_shape_mistake(context, loss),
        lambda: _pri_direction_error(move_eval, context, loss),
        lambda: _pri_overplay(flags, context, loss),
        lambda: _pri_endgame_slip(is_endgame, loss),
        lambda: _pri_slow_move(context, loss, flags),
        lambda: _pri_missed_tesuji(context, loss),
        lambda: _pri_territorial_loss(loss, flags, is_endgame),
        lambda: _pri_single_tag_fallbacks(loss, flags, is_endgame),
    )
    for rule in rules:
        result = rule()
        if result is not None:
            return result
    return MeaningTag(id=MeaningTagId.UNCERTAIN, debug_reason="no_match")


# Priority rules (1..11b). Each returns ``Optional[MeaningTag]``; the
# first non-None result is selected by ``_classify_by_priority``.
# Parameter ``in_endgame`` (renamed from ``is_endgame``) avoids shadowing
# the imported :func:`is_endgame` helper.


def _pri_capture_race_loss(loss: float, flags: ClassificationFlags) -> MeaningTag | None:
    """Priority 1: semeai pattern (atari + low_liberties) + large loss."""
    if loss >= THRESHOLD_LOSS_LARGE and flags.has_semeai_pattern:
        return MeaningTag(id=MeaningTagId.CAPTURE_RACE_LOSS)
    return None


def _pri_life_death_error(
    loss: float,
    flags: ClassificationFlags,
    context: ClassificationContext | None,
) -> MeaningTag | None:
    """Priority 2: huge loss with ownership flux, or catastrophic loss
    with tactical pressure (but not the semeai pattern)."""
    if (
        loss >= THRESHOLD_LOSS_HUGE
        and context is not None
        and context.ownership_flux is not None
        and context.ownership_flux >= THRESHOLD_OWNERSHIP_FLUX_LIFE_DEATH
    ):
        return MeaningTag(id=MeaningTagId.LIFE_DEATH_ERROR)
    if (
        loss >= THRESHOLD_LOSS_CATASTROPHIC
        and (flags.has_atari or flags.has_low_liberties)
        and not flags.has_semeai_pattern
    ):
        return MeaningTag(id=MeaningTagId.LIFE_DEATH_ERROR)
    return None


def _pri_connection_miss(loss: float, flags: ClassificationFlags) -> MeaningTag | None:
    """Priority 3: need_connect or cut_risk with sufficient loss."""
    if flags.has_need_connect and loss >= THRESHOLD_LOSS_MEDIUM:
        return MeaningTag(id=MeaningTagId.CONNECTION_MISS)
    if flags.has_cut_risk and loss >= THRESHOLD_LOSS_CUT_RISK:
        return MeaningTag(id=MeaningTagId.CONNECTION_MISS)
    return None


def _pri_reading_failure(
    flags: ClassificationFlags,
    context: ClassificationContext | None,
    loss: float,
) -> MeaningTag | None:
    """Priority 4: explicit reading_failure, or a high-policy trap move."""
    if flags.has_reading_failure:
        return MeaningTag(id=MeaningTagId.READING_FAILURE)
    if (
        context is not None
        and context.actual_move_policy is not None
        and context.actual_move_policy >= THRESHOLD_POLICY_TRAP
        and loss >= THRESHOLD_LOSS_LARGE
    ):
        return MeaningTag(id=MeaningTagId.READING_FAILURE)
    return None


def _pri_shape_mistake(context: ClassificationContext | None, loss: float) -> MeaningTag | None:
    """Priority 5: very-low actual-move policy implies KataGo hated the shape."""
    if (
        context is not None
        and context.actual_move_policy is not None
        and context.actual_move_policy < THRESHOLD_POLICY_VERY_LOW
        and loss >= THRESHOLD_LOSS_MEDIUM
    ):
        return MeaningTag(id=MeaningTagId.SHAPE_MISTAKE)
    return None


def _pri_direction_error(
    move_eval: "MoveEval",
    context: ClassificationContext | None,
    loss: float,
) -> MeaningTag | None:
    """Priority 6: early-game far move with low policy and a meaningful loss."""
    if (
        context is not None
        and context.move_distance is not None
        and context.actual_move_policy is not None
        and move_eval.move_number < THRESHOLD_MOVE_EARLY_GAME
        and context.move_distance >= THRESHOLD_DISTANCE_FAR
        and context.actual_move_policy >= THRESHOLD_POLICY_LOW
        and loss >= THRESHOLD_LOSS_MEDIUM
    ):
        return MeaningTag(id=MeaningTagId.DIRECTION_ERROR)
    return None


def _pri_overplay(
    flags: ClassificationFlags,
    context: ClassificationContext | None,
    loss: float,
) -> MeaningTag | None:
    """Priority 7: high score_stdev + large loss, or heavy_loss + chase_mode."""
    if (
        context is not None
        and context.score_stdev is not None
        and loss >= THRESHOLD_LOSS_LARGE
        and context.score_stdev >= THRESHOLD_SCORE_STDEV_HIGH
    ):
        return MeaningTag(id=MeaningTagId.OVERPLAY)
    if flags.has_heavy_loss and flags.has_chase_mode:
        return MeaningTag(id=MeaningTagId.OVERPLAY)
    return None


def _pri_endgame_slip(in_endgame: bool, loss: float) -> MeaningTag | None:
    """Priority 8: end-position slip with moderate (not huge) loss."""
    if in_endgame and THRESHOLD_LOSS_SMALL < loss < THRESHOLD_LOSS_HUGE:
        return MeaningTag(id=MeaningTagId.ENDGAME_SLIP)
    return None


def _pri_slow_move(
    context: ClassificationContext | None,
    loss: float,
    flags: ClassificationFlags,
) -> MeaningTag | None:
    """Priority 9: small/medium loss on a position close to a previous
    move (no urgent tactical pressure)."""
    if (
        context is not None
        and context.move_distance is not None
        and THRESHOLD_LOSS_SMALL <= loss < THRESHOLD_LOSS_LARGE
        and context.move_distance < THRESHOLD_DISTANCE_CLOSE
        and not flags.is_urgent
    ):
        return MeaningTag(id=MeaningTagId.SLOW_MOVE)
    return None


def _pri_missed_tesuji(context: ClassificationContext | None, loss: float) -> MeaningTag | None:
    """Priority 10: best move was obvious and KataGo didn't pick it."""
    if (
        context is not None
        and context.best_move_policy is not None
        and context.actual_move_policy is not None
        and context.best_move_policy >= THRESHOLD_POLICY_BEST_HIGH
        and context.actual_move_policy < THRESHOLD_POLICY_ACTUAL_LOW
        and loss >= THRESHOLD_LOSS_MEDIUM
    ):
        return MeaningTag(id=MeaningTagId.MISSED_TESUJI)
    return None


def _pri_territorial_loss(
    loss: float,
    flags: ClassificationFlags,
    in_endgame: bool,
) -> MeaningTag | None:
    """Priority 11: medium+ loss without tactical / endgame markers."""
    if loss >= THRESHOLD_LOSS_MEDIUM and not flags.has_tactical_tags and not in_endgame:
        return MeaningTag(id=MeaningTagId.TERRITORIAL_LOSS)
    return None


def _pri_single_tag_fallbacks(
    loss: float,
    flags: ClassificationFlags,
    in_endgame: bool,
) -> MeaningTag | None:
    """Priority 11b: catch tactical tags that didn't match higher priorities.

    Semantic notes:
    - READING_FAILURE: single low_liberties implies the player didn't
      read the liberty situation correctly.
    - CAPTURE_RACE_LOSS: single atari implies missed atari awareness.
    - ENDGAME_SLIP: single endgame_hint in non-endgame-detected positions.
    """
    if loss >= THRESHOLD_LOSS_MEDIUM:
        if flags.has_low_liberties and not flags.has_need_connect and not flags.has_atari and not flags.has_cut_risk:
            return MeaningTag(id=MeaningTagId.READING_FAILURE)
        if flags.has_atari and not flags.has_low_liberties and not flags.has_need_connect and not flags.has_cut_risk:
            return MeaningTag(id=MeaningTagId.CAPTURE_RACE_LOSS)

    if (
        flags.has_endgame_hint
        and loss >= THRESHOLD_LOSS_SMALL
        and not flags.has_atari
        and not flags.has_low_liberties
        and not flags.has_need_connect
        and not flags.has_cut_risk
        and not in_endgame
    ):
        return MeaningTag(id=MeaningTagId.ENDGAME_SLIP)
    return None
