"""Tests for katrain.core.curator.scoring (Phase 63).

Tests cover:
- Pure helper functions (_normalize_meaning_tag_key, _combine_meaning_tags,
  _round_half_up, _wrap_debug_info)
- _compute_volatility (population stdev)
- _compute_total (weighted total with normalization)
- compute_batch_percentiles (ECDF-style)
- _collect_score_leads (GameNode traversal)
- compute_stability (volatility-driven score)
- score_game_suitability (public single-game API)
- score_batch_suitability (public batch API)
"""

from __future__ import annotations

import math
from types import MappingProxyType
from unittest.mock import MagicMock

import pytest

from katrain.core.analysis.meaning_tags.models import MeaningTagId
from katrain.core.curator.models import (
    DEFAULT_CONFIG,
    UNCERTAIN_TAG,
    SuitabilityConfig,
    SuitabilityScore,
)
from katrain.core.curator.scoring import (
    _collect_score_leads,
    _combine_meaning_tags,
    _compute_total,
    _compute_volatility,
    _normalize_meaning_tag_key,
    _round_half_up,
    _wrap_debug_info,
    compute_batch_percentiles,
    compute_stability,
    score_batch_suitability,
    score_game_suitability,
)
from katrain.core.game_node import GameNode

# =============================================================================
# _normalize_meaning_tag_key
# =============================================================================


class TestNormalizeMeaningTagKey:
    """Tests for MeaningTagId/str normalization."""

    def test_string_passthrough(self):
        """Plain strings are returned as-is."""
        assert _normalize_meaning_tag_key("overplay") == "overplay"

    def test_enum_uses_value_not_str(self):
        """Enum uses .value (avoids "MeaningTagId.OVERPLAY" string drift)."""
        assert _normalize_meaning_tag_key(MeaningTagId.OVERPLAY) == "overplay"
        assert _normalize_meaning_tag_key(MeaningTagId.UNCERTAIN) == UNCERTAIN_TAG

    def test_string_passthrough_with_uncertain(self):
        """'uncertain' string is preserved (case-sensitive)."""
        assert _normalize_meaning_tag_key("uncertain") == "uncertain"


# =============================================================================
# _combine_meaning_tags
# =============================================================================


class TestCombineMeaningTags:
    """Tests for combining tag counts across players."""

    def test_combines_b_and_w(self):
        """Tags from both players are summed."""
        tags = {
            "B": {"overplay": 3, "missed_kill": 1},
            "W": {"overplay": 2, "territory_loss": 4},
        }
        combined = _combine_meaning_tags(tags)
        assert combined["overplay"] == 5
        assert combined["missed_kill"] == 1
        assert combined["territory_loss"] == 4

    def test_excludes_uncertain(self):
        """UNCERTAIN tag is filtered out."""
        tags = {
            "B": {"overplay": 3, UNCERTAIN_TAG: 10},
            "W": {"missed_kill": 2},
        }
        combined = _combine_meaning_tags(tags)
        assert UNCERTAIN_TAG not in combined
        assert combined == {"overplay": 3, "missed_kill": 2}

    def test_empty_input_returns_empty(self):
        """Empty tags dict returns empty combined."""
        assert _combine_meaning_tags({}) == {}

    def test_normalizes_enum_keys(self):
        """MeaningTagId enum keys are normalized to strings."""
        tags = {
            "B": {MeaningTagId.OVERPLAY: 2, MeaningTagId.MISSED_TESUJI: 1},
        }
        combined = _combine_meaning_tags(tags)
        assert combined == {"overplay": 2, "missed_tesuji": 1}


# =============================================================================
# _round_half_up
# =============================================================================


class TestRoundHalfUp:
    """Tests for half-up rounding (avoids banker's rounding)."""

    def test_round_up_at_half(self):
        """12.5 rounds to 13 (NOT 12 from banker's rounding)."""
        assert _round_half_up(12.5) == 13

    def test_round_down_below_half(self):
        """12.4 rounds to 12."""
        assert _round_half_up(12.4) == 12

    def test_round_up_above_half(self):
        """12.6 rounds to 13."""
        assert _round_half_up(12.6) == 13

    def test_zero(self):
        """0.0 rounds to 0."""
        assert _round_half_up(0.0) == 0

    def test_whole_numbers(self):
        """Whole numbers round to themselves."""
        assert _round_half_up(10.0) == 10
        assert _round_half_up(100.0) == 100

    def test_large_half_up(self):
        """Larger .5 values round up too."""
        assert _round_half_up(99.5) == 100


# =============================================================================
# _wrap_debug_info
# =============================================================================


class TestWrapDebugInfo:
    """Tests for MappingProxyType wrapping."""

    def test_none_returns_none(self):
        """None input returns None."""
        assert _wrap_debug_info(None) is None

    def test_dict_wrapped_in_mapping_proxy(self):
        """Dict becomes MappingProxyType."""
        d = {"key": "value"}
        wrapped = _wrap_debug_info(d)
        assert isinstance(wrapped, MappingProxyType)
        assert wrapped["key"] == "value"

    def test_copies_input_dict(self):
        """Original dict mutation does not affect wrapped proxy."""
        d = {"key": "original"}
        wrapped = _wrap_debug_info(d)
        d["key"] = "mutated"
        # Wrapped copy preserves original
        assert wrapped["key"] == "original"  # type: ignore[index]


# =============================================================================
# _compute_volatility
# =============================================================================


class TestComputeVolatility:
    """Tests for population standard deviation."""

    def test_too_few_values_returns_none(self):
        """len < 2 returns None (cannot compute stdev)."""
        assert _compute_volatility([]) is None
        assert _compute_volatility([1.0]) is None

    def test_constant_values_zero_volatility(self):
        """All-equal values produce zero volatility."""
        assert _compute_volatility([5.0, 5.0, 5.0]) == 0.0

    def test_simple_pair(self):
        """Two values [0, 10]: mean=5, variance=25, stdev=5."""
        # pop var = ((0-5)^2 + (10-5)^2) / 2 = 25
        # pop stdev = sqrt(25) = 5
        assert _compute_volatility([0.0, 10.0]) == pytest.approx(5.0)

    def test_symmetric_distribution(self):
        """Symmetric values around mean have known volatility."""
        # [10, 10, 10, 10, 10] -> 0
        assert _compute_volatility([10.0] * 5) == 0.0

    def test_uses_population_not_sample(self):
        """Population stdev uses /n, not /(n-1)."""
        # [1, 2, 3, 4, 5]: mean=3, pop var = (4+1+0+1+4)/5 = 2, pop stdev = sqrt(2)
        # Sample var = (4+1+0+1+4)/4 = 2.5, sample stdev = sqrt(2.5)
        expected = math.sqrt(2.0)
        assert _compute_volatility([1.0, 2.0, 3.0, 4.0, 5.0]) == pytest.approx(expected)


# =============================================================================
# _compute_total
# =============================================================================


class TestComputeTotal:
    """Tests for weighted total computation."""

    def test_equal_weights_50_50(self):
        """Equal weights give simple average."""
        cfg = SuitabilityConfig(needs_match_weight=0.5, stability_weight=0.5)
        # (0.4 * 0.5 + 0.6 * 0.5) / 1.0 = 0.5
        assert _compute_total(0.4, 0.6, cfg) == pytest.approx(0.5)

    def test_unnormalized_weights_normalized(self):
        """Weights are normalized at computation time."""
        # Sum=1.5 (unusual), but normalization handles it
        cfg = SuitabilityConfig(needs_match_weight=0.6, stability_weight=0.9)  # sum=1.5
        # w_n = 0.6/1.5 = 0.4, w_s = 0.9/1.5 = 0.6
        # 0.5 * 0.4 + 0.7 * 0.6 = 0.2 + 0.42 = 0.62
        assert _compute_total(0.5, 0.7, cfg) == pytest.approx(0.62)

    def test_zero_weights_returns_zero(self):
        """If weight_sum <= 0, returns 0.0."""
        cfg = SuitabilityConfig(needs_match_weight=0.0, stability_weight=0.0)
        assert _compute_total(0.5, 0.7, cfg) == 0.0

    def test_negative_weights_treated_as_zero(self):
        """Negative weights still normalize (sum <= 0 returns 0)."""
        cfg = SuitabilityConfig(needs_match_weight=-1.0, stability_weight=0.5)  # sum = -0.5
        assert _compute_total(0.5, 0.7, cfg) == 0.0

    def test_full_needs_match_weight(self):
        """When only needs_match is weighted, total = needs_match."""
        cfg = SuitabilityConfig(needs_match_weight=1.0, stability_weight=0.0)
        assert _compute_total(0.4, 0.9, cfg) == pytest.approx(0.4)

    def test_full_stability_weight(self):
        """When only stability is weighted, total = stability."""
        cfg = SuitabilityConfig(needs_match_weight=0.0, stability_weight=1.0)
        assert _compute_total(0.4, 0.9, cfg) == pytest.approx(0.9)


# =============================================================================
# compute_batch_percentiles (ECDF-style)
# =============================================================================


class TestComputeBatchPercentiles:
    """Tests for ECDF-style percentile calculation."""

    def test_empty_list_returns_empty(self):
        """Empty input → empty output."""
        assert compute_batch_percentiles([]) == []

    def test_single_score_gets_percentile_100(self):
        """Single game gets percentile=100."""
        score = SuitabilityScore(needs_match=0.5, stability=0.5, total=0.5)
        result = compute_batch_percentiles([score])
        assert len(result) == 1
        assert result[0].percentile == 100

    def test_all_same_total_all_get_100(self):
        """All games tied at top: all get percentile=100."""
        scores = [
            SuitabilityScore(needs_match=0.5, stability=0.5, total=1.0),
            SuitabilityScore(needs_match=0.5, stability=0.5, total=1.0),
            SuitabilityScore(needs_match=0.5, stability=0.5, total=1.0),
        ]
        result = compute_batch_percentiles(scores)
        for r in result:
            assert r.percentile == 100

    def test_unique_totals_strictly_ranked(self):
        """Each game gets a percentile based on its rank."""
        scores = [
            SuitabilityScore(needs_match=0.0, stability=0.0, total=0.0),  # worst
            SuitabilityScore(needs_match=0.5, stability=0.5, total=0.5),  # middle
            SuitabilityScore(needs_match=1.0, stability=1.0, total=1.0),  # best
        ]
        result = compute_batch_percentiles(scores)
        # count_le for total=0.0: 1/3 → 33%
        # count_le for total=0.5: 2/3 → 67%
        # count_le for total=1.0: 3/3 → 100%
        percentiles = [r.percentile for r in result]
        assert percentiles[0] == 33
        assert percentiles[1] == 67
        assert percentiles[2] == 100

    def test_top_tied_get_100(self):
        """Top tied items always get percentile=100 (ECDF property)."""
        scores = [
            SuitabilityScore(needs_match=0.3, stability=0.3, total=0.3),
            SuitabilityScore(needs_match=1.0, stability=1.0, total=1.0),
            SuitabilityScore(needs_match=1.0, stability=1.0, total=1.0),
        ]
        result = compute_batch_percentiles(scores)
        assert result[0].percentile == 33  # 1/3 → 33
        assert result[1].percentile == 100  # 3/3 → 100
        assert result[2].percentile == 100  # 3/3 → 100

    def test_preserves_original_fields(self):
        """Percentile calculation preserves other fields."""
        score = SuitabilityScore(
            needs_match=0.5, stability=0.5, total=1.0, percentile=None
        )
        result = compute_batch_percentiles([score])
        assert result[0].needs_match == 0.5
        assert result[0].stability == 0.5
        assert result[0].total == 1.0


# =============================================================================
# Helpers for GameNode-based tests
# =============================================================================


def _build_mainline_nodes(score_leads: list[float]) -> GameNode:
    """Build a mainline chain of GameNodes with analysis.scoreLead values.

    Returns the root. Trailing node has no children (or terminates naturally).
    """
    root = GameNode(properties={"SZ": ["19"], "KM": ["6.5"], "RU": ["Japanese"]})
    root.analysis = None
    current = root
    for i, lead in enumerate(score_leads):
        child = GameNode(parent=current, move=None, properties={})
        if lead is not None and math.isfinite(lead):
            child.analysis = {"root_info": {"scoreLead": lead}}
        else:
            child.analysis = None
        current = child
    return root


def _make_game_with_root(root: GameNode) -> MagicMock:
    """Wrap a GameNode tree in a Game-like MagicMock for _collect_score_leads."""
    game = MagicMock()
    game.root = root
    return game


# =============================================================================
# _collect_score_leads
# =============================================================================


class TestCollectScoreLeads:
    """Tests for scoreLead extraction from mainline GameNodes."""

    def test_empty_tree_returns_empty(self):
        """Empty/uninitialized root returns empty list."""
        root = GameNode(properties={"SZ": ["19"]})
        root.analysis = None
        game = _make_game_with_root(root)
        assert _collect_score_leads(game) == []

    def test_single_value(self):
        """Single valid scoreLead is collected."""
        root = _build_mainline_nodes([5.0])
        game = _make_game_with_root(root)
        result = _collect_score_leads(game)
        # Result includes scoreLeads along the chain
        assert 5.0 in result

    def test_multiple_values_in_order(self):
        """Multiple scoreLeads collected in mainline order."""
        root = _build_mainline_nodes([10.0, 20.0, 30.0])
        game = _make_game_with_root(root)
        result = _collect_score_leads(game)
        # Filter finite valid values
        finite = [v for v in result if math.isfinite(v)]
        assert finite == [10.0, 20.0, 30.0]

    def test_skips_node_without_analysis(self):
        """Nodes without analysis are skipped."""
        root = GameNode(properties={"SZ": ["19"]})
        root.analysis = None
        child = GameNode(parent=root, move=None, properties={})
        child.analysis = {"root_info": {"scoreLead": 7.0}}
        # root.analysis is None → skipped
        game = _make_game_with_root(root)
        result = _collect_score_leads(game)
        assert result == [7.0]

    def test_skips_node_with_missing_root_info(self):
        """Node where analysis lacks root_info is skipped."""
        root = GameNode(properties={"SZ": ["19"]})
        root.analysis = {"wrong_key": {}}  # no root_info
        game = _make_game_with_root(root)
        assert _collect_score_leads(game) == []

    def test_skips_node_with_missing_score_lead(self):
        """Node where root_info lacks scoreLead is skipped."""
        root = GameNode(properties={"SZ": ["19"]})
        root.analysis = {"root_info": {}}  # no scoreLead
        game = _make_game_with_root(root)
        assert _collect_score_leads(game) == []

    def test_skips_none_score_lead(self):
        """scoreLead=None is skipped."""
        root = GameNode(properties={"SZ": ["19"]})
        root.analysis = {"root_info": {"scoreLead": None}}
        game = _make_game_with_root(root)
        assert _collect_score_leads(game) == []

    def test_skips_non_numeric_score_lead(self):
        """Non-numeric scoreLead (e.g., string) is skipped."""
        root = GameNode(properties={"SZ": ["19"]})
        root.analysis = {"root_info": {"scoreLead": "not a number"}}
        game = _make_game_with_root(root)
        assert _collect_score_leads(game) == []

    def test_skips_nan_score_lead(self):
        """NaN scoreLead is skipped (math.isfinite filter)."""
        root = GameNode(properties={"SZ": ["19"]})
        root.analysis = {"root_info": {"scoreLead": float("nan")}}
        game = _make_game_with_root(root)
        assert _collect_score_leads(game) == []

    def test_skips_inf_score_lead(self):
        """Infinity scoreLead is skipped."""
        root = GameNode(properties={"SZ": ["19"]})
        root.analysis = {"root_info": {"scoreLead": float("inf")}}
        game = _make_game_with_root(root)
        assert _collect_score_leads(game) == []

    def test_follows_only_first_child(self):
        """Only the first child (children[0]) is followed (mainline)."""
        # Setup: root → [main_child, side_branch]
        root = GameNode(properties={"SZ": ["19"]})
        root.analysis = None
        main = GameNode(parent=root, move=None, properties={})
        main.analysis = {"root_info": {"scoreLead": 1.0}}
        side = GameNode(parent=root, move=None, properties={})
        side.analysis = {"root_info": {"scoreLead": 999.0}}  # variation
        root.children = [main, side]
        game = _make_game_with_root(root)
        result = _collect_score_leads(game)
        # Should only have 1.0 (main), not 999.0 (side branch)
        assert result == [1.0]

    def test_accepts_int_score_lead(self):
        """Integer scoreLead is accepted (coerced to float)."""
        root = GameNode(properties={"SZ": ["19"]})
        root.analysis = {"root_info": {"scoreLead": 5}}  # int, not float
        game = _make_game_with_root(root)
        result = _collect_score_leads(game)
        assert result == [5.0]


# =============================================================================
# compute_stability
# =============================================================================


class TestComputeStability:
    """Tests for stability score from scoreLead volatility."""

    def test_insufficient_data_returns_default(self):
        """< 2 valid scoreLeads → stability_insufficient_data (default 0.0)."""
        root = _build_mainline_nodes([5.0])
        game = _make_game_with_root(root)
        result = compute_stability(game)
        assert result == 0.0  # default

    def test_config_insufficient_data_used(self):
        """Custom stability_insufficient_data is used."""
        root = _build_mainline_nodes([5.0])
        game = _make_game_with_root(root)
        cfg = SuitabilityConfig(stability_insufficient_data=0.5)
        result = compute_stability(game, cfg)
        assert result == 0.5

    def test_zero_volatility_max_stability(self):
        """All-equal scoreLeads → volatility=0 → stability=1.0."""
        root = _build_mainline_nodes([5.0, 5.0, 5.0])
        game = _make_game_with_root(root)
        result = compute_stability(game)
        assert result == pytest.approx(1.0)

    def test_max_volatility_zero_returns_default(self):
        """max_volatility=0 (or negative) returns insufficient_data."""
        root = _build_mainline_nodes([5.0, 15.0])
        game = _make_game_with_root(root)
        cfg = SuitabilityConfig(max_volatility=0.0)
        result = compute_stability(game, cfg)
        assert result == 0.0

    def test_clamped_to_zero_minimum(self):
        """Volatility > max_volatility → stability clamped to 0."""
        # [0, 100] has volatility=50 (vs default max=15)
        root = _build_mainline_nodes([0.0, 100.0])
        game = _make_game_with_root(root)
        result = compute_stability(game)
        # 1.0 - clamp(50/15, 0, 1) = 1.0 - 1.0 = 0.0
        assert result == 0.0

    def test_partial_volatility(self):
        """Intermediate volatility → intermediate stability."""
        # [0, 10] volatility = 5; max=15 → 1 - 5/15 = 10/15 ≈ 0.667
        root = _build_mainline_nodes([0.0, 10.0])
        game = _make_game_with_root(root)
        result = compute_stability(game)
        assert result == pytest.approx(10.0 / 15.0)


# =============================================================================
# score_game_suitability (public single-game API)
# =============================================================================


class TestScoreGameSuitability:
    """Tests for score_game_suitability public API."""

    def test_returns_suitability_score(self):
        """score_game_suitability returns SuitabilityScore."""
        root = _build_mainline_nodes([5.0, 10.0])
        game = _make_game_with_root(root)
        stats = {"meaning_tags_by_player": {"B": {"overplay": 3}}}
        score = score_game_suitability(game, stats)  # type: ignore[arg-type]
        assert isinstance(score, SuitabilityScore)

    def test_needs_match_is_zero(self):
        """Phase 137: needs_match is always 0.0 (Radar deprecated)."""
        root = _build_mainline_nodes([5.0, 10.0])
        game = _make_game_with_root(root)
        stats = {"meaning_tags_by_player": {"B": {"overplay": 3}, "W": {"missed_kill": 1}}}
        score = score_game_suitability(game, stats)  # type: ignore[arg-type]
        assert score.needs_match == 0.0

    def test_percentile_not_set_yet(self):
        """Single-game scoring leaves percentile=None."""
        root = _build_mainline_nodes([5.0, 10.0])
        game = _make_game_with_root(root)
        stats: dict = {}
        score = score_game_suitability(game, stats)  # type: ignore[arg-type]
        assert score.percentile is None

    def test_debug_info_contains_combined_tags(self):
        """debug_info["meaning_tags_combined"] has B+W combined counts."""
        root = _build_mainline_nodes([5.0, 10.0])
        game = _make_game_with_root(root)
        stats = {
            "meaning_tags_by_player": {
                "B": {"overplay": 3, "missed_kill": 1},
                "W": {"overplay": 2},
            }
        }
        score = score_game_suitability(game, stats)  # type: ignore[arg-type]
        assert score.debug_info is not None
        combined = score.debug_info["meaning_tags_combined"]  # type: ignore[index]
        assert combined["overplay"] == 5  # 3+2
        assert combined["missed_kill"] == 1

    def test_empty_stats_does_not_crash(self):
        """Empty game_stats dict works (no meaning_tags)."""
        root = _build_mainline_nodes([5.0, 10.0])
        game = _make_game_with_root(root)
        score = score_game_suitability(game, {})  # type: ignore[arg-type]
        assert isinstance(score, SuitabilityScore)
        assert score.debug_info is not None

    def test_uses_default_config(self):
        """No config argument uses DEFAULT_CONFIG."""
        root = _build_mainline_nodes([5.0, 10.0])
        game = _make_game_with_root(root)
        score_no_cfg = score_game_suitability(game, {})  # type: ignore[arg-type]
        score_with_default = score_game_suitability(game, {}, DEFAULT_CONFIG)  # type: ignore[arg-type]
        # Same config → same values (modulo data independence)
        assert score_no_cfg.stability == score_with_default.stability


# =============================================================================
# score_batch_suitability (public batch API)
# =============================================================================


class TestScoreBatchSuitability:
    """Tests for score_batch_suitability public API."""

    def test_empty_batch_returns_empty(self):
        """Empty input → empty scores list."""
        result = score_batch_suitability([])
        assert result == []

    def test_single_game_gets_percentile(self):
        """Single game gets percentile=100 set automatically."""
        root = _build_mainline_nodes([5.0, 10.0])
        game = _make_game_with_root(root)
        result = score_batch_suitability([(game, {"meaning_tags_by_player": {}})])  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].percentile == 100

    def test_multiple_games_get_percentiles(self):
        """Multiple games all get percentiles computed."""
        root1 = _build_mainline_nodes([0.0, 5.0])
        root2 = _build_mainline_nodes([10.0, 15.0])
        games = [
            (_make_game_with_root(root1), {}),  # type: ignore[arg-type]
            (_make_game_with_root(root2), {}),  # type: ignore[arg-type]
        ]
        result = score_batch_suitability(games)
        assert len(result) == 2
        for r in result:
            assert r.percentile is not None
        # Best game (less volatility) should have higher percentile
        # root2: [10,15] → small volatility
        # root1: [0,5] → small volatility
        # Both may get same percentile depending on order
        assert result[0].percentile in (50, 100)
        assert result[1].percentile in (50, 100)

    def test_preserves_suitability_score_objects(self):
        """Output scores are SuitabilityScore instances."""
        root = _build_mainline_nodes([5.0, 10.0])
        game = _make_game_with_root(root)
        result = score_batch_suitability([(game, {})])  # type: ignore[arg-type]
        for r in result:
            assert isinstance(r, SuitabilityScore)
