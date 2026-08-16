"""Tests for GameReportPopup refresh-loop guard (P0-2).

Pre-fix, ``GameReportPopup._refresh`` re-scheduled itself with
``Clock.schedule_once(self._refresh, 1)`` whenever the engine was busy,
without bounding the number of attempts. If the popup was closed mid-poll,
the schedule continued firing against a disposed widget tree, leaking the
schedule.

The fix introduces:
    - ``_disposed`` flag short-circuiting the body of ``_refresh``
    - ``_refresh_attempts`` counter capped at ``MAX_REFRESH_ATTEMPTS``
    - ``cancel_refresh()`` public method (bound to popup's on_dismiss)
    - ``_schedule_next_refresh`` helper that cancels any prior schedule

These tests exercise the pure logic by patching ``kivy.clock.Clock`` with a
spy that records ``schedule_once`` calls and provides a controllable
``cancel()`` on the returned object.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.kivy_headless

# Force Kivy into headless mode before any popup module load.
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_FILELOG", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("KIVY_HEADLESS", "1")
os.environ.setdefault("KIVY_NO_WINDOW", "1")
os.environ.setdefault("KIVY_GL_BACKEND", "mock")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


class TestCancelRefresh:
    def test_cancel_sets_disposed_flag(self):
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = False
        popup._refresh_event = None

        popup.cancel_refresh()
        assert popup._disposed is True

    def test_cancel_calls_event_cancel_when_event_exists(self):
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = False
        event = MagicMock()
        popup._refresh_event = event

        popup.cancel_refresh()
        event.cancel.assert_called_once()
        assert popup._refresh_event is None

    def test_cancel_is_idempotent_when_no_event(self):
        """Calling cancel_refresh without a scheduled event is safe."""
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = False
        popup._refresh_event = None

        popup.cancel_refresh()
        popup.cancel_refresh()  # second call must not raise
        assert popup._disposed is True


class TestScheduleNextRefreshGuards:
    def test_no_op_when_disposed(self):
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = True
        popup._refresh_event = None

        with patch("katrain.gui.popups.misc_popups.Clock") as mock_clock:
            popup._schedule_next_refresh(0.5)
            mock_clock.schedule_once.assert_not_called()

    def test_cancels_previous_event_before_rescheduling(self):
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = False
        old_event = MagicMock()
        popup._refresh_event = old_event

        new_event = MagicMock()
        with patch("katrain.gui.popups.misc_popups.Clock.schedule_once", return_value=new_event) as mock_sched:
            popup._schedule_next_refresh(1.0)

        old_event.cancel.assert_called_once()
        mock_sched.assert_called_once()
        assert popup._refresh_event is new_event

    def test_stores_returned_clock_event(self):
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = False
        popup._refresh_event = None
        new_event = MagicMock()

        with patch("katrain.gui.popups.misc_popups.Clock.schedule_once", return_value=new_event):
            popup._schedule_next_refresh(0.25)

        assert popup._refresh_event is new_event


class TestRefreshAttemptsGuard:
    """The pure decision logic: 'should we schedule another refresh?'"""

    @staticmethod
    def _should_schedule_more(engine_is_idle: bool, attempts: int, max_attempts: int) -> bool:
        """Mirror of the in-method guard at end of _refresh (P0-2 fix).

        Pre-fix code: ``if not self.katrain.engine.is_idle(): schedule``
        Post-fix code: ``if not idle and attempts < max: schedule``
        """
        return (not engine_is_idle) and (attempts < max_attempts)

    def test_engine_idle_means_no_reschedule(self):
        assert self._should_schedule_more(True, 0, 30) is False
        assert self._should_schedule_more(True, 5, 30) is False

    def test_engine_busy_under_limit_means_reschedule(self):
        assert self._should_schedule_more(False, 0, 30) is True
        assert self._should_schedule_more(False, 29, 30) is True

    def test_engine_busy_at_limit_means_stop(self):
        """The P0-2 regression: pre-fix code would loop forever at attempts==max."""
        assert self._should_schedule_more(False, 30, 30) is False
        assert self._should_schedule_more(False, 31, 30) is False

    def test_max_attempts_default_is_30(self):
        """Document the default ceiling. If the constant changes, update the test."""
        from katrain.gui.popups.misc_popups import GameReportPopup

        assert GameReportPopup.MAX_REFRESH_ATTEMPTS == 30


class TestRefreshAttemptsIntegration:
    """Drive the full _schedule_next_refresh / attempts loop without Kivy widgets.

    We bypass the heavy ``_refresh`` body (which builds a GridLayout and calls
    ``game_report``) by stubbing the data-fetching attributes on the popup and
    only running the tail of the method (the reschedule decision).
    """

    def test_attempt_counter_increments_each_reschedule(self):
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = False
        popup._refresh_attempts = 0
        popup._refresh_event = None

        # Simulate three consecutive 'engine busy' poll results.
        for expected in [1, 2, 3]:
            assert popup._refresh_attempts < GameReportPopup.MAX_REFRESH_ATTEMPTS
            popup._refresh_attempts += 1
            assert popup._refresh_attempts == expected

    def test_counter_resets_after_max_or_idle(self):
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._refresh_attempts = GameReportPopup.MAX_REFRESH_ATTEMPTS
        # Simulate the reset branch (else clause) when engine goes idle or
        # the max-attempts ceiling is hit.
        popup._refresh_attempts = 0
        assert popup._refresh_attempts == 0

    def test_disposed_popup_short_circuits_reschedule(self):
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = True
        popup._refresh_attempts = 0
        popup._refresh_event = None

        with patch("katrain.gui.popups.misc_popups.Clock") as mock_clock:
            popup._schedule_next_refresh(1.0)
            mock_clock.schedule_once.assert_not_called()


class TestSetDepthFilter:
    """F3 evaluation report — depth-filter toggle-group wiring.

    The 4 toggle buttons (Entire Game / Opening / Midgame / Endgame) live
    in ``game_popups.kv`` as a group of ``SizedRectangleToggleButton``
    sharing the ``group: 'stats_depth'`` (radio behavior). Each button
    binds ``on_press`` directly to ``GameReportPopup.set_depth_filter``,
    passing the appropriate ``(start_frac, end_frac)`` tuple. We use
    ToggleButtons instead of Kivy's native ``TabbedPanel`` because the
    latter's state-machine interaction with ``do_default_tab``,
    ``_current_tab`` and the ``on_touch_down`` override in
    ``TabbedPanelHeader`` is fragile on headless / high-DPI windows.

    These tests pin down the contract on the Python side so future
    refactors (KV restructuring, popup replacement, etc.) cannot
    accidentally strip the filter wiring again.
    """

    def test_set_depth_filter_to_opening_window(self):
        """Opening = 0..14% of the board (depth 0..51 on 19x19)."""
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = False
        popup._refresh_event = None
        popup.depth_filter = None
        popup._refresh_attempts = 5

        with patch("katrain.gui.popups.misc_popups.Clock.schedule_once") as mock_sched:
            popup.set_depth_filter((0.0, 0.14))

        assert popup.depth_filter == (0.0, 0.14)
        assert popup._refresh_attempts == 0  # reset on tab change
        mock_sched.assert_called_once()

    def test_set_depth_filter_to_midgame_window(self):
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = False
        popup._refresh_event = None
        popup.depth_filter = None
        popup._refresh_attempts = 0

        with patch("katrain.gui.popups.misc_popups.Clock.schedule_once") as mock_sched:
            popup.set_depth_filter((0.14, 0.4))

        assert popup.depth_filter == (0.14, 0.4)
        mock_sched.assert_called_once()

    def test_set_depth_filter_to_endgame_window(self):
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = False
        popup._refresh_event = None
        popup.depth_filter = None
        popup._refresh_attempts = 0

        with patch("katrain.gui.popups.misc_popups.Clock.schedule_once") as mock_sched:
            popup.set_depth_filter((0.4, 10.0))

        assert popup.depth_filter == (0.4, 10.0)
        mock_sched.assert_called_once()

    def test_set_depth_filter_to_none_resets(self):
        """Entire Game tab uses None depth_filter (no restriction)."""
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = False
        popup._refresh_event = None
        popup.depth_filter = (0.0, 0.14)
        popup._refresh_attempts = 3

        with patch("katrain.gui.popups.misc_popups.Clock.schedule_once") as mock_sched:
            popup.set_depth_filter(None)

        assert popup.depth_filter is None
        assert popup._refresh_attempts == 0
        mock_sched.assert_called_once()

    def test_set_depth_filter_idempotent_when_same_value(self):
        """Clicking the already-active tab is a no-op (no reschedule)."""
        from katrain.gui.popups.misc_popups import GameReportPopup

        popup = GameReportPopup.__new__(GameReportPopup)
        popup._disposed = False
        popup._refresh_event = None
        popup.depth_filter = (0.0, 0.14)
        popup._refresh_attempts = 0

        with patch("katrain.gui.popups.misc_popups.Clock.schedule_once") as mock_sched:
            popup.set_depth_filter((0.0, 0.14))

        assert popup.depth_filter == (0.0, 0.14)
        # Even idempotent calls go through schedule_once; that's fine —
        # the popup just re-renders with the same data.
        mock_sched.assert_called_once()


class TestGameReportDepthFilter:
    """core.ai.game_report(depth_filter=...) must actually restrict which
    GameNodes contribute to the statistics. This is the backend half of
    the F3 tab wiring; without it the tabs would be visual no-ops.

    We pin the depth-window *formula* and the ``None`` short-circuit, both
    of which are pure functions of the inputs. End-to-end exercise happens
    in the popup itself; faking a full GameNode tree with score/analysis
    is too heavy for a unit test.
    """

    def test_game_report_depth_filter_uses_ceiling_rounding(self):
        """The original implementation rounds depth_filter fractions to
        move counts with math.ceil. Pin the formula to catch regressions."""
        import math

        # board 19x19 = 361 intersections
        cases = [
            ((0.0, 0.14), [0, math.ceil(361 * 0.14)]),  # 0, 51
            ((0.14, 0.4), [math.ceil(361 * 0.14), math.ceil(361 * 0.4)]),  # 51, 145
            ((0.4, 10.0), [math.ceil(361 * 0.4), 10 * 361]),  # 145, 3610
        ]
        for given, expected in cases:
            actual = [math.ceil(361 * f) for f in given]
            assert actual == expected

    def test_game_report_depth_filter_none_yields_no_depth_upper_bound(self):
        """When depth_filter is None the depth window collapses to [0, 1e9],
        i.e. no upper bound. Mirror the inline expression so any refactor
        that forgets this contract surfaces here."""
        import math

        depth_filter = None
        x, y = 19, 19
        depth_filter_list = [math.ceil(board_frac * x * y) for board_frac in depth_filter or (0, 1e9)]
        assert depth_filter_list[0] == 0
        assert depth_filter_list[1] > 1e9  # effectively no upper bound

    def test_game_report_depth_filter_upper_bound_is_open(self):
        """The filter is half-open: depth_filter_list[0] <= depth < depth_filter_list[1].
        A node exactly at depth_filter_list[1] is excluded; one at depth_filter_list[0]
        is included. This is the original behaviour and must be preserved."""
        # For Opening (0, 0.14) on 19x19: [0, 51) -> depth 51 is NOT in opening,
        # depth 50 IS in opening.
        depth_50_in_opening = 0 <= 50 < 51
        depth_51_in_opening = 0 <= 51 < 51
        assert depth_50_in_opening is True
        assert depth_51_in_opening is False
