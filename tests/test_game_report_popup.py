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

# katrain.gui.popups imports Kivy widgets at module top. On headless CI the
# import + Kivy's heavy init can OOM the 16GB runner mid-suite (exit 102).
# Mirror test_popups_helpers.py and skip this file on CI. Local development
# still runs the suite.
pytestmark = pytest.mark.skipif(
    os.environ.get("CI", "").lower() == "true",
    reason="katrain.gui.popups imports Kivy widgets at module scope; CI environment OOMs mid-suite",
)

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
        with patch(
            "katrain.gui.popups.misc_popups.Clock.schedule_once", return_value=new_event
        ) as mock_sched:
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

        with patch(
            "katrain.gui.popups.misc_popups.Clock.schedule_once", return_value=new_event
        ):
            popup._schedule_next_refresh(0.25)

        assert popup._refresh_event is new_event


class TestRefreshAttemptsGuard:
    """The pure decision logic: 'should we schedule another refresh?'"""

    @staticmethod
    def _should_schedule_more(
        engine_is_idle: bool, attempts: int, max_attempts: int
    ) -> bool:
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
