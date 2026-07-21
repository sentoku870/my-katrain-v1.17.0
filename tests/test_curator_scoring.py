"""Unit tests for ``katrain.core.curator.scoring`` (Phase 282-P1B).

The Curator scoring pipeline was previously uncovered despite being a core
batch-analysis feature. These tests exercise the pure helper functions
(no Kivy, no KataGo engine) to lock in regression-safe behavior.

Coverage targets:
- ``_normalize_meaning_tag_key``: enum / str handling
- ``_combine_meaning_tags``: B/W merge + UNCERTAIN filtering
- ``_extract_user_weak_tags``: 3 supported shapes
- ``_compute_jaccard_score``: math + insufficient-data branch
- ``_round_half_up``: half-up semantics (vs banker's)
- ``_wrap_debug_info``: MappingProxyType wrapping
- ``_compute_total``: weighted normalization
- ``compute_batch_percentiles``: ECDF-style percentile + ties
"""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import MagicMock

import pytest

from katrain.core.curator.models import DEFAULT_CONFIG, SuitabilityConfig, SuitabilityScore
from katrain.core.curator.scoring import (
    _combine_meaning_tags,
    _compute_jaccard_score,
    _compute_total,
    _compute_volatility,
    _extract_user_weak_tags,
    _normalize_meaning_tag_key,
    _round_half_up,
    _wrap_debug_info,
    compute_batch_percentiles,
)

# =============================================================================
# _normalize_meaning_tag_key
# =============================================================================


class TestNormalizeMeaningTagKey:
    def test_passthrough_string(self):
        assert _normalize_meaning_tag_key("overplay") == "overplay"

    def test_enum_value(self):
        from katrain.core.analysis.meaning_tags.models import MeaningTagId

        assert _normalize_meaning_tag_key(MeaningTagId.OVERPLAY) == "overplay"

    def test_uses_value_not_repr(self):
        """str(MeaningTagId.OVERPLAY) returns 'MeaningTagId.OVERPLAY' (wrong).

        This test ensures we always use ``.value`` so the resulting key
        matches what downstream callers expect (e.g. i18n lookup).
        """
        from katrain.core.analysis.meaning_tags.models import MeaningTagId

        result = _normalize_meaning_tag_key(MeaningTagId.OVERPLAY)
        assert "MeaningTagId" not in result
        assert result == "overplay"

    def test_non_string_non_enum_falls_back_to_str(self):
        assert _normalize_meaning_tag_key(123) == "123"  # type: ignore[arg-type]


# =============================================================================
# _combine_meaning_tags
# =============================================================================


class TestCombineMeaningTags:
    def test_combines_both_players(self):
        per_player = {
            "B": {"overplay": 2, "life_death_error": 1},
            "W": {"overplay": 1, "direction_miss": 3},
        }
        combined = _combine_meaning_tags(per_player)
        assert combined == {"overplay": 3, "life_death_error": 1, "direction_miss": 3}

    def test_excludes_uncertain_tag(self):
        from katrain.core.curator.models import UNCERTAIN_TAG

        per_player = {
            "B": {UNCERTAIN_TAG: 5, "overplay": 1},
            "W": {UNCERTAIN_TAG: 2},
        }
        combined = _combine_meaning_tags(per_player)
        assert UNCERTAIN_TAG not in combined
        assert combined == {"overplay": 1}

    def test_empty_input(self):
        assert _combine_meaning_tags({}) == {}

    def test_normalizes_enum_keys(self):
        from katrain.core.analysis.meaning_tags.models import MeaningTagId

        per_player = {"B": {MeaningTagId.OVERPLAY: 2}}
        combined = _combine_meaning_tags(per_player)
        assert combined == {"overplay": 2}


# =============================================================================
# _extract_user_weak_tags
# =============================================================================


class TestExtractUserWeakTags:
    def test_none_returns_empty(self):
        assert _extract_user_weak_tags(None, min_occurrences=1) == set()

    def test_weak_tags_set(self):
        agg = MagicMock(spec=["weak_tags"])
        agg.weak_tags = {"overplay", "life_death_error"}
        result = _extract_user_weak_tags(agg, min_occurrences=1)
        assert result == {"overplay", "life_death_error"}

    def test_weak_tags_dict_with_threshold(self):
        agg = MagicMock(spec=["weak_tags"])
        agg.weak_tags = {"overplay": 5, "rare_tag": 1, "common_tag": 10}
        result = _extract_user_weak_tags(agg, min_occurrences=3)
        assert result == {"overplay", "common_tag"}

    def test_meaning_tags_alias(self):
        """``meaning_tags`` is accepted as an alias for ``weak_tags``."""
        agg = MagicMock(spec=["meaning_tags"])
        agg.meaning_tags = {"overplay"}
        result = _extract_user_weak_tags(agg, min_occurrences=1)
        assert result == {"overplay"}

    def test_meaning_tags_by_player_shape(self):
        agg = MagicMock(spec=["meaning_tags_by_player"])
        agg.meaning_tags_by_player = {
            "B": {"overplay": 2, "bad_tag": 0},
            "W": {"life_death_error": 4},
        }
        result = _extract_user_weak_tags(agg, min_occurrences=2)
        assert result == {"overplay", "life_death_error"}

    def test_meaning_tags_by_player_skips_non_dict_values(self):
        agg = MagicMock(spec=["meaning_tags_by_player"])
        agg.meaning_tags_by_player = {
            "B": "not a dict",
            "W": {"valid": 5},
        }
        result = _extract_user_weak_tags(agg, min_occurrences=1)
        assert result == {"valid"}

    def test_no_known_attrs_returns_empty(self):
        agg = MagicMock(spec=["some_other_attr"])
        agg.some_other_attr = "x"
        assert _extract_user_weak_tags(agg, min_occurrences=1) == set()

    def test_skips_uncertain_in_set(self):
        from katrain.core.curator.models import UNCERTAIN_TAG

        agg = MagicMock(spec=["weak_tags"])
        agg.weak_tags = {"overplay", UNCERTAIN_TAG}
        result = _extract_user_weak_tags(agg, min_occurrences=1)
        assert UNCERTAIN_TAG not in result


# =============================================================================
# _compute_jaccard_score
# =============================================================================


class TestComputeJaccardScore:
    def test_full_overlap_returns_1(self):
        score = _compute_jaccard_score({"a", "b"}, {"a": 5, "b": 3}, DEFAULT_CONFIG)
        assert score == 1.0

    def test_partial_overlap(self):
        # A={a,b}, B={a,c} -> |intersect|=1, |union|=3 -> 1/3
        score = _compute_jaccard_score({"a", "b"}, {"a": 5, "c": 3}, DEFAULT_CONFIG)
        assert score == pytest.approx(1 / 3)

    def test_no_overlap_returns_zero(self):
        score = _compute_jaccard_score({"a", "b"}, {"x": 5, "y": 3}, DEFAULT_CONFIG)
        assert score == 0.0

    def test_empty_user_weak_tags_returns_insufficient(self):
        score = _compute_jaccard_score(set(), {"a": 5}, DEFAULT_CONFIG)
        assert score == DEFAULT_CONFIG.jaccard_insufficient_data

    def test_empty_game_tags_returns_insufficient(self):
        score = _compute_jaccard_score({"a"}, {}, DEFAULT_CONFIG)
        assert score == DEFAULT_CONFIG.jaccard_insufficient_data

    def test_filters_below_min_occurrences(self):
        cfg = SuitabilityConfig(min_tag_occurrences=3)
        # "rare" has only 2 occurrences -> excluded from game_tags
        # A={a}, B'={a} -> overlap=1, union=1 -> 1.0
        score = _compute_jaccard_score({"a"}, {"a": 5, "rare": 2}, cfg)
        assert score == 1.0

    def test_all_below_threshold_returns_insufficient(self):
        cfg = SuitabilityConfig(min_tag_occurrences=10)
        score = _compute_jaccard_score({"a"}, {"a": 1, "b": 2}, cfg)
        assert score == cfg.jaccard_insufficient_data


# =============================================================================
# _round_half_up
# =============================================================================


class TestRoundHalfUp:
    def test_half_rounds_up(self):
        """Python's round() uses banker's rounding: round(0.5) = 0.

        Our _round_half_up must always round .5 up.
        """
        assert _round_half_up(0.5) == 1
        assert _round_half_up(1.5) == 2
        assert _round_half_up(2.5) == 3  # banker's would give 2
        assert _round_half_up(12.5) == 13

    def test_normal_values(self):
        assert _round_half_up(0.4) == 0
        assert _round_half_up(0.6) == 1
        assert _round_half_up(3.7) == 4


# =============================================================================
# _wrap_debug_info
# =============================================================================


class TestWrapDebugInfo:
    def test_none_returns_none(self):
        assert _wrap_debug_info(None) is None

    def test_returns_immutable_mapping(self):
        wrapped = _wrap_debug_info({"a": 1, "b": 2})
        assert wrapped is not None
        assert wrapped == {"a": 1, "b": 2}
        assert isinstance(wrapped, MappingProxyType)
        with pytest.raises(TypeError):
            wrapped["c"] = 3  # type: ignore[index]

    def test_copies_to_prevent_external_mutation(self):
        """The function must create a copy before wrapping, so that
        subsequent mutations of the original dict don't leak through
        the MappingProxyType."""
        original = {"a": 1}
        wrapped = _wrap_debug_info(original)
        assert wrapped is not None
        original["a"] = 999
        original["b"] = 2
        # The wrapped copy should still reflect the values at wrap time
        assert wrapped == {"a": 1}


# =============================================================================
# _compute_volatility
# =============================================================================


class TestComputeVolatility:
    def test_single_value_returns_none(self):
        assert _compute_volatility([1.0]) is None

    def test_empty_returns_none(self):
        assert _compute_volatility([]) is None

    def test_constant_values_returns_zero(self):
        assert _compute_volatility([5.0, 5.0, 5.0, 5.0]) == 0.0

    def test_population_stdev(self):
        """Should use /n (population), not /n-1 (sample)."""
        # [2, 4, 4, 4, 5, 5, 7, 9] -> population stdev = 2.0
        values = [2, 4, 4, 4, 5, 5, 7, 9]
        result = _compute_volatility([float(v) for v in values])
        assert result == pytest.approx(2.0)

    def test_two_values(self):
        # [0, 10] -> mean=5, variance=(25+25)/2=25, sqrt=5
        assert _compute_volatility([0.0, 10.0]) == pytest.approx(5.0)


# =============================================================================
# _compute_total
# =============================================================================


class TestComputeTotal:
    def test_default_weights(self):
        cfg = DEFAULT_CONFIG
        total = _compute_total(0.5, 0.8, cfg)
        weight_sum = cfg.needs_match_weight + cfg.stability_weight
        expected = 0.5 * (cfg.needs_match_weight / weight_sum) + 0.8 * (cfg.stability_weight / weight_sum)
        assert total == pytest.approx(expected)

    def test_zero_weights_returns_zero(self):
        cfg = SuitabilityConfig(needs_match_weight=0.0, stability_weight=0.0)
        assert _compute_total(1.0, 1.0, cfg) == 0.0

    def test_normalized_to_one(self):
        """Even when weights are not normalized to sum=1, the total is
        normalized via the weight_sum division."""
        cfg = SuitabilityConfig(needs_match_weight=2.0, stability_weight=3.0)
        total = _compute_total(0.5, 0.8, cfg)
        # Same as default: 0.5*0.4 + 0.8*0.6 = 0.68
        assert total == pytest.approx(0.68)


# =============================================================================
# compute_batch_percentiles
# =============================================================================


def _make_score(total: float) -> SuitabilityScore:
    return SuitabilityScore(
        needs_match=total,
        stability=total,
        total=total,
        percentile=None,
        debug_info=None,
    )


class TestComputeBatchPercentiles:
    def test_empty_list(self):
        assert compute_batch_percentiles([]) == []

    def test_single_item_gets_100(self):
        """A single game should always rank at the 100th percentile."""
        result = compute_batch_percentiles([_make_score(0.5)])
        assert len(result) == 1
        assert result[0].percentile == 100

    def test_higher_score_always_gets_higher_percentile(self):
        scores = [_make_score(0.3), _make_score(0.5), _make_score(0.7)]
        result = compute_batch_percentiles(scores)
        percentiles = [s.percentile for s in result]
        # Match each percentile to its original total
        totals_with_pct = list(zip([s.total for s in scores], percentiles, strict=False))
        # Higher totals should have higher or equal percentiles
        for i in range(len(totals_with_pct)):
            for j in range(len(totals_with_pct)):
                if totals_with_pct[i][0] > totals_with_pct[j][0]:
                    assert percentiles[i] >= percentiles[j]

    def test_top_item_always_gets_100(self):
        scores = [_make_score(0.3), _make_score(0.5), _make_score(0.7)]
        result = compute_batch_percentiles(scores)
        max_idx = max(range(3), key=lambda i: scores[i].total)
        assert result[max_idx].percentile == 100

    def test_tied_top_items_all_get_100(self):
        """ECDF-style: top-tied items all get 100."""
        scores = [_make_score(0.5), _make_score(0.5), _make_score(0.3)]
        result = compute_batch_percentiles(scores)
        # Both 0.5 entries should get 100
        assert result[0].percentile == 100
        assert result[1].percentile == 100

    def test_preserves_other_fields(self):
        """percentile is the only field changed; needs_match/stability/total
        must be preserved."""
        original = SuitabilityScore(
            needs_match=0.3,
            stability=0.4,
            total=0.5,
            percentile=None,
            debug_info=None,
        )
        result = compute_batch_percentiles([original])
        assert result[0].needs_match == 0.3
        assert result[0].stability == 0.4
        assert result[0].total == 0.5

    def test_ecdf_formula_for_two_items(self):
        """Two items, totals [0.4, 0.6]:
        - For 0.4: count(<=0.4)=1, pct = round_half_up(1/2 * 100) = 50
        - For 0.6: count(<=0.6)=2, pct = round_half_up(2/2 * 100) = 100
        """
        scores = [_make_score(0.4), _make_score(0.6)]
        result = compute_batch_percentiles(scores)
        assert result[0].percentile == 50
        assert result[1].percentile == 100
