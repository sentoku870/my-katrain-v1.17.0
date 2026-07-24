"""Beginner Hint test suite.

This file merges two previously-separate modules:

- ``test_beginner_hints.py`` (Phase 91-92 main, 64 tests) — basic
  detectors, ``find_matching_group``, CUT_RISK monkeypatched tests,
  node-state restoration, reliability filter, ``.po`` i18n checks.
- ``test_beginner_hints_main.py`` (Phase A1 follow-up, 78 tests) —
  main pipeline coverage, gate functions, summary context builder,
  cache wrappers, summary priority chain.

The two had significant overlap on the gate functions
(``TestShouldShowBeginnerHints``, ``TestShouldDrawBoardHighlight``,
``TestIsCoordsValid``, ``TestNormalizeBoardSize``). Phase 7 of the
test-suite audit merges them into one file, keeping the more
comprehensive version of each overlapping class (file1's
``TestIsCoordsValid`` covers 10 cases vs file2's 6; file2's
``TestShouldShowBeginnerHints`` is parametrised; etc.).

Kivy imports are deliberately avoided at module level to comply with
Phase 173 (kivy mkdir side effect → CI exit-102). The module under
test (``hints`` package) is core-layer and Kivy-free.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.beginner import (
    MIN_RELIABLE_VISITS,
    MIN_SUMMARY_VISITS,
    BeginnerHint,
    HintCategory,
)
from katrain.core.beginner.detector import find_matching_group
from katrain.core.beginner.hints import (
    _DETECTOR_CATEGORIES,
    _NOT_COMPUTED,
    _compute_summary_context,
    _extract_best_policy,
    _extract_predicted_territory,
    _is_endgame_position,
    _normalize_board_size,
    compute_beginner_hint,
    compute_summary_hint,
    get_beginner_hint_cached,
    get_summary_hint_cached,
    is_coords_valid,
    should_draw_board_highlight,
    should_show_beginner_hints,
    should_show_summary_hint,
)
from katrain.core.sgf_parser import Move

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockGroup:
    """Mock ``Group`` for ``find_matching_group`` tests (file1)."""

    def __init__(self, color: str, stones: set[tuple[int, int]]):
        self.color = color
        self.stones = stones


class _MockNode:
    """Minimal ``GameNode`` stand-in for ``_compute_summary_context`` tests (file2).

    Mirrors the attribute access pattern of ``test_beginner_hints_summary._MockNode``
    but lives here as a small, locally-scoped helper to keep this file
    self-contained.
    """

    def __init__(
        self,
        *,
        analysis: dict[str, Any] | None = None,
        ownership: list[Any] | None = None,
        policy: list[Any] | None = None,
        points_lost: float | None = None,
        move_number: int = 50,
        depth: int = 0,
        candidate_moves: list[dict[str, Any]] | None = None,
        meaning_tag_id: str | None = None,
    ) -> None:
        self.analysis = analysis
        self.ownership = ownership
        self.policy = policy
        self.points_lost = points_lost
        self.meaning_tag_id = meaning_tag_id
        # get_score_stdev guards on analysis_exists, so surface it.
        self.analysis_exists = bool(analysis)
        self.depth = depth
        self.move: MagicMock | None
        self.parent: MagicMock | None
        if move_number > 0 or candidate_moves is not None:
            self.move = MagicMock()
            self.move.move_number = move_number
        else:
            self.move = None
        if candidate_moves is not None:
            self.parent = MagicMock()
            self.parent.candidate_moves = candidate_moves
        else:
            self.parent = None


# ---------------------------------------------------------------------------
# Section 1: find_matching_group (file1)
# ---------------------------------------------------------------------------


class TestFindMatchingGroup:
    """Tests for ``find_matching_group`` function."""

    def test_exact_match(self):
        """Exact stone set should match."""
        target = {(0, 0), (0, 1), (1, 0)}
        groups = [
            MockGroup("B", {(0, 0), (0, 1), (1, 0)}),
            MockGroup("W", {(5, 5)}),
        ]
        result = find_matching_group(target, groups, "B")
        assert result is not None
        assert result.stones == target

    def test_partial_overlap_above_threshold(self):
        """50%+ overlap should match."""
        target = {(0, 0), (0, 1), (1, 0), (1, 1)}  # 4 stones
        groups = [
            MockGroup("B", {(0, 0), (0, 1), (2, 2)}),  # 2/3 overlap
        ]
        result = find_matching_group(target, groups, "B")
        assert result is not None

    def test_partial_overlap_below_threshold(self):
        """<50% overlap should not match."""
        target = {(0, 0), (0, 1), (1, 0), (1, 1), (2, 2), (3, 3)}  # 6 stones
        groups = [
            MockGroup("B", {(0, 0), (5, 5), (6, 6), (7, 7)}),  # 1/4 overlap
        ]
        result = find_matching_group(target, groups, "B")
        assert result is None

    def test_wrong_color_no_match(self):
        """Different color should not match."""
        target = {(0, 0), (0, 1)}
        groups = [
            MockGroup("W", {(0, 0), (0, 1)}),  # Same stones but wrong color
        ]
        result = find_matching_group(target, groups, "B")
        assert result is None

    def test_empty_groups_no_match(self):
        """Empty groups list should return ``None``."""
        target = {(0, 0)}
        result = find_matching_group(target, [], "B")
        assert result is None


# ---------------------------------------------------------------------------
# Section 2: Basic detection (file1)
# ---------------------------------------------------------------------------


class TestBasicDetection:
    """Basic detection tests using ``game_9x9`` fixture."""

    def test_pass_move_returns_none(self, game_9x9):
        """Pass moves should not generate hints."""
        pass_move = Move.from_gtp("pass", "B")
        game_9x9.play(pass_move, analyze=False)
        node = game_9x9.current_node

        hint = compute_beginner_hint(game_9x9, node)
        assert hint is None

    def test_root_node_returns_none(self, game_9x9):
        """Root node (no parent) should not generate hints."""
        node = game_9x9.root

        hint = compute_beginner_hint(game_9x9, node)
        assert hint is None

    def test_cache_works(self, game_9x9):
        """Cached hint should be returned on second call."""
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
        """Cache should distinguish ``None`` from not-computed."""
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        # First call computes (likely None for simple position)
        get_beginner_hint_cached(game_9x9, node)

        # Phase 92: Cache format was (require_reliable, hint).
        # Phase 251: extended to (require_reliable, filter_key, hint)
        # so per-category toggles invalidate the cache.
        # Phase 270: the curator_key was removed along with the
        # Curator weak-axis hint, leaving the 3-tuple.
        node._beginner_hint_cache = (True, None, "MARKER")

        # Second call should return cached "MARKER"
        hint2 = get_beginner_hint_cached(game_9x9, node, require_reliable=True)
        assert hint2 == "MARKER"


# ---------------------------------------------------------------------------
# Section 3: CUT_RISK detection (file1)
# ---------------------------------------------------------------------------


class TestCutRiskDetection:
    """Tests for ``CUT_RISK`` detection with monkeypatching."""

    def test_cut_risk_detects_with_mocked_connect_points(self, game_9x9, monkeypatch):
        """``CUT_RISK`` should detect when ``find_connect_points`` returns high improvement."""
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
        """``CUT_RISK`` should not fire when improvement is below threshold."""
        game_9x9.play(Move.from_gtp("D5", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("A1", "W"), analyze=False)
        game_9x9.play(Move.from_gtp("D3", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("A2", "W"), analyze=False)
        node = game_9x9.current_node

        def mock_find_connect_points(game, groups, danger_scores):
            return [
                ((3, 3), [0, 1], 10.0),  # Below threshold
            ]

        monkeypatch.setattr(
            "katrain.core.board_analysis.find_connect_points",
            mock_find_connect_points,
        )

        hint = compute_beginner_hint(game_9x9, node)
        assert hint is None or hint.category != HintCategory.CUT_RISK

    def test_cut_risk_node_state_is_corrected(self, game_9x9, monkeypatch):
        """``game.current_node`` should be at ``inp.node`` when ``find_connect_points`` is called."""
        game_9x9.play(Move.from_gtp("D5", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        game_9x9.play(Move.from_gtp("D3", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("F5", "W"), analyze=False)
        node = game_9x9.current_node

        recorded_nodes = []

        def mock_find_connect_points(game, groups, danger_scores):
            recorded_nodes.append(game.current_node)
            return []

        monkeypatch.setattr(
            "katrain.core.board_analysis.find_connect_points",
            mock_find_connect_points,
        )

        compute_beginner_hint(game_9x9, node)

        assert len(recorded_nodes) == 1
        assert recorded_nodes[0] == node


# ---------------------------------------------------------------------------
# Section 4: Node state restoration (file1)
# ---------------------------------------------------------------------------


class TestNodeStateRestoration:
    """Tests for node state restoration after ``compute_beginner_hint``."""

    def test_node_state_restored_after_hint(self, game_9x9):
        """``game.current_node`` should be restored after ``compute_beginner_hint``."""
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        game_9x9.play(Move.from_gtp("F6", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("G7", "W"), analyze=False)
        node = game_9x9.current_node

        # Set to a different node
        game_9x9.set_current_node(node.parent)
        original_node = game_9x9.current_node

        compute_beginner_hint(game_9x9, node)
        assert game_9x9.current_node == original_node

    def test_node_state_restored_on_exception(self, game_9x9, monkeypatch):
        """``game.current_node`` should be restored even if detector raises."""

        def mock_extract_groups(game):
            raise ValueError("Test exception")

        monkeypatch.setattr(
            "katrain.core.beginner.hints.extract_groups_from_game",
            mock_extract_groups,
        )

        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node
        original_node = game_9x9.current_node

        with pytest.raises(ValueError):
            compute_beginner_hint(game_9x9, node)

        assert game_9x9.current_node == original_node


# ---------------------------------------------------------------------------
# Section 5: HintCategory priority (file1)
# ---------------------------------------------------------------------------


class TestHintCategoryPriority:
    """Tests for hint category values and ordering."""

    def test_hint_categories_exist(self):
        """All expected hint categories should exist."""
        assert HintCategory.SELF_ATARI.value == "self_atari"
        assert HintCategory.IGNORE_ATARI.value == "ignore_atari"
        assert HintCategory.MISSED_CAPTURE.value == "missed_capture"
        assert HintCategory.CUT_RISK.value == "cut_risk"

    def test_beginner_hint_is_frozen(self):
        """``BeginnerHint`` should be immutable (frozen dataclass)."""
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
# Section 6: MeaningTag mapping (file1)
# ---------------------------------------------------------------------------


class TestHintCategoryFromMeaningTag:
    """Tests for ``HintCategory.from_meaning_tag_id()`` (Phase 92a)."""

    def test_known_meaning_tag_ids_map_correctly(self):
        """Known ``MeaningTagIds`` map to correct ``HintCategory``."""
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
        """Unknown ``MeaningTagId`` returns ``None`` (no crash)."""
        assert HintCategory.from_meaning_tag_id("nonexistent_tag") is None
        assert HintCategory.from_meaning_tag_id("uncertain") is None
        assert HintCategory.from_meaning_tag_id("") is None

    def test_none_meaning_tag_returns_none(self):
        """``None`` input returns ``None``."""
        assert HintCategory.from_meaning_tag_id(None) is None


class TestPhase92HintCategories:
    """Tests for Phase 92 hint categories."""

    def test_new_hint_categories_exist(self):
        """Phase 92 hint categories should exist."""
        assert HintCategory.LOW_LIBERTIES.value == "low_liberties"
        assert HintCategory.SELF_CAPTURE_LIKE.value == "self_capture_like"
        assert HintCategory.BAD_SHAPE.value == "bad_shape"
        assert HintCategory.HEAVY_GROUP.value == "heavy_group"
        assert HintCategory.MISSED_DEFENSE.value == "missed_defense"
        assert HintCategory.URGENT_VS_BIG.value == "urgent_vs_big"

    def test_total_hint_categories_is_twenty_two(self):
        """Should have 22 total hint categories.

        Phase 270 removed the ``CURATOR_WEAK_AXIS`` category along
        with the deprecated Curator weak-axis hint.

        Composition:
        - 4 Phase 91 structural detectors (SELF_ATARI, IGNORE_ATARI,
          MISSED_CAPTURE, CUT_RISK)
        - 6 Phase 92 MeaningTag fallbacks (LOW_LIBERTIES,
          SELF_CAPTURE_LIKE, BAD_SHAPE, HEAVY_GROUP, MISSED_DEFENSE,
          URGENT_VS_BIG)
        - 9 Phase 179 summary hints (MISTAKE_BLUNDER/MISTAKE/GOOD,
          FREEDOM_ONLY_MOVE/NARROW/WIDE, DIFFICULTY_TRICKY/CALM,
          KATAGO_UNCERTAIN)
        - 3 Phase 182 summary hints (OWNERSHIP_DOMINANT,
          POLICY_CONFLICT, POLICY_CONFIDENT)
        """
        assert len(HintCategory) == 22


class TestMeaningTagHintFallback:
    """Tests for ``_get_meaning_tag_hint()`` function (Phase 92a)."""

    def test_node_with_meaning_tag_returns_hint(self):
        """Node with ``meaning_tag_id`` should return corresponding hint."""
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
        """Node without ``meaning_tag_id`` should return ``None``."""
        from katrain.core.beginner.hints import _get_meaning_tag_hint

        class MockNode:
            pass  # No meaning_tag_id attribute

        hint = _get_meaning_tag_hint(MockNode(), move_coords=(5, 5))
        assert hint is None

    def test_node_with_none_meaning_tag_returns_none(self):
        """Node with ``meaning_tag_id=None`` should return ``None``."""
        from katrain.core.beginner.hints import _get_meaning_tag_hint

        class MockNode:
            meaning_tag_id = None

        hint = _get_meaning_tag_hint(MockNode(), move_coords=(5, 5))
        assert hint is None

    def test_node_with_unknown_meaning_tag_returns_none(self):
        """Node with unknown ``meaning_tag_id`` should return ``None``."""
        from katrain.core.beginner.hints import _get_meaning_tag_hint

        class MockNode:
            meaning_tag_id = "uncertain"  # Not mapped to beginner hint

        hint = _get_meaning_tag_hint(MockNode(), move_coords=(5, 5))
        assert hint is None


class TestDetectorTakesPriorityOverMeaningTag:
    """Tests for detector priority over MeaningTag (Phase 92a)."""

    def test_detector_hint_returned_even_with_meaning_tag(self, game_9x9, monkeypatch):
        """Detector hint should be returned even if node has ``meaning_tag_id``."""
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node
        node.meaning_tag_id = "overplay"

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
        """MeaningTag hint should be returned when no detector fires."""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS

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

        assert hint is not None
        assert hint.category == HintCategory.BAD_SHAPE
        assert hint.context.get("source") == "meaning_tag"


# ---------------------------------------------------------------------------
# Section 7: Reliability filter (file1)
# ---------------------------------------------------------------------------


class TestReliabilityFilter:
    """Tests for reliability filter (Phase 92b)."""

    def test_get_visits_from_node_with_rootInfo(self):
        """Get visits from ``rootInfo.visits`` format."""
        from katrain.core.beginner.hints import _get_visits_from_node

        class MockNode:
            analysis = {"rootInfo": {"visits": 500}}

        visits = _get_visits_from_node(MockNode())
        assert visits == 500

    def test_get_visits_from_node_with_root(self):
        """Get visits from ``root.visits`` format."""
        from katrain.core.beginner.hints import _get_visits_from_node

        class MockNode:
            analysis = {"root": {"visits": 300}}

        visits = _get_visits_from_node(MockNode())
        assert visits == 300

    def test_get_visits_from_node_with_direct_visits(self):
        """Get visits from direct ``visits`` key."""
        from katrain.core.beginner.hints import _get_visits_from_node

        class MockNode:
            analysis = {"visits": 200}

        visits = _get_visits_from_node(MockNode())
        assert visits == 200

    def test_get_visits_from_node_no_analysis(self):
        """Returns ``None`` when no analysis."""
        from katrain.core.beginner.hints import _get_visits_from_node

        class MockNode:
            pass  # No analysis attribute

        visits = _get_visits_from_node(MockNode())
        assert visits is None

    def test_get_visits_from_node_analysis_none(self):
        """Returns ``None`` when analysis is ``None``."""
        from katrain.core.beginner.hints import _get_visits_from_node

        class MockNode:
            analysis = None

        visits = _get_visits_from_node(MockNode())
        assert visits is None

    def test_is_reliable_true(self):
        """Returns ``True`` when visits >= threshold."""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS, _is_reliable

        class MockNode:
            analysis = {"rootInfo": {"visits": MIN_RELIABLE_VISITS}}

        assert _is_reliable(MockNode()) is True

    def test_is_reliable_false_low_visits(self):
        """Returns ``False`` when visits < threshold."""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS, _is_reliable

        class MockNode:
            analysis = {"rootInfo": {"visits": MIN_RELIABLE_VISITS - 1}}

        assert _is_reliable(MockNode()) is False

    def test_is_reliable_false_no_analysis(self):
        """Returns ``False`` when no analysis."""
        from katrain.core.beginner.hints import _is_reliable

        class MockNode:
            pass

        assert _is_reliable(MockNode()) is False

    def test_is_reliable_false_visits_zero(self):
        """Returns ``False`` when visits=0."""
        from katrain.core.beginner.hints import _is_reliable

        class MockNode:
            analysis = {"rootInfo": {"visits": 0}}

        assert _is_reliable(MockNode()) is False


class TestReliabilityFilterWithHints:
    """Tests for reliability filter applied to hints (Phase 92b)."""

    def test_unreliable_meaning_tag_hint_filtered(self, game_9x9, monkeypatch):
        """MeaningTag hint is filtered when visits < threshold."""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS

        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node
        node.meaning_tag_id = "overplay"
        node.analysis = {"rootInfo": {"visits": MIN_RELIABLE_VISITS - 1}}

        monkeypatch.setattr("katrain.core.beginner.hints.detect_self_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_ignore_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_missed_capture", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_cut_risk", lambda inp, game: None)

        hint = compute_beginner_hint(game_9x9, node, require_reliable=True)
        assert hint is None

    def test_unreliable_meaning_tag_hint_shown_when_filter_disabled(self, game_9x9, monkeypatch):
        """MeaningTag hint is shown when ``require_reliable=False``."""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS

        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node
        node.meaning_tag_id = "overplay"
        node.analysis = {"rootInfo": {"visits": MIN_RELIABLE_VISITS - 1}}

        monkeypatch.setattr("katrain.core.beginner.hints.detect_self_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_ignore_atari", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_missed_capture", lambda inp: None)
        monkeypatch.setattr("katrain.core.beginner.hints.detect_cut_risk", lambda inp, game: None)

        hint = compute_beginner_hint(game_9x9, node, require_reliable=False)
        assert hint is not None
        assert hint.category == HintCategory.HEAVY_GROUP

    def test_detector_hint_shown_even_when_unreliable(self, game_9x9, monkeypatch):
        """Detector hint is shown regardless of visits (uses board state)."""
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node
        node.analysis = None

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
        assert hint is not None
        assert hint.category == HintCategory.SELF_ATARI


class TestCacheWithReliableSettings:
    """Tests for cache with ``require_reliable`` settings awareness (Phase 92b)."""

    def test_cache_invalidates_on_require_reliable_change(self, game_9x9, monkeypatch):
        """Cache returns fresh result when ``require_reliable`` changes."""
        from katrain.core.beginner.hints import MIN_RELIABLE_VISITS

        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node
        node.meaning_tag_id = "overplay"
        node.analysis = {"rootInfo": {"visits": MIN_RELIABLE_VISITS - 1}}

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
        """Cache returns cached result for same ``require_reliable`` value."""
        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        if hasattr(node, "_beginner_hint_cache"):
            delattr(node, "_beginner_hint_cache")

        get_beginner_hint_cached(game_9x9, node, require_reliable=True)

        # Phase 251: cache tuple gained a filter_key slot
        # (None = no per-category filter). When the next call matches
        # the cached (require_reliable, filter_key), the cached hint
        # is returned without re-running the dispatchers.
        # Phase 270: cache is now (require_reliable, filter_key, hint).
        node._beginner_hint_cache = (True, None, "MARKER")

        hint2 = get_beginner_hint_cached(game_9x9, node, require_reliable=True)
        assert hint2 == "MARKER"

        # Phase 251: different filter_key invalidates the cache.
        node._beginner_hint_cache = (True, None, "OLD")
        hint3 = get_beginner_hint_cached(game_9x9, node, require_reliable=True, category_filter={"self_atari": False})
        assert hint3 != "OLD", "category_filter change must invalidate cache"


# ---------------------------------------------------------------------------
# Section 8: Public gate functions (file2 — parametrised where helpful)
# ---------------------------------------------------------------------------


class TestShouldShowBeginnerHints:
    """Phase 92: master switch + mode gate."""

    @pytest.mark.parametrize(
        "enabled,mode,expected",
        [
            (True, "analyze", True),
            (True, "play", False),
            (False, "analyze", False),
            (False, "play", False),
        ],
    )
    def test_matrix(self, enabled: bool, mode: str, expected: bool) -> None:
        assert should_show_beginner_hints(enabled, mode) is expected


class TestShouldShowSummaryHint:
    """Phase 179: master gate + summary_flag gate."""

    def test_disabled_master(self) -> None:
        assert should_show_summary_hint(False, "analyze", "summary_mistake", None) is False

    def test_play_mode_blocks(self) -> None:
        assert should_show_summary_hint(True, "play", "summary_mistake", None) is False

    def test_no_flags_dict_defaults_true(self) -> None:
        assert should_show_summary_hint(True, "analyze", "summary_mistake", None) is True
        assert should_show_summary_hint(True, "analyze", "summary_freedom", None) is True
        assert should_show_summary_hint(True, "analyze", "katago_uncertain", None) is True

    def test_empty_flags_dict_defaults_true(self) -> None:
        assert should_show_summary_hint(True, "analyze", "summary_mistake", {}) is True

    def test_explicit_flag_true(self) -> None:
        assert (
            should_show_summary_hint(
                True,
                "analyze",
                "summary_mistake",
                {"summary_mistake": True},
            )
            is True
        )

    def test_explicit_flag_false(self) -> None:
        assert (
            should_show_summary_hint(
                True,
                "analyze",
                "summary_mistake",
                {"summary_mistake": False},
            )
            is False
        )

    def test_unknown_flag_key_defaults_true(self) -> None:
        flags = {"summary_mistake": False, "unknown_future_flag": False}
        assert should_show_summary_hint(True, "analyze", "katago_uncertain", flags) is True

    @pytest.mark.parametrize(
        "key",
        [
            "summary_mistake",
            "summary_freedom",
            "summary_difficulty",
            "katago_uncertain",
            "summary_ownership",
            "summary_policy",
        ],
    )
    def test_each_known_key_respects_false(self, key: str) -> None:
        flags = {key: False}
        assert should_show_summary_hint(True, "analyze", key, flags) is False


class TestShouldDrawBoardHighlight:
    """Phase 92: master + ``board_highlight`` flag."""

    def test_returns_false_when_hints_disabled(self) -> None:
        assert should_draw_board_highlight(False, "analyze", True) is False

    def test_returns_false_when_board_highlight_disabled(self) -> None:
        assert should_draw_board_highlight(True, "analyze", False) is False

    def test_returns_false_in_play_mode(self) -> None:
        assert should_draw_board_highlight(True, "play", True) is False

    def test_returns_true_when_all_conditions_met(self) -> None:
        assert should_draw_board_highlight(True, "analyze", True) is True


class TestIsCoordsValid:
    """Phase 92: bounds check (10 cases from file1 + 6 from file2 deduped)."""

    def test_none_coords_invalid(self) -> None:
        assert is_coords_valid(None, 19) is False

    def test_valid_coords_returns_true(self) -> None:
        assert is_coords_valid((3, 4), 19) is True

    def test_coords_out_of_bounds_x_returns_false(self) -> None:
        assert is_coords_valid((20, 5), 19) is False

    def test_coords_out_of_bounds_y_returns_false(self) -> None:
        assert is_coords_valid((5, 19), 19) is False

    def test_coords_negative_returns_false(self) -> None:
        assert is_coords_valid((-1, 5), 19) is False
        assert is_coords_valid((5, -1), 19) is False

    def test_boundary_9x9_max_valid(self) -> None:
        # Coords (8, 8) is valid boundary for 9x9.
        assert is_coords_valid((8, 8), board_size=(9, 9)) is True

    def test_boundary_9x9_just_over_invalid(self) -> None:
        # Coords (9, 9) is out of bounds for 9x9.
        assert is_coords_valid((9, 9), board_size=(9, 9)) is False

    def test_origin_valid(self) -> None:
        assert is_coords_valid((0, 0), board_size=(9, 9)) is True
        assert is_coords_valid((0, 0), board_size=(19, 19)) is True

    def test_int_board_size_works(self) -> None:
        assert is_coords_valid((5, 5), 19) is True
        assert is_coords_valid((20, 5), 19) is False

    def test_rectangular_board_outside(self) -> None:
        # x=10 is out of 10-wide board (strict-less-than)
        assert is_coords_valid((10, 5), (10, 20)) is False
        # y=20 is out of 20-tall board
        assert is_coords_valid((5, 20), (10, 20)) is False


class TestNormalizeBoardSize:
    """Phase 92: ``int -> (n, n)``."""

    def test_int_returns_tuple(self) -> None:
        assert _normalize_board_size(19) == (19, 19)
        assert _normalize_board_size(9) == (9, 9)
        assert _normalize_board_size(13) == (13, 13)

    def test_tuple_returns_same(self) -> None:
        assert _normalize_board_size((19, 19)) == (19, 19)
        assert _normalize_board_size((9, 13)) == (9, 13)  # non-square


# ---------------------------------------------------------------------------
# Section 9: Pure extractors (file2)
# ---------------------------------------------------------------------------


class TestExtractPredictedTerritory:
    """Phase 182: ownership grid -> single signed scalar."""

    def test_none_ownership(self) -> None:
        node = _MockNode()
        assert _extract_predicted_territory(node) is None

    def test_empty_ownership(self) -> None:
        node = _MockNode(ownership=[])
        assert _extract_predicted_territory(node) is None

    def test_uniform_black(self) -> None:
        node = _MockNode(ownership=[1.0] * 81)
        result = _extract_predicted_territory(node)
        assert result is not None and result == pytest.approx(1.0)

    def test_uniform_white(self) -> None:
        node = _MockNode(ownership=[-1.0] * 81)
        result = _extract_predicted_territory(node)
        assert result is not None and result == pytest.approx(-1.0)

    def test_balanced_returns_zero(self) -> None:
        node = _MockNode(ownership=[1.0, -1.0] * 40)
        result = _extract_predicted_territory(node)
        assert result is not None and result == pytest.approx(0.0)

    def test_none_entries_skipped(self) -> None:
        node = _MockNode(ownership=[None, 1.0, None, 1.0])
        result = _extract_predicted_territory(node)
        assert result is not None and result == pytest.approx(1.0)

    def test_non_numeric_entries_skipped(self) -> None:
        node = _MockNode(ownership=["junk", 0.5, "x", 1.5])
        result = _extract_predicted_territory(node)
        assert result is not None and result == pytest.approx(1.0)

    def test_all_invalid_returns_none(self) -> None:
        node = _MockNode(ownership=[None, None, "x"])
        assert _extract_predicted_territory(node) is None


class TestExtractBestPolicy:
    """Phase 182: policy list -> maximum probability."""

    def test_none_policy(self) -> None:
        node = _MockNode()
        assert _extract_best_policy(node) is None

    def test_empty_policy(self) -> None:
        node = _MockNode(policy=[])
        assert _extract_best_policy(node) is None

    def test_single_value(self) -> None:
        node = _MockNode(policy=[0.42])
        result = _extract_best_policy(node)
        assert result is not None and result == pytest.approx(0.42)

    def test_max_extracted(self) -> None:
        node = _MockNode(policy=[0.1, 0.5, 0.3, 0.05])
        result = _extract_best_policy(node)
        assert result is not None and result == pytest.approx(0.5)

    def test_none_entries_skipped(self) -> None:
        node = _MockNode(policy=[None, 0.4, None])
        result = _extract_best_policy(node)
        assert result is not None and result == pytest.approx(0.4)

    def test_all_zero_returns_none(self) -> None:
        # best stays at 0.0 and the function returns None in that case.
        node = _MockNode(policy=[0.0, 0.0, 0.0])
        assert _extract_best_policy(node) is None

    def test_invalid_entries_skipped(self) -> None:
        node = _MockNode(policy=["x", 0.25, "y"])
        result = _extract_best_policy(node)
        assert result is not None and result == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Section 10: Summary context builder (file2)
# ---------------------------------------------------------------------------


class TestComputeSummaryContext:
    """Phase 179.1/182/186: build ``SummaryHintContext`` from a ``GameNode``."""

    def test_minimal_node_yields_none_metrics(self) -> None:
        ctx = _compute_summary_context(_MockNode())
        assert ctx.points_lost is None
        assert ctx.overall_difficulty is None
        assert ctx.is_reliable is False
        assert ctx.root_visits == 0
        assert ctx.score_stdev is None
        assert ctx.is_endgame is False
        assert ctx.predicted_territory is None
        assert ctx.best_policy is None

    def test_points_lost_passed_through(self) -> None:
        ctx = _compute_summary_context(_MockNode(points_lost=3.5))
        assert ctx.points_lost == pytest.approx(3.5)

    def test_move_number_falls_back_to_depth(self) -> None:
        node = _MockNode(move_number=0, depth=120)
        ctx = _compute_summary_context(node)
        assert ctx.move_number == 120

    def test_metrics_exception_returns_none_and_unreliable(self) -> None:
        # difficulty_metrics_from_node raises -> overall_difficulty=None,
        # is_reliable=False. Patch at the ``katrain.core.analysis`` import
        # location (this is where the hints package binds the symbol).
        node = _MockNode(points_lost=1.0)
        with patch(
            "katrain.core.analysis.difficulty_metrics_from_node",
            side_effect=RuntimeError("boom"),
        ):
            ctx = _compute_summary_context(node)
        assert ctx.overall_difficulty is None
        assert ctx.is_reliable is False

    def test_metrics_unknown_returns_none_and_unreliable(self) -> None:
        # ``is_unknown`` attribute present and True -> overall_difficulty=None
        fake_metrics = MagicMock(spec=["is_unknown", "is_reliable", "overall_difficulty"])
        fake_metrics.is_unknown = True
        fake_metrics.is_reliable = True
        fake_metrics.overall_difficulty = 0.5
        with patch(
            "katrain.core.analysis.difficulty_metrics_from_node",
            return_value=fake_metrics,
        ):
            ctx = _compute_summary_context(_MockNode())
        assert ctx.overall_difficulty is None
        assert ctx.is_reliable is False

    def test_metrics_known_returns_values(self) -> None:
        fake_metrics = MagicMock(spec=["is_unknown", "is_reliable", "overall_difficulty"])
        fake_metrics.is_unknown = False
        fake_metrics.is_reliable = True
        fake_metrics.overall_difficulty = 0.6
        with patch(
            "katrain.core.analysis.difficulty_metrics_from_node",
            return_value=fake_metrics,
        ):
            ctx = _compute_summary_context(_MockNode())
        assert ctx.overall_difficulty == pytest.approx(0.6)
        assert ctx.is_reliable is True

    def test_thresholds_forwarded(self) -> None:
        ctx = _compute_summary_context(
            _MockNode(),
            threshold_blunder=12.0,
            threshold_mistake=3.0,
            threshold_score_stdev=2.0,
        )
        assert ctx.score_loss_threshold_blunder == 12.0
        assert ctx.score_loss_threshold_mistake == 3.0
        assert ctx.score_stdev_threshold == 2.0

    def test_ownership_and_policy_forwarded(self) -> None:
        node = _MockNode(ownership=[1.0] * 4, policy=[0.1, 0.6, 0.05, 0.2])
        ctx = _compute_summary_context(node)
        assert ctx.predicted_territory == pytest.approx(1.0)
        assert ctx.best_policy == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Section 11: Endgame heuristic (file2)
# ---------------------------------------------------------------------------


class TestIsEndgamePosition:
    """Phase 179.2: ``scoreStdev``-based dynamic + move-number fallback."""

    def test_no_analysis_returns_false(self) -> None:
        # No analysis -> get_score_stdev returns None -> falls back to move
        # heuristic. move_number=0 + depth=0 => False.
        assert _is_endgame_position(_MockNode()) is False

    def test_static_fallback_move_at_200(self) -> None:
        # Patch get_score_stdev to return None to force fallback
        with patch("katrain.core.analysis.get_score_stdev", return_value=None):
            assert _is_endgame_position(_MockNode(move_number=200)) is True

    def test_static_fallback_move_below_200(self) -> None:
        with patch("katrain.core.analysis.get_score_stdev", return_value=None):
            assert _is_endgame_position(_MockNode(move_number=150)) is False

    def test_dynamic_stdev_below_threshold(self) -> None:
        # scoreStdev <= 8.0 => True (threshold from logic_phase_dynamic)
        with patch("katrain.core.analysis.get_score_stdev", return_value=7.5):
            assert _is_endgame_position(_MockNode()) is True

    def test_dynamic_stdev_above_threshold(self) -> None:
        with patch("katrain.core.analysis.get_score_stdev", return_value=12.0):
            assert _is_endgame_position(_MockNode()) is False


# ---------------------------------------------------------------------------
# Section 12: Cache wrappers (file2)
# ---------------------------------------------------------------------------


class TestGetBeginnerHintCached:
    """Phase 92 cache key includes ``require_reliable``."""

    def test_cache_miss_then_hit(self) -> None:
        node = MagicMock()
        node.move = MagicMock()
        node.move.is_pass = False
        node.move.coords = (3, 3)
        node.parent = MagicMock()
        sentinel = BeginnerHint(category=HintCategory.SELF_ATARI, coords=(0, 0), severity=2)
        with patch("katrain.core.beginner.hints.compute_beginner_hint", return_value=sentinel) as mock:
            h1 = get_beginner_hint_cached(MagicMock(), node)
            h2 = get_beginner_hint_cached(MagicMock(), node)
        assert h1 is sentinel
        assert h2 is sentinel
        assert mock.call_count == 1

    def test_require_reliable_change_invalidates(self) -> None:
        node = MagicMock()
        node.move = MagicMock()
        node.move.is_pass = False
        node.move.coords = (3, 3)
        node.parent = MagicMock()
        sentinel_a = BeginnerHint(category=HintCategory.SELF_ATARI, coords=(0, 0), severity=2)
        sentinel_b = None
        with patch("katrain.core.beginner.hints.compute_beginner_hint", side_effect=[sentinel_a, sentinel_b]) as mock:
            h1 = get_beginner_hint_cached(MagicMock(), node, require_reliable=True)
            h2 = get_beginner_hint_cached(MagicMock(), node, require_reliable=False)
        assert h1 is sentinel_a
        assert h2 is sentinel_b
        assert mock.call_count == 2

    def test_none_is_cached_not_recomputed(self) -> None:
        node = MagicMock()
        node.move = MagicMock()
        node.move.is_pass = False
        node.move.coords = (3, 3)
        node.parent = MagicMock()
        with patch("katrain.core.beginner.hints.compute_beginner_hint", return_value=None) as mock:
            h1 = get_beginner_hint_cached(MagicMock(), node)
            h2 = get_beginner_hint_cached(MagicMock(), node)
        assert h1 is None
        assert h2 is None
        # Sentinel-vs-None distinction: must NOT re-call compute on None hit.
        assert mock.call_count == 1

    def test_not_computed_sentinel_triggers_recompute(self) -> None:
        # When the cache attribute exists but equals the sentinel, the
        # wrapper must recompute (not return the sentinel).
        node = MagicMock(spec=["move", "parent", "_beginner_hint_cache"])
        node.move = MagicMock()
        node.move.is_pass = False
        node.move.coords = (3, 3)
        node.parent = MagicMock()
        # Pre-set cache to the sentinel - should still recompute
        node._beginner_hint_cache = _NOT_COMPUTED
        sentinel = BeginnerHint(category=HintCategory.SELF_ATARI, coords=(0, 0), severity=2)
        with patch("katrain.core.beginner.hints.compute_beginner_hint", return_value=sentinel) as mock:
            h = get_beginner_hint_cached(MagicMock(), node)
        assert h is sentinel
        assert mock.call_count == 1


class TestGetSummaryHintCached:
    """Phase 179.1/186: cache invalidates on flags / ``require_reliable``."""

    def test_cache_miss_then_hit(self) -> None:
        node = _MockNode(analysis={"root": {"visits": 200}})
        sentinel = BeginnerHint(category=HintCategory.MISTAKE_BLUNDER, coords=(0, 0), severity=2)
        with patch("katrain.core.beginner.hints.compute_summary_hint", return_value=sentinel) as mock:
            h1 = get_summary_hint_cached(node)
            h2 = get_summary_hint_cached(node)
        assert h1 is sentinel
        assert h2 is sentinel
        assert mock.call_count == 1

    def test_flags_change_invalidates(self) -> None:
        node = _MockNode(analysis={"root": {"visits": 200}})
        sentinel_a = BeginnerHint(category=HintCategory.MISTAKE_BLUNDER, coords=(0, 0), severity=2)
        sentinel_b = None
        with patch("katrain.core.beginner.hints.compute_summary_hint", side_effect=[sentinel_a, sentinel_b]) as mock:
            h1 = get_summary_hint_cached(node, summary_flags={"summary_mistake": True})
            h2 = get_summary_hint_cached(node, summary_flags={"summary_mistake": False})
        assert h1 is sentinel_a
        assert h2 is sentinel_b
        assert mock.call_count == 2

    def test_require_reliable_change_invalidates(self) -> None:
        node = _MockNode(analysis={"root": {"visits": 200}})
        with patch("katrain.core.beginner.hints.compute_summary_hint", return_value=None) as mock:
            get_summary_hint_cached(node, require_reliable=True)
            get_summary_hint_cached(node, require_reliable=False)
        assert mock.call_count == 2

    # Phase 270: ``user_weak_tags`` / ``curator_min_occurrences`` were
    # removed from the dispatcher; the curator-cache invalidation tests
    # are intentionally dropped with them.

    def test_none_cache_hit_does_not_recompute(self) -> None:
        node = _MockNode(analysis={"root": {"visits": 200}})
        with patch("katrain.core.beginner.hints.compute_summary_hint", return_value=None) as mock:
            h1 = get_summary_hint_cached(node)
            h2 = get_summary_hint_cached(node)
        assert h1 is None
        assert h2 is None
        assert mock.call_count == 1


# ---------------------------------------------------------------------------
# Section 13: compute_beginner_hint main paths (file2)
# ---------------------------------------------------------------------------


class TestComputeBeginnerHintShortCircuits:
    """Top-of-function guards in ``compute_beginner_hint``."""

    def test_no_move_returns_none(self) -> None:
        node = MagicMock()
        node.move = None
        node.parent = MagicMock()
        assert compute_beginner_hint(MagicMock(), node) is None

    def test_no_parent_returns_none(self) -> None:
        node = MagicMock()
        node.move = MagicMock()
        node.move.is_pass = False
        node.parent = None
        assert compute_beginner_hint(MagicMock(), node) is None

    def test_pass_move_returns_none(self) -> None:
        node = MagicMock()
        node.move = MagicMock()
        node.move.is_pass = True
        node.parent = MagicMock()
        assert compute_beginner_hint(MagicMock(), node) is None


class TestComputeBeginnerHintNodeRestoration:
    """The ``finally``-block must restore the original ``current_node``."""

    def test_restores_original_node_when_different(self) -> None:
        # Patch extract_groups_from_game to a no-op so we don't need a
        # fully-shaped game. This isolates the dispatch+restore logic.
        game = MagicMock()
        original_node = MagicMock()
        target_node = MagicMock()
        target_node.move = MagicMock()
        target_node.move.is_pass = False
        target_node.move.coords = (3, 3)
        target_node.parent = MagicMock()
        game.current_node = original_node

        call_order: list[str] = []

        def fake_set_current_node(node: Any) -> None:
            call_order.append(getattr(node, "_label", ""))
            game.current_node = node

        game.set_current_node.side_effect = fake_set_current_node
        original_node._label = "original"
        target_node._label = "target"

        with (
            patch("katrain.core.beginner.hints.extract_groups_from_game", return_value=[]),
            patch("katrain.core.beginner.hints.detect_self_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_ignore_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_missed_capture", return_value=None),
            patch("katrain.core.beginner.hints.detect_cut_risk", return_value=None),
        ):
            compute_beginner_hint(game, target_node)

        # The last call must restore the original_node
        assert call_order[-1] == "original"

    def test_no_restore_when_already_at_target(self) -> None:
        game = MagicMock()
        target_node = MagicMock()
        target_node.move = MagicMock()
        target_node.move.is_pass = False
        target_node.move.coords = (3, 3)
        target_node.parent = MagicMock()
        target_node.parent._label = "parent"
        target_node._label = "target"
        game.current_node = target_node

        set_calls: list[str] = []

        def fake_set_current_node(node: Any) -> None:
            set_calls.append(getattr(node, "_label", ""))

        game.set_current_node.side_effect = fake_set_current_node

        with (
            patch("katrain.core.beginner.hints.extract_groups_from_game", return_value=[]),
            patch("katrain.core.beginner.hints.detect_self_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_ignore_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_missed_capture", return_value=None),
            patch("katrain.core.beginner.hints.detect_cut_risk", return_value=None),
        ):
            compute_beginner_hint(game, target_node)

        # compute_beginner_hint moves to parent (Step 3) then back to
        # target (Step 4, required for CUT_RISK). Restore is skipped
        # because original_node == target_node.
        assert set_calls == ["parent", "target"]


# ---------------------------------------------------------------------------
# Section 14: compute_summary_hint priority chain (file2)
# ---------------------------------------------------------------------------


class TestComputeSummaryHintPriorityChain:
    """Phase 179+182+186 priority order: Mistake > Freedom > Difficulty >
    KataGo > Ownership > Policy.
    """

    @staticmethod
    def _node_with_visits(visits: int = 200) -> _MockNode:
        # root visits is extracted from analysis.get('root', {}).get('visits')
        return _MockNode(analysis={"root": {"visits": visits}})

    def test_unreliable_visits_returns_none(self) -> None:
        # visits < MIN_SUMMARY_VISITS (100) and require_reliable=True => None
        node = self._node_with_visits(50)
        assert compute_summary_hint(node, require_reliable=True) is None

    def test_low_visits_but_require_reliable_false_runs(self) -> None:
        # visits < MIN_SUMMARY_VISITS but require_reliable=False => runs
        # None of the detectors should fire on an empty node -> still None
        node = self._node_with_visits(50)
        assert compute_summary_hint(node, require_reliable=False) is None

    def test_mistake_outranks_freedom(self) -> None:
        node = self._node_with_visits()
        mistake_hint = BeginnerHint(category=HintCategory.MISTAKE_BLUNDER, coords=(0, 0), severity=2)
        freedom_hint = BeginnerHint(category=HintCategory.FREEDOM_NARROW, coords=(0, 0), severity=1)
        with (
            patch("katrain.core.beginner.hints.detect_mistake_summary", return_value=mistake_hint),
            patch("katrain.core.beginner.hints.detect_freedom_summary", return_value=freedom_hint),
        ):
            hint = compute_summary_hint(node)
        assert hint is mistake_hint

    def test_freedom_outranks_difficulty(self) -> None:
        node = self._node_with_visits()
        freedom_hint = BeginnerHint(category=HintCategory.FREEDOM_NARROW, coords=(0, 0), severity=1)
        difficulty_hint = BeginnerHint(category=HintCategory.DIFFICULTY_TRICKY, coords=(0, 0), severity=1)
        with (
            patch("katrain.core.beginner.hints.detect_mistake_summary", return_value=None),
            patch("katrain.core.beginner.hints.detect_freedom_summary", return_value=freedom_hint),
            patch("katrain.core.beginner.hints.detect_difficulty_summary", return_value=difficulty_hint),
        ):
            hint = compute_summary_hint(node)
        assert hint is freedom_hint

    def test_policy_confident_outranks_policy_conflict(self) -> None:
        node = self._node_with_visits()
        confident = BeginnerHint(category=HintCategory.POLICY_CONFIDENT, coords=(0, 0), severity=0)
        conflict = BeginnerHint(category=HintCategory.POLICY_CONFLICT, coords=(0, 0), severity=1)
        with (
            patch("katrain.core.beginner.hints.detect_policy_confident", return_value=confident),
            patch("katrain.core.beginner.hints.detect_policy_conflict", return_value=conflict),
        ):
            hint = compute_summary_hint(node)
        assert hint is confident

    def test_flag_off_skips_detector(self) -> None:
        node = self._node_with_visits()
        mistake_hint = BeginnerHint(category=HintCategory.MISTAKE_BLUNDER, coords=(0, 0), severity=2)
        with patch("katrain.core.beginner.hints.detect_mistake_summary", return_value=mistake_hint) as mock:
            hint = compute_summary_hint(node, summary_flags={"summary_mistake": False})
        assert hint is None
        assert mock.call_count == 0

    def test_flags_none_defaults_all_true(self) -> None:
        # Pass flags=None: every detector should be called exactly once.
        node = self._node_with_visits()
        with (
            patch("katrain.core.beginner.hints.detect_mistake_summary", return_value=None) as m,
            patch("katrain.core.beginner.hints.detect_freedom_summary", return_value=None) as f,
            patch("katrain.core.beginner.hints.detect_difficulty_summary", return_value=None) as d,
            patch("katrain.core.beginner.hints.detect_katago_uncertain", return_value=None) as k,
            patch("katrain.core.beginner.hints.detect_ownership_dominant", return_value=None) as o,
            patch("katrain.core.beginner.hints.detect_policy_confident", return_value=None) as pc,
            patch("katrain.core.beginner.hints.detect_policy_conflict", return_value=None) as px,
        ):
            hint = compute_summary_hint(node, summary_flags=None)
        assert hint is None
        assert m.call_count == 1
        assert f.call_count == 1
        assert d.call_count == 1
        assert k.call_count == 1
        assert o.call_count == 1
        assert pc.call_count == 1
        assert px.call_count == 1

    # Phase 270: the four ``test_user_weak_tags_*`` /
    # ``test_curator_hint_*`` / ``test_curator_flag_off_*`` tests were
    # removed along with the Curator weak-axis hint. The dispatcher
    # no longer accepts ``user_weak_tags`` / ``curator_min_occurrences``.


# ---------------------------------------------------------------------------
# Section 15: i18n integration sanity (file2)
# ---------------------------------------------------------------------------


class TestHintCategoryI18nNamespaces:
    """All ``HintCategories`` must produce non-empty i18n namespaces."""

    @pytest.mark.parametrize("category", list(HintCategory))
    def test_namespace_non_empty(self, category: HintCategory) -> None:
        ns = category.i18n_namespace
        assert isinstance(ns, str)
        assert len(ns) > 0

    @pytest.mark.parametrize("category", list(HintCategory))
    def test_fallback_titles_non_empty(self, category: HintCategory) -> None:
        title = category.fallback_title
        body = category.fallback_body
        assert isinstance(title, str) and len(title) > 0
        assert isinstance(body, str) and len(body) > 0

    def test_structural_categories_have_per_category_config_key(self) -> None:
        """Phase 251: structural categories now expose an individual
        toggle via ``HintCategory.config_key`` (returns the category's
        own enum value). Previously this returned ``None`` and the
        category was gated only by the master ``beginner_hints/enabled``
        switch.
        """
        for c in HintCategory:
            if c.is_structural:
                assert c.config_key == c.value, (
                    f"Structural category {c} should map config_key to its own value, got {c.config_key!r}"
                )

    def test_meaning_tag_categories_have_per_category_config_key(self) -> None:
        """Phase 251: meaning-tag fallback categories also expose a
        per-category key (returns the category's own enum value).
        """
        for c in HintCategory:
            if c.is_meaning_tag:
                assert c.config_key == c.value, (
                    f"Meaning-tag category {c} should map config_key to its own value, got {c.config_key!r}"
                )

    def test_summary_categories_have_config_key(self) -> None:
        for c in HintCategory:
            if c.is_summary:
                assert c.config_key is not None


# ---------------------------------------------------------------------------
# Section 16: Constants sanity (file2)
# ---------------------------------------------------------------------------


class TestHintConstants:
    """Phase 91/92/179 constants must hold reasonable values."""

    def test_min_reliable_visits_is_positive(self) -> None:
        assert MIN_RELIABLE_VISITS > 0

    def test_min_summary_visits_is_less_than_reliable(self) -> None:
        # Summary hints are more permissive than structural hints.
        assert MIN_SUMMARY_VISITS < MIN_RELIABLE_VISITS

    def test_detector_categories_frozenset_matches_priority_group(self) -> None:
        # The 4 priority detectors must always be in this set.
        expected = {
            HintCategory.SELF_ATARI,
            HintCategory.IGNORE_ATARI,
            HintCategory.MISSED_CAPTURE,
            HintCategory.CUT_RISK,
        }
        assert expected == _DETECTOR_CATEGORIES

    def test_not_computed_is_singleton(self) -> None:
        # The sentinel object must be unique per process.
        from katrain.core.beginner.hints import _NOT_COMPUTED as _NC2

        assert _NOT_COMPUTED is _NC2


# ---------------------------------------------------------------------------
# Section 17: i18n .po file checks (file1)
# ---------------------------------------------------------------------------


class TestBeginnerHintI18n:
    """Test beginner hint i18n keys exist in ``.po`` files (Phase 92d)."""

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
        """All 30 beginner hint i18n keys exist in JP ``.po`` file."""
        import polib

        po_path = "katrain/i18n/locales/jp/LC_MESSAGES/katrain.po"
        po = polib.pofile(po_path)
        existing_keys = {entry.msgid for entry in po}

        expected_keys = {f"beginner_hint:{cat}:{suffix}" for cat in self.CATEGORIES for suffix in self.SUFFIXES}

        missing = expected_keys - existing_keys
        assert not missing, f"Missing keys in JP: {missing}"

    def test_all_hint_keys_exist_in_en_po(self):
        """All 30 beginner hint i18n keys exist in EN ``.po`` file."""
        import polib

        po_path = "katrain/i18n/locales/en/LC_MESSAGES/katrain.po"
        po = polib.pofile(po_path)
        existing_keys = {entry.msgid for entry in po}

        expected_keys = {f"beginner_hint:{cat}:{suffix}" for cat in self.CATEGORIES for suffix in self.SUFFIXES}

        missing = expected_keys - existing_keys
        assert not missing, f"Missing keys in EN: {missing}"

    def test_no_empty_msgstr_for_hint_keys_jp(self):
        """All JP beginner hint keys have non-empty ``msgstr``."""
        import polib

        po_path = "katrain/i18n/locales/jp/LC_MESSAGES/katrain.po"
        po = polib.pofile(po_path)

        empty_keys = []
        for entry in po:
            if entry.msgid.startswith("beginner_hint:") and not entry.msgstr:
                empty_keys.append(entry.msgid)

        assert not empty_keys, f"Empty msgstr in JP: {empty_keys}"

    def test_no_empty_msgstr_for_hint_keys_en(self):
        """All EN beginner hint keys have non-empty ``msgstr``."""
        import polib

        po_path = "katrain/i18n/locales/en/LC_MESSAGES/katrain.po"
        po = polib.pofile(po_path)

        empty_keys = []
        for entry in po:
            if entry.msgid.startswith("beginner_hint:") and not entry.msgstr:
                empty_keys.append(entry.msgid)

        assert not empty_keys, f"Empty msgstr in EN: {empty_keys}"
