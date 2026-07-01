"""Tests for katrain/core/analysis/time/parser.py (Phase 167)."""
from __future__ import annotations

import pytest

from katrain.core.analysis.time.parser import _extract_time_left, parse_time_data
from katrain.core.game.base import KaTrainSGF


def _parse(sgf_str: str):
    """Helper: parse SGF string. Add GM[1] root property if missing.

    The SGF parser treats the content as the root node when no root
    properties are present, so to get a proper tree with root + child
    moves, we need at least one root property like GM[1].
    """
    if "(;B[" not in sgf_str and "(;W[" not in sgf_str:
        return KaTrainSGF.parse_sgf(sgf_str)
    if "(;GM[" not in sgf_str:
        # Insert GM[1] right after "(;"
        sgf_str = sgf_str.replace("(", "(;GM[1]", 1)
    return KaTrainSGF.parse_sgf(sgf_str)


def _first_move_node(sgf_str: str):
    """Helper: parse and return first move node (not root)."""
    return _parse(sgf_str).children[0]


class TestExtractTimeLeft:
    def test_valid_integer_B(self):
        node = _first_move_node("(;B[aa]BL[100])")
        assert _extract_time_left(node, "B") == 100.0

    def test_valid_integer_W(self):
        node = _first_move_node("(;W[bb]WL[95])")
        assert _extract_time_left(node, "W") == 95.0

    def test_valid_float(self):
        node = _first_move_node("(;B[aa]BL[123.456])")
        assert _extract_time_left(node, "B") == pytest.approx(123.456)

    def test_whitespace_stripped(self):
        node = _first_move_node("(;B[aa]BL[  42  ])")
        assert _extract_time_left(node, "B") == 42.0

    def test_missing_property_returns_none(self):
        node = _first_move_node("(;B[aa])")
        assert _extract_time_left(node, "B") is None

    def test_empty_value_returns_none(self):
        node = _first_move_node("(;B[aa]BL[])")
        assert _extract_time_left(node, "B") is None

    def test_whitespace_only_returns_none(self):
        node = _first_move_node("(;B[aa]BL[   ])")
        assert _extract_time_left(node, "B") is None

    def test_negative_returns_none(self):
        node = _first_move_node("(;B[aa]BL[-5])")
        assert _extract_time_left(node, "B") is None

    def test_invalid_string_returns_none(self):
        node = _first_move_node("(;B[aa]BL[abc])")
        assert _extract_time_left(node, "B") is None

    def test_BL_for_white_returns_none(self):
        """W player should read WL, not BL."""
        node = _first_move_node("(;B[aa]BL[100])")
        assert _extract_time_left(node, "W") is None

    def test_WL_for_black_returns_none(self):
        """B player should read BL, not WL."""
        node = _first_move_node("(;W[bb]WL[100])")
        assert _extract_time_left(node, "B") is None

    def test_malformed_empty_list_returns_none(self):
        """Property list raises IndexError on empty list."""
        from katrain.core.sgf_parser import SGFNode

        node = SGFNode(properties={}, parent=None)
        node.properties["BL"] = []
        assert _extract_time_left(node, "B") is None


class TestParseTimeData:
    def test_no_time_data(self):
        """Game without BL/WL returns has_time_data=False."""
        root = _parse("(;GM[1]SZ[19];B[aa];W[bb])")
        result = parse_time_data(root)
        assert result.has_time_data is False
        assert result.metrics == ()
        assert result.black_moves_with_time == 0
        assert result.white_moves_with_time == 0

    def test_basic_time_data(self):
        """Game with BL/WL on every move."""
        sgf = "(;GM[1]SZ[19];B[aa]BL[100];W[bb]WL[95];B[cc]BL[90];W[dd]WL[85])"
        root = _parse(sgf)
        result = parse_time_data(root)
        assert result.has_time_data is True
        assert result.black_moves_with_time == 2
        assert result.white_moves_with_time == 2
        assert len(result.metrics) == 4
        # First move: time_spent is None (no previous)
        assert result.metrics[0].time_spent_sec is None
        # Second move (B): spent 100-90 = 10 sec
        assert result.metrics[2].time_spent_sec == pytest.approx(10.0)

    def test_partial_time_data(self):
        """Some moves have BL/WL, some don't. Per-player prev is preserved.

        prev_time[player] is only updated for the current player, not
        for all players. So move 3 (B) still has prev_time[B] = 100 from
        move 1, even though move 2 (W) had no BL/WL.
        """
        sgf = "(;B[aa]BL[100];W[bb];B[cc]BL[90];W[dd]WL[85])"
        root = _parse(sgf)
        result = parse_time_data(root)
        assert result.has_time_data is True
        # Move 1 (B): time_left=100, no prev
        assert result.metrics[0].time_left_sec == 100.0
        assert result.metrics[0].time_spent_sec is None
        # Move 2 (W): no BL/WL
        assert result.metrics[1].time_left_sec is None
        assert result.metrics[1].time_spent_sec is None
        # Move 3 (B): time_left=90, prev was 100 (preserved from move 1)
        assert result.metrics[2].time_left_sec == 90.0
        assert result.metrics[2].time_spent_sec == pytest.approx(10.0)
        # Move 4 (W): time_left=85, prev was None (move 2 was W with no WL)
        assert result.metrics[3].time_left_sec == 85.0
        assert result.metrics[3].time_spent_sec is None

    def test_byoyomi_reset_treated_as_unknown(self):
        """Negative delta (time increased) is treated as unknown spent."""
        # Move 1: B 100 -> Move 2: B 200 (time increased = byoyomi reset)
        sgf = "(;B[aa]BL[100];W[bb]WL[200];B[cc]BL[150])"
        root = _parse(sgf)
        result = parse_time_data(root)
        # W2 prev was None (B1 set B prev, W1 sets W prev)
        # Actually: move 1 is B with BL=100, so prev_time[B]=100
        # move 2 is W with WL=200, so prev_time[W]=200, but B prev stays 100
        # move 3 is B with BL=150, prev_time[B]=100, delta=100-150=-50 -> unknown
        assert result.metrics[2].time_left_sec == 150.0
        assert result.metrics[2].time_spent_sec is None  # negative delta

    def test_tiny_negative_treated_as_zero(self):
        """Tiny negative delta (floating point noise) treated as 0."""
        # 100.0001 - 100 = 0.0001 < EPS (0.001), so treat as 0
        sgf = "(;B[aa]BL[100.0001];W[bb]WL[100];B[cc]BL[100])"
        root = _parse(sgf)
        result = parse_time_data(root)
        # B move 3: prev=100.0001, current=100, delta=0.0001 < 0.001
        # time_spent = max(0, 0.0001) = 0.0001
        assert result.metrics[2].time_spent_sec == pytest.approx(0.0001, abs=1e-6)

    def test_move_numbers_sequential(self):
        """Move numbers count only actual moves, not non-move nodes."""
        # Add a comment node between moves
        sgf = "(;B[aa]BL[100];W[bb]WL[95]C[comment];B[cc]BL[90])"
        root = _parse(sgf)
        result = parse_time_data(root)
        move_numbers = [m.move_number for m in result.metrics]
        assert move_numbers == [1, 2, 3]

    def test_setup_nodes_skipped(self):
        """Setup nodes (no move) don't count as moves."""
        sgf = "(;B[aa]BL[100];W[bb]WL[95]AB[cc];B[dd]BL[85])"
        root = _parse(sgf)
        result = parse_time_data(root)
        assert len(result.metrics) == 3  # 3 actual moves

    def test_branching_only_mainline(self):
        """Only mainline (first child) is traversed."""
        # Variant tree: root -> B[aa], then B[aa] has 2 children: W[bb] (mainline) and W[cc] (variant)
        sgf = "(;B[aa]BL[100](;W[bb]WL[90])(;W[cc]WL[80]))"
        root = _parse(sgf)
        result = parse_time_data(root)
        # Only mainline (B[aa] -> W[bb]) is traversed
        assert len(result.metrics) == 2
        assert result.metrics[1].time_left_sec == 90.0

    def test_single_move(self):
        """Single-move game."""
        sgf = "(;B[aa]BL[100])"
        root = _parse(sgf)
        result = parse_time_data(root)
        assert result.has_time_data is True
        assert len(result.metrics) == 1
        assert result.metrics[0].time_spent_sec is None  # no previous
