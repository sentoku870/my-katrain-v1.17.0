"""Pure geometry/visual logic for the BadukPan widget.

Phase 140: Extracted from katrain/gui/badukpan.py to enable unit testing
without Kivy dependencies.

All functions in this module are pure: they take their inputs as explicit
parameters and return values without side effects or hidden state.

The wrapper methods in BadukPanWidget continue to work as before but
delegate to these functions. Tests should target this module directly.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from katrain.core.utils import evaluation_class

if TYPE_CHECKING:
    from katrain.core.sgf_parser import Move

__all__ = [
    "compute_board_with_margins",
    "compute_extra_px_margins",
    "compute_grid_size",
    "compute_grid_spaces",
    "compute_initial_gridpos",
    "compute_stone_size",
    "eval_color",
    "find_closest_grid_point",
    "format_leela_stat",
    "format_loss",
    "x_coordinate_text",
    "y_coordinate_text",
]


def compute_grid_spaces(
    board_size_x: int, board_size_y: int, margin_x: list[float], margin_y: list[float]
) -> tuple[float, float]:
    """Compute x/y grid space counts from board size and margins.

    Returns:
        (x_grid_spaces, y_grid_spaces) - total grid spaces including margins.
    """
    return (
        board_size_x - 1 + sum(margin_x),
        board_size_y - 1 + sum(margin_y),
    )


def compute_grid_size(
    width: float, height: float, x_grid_spaces: float, y_grid_spaces: float
) -> int:
    """Compute integer grid size that fits the available area.

    The +0.1 floor is intentional: it prevents rounding errors that would
    produce tiny gaps between shaded grid squares.
    """
    return math.floor(min(width / x_grid_spaces, height / y_grid_spaces) + 0.1)


def compute_board_with_margins(
    x_grid_spaces: float, y_grid_spaces: float, grid_size: float
) -> tuple[float, float]:
    """Compute the actual board width/height after applying grid_size."""
    return (x_grid_spaces * grid_size, y_grid_spaces * grid_size)


def compute_extra_px_margins(
    width: float, height: float, board_width: float, board_height: float
) -> tuple[float, float]:
    """Compute the extra pixel margins to center the board."""
    return (
        round((width - board_width) / 2, 4),
        round((height - board_height) / 2, 4),
    )


def compute_stone_size(grid_size: float, stone_size_factor: float) -> float:
    """Compute the stone size from the grid size and a scaling factor."""
    return grid_size * stone_size_factor


def compute_initial_gridpos(
    pos_xy: tuple[float, float],
    board_size_x: int,
    board_size_y: int,
    margin_x: list[float],
    margin_y: list[float],
    extra_px_margin_x: float,
    extra_px_margin_y: float,
    grid_size: float,
) -> tuple[list[float], list[float]]:
    """Compute the initial grid positions (x and y arrays).

    Each entry is rounded to 4 decimals to keep coordinates stable.
    """
    pos_x, pos_y = pos_xy
    gridpos_x = [
        round(
            pos_x + extra_px_margin_x + math.floor((margin_x[0] + i) * grid_size + 0.5),
            4,
        )
        for i in range(board_size_x)
    ]
    gridpos_y = [
        round(
            pos_y + extra_px_margin_y + math.floor((margin_y[0] + i) * grid_size + 0.5),
            4,
        )
        for i in range(board_size_y)
    ]
    return gridpos_x, gridpos_y


def format_loss(x: float, extra_precision: bool = False) -> str:
    """Format a score-loss value for display.

    With extra_precision, the output uses 2 decimals with sign; otherwise
    1 decimal with sign.
    """
    if extra_precision:
        if abs(x) < 0.005:
            return "0.0"
        if 0 < x <= 0.995:
            return "+" + f"{x:.2f}"[1:]
        if -0.995 <= x < 0:
            return "-" + f"{x:.2f}"[2:]
    return f"{x:+.1f}"


def eval_color(
    points_lost: float,
    eval_thresholds: list[float],
    eval_colors: list[list[float]],
    show_dots_for_class: list[bool] | None = None,
) -> list[float] | None:
    """Return the RGBA color for a points-lost value, or None if the row is hidden.

    Args:
        points_lost: KataGo loss in points.
        eval_thresholds: List of thresholds in descending order (worst first).
        eval_colors: Theme.EVAL_COLORS[theme] - list of RGBA color rows.
        show_dots_for_class: Optional per-class visibility flags. If given and
            a row is False, the row is treated as "no dot" and returns None.
    """
    i = evaluation_class(points_lost, eval_thresholds)
    if show_dots_for_class is None or show_dots_for_class[i]:
        return eval_colors[i]
    return None


def x_coordinate_text(i: int, board_size_x: int, rotation_degree: int, gtp_coord: list[str]) -> str:
    """Return the label text for an x coordinate given the rotation."""
    if rotation_degree == 90:
        return str(i + 1)
    if rotation_degree == 180:
        return gtp_coord[board_size_x - i - 1]
    if rotation_degree == 270:
        return str(board_size_x - i)
    return gtp_coord[i]


def y_coordinate_text(i: int, board_size_y: int, rotation_degree: int, gtp_coord: list[str]) -> str:
    """Return the label text for a y coordinate given the rotation."""
    if rotation_degree == 90:
        return gtp_coord[board_size_y - i - 1]
    if rotation_degree == 180:
        return str(board_size_y - i)
    if rotation_degree == 270:
        return gtp_coord[i]
    return str(i + 1)


def find_closest_grid_point(
    pos_x: float,
    pos_y: float,
    gridpos_x: list[float],
    gridpos_y: list[float],
) -> tuple[float, int, float, int] | None:
    """Find the closest grid intersection to a pixel coordinate.

    Returns:
        (closest_x, idx_x, closest_y, idx_y) or None when the input lists
        are empty. idx_* are indices into gridpos_*.
    """
    if not gridpos_x or not gridpos_y:
        return None
    cx = min(gridpos_x, key=lambda v: abs(v - pos_x))
    cy = min(gridpos_y, key=lambda v: abs(v - pos_y))
    return (cx, gridpos_x.index(cx), cy, gridpos_y.index(cy))


def format_leela_stat(candidate: Any, stat_type: str) -> str:
    """Format a single Leela stat (e.g. visits, winrate, score) for display.

    Args:
        candidate: A LeelaCandidate-like object exposing a ``stats`` dict
            (or any object whose ``stats[stat_type]`` returns the value).
        stat_type: Stat key, one of the LEELA_TOP_MOVE_* constants.

    Returns:
        Formatted string, or "" when the value is None.
    """
    NOTHING = ""
    val = candidate.stats.get(stat_type)
    if val is None:
        return NOTHING
    if stat_type in ("LEELA_TOP_MOVE_VISITS", "LEELA_TOP_MOVE_RAW_VISITS"):
        return f"{int(val):d}"
    if stat_type in (
        "LEELA_TOP_MOVE_WINRATE",
        "LEELA_TOP_MOVE_RELATIVE_WINRATE",
    ):
        return f"{val * 100:.1f}%"
    if stat_type == "LEELA_TOP_MOVE_SCORE":
        return f"{val:+.1f}"
    return str(val)
