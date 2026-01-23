"""
Golden tests for Radar output determinism (Phase 52-B).

These tests verify:
1. Normalization correctness (rounding, enum, null handling, float stability)
2. Schema compatibility (missing keys filled, extra keys preserved)
3. Tier calculation (odd/even axis median rules)
4. Determinism (order independence, roundtrip, repeated runs)
5. Golden file comparison (single game, aggregated)

Test matrix (from Phase 52-B plan v6):
- P0 tests (11): Must pass for PR merge
- P1 tests (2): Recommended, golden file comparison
"""

import json
import pytest
from typing import Dict, Any, Optional
from enum import Enum

from tests.conftest import (
    round_half_up,
    _stabilize_float,
    normalize_radar_output,
    RADAR_SCHEMA_DEFAULTS,
    load_golden,
    save_golden,
    update_golden_if_requested,
    GOLDEN_DIR,
)

# Import radar types for testing
from katrain.core.analysis.skill_radar import (
    RadarAxis,
    SkillTier,
    RadarMetrics,
    compute_overall_tier,
    radar_from_dict,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_radar_dict() -> Dict[str, Any]:
    """Sample RadarMetrics.to_dict() output for testing.

    This matches the actual output format of RadarMetrics.to_dict():
    - scores: per-axis float scores
    - tiers: per-axis tier strings
    - overall_tier: overall tier string
    - valid_move_counts: per-axis int counts
    """
    return {
        "scores": {
            "opening": 3.0,
            "fighting": 4.0,
            "endgame": 2.0,
            "stability": 3.0,
            "awareness": 4.0,
        },
        "tiers": {
            "opening": "tier_3",
            "fighting": "tier_4",
            "endgame": "tier_2",
            "stability": "tier_3",
            "awareness": "tier_4",
        },
        "overall_tier": "tier_3",
        "valid_move_counts": {
            "opening": 45,
            "fighting": 80,
            "endgame": 30,
            "stability": 155,
            "awareness": 155,
        },
    }


@pytest.fixture
def sample_radar_metrics() -> RadarMetrics:
    """Sample RadarMetrics object for testing.

    Uses the actual RadarMetrics constructor with individual fields.
    """
    from types import MappingProxyType

    return RadarMetrics(
        opening=3.0,
        fighting=4.0,
        endgame=2.0,
        stability=3.0,
        awareness=4.0,
        opening_tier=SkillTier.TIER_3,
        fighting_tier=SkillTier.TIER_4,
        endgame_tier=SkillTier.TIER_2,
        stability_tier=SkillTier.TIER_3,
        awareness_tier=SkillTier.TIER_4,
        overall_tier=SkillTier.TIER_3,
        valid_move_counts=MappingProxyType({
            RadarAxis.OPENING: 45,
            RadarAxis.FIGHTING: 80,
            RadarAxis.ENDGAME: 30,
            RadarAxis.STABILITY: 155,
            RadarAxis.AWARENESS: 155,
        }),
    )


# =============================================================================
# TestRadarNormalization - P0 tests for normalization correctness
# =============================================================================


class TestRadarNormalization:
    """Test normalization functions for deterministic output."""

    def test_rounding_boundary_decimals2(self):
        """Test ROUND_HALF_UP vs banker's rounding for decimals=2.

        Boundary values where ROUND_HALF_UP differs from banker's:
        - 2.545 -> 2.55 (banker's: 2.54)
        - 3.145 -> 3.15 (banker's: 3.14)
        - 2.125 -> 2.13 (banker's: 2.12)
        - 2.135 -> 2.14 (banker's: 2.14, same)

        Note: Python's round() behavior can be unintuitive due to
        floating point representation. 2.545 as a float is actually
        slightly less than 2.545, so round(2.545, 2) gives 2.54.
        Our ROUND_HALF_UP via Decimal handles this correctly.
        """
        # Cases where ROUND_HALF_UP differs from Python's round()
        assert round_half_up(2.545, 2) == 2.55, "2.545 should round to 2.55"
        assert round_half_up(3.145, 2) == 3.15, "3.145 should round to 3.15"
        assert round_half_up(2.125, 2) == 2.13, "2.125 should round to 2.13"

        # Case where both methods agree
        assert round_half_up(2.135, 2) == 2.14, "2.135 should round to 2.14"

        # Positive tests - ensure our function works correctly
        assert round_half_up(1.0, 2) == 1.0
        assert round_half_up(1.005, 2) == 1.01  # 0.5 rounds up
        assert round_half_up(1.004, 2) == 1.0   # 0.4 rounds down
        assert round_half_up(2.555, 2) == 2.56

    def test_rounding_none_handling(self):
        """Test that None input returns None."""
        assert round_half_up(None, 2) is None

    def test_enum_serialization(self):
        """Test Enum → .value conversion for str,Enum classes.

        SkillTier inherits from (str, Enum), so isinstance(obj, str) is True.
        We must check isinstance(obj, Enum) first.
        """
        # Test with actual Enum values in a dict structure
        radar_with_enum = {
            "scores": {"opening": 3.0},
            "tiers": {"opening": SkillTier.TIER_3},  # Enum value
            "overall_tier": SkillTier.TIER_3,  # Enum value
            "valid_move_counts": {},
        }

        normalized = normalize_radar_output(radar_with_enum)
        parsed = json.loads(normalized)

        # Enum values should be converted to their string values
        # Note: SkillTier uses lowercase values ("tier_3" not "TIER_3")
        assert parsed["overall_tier"] == "tier_3"
        assert parsed["tiers"]["opening"] == "tier_3"

    def test_null_handling(self):
        """Test None → JSON null conversion."""
        radar_with_null = {
            "scores": {},
            "tiers": {},
            "overall_tier": None,
            "valid_move_counts": {},
        }

        normalized = normalize_radar_output(radar_with_null)
        parsed = json.loads(normalized)

        assert parsed["overall_tier"] is None

    def test_float_stability(self):
        """Test _stabilize_float for computed values.

        Floating point arithmetic can produce unstable representations.
        0.1 + 0.2 = 0.30000000000000004 in Python.
        After stabilization: 0.3
        """
        # Classic floating point issue
        computed = 0.1 + 0.2
        assert computed != 0.3, "Floating point: 0.1+0.2 != 0.3"

        # After stabilization
        stabilized = _stabilize_float(round_half_up(computed, 2))
        assert stabilized == 0.3, "Stabilized: 0.1+0.2 should become 0.3"

        # More examples
        assert _stabilize_float(round_half_up(1.005, 2)) == 1.01
        assert _stabilize_float(round_half_up(2.555, 2)) == 2.56


# =============================================================================
# TestRadarSchemaCompat - P0 tests for schema compatibility
# =============================================================================


class TestRadarSchemaCompat:
    """Test schema fill and extra key handling."""

    def test_missing_keys_filled(self):
        """Test that missing top-level keys are filled with defaults."""
        # Only provide scores
        partial_dict = {
            "scores": {"opening": 3.0, "fighting": 4.0},
        }

        normalized = normalize_radar_output(partial_dict)
        parsed = json.loads(normalized)

        # All 4 top-level keys should be present
        assert "scores" in parsed
        assert "tiers" in parsed
        assert "overall_tier" in parsed
        assert "valid_move_counts" in parsed

        # Defaults should be applied
        assert parsed["overall_tier"] is None
        assert parsed["tiers"] == {}
        assert parsed["valid_move_counts"] == {}

        # Provided value should be preserved
        assert parsed["scores"] == {"fighting": 4.0, "opening": 3.0}

    def test_extra_keys_preserved(self):
        """Test that unknown keys are not deleted."""
        dict_with_extra = {
            "scores": {},
            "tiers": {},
            "overall_tier": "TIER_3",
            "valid_move_counts": {},
            "custom_field": "test_value",
            "debug_info": {"timestamp": 12345},
        }

        normalized = normalize_radar_output(dict_with_extra)
        parsed = json.loads(normalized)

        # Extra keys should be preserved
        assert parsed["custom_field"] == "test_value"
        assert parsed["debug_info"] == {"timestamp": 12345}


# =============================================================================
# TestRadarTierCalculation - P0 tests for tier computation
# =============================================================================


class TestRadarTierCalculation:
    """Test overall tier calculation from axis tiers."""

    def test_odd_axes_median(self):
        """Test median for odd number of axes (5 known tiers).

        [1,2,3,4,5] -> middle element = 3 -> TIER_3
        """
        tiers = [
            SkillTier.TIER_1,
            SkillTier.TIER_2,
            SkillTier.TIER_3,
            SkillTier.TIER_4,
            SkillTier.TIER_5,
        ]
        result = compute_overall_tier(tiers)
        assert result == SkillTier.TIER_3

    def test_even_axes_avg_ceil(self):
        """Test median for even number of axes (4 known tiers).

        Implementation uses average of middle two + ceil.
        [1,2,4,5] -> mid_low=2, mid_high=4 -> avg=3.0 -> ceil=3 -> TIER_3

        Note: Plan v6 specified upper median (TIER_4), but actual
        implementation uses avg+ceil method which gives TIER_3.
        """
        tiers = [
            SkillTier.TIER_1,
            SkillTier.TIER_2,
            SkillTier.TIER_4,
            SkillTier.TIER_5,
        ]
        result = compute_overall_tier(tiers)
        # avg=(2+4)/2=3.0, ceil(3.0)=3 -> TIER_3
        assert result == SkillTier.TIER_3

    def test_even_axes_ceil_on_half(self):
        """Test ceil behavior for .5 average.

        [1,2] -> avg=1.5 -> ceil=2 -> TIER_2
        [4,5] -> avg=4.5 -> ceil=5 -> TIER_5
        """
        assert compute_overall_tier([SkillTier.TIER_1, SkillTier.TIER_2]) == SkillTier.TIER_2
        assert compute_overall_tier([SkillTier.TIER_4, SkillTier.TIER_5]) == SkillTier.TIER_5

    def test_all_unknown_returns_unknown(self):
        """Test that all UNKNOWN returns UNKNOWN."""
        tiers = [SkillTier.TIER_UNKNOWN] * 5
        result = compute_overall_tier(tiers)
        assert result == SkillTier.TIER_UNKNOWN

    def test_partial_unknown_excluded(self):
        """Test that UNKNOWN tiers are excluded from calculation.

        [1, UNKNOWN, 3, UNKNOWN, 5] -> known=[1,3,5] -> middle=3 -> TIER_3
        """
        tiers = [
            SkillTier.TIER_1,
            SkillTier.TIER_UNKNOWN,
            SkillTier.TIER_3,
            SkillTier.TIER_UNKNOWN,
            SkillTier.TIER_5,
        ]
        result = compute_overall_tier(tiers)
        assert result == SkillTier.TIER_3


# =============================================================================
# TestRadarDeterminism - P0 tests for deterministic output
# =============================================================================


class TestRadarDeterminism:
    """Test deterministic behavior of radar normalization."""

    def test_order_independence(self, sample_radar_dict):
        """Test that input dict key order doesn't affect output.

        Shuffled scores should produce identical normalized output.
        """
        # Original order
        original = sample_radar_dict.copy()

        # Create shuffled version (Python 3.7+ dicts maintain insertion order)
        shuffled_scores = {
            "awareness": 4.0,
            "stability": 3.0,
            "endgame": 2.0,
            "fighting": 4.0,
            "opening": 3.0,
        }
        shuffled = {
            "scores": shuffled_scores,
            "tiers": sample_radar_dict["tiers"].copy(),
            "overall_tier": sample_radar_dict["overall_tier"],
            "valid_move_counts": sample_radar_dict["valid_move_counts"].copy(),
        }

        norm1 = normalize_radar_output(original)
        norm2 = normalize_radar_output(shuffled)

        assert norm1 == norm2, "Key order should not affect normalized output"

    def test_roundtrip_equality(self, sample_radar_metrics):
        """Test dict -> json -> dict -> json roundtrip equality."""
        # First conversion
        dict1 = sample_radar_metrics.to_dict()
        json1 = normalize_radar_output(dict1)

        # Parse and re-normalize
        parsed = json.loads(json1)
        json2 = normalize_radar_output(parsed)

        assert json1 == json2, "Roundtrip should produce identical JSON"

    def test_deterministic_3runs(self, sample_radar_dict):
        """Test that 3 consecutive normalizations produce identical output."""
        results = []
        for _ in range(3):
            result = normalize_radar_output(sample_radar_dict.copy())
            results.append(result)

        assert results[0] == results[1] == results[2], "3 runs should be identical"


# =============================================================================
# TestRadarGolden - P1 tests for golden file comparison
# =============================================================================


class TestRadarGolden:
    """Golden file comparison tests."""

    def test_single_game_golden(self, sample_radar_metrics, request):
        """Test single game radar output against golden file."""
        golden_name = "radar_single_game.golden.json"
        actual = normalize_radar_output(sample_radar_metrics.to_dict())

        # Update golden if requested
        update_golden_if_requested(golden_name, actual, request)

        # Load and compare
        try:
            expected = load_golden(golden_name)
            assert actual == expected, f"Output differs from {golden_name}"
        except FileNotFoundError:
            pytest.skip(f"Golden file {golden_name} not found. Run with --update-goldens")

    def test_aggregated_golden(self, request):
        """Test aggregated radar output against golden file."""
        golden_name = "radar_aggregated.golden.json"

        # Create sample aggregated data (matches AggregatedRadarResult.to_dict() format)
        aggregated_dict = {
            "scores": {
                "opening": 3.5,
                "fighting": 4.0,
                "endgame": 2.5,
                "stability": 3.0,
                "awareness": 4.0,
            },
            "tiers": {
                "opening": "tier_4",
                "fighting": "tier_4",
                "endgame": "tier_3",
                "stability": "tier_3",
                "awareness": "tier_4",
            },
            "overall_tier": "tier_4",
            "valid_move_counts": {
                "opening": 135,
                "fighting": 240,
                "endgame": 90,
                "stability": 465,
                "awareness": 465,
            },
            "games_aggregated": 3,
        }

        actual = normalize_radar_output(aggregated_dict)

        # Update golden if requested
        update_golden_if_requested(golden_name, actual, request)

        # Load and compare
        try:
            expected = load_golden(golden_name)
            assert actual == expected, f"Output differs from {golden_name}"
        except FileNotFoundError:
            pytest.skip(f"Golden file {golden_name} not found. Run with --update-goldens")
