"""Tests for UIUpdateManager (Phase 173 P0-①-A replacement).

Phase 107 introduced a static-method layer on KaTrainGui that delegated to a
prototype coalescing implementation. Phase 133 moved the real logic into
``UIUpdateManager`` and ``__main__.py`` was updated to call that manager's
methods. The legacy static helpers became dead code.

This file replaces ``tests/test_phase107_subscribe.py`` (which exercised the
dead code) with direct tests against the live ``UIUpdateManager``. Coverage
parity:

- subscribe / re-subscribe idempotency (TestSetupStateSubscriptions)
- coalescing under repeated schedule (TestScheduleUiUpdate)
- multi-thread coalescing (TestThreadSafety)
- _do_ui_update flag reset behaviour (TestDoUiUpdateCallback)
"""

from __future__ import annotations

import concurrent.futures
import threading
from typing import Any
from unittest.mock import MagicMock

from katrain.core.constants.output import OUTPUT_DEBUG
from katrain.core.state import EventType
from katrain.gui.managers.ui_update_manager import UIUpdateManager


def _make_ctx(game: Any = None) -> MagicMock:
    """A bare ``UIUpdateContext``-compatible mock."""
    ctx = MagicMock()
    ctx.state_notifier = MagicMock()
    ctx.update_gui = MagicMock()
    ctx.log = MagicMock()
    if game is None:
        ctx.get_game.return_value = None
    else:
        ctx.get_game.return_value = game
    return ctx


def _make_manager() -> tuple[UIUpdateManager, MagicMock]:
    clock = MagicMock()
    ctx = _make_ctx()
    return UIUpdateManager(ctx, clock), ctx


class TestSetupStateSubscriptions:
    def test_subscribes_three_events(self):
        manager, ctx = _make_manager()
        manager.setup_state_subscriptions()
        event_types = [c.args[0] for c in ctx.state_notifier.subscribe.call_args_list]
        assert EventType.GAME_CHANGED in event_types
        assert EventType.ANALYSIS_COMPLETE in event_types
        assert EventType.CONFIG_UPDATED in event_types

    def test_double_setup_is_noop(self):
        manager, ctx = _make_manager()
        manager.setup_state_subscriptions()
        manager.setup_state_subscriptions()
        assert ctx.state_notifier.subscribe.call_count == 3

    def test_flag_prevents_resubscribe(self):
        manager, _ = _make_manager()
        assert manager._state_subscriptions_setup is False
        manager.setup_state_subscriptions()
        assert manager._state_subscriptions_setup is True


class TestScheduleUiUpdate:
    def test_single_call_schedules_once(self):
        manager, ctx = _make_manager()
        manager.schedule_ui_update(redraw_board=True)
        manager._clock.schedule_once.assert_called_once()
        assert manager._pending_ui_update is not None
        assert manager._pending_redraw_board is True

    def test_multiple_calls_coalesce(self):
        manager, ctx = _make_manager()
        manager.schedule_ui_update(redraw_board=False)
        manager.schedule_ui_update(redraw_board=True)
        manager._clock.schedule_once.assert_called_once()
        assert manager._pending_redraw_board is True

    def test_redraw_flag_is_sticky(self):
        manager, ctx = _make_manager()
        # Pre-existing scheduled event → new schedule is coalesced.
        manager._pending_ui_update = MagicMock()
        manager._pending_redraw_board = False
        manager.schedule_ui_update(redraw_board=True)
        assert manager._pending_redraw_board is True
        manager.schedule_ui_update(redraw_board=False)
        # Once True, stays True.
        assert manager._pending_redraw_board is True


class TestEventHandlers:
    def test_on_game_changed_schedules_with_redraw(self):
        manager, _ = _make_manager()
        manager._on_game_changed(MagicMock())
        manager._clock.schedule_once.assert_called_once()
        assert manager._pending_redraw_board is True

    def test_on_analysis_complete_schedules_without_redraw(self):
        manager, _ = _make_manager()
        manager._on_analysis_complete(MagicMock())
        manager._clock.schedule_once.assert_called_once()
        assert manager._pending_redraw_board is False

    def test_on_config_updated_schedules_without_redraw(self):
        manager, _ = _make_manager()
        manager._on_config_updated(MagicMock())
        manager._clock.schedule_once.assert_called_once()
        assert manager._pending_redraw_board is False


class TestDoUiUpdateCallback:
    def test_calls_update_gui_with_accumulated_flags(self):
        manager, ctx = _make_manager()
        manager._pending_ui_update = MagicMock()
        manager._pending_redraw_board = True
        node = MagicMock()
        ctx.get_game.return_value = MagicMock(current_node=node)
        manager._do_ui_update(0)
        ctx.update_gui.assert_called_once_with(node, redraw_board=True)

    def test_skips_when_no_game(self):
        manager, ctx = _make_manager()
        manager._pending_ui_update = MagicMock()
        manager._pending_redraw_board = False
        ctx.get_game.return_value = None
        manager._do_ui_update(0)
        ctx.update_gui.assert_not_called()

    def test_skips_when_no_current_node(self):
        manager, ctx = _make_manager()
        manager._pending_ui_update = MagicMock()
        ctx.get_game.return_value = MagicMock(current_node=None)
        manager._do_ui_update(0)
        ctx.update_gui.assert_not_called()

    def test_resets_flags_after_execution(self):
        manager, _ = _make_manager()
        manager._pending_ui_update = MagicMock()
        manager._pending_redraw_board = True
        ctx = manager._ctx
        node = MagicMock()
        ctx.get_game.return_value = MagicMock(current_node=node)
        manager._do_ui_update(0)
        assert manager._pending_ui_update is None
        assert manager._pending_redraw_board is False

    def test_logs_exception_without_raising(self):
        manager, ctx = _make_manager()
        manager._pending_ui_update = MagicMock()
        ctx.get_game.return_value = MagicMock(current_node=MagicMock())
        ctx.update_gui.side_effect = RuntimeError("test error")
        # Should not raise.
        manager._do_ui_update(0)
        ctx.log.assert_called_once()
        msg = ctx.log.call_args.args[0]
        assert "update_gui failed" in msg
        assert ctx.log.call_args.args[1] == OUTPUT_DEBUG


class TestThreadSafety:
    def test_concurrent_schedule_calls(self):
        # The manager itself owns its lock; reuse the production instance.
        manager, _ = _make_manager()
        schedule_calls = 0
        lock = threading.Lock()

        def track_schedule(*_args, **_kwargs):
            nonlocal schedule_calls
            with lock:
                schedule_calls += 1
            return MagicMock()

        manager._clock.schedule_once.side_effect = track_schedule

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(manager.schedule_ui_update, redraw_board=True) for _ in range(10)]
            concurrent.futures.wait(futures)

        assert schedule_calls == 1
        assert manager._pending_redraw_board is True
