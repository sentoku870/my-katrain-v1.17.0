"""Phase 248-G2: tests for ``compute_complexity_filter_stats``.

The function returns the Phase 83 complexity-filter statistics without
performing the actual greedy selection — useful for surfacing the
"how many candidates were discounted by scoreStdev > 20" figure in
the GUI / Karte output. Previously the only visibility was the runtime
INFO log line emitted by ``select_critical_moves``.
"""

from __future__ import annotations

import pytest

from katrain.core.analysis import (
    COMPLEXITY_DISCOUNT_FACTOR,
    THRESHOLD_SCORE_STDEV_CHAOS,
    ComplexityFilterStats,
    compute_complexity_filter_stats,
)
from tests.helpers_eval_metrics import make_move_eval


def _make_stub_game(score_stdevs: list[tuple[int, str, float | None]]):
    """Build a stub game for ``compute_complexity_filter_stats``.

    Args:
        score_stdevs: list of (move_number, player, score_stdev) tuples
            in move-number order. ``None`` score_stdev = unanalysed node.

    The returned stub has:
    - ``iter_main_branch_nodes()`` that yields one node per entry (skipping root)
    - Each node has ``analysis_exists`` and ``analysis`` matching the
      provided score_stdev so ``_get_score_stdev_for_move`` returns it.

    Returns:
        A (game, move_evals) tuple. The move_evals are pre-classified
        MoveEval instances passed via ``pre_classified_moves`` to bypass
        the snapshot/importance-scoring pipeline (which is exercised
        elsewhere).
    """
    nodes: list[_StubNode] = [_StubNode(None, depth=0)]  # root has no analysis
    move_evals: list = []
    for move_number, player, score_stdev in score_stdevs:
        # depth == move_number because build_node_map keys by node.depth
        # and main-branch iteration skips the root.
        nodes.append(_StubNode(score_stdev, depth=move_number))
        # Use the standard helper to construct MoveEval.
        # ``is_reliable=True`` so importance scoring accepts them.
        mv = make_move_eval(
            move_number=move_number,
            player=player,
            gtp="D4",
            score_loss=5.0,  # arbitrary, not relevant to complexity filter
            root_visits=500,  # reliability scale 1.0
        )
        move_evals.append(mv)
    return _StubGame(nodes), move_evals


class TestComplexityFilterStatsReturnType:
    """Lock in the public return type and basic invariants."""

    def test_returns_complexity_filter_stats(self):
        """The return value is a ``ComplexityFilterStats`` instance."""
        game, moves = _make_stub_game(
            [
                (1, "B", 10.0),  # below threshold → not discounted
                (2, "B", 25.0),  # above threshold → discounted
                (3, "B", 30.0),  # above threshold → discounted
                (4, "W", 5.0),  # below → not discounted
            ]
        )
        stats = compute_complexity_filter_stats(game, level="normal", pre_classified_moves=moves)
        assert isinstance(stats, ComplexityFilterStats)

    def test_total_candidates_matches_input(self):
        """``total_candidates`` is the full input list size."""
        game, moves = _make_stub_game([(i + 1, "B", 10.0) for i in range(5)])
        stats = compute_complexity_filter_stats(game, level="normal", pre_classified_moves=moves)
        assert stats.total_candidates == 5

    def test_discounted_count_matches_threshold(self):
        """``discounted_count`` is the number of candidates with stdev > 20."""
        game, moves = _make_stub_game(
            [
                (1, "B", 10.0),  # not
                (2, "B", 25.0),  # yes
                (3, "B", 30.0),  # yes
                (4, "W", 50.0),  # yes
                (5, "W", 20.0),  # boundary: stdev == 20 → NOT discounted (strict >)
            ]
        )
        stats = compute_complexity_filter_stats(game, level="normal", pre_classified_moves=moves)
        assert stats.discounted_count == 3

    def test_max_stdev_seen_is_aggregate_max(self):
        """``max_stdev_seen`` is the maximum observed stdev across all candidates."""
        game, moves = _make_stub_game(
            [
                (1, "B", 10.0),
                (2, "B", 35.5),  # max
                (3, "B", 30.0),
            ]
        )
        stats = compute_complexity_filter_stats(game, level="normal", pre_classified_moves=moves)
        assert stats.max_stdev_seen == 35.5

    def test_max_stdev_none_when_all_missing(self):
        """When every candidate is unanalysed, ``max_stdev_seen`` is None."""
        game, moves = _make_stub_game([(1, "B", None), (2, "B", None)])
        stats = compute_complexity_filter_stats(game, level="normal", pre_classified_moves=moves)
        assert stats.max_stdev_seen is None
        # No discount either, because the discount function returns 1.0
        # for None stdev.
        assert stats.discounted_count == 0

    def test_discount_rate_property(self):
        """The ``discount_rate`` property computes the percentage."""
        stats = ComplexityFilterStats(total_candidates=4, discounted_count=1)
        assert stats.discount_rate == pytest.approx(25.0)

    def test_discount_rate_zero_when_empty(self):
        """Empty stats → 0% (no division-by-zero)."""
        stats = ComplexityFilterStats()
        assert stats.discount_rate == 0.0

    def test_constants_match_phase_83_spec(self):
        """The Phase 83 thresholds must not drift silently.

        ``THRESHOLD_SCORE_STDEV_CHAOS = 20.0`` and
        ``COMPLEXITY_DISCOUNT_FACTOR = 0.3`` were tuned in Phase 83 and
        are referenced by Karte / Karte-export consumer docs.
        """
        assert THRESHOLD_SCORE_STDEV_CHAOS == 20.0
        assert pytest.approx(0.3) == COMPLEXITY_DISCOUNT_FACTOR


class TestComplexityFilterStatsPlayerFilter:
    """``player_filter`` should restrict the candidate pool."""

    def test_player_filter_black_only(self):
        game, moves = _make_stub_game(
            [
                (1, "B", 25.0),  # discounted
                (2, "W", 25.0),  # would-be-discounted, but W is filtered out
            ]
        )
        stats_b = compute_complexity_filter_stats(game, level="normal", pre_classified_moves=moves, player_filter="B")
        assert stats_b.total_candidates == 1
        assert stats_b.discounted_count == 1

    def test_player_filter_white_only(self):
        game, moves = _make_stub_game(
            [
                (1, "B", 25.0),
                (2, "W", 25.0),
            ]
        )
        stats_w = compute_complexity_filter_stats(game, level="normal", pre_classified_moves=moves, player_filter="W")
        assert stats_w.total_candidates == 1
        assert stats_w.discounted_count == 1


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _StubNode:
    """Minimal node that exposes ``analysis``, ``analysis_exists``, ``depth``."""

    def __init__(self, score_stdev: float | None, depth: int = 0, move: object | None = None):
        self.analysis_exists = score_stdev is not None
        self.analysis = {"root": {"scoreStdev": score_stdev}} if score_stdev is not None else {}
        # ``build_node_map`` keys nodes by ``node.depth``. The root is
        # depth 0; subsequent main-branch nodes use 1..N. The stub
        # assigns depths by position in the test.
        self.depth = depth
        # ``iter_main_branch_nodes`` walks the tree via ``node.children``
        # and yields the node when ``node.move is not None``. We tag
        # every non-root node with a dummy move so the iterator yields
        # them.
        self.move = move if move is not None else (object() if depth > 0 else None)
        self.children: list = []
        self.is_mainline = True
        self.is_main = True


class _StubGame:
    """Minimal game object that exposes ``iter_main_branch_nodes`` via root.children."""

    def __init__(self, nodes: list[_StubNode]):
        self._nodes = nodes
        # The first node is the root; remaining are the main-branch
        # children chained via ``children`` so the depth-first iterator
        # visits them in order.
        if nodes:
            self.root = nodes[0]
            for i in range(len(nodes) - 1):
                nodes[i].children = [nodes[i + 1]]

    def iter_main_branch_nodes(self):
        # Not used directly (the real Game delegates to a module-level
        # helper that walks root.children). Kept for completeness.
        yield from self._nodes[1:]
