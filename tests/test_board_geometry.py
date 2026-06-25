"""Tests for katrain.core.board_geometry module.

Phase 140: Pure-geometry unit tests. No Kivy imports.
"""
from dataclasses import dataclass, field
from typing import Any

import pytest

from katrain.core.board_geometry import (
    compute_board_with_margins,
    compute_extra_px_margins,
    compute_grid_size,
    compute_grid_spaces,
    compute_initial_gridpos,
    compute_stone_size,
    eval_color,
    find_closest_grid_point,
    format_leela_stat,
    format_loss,
    x_coordinate_text,
    y_coordinate_text,
)
from katrain.core.utils import evaluation_class


# =============================================================================
# compute_grid_spaces
# =============================================================================


class TestComputeGridSpaces:
    @pytest.mark.parametrize(
        "bsx,bsy,mx,my,expected",
        [
            (19, 19, [0.0, 0.0], [0.0, 0.0], (18.0, 18.0)),
            (13, 13, [0.0, 0.0], [0.0, 0.0], (12.0, 12.0)),
            (9, 9, [0.0, 0.0], [0.0, 0.0], (8.0, 8.0)),
            (5, 5, [0.0, 0.0], [0.0, 0.0], (4.0, 4.0)),
            (1, 1, [0.0, 0.0], [0.0, 0.0], (0.0, 0.0)),
            (19, 19, [0.5, 0.5], [0.5, 0.5], (19.0, 19.0)),
            (19, 13, [0.0, 0.0], [0.0, 0.0], (18.0, 12.0)),
        ],
    )
    def test_grid_spaces(self, bsx, bsy, mx, my, expected):
        assert compute_grid_spaces(bsx, bsy, mx, my) == expected

    def test_grid_spaces_with_margins(self):
        # 19x19 board with extra margins of 1 + 1 = 2
        assert compute_grid_spaces(19, 19, [1.0, 1.0], [1.0, 1.0]) == (20.0, 20.0)


# =============================================================================
# compute_grid_size
# =============================================================================


class TestComputeGridSize:
    def test_square_area(self):
        # 360x360 with 18 grid spaces -> 20 px per cell
        size = compute_grid_size(360.0, 360.0, 18.0, 18.0)
        assert size == 20

    def test_asymmetric_area(self):
        # Width is the limiting dimension
        size = compute_grid_size(180.0, 360.0, 18.0, 18.0)
        assert size == 10

    def test_height_limiting(self):
        size = compute_grid_size(360.0, 90.0, 18.0, 18.0)
        assert size == 5

    def test_returns_integer(self):
        size = compute_grid_size(100.0, 100.0, 18.0, 18.0)
        assert isinstance(size, int)

    def test_zero_spaces_raises(self):
        with pytest.raises(ZeroDivisionError):
            compute_grid_size(100.0, 100.0, 0.0, 18.0)


# =============================================================================
# compute_board_with_margins
# =============================================================================


class TestComputeBoardWithMargins:
    def test_basic(self):
        assert compute_board_with_margins(18.0, 18.0, 20.0) == (360.0, 360.0)

    def test_asymmetric(self):
        assert compute_board_with_margins(18.0, 12.0, 10.0) == (180.0, 120.0)

    def test_zero(self):
        assert compute_board_with_margins(0.0, 0.0, 0.0) == (0.0, 0.0)


# =============================================================================
# compute_extra_px_margins
# =============================================================================


class TestComputeExtraPxMargins:
    def test_square_centered(self):
        # 400x400 with 360x360 board -> 20 each side
        x, y = compute_extra_px_margins(400.0, 400.0, 360.0, 360.0)
        assert x == 20.0
        assert y == 20.0

    def test_rounded_to_4_decimals(self):
        # Width diff = 33 / 2 = 16.5
        x, _ = compute_extra_px_margins(393.0, 400.0, 360.0, 360.0)
        assert x == 16.5
        assert isinstance(x, float)

    def test_zero_when_perfect_fit(self):
        x, y = compute_extra_px_margins(360.0, 360.0, 360.0, 360.0)
        assert x == 0.0
        assert y == 0.0


# =============================================================================
# compute_stone_size
# =============================================================================


class TestComputeStoneSize:
    def test_default_factor(self):
        # Theme.STONE_SIZE ~ 0.95
        assert compute_stone_size(20.0, 0.95) == 19.0

    def test_factor_one(self):
        assert compute_stone_size(20.0, 1.0) == 20.0

    def test_factor_zero(self):
        assert compute_stone_size(20.0, 0.0) == 0.0


# =============================================================================
# compute_initial_gridpos
# =============================================================================


class TestComputeInitialGridpos:
    def test_19x19_basic(self):
        gx, gy = compute_initial_gridpos(
            pos_xy=(0.0, 0.0),
            board_size_x=19,
            board_size_y=19,
            margin_x=[0.0, 0.0],
            margin_y=[0.0, 0.0],
            extra_px_margin_x=10.0,
            extra_px_margin_y=10.0,
            grid_size=20.0,
        )
        assert len(gx) == 19
        assert len(gy) == 19
        # First coord = pos + extra_margin + floor(0*grid + 0.5) = 10.0
        assert gx[0] == 10.0
        assert gy[0] == 10.0
        # Second coord = pos + extra_margin + floor(1*20 + 0.5) = 30.0
        assert gx[1] == 30.0
        assert gy[1] == 30.0

    def test_rounding_to_4_decimals(self):
        gx, _ = compute_initial_gridpos(
            pos_xy=(0.0, 0.0),
            board_size_x=2,
            board_size_y=2,
            margin_x=[0.0, 0.0],
            margin_y=[0.0, 0.0],
            extra_px_margin_x=0.0,
            extra_px_margin_y=0.0,
            grid_size=20.0,
        )
        for v in gx:
            assert round(v, 4) == v  # No trailing decimals > 4

    def test_positive_pos(self):
        gx, _ = compute_initial_gridpos(
            pos_xy=(100.0, 50.0),
            board_size_x=3,
            board_size_y=3,
            margin_x=[0.0, 0.0],
            margin_y=[0.0, 0.0],
            extra_px_margin_x=5.0,
            extra_px_margin_y=5.0,
            grid_size=10.0,
        )
        assert gx[0] == 105.0
        assert gx[2] == 125.0

    def test_with_extra_margin(self):
        gx, _ = compute_initial_gridpos(
            pos_xy=(0.0, 0.0),
            board_size_x=3,
            board_size_y=3,
            margin_x=[0.5, 0.0],  # half-cell before
            margin_y=[0.0, 0.0],
            extra_px_margin_x=0.0,
            extra_px_margin_y=0.0,
            grid_size=10.0,
        )
        # i=0: floor((0.5+0)*10 + 0.5) = floor(5.5) = 5
        assert gx[0] == 5.0
        # i=1: floor((0.5+1)*10 + 0.5) = floor(15.5) = 15
        assert gx[1] == 15.0


# =============================================================================
# format_loss
# =============================================================================


class TestFormatLoss:
    def test_zero_default_precision(self):
        assert format_loss(0.0) == "+0.0"

    def test_positive_default_precision(self):
        assert format_loss(1.5) == "+1.5"

    def test_negative_default_precision(self):
        assert format_loss(-2.3) == "-2.3"

    def test_extra_precision_zero(self):
        assert format_loss(0.0, extra_precision=True) == "0.0"

    def test_extra_precision_tiny(self):
        # |x| < 0.005 -> 0.0
        assert format_loss(0.001, extra_precision=True) == "0.0"
        assert format_loss(-0.001, extra_precision=True) == "0.0"

    def test_extra_precision_small_positive(self):
        # 0 < x <= 0.995
        assert format_loss(0.5, extra_precision=True) == "+.50"
        assert format_loss(0.95, extra_precision=True) == "+.95"

    def test_extra_precision_small_negative(self):
        # -0.995 <= x < 0
        assert format_loss(-0.5, extra_precision=True) == "-.50"
        assert format_loss(-0.95, extra_precision=True) == "-.95"

    def test_extra_precision_large(self):
        # Falls through to default format
        assert format_loss(5.0, extra_precision=True) == "+5.0"
        assert format_loss(-10.0, extra_precision=True) == "-10.0"

    def test_extra_precision_boundary(self):
        # 0.995 boundary inclusive
        assert format_loss(0.995, extra_precision=True) == "+.99"  # 0.995 -> "0.99" or "1.00" depending on banker's rounding
        # 1.0 is over the threshold, falls to default
        assert format_loss(1.0, extra_precision=True) == "+1.0"


# =============================================================================
# evaluation_class
# =============================================================================


class TestEvaluationClass:
    # Default trainer thresholds: [12.0, 6.0, 3.0, 1.5, 0.5, 0.0]
    THRESHOLDS = [12.0, 6.0, 3.0, 1.5, 0.5, 0.0]

    def test_very_large_loss(self):
        assert evaluation_class(20.0, self.THRESHOLDS) == 0

    def test_threshold_boundary(self):
        # points_lost == 12.0 -> index 0
        assert evaluation_class(12.0, self.THRESHOLDS) == 0

    def test_moderate_loss(self):
        # 3.0 <= x < 6.0 -> index 2
        assert evaluation_class(5.0, self.THRESHOLDS) == 2

    def test_small_loss(self):
        # 1.5 <= x < 3.0 -> index 3
        assert evaluation_class(2.0, self.THRESHOLDS) == 3

    def test_zero_loss(self):
        # 0.0 <= x < 0.5 -> index 5 (last)
        assert evaluation_class(0.0, self.THRESHOLDS) == 5

    def test_negative_loss_returns_last(self):
        # Negative falls through to last
        assert evaluation_class(-1.0, self.THRESHOLDS) == 5

    def test_just_above_zero(self):
        # 0.5 <= x < 1.5 -> index 4
        assert evaluation_class(0.5, self.THRESHOLDS) == 4


# =============================================================================
# eval_color
# =============================================================================


class TestEvalColor:
    THRESHOLDS = [12.0, 6.0, 3.0, 1.5, 0.5, 0.0]
    COLORS = [
        [1, 0, 0, 1],  # 0: red
        [1, 0.5, 0, 1],  # 1: orange
        [1, 1, 0, 1],  # 2: yellow
        [0, 1, 0, 1],  # 3: green
        [0, 0, 1, 1],  # 4: blue
        [0, 1, 1, 1],  # 5: cyan
    ]

    def test_worst_class(self):
        assert eval_color(15.0, self.THRESHOLDS, self.COLORS) == self.COLORS[0]

    def test_best_class(self):
        assert eval_color(0.0, self.THRESHOLDS, self.COLORS) == self.COLORS[5]

    def test_show_dots_none_returns_color(self):
        # None means "all visible"
        assert eval_color(5.0, self.THRESHOLDS, self.COLORS) == self.COLORS[2]

    def test_show_dots_all_true(self):
        flags = [True] * 6
        assert eval_color(0.0, self.THRESHOLDS, self.COLORS, flags) == self.COLORS[5]

    def test_show_dots_hides_class(self):
        flags = [True, True, True, True, True, False]  # hide best class
        # For 0.0 loss -> class 5 -> hidden -> None
        assert eval_color(0.0, self.THRESHOLDS, self.COLORS, flags) is None

    def test_show_dots_visible_class(self):
        flags = [True, True, True, True, True, False]
        # For 1.0 loss -> class 4 -> visible
        assert eval_color(1.0, self.THRESHOLDS, self.COLORS, flags) == self.COLORS[4]


# =============================================================================
# x_coordinate_text
# =============================================================================


class TestXCoordinateText:
    # GTP_COORD: A, B, C, ..., T (skipping I) - 19 entries
    GTP = [chr(ord("A") + i) if i < 8 else chr(ord("A") + i + 1) for i in range(19)]

    def test_no_rotation(self):
        # index 0 -> A, index 18 -> T
        assert x_coordinate_text(0, 19, 0, self.GTP) == "A"
        assert x_coordinate_text(18, 19, 0, self.GTP) == "T"

    def test_rotation_90(self):
        # At 90deg, x uses index+1 numeric
        assert x_coordinate_text(0, 19, 90, self.GTP) == "1"
        assert x_coordinate_text(5, 19, 90, self.GTP) == "6"

    def test_rotation_180(self):
        # At 180deg, x uses mirrored GTP
        # i=0 -> GTP[18] = T
        # i=18 -> GTP[0] = A
        assert x_coordinate_text(0, 19, 180, self.GTP) == "T"
        assert x_coordinate_text(18, 19, 180, self.GTP) == "A"

    def test_rotation_270(self):
        # At 270deg, x uses board_size - i numeric
        assert x_coordinate_text(0, 19, 270, self.GTP) == "19"
        assert x_coordinate_text(5, 19, 270, self.GTP) == "14"


# =============================================================================
# y_coordinate_text
# =============================================================================


class TestYCoordinateText:
    GTP = [chr(ord("A") + i) if i < 8 else chr(ord("A") + i + 1) for i in range(19)]

    def test_no_rotation(self):
        # No rotation: y uses index+1 numeric
        assert y_coordinate_text(0, 19, 0, self.GTP) == "1"
        assert y_coordinate_text(5, 19, 0, self.GTP) == "6"
        assert y_coordinate_text(18, 19, 0, self.GTP) == "19"

    def test_rotation_90(self):
        # At 90deg, y uses mirrored GTP
        # i=0 -> GTP[18] = T
        # i=18 -> GTP[0] = A
        assert y_coordinate_text(0, 19, 90, self.GTP) == "T"
        assert y_coordinate_text(18, 19, 90, self.GTP) == "A"

    def test_rotation_180(self):
        # At 180deg, y uses board_size - i numeric
        assert y_coordinate_text(0, 19, 180, self.GTP) == "19"
        assert y_coordinate_text(18, 19, 180, self.GTP) == "1"

    def test_rotation_270(self):
        # At 270deg, y uses index directly
        assert y_coordinate_text(0, 19, 270, self.GTP) == "A"
        assert y_coordinate_text(18, 19, 270, self.GTP) == "T"


# =============================================================================
# find_closest_grid_point
# =============================================================================


class TestFindClosestGridPoint:
    def test_empty_returns_none(self):
        assert find_closest_grid_point(5.0, 5.0, [], []) is None
        assert find_closest_grid_point(5.0, 5.0, [1.0, 2.0], []) is None

    def test_exact_match(self):
        result = find_closest_grid_point(2.0, 3.0, [1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert result == (2.0, 1, 3.0, 2)

    def test_closest_x(self):
        result = find_closest_grid_point(2.4, 0.0, [1.0, 2.0, 3.0], [0.0])
        # Closest x to 2.4 is 2.0 (index 1) since |2.4-2.0|=0.4 < |2.4-3.0|=0.6
        assert result == (2.0, 1, 0.0, 0)

    def test_closest_y(self):
        result = find_closest_grid_point(0.0, 2.6, [0.0], [1.0, 2.0, 3.0])
        # Closest y to 2.6 is 3.0 (index 2)
        assert result == (0.0, 0, 3.0, 2)


# =============================================================================
# format_leela_stat
# =============================================================================


@dataclass
class FakeLeelaCandidate:
    stats: dict[str, Any] = field(default_factory=dict)


class TestFormatLeelaStat:
    def test_visits_int(self):
        c = FakeLeelaCandidate(stats={"LEELA_TOP_MOVE_VISITS": 1500})
        assert format_leela_stat(c, "LEELA_TOP_MOVE_VISITS") == "1500"

    def test_visits_float_truncated(self):
        c = FakeLeelaCandidate(stats={"LEELA_TOP_MOVE_VISITS": 1500.7})
        assert format_leela_stat(c, "LEELA_TOP_MOVE_VISITS") == "1500"

    def test_winrate(self):
        c = FakeLeelaCandidate(stats={"LEELA_TOP_MOVE_WINRATE": 0.523})
        assert format_leela_stat(c, "LEELA_TOP_MOVE_WINRATE") == "52.3%"

    def test_relative_winrate(self):
        c = FakeLeelaCandidate(stats={"LEELA_TOP_MOVE_RELATIVE_WINRATE": 0.05})
        assert format_leela_stat(c, "LEELA_TOP_MOVE_RELATIVE_WINRATE") == "5.0%"

    def test_score(self):
        c = FakeLeelaCandidate(stats={"LEELA_TOP_MOVE_SCORE": 2.3})
        assert format_leela_stat(c, "LEELA_TOP_MOVE_SCORE") == "+2.3"

    def test_score_negative(self):
        c = FakeLeelaCandidate(stats={"LEELA_TOP_MOVE_SCORE": -1.5})
        assert format_leela_stat(c, "LEELA_TOP_MOVE_SCORE") == "-1.5"

    def test_none_returns_empty(self):
        c = FakeLeelaCandidate(stats={"LEELA_TOP_MOVE_VISITS": None})
        assert format_leela_stat(c, "LEELA_TOP_MOVE_VISITS") == ""

    def test_missing_key_returns_empty(self):
        c = FakeLeelaCandidate(stats={})
        assert format_leela_stat(c, "LEELA_TOP_MOVE_VISITS") == ""

    def test_unknown_stat_returns_str(self):
        c = FakeLeelaCandidate(stats={"UNKNOWN_KEY": 42})
        assert format_leela_stat(c, "UNKNOWN_KEY") == "42"

    def test_unknown_stat_with_text(self):
        c = FakeLeelaCandidate(stats={"LEELA_TOP_MOVE_ORDER": "best"})
        assert format_leela_stat(c, "LEELA_TOP_MOVE_ORDER") == "best"
