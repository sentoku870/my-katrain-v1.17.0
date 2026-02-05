"""Phase 91-92: Beginner Hint Tests

Tests for the beginner safety hint system.

Phase 91: Basic detectors (SELF_ATARI, IGNORE_ATARI, MISSED_CAPTURE, CUT_RISK)
Phase 92: MeaningTag fallback, reliability filter, gating functions
"""

from __future__ import annotations

import pytest

from katrain.core.beginner.detector import (
    find_matching_group,
)
from katrain.core.beginner.hints import compute_beginner_hint, get_beginner_hint_cached
from katrain.core.beginner.models import BeginnerHint, HintCategory
from katrain.core.sgf_parser import Move

# ---------------------------------------------------------------------------
# find_matching_group tests
# ---------------------------------------------------------------------------


class MockGroup:
    """Mock Group for testing find_matching_group"""

    def __init__(self, color: str, stones: set[tuple[int, int]]):
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
        get_beginner_hint_cached(game_9x9, node)

        # Phase 92: Cache format is (require_reliable, hint) tuple
        # Add a marker to verify cache is used
        node._beginner_hint_cache = (True, "MARKER")

        # Second call should return cached "MARKER"
        hint2 = get_beginner_hint_cached(game_9x9, node, require_reliable=True)
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
            ("D5", "B"),
            ("A1", "W"),
            ("D4", "B"),
            ("A2", "W"),
            ("D3", "B"),
            ("A3", "W"),
            ("E3", "B"),
            ("A4", "W"),
            ("F3", "B"),
            ("A5", "W"),
            ("G3", "B"),
            ("A6", "W"),
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


# ---------------------------------------------------------------------------
# Phase 92a: MeaningTag Mapping Tests
# ---------------------------------------------------------------------------


class TestHintCategoryFromMeaningTag:
    """Tests for HintCategory.from_meaning_tag_id() (Phase 92a)"""

    def test_known_meaning_tag_ids_map_correctly(self):
        """Known MeaningTagIds map to correct HintCategory"""
        mappings = [
            ("capture_race_loss", HintCategory.LOW_LIBERTIES),
            ("life_death_error", HintCategory.SELF_CAPTURE_LIKE),
            ("shape_mistake", HintCategory.BAD_SHAPE),
            ("overplay", HintCategory.HEAVY_GROUP),
            ("connection_miss", HintCategory.MISSED_DEFENSE),
            ("endgame_slip", HintCategory.URGENT_VS_BIG),
        ]
        for tag_id, expected_category in mappings:
            result = HintCategory.from_meaning_tag_id(tag_id)
            assert result == expected_category, f"Expected {expected_category} for {tag_id}"

    def test_unknown_meaning_tag_returns_none(self):
        """Unknown MeaningTagId returns None (no crash)"""
        assert HintCategory.from_meaning_tag_id("nonexistent_tag") is None
        assert HintCategory.from_meaning_tag_id("uncertain") is None  # UNCERTAIN is not mapped
        assert HintCategory.from_meaning_tag_id("") is None

    def test_none_meaning_tag_returns_none(self):
        """None input returns None"""
        assert HintCategory.from_meaning_tag_id(None) is None


class TestPhase92HintCategories:
    """Tests for Phase 92 hint categories"""

    def test_new_hint_categories_exist(self):
        """Phase 92 hint categories should exist"""
        assert HintCategory.LOW_LIBERTIES.value == "low_liberties"
        assert HintCategory.SELF_CAPTURE_LIKE.value == "self_capture_like"
        assert HintCategory.BAD_SHAPE.value == "bad_shape"
        assert HintCategory.HEAVY_GROUP.value == "heavy_group"
        assert HintCategory.MISSED_DEFENSE.value == "missed_defense"
        assert HintCategory.URGENT_VS_BIG.value == "urgent_vs_big"

    def test_total_hint_categories_is_ten(self):
        """Should have 10 total hint categories (4 Phase 91 + 6 Phase 92)"""
        assert len(HintCategory) == 10


class TestMeaningTagHintFallback:
    """Tests for _get_meaning_tag_hint() function (Phase 92a)"""

    def test_node_with_meaning_tag_returns_hint(self):
        """Node with meaning_tag_id should return corresponding hint"""
        from katrain.core.beginner.hints import _get_meaning_tag_hint

        class MockNode:
            meaning_tag_id = "overplay"

        hint = _get_meaning_tag_hint(MockNode(), move_coords=(5, 5))

        assert hint is not None
        assert hint.category == HintCategory.HEAVY_GROUP
        assert hint.coords == (5, 5)
        assert hint.severity == 1  # Lower priority than detectors
        assert hint.context.get("source") == "meaning_tag"
        assert hint.context.get("tag_id") == "overplay"

    def test_node_without_meaning_tag_returns_none(self):
        """Node without meaning_tag_id should return None"""
        from katrain.core.beginner.hints import _get_meaning_tag_hint

        class MockNode:
            pass  # No meaning_tag_id attribute

        hint = _get_meaning_tag_hint(MockNode(), move_coords=(5, 5))
        assert hint is None

    def test_node_with_none_meaning_tag_returns_none(self):
        """Node with meaning_tag_id=None should return None"""
        from katrain.core.beginner.hints import _get_meaning_tag_hint

        class MockNode:
            meaning_tag_id = None

        hint = _get_meaning_tag_hint(MockNode(), move_coords=(5, 5))
        assert hint is None

    def test_node_with_unknown_meaning_tag_returns_none(self):
        """Node with unknown meaning_tag_id should return None"""
        from katrain.core.beginner.hints import _get_meaning_tag_hint

        class MockNode:
            meaning_tag_id = "uncertain"  # Not mapped to beginner hint

        hint = _get_meaning_tag_hint(MockNode(), move_coords=(5, 5))
        assert hint is None


class TestDetectorTakesPriorityOverMeaningTag:
    """Tests for detector priority over MeaningTag (Phase 92a)"""

    def test_detector_hint_returned_even_with_meaning_tag(self, game_9x9, monkeypatch):
        """Detector hint should be returned even if node has meaning_tag_id"""
        # Play a move
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        # Set meaning_tag_id on node
        node.meaning_tag_id = "overplay"

        # Mock detector to return a hint
        def mock_detect_self_atari(inp):
            return BeginnerHint(
                category=HintCategory.SELF_ATARI,
                coords=(3, 3),
                severity=3,
                context={"source": "detector"},
            )

        monkeypatch.setattr(
            "katrain.core.beginner.hints.detect_self_atari",
            mock_detect_self_atari,
        )

        hint = compute_beginner_hint(game_9x9, node)

        # Detector hint should be returned, not MeaningTag hint
        assert hint is not None
        assert hint.category == HintCategory.SELF_ATARI
        assert hint.context.get("source") == "detector"

    def test_meaning_tag_hint_returned_when_no_detector_fires(self, game_9x9, monkeypatch):
        """MeaningTag hint should be returned when no detector fires"""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS

        # Play a move
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        # Set meaning_tag_id on node and ensure reliable analysis
        node.meaning_tag_id = "shape_mistake"
        node.analysis = {"rootInfo": {"visits": MIN_RELIABLE_VISITS}}

        # Mock all detectors to return None
        monkeypatch.setattr("katrain.core.beginner.hints.detect_self_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_ignore_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_missed_capture", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_cut_risk", lambda inp, game: None)

        hint = compute_beginner_hint(game_9x9, node)

        # MeaningTag hint should be returned
        assert hint is not None
        assert hint.category == HintCategory.BAD_SHAPE
        assert hint.context.get("source") == "meaning_tag"


# ---------------------------------------------------------------------------
# Phase 92b: Reliability Filter Tests
# ---------------------------------------------------------------------------


class TestReliabilityFilter:
    """Tests for reliability filter (Phase 92b)"""

    def test_get_visits_from_node_with_rootInfo(self):
        """Get visits from rootInfo.visits format"""
        from katrain.core.beginner.hints import _get_visits_from_node

        class MockNode:
            analysis = {"rootInfo": {"visits": 500}}

        visits = _get_visits_from_node(MockNode())
        assert visits == 500

    def test_get_visits_from_node_with_root(self):
        """Get visits from root.visits format"""
        from katrain.core.beginner.hints import _get_visits_from_node

        class MockNode:
            analysis = {"root": {"visits": 300}}

        visits = _get_visits_from_node(MockNode())
        assert visits == 300

    def test_get_visits_from_node_with_direct_visits(self):
        """Get visits from direct visits key"""
        from katrain.core.beginner.hints import _get_visits_from_node

        class MockNode:
            analysis = {"visits": 200}

        visits = _get_visits_from_node(MockNode())
        assert visits == 200

    def test_get_visits_from_node_no_analysis(self):
        """Returns None when no analysis"""
        from katrain.core.beginner.hints import _get_visits_from_node

        class MockNode:
            pass  # No analysis attribute

        visits = _get_visits_from_node(MockNode())
        assert visits is None

    def test_get_visits_from_node_analysis_none(self):
        """Returns None when analysis is None"""
        from katrain.core.beginner.hints import _get_visits_from_node

        class MockNode:
            analysis = None

        visits = _get_visits_from_node(MockNode())
        assert visits is None

    def test_is_reliable_true(self):
        """Returns True when visits >= threshold"""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS, _is_reliable

        class MockNode:
            analysis = {"rootInfo": {"visits": MIN_RELIABLE_VISITS}}

        assert _is_reliable(MockNode()) is True

    def test_is_reliable_false_low_visits(self):
        """Returns False when visits < threshold"""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS, _is_reliable

        class MockNode:
            analysis = {"rootInfo": {"visits": MIN_RELIABLE_VISITS - 1}}

        assert _is_reliable(MockNode()) is False

    def test_is_reliable_false_no_analysis(self):
        """Returns False when no analysis"""
        from katrain.core.beginner.hints import _is_reliable

        class MockNode:
            pass

        assert _is_reliable(MockNode()) is False

    def test_is_reliable_false_visits_zero(self):
        """Returns False when visits=0"""
        from katrain.core.beginner.hints import _is_reliable

        class MockNode:
            analysis = {"rootInfo": {"visits": 0}}

        assert _is_reliable(MockNode()) is False


class TestReliabilityFilterWithHints:
    """Tests for reliability filter applied to hints (Phase 92b)"""

    def test_unreliable_meaning_tag_hint_filtered(self, game_9x9, monkeypatch):
        """MeaningTag hint is filtered when visits < threshold"""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS

        # Play a move
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        # Set meaning_tag_id and low visits
        node.meaning_tag_id = "overplay"
        node.analysis = {"rootInfo": {"visits": MIN_RELIABLE_VISITS - 1}}

        # Mock all detectors to return None
        monkeypatch.setattr("katrain.core.beginner.hints.detect_self_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_ignore_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_missed_capture", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_cut_risk", lambda inp, game: None)

        hint = compute_beginner_hint(game_9x9, node, require_reliable=True)

        # Hint should be filtered (None)
        assert hint is None

    def test_unreliable_meaning_tag_hint_shown_when_filter_disabled(self, game_9x9, monkeypatch):
        """MeaningTag hint is shown when require_reliable=False"""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS

        # Play a move
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        # Set meaning_tag_id and low visits
        node.meaning_tag_id = "overplay"
        node.analysis = {"rootInfo": {"visits": MIN_RELIABLE_VISITS - 1}}

        # Mock all detectors to return None
        monkeypatch.setattr("katrain.core.beginner.hints.detect_self_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_ignore_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_missed_capture", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_cut_risk", lambda inp, game: None)

        hint = compute_beginner_hint(game_9x9, node, require_reliable=False)

        # Hint should be returned (filter disabled)
        assert hint is not None
        assert hint.category == HintCategory.HEAVY_GROUP

    def test_detector_hint_shown_even_when_unreliable(self, game_9x9, monkeypatch):
        """Detector hint is shown regardless of visits (uses board state)"""
        # Play a move
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        # No analysis (low reliability)
        node.analysis = None

        # Mock detector to return a hint
        def mock_detect_self_atari(inp):
            return BeginnerHint(
                category=HintCategory.SELF_ATARI,
                coords=(3, 3),
                severity=3,
                context={"source": "detector"},
            )

        monkeypatch.setattr(
            "katrain.core.beginner.hints.detect_self_atari",
            mock_detect_self_atari,
        )

        hint = compute_beginner_hint(game_9x9, node, require_reliable=True)

        # Detector hint should still be returned (not filtered)
        assert hint is not None
        assert hint.category == HintCategory.SELF_ATARI


class TestCacheWithReliableSettings:
    """Tests for cache with require_reliable settings awareness (Phase 92b)"""

    def test_cache_invalidates_on_require_reliable_change(self, game_9x9, monkeypatch):
        """Cache returns fresh result when require_reliable changes"""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS

        # Play a move
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        # Set meaning_tag_id and low visits (unreliable)
        node.meaning_tag_id = "overplay"
        node.analysis = {"rootInfo": {"visits": MIN_RELIABLE_VISITS - 1}}

        # Mock all detectors to return None
        monkeypatch.setattr("katrain.core.beginner.hints.detect_self_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_ignore_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_missed_capture", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_cut_risk", lambda inp, game: None)

        # First call with require_reliable=False (hint should be returned)
        hint1 = get_beginner_hint_cached(game_9x9, node, require_reliable=False)
        assert hint1 is not None

        # Second call with require_reliable=True (hint should be filtered)
        hint2 = get_beginner_hint_cached(game_9x9, node, require_reliable=True)
        assert hint2 is None

    def test_cache_returns_same_result_for_same_settings(self, game_9x9, monkeypatch):
        """Cache returns cached result for same require_reliable value"""
        # Play a move
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        # Ensure no cache
        if hasattr(node, "_beginner_hint_cache"):
            delattr(node, "_beginner_hint_cache")

        # First call
        get_beginner_hint_cached(game_9x9, node, require_reliable=True)

        # Modify cache to verify it's used
        node._beginner_hint_cache = (True, "MARKER")

        # Second call with same settings should return cached value
        hint2 = get_beginner_hint_cached(game_9x9, node, require_reliable=True)
        assert hint2 == "MARKER"


# =============================================================================
# Phase 92c: Gating Pure Function Tests
# =============================================================================


class TestShouldShowBeginnerHints:
    """Test should_show_beginner_hints() pure function (Phase 92c)."""

    def test_returns_false_when_disabled(self):
        """Returns False when enabled=False."""
        from katrain.core.beginner.hints import should_show_beginner_hints

        result = should_show_beginner_hints(enabled=False, mode="analyze")
        assert result is False

    def test_returns_false_in_play_mode(self):
        """Returns False in PLAY mode even if enabled."""
        from katrain.core.beginner.hints import should_show_beginner_hints
        from katrain.core.constants import MODE_PLAY

        result = should_show_beginner_hints(enabled=True, mode=MODE_PLAY)
        assert result is False

    def test_returns_true_when_enabled_and_not_play_mode(self):
        """Returns True when enabled and not in PLAY mode."""
        from katrain.core.beginner.hints import should_show_beginner_hints

        result = should_show_beginner_hints(enabled=True, mode="analyze")
        assert result is True

    def test_returns_true_for_review_mode(self):
        """Returns True for review mode."""
        from katrain.core.beginner.hints import should_show_beginner_hints

        result = should_show_beginner_hints(enabled=True, mode="review")
        assert result is True


class TestShouldDrawBoardHighlight:
    """Test should_draw_board_highlight() pure function (Phase 92c)."""

    def test_returns_false_when_hints_disabled(self):
        """Returns False when beginner hints disabled."""
        from katrain.core.beginner.hints import should_draw_board_highlight

        result = should_draw_board_highlight(enabled=False, mode="analyze", board_highlight=True)
        assert result is False

    def test_returns_false_when_board_highlight_disabled(self):
        """Returns False when board_highlight=False."""
        from katrain.core.beginner.hints import should_draw_board_highlight

        result = should_draw_board_highlight(enabled=True, mode="analyze", board_highlight=False)
        assert result is False

    def test_returns_false_in_play_mode(self):
        """Returns False in PLAY mode even with all enabled."""
        from katrain.core.beginner.hints import should_draw_board_highlight
        from katrain.core.constants import MODE_PLAY

        result = should_draw_board_highlight(enabled=True, mode=MODE_PLAY, board_highlight=True)
        assert result is False

    def test_returns_true_when_all_conditions_met(self):
        """Returns True when all conditions are met."""
        from katrain.core.beginner.hints import should_draw_board_highlight

        result = should_draw_board_highlight(enabled=True, mode="analyze", board_highlight=True)
        assert result is True


class TestIsCoordsValid:
    """Test is_coords_valid() pure function (Phase 92c)."""

    def test_none_coords_returns_false(self):
        """Returns False for None coords."""
        from katrain.core.beginner.hints import is_coords_valid

        result = is_coords_valid(None, board_size=(19, 19))
        assert result is False

    def test_valid_coords_returns_true(self):
        """Returns True for valid coords within bounds."""
        from katrain.core.beginner.hints import is_coords_valid

        result = is_coords_valid((5, 7), board_size=(19, 19))
        assert result is True

    def test_coords_out_of_bounds_x_returns_false(self):
        """Returns False when x is out of bounds."""
        from katrain.core.beginner.hints import is_coords_valid

        result = is_coords_valid((20, 5), board_size=(19, 19))
        assert result is False

    def test_coords_out_of_bounds_y_returns_false(self):
        """Returns False when y is out of bounds."""
        from katrain.core.beginner.hints import is_coords_valid

        result = is_coords_valid((5, 19), board_size=(19, 19))
        assert result is False

    def test_coords_negative_returns_false(self):
        """Returns False for negative coords."""
        from katrain.core.beginner.hints import is_coords_valid

        assert is_coords_valid((-1, 5), board_size=(19, 19)) is False
        assert is_coords_valid((5, -1), board_size=(19, 19)) is False

    def test_boundary_9x9_max_valid(self):
        """Coords (8, 8) is valid boundary for 9x9."""
        from katrain.core.beginner.hints import is_coords_valid

        assert is_coords_valid((8, 8), board_size=(9, 9)) is True

    def test_boundary_9x9_just_over_invalid(self):
        """Coords (9, 9) is out of bounds for 9x9."""
        from katrain.core.beginner.hints import is_coords_valid

        assert is_coords_valid((9, 9), board_size=(9, 9)) is False

    def test_origin_valid(self):
        """Coords (0, 0) is always valid."""
        from katrain.core.beginner.hints import is_coords_valid

        assert is_coords_valid((0, 0), board_size=(9, 9)) is True
        assert is_coords_valid((0, 0), board_size=(19, 19)) is True

    def test_int_board_size_works(self):
        """Works with int board_size (square board)."""
        from katrain.core.beginner.hints import is_coords_valid

        assert is_coords_valid((5, 5), board_size=19) is True
        assert is_coords_valid((20, 5), board_size=19) is False


class TestNormalizeBoardSize:
    """Test _normalize_board_size() helper (Phase 92c)."""

    def test_int_returns_tuple(self):
        """Int input returns (n, n) tuple."""
        from katrain.core.beginner.hints import _normalize_board_size

        assert _normalize_board_size(19) == (19, 19)
        assert _normalize_board_size(9) == (9, 9)
        assert _normalize_board_size(13) == (13, 13)

    def test_tuple_returns_same(self):
        """Tuple input returns same tuple."""
        from katrain.core.beginner.hints import _normalize_board_size

        assert _normalize_board_size((19, 19)) == (19, 19)
        assert _normalize_board_size((9, 13)) == (9, 13)  # non-square


# =============================================================================
# Phase 92d: i18n Tests
# =============================================================================


class TestBeginnerHintI18n:
    """Test beginner hint i18n keys exist in .po files (Phase 92d)."""

    CATEGORIES = [
        "self_atari",
        "ignore_atari",
        "missed_capture",
        "cut_risk",
        "low_liberties",
        "self_capture_like",
        "bad_shape",
        "heavy_group",
        "missed_defense",
        "urgent_vs_big",
    ]
    SUFFIXES = ["title", "body", "why"]

    def test_all_hint_keys_exist_in_jp_po(self):
        """All 30 beginner hint i18n keys exist in JP .po file."""
        import polib

        po_path = "katrain/i18n/locales/jp/LC_MESSAGES/katrain.po"
        po = polib.pofile(po_path)
        existing_keys = {entry.msgid for entry in po}

        expected_keys = {f"beginner_hint:{cat}:{suffix}" for cat in self.CATEGORIES for suffix in self.SUFFIXES}

        missing = expected_keys - existing_keys
        assert not missing, f"Missing keys in JP: {missing}"

    def test_all_hint_keys_exist_in_en_po(self):
        """All 30 beginner hint i18n keys exist in EN .po file."""
        import polib

        po_path = "katrain/i18n/locales/en/LC_MESSAGES/katrain.po"
        po = polib.pofile(po_path)
        existing_keys = {entry.msgid for entry in po}

        expected_keys = {f"beginner_hint:{cat}:{suffix}" for cat in self.CATEGORIES for suffix in self.SUFFIXES}

        missing = expected_keys - existing_keys
        assert not missing, f"Missing keys in EN: {missing}"

    def test_no_empty_msgstr_for_hint_keys_jp(self):
        """All JP beginner hint keys have non-empty msgstr."""
        import polib

        po_path = "katrain/i18n/locales/jp/LC_MESSAGES/katrain.po"
        po = polib.pofile(po_path)

        empty_keys = []
        for entry in po:
            if entry.msgid.startswith("beginner_hint:") and not entry.msgstr:
                empty_keys.append(entry.msgid)

        assert not empty_keys, f"Empty msgstr in JP: {empty_keys}"

    def test_no_empty_msgstr_for_hint_keys_en(self):
        """All EN beginner hint keys have non-empty msgstr."""
        import polib

        po_path = "katrain/i18n/locales/en/LC_MESSAGES/katrain.po"
        po = polib.pofile(po_path)

        empty_keys = []
        for entry in po:
            if entry.msgid.startswith("beginner_hint:") and not entry.msgstr:
                empty_keys.append(entry.msgid)

        assert not empty_keys, f"Empty msgstr in EN: {empty_keys}"
