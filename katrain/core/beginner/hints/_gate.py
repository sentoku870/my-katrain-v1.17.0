"""Phase 92 + 92c: gating and validation pure functions.

Phase 196 extraction: kept as a thin module so callers / tests that
relied on ``from katrain.core.beginner.hints import should_show_*``
continue to work through the legacy shim in ``katrain/core/beginner/hints.py``.
"""

from __future__ import annotations

# Phase 92: Reliability filter constant for structural hints.
MIN_RELIABLE_VISITS = 200


def _normalize_board_size(board_size: int | tuple[int, int]) -> tuple[int, int]:
    """Normalize board_size to (width, height) tuple.

    Args:
        board_size: Either int (square board) or (width, height) tuple.

    Returns:
        Tuple of (width, height).
    """
    if isinstance(board_size, int):
        return (board_size, board_size)
    return board_size


def should_show_beginner_hints(enabled: bool, mode: str) -> bool:
    """Check if beginner hints should be shown (pure function).

    Args:
        enabled: beginner_hints/enabled config value
        mode: Current play_analyze_mode

    Returns:
        True if hints should be displayed.
    """
    from katrain.core.constants import MODE_PLAY

    if not enabled:
        return False
    return mode != MODE_PLAY


def should_show_summary_hint(
    enabled: bool,
    mode: str,
    summary_key: str,
    summary_flags: dict[str, bool] | None,
) -> bool:
    """Phase 179: gate a summary hint category group.

    Args:
        enabled: beginner_hints/enabled (master switch).
        mode: Current play_analyze_mode.
        summary_key: One of "summary_mistake", "summary_freedom",
            "summary_difficulty", "katago_uncertain".
        summary_flags: Dict of summary_key -> bool. Missing keys default
            to True (preserve existing behavior for users who upgrade).

    Returns:
        True if the summary hint category group should be displayed.
    """
    if not should_show_beginner_hints(enabled, mode):
        return False
    if not summary_flags:
        return True
    return bool(summary_flags.get(summary_key, True))


def should_draw_board_highlight(
    enabled: bool,
    mode: str,
    board_highlight: bool,
) -> bool:
    """Check if board highlight should be drawn (pure function).

    Args:
        enabled: beginner_hints/enabled config value
        mode: Current play_analyze_mode
        board_highlight: beginner_hints/board_highlight config value

    Returns:
        True if highlight should be drawn.
    """
    if not should_show_beginner_hints(enabled, mode):
        return False
    return board_highlight


def is_coords_valid(
    coords: tuple[int, int] | None,
    board_size: int | tuple[int, int],
) -> bool:
    """Check if coords are valid for the given board size (pure function).

    Args:
        coords: (x, y) coordinates or None
        board_size: Board size (int or tuple)

    Returns:
        True if coords are within bounds.
    """
    if coords is None:
        return False
    x, y = coords
    board_size_x, board_size_y = _normalize_board_size(board_size)
    return 0 <= x < board_size_x and 0 <= y < board_size_y
