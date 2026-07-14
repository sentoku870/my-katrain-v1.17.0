"""Phase 179 / 182: node-attribute extractors.

Phase 196 extraction: helpers that pull ``predicted_territory`` /
``best_policy`` / endgame signal out of a :class:`GameNode` without
touching the rest of the pipeline. Pure functions, no side effects.
"""

from __future__ import annotations

from typing import Any


def _extract_predicted_territory(node: Any) -> float | None:
    """Phase 182: derive a single-sided territory signal from
    ``node.ownership``.

    The ownership grid is a flat list with one value per cell:
    +1 = that cell is fully owned by Black (per KataGo's JSON convention),
    -1 = fully White, 0 = neutral. Summing all cells and dividing by the
    cell count gives ``predicted_territory`` in ``[-1.0, +1.0]`` where
    +1 means Black owns 100% of the board, -1 means White owns 100%.
    Beginners benefit from this single signed scalar far more than from
    a 361-cell grid.

    Args:
        node: GameNode.

    Returns:
        Normalised territory in [-1.0, +1.0], or None when ownership is
        unavailable (config disabled, analysis missing, or malformed).
    """
    ownership = getattr(node, "ownership", None)
    if not ownership:
        return None
    values: list[float] = []
    for v in ownership:
        if v is None:
            continue
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return sum(values) / len(values)


def _extract_best_policy(node: Any) -> float | None:
    """Phase 182: extract the maximum probability from ``node.policy``.

    The policy distribution is a flat list of probabilities (one per
    cell, summing to ~1). The maximum value indicates how confident
    KataGo's policy network is about its top choice. Range 0..1.

    Args:
        node: GameNode.

    Returns:
        Maximum policy probability in [0.0, 1.0], or None when policy is
        unavailable (analysis missing, or empty / malformed list).
    """
    policy = getattr(node, "policy", None)
    if not policy:
        return None
    best = 0.0
    for v in policy:
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f > best:
            best = f
    return best if best > 0.0 else None


def _is_endgame_position(node: Any) -> bool:
    """Phase 179.2: endgame heuristic for MISTAKE_GOOD gating.

    Returns True when the node is in (or very close to) the endgame. Two
    signals are combined:

    1. **Dynamic (primary)**: KataGo's ``scoreStdev`` is at or below
       ``ENDGAME_SCORE_STDEV_THRESHOLD`` (8.0). This is the same
       threshold used by ``analysis.logic_phase_dynamic`` (Phase 156-A
       / 158-G) for the dynamic phase classifier — when KataGo has
       effectively read the position out, the game is likely in the
       endgame.
    2. **Static (fallback)**: ``move_number >= 200`` for legacy /
       short-game compatibility. Used only when ``scoreStdev`` is
       unavailable (no analysis yet, batch mode without stdev).

    The previous static-only check (Phase 179.1, ``move_number >= 200``)
    fired for middle-game persistence fights on 19x19 boards because
    long sequences of small skirmishes can stay below 200 moves; in
    those positions MISTAKE_GOOD ("良い手") praise would mislead
    beginners.

    Args:
        node: GameNode.

    Returns:
        True if the position is plausibly in the endgame.
    """
    from katrain.core.analysis import get_score_stdev
    from katrain.core.analysis.logic_phase_dynamic import ENDGAME_SCORE_STDEV_THRESHOLD

    stdev_val = get_score_stdev(node)
    if stdev_val is not None:
        return float(stdev_val) <= float(ENDGAME_SCORE_STDEV_THRESHOLD)

    move_number = 0
    if getattr(node, "move", None) is not None:
        move_number = int(getattr(node.move, "move_number", 0) or 0)
    if move_number == 0:
        depth = getattr(node, "depth", 0) or 0
        move_number = int(depth)
    return move_number >= 200
