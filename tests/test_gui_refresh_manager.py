"""Tests for GUIRefreshManager (Phase PR4 coverage).

The manager is a thin dependency-injected wrapper, so each test
plugs in MagicMock callables and exercises the branches inside
``update_gui``, ``update_status_for_error``, and ``on_engine_status``.

This file targets >80% coverage on ``katrain.gui.managers.gui_refresh_manager``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from katrain.core.constants.output import (
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    OUTPUT_INFO,
    OUTPUT_KATAGO_STDERR,
    STATUS_ERROR,
    STATUS_INFO,
)
from katrain.gui.managers.gui_refresh_manager import GUIRefreshManager


def _make_manager(set_status=None):
    """Build a GUIRefreshManager with MagicMock callables."""
    game = MagicMock(name="game")
    board_gui = MagicMock(name="board_gui")
    board_controls = MagicMock(name="board_controls")
    controls = MagicMock(name="controls")
    gui = MagicMock(name="gui")

    mgr = GUIRefreshManager(
        get_game=lambda: game,
        get_board_gui=lambda: board_gui,
        get_board_controls=lambda: board_controls,
        get_controls=lambda: controls,
        get_gui=lambda: gui,
        set_status=set_status,
    )
    return mgr, game, board_gui, board_controls, controls, gui


class TestUpdateGui:
    def test_returns_early_when_no_game(self):
        """When ``get_game()`` returns ``None``, nothing is called."""
        mgr = GUIRefreshManager(
            get_game=lambda: None,
            get_board_gui=MagicMock(),
            get_board_controls=MagicMock(),
            get_controls=MagicMock(),
            get_gui=MagicMock(),
        )
        mgr.update_gui(cn=None, redraw_board=True)
        # No assertions needed: if any branch tried to call the mocks,
        # they would still return MagicMocks; we just verify no exception.

    def test_full_refresh_runs_all_widget_steps(self):
        mgr, game, board_gui, board_controls, controls, gui = _make_manager()
        mgr.update_gui(cn=MagicMock(), redraw_board=True)

        board_controls.update_controls.assert_called_once_with(gui)
        board_gui.draw_board.assert_called_once()
        board_gui.redraw_board_contents_trigger.assert_called_once()
        controls.update_evaluation.assert_called_once()
        controls.update_timer.assert_called_once_with(1)
        assert controls.move_tree.current_node is game.current_node

    def test_optional_widgets_can_be_none(self):
        """Missing board_gui / controls / board_controls must be tolerated."""
        game = MagicMock()
        mgr = GUIRefreshManager(
            get_game=lambda: game,
            get_board_gui=lambda: None,
            get_board_controls=lambda: None,
            get_controls=lambda: None,
            get_gui=lambda: MagicMock(),
        )
        mgr.update_gui(cn=MagicMock(), redraw_board=False)
        # No exception, no NoneType attribute access.

    def test_redraw_board_false_skips_full_draw(self):
        mgr, _game, board_gui, _bc, _c, _gui = _make_manager()
        mgr.update_gui(cn=MagicMock(), redraw_board=False)
        board_gui.draw_board.assert_not_called()
        board_gui.redraw_board_contents_trigger.assert_called_once()


class TestUpdateStatusForError:
    def test_set_status_none_is_noop(self):
        mgr = GUIRefreshManager(
            get_game=MagicMock(),
            get_board_gui=MagicMock(),
            get_board_controls=MagicMock(),
            get_controls=MagicMock(),
            get_gui=MagicMock(),
            set_status=None,
        )
        # Must not raise even though OUTPUT_ERROR is passed in.
        mgr.update_status_for_error("some error", OUTPUT_ERROR)

    def test_output_error_triggers_status(self):
        set_status = MagicMock()
        mgr = GUIRefreshManager(
            get_game=MagicMock(),
            get_board_gui=MagicMock(),
            get_board_controls=MagicMock(),
            get_controls=MagicMock(),
            get_gui=MagicMock(),
            set_status=set_status,
        )
        mgr.update_status_for_error("kaboom", OUTPUT_ERROR)
        set_status.assert_called_once_with("ERROR: kaboom", STATUS_ERROR)

    def test_katago_stderr_with_error_word_triggers_status(self):
        set_status = MagicMock()
        mgr = GUIRefreshManager(
            get_game=MagicMock(),
            get_board_gui=MagicMock(),
            get_board_controls=MagicMock(),
            get_controls=MagicMock(),
            get_gui=MagicMock(),
            set_status=set_status,
        )
        mgr.update_status_for_error("Error in GTP command", OUTPUT_KATAGO_STDERR)
        set_status.assert_called_once()

    def test_katago_stderr_with_tuning_word_skipped(self):
        """Tuning-related stderr lines are not surfaced as errors."""
        set_status = MagicMock()
        mgr = GUIRefreshManager(
            get_game=MagicMock(),
            get_board_gui=MagicMock(),
            get_board_controls=MagicMock(),
            get_controls=MagicMock(),
            get_gui=MagicMock(),
            set_status=set_status,
        )
        mgr.update_status_for_error("tuning: hyperparameter search", OUTPUT_KATAGO_STDERR)
        set_status.assert_not_called()

    def test_info_level_skips_status(self):
        set_status = MagicMock()
        mgr = GUIRefreshManager(
            get_game=MagicMock(),
            get_board_gui=MagicMock(),
            get_board_controls=MagicMock(),
            get_controls=MagicMock(),
            get_gui=MagicMock(),
            set_status=set_status,
        )
        mgr.update_status_for_error("hello", OUTPUT_INFO)
        set_status.assert_not_called()

    def test_debug_level_skips_status(self):
        set_status = MagicMock()
        mgr = GUIRefreshManager(
            get_game=MagicMock(),
            get_board_gui=MagicMock(),
            get_board_controls=MagicMock(),
            get_controls=MagicMock(),
            get_gui=MagicMock(),
            set_status=set_status,
        )
        mgr.update_status_for_error("hello", OUTPUT_DEBUG)
        set_status.assert_not_called()


class TestOnEngineStatus:
    @pytest.mark.parametrize(
        "event_type,msg,expected_substr",
        [
            ("starting", "", "starting"),
            ("tuning", " please wait", "tuning"),
            ("ready", "", "ready"),
        ],
    )
    def test_known_event_types_set_status(self, event_type, msg, expected_substr):
        set_status = MagicMock()
        mgr = GUIRefreshManager(
            get_game=MagicMock(),
            get_board_gui=MagicMock(),
            get_board_controls=MagicMock(),
            get_controls=MagicMock(),
            get_gui=MagicMock(),
            set_status=set_status,
        )
        mgr.on_engine_status(event_type, msg)
        assert set_status.called
        # The first positional arg carries the user-facing text.
        called_text = set_status.call_args[0][0]
        assert expected_substr.lower() in called_text.lower()
        # And the level is STATUS_INFO.
        assert set_status.call_args[0][1] == STATUS_INFO

    def test_unknown_event_type_skipped(self):
        set_status = MagicMock()
        mgr = GUIRefreshManager(
            get_game=MagicMock(),
            get_board_gui=MagicMock(),
            get_board_controls=MagicMock(),
            get_controls=MagicMock(),
            get_gui=MagicMock(),
            set_status=set_status,
        )
        mgr.on_engine_status("never_heard_of_it", "msg")
        set_status.assert_not_called()

    def test_set_status_none_is_safe(self):
        mgr = GUIRefreshManager(
            get_game=MagicMock(),
            get_board_gui=MagicMock(),
            get_board_controls=MagicMock(),
            get_controls=MagicMock(),
            get_gui=MagicMock(),
            set_status=None,
        )
        mgr.on_engine_status("starting", "")
        # No exception raised.
