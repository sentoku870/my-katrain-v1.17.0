"""Tests for Phase 49: Radar Aggregation Functions.

Test coverage:
- aggregate_radar() core functionality
- Per-axis handling (UNKNOWN filtering)
- Overall tier median calculation
- radar_from_dict() roundtrip and robustness
- round_score() helper
- AggregatedRadarResult serialization

Test priority:
- P0: Critical - must pass for module to be usable
- P1: Important - covers edge cases and integration
- P2: Nice to have - comprehensive coverage
"""

from types import MappingProxyType, SimpleNamespace

import pytest

from katrain.core.analysis.models import MistakeCategory, PositionDifficulty
from katrain.core.analysis.skill_radar import (
    # Enums
    RadarAxis,
    SkillTier,
    # Dataclasses
    RadarMetrics,
    AggregatedRadarResult,
    # Constants
    TIER_TO_INT,
    INT_TO_TIER,
    MIN_VALID_AXES_FOR_OVERALL,
    MIN_MOVES_FOR_RADAR,
    REQUIRED_RADAR_DICT_KEYS,
    OPTIONAL_RADAR_DICT_KEYS,
    NEUTRAL_DISPLAY_SCORE,
    NEUTRAL_TIER,
    # Functions
    compute_overall_tier,
    compute_radar_from_moves,
    round_score,
    radar_from_dict,
    aggregate_radar,
)


# =============================================================================
# Test Fixtures
# =============================================================================


def make_radar_metrics(
    opening: float = 3.0,
    fighting: float = 3.0,
    endgame: float = 3.0,
    stability: float = 3.0,
    awareness: float = 3.0,
    opening_tier: SkillTier = SkillTier.TIER_3,
    fighting_tier: SkillTier = SkillTier.TIER_3,
    endgame_tier: SkillTier = SkillTier.TIER_3,
    stability_tier: SkillTier = SkillTier.TIER_3,
    awareness_tier: SkillTier = SkillTier.TIER_3,
    overall_tier: SkillTier = SkillTier.TIER_3,
    valid_move_counts: dict | None = None,
) -> RadarMetrics:
    """Create a RadarMetrics instance for testing."""
    if valid_move_counts is None:
        valid_move_counts = {
            RadarAxis.OPENING: 50,
            RadarAxis.FIGHTING: 20,
            RadarAxis.ENDGAME: 30,
            RadarAxis.STABILITY: 100,
            RadarAxis.AWARENESS: 100,
        }
    return RadarMetrics(
        opening=opening,
        fighting=fighting,
        endgame=endgame,
        stability=stability,
        awareness=awareness,
        opening_tier=opening_tier,
        fighting_tier=fighting_tier,
        endgame_tier=endgame_tier,
        stability_tier=stability_tier,
        awareness_tier=awareness_tier,
        overall_tier=overall_tier,
        valid_move_counts=MappingProxyType(valid_move_counts),
    )


def make_move_stub(
    move_number: int = 1,
    player: str = "B",
    points_lost: float | None = 0.0,
    mistake_category: MistakeCategory = MistakeCategory.GOOD,
    position_difficulty: PositionDifficulty | None = PositionDifficulty.NORMAL,
    winrate_before: float | None = 0.5,
) -> SimpleNamespace:
    """Create a lightweight MoveEval stub for testing."""
    return SimpleNamespace(
        move_number=move_number,
        player=player,
        points_lost=points_lost,
        mistake_category=mistake_category,
        position_difficulty=position_difficulty,
        winrate_before=winrate_before,
    )


# =============================================================================
# P0: Aggregation Core Tests
# =============================================================================


class TestAggregateRadarCore:
    """P0: Test aggregate_radar() core functionality."""

    def test_aggregate_empty_list_returns_none(self):
        """Empty radar list returns None."""
        result = aggregate_radar([])
        assert result is None

    def test_aggregate_single_game(self):
        """Single RadarMetrics returns same values."""
        radar = make_radar_metrics(
            opening=4.0,
            fighting=3.0,
            endgame=2.0,
            stability=5.0,
            awareness=4.0,
            opening_tier=SkillTier.TIER_4,
            fighting_tier=SkillTier.TIER_3,
            endgame_tier=SkillTier.TIER_2,
            stability_tier=SkillTier.TIER_5,
            awareness_tier=SkillTier.TIER_4,
        )

        result = aggregate_radar([radar])

        assert result is not None
        assert result.opening == 4.0
        assert result.fighting == 3.0
        assert result.endgame == 2.0
        assert result.stability == 5.0
        assert result.awareness == 4.0
        assert result.games_aggregated == 1

    def test_aggregate_two_games(self):
        """Simple average of 2 games."""
        radar1 = make_radar_metrics(opening=4.0, opening_tier=SkillTier.TIER_4)
        radar2 = make_radar_metrics(opening=2.0, opening_tier=SkillTier.TIER_2)

        result = aggregate_radar([radar1, radar2])

        assert result is not None
        # Average of 4.0 and 2.0 = 3.0
        assert result.opening == 3.0
        assert result.games_aggregated == 2

    def test_aggregate_three_games(self):
        """Simple average of 3 games."""
        radar1 = make_radar_metrics(opening=5.0, opening_tier=SkillTier.TIER_5)
        radar2 = make_radar_metrics(opening=4.0, opening_tier=SkillTier.TIER_4)
        radar3 = make_radar_metrics(opening=3.0, opening_tier=SkillTier.TIER_3)

        result = aggregate_radar([radar1, radar2, radar3])

        assert result is not None
        # Average of 5.0, 4.0, 3.0 = 4.0
        assert result.opening == 4.0
        assert result.games_aggregated == 3

    def test_aggregate_games_aggregated_count(self):
        """Metadata reflects input count."""
        radars = [make_radar_metrics() for _ in range(5)]

        result = aggregate_radar(radars)

        assert result is not None
        assert result.games_aggregated == 5


# =============================================================================
# P0: Axis-Level Handling Tests
# =============================================================================


class TestAggregateAxisHandling:
    """P0: Test per-axis handling with UNKNOWN filtering."""

    def test_aggregate_partial_axis_unknown(self):
        """Game1 has valid opening, Game2 has UNKNOWN -> only Game1 contributes."""
        radar1 = make_radar_metrics(opening=4.0, opening_tier=SkillTier.TIER_4)
        radar2 = make_radar_metrics(
            opening=NEUTRAL_DISPLAY_SCORE, opening_tier=SkillTier.TIER_UNKNOWN
        )

        result = aggregate_radar([radar1, radar2])

        assert result is not None
        # Only Game1's opening (4.0) contributes
        assert result.opening == 4.0
        assert result.opening_tier == SkillTier.TIER_4

    def test_aggregate_axis_all_unknown_returns_none(self):
        """All games have UNKNOWN for opening -> opening=None."""
        radar1 = make_radar_metrics(
            opening=NEUTRAL_DISPLAY_SCORE, opening_tier=SkillTier.TIER_UNKNOWN
        )
        radar2 = make_radar_metrics(
            opening=NEUTRAL_DISPLAY_SCORE, opening_tier=SkillTier.TIER_UNKNOWN
        )

        result = aggregate_radar([radar1, radar2])

        assert result is not None
        assert result.opening is None
        assert result.opening_tier == SkillTier.TIER_UNKNOWN

    def test_aggregate_valid_move_counts_filtered(self):
        """Counts only from games where axis tier != UNKNOWN."""
        radar1 = make_radar_metrics(
            opening=4.0,
            opening_tier=SkillTier.TIER_4,
            valid_move_counts={
                RadarAxis.OPENING: 50,
                RadarAxis.FIGHTING: 20,
                RadarAxis.ENDGAME: 30,
                RadarAxis.STABILITY: 100,
                RadarAxis.AWARENESS: 100,
            },
        )
        radar2 = make_radar_metrics(
            opening=NEUTRAL_DISPLAY_SCORE,
            opening_tier=SkillTier.TIER_UNKNOWN,
            valid_move_counts={
                RadarAxis.OPENING: 0,  # UNKNOWN axis, should not count
                RadarAxis.FIGHTING: 25,
                RadarAxis.ENDGAME: 35,
                RadarAxis.STABILITY: 90,
                RadarAxis.AWARENESS: 90,
            },
        )

        result = aggregate_radar([radar1, radar2])

        assert result is not None
        # Opening: only radar1 contributes (radar2 has UNKNOWN)
        assert result.valid_move_counts[RadarAxis.OPENING] == 50
        # Fighting: both contribute
        assert result.valid_move_counts[RadarAxis.FIGHTING] == 45  # 20 + 25
        # Endgame: both contribute
        assert result.valid_move_counts[RadarAxis.ENDGAME] == 65  # 30 + 35


# =============================================================================
# P0: Overall Tier Median Tests
# =============================================================================


class TestAggregateOverallTier:
    """P0: Test overall tier computation (reuses compute_overall_tier)."""

    def test_aggregate_overall_tier_needs_3_valid(self):
        """2 valid axes -> overall_tier=TIER_UNKNOWN."""
        radar = make_radar_metrics(
            opening=4.0,
            fighting=4.0,
            endgame=NEUTRAL_DISPLAY_SCORE,
            stability=NEUTRAL_DISPLAY_SCORE,
            awareness=NEUTRAL_DISPLAY_SCORE,
            opening_tier=SkillTier.TIER_4,
            fighting_tier=SkillTier.TIER_4,
            endgame_tier=SkillTier.TIER_UNKNOWN,
            stability_tier=SkillTier.TIER_UNKNOWN,
            awareness_tier=SkillTier.TIER_UNKNOWN,
        )

        result = aggregate_radar([radar])

        assert result is not None
        # Only 2 valid axes, need >= 3
        assert result.overall_tier == SkillTier.TIER_UNKNOWN

    def test_aggregate_overall_tier_median_3_axes(self):
        """3 valid axes -> median = middle value."""
        radar = make_radar_metrics(
            opening=2.0,  # TIER_2
            fighting=3.0,  # TIER_3
            endgame=4.0,  # TIER_4
            stability=NEUTRAL_DISPLAY_SCORE,
            awareness=NEUTRAL_DISPLAY_SCORE,
            opening_tier=SkillTier.TIER_2,
            fighting_tier=SkillTier.TIER_3,
            endgame_tier=SkillTier.TIER_4,
            stability_tier=SkillTier.TIER_UNKNOWN,
            awareness_tier=SkillTier.TIER_UNKNOWN,
        )

        result = aggregate_radar([radar])

        assert result is not None
        # Median of [2, 3, 4] = 3 -> TIER_3
        assert result.overall_tier == SkillTier.TIER_3

    def test_aggregate_overall_tier_median_4_axes_ceil(self):
        """4 valid axes -> avg of middle two, ceil for ties."""
        radar = make_radar_metrics(
            opening=2.0,  # TIER_2
            fighting=3.0,  # TIER_3
            endgame=4.0,  # TIER_4
            stability=5.0,  # TIER_5
            awareness=NEUTRAL_DISPLAY_SCORE,
            opening_tier=SkillTier.TIER_2,
            fighting_tier=SkillTier.TIER_3,
            endgame_tier=SkillTier.TIER_4,
            stability_tier=SkillTier.TIER_5,
            awareness_tier=SkillTier.TIER_UNKNOWN,
        )

        result = aggregate_radar([radar])

        assert result is not None
        # Sorted: [2, 3, 4, 5], middle two = 3, 4
        # Average = 3.5 -> ceil = 4 -> TIER_4
        assert result.overall_tier == SkillTier.TIER_4

    def test_aggregate_overall_tier_median_5_axes(self):
        """5 valid axes -> median = middle value."""
        radar = make_radar_metrics(
            opening=1.0,  # TIER_1
            fighting=2.0,  # TIER_2
            endgame=3.0,  # TIER_3
            stability=4.0,  # TIER_4
            awareness=5.0,  # TIER_5
            opening_tier=SkillTier.TIER_1,
            fighting_tier=SkillTier.TIER_2,
            endgame_tier=SkillTier.TIER_3,
            stability_tier=SkillTier.TIER_4,
            awareness_tier=SkillTier.TIER_5,
        )

        result = aggregate_radar([radar])

        assert result is not None
        # Sorted: [1, 2, 3, 4, 5], middle = 3 -> TIER_3
        assert result.overall_tier == SkillTier.TIER_3

    def test_aggregate_overall_tier_matches_phase48(self):
        """Verify same result as calling compute_overall_tier() directly."""
        radar = make_radar_metrics(
            opening_tier=SkillTier.TIER_2,
            fighting_tier=SkillTier.TIER_4,
            endgame_tier=SkillTier.TIER_3,
            stability_tier=SkillTier.TIER_5,
            awareness_tier=SkillTier.TIER_1,
        )

        result = aggregate_radar([radar])

        # Expected from compute_overall_tier
        expected = compute_overall_tier([
            SkillTier.TIER_2,
            SkillTier.TIER_4,
            SkillTier.TIER_3,
            SkillTier.TIER_5,
            SkillTier.TIER_1,
        ])

        assert result is not None
        assert result.overall_tier == expected


# =============================================================================
# P0: radar_from_dict() Robustness Tests
# =============================================================================


class TestRadarFromDict:
    """P0: Test radar_from_dict() roundtrip and error handling."""

    def test_radar_from_dict_roundtrip_tiers_exact(self):
        """to_dict -> from_dict -> tiers match exactly."""
        original = make_radar_metrics(
            opening_tier=SkillTier.TIER_4,
            fighting_tier=SkillTier.TIER_3,
            endgame_tier=SkillTier.TIER_2,
            stability_tier=SkillTier.TIER_5,
            awareness_tier=SkillTier.TIER_1,
            overall_tier=SkillTier.TIER_3,
        )

        d = original.to_dict()
        reconstructed = radar_from_dict(d)

        assert reconstructed is not None
        assert reconstructed.opening_tier == original.opening_tier
        assert reconstructed.fighting_tier == original.fighting_tier
        assert reconstructed.endgame_tier == original.endgame_tier
        assert reconstructed.stability_tier == original.stability_tier
        assert reconstructed.awareness_tier == original.awareness_tier
        assert reconstructed.overall_tier == original.overall_tier

    def test_radar_from_dict_roundtrip_scores_approx(self):
        """to_dict -> from_dict -> scores match via pytest.approx."""
        original = make_radar_metrics(
            opening=4.2,
            fighting=3.3,
            endgame=2.7,
            stability=4.8,
            awareness=1.5,
        )

        d = original.to_dict()
        reconstructed = radar_from_dict(d)

        assert reconstructed is not None
        assert reconstructed.opening == pytest.approx(original.opening, rel=0.01)
        assert reconstructed.fighting == pytest.approx(original.fighting, rel=0.01)
        assert reconstructed.endgame == pytest.approx(original.endgame, rel=0.01)
        assert reconstructed.stability == pytest.approx(original.stability, rel=0.01)
        assert reconstructed.awareness == pytest.approx(original.awareness, rel=0.01)

    def test_radar_from_dict_none_input(self):
        """None input -> None output."""
        result = radar_from_dict(None)
        assert result is None

    def test_radar_from_dict_empty_dict(self):
        """{} -> None."""
        result = radar_from_dict({})
        assert result is None

    def test_radar_from_dict_missing_required_key(self):
        """Missing 'scores' -> None, logged."""
        d = {
            "tiers": {
                "opening": "tier_3",
                "fighting": "tier_3",
                "endgame": "tier_3",
                "stability": "tier_3",
                "awareness": "tier_3",
            },
            "overall_tier": "tier_3",
        }
        result = radar_from_dict(d)
        assert result is None

    def test_radar_from_dict_missing_optional_key(self):
        """Missing 'valid_move_counts' -> uses empty default."""
        d = {
            "scores": {
                "opening": 3.0,
                "fighting": 3.0,
                "endgame": 3.0,
                "stability": 3.0,
                "awareness": 3.0,
            },
            "tiers": {
                "opening": "tier_3",
                "fighting": "tier_3",
                "endgame": "tier_3",
                "stability": "tier_3",
                "awareness": "tier_3",
            },
            "overall_tier": "tier_3",
        }
        result = radar_from_dict(d)
        assert result is not None
        # Defaults to 0 for all axes
        for axis in RadarAxis:
            assert result.valid_move_counts[axis] == 0

    def test_radar_from_dict_extra_keys_ignored(self):
        """Unknown keys don't break parsing."""
        original = make_radar_metrics()
        d = original.to_dict()
        d["extra_unknown_key"] = "some_value"
        d["another_key"] = 12345

        result = radar_from_dict(d)
        assert result is not None

    def test_radar_from_dict_malformed_nested(self):
        """Bad nested structure -> None, logged."""
        d = {
            "scores": "not_a_dict",  # Should be dict
            "tiers": {},
            "overall_tier": "tier_3",
        }
        result = radar_from_dict(d)
        assert result is None


# =============================================================================
# P1: Rounding Helper Tests
# =============================================================================


class TestRoundScore:
    """P1: Test round_score() helper function."""

    def test_round_score_none(self):
        """round_score(None) -> None."""
        assert round_score(None) is None

    def test_round_score_midpoint(self):
        """2.25 -> 2.3 (ROUND_HALF_UP, not banker's rounding)."""
        assert round_score(2.25) == 2.3

    def test_round_score_deterministic(self):
        """Same input always same output."""
        value = 3.456
        result1 = round_score(value)
        result2 = round_score(value)
        result3 = round_score(value)

        assert result1 == result2 == result3 == 3.5

    def test_round_score_various_values(self):
        """Test various rounding scenarios."""
        assert round_score(1.0) == 1.0
        assert round_score(1.04) == 1.0
        assert round_score(1.05) == 1.1  # ROUND_HALF_UP
        assert round_score(1.06) == 1.1
        assert round_score(2.35) == 2.4  # ROUND_HALF_UP
        assert round_score(4.99) == 5.0
        assert round_score(5.0) == 5.0


# =============================================================================
# P1: Serialization Tests
# =============================================================================


class TestAggregatedResultToDict:
    """P1: Test AggregatedRadarResult.to_dict() serialization."""

    def test_aggregated_result_to_dict_schema(self):
        """Output matches expected schema."""
        radar = make_radar_metrics()
        result = aggregate_radar([radar])

        assert result is not None
        d = result.to_dict()

        # Check top-level keys
        assert "axes" in d
        assert "games_aggregated" in d
        assert "overall_tier" in d
        assert "valid_move_counts" in d

        # Check axes structure
        axes = d["axes"]
        for axis_name in ["opening", "fighting", "endgame", "stability", "awareness"]:
            assert axis_name in axes
            assert "score" in axes[axis_name]
            assert "tier" in axes[axis_name]

    def test_aggregated_result_to_dict_null_scores(self):
        """None scores -> null in JSON."""
        radar1 = make_radar_metrics(
            opening=NEUTRAL_DISPLAY_SCORE,
            opening_tier=SkillTier.TIER_UNKNOWN,
        )
        radar2 = make_radar_metrics(
            opening=NEUTRAL_DISPLAY_SCORE,
            opening_tier=SkillTier.TIER_UNKNOWN,
        )

        result = aggregate_radar([radar1, radar2])
        assert result is not None
        d = result.to_dict()

        # opening should be None
        assert d["axes"]["opening"]["score"] is None
        assert d["axes"]["opening"]["tier"] == "unknown"

    def test_aggregated_result_frozen(self):
        """Cannot modify after creation."""
        radar = make_radar_metrics()
        result = aggregate_radar([radar])

        assert result is not None
        with pytest.raises(AttributeError):
            result.opening = 1.0  # type: ignore


class TestIsWeakAxis:
    """P1: Test AggregatedRadarResult.is_weak_axis() method."""

    def test_is_weak_axis_uses_raw_score(self):
        """2.45 raw is weak even if rounds to 2.5."""
        # Create a result with opening = 2.45 (weak, < 2.5)
        radar = make_radar_metrics(
            opening=2.45,  # Will round to 2.5 for display, but is weak
            opening_tier=SkillTier.TIER_2,
        )
        result = aggregate_radar([radar])

        assert result is not None
        assert result.is_weak_axis(RadarAxis.OPENING) is True

        # Verify it rounds to 2.5 for display
        assert round_score(result.opening) == 2.5

    def test_is_weak_axis_not_weak_at_2_5(self):
        """Exactly 2.5 is not weak."""
        radar = make_radar_metrics(opening=2.5, opening_tier=SkillTier.TIER_3)
        result = aggregate_radar([radar])

        assert result is not None
        assert result.is_weak_axis(RadarAxis.OPENING) is False

    def test_is_weak_axis_none_score_not_weak(self):
        """None score is not flagged as weak."""
        radar1 = make_radar_metrics(
            opening=NEUTRAL_DISPLAY_SCORE,
            opening_tier=SkillTier.TIER_UNKNOWN,
        )
        radar2 = make_radar_metrics(
            opening=NEUTRAL_DISPLAY_SCORE,
            opening_tier=SkillTier.TIER_UNKNOWN,
        )

        result = aggregate_radar([radar1, radar2])

        assert result is not None
        assert result.opening is None
        assert result.is_weak_axis(RadarAxis.OPENING) is False


# =============================================================================
# P2: Constants Tests
# =============================================================================


class TestPhase49Constants:
    """P2: Test Phase 49 constants."""

    def test_min_valid_axes_for_overall(self):
        """MIN_VALID_AXES_FOR_OVERALL is 3."""
        assert MIN_VALID_AXES_FOR_OVERALL == 3

    def test_min_moves_for_radar(self):
        """MIN_MOVES_FOR_RADAR is 10."""
        assert MIN_MOVES_FOR_RADAR == 10

    def test_required_radar_dict_keys(self):
        """Required keys are correct."""
        assert REQUIRED_RADAR_DICT_KEYS == frozenset(
            {"scores", "tiers", "overall_tier"}
        )

    def test_optional_radar_dict_keys(self):
        """Optional keys are correct."""
        assert OPTIONAL_RADAR_DICT_KEYS == frozenset({"valid_move_counts"})


# =============================================================================
# P2: Integration Tests
# =============================================================================


class TestAggregationIntegration:
    """P2: Integration tests for aggregation workflow."""

    def test_roundtrip_aggregate_single_game(self):
        """Full workflow: compute -> to_dict -> from_dict -> aggregate."""
        # Create moves that will produce a RadarMetrics
        moves = [
            make_move_stub(
                move_number=i,
                player="B",
                points_lost=0.5,
                mistake_category=MistakeCategory.GOOD,
                position_difficulty=PositionDifficulty.NORMAL,
                winrate_before=0.5,
            )
            for i in range(1, 101)
        ]

        # Compute radar from moves
        radar = compute_radar_from_moves(moves, player="B")

        # Serialize and deserialize
        d = radar.to_dict()
        reconstructed = radar_from_dict(d)

        assert reconstructed is not None

        # Aggregate single game
        result = aggregate_radar([reconstructed])

        assert result is not None
        assert result.games_aggregated == 1

    def test_mixed_valid_and_unknown_axes_aggregation(self):
        """Aggregate games with different axes being UNKNOWN."""
        # Game 1: Opening valid, Endgame UNKNOWN
        radar1 = make_radar_metrics(
            opening=4.0,
            endgame=NEUTRAL_DISPLAY_SCORE,
            opening_tier=SkillTier.TIER_4,
            endgame_tier=SkillTier.TIER_UNKNOWN,
        )

        # Game 2: Opening UNKNOWN, Endgame valid
        radar2 = make_radar_metrics(
            opening=NEUTRAL_DISPLAY_SCORE,
            endgame=2.0,
            opening_tier=SkillTier.TIER_UNKNOWN,
            endgame_tier=SkillTier.TIER_2,
        )

        result = aggregate_radar([radar1, radar2])

        assert result is not None
        # Opening: only radar1 contributes
        assert result.opening == 4.0
        # Endgame: only radar2 contributes
        assert result.endgame == 2.0

    def test_to_dict_output_is_json_serializable(self):
        """AggregatedRadarResult.to_dict() output can be JSON serialized."""
        import json

        radar = make_radar_metrics()
        result = aggregate_radar([radar])

        assert result is not None
        d = result.to_dict()

        # Should not raise
        json_str = json.dumps(d, ensure_ascii=False, sort_keys=True)
        assert json_str is not None

        # Should be parseable back
        parsed = json.loads(json_str)
        assert parsed == d
