"""Phase 250: Tests for ``color_filter`` parameter in
``GameNavigator`` important-move navigation.

The Phase 250 UI uses 4 buttons (黒前/黒次/白前/白次) that each pass
``color_filter="B"`` or ``"W"`` to the navigator. These tests pin
the color-splitting behaviour so the 4 buttons don't regress into the
old "all players mixed" behaviour.

Coverage:
- :func:`GameNavigator._compute_important_moves` with ``color_filter``
- :func:`GameNavigator.get_prev_important_node` with ``color_filter``
- :func:`GameNavigator.get_next_important_node` with ``color_filter``
- :func:`GameNavigator.jump_to_prev_important_move` with ``color_filter``
- :func:`GameNavigator.jump_to_next_important_move` with ``color_filter``
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from katrain.core.game.navigation import GameNavigator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(*, depth: int, player: str, score: float, points_lost: float = 0.0) -> SimpleNamespace:
    """Build a minimal stand-in for ``GameNode`` with the fields the
    navigator uses (``depth``, ``player``, ``score``, ``points_lost``,
    ``analysis_complete``, ``nodes_from_root``).

    ``nodes_from_root`` is set to a list of length ``depth+1`` so
    ``move_no = len(nodes_from_root) - 1 = depth``.
    """
    return SimpleNamespace(
        depth=depth,
        player=player,
        score=score,
        points_lost=points_lost,
        analysis_complete=True,
        nodes_from_root=list(range(depth + 1)),
    )


def _make_navigator(*, nodes: list[SimpleNamespace], current_depth: int) -> GameNavigator:
    """Build a GameNavigator with a mock game that yields ``nodes`` from
    ``_iter_main_branch_nodes`` and has ``current_node.depth ==
    current_depth``.

    Implementation: ``GameNavigator._iter_main_branch_nodes`` is patched
    directly so the mock-skipping main-branch traversal works without
    building a full GameNode tree.
    """
    game = MagicMock()
    game.current_node = SimpleNamespace(
        depth=current_depth,
        nodes_from_root=list(range(current_depth + 1)),
    )
    nav = GameNavigator(game)
    nav._iter_main_branch_nodes = lambda: iter(nodes)
    return nav


# ---------------------------------------------------------------------------
# _compute_important_moves color_filter
# ---------------------------------------------------------------------------


class TestComputeImportantMovesColorFilter:
    """``_compute_important_moves(color_filter=...)`` filters by player."""

    def test_no_filter_returns_all_players(self):
        """Default ``color_filter=None`` keeps the legacy mixed behaviour."""
        nodes = [
            _make_node(depth=1, player="B", score=1.0, points_lost=2.0),
            _make_node(depth=2, player="W", score=-1.0, points_lost=2.0),
            _make_node(depth=3, player="B", score=0.0, points_lost=0.0),
        ]
        nav = _make_navigator(nodes=nodes, current_depth=0)
        result = nav._compute_important_moves(max_moves=10)
        move_nos = [m for m, _, _ in result]
        assert move_nos == [1, 2, 3]

    def test_color_filter_B_excludes_white(self):
        """``color_filter="B"`` returns only black-played nodes."""
        nodes = [
            _make_node(depth=1, player="B", score=1.0, points_lost=2.0),
            _make_node(depth=2, player="W", score=-1.0, points_lost=2.0),
            _make_node(depth=3, player="B", score=0.0, points_lost=0.0),
        ]
        nav = _make_navigator(nodes=nodes, current_depth=0)
        result = nav._compute_important_moves(max_moves=10, color_filter="B")
        move_nos = [m for m, _, _ in result]
        assert move_nos == [1, 3]

    def test_color_filter_W_excludes_black(self):
        """``color_filter="W"`` returns only white-played nodes."""
        nodes = [
            _make_node(depth=1, player="B", score=1.0, points_lost=2.0),
            _make_node(depth=2, player="W", score=-1.0, points_lost=2.0),
            _make_node(depth=3, player="B", score=0.0, points_lost=0.0),
            _make_node(depth=4, player="W", score=-2.0, points_lost=2.0),
        ]
        nav = _make_navigator(nodes=nodes, current_depth=0)
        result = nav._compute_important_moves(max_moves=10, color_filter="W")
        move_nos = [m for m, _, _ in result]
        assert move_nos == [2, 4]


# ---------------------------------------------------------------------------
# get_prev/next_important_node color_filter
# ---------------------------------------------------------------------------


class TestGetPrevImportantNodeColorFilter:
    """``get_prev_important_node(color_filter=...)`` returns the closest
    important move before the current node, restricted to the player's
    color."""

    def test_no_filter_returns_largest_before(self):
        nodes = [
            _make_node(depth=1, player="B", score=1.0, points_lost=2.0),
            _make_node(depth=2, player="W", score=-1.0, points_lost=2.0),
            _make_node(depth=3, player="B", score=0.0, points_lost=2.0),
        ]
        nav = _make_navigator(nodes=nodes, current_depth=3)
        prev = nav.get_prev_important_node(max_moves=10)
        assert prev is not None
        assert prev.depth == 2

    def test_color_filter_B_skips_white(self):
        nodes = [
            _make_node(depth=1, player="B", score=1.0, points_lost=2.0),
            _make_node(depth=2, player="W", score=-1.0, points_lost=2.0),
            _make_node(depth=3, player="B", score=0.0, points_lost=2.0),
        ]
        nav = _make_navigator(nodes=nodes, current_depth=3)
        prev = nav.get_prev_important_node(max_moves=10, color_filter="B")
        assert prev is not None
        # black candidates are at depths 1 and 3; the largest strictly
        # before current_depth=3 is depth=1.
        assert prev.depth == 1

    def test_color_filter_W_finds_only_white(self):
        nodes = [
            _make_node(depth=1, player="B", score=1.0, points_lost=2.0),
            _make_node(depth=2, player="W", score=-1.0, points_lost=2.0),
            _make_node(depth=3, player="B", score=0.0, points_lost=2.0),
        ]
        nav = _make_navigator(nodes=nodes, current_depth=3)
        prev = nav.get_prev_important_node(max_moves=10, color_filter="W")
        assert prev is not None
        # the only white candidate is at depth=2.
        assert prev.depth == 2

    def test_color_filter_no_candidates_returns_None(self):
        nodes = [
            _make_node(depth=1, player="B", score=1.0, points_lost=0.0),
            _make_node(depth=2, player="B", score=0.0, points_lost=0.0),
        ]
        nav = _make_navigator(nodes=nodes, current_depth=2)
        prev = nav.get_prev_important_node(max_moves=10, color_filter="W")
        # No white moves → None (no fallback to other colors).
        assert prev is None


class TestGetNextImportantNodeColorFilter:
    """``get_next_important_node(color_filter=...)`` returns the closest
    important move after the current node, restricted to the player's
    color."""

    def test_color_filter_B_skips_white(self):
        nodes = [
            _make_node(depth=1, player="B", score=1.0, points_lost=2.0),
            _make_node(depth=2, player="W", score=-1.0, points_lost=2.0),
            _make_node(depth=3, player="B", score=0.0, points_lost=2.0),
        ]
        nav = _make_navigator(nodes=nodes, current_depth=1)
        nxt = nav.get_next_important_node(max_moves=10, color_filter="B")
        assert nxt is not None
        assert nxt.depth == 3

    def test_color_filter_W_finds_only_white(self):
        nodes = [
            _make_node(depth=1, player="B", score=1.0, points_lost=2.0),
            _make_node(depth=2, player="W", score=-1.0, points_lost=2.0),
            _make_node(depth=3, player="B", score=0.0, points_lost=2.0),
            _make_node(depth=4, player="W", score=-2.0, points_lost=2.0),
        ]
        nav = _make_navigator(nodes=nodes, current_depth=1)
        nxt = nav.get_next_important_node(max_moves=10, color_filter="W")
        assert nxt is not None
        # the closest white candidate strictly after current_depth=1
        # is depth=2 (not 4, which is later).
        assert nxt.depth == 2


# ---------------------------------------------------------------------------
# jump_to_prev/next_important_move color_filter
# ---------------------------------------------------------------------------


class TestJumpToImportantMoveColorFilter:
    """``jump_to_*_important_move(color_filter=...)`` calls
    ``set_current_node`` with the colour-restricted target."""

    def test_jump_to_next_with_color_filter(self):
        nodes = [
            _make_node(depth=1, player="B", score=1.0, points_lost=2.0),
            _make_node(depth=2, player="W", score=-1.0, points_lost=2.0),
            _make_node(depth=3, player="B", score=0.0, points_lost=2.0),
        ]
        nav = _make_navigator(nodes=nodes, current_depth=1)
        result = nav.jump_to_next_important_move(max_moves=10, color_filter="B")
        assert result is not None
        assert result.depth == 3
        nav._game.set_current_node.assert_called_once()

    def test_jump_to_prev_with_color_filter_no_candidate(self):
        nodes = [
            _make_node(depth=1, player="B", score=1.0, points_lost=0.0),
            _make_node(depth=2, player="B", score=0.0, points_lost=0.0),
        ]
        nav = _make_navigator(nodes=nodes, current_depth=2)
        result = nav.jump_to_prev_important_move(max_moves=10, color_filter="W")
        # No white candidates → no jump, no set_current_node call.
        assert result is None
        nav._game.set_current_node.assert_not_called()
