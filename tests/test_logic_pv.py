"""Tests for katrain/core/analysis/logic_pv.py (Phase 167)."""
from __future__ import annotations

from katrain.core.analysis.logic_pv import filter_candidates_by_pv_complexity, get_pv_filter_config
from katrain.core.analysis.models import (
    DEFAULT_SKILL_PRESET,
    PV_FILTER_CONFIGS,
    SKILL_TO_PV_FILTER,
)


class TestGetPvFilterConfig:
    def test_off_returns_none(self):
        """OFF level returns None (no filter)."""
        assert get_pv_filter_config("off") is None

    def test_weak_returns_config(self):
        """weak level returns the weak PVFilterConfig."""
        config = get_pv_filter_config("weak")
        assert config == PV_FILTER_CONFIGS["weak"]
        assert config.max_candidates == 15
        assert config.max_points_lost == 4.0
        assert config.max_pv_length == 15

    def test_medium_returns_config(self):
        """medium level returns the medium PVFilterConfig."""
        config = get_pv_filter_config("medium")
        assert config == PV_FILTER_CONFIGS["medium"]
        assert config.max_candidates == 8
        assert config.max_points_lost == 2.0
        assert config.max_pv_length == 10

    def test_strong_returns_config(self):
        """strong level returns the strong PVFilterConfig."""
        config = get_pv_filter_config("strong")
        assert config == PV_FILTER_CONFIGS["strong"]
        assert config.max_candidates == 4
        assert config.max_points_lost == 1.0
        assert config.max_pv_length == 6

    def test_case_insensitive(self):
        """Level matching is case-insensitive."""
        assert get_pv_filter_config("WEAK") == PV_FILTER_CONFIGS["weak"]
        assert get_pv_filter_config("Medium") == PV_FILTER_CONFIGS["medium"]

    def test_unknown_level_returns_none(self):
        """Unknown level returns None (acts like off)."""
        assert get_pv_filter_config("nonexistent") is None

    def test_auto_with_relaxed_skill(self):
        """auto + relaxed skill maps to weak filter."""
        config = get_pv_filter_config("auto", skill_preset="relaxed")
        assert config == PV_FILTER_CONFIGS[SKILL_TO_PV_FILTER["relaxed"]]

    def test_auto_with_pro_skill(self):
        """auto + pro skill maps to strong filter."""
        config = get_pv_filter_config("auto", skill_preset="pro")
        assert config == PV_FILTER_CONFIGS[SKILL_TO_PV_FILTER["pro"]]

    def test_auto_with_unknown_skill_falls_back_to_medium(self):
        """auto + unknown skill_preset falls back to medium (default)."""
        config = get_pv_filter_config("auto", skill_preset="unknown_preset")
        assert config == PV_FILTER_CONFIGS["medium"]

    def test_auto_default_uses_default_skill_preset(self):
        """auto with default skill_preset uses DEFAULT_SKILL_PRESET."""
        config = get_pv_filter_config("auto")
        expected = PV_FILTER_CONFIGS[SKILL_TO_PV_FILTER.get(DEFAULT_SKILL_PRESET, "medium")]
        assert config == expected


def _cand(order: int, points_lost: float, pv: list[str]) -> dict:
    """Helper: build a candidate dict."""
    return {"order": order, "pointsLost": points_lost, "pv": pv}


class TestFilterCandidatesByPvComplexity:
    def test_empty_candidates(self):
        """Empty input returns empty list."""
        config = PV_FILTER_CONFIGS["medium"]
        assert filter_candidates_by_pv_complexity([], config) == []

    def test_no_filter_with_off_config(self):
        """OFF config (None) is not supported here; use weakest config instead."""
        # This test documents the assumption that config is always provided.
        # (get_pv_filter_config returns None for "off", so callers must
        # skip the filter call entirely in that case.)
        pass

    def test_best_move_preserved_at_top(self):
        """Best move (order=0) is always first regardless of filter."""
        config = PV_FILTER_CONFIGS["medium"]  # max_points_lost=2, max_pv=10
        candidates = [
            _cand(0, 0.0, ["D4"]),  # best move
            _cand(1, 100.0, ["D4", "Q5", "R6"]),  # high loss - filtered out
        ]
        result = filter_candidates_by_pv_complexity(candidates, config)
        assert len(result) == 1
        assert result[0]["order"] == 0

    def test_filters_by_points_lost(self):
        """Candidates with points_lost > max_points_lost are filtered out."""
        config = PV_FILTER_CONFIGS["strong"]  # max_points_lost=1.0
        candidates = [
            _cand(0, 0.0, ["D4"]),  # best
            _cand(1, 0.5, ["D4"]),  # OK
            _cand(2, 1.0, ["D4"]),  # borderline OK (<=)
            _cand(3, 1.5, ["D4"]),  # filtered
        ]
        result = filter_candidates_by_pv_complexity(candidates, config)
        orders = [c["order"] for c in result]
        assert orders == [0, 1, 2]  # best first, then 1, 2

    def test_filters_by_pv_length(self):
        """Candidates with pv length > max_pv_length are filtered out."""
        config = PV_FILTER_CONFIGS["strong"]  # max_pv_length=6
        candidates = [
            _cand(0, 0.0, ["D4"]),  # best
            _cand(1, 0.5, ["D4", "Q5"]),  # OK
            _cand(2, 0.5, ["D4", "Q5", "R6", "S7", "T8", "U9"]),  # OK (6)
            _cand(3, 0.5, ["D4", "Q5", "R6", "S7", "T8", "U9", "V10"]),  # filtered (7)
        ]
        result = filter_candidates_by_pv_complexity(candidates, config)
        orders = [c["order"] for c in result]
        assert orders == [0, 1, 2]

    def test_max_candidates_limit(self):
        """After filtering, only max_candidates non-best moves are kept."""
        config = PV_FILTER_CONFIGS["strong"]  # max_candidates=4
        candidates = [
            _cand(0, 0.0, ["D4"]),  # best
        ] + [_cand(i, 0.1, ["D4"]) for i in range(1, 11)]  # 10 more
        result = filter_candidates_by_pv_complexity(candidates, config)
        # Best + 4 others = 5 total
        assert len(result) == 5
        assert result[0]["order"] == 0  # best first
        orders = [c["order"] for c in result[1:]]
        assert orders == [1, 2, 3, 4]  # sorted by order, first 4

    def test_order_sorting(self):
        """Filtered results are sorted by order (ascending)."""
        config = PV_FILTER_CONFIGS["medium"]
        candidates = [
            _cand(0, 0.0, ["D4"]),  # best
            _cand(3, 0.5, ["D4"]),  # OK but out of order in input
            _cand(1, 0.5, ["D4"]),
            _cand(2, 0.5, ["D4"]),
        ]
        result = filter_candidates_by_pv_complexity(candidates, config)
        orders = [c["order"] for c in result]
        assert orders == [0, 1, 2, 3]

    def test_missing_pv_defaults_to_empty(self):
        """Missing pv field defaults to empty list (length 0, passes filter)."""
        config = PV_FILTER_CONFIGS["strong"]  # max_pv_length=6
        candidates = [
            _cand(0, 0.0, ["D4"]),  # best
            _cand(1, 0.5, {}),  # no pv field
        ]
        result = filter_candidates_by_pv_complexity(candidates, config)
        # The {} candidate has no pv, so pv_length=0 <= 6, passes
        # But "order" defaults to 999 if missing
        assert any(c.get("order") == 1 for c in result)

    def test_missing_points_lost_defaults_to_zero(self):
        """Missing pointsLost defaults to 0.0 (passes filter)."""
        config = PV_FILTER_CONFIGS["strong"]
        candidates = [
            _cand(0, 0.0, ["D4"]),  # best
            {"order": 1, "pv": ["D4"]},  # no pointsLost
        ]
        result = filter_candidates_by_pv_complexity(candidates, config)
        assert any(c.get("order") == 1 for c in result)

    def test_no_best_move(self):
        """Without a best move (no order=0), the filter still works."""
        config = PV_FILTER_CONFIGS["strong"]
        candidates = [
            _cand(1, 0.5, ["D4"]),
            _cand(2, 0.5, ["D4"]),
        ]
        result = filter_candidates_by_pv_complexity(candidates, config)
        assert len(result) == 2
        # No best move is prepended
        assert result[0]["order"] == 1
        assert result[1]["order"] == 2
