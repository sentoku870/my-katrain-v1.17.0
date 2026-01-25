"""Tests for Curator Scoring (Phase 63)."""

import dataclasses
import math
from types import MappingProxyType
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from katrain.core.analysis.meaning_tags.models import MeaningTagId
from katrain.core.analysis.skill_radar import AggregatedRadarResult, RadarAxis, SkillTier
from katrain.core.curator import (
    AXIS_TO_MEANING_TAGS,
    DEFAULT_CONFIG,
    SUPPORTED_AXES,
    UNCERTAIN_TAG,
    SuitabilityConfig,
    SuitabilityScore,
    compute_batch_percentiles,
    compute_needs_match,
    compute_stability,
    score_batch_suitability,
    score_game_suitability,
)
from katrain.core.curator.scoring import (
    _collect_score_leads,
    _combine_meaning_tags,
    _compute_total,
    _compute_volatility,
    _normalize_meaning_tag_key,
    _round_half_up,
    _wrap_debug_info,
)


# =============================================================================
# Fixtures
# =============================================================================


def _make_aggregated_radar(
    opening: Optional[float] = 3.0,
    fighting: Optional[float] = 3.0,
    endgame: Optional[float] = 3.0,
    stability: Optional[float] = 3.0,
    awareness: Optional[float] = 3.0,
) -> AggregatedRadarResult:
    """Create an AggregatedRadarResult for testing."""
    return AggregatedRadarResult(
        opening=opening,
        fighting=fighting,
        endgame=endgame,
        stability=stability,
        awareness=awareness,
        opening_tier=SkillTier.TIER_3,
        fighting_tier=SkillTier.TIER_3,
        endgame_tier=SkillTier.TIER_3,
        stability_tier=SkillTier.TIER_3,
        awareness_tier=SkillTier.TIER_3,
        overall_tier=SkillTier.TIER_3,
        valid_move_counts={axis: 10 for axis in RadarAxis},
        games_aggregated=1,
    )


def _make_mock_game(score_leads: List[Optional[float]]) -> MagicMock:
    """Create a mock Game with specified scoreLead values on mainline."""
    game = MagicMock()

    # Build linked list of nodes
    nodes = []
    for score_lead in score_leads:
        node = MagicMock()
        if score_lead is not None:
            node.analysis = {"root_info": {"scoreLead": score_lead}}
        else:
            node.analysis = None
        node.children = []
        nodes.append(node)

    # Link nodes
    for i in range(len(nodes) - 1):
        nodes[i].children = [nodes[i + 1]]

    game.root = nodes[0] if nodes else MagicMock(analysis=None, children=[])
    return game


# =============================================================================
# TestModels
# =============================================================================


class TestModels:
    """Tests for data models."""

    def test_suitability_score_is_frozen(self):
        """Ensure SuitabilityScore is frozen (immutable)."""
        score = SuitabilityScore(
            needs_match=0.5, stability=0.5, total=0.5, percentile=50
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            score.needs_match = 0.6  # type: ignore

    def test_suitability_config_is_frozen(self):
        """Ensure SuitabilityConfig is frozen (immutable)."""
        config = SuitabilityConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.needs_match_weight = 0.7  # type: ignore

    def test_default_config_values(self):
        """Verify default config values."""
        assert DEFAULT_CONFIG.needs_match_weight == 0.6
        assert DEFAULT_CONFIG.stability_weight == 0.4
        assert DEFAULT_CONFIG.min_tag_occurrences == 3
        assert DEFAULT_CONFIG.max_volatility == 15.0
        assert DEFAULT_CONFIG.stability_insufficient_data == 0.0


# =============================================================================
# TestDebugInfoImmutability
# =============================================================================


class TestDebugInfoImmutability:
    """Tests for debug_info immutability."""

    def test_wrap_debug_info_returns_mapping_proxy(self):
        """Ensure _wrap_debug_info returns MappingProxyType."""
        original = {"key": "value"}
        wrapped = _wrap_debug_info(original)
        assert isinstance(wrapped, MappingProxyType)

    def test_wrap_debug_info_none(self):
        """Ensure _wrap_debug_info handles None."""
        assert _wrap_debug_info(None) is None

    def test_debug_info_is_immutable(self):
        """Ensure debug_info cannot be mutated after construction."""
        original = {"key": "value"}
        wrapped = _wrap_debug_info(original)
        assert wrapped is not None
        with pytest.raises(TypeError):
            wrapped["new_key"] = "value"  # type: ignore

    def test_debug_info_is_isolated_from_original(self):
        """Ensure original dict mutation doesn't affect stored debug_info."""
        original = {"key": "original"}
        wrapped = _wrap_debug_info(original)
        original["key"] = "mutated"
        assert wrapped is not None
        assert wrapped["key"] == "original"  # Still original value


# =============================================================================
# TestRadarAxisMapping
# =============================================================================


class TestRadarAxisMapping:
    """Tests for RadarAxis mapping consistency."""

    def test_radar_axis_value_matches_aggregated_radar_fields(self):
        """Ensure RadarAxis.value matches AggregatedRadarResult field names."""
        field_names = {f.name for f in dataclasses.fields(AggregatedRadarResult)}
        for axis in SUPPORTED_AXES:
            assert axis.value in field_names, (
                f"RadarAxis.{axis.name}.value='{axis.value}' "
                f"is not a field of AggregatedRadarResult."
            )

    def test_supported_axes_matches_mapping_keys(self):
        """Ensure SUPPORTED_AXES equals AXIS_TO_MEANING_TAGS keys."""
        assert SUPPORTED_AXES == frozenset(AXIS_TO_MEANING_TAGS.keys())


# =============================================================================
# TestUncertainTag
# =============================================================================


class TestUncertainTag:
    """Tests for UNCERTAIN_TAG constant."""

    def test_uncertain_tag_matches_enum(self):
        """Ensure UNCERTAIN_TAG equals MeaningTagId.UNCERTAIN.value."""
        assert UNCERTAIN_TAG == MeaningTagId.UNCERTAIN.value


# =============================================================================
# TestMeaningTagNormalization
# =============================================================================


class TestMeaningTagNormalization:
    """Tests for MeaningTag key normalization."""

    def test_normalize_string(self):
        """String keys are returned as-is."""
        assert _normalize_meaning_tag_key("overplay") == "overplay"

    def test_normalize_meaning_tag_id(self):
        """MeaningTagId uses .value for normalization."""
        assert _normalize_meaning_tag_key(MeaningTagId.OVERPLAY) == "overplay"

    def test_combine_meaning_tags_excludes_uncertain_string(self):
        """UNCERTAIN string tags are excluded."""
        tags = {"B": {"uncertain": 5, "overplay": 2}, "W": {}}
        combined = _combine_meaning_tags(tags)
        assert "uncertain" not in combined
        assert combined["overplay"] == 2

    def test_combine_meaning_tags_combines_both_players(self):
        """Tags from both players are combined."""
        tags = {"B": {"overplay": 2}, "W": {"overplay": 3, "direction_error": 1}}
        combined = _combine_meaning_tags(tags)
        assert combined["overplay"] == 5
        assert combined["direction_error"] == 1


# =============================================================================
# TestNeedsMatch
# =============================================================================


class TestNeedsMatch:
    """Tests for needs_match calculation."""

    def test_no_user_data_returns_zero(self):
        """No user aggregate returns 0.0."""
        result = compute_needs_match(None, {"overplay": 5})
        assert result == 0.0

    def test_no_weak_axes_returns_zero(self):
        """All axes >= 2.5 returns 0.0."""
        aggregate = _make_aggregated_radar()  # All 3.0
        result = compute_needs_match(aggregate, {"overplay": 5})
        assert result == 0.0

    def test_tag_occurrences_below_threshold_returns_zero(self):
        """total_occurrences < min_tag_occurrences returns 0.0."""
        aggregate = _make_aggregated_radar(fighting=2.0)  # Weak FIGHTING
        result = compute_needs_match(aggregate, {"reading_failure": 2})  # Only 2
        assert result == 0.0

    def test_full_match(self):
        """All tags match weak axis returns 1.0."""
        aggregate = _make_aggregated_radar(fighting=2.0)  # Weak FIGHTING
        # FIGHTING includes: capture_race_loss, life_death_error, reading_failure, missed_tesuji
        tags = {"reading_failure": 3}
        result = compute_needs_match(aggregate, tags)
        assert result == pytest.approx(1.0)

    def test_partial_match(self):
        """Partial match returns matching_occurrences / total_occurrences."""
        aggregate = _make_aggregated_radar(fighting=2.0)  # Weak FIGHTING
        tags = {"reading_failure": 1, "direction_error": 2}  # 1/3 match
        result = compute_needs_match(aggregate, tags)
        assert result == pytest.approx(1 / 3)

    def test_multiple_weak_axes(self):
        """Multiple weak axes combine their related tags."""
        aggregate = _make_aggregated_radar(fighting=2.0, endgame=2.0)
        # FIGHTING + ENDGAME tags
        tags = {"reading_failure": 2, "endgame_slip": 1}
        result = compute_needs_match(aggregate, tags)
        assert result == pytest.approx(1.0)


# =============================================================================
# TestCollectScoreLeads
# =============================================================================


class TestCollectScoreLeads:
    """Tests for scoreLead collection."""

    def test_collects_mainline_only(self):
        """Only mainline nodes are collected."""
        game = _make_mock_game([1.0, 2.0, 3.0])
        result = _collect_score_leads(game)
        assert result == [1.0, 2.0, 3.0]

    def test_skips_unanalyzed_nodes(self):
        """Nodes without analysis are skipped."""
        game = _make_mock_game([1.0, None, 3.0])
        result = _collect_score_leads(game)
        assert result == [1.0, 3.0]

    def test_skips_missing_root_info(self):
        """Nodes with analysis but no root_info are skipped."""
        game = _make_mock_game([1.0])
        # Modify second node to have analysis but no root_info
        node2 = MagicMock()
        node2.analysis = {"other_key": "value"}  # No root_info
        node2.children = []
        game.root.children = [node2]

        result = _collect_score_leads(game)
        assert result == [1.0]

    def test_skips_nan_score_lead(self):
        """NaN scoreLead values are skipped."""
        game = _make_mock_game([1.0, float("nan"), 3.0])
        result = _collect_score_leads(game)
        assert result == [1.0, 3.0]

    def test_empty_game_returns_empty_list(self):
        """Empty game returns empty list."""
        game = MagicMock()
        game.root = MagicMock(analysis=None, children=[])
        result = _collect_score_leads(game)
        assert result == []


# =============================================================================
# TestVolatility
# =============================================================================


class TestVolatility:
    """Tests for volatility calculation."""

    def test_insufficient_data_returns_none(self):
        """Less than 2 values returns None."""
        assert _compute_volatility([]) is None
        assert _compute_volatility([1.0]) is None

    def test_constant_values_return_zero(self):
        """Constant values have zero volatility."""
        result = _compute_volatility([5.0, 5.0, 5.0])
        assert result == pytest.approx(0.0)

    def test_population_stdev(self):
        """Verifies population standard deviation calculation."""
        # Values: 2, 4, 4, 4, 5, 5, 7, 9
        # Mean = 5, Variance = 4, Stdev = 2
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        result = _compute_volatility(values)
        assert result == pytest.approx(2.0)


# =============================================================================
# TestStability
# =============================================================================


class TestStability:
    """Tests for stability calculation."""

    def test_stable_game(self):
        """Low volatility gives high stability."""
        game = _make_mock_game([0.0, 0.0, 0.0])  # volatility = 0
        result = compute_stability(game)
        assert result == pytest.approx(1.0)

    def test_chaotic_game(self):
        """High volatility (= max_volatility) gives stability = 0."""
        # Need volatility = 15.0
        # stdev([0, 30]) = 15.0
        game = _make_mock_game([0.0, 30.0])
        result = compute_stability(game)
        assert result == pytest.approx(0.0)

    def test_very_chaotic_game_clamped(self):
        """Volatility > max_volatility is clamped to 0."""
        # stdev([0, 40]) = 20.0 > 15.0
        game = _make_mock_game([0.0, 40.0])
        result = compute_stability(game)
        assert result == pytest.approx(0.0)

    def test_insufficient_data_returns_default(self):
        """Less than 2 valid scores returns config default."""
        game = _make_mock_game([1.0])  # Only 1 value
        result = compute_stability(game)
        assert result == pytest.approx(0.0)  # Default

    def test_insufficient_data_custom_default(self):
        """Custom config.stability_insufficient_data is used."""
        game = _make_mock_game([1.0])
        config = SuitabilityConfig(stability_insufficient_data=0.5)
        result = compute_stability(game, config)
        assert result == pytest.approx(0.5)


# =============================================================================
# TestTotal
# =============================================================================


class TestTotal:
    """Tests for total calculation."""

    def test_default_weights(self):
        """Default weights: 0.6 * needs_match + 0.4 * stability."""
        result = _compute_total(1.0, 1.0, DEFAULT_CONFIG)
        assert result == pytest.approx(1.0)

        result = _compute_total(0.5, 0.5, DEFAULT_CONFIG)
        assert result == pytest.approx(0.5)

    def test_weight_normalization(self):
        """Weights are normalized if sum != 1.0."""
        config = SuitabilityConfig(needs_match_weight=0.9, stability_weight=0.6)
        # Normalized: 0.9/1.5 = 0.6, 0.6/1.5 = 0.4
        result = _compute_total(1.0, 0.0, config)
        assert result == pytest.approx(0.6)

    def test_zero_weights_returns_zero(self):
        """Zero weights returns 0.0."""
        config = SuitabilityConfig(needs_match_weight=0.0, stability_weight=0.0)
        result = _compute_total(1.0, 1.0, config)
        assert result == pytest.approx(0.0)


# =============================================================================
# TestRoundHalfUp
# =============================================================================


class TestRoundHalfUp:
    """Tests for half-up rounding (non-negative values)."""

    def test_round_down(self):
        """Values < .5 round down."""
        assert _round_half_up(12.4) == 12

    def test_round_half_up(self):
        """Values = .5 round up (not banker's rounding)."""
        assert _round_half_up(12.5) == 13

    def test_round_up(self):
        """Values > .5 round up."""
        assert _round_half_up(12.6) == 13

    def test_half_boundary(self):
        """0.5 rounds to 1."""
        assert _round_half_up(0.5) == 1

    def test_zero(self):
        """0.0 rounds to 0."""
        assert _round_half_up(0.0) == 0


# =============================================================================
# TestPercentileECDF
# =============================================================================


class TestPercentileECDF:
    """Tests for ECDF-style percentile calculation."""

    def _make_scores(self, totals: List[float]) -> List[SuitabilityScore]:
        """Create SuitabilityScore list from totals."""
        return [
            SuitabilityScore(needs_match=0.5, stability=0.5, total=t) for t in totals
        ]

    def test_ascending_totals(self):
        """Ascending totals: [0.3, 0.5, 0.7] -> [33, 67, 100]."""
        scores = self._make_scores([0.3, 0.5, 0.7])
        result = compute_batch_percentiles(scores)
        percentiles = [s.percentile for s in result]
        assert percentiles == [33, 67, 100]

    def test_top_ties_get_100(self):
        """Top-tied items get 100: [0.5, 0.7, 0.7] -> [33, 100, 100]."""
        scores = self._make_scores([0.5, 0.7, 0.7])
        result = compute_batch_percentiles(scores)
        percentiles = [s.percentile for s in result]
        assert percentiles == [33, 100, 100]

    def test_middle_ties(self):
        """Middle ties: [0.5, 0.5, 0.7] -> [67, 67, 100]."""
        scores = self._make_scores([0.5, 0.5, 0.7])
        result = compute_batch_percentiles(scores)
        percentiles = [s.percentile for s in result]
        assert percentiles == [67, 67, 100]

    def test_all_equal(self):
        """All equal: [0.5, 0.5, 0.5] -> [100, 100, 100]."""
        scores = self._make_scores([0.5, 0.5, 0.5])
        result = compute_batch_percentiles(scores)
        percentiles = [s.percentile for s in result]
        assert percentiles == [100, 100, 100]

    def test_single_item(self):
        """Single item: [0.5] -> [100]."""
        scores = self._make_scores([0.5])
        result = compute_batch_percentiles(scores)
        percentiles = [s.percentile for s in result]
        assert percentiles == [100]

    def test_empty_list(self):
        """Empty list returns empty list."""
        result = compute_batch_percentiles([])
        assert result == []

    def test_four_items(self):
        """Four items: [0.3, 0.5, 0.5, 0.7] -> [25, 75, 75, 100]."""
        scores = self._make_scores([0.3, 0.5, 0.5, 0.7])
        result = compute_batch_percentiles(scores)
        percentiles = [s.percentile for s in result]
        assert percentiles == [25, 75, 75, 100]

    def test_half_up_boundary(self):
        """n=8, lowest -> 1/8*100=12.5 -> 13 (half-up)."""
        scores = self._make_scores([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        result = compute_batch_percentiles(scores)
        assert result[0].percentile == 13  # 1/8 = 12.5 -> 13


# =============================================================================
# TestBatchScoring
# =============================================================================


class TestBatchScoring:
    """Integration tests for batch scoring."""

    def test_score_game_suitability_basic(self):
        """Basic scoring returns valid SuitabilityScore."""
        aggregate = _make_aggregated_radar(fighting=2.0)  # Weak FIGHTING
        game = _make_mock_game([1.0, 2.0, 3.0])
        stats: Dict[str, Any] = {
            "meaning_tags_by_player": {"B": {"reading_failure": 3}, "W": {}}
        }

        score = score_game_suitability(aggregate, game, stats)

        assert 0.0 <= score.needs_match <= 1.0
        assert 0.0 <= score.stability <= 1.0
        assert 0.0 <= score.total <= 1.0
        assert score.percentile is None  # Not set yet
        assert score.debug_info is not None

    def test_score_batch_suitability(self):
        """Batch scoring computes percentiles."""
        aggregate = _make_aggregated_radar(fighting=2.0)
        games_and_stats = [
            (
                _make_mock_game([1.0, 2.0]),
                {"meaning_tags_by_player": {"B": {"reading_failure": 3}, "W": {}}},
            ),
            (
                _make_mock_game([1.0, 2.0]),
                {"meaning_tags_by_player": {"B": {"direction_error": 3}, "W": {}}},
            ),
        ]

        scores = score_batch_suitability(aggregate, games_and_stats)

        assert len(scores) == 2
        assert all(s.percentile is not None for s in scores)
        # At least one should be 100 (ECDF-style)
        assert any(s.percentile == 100 for s in scores)

    def test_debug_info_immutable_in_score_game(self):
        """debug_info from score_game_suitability is immutable."""
        aggregate = _make_aggregated_radar()
        game = _make_mock_game([1.0, 2.0])
        stats: Dict[str, Any] = {"meaning_tags_by_player": {"B": {}, "W": {}}}

        score = score_game_suitability(aggregate, game, stats)

        assert score.debug_info is not None
        with pytest.raises(TypeError):
            score.debug_info["new_key"] = "value"  # type: ignore
