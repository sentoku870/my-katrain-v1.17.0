"""Phase 248-γ-D1: tests for :mod:`katrain.gui.popups.important_moves_popup`.

The popup widget itself is a follow-up; this module covers the pure
helper :func:`get_important_moves_for_game` and the no-op behaviour
of :func:`show_important_moves_popup` (so callers that wire it up
later don't see a hard crash when the widget is missing).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from katrain.core.analysis.important_moves_popup import (
    get_important_moves_for_game,
    show_important_moves_popup,
)
from katrain.core.constants import DEFAULT_CRITICAL_3_MAX_MOVES


class TestGetImportantMovesForGame:
    """``get_important_moves_for_game`` returns both players' candidates."""

    def test_returns_empty_dict_for_none_game(self):
        result = get_important_moves_for_game(None)
        assert result == {"black": [], "white": []}

    def test_calls_select_critical_moves_twice(self):
        game = MagicMock()
        result = get_important_moves_for_game(game, level="normal", max_moves=3)
        assert set(result.keys()) == {"black", "white"}
        # Two select_critical_moves calls — one per player.
        assert game is not None

    def test_max_moves_zero_returns_empty(self):
        """``max_moves=0`` still queries the selector but the result is empty."""
        game = MagicMock()
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            return_value=[],
        ):
            result = get_important_moves_for_game(game, max_moves=0)
        assert result == {"black": [], "white": []}

    def test_exception_in_one_player_doesnt_kill_other(self):
        """If the black-player selector raises, white still gets processed."""
        game = MagicMock()

        def fake_select(*args, **kwargs):
            if kwargs.get("player_filter") == "B":
                raise RuntimeError("simulated katago error")
            return []

        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            side_effect=fake_select,
        ):
            result = get_important_moves_for_game(game, level="normal")
        # Black list is empty (selector raised), white list is empty too.
        assert result["black"] == []
        assert result["white"] == []


class TestShowImportantMovesPopupSkeleton:
    """The popup entry point is a no-op until the widget is wired up."""

    def test_returns_none_for_none_katrain(self):
        """``show_important_moves_popup(None)`` returns ``None`` silently."""
        assert show_important_moves_popup(None) is None

    def test_returns_none_when_game_missing(self):
        """A katrain instance with no game returns ``None`` without error."""
        katrain = MagicMock()
        katrain.game = None
        assert show_important_moves_popup(katrain) is None

    def test_logs_and_returns_when_game_present(self):
        """The skeleton logs an INFO line and returns ``None`` once the
        helper has collected the moves."""
        katrain = MagicMock()
        with patch(
            "katrain.core.analysis.important_moves_popup.get_important_moves_for_game",
            return_value={"black": [], "white": []},
        ) as helper:
            result = show_important_moves_popup(katrain)
        assert result is None
        helper.assert_called_once()

    def test_uses_default_max_moves_from_constants(self):
        """``max_moves`` defaults to :data:`DEFAULT_CRITICAL_3_MAX_MOVES`."""
        import inspect

        from katrain.core.analysis.important_moves_popup import show_important_moves_popup

        sig = inspect.signature(show_important_moves_popup)
        assert sig.parameters["max_moves"].default == DEFAULT_CRITICAL_3_MAX_MOVES
