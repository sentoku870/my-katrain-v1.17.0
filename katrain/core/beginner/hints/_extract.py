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


# Phase 252: per-board-size move-number threshold for the static
# fallback in ``_is_endgame_position``. 9x9 games rarely exceed 80
# moves, so a 200-move threshold would never fire on a small board.
# 13x13 sits between; 19x19 keeps the Phase 179.2 default.
_ENDGAME_MOVE_THRESHOLD_BY_SIZE: dict[int, int] = {
    9: 60,
    13: 100,
    19: 200,
}


def endgame_move_threshold_for_board_size(
    board_size: int | tuple[int, int] | None,
) -> int:
    """Phase 252: return the static-fallback move threshold for endgame gating.

    Falls back to ``200`` for unknown sizes (rectangular, custom,
    ``None``) so legacy callers and tests preserve their pre-Phase-252
    behaviour.

    Args:
        board_size: Either an int (square board) or a ``(width, height)``
            tuple. ``None`` falls back to the 19x19 default.

    Returns:
        The move-number threshold (>= 1).
    """
    if board_size is None:
        return _ENDGAME_MOVE_THRESHOLD_BY_SIZE[19]
    if isinstance(board_size, (tuple, list)):
        if not board_size:
            return _ENDGAME_MOVE_THRESHOLD_BY_SIZE[19]
        try:
            size = min(int(board_size[0]), int(board_size[1] or board_size[0]))
        except (TypeError, ValueError):
            return _ENDGAME_MOVE_THRESHOLD_BY_SIZE[19]
    else:
        try:
            size = int(board_size)
        except (TypeError, ValueError):
            return _ENDGAME_MOVE_THRESHOLD_BY_SIZE[19]
    return _ENDGAME_MOVE_THRESHOLD_BY_SIZE.get(size, _ENDGAME_MOVE_THRESHOLD_BY_SIZE[19])


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
    2. **Static (fallback)**: ``move_number >= THRESHOLD`` where
       ``THRESHOLD`` is board-size-aware (Phase 252: 60 for 9x9, 100
       for 13x13, 200 for 19x19). Used only when ``scoreStdev`` is
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

    # Phase 252: scale the static-fallback threshold by board size.
    board_size = None
    try:
        parent = getattr(node, "parent", None)
        game = getattr(parent, "game", None) if parent is not None else None
        if game is not None:
            board_size = getattr(game, "board_size", None)
    except Exception:
        board_size = None
    return move_number >= endgame_move_threshold_for_board_size(board_size)
