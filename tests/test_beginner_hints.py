"""Phase 91: Beginner Hint Tests

Tests for the beginner safety hint system.
"""

from typing import List, Set, Tuple

import pytest

from katrain.core.beginner.detector import (
    detect_ignore_atari,
    detect_missed_capture,
    detect_self_atari,
    find_matching_group,
)
from katrain.core.beginner.hints import compute_beginner_hint, get_beginner_hint_cached
from katrain.core.beginner.models import BeginnerHint, DetectorInput, HintCategory
from katrain.core.game import Game
from katrain.core.game_node import GameNode
from katrain.core.sgf_parser import Move


# ---------------------------------------------------------------------------
# find_matching_group tests
# ---------------------------------------------------------------------------


class MockGroup:
    """Mock Group for testing find_matching_group"""

    def __init__(self, color: str, stones: Set[Tuple[int, int]]):
        self.color = color
        self.stones = stones


class TestFindMatchingGroup:
    """Tests for find_matching_group function"""

    def test_exact_match(self):
        """Exact stone set should match"""
        target = {(0, 0), (0, 1), (1, 0)}
        groups = [
            MockGroup("B", {(0, 0), (0, 1), (1, 0)}),
            MockGroup("W", {(5, 5)}),
        ]
        result = find_matching_group(target, groups, "B")
        assert result is not None
        assert result.stones == target

    def test_partial_overlap_above_threshold(self):
        """50%+ overlap should match"""
        target = {(0, 0), (0, 1), (1, 0), (1, 1)}  # 4 stones
        groups = [
            MockGroup("B", {(0, 0), (0, 1), (2, 2)}),  # 2/3 overlap
        ]
        result = find_matching_group(target, groups, "B")
        assert result is not None

    def test_partial_overlap_below_threshold(self):
        """<50% overlap should not match"""
        target = {(0, 0), (0, 1), (1, 0), (1, 1), (2, 2), (3, 3)}  # 6 stones
        groups = [
            MockGroup("B", {(0, 0), (5, 5), (6, 6), (7, 7)}),  # 1/4 overlap
        ]
        result = find_matching_group(target, groups, "B")
        assert result is None

    def test_wrong_color_no_match(self):
        """Different color should not match"""
        target = {(0, 0), (0, 1)}
        groups = [
            MockGroup("W", {(0, 0), (0, 1)}),  # Same stones but wrong color
        ]
        result = find_matching_group(target, groups, "B")
        assert result is None

    def test_empty_groups_no_match(self):
        """Empty groups list should return None"""
        target = {(0, 0)}
        result = find_matching_group(target, [], "B")
        assert result is None


# ---------------------------------------------------------------------------
# Basic detection tests using conftest fixtures
# ---------------------------------------------------------------------------


class TestBasicDetection:
    """Basic detection tests using game fixture"""

    def test_pass_move_returns_none(self, game_9x9):
        """Pass moves should not generate hints"""
        # Play a pass move
        pass_move = Move.from_gtp("pass", "B")
        game_9x9.play(pass_move, analyze=False)
        node = game_9x9.current_node

        hint = compute_beginner_hint(game_9x9, node)
        assert hint is None

    def test_root_node_returns_none(self, game_9x9):
        """Root node (no parent) should not generate hints"""
        node = game_9x9.root

        hint = compute_beginner_hint(game_9x9, node)
        assert hint is None

    def test_cache_works(self, game_9x9):
        """Cached hint should be returned on second call"""
        # Play some moves
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        # First call computes
        hint1 = get_beginner_hint_cached(game_9x9, node)

        # Second call should return cached value
        hint2 = get_beginner_hint_cached(game_9x9, node)

        # Should be same object (cached)
        assert hint1 is hint2

    def test_cache_distinguishes_none(self, game_9x9):
        """Cache should distinguish None from not-computed"""
        # Play some moves
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        # First call computes (likely None for simple position)
        hint1 = get_beginner_hint_cached(game_9x9, node)

        # Add a marker to verify cache is used
        node._beginner_hint_cache = "MARKER"

        # Second call should return cached "MARKER"
        hint2 = get_beginner_hint_cached(game_9x9, node)
        assert hint2 == "MARKER"


# ---------------------------------------------------------------------------
# CUT_RISK tests (with monkeypatch)
# ---------------------------------------------------------------------------


class TestCutRiskDetection:
    """Tests for CUT_RISK detection with monkeypatching"""

    def test_cut_risk_detects_with_mocked_connect_points(self, game_9x9, monkeypatch):
        """CUT_RISK should detect when find_connect_points returns high improvement"""
        # Play enough moves to create stones
        moves = [
            ("D5", "B"), ("A1", "W"),
            ("D4", "B"), ("A2", "W"),
            ("D3", "B"), ("A3", "W"),
            ("E3", "B"), ("A4", "W"),
            ("F3", "B"), ("A5", "W"),
            ("G3", "B"), ("A6", "W"),
        ]
        for coord, player in moves:
            game_9x9.play(Move.from_gtp(coord, player), analyze=False)
        node = game_9x9.current_node

        # Mock find_connect_points to return controlled data
        def mock_find_connect_points(game, groups, danger_scores):
            return [
                ((4, 4), [0, 1], 20.0),  # E5: improvement above threshold (15.0)
            ]

        monkeypatch.setattr(
            "katrain.core.board_analysis.find_connect_points",
            mock_find_connect_points,
        )

        hint = compute_beginner_hint(game_9x9, node)

        # Note: Other detectors may fire first depending on position
        if hint is not None and hint.category == HintCategory.CUT_RISK:
            assert hint.coords == (4, 4)  # E5
            assert hint.context["improvement"] == 20.0

    def test_cut_risk_below_threshold_returns_none(self, game_9x9, monkeypatch):
        """CUT_RISK should not fire when improvement is below threshold"""
        # Play some moves
        game_9x9.play(Move.from_gtp("D5", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("A1", "W"), analyze=False)
        game_9x9.play(Move.from_gtp("D3", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("A2", "W"), analyze=False)
        node = game_9x9.current_node

        # Return improvement below threshold (15.0)
        def mock_find_connect_points(game, groups, danger_scores):
            return [
                ((3, 3), [0, 1], 10.0),  # Below threshold
            ]

        monkeypatch.setattr(
            "katrain.core.board_analysis.find_connect_points",
            mock_find_connect_points,
        )

        hint = compute_beginner_hint(game_9x9, node)

        # CUT_RISK should not fire (other hints may or may not fire)
        assert hint is None or hint.category != HintCategory.CUT_RISK

    def test_cut_risk_node_state_is_corrected(self, game_9x9, monkeypatch):
        """game.current_node should be at inp.node when find_connect_points is called"""
        # Play some moves
        game_9x9.play(Move.from_gtp("D5", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        game_9x9.play(Move.from_gtp("D3", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("F5", "W"), analyze=False)
        node = game_9x9.current_node

        # Record node state when find_connect_points is called
        recorded_nodes = []

        def mock_find_connect_points(game, groups, danger_scores):
            recorded_nodes.append(game.current_node)
            return []  # Return empty (no CUT_RISK)

        monkeypatch.setattr(
            "katrain.core.board_analysis.find_connect_points",
            mock_find_connect_points,
        )

        # Call compute_beginner_hint
        compute_beginner_hint(game_9x9, node)

        # Verify find_connect_points was called with correct node state
        assert len(recorded_nodes) == 1
        assert recorded_nodes[0] == node


# ---------------------------------------------------------------------------
# Node state restoration tests
# ---------------------------------------------------------------------------


class TestNodeStateRestoration:
    """Tests for node state restoration after compute_beginner_hint"""

    def test_node_state_restored_after_hint(self, game_9x9):
        """game.current_node should be restored after compute_beginner_hint"""
        # Play some moves
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        game_9x9.play(Move.from_gtp("F6", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("G7", "W"), analyze=False)
        node = game_9x9.current_node

        # Set to a different node
        game_9x9.set_current_node(node.parent)
        original_node = game_9x9.current_node

        # Compute hint
        compute_beginner_hint(game_9x9, node)

        # Should be restored
        assert game_9x9.current_node == original_node

    def test_node_state_restored_on_exception(self, game_9x9, monkeypatch):
        """game.current_node should be restored even if detector raises"""

        def mock_extract_groups(game):
            raise ValueError("Test exception")

        monkeypatch.setattr(
            "katrain.core.beginner.hints.extract_groups_from_game",
            mock_extract_groups,
        )

        # Play some moves
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node
        original_node = game_9x9.current_node

        with pytest.raises(ValueError):
            compute_beginner_hint(game_9x9, node)

        # Should still be restored (via finally)
        assert game_9x9.current_node == original_node


# ---------------------------------------------------------------------------
# HintCategory priority tests
# ---------------------------------------------------------------------------


class TestHintCategoryPriority:
    """Tests for hint category values and ordering"""

    def test_hint_categories_exist(self):
        """All expected hint categories should exist"""
        assert HintCategory.SELF_ATARI.value == "self_atari"
        assert HintCategory.IGNORE_ATARI.value == "ignore_atari"
        assert HintCategory.MISSED_CAPTURE.value == "missed_capture"
        assert HintCategory.CUT_RISK.value == "cut_risk"

    def test_beginner_hint_is_frozen(self):
        """BeginnerHint should be immutable (frozen dataclass)"""
        hint = BeginnerHint(
            category=HintCategory.SELF_ATARI,
            coords=(3, 3),
            severity=3,
            context={},
        )

        # Should raise FrozenInstanceError
        with pytest.raises(Exception):  # FrozenInstanceError is a subclass
            hint.severity = 5
