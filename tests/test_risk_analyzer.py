"""Tests for Risk Context Analyzer.

Part of Phase 61: Risk Context Core.

Test coverage:
- TestToPlayerPerspective: Perspective conversion
- TestDetermineJudgment: Game situation judgment with boundary tests
- TestDetermineBehaviorFromStdev: Stdev-based behavior with boundary tests
- TestDetermineBehaviorFromVolatility: Volatility-based behavior
- TestStrategyMismatch: Mismatch detection (all combinations)
- TestVolatilityWindow: Window value extraction
- TestComputeVolatility: Standard deviation calculation
- TestNodeDataExtraction: Hardened dict access
- TestAnalyzeRisk: Integration tests
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pytest

from katrain.core.analysis.risk import (
    PlayerRiskStats,
    RiskAnalysisConfig,
    RiskAnalysisResult,
    RiskBehavior,
    RiskContext,
    RiskJudgmentType,
    analyze_risk,
    check_strategy_mismatch,
    determine_behavior_from_stdev,
    determine_behavior_from_volatility,
    determine_judgment,
    to_player_perspective,
)
from katrain.core.analysis.risk.analyzer import (
    _compute_volatility,
    _get_player_from_node,
    _get_score_lead_from_node,
    _get_score_stdev_from_node,
    _get_volatility_window_values,
    _get_winrate_from_node,
)

# =============================================================================
# Mock Classes
# =============================================================================


@dataclass
class MockMove:
    """Mock Move object for testing."""

    player: str
    coords: tuple | None = None

    @property
    def is_pass(self) -> bool:
        return self.coords is None


@dataclass
class MockNode:
    """Mock GameNode for testing."""

    analysis_exists: bool = False
    analysis: dict[str, Any] | None = None
    move: MockMove | None = None
    parent: MockNode | None = None


def make_node_with_analysis(
    winrate: float | None = None,
    score_lead: float | None = None,
    score_stdev: float | None = None,
    player: str = "B",
    parent: MockNode | None = None,
) -> MockNode:
    """Create a MockNode with specified analysis values."""
    root_info: dict[str, Any] = {}
    if winrate is not None:
        root_info["winrate"] = winrate
    if score_lead is not None:
        root_info["scoreLead"] = score_lead
    if score_stdev is not None:
        root_info["scoreStdev"] = score_stdev

    analysis = {"root": root_info} if root_info else None
    analysis_exists = analysis is not None

    return MockNode(
        analysis_exists=analysis_exists,
        analysis=analysis,
        move=MockMove(player=player),
        parent=parent,
    )


# =============================================================================
# Test: Perspective Conversion
# =============================================================================


class TestToPlayerPerspective:
    """Test to_player_perspective function."""

    def test_black_player_no_conversion(self):
        """Black player: values unchanged."""
        wr, score = to_player_perspective(0.90, 15.0, "B")
        assert wr == 0.90
        assert score == 15.0

    def test_white_player_inverts_values(self):
        """White player: winrate and score inverted."""
        wr, score = to_player_perspective(0.90, 15.0, "W")
        assert wr == pytest.approx(0.10)
        assert score == pytest.approx(-15.0)

    def test_black_perspective_losing_to_white_winning(self):
        """Black losing (WR=0.10, Score=-15) → White winning."""
        wr, score = to_player_perspective(0.10, -15.0, "W")
        assert wr == pytest.approx(0.90)
        assert score == pytest.approx(15.0)

    def test_fifty_fifty_unchanged(self):
        """50-50 game stays 50-50 for both players."""
        wr_b, score_b = to_player_perspective(0.50, 0.0, "B")
        wr_w, score_w = to_player_perspective(0.50, 0.0, "W")
        assert wr_b == 0.50
        assert score_b == 0.0
        assert wr_w == 0.50
        assert score_w == 0.0


# =============================================================================
# Test: Game Situation Judgment
# =============================================================================


class TestDetermineJudgment:
    """Test determine_judgment function with boundary cases."""

    @pytest.fixture
    def config(self):
        return RiskAnalysisConfig()

    def test_winning_exact_boundary(self, config):
        """WR=0.85, Score=10.0 → WINNING (boundary exact)."""
        result = determine_judgment(0.85, 10.0, config)
        assert result == RiskJudgmentType.WINNING

    def test_winning_above_boundary(self, config):
        """WR=0.90, Score=15.0 → WINNING."""
        result = determine_judgment(0.90, 15.0, config)
        assert result == RiskJudgmentType.WINNING

    def test_close_wr_just_below_winning(self, config):
        """WR=0.8499, Score=10.0 → CLOSE (WR insufficient)."""
        result = determine_judgment(0.8499, 10.0, config)
        assert result == RiskJudgmentType.CLOSE

    def test_close_score_just_below_winning(self, config):
        """WR=0.85, Score=9.99 → CLOSE (Score insufficient)."""
        result = determine_judgment(0.85, 9.99, config)
        assert result == RiskJudgmentType.CLOSE

    def test_losing_exact_boundary(self, config):
        """WR=0.15, Score=-10.0 → LOSING (boundary exact)."""
        result = determine_judgment(0.15, -10.0, config)
        assert result == RiskJudgmentType.LOSING

    def test_losing_below_boundary(self, config):
        """WR=0.10, Score=-15.0 → LOSING."""
        result = determine_judgment(0.10, -15.0, config)
        assert result == RiskJudgmentType.LOSING

    def test_close_wr_just_above_losing(self, config):
        """WR=0.1501, Score=-10.0 → CLOSE (WR insufficient)."""
        result = determine_judgment(0.1501, -10.0, config)
        assert result == RiskJudgmentType.CLOSE

    def test_close_score_just_above_losing(self, config):
        """WR=0.15, Score=-9.99 → CLOSE (Score insufficient)."""
        result = determine_judgment(0.15, -9.99, config)
        assert result == RiskJudgmentType.CLOSE

    def test_close_middle_range(self, config):
        """WR=0.50, Score=0.0 → CLOSE."""
        result = determine_judgment(0.50, 0.0, config)
        assert result == RiskJudgmentType.CLOSE

    def test_close_high_wr_low_score(self, config):
        """WR=0.90 but Score=5.0 → CLOSE (Score insufficient)."""
        result = determine_judgment(0.90, 5.0, config)
        assert result == RiskJudgmentType.CLOSE

    def test_close_low_wr_not_low_enough_score(self, config):
        """WR=0.15 but Score=-5.0 → CLOSE (Score insufficient)."""
        result = determine_judgment(0.15, -5.0, config)
        assert result == RiskJudgmentType.CLOSE


# =============================================================================
# Test: Behavior from Stdev
# =============================================================================


class TestDetermineBehaviorFromStdev:
    """Test determine_behavior_from_stdev with boundary cases."""

    @pytest.fixture
    def config(self):
        return RiskAnalysisConfig()

    def test_complicating_exact_boundary(self, config):
        """delta=1.0 → COMPLICATING (boundary exact, >=)."""
        result = determine_behavior_from_stdev(1.0, config)
        assert result == RiskBehavior.COMPLICATING

    def test_complicating_above_boundary(self, config):
        """delta=2.0 → COMPLICATING."""
        result = determine_behavior_from_stdev(2.0, config)
        assert result == RiskBehavior.COMPLICATING

    def test_neutral_just_below_complicating(self, config):
        """delta=0.99 → NEUTRAL."""
        result = determine_behavior_from_stdev(0.99, config)
        assert result == RiskBehavior.NEUTRAL

    def test_solid_exact_boundary(self, config):
        """delta=-0.5 → SOLID (boundary exact, <=)."""
        result = determine_behavior_from_stdev(-0.5, config)
        assert result == RiskBehavior.SOLID

    def test_solid_below_boundary(self, config):
        """delta=-1.0 → SOLID."""
        result = determine_behavior_from_stdev(-1.0, config)
        assert result == RiskBehavior.SOLID

    def test_neutral_just_above_solid(self, config):
        """delta=-0.49 → NEUTRAL."""
        result = determine_behavior_from_stdev(-0.49, config)
        assert result == RiskBehavior.NEUTRAL

    def test_neutral_zero(self, config):
        """delta=0.0 → NEUTRAL."""
        result = determine_behavior_from_stdev(0.0, config)
        assert result == RiskBehavior.NEUTRAL


# =============================================================================
# Test: Behavior from Volatility
# =============================================================================


class TestDetermineBehaviorFromVolatility:
    """Test determine_behavior_from_volatility with boundary cases."""

    @pytest.fixture
    def config(self):
        return RiskAnalysisConfig()

    def test_complicating_exact_boundary(self, config):
        """volatility=5.0 → COMPLICATING (boundary exact, >=)."""
        result = determine_behavior_from_volatility(5.0, config)
        assert result == RiskBehavior.COMPLICATING

    def test_complicating_above_boundary(self, config):
        """volatility=10.0 → COMPLICATING."""
        result = determine_behavior_from_volatility(10.0, config)
        assert result == RiskBehavior.COMPLICATING

    def test_neutral_just_below_complicating(self, config):
        """volatility=4.99 → NEUTRAL."""
        result = determine_behavior_from_volatility(4.99, config)
        assert result == RiskBehavior.NEUTRAL

    def test_solid_exact_boundary(self, config):
        """volatility=2.0 → SOLID (boundary exact, <=)."""
        result = determine_behavior_from_volatility(2.0, config)
        assert result == RiskBehavior.SOLID

    def test_solid_below_boundary(self, config):
        """volatility=1.0 → SOLID."""
        result = determine_behavior_from_volatility(1.0, config)
        assert result == RiskBehavior.SOLID

    def test_neutral_just_above_solid(self, config):
        """volatility=2.01 → NEUTRAL."""
        result = determine_behavior_from_volatility(2.01, config)
        assert result == RiskBehavior.NEUTRAL

    def test_neutral_none(self, config):
        """volatility=None → NEUTRAL."""
        result = determine_behavior_from_volatility(None, config)
        assert result == RiskBehavior.NEUTRAL


# =============================================================================
# Test: Strategy Mismatch
# =============================================================================


class TestStrategyMismatch:
    """Test check_strategy_mismatch for all combinations."""

    def test_winning_complicating_mismatch(self):
        """WINNING + COMPLICATING → mismatch."""
        is_mismatch, reason = check_strategy_mismatch(RiskJudgmentType.WINNING, RiskBehavior.COMPLICATING)
        assert is_mismatch is True
        assert reason == "unnecessary_risk_when_winning"

    def test_losing_solid_mismatch(self):
        """LOSING + SOLID → mismatch."""
        is_mismatch, reason = check_strategy_mismatch(RiskJudgmentType.LOSING, RiskBehavior.SOLID)
        assert is_mismatch is True
        assert reason == "passive_when_losing"

    def test_winning_solid_ok(self):
        """WINNING + SOLID → OK."""
        is_mismatch, reason = check_strategy_mismatch(RiskJudgmentType.WINNING, RiskBehavior.SOLID)
        assert is_mismatch is False
        assert reason is None

    def test_winning_neutral_ok(self):
        """WINNING + NEUTRAL → OK."""
        is_mismatch, reason = check_strategy_mismatch(RiskJudgmentType.WINNING, RiskBehavior.NEUTRAL)
        assert is_mismatch is False
        assert reason is None

    def test_losing_complicating_ok(self):
        """LOSING + COMPLICATING → OK."""
        is_mismatch, reason = check_strategy_mismatch(RiskJudgmentType.LOSING, RiskBehavior.COMPLICATING)
        assert is_mismatch is False
        assert reason is None

    def test_losing_neutral_ok(self):
        """LOSING + NEUTRAL → OK."""
        is_mismatch, reason = check_strategy_mismatch(RiskJudgmentType.LOSING, RiskBehavior.NEUTRAL)
        assert is_mismatch is False
        assert reason is None

    def test_close_solid_ok(self):
        """CLOSE + SOLID → OK."""
        is_mismatch, reason = check_strategy_mismatch(RiskJudgmentType.CLOSE, RiskBehavior.SOLID)
        assert is_mismatch is False
        assert reason is None

    def test_close_complicating_ok(self):
        """CLOSE + COMPLICATING → OK."""
        is_mismatch, reason = check_strategy_mismatch(RiskJudgmentType.CLOSE, RiskBehavior.COMPLICATING)
        assert is_mismatch is False
        assert reason is None

    def test_close_neutral_ok(self):
        """CLOSE + NEUTRAL → OK."""
        is_mismatch, reason = check_strategy_mismatch(RiskJudgmentType.CLOSE, RiskBehavior.NEUTRAL)
        assert is_mismatch is False
        assert reason is None


# =============================================================================
# Test: Volatility Window
# =============================================================================


class TestVolatilityWindow:
    """Test _get_volatility_window_values function."""

    def test_full_window(self):
        """Window fully available."""
        history = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        # Move 10: current_index=9, window=5 → indices [5,6,7,8,9]
        values = _get_volatility_window_values(history, 9, 5)
        assert values == [6.0, 7.0, 8.0, 9.0, 10.0]

    def test_partial_window_early_game(self):
        """Partial window at game start."""
        history = [1.0, 2.0, 3.0]
        # Move 3: current_index=2, window=5 → indices [0,1,2]
        values = _get_volatility_window_values(history, 2, 5)
        assert values == [1.0, 2.0, 3.0]

    def test_single_value(self):
        """Only one value available."""
        history = [1.0]
        values = _get_volatility_window_values(history, 0, 5)
        assert values == [1.0]

    def test_none_values_excluded(self):
        """None values are excluded."""
        history = [1.0, None, 3.0, None, 5.0]
        values = _get_volatility_window_values(history, 4, 5)
        assert values == [1.0, 3.0, 5.0]

    def test_all_none(self):
        """All None → empty list."""
        history = [None, None, None]
        values = _get_volatility_window_values(history, 2, 5)
        assert values == []

    def test_does_not_include_future_data(self):
        """Future data not included (key safety test)."""
        # Index 3 is "future" for move 3 (current_index=2)
        history = [1.0, 2.0, 3.0, 100.0]
        values = _get_volatility_window_values(history, 2, 5)
        assert values == [1.0, 2.0, 3.0]
        assert 100.0 not in values

    def test_move10_uses_correct_indices(self):
        """Move 10 uses indices [5,6,7,8,9] = Node(5)..Node(9)."""
        history = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 100.0]
        # Move 10: current_index=9, window=5
        values = _get_volatility_window_values(history, 9, 5)
        assert values == [5.0, 6.0, 7.0, 8.0, 9.0]
        assert 100.0 not in values  # index 10 is future


# =============================================================================
# Test: Compute Volatility
# =============================================================================


class TestComputeVolatility:
    """Test _compute_volatility function."""

    def test_returns_none_for_single_value(self):
        """Single value → None (insufficient samples)."""
        result = _compute_volatility([1.0])
        assert result is None

    def test_returns_none_for_empty(self):
        """Empty list → None."""
        result = _compute_volatility([])
        assert result is None

    def test_all_same_values_zero_volatility(self):
        """All same values → 0.0."""
        result = _compute_volatility([5.0, 5.0, 5.0, 5.0])
        assert result == pytest.approx(0.0)

    def test_known_values_population_stdev(self):
        """Known values: [1, 2, 3, 4, 5] → population stdev."""
        # Mean = 3, variance = (4+1+0+1+4)/5 = 2, stdev = sqrt(2) ≈ 1.414
        result = _compute_volatility([1.0, 2.0, 3.0, 4.0, 5.0])
        expected = math.sqrt(2.0)
        assert result == pytest.approx(expected)

    def test_two_values(self):
        """Two values: [0, 10] → stdev = 5."""
        # Mean = 5, variance = (25+25)/2 = 25, stdev = 5
        result = _compute_volatility([0.0, 10.0])
        assert result == pytest.approx(5.0)


# =============================================================================
# Test: Node Data Extraction (Hardened Dict Access)
# =============================================================================


class TestNodeDataExtraction:
    """Test hardened dict access functions."""

    def test_get_winrate_no_analysis_exists(self):
        """analysis_exists=False → None."""
        node = MockNode(analysis_exists=False)
        assert _get_winrate_from_node(node) is None

    def test_get_winrate_analysis_none(self):
        """analysis=None → None."""
        node = MockNode(analysis_exists=True, analysis=None)
        assert _get_winrate_from_node(node) is None

    def test_get_winrate_no_root_key(self):
        """analysis exists but no "root" key → None."""
        node = MockNode(analysis_exists=True, analysis={"other": {}})
        assert _get_winrate_from_node(node) is None

    def test_get_winrate_root_but_no_winrate(self):
        """analysis["root"] exists but no winrate → None."""
        node = MockNode(analysis_exists=True, analysis={"root": {"scoreLead": 5.0}})
        assert _get_winrate_from_node(node) is None

    def test_get_winrate_success(self):
        """Valid winrate → returns value."""
        node = MockNode(analysis_exists=True, analysis={"root": {"winrate": 0.75}})
        assert _get_winrate_from_node(node) == 0.75

    def test_get_score_lead_success(self):
        """Valid scoreLead → returns value."""
        node = MockNode(analysis_exists=True, analysis={"root": {"scoreLead": 10.5}})
        assert _get_score_lead_from_node(node) == 10.5

    def test_get_score_stdev_success(self):
        """Valid scoreStdev → returns value."""
        node = MockNode(analysis_exists=True, analysis={"root": {"scoreStdev": 3.2}})
        assert _get_score_stdev_from_node(node) == 3.2

    def test_get_player_valid_black(self):
        """Valid player "B" → returns "B"."""
        node = MockNode(move=MockMove(player="B"))
        assert _get_player_from_node(node) == "B"

    def test_get_player_valid_white(self):
        """Valid player "W" → returns "W"."""
        node = MockNode(move=MockMove(player="W"))
        assert _get_player_from_node(node) == "W"

    def test_get_player_no_move(self):
        """No move → None."""
        node = MockNode(move=None)
        assert _get_player_from_node(node) is None

    def test_get_player_invalid_raises(self):
        """Invalid player value → ValueError."""
        node = MockNode(move=MockMove(player="X"))
        with pytest.raises(ValueError, match="Unexpected player"):
            _get_player_from_node(node)


# =============================================================================
# Test: Integration - analyze_risk
# =============================================================================


class MockGame:
    """Mock Game for testing analyze_risk."""

    def __init__(self, root: MockNode):
        self.root = root


class TestAnalyzeRisk:
    """Integration tests for analyze_risk function."""

    def test_empty_game(self):
        """Game with only root → empty result."""
        root = MockNode(analysis_exists=True, analysis={"root": {"winrate": 0.5, "scoreLead": 0.0}})
        root.parent = None
        game = MockGame(root)

        result = analyze_risk(game)

        assert len(result.contexts) == 0
        assert result.strategy_mismatch_count == 0
        assert result.black_stats.total_contexts == 0
        assert result.white_stats.total_contexts == 0

    def test_single_move_with_stdev(self):
        """Single move with scoreStdev → uses stdev."""
        # Root node (parent=None)
        root = MockNode(
            analysis_exists=True,
            analysis={"root": {"winrate": 0.5, "scoreLead": 0.0, "scoreStdev": 10.0}},
            parent=None,
        )

        # Move 1: Black plays, post_stdev = 11.0 (delta = +1.0 → COMPLICATING)
        move1 = MockNode(
            analysis_exists=True,
            analysis={"root": {"winrate": 0.55, "scoreLead": 2.0, "scoreStdev": 11.0}},
            move=MockMove(player="B"),
            parent=root,
        )

        # Link for iteration
        root.children = [move1]

        # Build game with custom iteration
        game = MockGame(root)

        result = analyze_risk(game)

        assert len(result.contexts) == 1
        ctx = result.contexts[0]
        assert ctx.move_number == 1
        assert ctx.player == "B"
        assert ctx.has_stdev_data is True
        assert ctx.delta_stdev == pytest.approx(1.0)
        assert ctx.risk_behavior == RiskBehavior.COMPLICATING
        assert result.has_stdev_data is True
        assert result.fallback_used is False

    def test_single_move_with_fallback(self):
        """Single move without scoreStdev → uses volatility fallback."""
        # Root node (no stdev)
        root = MockNode(
            analysis_exists=True,
            analysis={"root": {"winrate": 0.5, "scoreLead": 0.0}},  # no scoreStdev
            parent=None,
        )

        # Move 1: Black plays (no stdev on post_node either)
        move1 = MockNode(
            analysis_exists=True,
            analysis={"root": {"winrate": 0.55, "scoreLead": 2.0}},  # no scoreStdev
            move=MockMove(player="B"),
            parent=root,
        )

        root.children = [move1]
        game = MockGame(root)

        result = analyze_risk(game)

        assert len(result.contexts) == 1
        ctx = result.contexts[0]
        assert ctx.has_stdev_data is False
        # With only 1 score value, volatility is None → NEUTRAL
        assert ctx.volatility_metric is None
        assert ctx.risk_behavior == RiskBehavior.NEUTRAL
        assert result.has_stdev_data is False
        assert result.fallback_used is True

    def test_skip_when_pre_node_no_analysis(self):
        """pre_node without analysis → skip (but score_history gets None)."""
        # Root node (no analysis)
        root = MockNode(
            analysis_exists=False,
            analysis=None,
            parent=None,
        )

        # Move 1: Black plays (has analysis)
        move1 = MockNode(
            analysis_exists=True,
            analysis={"root": {"winrate": 0.5, "scoreLead": 0.0, "scoreStdev": 10.0}},
            move=MockMove(player="B"),
            parent=root,
        )

        root.children = [move1]
        game = MockGame(root)

        result = analyze_risk(game)

        # Move 1 should be skipped (root has no analysis)
        assert len(result.contexts) == 0

    def test_strategy_mismatch_detection(self):
        """Detect strategy mismatch: WINNING + COMPLICATING."""
        # Root: Black winning (WR=0.90, Score=15.0)
        root = MockNode(
            analysis_exists=True,
            analysis={"root": {"winrate": 0.90, "scoreLead": 15.0, "scoreStdev": 5.0}},
            parent=None,
        )

        # Move 1: Black plays, increases stdev significantly (COMPLICATING)
        move1 = MockNode(
            analysis_exists=True,
            analysis={"root": {"winrate": 0.88, "scoreLead": 14.0, "scoreStdev": 8.0}},
            move=MockMove(player="B"),
            parent=root,
        )

        root.children = [move1]
        game = MockGame(root)

        result = analyze_risk(game)

        assert len(result.contexts) == 1
        ctx = result.contexts[0]
        assert ctx.judgment_type == RiskJudgmentType.WINNING
        assert ctx.delta_stdev == pytest.approx(3.0)
        assert ctx.risk_behavior == RiskBehavior.COMPLICATING
        assert ctx.is_strategy_mismatch is True
        assert ctx.mismatch_reason == "unnecessary_risk_when_winning"
        assert result.strategy_mismatch_count == 1

    def test_player_stats_separation(self):
        """Statistics correctly separated by player."""
        # Root
        root = MockNode(
            analysis_exists=True,
            analysis={"root": {"winrate": 0.5, "scoreLead": 0.0, "scoreStdev": 5.0}},
            parent=None,
        )

        # Move 1: Black
        move1 = MockNode(
            analysis_exists=True,
            analysis={"root": {"winrate": 0.55, "scoreLead": 2.0, "scoreStdev": 5.5}},
            move=MockMove(player="B"),
            parent=root,
        )

        # Move 2: White
        move2 = MockNode(
            analysis_exists=True,
            analysis={"root": {"winrate": 0.50, "scoreLead": 0.0, "scoreStdev": 5.0}},
            move=MockMove(player="W"),
            parent=move1,
        )

        # Move 3: Black
        move3 = MockNode(
            analysis_exists=True,
            analysis={"root": {"winrate": 0.60, "scoreLead": 3.0, "scoreStdev": 6.0}},
            move=MockMove(player="B"),
            parent=move2,
        )

        root.children = [move1]
        move1.children = [move2]
        move2.children = [move3]
        game = MockGame(root)

        result = analyze_risk(game)

        assert len(result.contexts) == 3
        assert result.black_stats.total_contexts == 2  # moves 1 and 3
        assert result.white_stats.total_contexts == 1  # move 2

    def test_to_dict_serialization(self):
        """RiskContext and RiskAnalysisResult to_dict work correctly."""
        ctx = RiskContext(
            move_number=1,
            player="B",
            judgment_type=RiskJudgmentType.CLOSE,
            winrate_before=0.5,
            score_lead_before=0.0,
            risk_behavior=RiskBehavior.NEUTRAL,
            delta_stdev=0.5,
            volatility_metric=None,
            is_strategy_mismatch=False,
            mismatch_reason=None,
            has_stdev_data=True,
        )

        ctx_dict = ctx.to_dict()
        assert ctx_dict["move_number"] == 1
        assert ctx_dict["player"] == "B"
        assert ctx_dict["judgment_type"] == "close"
        assert ctx_dict["risk_behavior"] == "neutral"
        assert ctx_dict["delta_stdev"] == 0.5
        assert ctx_dict["volatility_metric"] is None

    def test_result_to_dict(self):
        """RiskAnalysisResult to_dict includes all fields."""
        black_stats = PlayerRiskStats(
            total_contexts=5,
            winning_count=2,
            losing_count=1,
            close_count=2,
            mismatch_count=1,
            contexts_with_stdev=4,
            contexts_with_fallback=1,
        )
        white_stats = PlayerRiskStats(
            total_contexts=4,
            winning_count=1,
            losing_count=2,
            close_count=1,
            mismatch_count=0,
            contexts_with_stdev=4,
            contexts_with_fallback=0,
        )
        result = RiskAnalysisResult(
            contexts=(),
            has_stdev_data=True,
            fallback_used=True,
            strategy_mismatch_count=1,
            winning_contexts=3,
            losing_contexts=3,
            black_stats=black_stats,
            white_stats=white_stats,
        )

        result_dict = result.to_dict()
        assert result_dict["has_stdev_data"] is True
        assert result_dict["fallback_used"] is True
        assert result_dict["strategy_mismatch_count"] == 1
        assert result_dict["black_stats"]["total_contexts"] == 5
        assert result_dict["white_stats"]["mismatch_count"] == 0
