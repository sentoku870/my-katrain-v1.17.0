"""Phase 248-γ-D2: tests for the prev/next 重要局面 ヘルパー.

The helpers live in :mod:`katrain.core.analysis.important_moves_popup`
and are used by the existing ``do_prev_important`` / ``do_next_important``
dispatch keys (UI buttons in ``panels.kv``). The D2 phase adds the
``select_critical_moves``-based helpers so the popup and the
prev/next buttons share a single source of truth for "what counts as
重要局面".

Helpers tested:
- :func:`find_prev_important_move`
- :func:`find_next_important_move`
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from katrain.core.analysis.important_moves_popup import (
    find_next_important_move,
    find_prev_important_move,
)


def _move(move_number: int, player: str = "B") -> SimpleNamespace:
    """Build a minimal stand-in for ``CriticalMove`` with just the
    fields the helpers use."""
    return SimpleNamespace(move_number=move_number, player=player)


def _game(*, current_depth: int) -> MagicMock:
    """Build a mock game where the current_node has the given depth.

    The ``select_critical_moves`` patch is applied separately by the
    caller (so each test can vary the candidate set without rebuilding
    the game).
    """
    game = MagicMock()
    game.current_node = SimpleNamespace(depth=current_depth)
    return game


class TestFindPrevImportantMove:
    """``find_prev_important_move`` returns the largest move number < depth."""

    def test_none_game_returns_none(self):
        assert find_prev_important_move(None) is None

    def test_no_current_node_returns_none(self):
        game = MagicMock()
        game.current_node = None
        assert find_prev_important_move(game) is None

    def test_no_candidates_returns_none(self):
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            return_value=[],
        ):
            game = _game(current_depth=10)
            assert find_prev_important_move(game) is None

    def test_returns_largest_move_strictly_before_depth(self):
        # Current depth = 10; candidates at 3, 7, 12, 15 → prev = 7.
        candidates_b = [_move(3), _move(12), _move(15)]
        candidates_w = [_move(7)]
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            side_effect=[candidates_b, candidates_w],
        ):
            game = _game(current_depth=10)
            result = find_prev_important_move(game)
        assert result == 7

    def test_at_first_move_returns_none(self):
        """Current depth = 0 (root); no candidate can be < 0 → None."""
        candidates = [_move(1), _move(2), _move(3)]
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            return_value=candidates,
        ):
            game = _game(current_depth=0)
            assert find_prev_important_move(game) is None

    def test_candidates_at_exact_depth_excluded(self):
        """A move at the current depth is *not* a prev jump — already there."""
        candidates = [_move(5), _move(5)]  # both at depth 5
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            return_value=candidates,
        ):
            game = _game(current_depth=5)
            # ``n < current_depth`` (5 < 5) is False → no candidates.
            assert find_prev_important_move(game) is None

    def test_one_player_selector_raises_but_other_works(self):
        """If the B selector raises, the W selector still contributes."""
        candidates_w = [_move(3), _move(7)]

        def fake_select(*args, **kwargs):
            if kwargs.get("player_filter") == "B":
                raise RuntimeError("simulated B selector failure")
            return candidates_w

        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            side_effect=fake_select,
        ):
            game = _game(current_depth=10)
            result = find_prev_important_move(game)
        assert result == 7  # the W candidate


class TestFindNextImportantMove:
    """``find_next_important_move`` returns the smallest move number > depth."""

    def test_none_game_returns_none(self):
        assert find_next_important_move(None) is None

    def test_no_current_node_returns_none(self):
        game = MagicMock()
        game.current_node = None
        assert find_next_important_move(game) is None

    def test_no_candidates_returns_none(self):
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            return_value=[],
        ):
            game = _game(current_depth=10)
            assert find_next_important_move(game) is None

    def test_returns_smallest_move_strictly_after_depth(self):
        # Current depth = 5; candidates at 3, 7, 12, 15 → next = 7.
        candidates_b = [_move(3), _move(12), _move(15)]
        candidates_w = [_move(7)]
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            side_effect=[candidates_b, candidates_w],
        ):
            game = _game(current_depth=5)
            result = find_next_important_move(game)
        assert result == 7

    def test_at_last_move_returns_none(self):
        """Current depth = 20; no candidate can be > 20 → None."""
        candidates = [_move(1), _move(10), _move(20)]
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            return_value=candidates,
        ):
            game = _game(current_depth=20)
            assert find_next_important_move(game) is None

    def test_candidates_at_exact_depth_excluded(self):
        candidates = [_move(5), _move(5)]
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            return_value=candidates,
        ):
            game = _game(current_depth=5)
            # ``n > current_depth`` (5 > 5) is False → no candidates.
            assert find_next_important_move(game) is None


class TestFindMoveSymmetry:
    """``prev`` and ``next`` use the same candidate set but different
    comparisons. They are mirror functions.
    """

    def test_prev_and_next_cover_full_range(self):
        """At depth=5 with candidates {3, 7, 10}, prev=3 and next=7."""
        candidates = [_move(3), _move(7), _move(10)]
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            return_value=candidates,
        ):
            game = _game(current_depth=5)
            assert find_prev_important_move(game) == 3
            assert find_next_important_move(game) == 7

    def test_both_return_none_at_empty_candidate_list(self):
        """When there are no important moves at all, both helpers return None."""
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            return_value=[],
        ):
            game = _game(current_depth=5)
            assert find_prev_important_move(game) is None
            assert find_next_important_move(game) is None

    def test_invalid_current_node_depth_does_not_crash(self):
        """``current_node.depth`` is None / non-numeric → treated as 0."""
        for bad_depth in (None, "five", [], {}, ""):
            game = MagicMock()
            game.current_node = SimpleNamespace(depth=bad_depth)
            with patch(
                "katrain.core.analysis.important_moves_popup.select_critical_moves",
                return_value=[],
            ):
                # Both helpers should handle the bad depth gracefully.
                assert find_prev_important_move(game) is None
                assert find_next_important_move(game) is None


class TestDoPrevNextImportantDispatch:
    """The existing dispatch keys (Phase 248-γ-D2 enhancement)."""

    def test_do_prev_important_registered(self):
        from katrain.gui.features.commands import DISPATCH_TABLE

        assert "prev_important" in DISPATCH_TABLE
        assert DISPATCH_TABLE["prev_important"].__name__ == "do_prev_important"

    def test_do_next_important_registered(self):
        from katrain.gui.features.commands import DISPATCH_TABLE

        assert "next_important" in DISPATCH_TABLE
        assert DISPATCH_TABLE["next_important"].__name__ == "do_next_important"

    def test_panels_kv_has_prev_important_button(self):
        import os

        panels_path = os.path.join("katrain", "gui", "kv", "panels.kv")
        with open(panels_path, encoding="utf-8") as f:
            content = f.read()
        assert "prev_important" in content
        assert "next_important" in content

    def test_i18n_keys_exist(self):
        """The button labels (前の重要局面 / Prev Important) exist in JP/EN .po files."""
        import os

        for locale, expected_label in (
            ("jp", "前の重要局面"),
            ("en", "Prev Important"),
        ):
            po_path = os.path.join("katrain", "i18n", "locales", locale, "LC_MESSAGES", "katrain.po")
            with open(po_path, encoding="utf-8") as f:
                content = f.read()
            assert "prev-important-move" in content, f"Missing key in {locale}"
            assert expected_label in content, f"Missing label '{expected_label}' in {locale}"
