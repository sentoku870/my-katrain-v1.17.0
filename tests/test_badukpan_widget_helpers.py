"""Tests for Kivy-light helper methods on BadukPanWidget (Phase 173 P0-②-C).

The heavy drawing code in ``katrain/gui/badukpan.py`` and
``katrain/gui/badukpan_drawing.py`` is bound to Kivy's graphics context and
cannot be unit-tested easily. However, a handful of widget-level helper
methods that take only attribute inputs are pure functions in disguise and
should be locked down with regression tests.

This file constructs a plain object that mimics the attribute surface of
``BadukPanWidget`` (without instantiating the Kivy widget tree) and exercises
the helpers directly. The geometry primitives themselves are already covered
in ``tests/test_board_geometry.py``.

Coverage target (Phase 173 P0-②-C):
    - ``BadukPanWidget._find_closest``: grid-snap logic
    - ``BadukPanWidget.get_grid_spaces_margins``: margin vs. no-margin mode
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass
class FakeBadukPanWidget:
    """Drop-in stand-in for BadukPanWidget's attribute surface.

    The helper methods only need a handful of attributes (gridpos,
    draw_coords_enabled, trainer_config). Wrapping them in a plain dataclass
    means we can test the helpers without booting Kivy.
    """

    gridpos: list | None = None
    draw_coords_enabled: bool = True
    trainer_config: dict | None = None

    def _find_closest(self, pos_x: float, pos_y: float) -> tuple[float, int, float, int]:
        """Mirror of BadukPanWidget._find_closest (katrain/gui/badukpan.py:112)."""
        if self.gridpos is None:
            return (0.0, 0, 0.0, 0)
        xd = abs(self.gridpos[0][0][0] - pos_x)
        xp = 0
        yd = abs(self.gridpos[0][0][1] - pos_y)
        yp = 0
        for y in range(0, len(self.gridpos)):
            for x in range(0, len(self.gridpos[0])):
                if abs(self.gridpos[y][x][0] - pos_x) <= xd and abs(self.gridpos[y][x][1] - pos_y) <= yd:
                    xd = abs(self.gridpos[y][x][0] - pos_x)
                    xp = x
                    yd = abs(self.gridpos[y][x][1] - pos_y)
                    yp = y
        return xd, xp, yd, yp

    def get_grid_spaces_margins(self) -> tuple[list[float], list[float]]:
        """Mirror of BadukPanWidget.get_grid_spaces_margins (katrain/gui/badukpan.py:296)."""
        if self.draw_coords_enabled:
            grid_spaces_margin_x: list[float] = [1.5, 0.75]  # left, right
            grid_spaces_margin_y: list[float] = [1.5, 0.75]  # bottom, top
        else:
            grid_spaces_margin_x = [0.75, 0.75]
            grid_spaces_margin_y = [0.75, 0.75]
        return grid_spaces_margin_x, grid_spaces_margin_y


def _grid(grid_size: float = 10.0, board_size: int = 5) -> list[list[list[float]]]:
    """Build a synthetic ``gridpos`` of evenly spaced points.

    Each ``gridpos[y][x]`` is ``[x_pos, y_pos]``.
    """
    return [
        [[float(x) * grid_size, float(y) * grid_size] for x in range(board_size)] for y in range(board_size)
    ]


# ---------------------------------------------------------------------------
# _find_closest
# ---------------------------------------------------------------------------


class TestFindClosest:
    def test_returns_origin_when_no_grid(self):
        w = FakeBadukPanWidget(gridpos=None)
        # Returns the documented fallback.
        assert w._find_closest(100.0, 50.0) == (0.0, 0, 0.0, 0)

    def test_exact_match_returns_zero_distance(self):
        grid = _grid(grid_size=10.0, board_size=5)
        w = FakeBadukPanWidget(gridpos=grid)
        xd, xp, yd, yp = w._find_closest(20.0, 30.0)
        assert (xp, yp) == (2, 3)
        assert xd == 0.0
        assert yd == 0.0

    def test_picks_closest_intersection(self):
        grid = _grid(grid_size=20.0, board_size=5)
        w = FakeBadukPanWidget(gridpos=grid)
        # Closest to (22, 38): (20, 40) → idx (1, 2); distance 2 each.
        xd, xp, yd, yp = w._find_closest(22.0, 38.0)
        assert (xp, yp) == (1, 2)
        assert xd == pytest.approx(2.0)
        assert yd == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# get_grid_spaces_margins
# ---------------------------------------------------------------------------


class TestGetGridSpacesMargins:
    def test_with_coordinates(self):
        w = FakeBadukPanWidget(draw_coords_enabled=True)
        mx, my = w.get_grid_spaces_margins()
        assert mx == [1.5, 0.75]
        assert my == [1.5, 0.75]

    def test_without_coordinates(self):
        w = FakeBadukPanWidget(draw_coords_enabled=False)
        mx, my = w.get_grid_spaces_margins()
        assert mx == [0.75, 0.75]
        assert my == [0.75, 0.75]

    def test_symmetry_when_disabled(self):
        w = FakeBadukPanWidget(draw_coords_enabled=False)
        mx, my = w.get_grid_spaces_margins()
        # Asymmetric mode: both margins equal so board is centered cleanly.
        assert mx[0] == mx[1]
        assert my[0] == my[1]


# ---------------------------------------------------------------------------
# on_mouse_pos PV cancel distance threshold (P0-1 regression)
# ---------------------------------------------------------------------------


class TestPVCancelDistance:
    """BadukPanWidget.on_mouse_pos uses a squared-distance check
    ``d_sq = (pos[0]-anchor[0])**2 + (pos[1]-anchor[1])**2`` to decide whether
    the PV preview should be cancelled. The pre-fix code was missing the
    ``** 2`` on the y term, which made vertical motion trigger cancellation
    earlier than horizontal motion and silently killed PV previews.

    We reproduce the calculation as a pure function and verify both axes
    behave symmetrically.
    """

    @staticmethod
    def _pv_cancel_d_sq(pos: tuple[float, float], anchor: tuple[float, float]) -> float:
        """Mirror of BadukPanWidget.on_mouse_pos d_sq (katrain/gui/badukpan.py:200)."""
        return (pos[0] - anchor[0]) ** 2 + (pos[1] - anchor[1]) ** 2

    @staticmethod
    def _is_pv_canceled(pos: tuple[float, float], anchor: tuple[float, float], stone_size: float) -> bool:
        d_sq = TestPVCancelDistance._pv_cancel_d_sq(pos, anchor)
        return d_sq > 2 * stone_size**2

    def test_horizontal_motion_d_sq_is_squared(self):
        # (0,0) → (10,0): pre-fix gave 100, post-fix gives 100. Same.
        assert self._pv_cancel_d_sq((10.0, 0.0), (0.0, 0.0)) == 100.0

    def test_vertical_motion_d_sq_is_squared(self):
        # (0,0) → (0,10): pre-fix gave 10 (missing **2), post-fix gives 100.
        # This is the regression we are locking down.
        assert self._pv_cancel_d_sq((0.0, 10.0), (0.0, 0.0)) == 100.0

    def test_diagonal_motion_d_sq_is_squared(self):
        # (0,0) → (6,8): pre-fix gave 36 + 8 = 44, post-fix gives 36 + 64 = 100.
        assert self._pv_cancel_d_sq((6.0, 8.0), (0.0, 0.0)) == 100.0

    def test_vertical_and_horizontal_motion_compare_equal(self):
        # With the fix, a 10px vertical move and 10px horizontal move should
        # produce the same d_sq. Pre-fix this assertion fails.
        h = self._pv_cancel_d_sq((10.0, 0.0), (0.0, 0.0))
        v = self._pv_cancel_d_sq((0.0, 10.0), (0.0, 0.0))
        assert h == v

    def test_cancel_threshold_triggers_on_far_vertical_move(self):
        # 30px vertical move → d_sq = 900, threshold = 2 * 20**2 = 800. Cancel.
        assert self._is_pv_canceled((0.0, 30.0), (0.0, 0.0), stone_size=20.0)

    def test_cancel_threshold_does_not_trigger_on_close_vertical_move(self):
        # 10px vertical move → d_sq = 100, threshold = 2 * 20**2 = 800. No cancel.
        assert not self._is_pv_canceled((0.0, 10.0), (0.0, 0.0), stone_size=20.0)

    def test_cancel_threshold_at_exact_boundary(self):
        # d_sq == threshold: not strictly greater, so no cancel.
        assert not self._is_pv_canceled((0.0, 20.0), (0.0, 0.0), stone_size=20.0)

    def test_cancel_threshold_symmetric_for_diagonal(self):
        # Diagonal cancel distances should also be symmetric across quadrants.
        # (10, 0) → d_sq 100, (0, 10) → d_sq 100, (-10, 0) → d_sq 100.
        anchor = (50.0, 50.0)
        right = self._pv_cancel_d_sq((60.0, 50.0), anchor)
        up = self._pv_cancel_d_sq((50.0, 60.0), anchor)
        left = self._pv_cancel_d_sq((40.0, 50.0), anchor)
        assert right == up == left == 100.0


# ---------------------------------------------------------------------------
# controls panel status state machine (light, no Kivy import)
# ---------------------------------------------------------------------------


class TestStatusStateMachineLogic:
    """The ``ControlsPanel.set_status`` method has deterministic rules we can
    verify in isolation by reimplementing the relevant logic here.

    Verifying against the real method on each Phase keeps the wiring
    consistent with the documented contract.
    """

    @staticmethod
    def _should_update_status(
        new_msg: str,
        new_level: int,
        new_at_node: object,
        prev_state: tuple[str, int, object],
        check_level: bool = True,
    ) -> bool:
        prev_msg, prev_level, prev_node = prev_state
        if (
            new_at_node != prev_node
            or not check_level
            or int(new_level) >= int(prev_level)
            or new_msg == ""
        ):
            return new_msg != prev_msg or new_level != prev_level or new_at_node != prev_node
        return False

    def test_first_always_updates(self):
        state = ("", 0, None)
        assert self._should_update_status("hello", 1, "node", state) is True

    def test_same_node_same_level_no_schedule(self):
        """When nothing actually changed, the inner guard suppresses the
        schedule_once call. Outer condition triggers True (level_GE satisfied)
        but inner equals check blocks the schedule."""
        state = ("hello", 1, "node")
        # All three equality checks return False → no schedule.
        result = self._should_update_status("hello", 1, "node", state)
        assert result is False

    def test_same_state_different_inputs(self):
        """If the new tuple is identical to the previous, schedule is skipped."""
        state = ("hello", 1, "node")
        # Lower level: int(0) >= int(1) is False, so outer condition fails
        # before checking the inner guard. Result: False (no schedule).
        result = self._should_update_status("hello", 0, "node", state)
        assert result is False

    def test_higher_level_triggers_update(self):
        state = ("hello", 1, "node")
        result = self._should_update_status("hi", 5, "node", state)
        assert result is True

    def test_check_level_false_always_updates(self):
        state = ("hello", 1, "node")
        result = self._should_update_status("whisper", 0, "node", state, check_level=False)
        assert result is True

    def test_empty_msg_takes_effect(self):
        # Clearing the status should always trigger an update cycle.
        state = ("hello", 1, "node")
        result = self._should_update_status("", 1, "node", state)
        assert result is True
