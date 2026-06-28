"""Dynamic phase classification (Phase 156-A).

Phase 156 introduces a scoreStdev-based endgame detector that augments the
fixed ``51-200 / 200+`` split (see :mod:`katrain.core.analysis.logic_phase`).

Rationale:
    The fixed split is easy to predict but misclassifies short games and
    games with unusually long openings. KataGo's ``scoreStdev`` is a
    natural signal: it drops toward zero when the position has been
    "read out" (typical endgame behavior on a fully settled board).
    Tracking when the stdev stays below a small threshold for a
    contiguous window yields a more accurate endgame boundary.

Algorithm:
    1. Walk the moves chronologically with their ``score_stdev`` value
       (may be None for Leela / unanalyzed moves).
    2. Skip moves whose ``score_stdev`` is missing (they remain
       "middle" until proven otherwise).
    3. Once ``score_stdev`` has been ``<= ENDGAME_SCORE_STDEV_THRESHOLD``
       for ``ENDGAME_DETECTION_WINDOW`` consecutive moves, classify
       subsequent moves as ``"endgame"`` (with the legacy alias
       ``"yose"`` also returned for back-compat consumers).
    4. Within the first ``opening_end`` moves, fall back to the fixed
       thresholds so openings remain consistent with the static
       classifier.

This module is intentionally decoupled from any I/O: callers feed a
sequence of moves and receive a per-move phase label.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from katrain.core.analysis.logic_phase import classify_game_phase, get_phase_thresholds

if TYPE_CHECKING:
    from katrain.core.analysis.models import MoveEval


#: scoreStdev at or below this value is considered "read out" (endgame signal).
ENDGAME_SCORE_STDEV_THRESHOLD: float = 5.0

#: Number of consecutive moves the stdev must remain low to trigger
#: endgame classification.
ENDGAME_DETECTION_WINDOW: int = 5


def _phase_static(move_number: int, board_size: int = 19) -> str:
    """Wrapper around :func:`classify_game_phase` for clarity at call sites."""
    return classify_game_phase(move_number, board_size)


def classify_phases_dynamic(
    moves: Sequence["MoveEval"],
    *,
    board_size: int = 19,
    endgame_threshold: float = ENDGAME_SCORE_STDEV_THRESHOLD,
    endgame_window: int = ENDGAME_DETECTION_WINDOW,
) -> list[str]:
    """Return a phase label for each move using the dynamic endgame detector.

    Args:
        moves: Chronologically ordered moves. Each entry may carry
            ``score_stdev`` (None when missing).
        board_size: Board size for the fixed opening fallback.
        endgame_threshold: Maximum ``score_stdev`` to count a move as
            "endgame-eligible".
        endgame_window: Required number of consecutive stdev-below
            moves to flip into endgame mode.

    Returns:
        List of phase labels (same length as ``moves``). Each label is
        one of ``"opening"``, ``"middle"``, ``"endgame"``, or ``"yose"``
        (legacy alias for ``"endgame"``).
    """
    if endgame_window <= 0:
        raise ValueError(f"endgame_window must be positive, got {endgame_window}")

    opening_end, _ = get_phase_thresholds(board_size)
    phases: list[str] = []
    low_streak = 0
    endgame_active = False

    for mv in moves:
        # Static opening window: always trust the fixed threshold.
        if mv.move_number <= opening_end:
            phases.append("opening")
            continue
        # Once endgame is locked in, stay there for the rest of the game.
        if endgame_active:
            phases.append("endgame")
            continue
        # Need a real (non-None) score_stdev value to advance the detector.
        if mv.score_stdev is None:
            phases.append(_phase_static(mv.move_number, board_size))
            low_streak = 0
            continue
        if mv.score_stdev <= endgame_threshold:
            low_streak += 1
        else:
            low_streak = 0
        if low_streak >= endgame_window:
            endgame_active = True
            phases.append("endgame")
            continue
        phases.append(_phase_static(mv.move_number, board_size))

    return phases


def it_consistent_with_static(
    static_phases: Iterable[str],
    dynamic_phases: Iterable[str],
) -> bool:
    """Quick sanity check: both classifiers agreed on every move.

    Used by tests to verify the dynamic classifier does not contradict
    the static one in cases where scoreStdev is unavailable.
    """
    return list(static_phases) == list(dynamic_phases)


def apply_dynamic_phases(
    moves: Sequence["MoveEval"],
    *,
    board_size: int = 19,
    endgame_threshold: float = ENDGAME_SCORE_STDEV_THRESHOLD,
    endgame_window: int = ENDGAME_DETECTION_WINDOW,
) -> None:
    """In-place: rewrite ``move.tag`` using the dynamic phase classifier.

    This is the convenience entry point used by Karte / Summary builders
    when the user opts in to dynamic phase detection. Tags are written
    in place so existing downstream aggregation (``phase_mistake_counts``
    etc.) picks up the new phase labels without further plumbing.

    Args:
        moves: Moves whose ``tag`` attribute should be updated.
        board_size: Board size for the fixed opening fallback.
        endgame_threshold: Same as :func:`classify_phases_dynamic`.
        endgame_window: Same as :func:`classify_phases_dynamic`.

    Note:
        Aliases ``"yose"`` and ``"endgame"`` are both written for callers
        that hard-code one of the two spellings; downstream aggregators
        normalize via :data:`katrain.core.reports.definitions.PHASE_ALIASES`.
    """
    phases = classify_phases_dynamic(
        moves,
        board_size=board_size,
        endgame_threshold=endgame_threshold,
        endgame_window=endgame_window,
    )
    for mv, phase in zip(moves, phases):
        mv.tag = phase