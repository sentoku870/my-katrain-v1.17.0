"""Tests for AnalysisController (Phase 173 P0-①-B).

Phase 133 created AnalysisController for analysis-related UI mutations
(set_analysis_focus_toggle, re_analyze_from_current_node, etc.). Phase 173
P0-①-B extracted two more methods from KaTrainGui into the controller:

  - ``toggle_move_num`` (was on KaTrainGui)
  - ``restore_last_mode`` (was on KaTrainGui)

This file locks down those two new entry points with focused unit tests that
don't need Kivy.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from katrain.gui.controllers.analysis_controller import AnalysisController


def _make_ctx(
    *,
    ui_state_last_mode: str | None = None,
    current_play_mode: str | None = "play",
) -> MagicMock:
    """Build a stub AnalysisContext.

    Defaults to ``MODE_PLAY``/``MODE_PLAY`` (no transition needed).
    """
    ctx = MagicMock()
    ctx.engine = MagicMock()
    ctx.engine.config = {}
    ctx.game = MagicMock()
    ctx.game.root = MagicMock()
    ctx.board_controls = MagicMock()
    ctx.analysis_controls = MagicMock()
    ctx.controls = MagicMock()
    ctx.pondering = False
    ctx.show_move_num = False
    # play_mode with analyze / play trigger_action mocks.
    play_mode = MagicMock()
    play_mode.mode = current_play_mode
    play_mode.analyze = MagicMock()
    play_mode.play = MagicMock()
    ctx.play_mode = play_mode

    # config() - only register the key if the value is non-None so a missing
    # persisted setting actually falls back to the default the production
    # code expects.
    cfg_map = {}
    if ui_state_last_mode is not None:
        cfg_map["ui_state/last_mode"] = ui_state_last_mode
    ctx.config = lambda key, default=None: cfg_map.get(key, default)
    return ctx


# ---------------------------------------------------------------------------
# toggle_move_num
# ---------------------------------------------------------------------------


class TestToggleMoveNum:
    def test_toggles_off_to_on(self):
        ctx = _make_ctx()
        controller = AnalysisController(ctx)
        assert ctx.show_move_num is False

        controller.toggle_move_num()

        assert ctx.show_move_num is True
        ctx.update_state.assert_called_once()

    def test_toggles_on_to_off(self):
        ctx = _make_ctx()
        ctx.show_move_num = True
        controller = AnalysisController(ctx)

        controller.toggle_move_num()

        assert ctx.show_move_num is False
        ctx.update_state.assert_called_once()

    def test_each_call_calls_update_state(self):
        ctx = _make_ctx()
        controller = AnalysisController(ctx)
        controller.toggle_move_num()
        controller.toggle_move_num()
        assert ctx.update_state.call_count == 2


# ---------------------------------------------------------------------------
# restore_last_mode
# ---------------------------------------------------------------------------


class TestRestoreLastMode:
    def test_restore_analyze_when_in_play(self):
        # Persisted = analyze, current = play → should fire analyze.trigger_action.
        ctx = _make_ctx(ui_state_last_mode="analyze", current_play_mode="play")
        controller = AnalysisController(ctx)

        controller.restore_last_mode()

        ctx.play_mode.analyze.trigger_action.assert_called_once_with(duration=0)
        ctx.play_mode.play.trigger_action.assert_not_called()

    def test_restore_play_when_in_analyze(self):
        # Persisted = play, current = analyze → should fire play.trigger_action.
        ctx = _make_ctx(ui_state_last_mode="play", current_play_mode="analyze")
        controller = AnalysisController(ctx)

        controller.restore_last_mode()

        ctx.play_mode.play.trigger_action.assert_called_once_with(duration=0)
        ctx.play_mode.analyze.trigger_action.assert_not_called()

    def test_no_op_when_already_in_persisted_mode(self):
        # Persisted = play, current = play → no trigger.
        ctx = _make_ctx(ui_state_last_mode="play", current_play_mode="play")
        controller = AnalysisController(ctx)

        controller.restore_last_mode()

        ctx.play_mode.analyze.trigger_action.assert_not_called()
        ctx.play_mode.play.trigger_action.assert_not_called()

    def test_defaults_to_play_when_persisted_missing(self):
        # Persisted value missing → defaults to MODE_PLAY.
        ctx = _make_ctx(ui_state_last_mode=None, current_play_mode="analyze")
        controller = AnalysisController(ctx)

        controller.restore_last_mode()

        # Default is 'play' → triggers play.trigger_action.
        ctx.play_mode.play.trigger_action.assert_called_once_with(duration=0)

    def test_exception_is_logged_not_raised(self):
        # If trigger_action blows up, we log and swallow.
        ctx = _make_ctx(ui_state_last_mode="play", current_play_mode="analyze")
        ctx.play_mode.play.trigger_action.side_effect = RuntimeError("ui boom")
        controller = AnalysisController(ctx)

        # Should not raise.
        controller.restore_last_mode()
        # log() should have been called with a "failed" message.
        logged = [c for c in ctx.log.call_args_list if "failed" in c.args[0]]
        assert len(logged) >= 1

    def test_no_play_mode_is_safe(self):
        # If play_mode is None, the function should not raise.
        ctx = _make_ctx(ui_state_last_mode="play", current_play_mode="play")
        ctx.play_mode = None
        controller = AnalysisController(ctx)
        controller.restore_last_mode()  # Should not raise
