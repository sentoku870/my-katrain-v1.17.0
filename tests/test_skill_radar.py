"""Tests for 5-Axis Skill Radar and Tier Assessment Module (Phase 48).

Test priority:
- P0: Critical - must pass for module to be usable
- P1: Important - covers edge cases and integration
- P2: Nice to have - comprehensive coverage
"""

from types import SimpleNamespace

import pytest

from katrain.core.analysis.models import MistakeCategory, PositionDifficulty
from katrain.core.analysis.skill_radar import (
    # Enums
    RadarAxis,
    SkillTier,
    # Dataclass
    RadarMetrics,
    # Constants
    TIER_TO_INT,
    INT_TO_TIER,
    APL_TIER_THRESHOLDS,
    BLUNDER_RATE_TIER_THRESHOLDS,
    MATCH_RATE_TIER_THRESHOLDS,
    GARBAGE_TIME_WINRATE_HIGH,
    GARBAGE_TIME_WINRATE_LOW,
    OPENING_END_MOVE,
    ENDGAME_START_MOVE,
    NEUTRAL_DISPLAY_SCORE,
    NEUTRAL_TIER,
    # Conversion functions
    apl_to_tier_and_score,
    blunder_rate_to_tier_and_score,
    match_rate_to_tier_and_score,
    # Detection functions
    is_garbage_time,
    compute_overall_tier,
    # Axis computation functions
    compute_opening_axis,
    compute_fighting_axis,
    compute_endgame_axis,
    compute_stability_axis,
    compute_awareness_axis,
    # Main entry point
    compute_radar_from_moves,
)


# =============================================================================
# Test Fixtures
# =============================================================================


def make_move_stub(
    move_number: int = 1,
    player: str = "B",
    points_lost: float | None = 0.0,
    mistake_category: MistakeCategory = MistakeCategory.GOOD,
    position_difficulty: PositionDifficulty | None = PositionDifficulty.NORMAL,
    winrate_before: float | None = 0.5,
) -> SimpleNamespace:
    """Create a lightweight MoveEval stub for testing.

    Note:
        - skill_radar.py only uses these fields
        - mistake_category is non-Optional (MoveEval has default=GOOD)
        - SimpleNamespace supports attribute access
    """
    return SimpleNamespace(
        move_number=move_number,
        player=player,
        points_lost=points_lost,
        mistake_category=mistake_category,
        position_difficulty=position_difficulty,
        winrate_before=winrate_before,
    )


# =============================================================================
# P0: Enum Tests
# =============================================================================


class TestRadarEnums:
    """P0: Test RadarAxis and SkillTier enums."""

    def test_radar_axis_values(self):
        """RadarAxis has correct string values."""
        assert RadarAxis.OPENING.value == "opening"
        assert RadarAxis.FIGHTING.value == "fighting"
        assert RadarAxis.ENDGAME.value == "endgame"
        assert RadarAxis.STABILITY.value == "stability"
        assert RadarAxis.AWARENESS.value == "awareness"

    def test_radar_axis_is_str(self):
        """RadarAxis inherits from str."""
        assert isinstance(RadarAxis.OPENING, str)
        assert RadarAxis.OPENING == "opening"

    def test_skill_tier_values(self):
        """SkillTier has correct string values."""
        assert SkillTier.TIER_1.value == "tier_1"
        assert SkillTier.TIER_2.value == "tier_2"
        assert SkillTier.TIER_3.value == "tier_3"
        assert SkillTier.TIER_4.value == "tier_4"
        assert SkillTier.TIER_5.value == "tier_5"
        assert SkillTier.TIER_UNKNOWN.value == "unknown"

    def test_skill_tier_is_str(self):
        """SkillTier inherits from str."""
        assert isinstance(SkillTier.TIER_3, str)
        assert SkillTier.TIER_3 == "tier_3"

    def test_tier_to_int_mapping(self):
        """TIER_TO_INT maps tiers to integers correctly."""
        assert TIER_TO_INT[SkillTier.TIER_1] == 1
        assert TIER_TO_INT[SkillTier.TIER_2] == 2
        assert TIER_TO_INT[SkillTier.TIER_3] == 3
        assert TIER_TO_INT[SkillTier.TIER_4] == 4
        assert TIER_TO_INT[SkillTier.TIER_5] == 5

    def test_int_to_tier_mapping(self):
        """INT_TO_TIER maps integers to tiers correctly."""
        assert INT_TO_TIER[1] == SkillTier.TIER_1
        assert INT_TO_TIER[2] == SkillTier.TIER_2
        assert INT_TO_TIER[3] == SkillTier.TIER_3
        assert INT_TO_TIER[4] == SkillTier.TIER_4
        assert INT_TO_TIER[5] == SkillTier.TIER_5

    def test_tier_unknown_not_in_int_mapping(self):
        """TIER_UNKNOWN is not in numeric mappings."""
        assert SkillTier.TIER_UNKNOWN not in TIER_TO_INT


# =============================================================================
# P0: RadarMetrics Tests
# =============================================================================


class TestRadarMetrics:
    """P0: Test RadarMetrics dataclass."""

    def test_frozen_immutability(self):
        """RadarMetrics is frozen (immutable)."""
        from types import MappingProxyType

        metrics = RadarMetrics(
            opening=3.0,
            fighting=3.0,
            endgame=3.0,
            stability=3.0,
            awareness=3.0,
            opening_tier=SkillTier.TIER_3,
            fighting_tier=SkillTier.TIER_3,
            endgame_tier=SkillTier.TIER_3,
            stability_tier=SkillTier.TIER_3,
            awareness_tier=SkillTier.TIER_3,
            overall_tier=SkillTier.TIER_3,
            valid_move_counts=MappingProxyType({RadarAxis.OPENING: 10}),
        )
        with pytest.raises(AttributeError):
            metrics.opening = 5.0  # type: ignore

    def test_valid_move_counts_immutable(self):
        """valid_move_counts cannot be modified externally."""
        from types import MappingProxyType

        counts = MappingProxyType({RadarAxis.OPENING: 10})
        metrics = RadarMetrics(
            opening=3.0,
            fighting=3.0,
            endgame=3.0,
            stability=3.0,
            awareness=3.0,
            opening_tier=SkillTier.TIER_3,
            fighting_tier=SkillTier.TIER_3,
            endgame_tier=SkillTier.TIER_3,
            stability_tier=SkillTier.TIER_3,
            awareness_tier=SkillTier.TIER_3,
            overall_tier=SkillTier.TIER_3,
            valid_move_counts=counts,
        )
        with pytest.raises(TypeError):
            metrics.valid_move_counts[RadarAxis.FIGHTING] = 20  # type: ignore

    def test_all_fields_present(self):
        """RadarMetrics has all required fields."""
        from types import MappingProxyType

        metrics = RadarMetrics(
            opening=4.0,
            fighting=3.0,
            endgame=2.0,
            stability=5.0,
            awareness=1.0,
            opening_tier=SkillTier.TIER_4,
            fighting_tier=SkillTier.TIER_3,
            endgame_tier=SkillTier.TIER_2,
            stability_tier=SkillTier.TIER_5,
            awareness_tier=SkillTier.TIER_1,
            overall_tier=SkillTier.TIER_3,
            valid_move_counts=MappingProxyType(
                {
                    RadarAxis.OPENING: 25,
                    RadarAxis.FIGHTING: 12,
                    RadarAxis.ENDGAME: 30,
                    RadarAxis.STABILITY: 120,
                    RadarAxis.AWARENESS: 115,
                }
            ),
        )
        assert metrics.opening == 4.0
        assert metrics.fighting == 3.0
        assert metrics.endgame == 2.0
        assert metrics.stability == 5.0
        assert metrics.awareness == 1.0
        assert metrics.opening_tier == SkillTier.TIER_4
        assert metrics.overall_tier == SkillTier.TIER_3
        assert metrics.valid_move_counts[RadarAxis.OPENING] == 25

    def test_to_dict_scores_are_floats(self):
        """to_dict() returns float scores."""
        from types import MappingProxyType

        metrics = RadarMetrics(
            opening=3.0,
            fighting=3.0,
            endgame=3.0,
            stability=3.0,
            awareness=3.0,
            opening_tier=SkillTier.TIER_3,
            fighting_tier=SkillTier.TIER_3,
            endgame_tier=SkillTier.TIER_3,
            stability_tier=SkillTier.TIER_3,
            awareness_tier=SkillTier.TIER_3,
            overall_tier=SkillTier.TIER_3,
            valid_move_counts=MappingProxyType({RadarAxis.OPENING: 10}),
        )
        d = metrics.to_dict()
        for axis in ["opening", "fighting", "endgame", "stability", "awareness"]:
            assert isinstance(d["scores"][axis], float)

    def test_to_dict_tiers_are_strings(self):
        """to_dict() returns string tiers."""
        from types import MappingProxyType

        metrics = RadarMetrics(
            opening=3.0,
            fighting=3.0,
            endgame=3.0,
            stability=3.0,
            awareness=3.0,
            opening_tier=SkillTier.TIER_3,
            fighting_tier=SkillTier.TIER_3,
            endgame_tier=SkillTier.TIER_3,
            stability_tier=SkillTier.TIER_3,
            awareness_tier=SkillTier.TIER_3,
            overall_tier=SkillTier.TIER_3,
            valid_move_counts=MappingProxyType({RadarAxis.OPENING: 10}),
        )
        d = metrics.to_dict()
        for axis in ["opening", "fighting", "endgame", "stability", "awareness"]:
            assert isinstance(d["tiers"][axis], str)
            assert d["tiers"][axis].startswith("tier_") or d["tiers"][axis] == "unknown"

    def test_to_dict_overall_tier_is_string(self):
        """to_dict() returns string overall_tier."""
        from types import MappingProxyType

        metrics = RadarMetrics(
            opening=3.0,
            fighting=3.0,
            endgame=3.0,
            stability=3.0,
            awareness=3.0,
            opening_tier=SkillTier.TIER_3,
            fighting_tier=SkillTier.TIER_3,
            endgame_tier=SkillTier.TIER_3,
            stability_tier=SkillTier.TIER_3,
            awareness_tier=SkillTier.TIER_3,
            overall_tier=SkillTier.TIER_3,
            valid_move_counts=MappingProxyType({RadarAxis.OPENING: 10}),
        )
        d = metrics.to_dict()
        assert isinstance(d["overall_tier"], str)
        assert d["overall_tier"] == "tier_3"

    def test_to_dict_valid_move_counts_keys_are_strings(self):
        """to_dict() returns string keys for valid_move_counts."""
        from types import MappingProxyType

        metrics = RadarMetrics(
            opening=3.0,
            fighting=3.0,
            endgame=3.0,
            stability=3.0,
            awareness=3.0,
            opening_tier=SkillTier.TIER_3,
            fighting_tier=SkillTier.TIER_3,
            endgame_tier=SkillTier.TIER_3,
            stability_tier=SkillTier.TIER_3,
            awareness_tier=SkillTier.TIER_3,
            overall_tier=SkillTier.TIER_3,
            valid_move_counts=MappingProxyType(
                {
                    RadarAxis.OPENING: 25,
                    RadarAxis.FIGHTING: 12,
                }
            ),
        )
        d = metrics.to_dict()
        for key in d["valid_move_counts"]:
            assert isinstance(key, str)
            assert key in ["opening", "fighting", "endgame", "stability", "awareness"]


# =============================================================================
# P0: APL Conversion Tests
# =============================================================================


class TestAPLConversion:
    """P0: Test APL to tier conversion with boundary values."""

    def test_apl_0_39_is_tier_5(self):
        """APL=0.39 < 0.4 -> TIER_5."""
        tier, score = apl_to_tier_and_score(0.39)
        assert tier == SkillTier.TIER_5
        assert score == 5.0

    def test_apl_0_40_is_tier_4(self):
        """APL=0.40 NOT < 0.4, but < 0.8 -> TIER_4."""
        tier, score = apl_to_tier_and_score(0.40)
        assert tier == SkillTier.TIER_4
        assert score == 4.0

    def test_apl_0_79_is_tier_4(self):
        """APL=0.79 < 0.8 -> TIER_4."""
        tier, score = apl_to_tier_and_score(0.79)
        assert tier == SkillTier.TIER_4
        assert score == 4.0

    def test_apl_0_80_is_tier_3(self):
        """APL=0.80 NOT < 0.8, but < 1.2 -> TIER_3."""
        tier, score = apl_to_tier_and_score(0.80)
        assert tier == SkillTier.TIER_3
        assert score == 3.0

    def test_apl_1_19_is_tier_3(self):
        """APL=1.19 < 1.2 -> TIER_3."""
        tier, score = apl_to_tier_and_score(1.19)
        assert tier == SkillTier.TIER_3
        assert score == 3.0

    def test_apl_1_20_is_tier_2(self):
        """APL=1.20 NOT < 1.2, but < 2.0 -> TIER_2."""
        tier, score = apl_to_tier_and_score(1.20)
        assert tier == SkillTier.TIER_2
        assert score == 2.0

    def test_apl_1_99_is_tier_2(self):
        """APL=1.99 < 2.0 -> TIER_2."""
        tier, score = apl_to_tier_and_score(1.99)
        assert tier == SkillTier.TIER_2
        assert score == 2.0

    def test_apl_2_00_is_tier_1(self):
        """APL=2.00 NOT < 2.0 -> TIER_1."""
        tier, score = apl_to_tier_and_score(2.00)
        assert tier == SkillTier.TIER_1
        assert score == 1.0


# =============================================================================
# P0: Blunder Rate Conversion Tests
# =============================================================================


class TestBlunderRateConversion:
    """P0: Test Blunder Rate to tier conversion with boundary values."""

    def test_rate_0_009_is_tier_5(self):
        """Rate=0.009 < 0.01 -> TIER_5."""
        tier, score = blunder_rate_to_tier_and_score(0.009)
        assert tier == SkillTier.TIER_5
        assert score == 5.0

    def test_rate_0_010_is_tier_4(self):
        """Rate=0.010 NOT < 0.01 -> TIER_4."""
        tier, score = blunder_rate_to_tier_and_score(0.010)
        assert tier == SkillTier.TIER_4
        assert score == 4.0

    def test_rate_0_029_is_tier_4(self):
        """Rate=0.029 < 0.03 -> TIER_4."""
        tier, score = blunder_rate_to_tier_and_score(0.029)
        assert tier == SkillTier.TIER_4
        assert score == 4.0

    def test_rate_0_030_is_tier_3(self):
        """Rate=0.030 NOT < 0.03 -> TIER_3."""
        tier, score = blunder_rate_to_tier_and_score(0.030)
        assert tier == SkillTier.TIER_3
        assert score == 3.0

    def test_rate_0_049_is_tier_3(self):
        """Rate=0.049 < 0.05 -> TIER_3."""
        tier, score = blunder_rate_to_tier_and_score(0.049)
        assert tier == SkillTier.TIER_3
        assert score == 3.0

    def test_rate_0_050_is_tier_2(self):
        """Rate=0.050 NOT < 0.05 -> TIER_2."""
        tier, score = blunder_rate_to_tier_and_score(0.050)
        assert tier == SkillTier.TIER_2
        assert score == 2.0

    def test_rate_0_099_is_tier_2(self):
        """Rate=0.099 < 0.10 -> TIER_2."""
        tier, score = blunder_rate_to_tier_and_score(0.099)
        assert tier == SkillTier.TIER_2
        assert score == 2.0

    def test_rate_0_100_is_tier_1(self):
        """Rate=0.100 NOT < 0.10 -> TIER_1."""
        tier, score = blunder_rate_to_tier_and_score(0.100)
        assert tier == SkillTier.TIER_1
        assert score == 1.0


# =============================================================================
# P0: Match Rate Conversion Tests
# =============================================================================


class TestMatchRateConversion:
    """P0: Test Match Rate to tier conversion with boundary values."""

    def test_rate_0_249_is_tier_1(self):
        """Rate=0.249 < 0.25 -> TIER_1."""
        tier, score = match_rate_to_tier_and_score(0.249)
        assert tier == SkillTier.TIER_1
        assert score == 1.0

    def test_rate_0_250_is_tier_2(self):
        """Rate=0.250 NOT < 0.25, but < 0.35 -> TIER_2."""
        tier, score = match_rate_to_tier_and_score(0.250)
        assert tier == SkillTier.TIER_2
        assert score == 2.0

    def test_rate_0_349_is_tier_2(self):
        """Rate=0.349 < 0.35 -> TIER_2."""
        tier, score = match_rate_to_tier_and_score(0.349)
        assert tier == SkillTier.TIER_2
        assert score == 2.0

    def test_rate_0_350_is_tier_3(self):
        """Rate=0.350 NOT < 0.35 -> TIER_3."""
        tier, score = match_rate_to_tier_and_score(0.350)
        assert tier == SkillTier.TIER_3
        assert score == 3.0

    def test_rate_0_449_is_tier_3(self):
        """Rate=0.449 < 0.45 -> TIER_3."""
        tier, score = match_rate_to_tier_and_score(0.449)
        assert tier == SkillTier.TIER_3
        assert score == 3.0

    def test_rate_0_450_is_tier_4(self):
        """Rate=0.450 NOT < 0.45 -> TIER_4."""
        tier, score = match_rate_to_tier_and_score(0.450)
        assert tier == SkillTier.TIER_4
        assert score == 4.0

    def test_rate_0_549_is_tier_4(self):
        """Rate=0.549 < 0.55 -> TIER_4."""
        tier, score = match_rate_to_tier_and_score(0.549)
        assert tier == SkillTier.TIER_4
        assert score == 4.0

    def test_rate_0_550_is_tier_5(self):
        """Rate=0.550 NOT < 0.55 -> TIER_5."""
        tier, score = match_rate_to_tier_and_score(0.550)
        assert tier == SkillTier.TIER_5
        assert score == 5.0


# =============================================================================
# P0: Garbage Time Detection Tests
# =============================================================================


class TestGarbageTime:
    """P0: Test garbage time detection."""

    def test_winrate_0_99_is_garbage(self):
        """winrate=0.99 >= 0.99 -> garbage time."""
        assert is_garbage_time(0.99) is True

    def test_winrate_0_01_is_garbage(self):
        """winrate=0.01 <= 0.01 -> garbage time."""
        assert is_garbage_time(0.01) is True

    def test_winrate_0_989_is_not_garbage(self):
        """winrate=0.989 < 0.99 -> not garbage."""
        assert is_garbage_time(0.989) is False

    def test_winrate_0_011_is_not_garbage(self):
        """winrate=0.011 > 0.01 -> not garbage."""
        assert is_garbage_time(0.011) is False

    def test_winrate_0_5_is_not_garbage(self):
        """winrate=0.5 is normal."""
        assert is_garbage_time(0.5) is False

    def test_winrate_none_is_not_garbage(self):
        """winrate=None -> cannot determine, include."""
        assert is_garbage_time(None) is False


# =============================================================================
# P0: Overall Tier Calculation Tests
# =============================================================================


class TestOverallTier:
    """P0: Test overall tier median calculation."""

    def test_two_tiers_1_5_gives_tier_3(self):
        """[1, 5] -> avg=3.0 -> TIER_3."""
        result = compute_overall_tier(
            [SkillTier.TIER_1, SkillTier.TIER_5]
        )
        assert result == SkillTier.TIER_3

    def test_two_tiers_2_4_gives_tier_3(self):
        """[2, 4] -> avg=3.0 -> TIER_3."""
        result = compute_overall_tier(
            [SkillTier.TIER_2, SkillTier.TIER_4]
        )
        assert result == SkillTier.TIER_3

    def test_two_tiers_1_2_gives_tier_2(self):
        """[1, 2] -> avg=1.5 -> ceil=2 -> TIER_2."""
        result = compute_overall_tier(
            [SkillTier.TIER_1, SkillTier.TIER_2]
        )
        assert result == SkillTier.TIER_2

    def test_two_tiers_4_5_gives_tier_5(self):
        """[4, 5] -> avg=4.5 -> ceil=5 -> TIER_5."""
        result = compute_overall_tier(
            [SkillTier.TIER_4, SkillTier.TIER_5]
        )
        assert result == SkillTier.TIER_5

    def test_three_tiers_1_2_3_gives_tier_2(self):
        """[1, 2, 3] -> middle=2 -> TIER_2."""
        result = compute_overall_tier(
            [SkillTier.TIER_1, SkillTier.TIER_2, SkillTier.TIER_3]
        )
        assert result == SkillTier.TIER_2

    def test_three_tiers_3_4_5_gives_tier_4(self):
        """[3, 4, 5] -> middle=4 -> TIER_4."""
        result = compute_overall_tier(
            [SkillTier.TIER_3, SkillTier.TIER_4, SkillTier.TIER_5]
        )
        assert result == SkillTier.TIER_4

    def test_four_tiers_1_2_3_4_gives_tier_3(self):
        """[1, 2, 3, 4] -> avg(2,3)=2.5 -> ceil=3 -> TIER_3."""
        result = compute_overall_tier(
            [SkillTier.TIER_1, SkillTier.TIER_2, SkillTier.TIER_3, SkillTier.TIER_4]
        )
        assert result == SkillTier.TIER_3

    def test_five_tiers_with_two_unknown_gives_tier_4(self):
        """[UNKNOWN, UNKNOWN, 3, 4, 5] -> known=[3,4,5] -> mid=4 -> TIER_4."""
        result = compute_overall_tier(
            [
                SkillTier.TIER_UNKNOWN,
                SkillTier.TIER_UNKNOWN,
                SkillTier.TIER_3,
                SkillTier.TIER_4,
                SkillTier.TIER_5,
            ]
        )
        assert result == SkillTier.TIER_4

    def test_all_unknown_gives_tier_unknown(self):
        """All UNKNOWN -> TIER_UNKNOWN."""
        result = compute_overall_tier(
            [
                SkillTier.TIER_UNKNOWN,
                SkillTier.TIER_UNKNOWN,
                SkillTier.TIER_UNKNOWN,
                SkillTier.TIER_UNKNOWN,
                SkillTier.TIER_UNKNOWN,
            ]
        )
        assert result == SkillTier.TIER_UNKNOWN

    def test_single_tier(self):
        """Single tier -> that tier."""
        result = compute_overall_tier([SkillTier.TIER_3])
        assert result == SkillTier.TIER_3


# =============================================================================
# P1: Axis Filtering Tests
# =============================================================================


class TestAxisFiltering:
    """P1: Test axis-specific filtering logic."""

    def test_opening_boundary_move_50_included(self):
        """move_number=50 is included in Opening."""
        moves = [make_move_stub(move_number=50, points_lost=0.3)]
        tier, score, count = compute_opening_axis(moves)
        assert count == 1
        assert tier == SkillTier.TIER_5

    def test_opening_boundary_move_51_excluded(self):
        """move_number=51 is excluded from Opening."""
        moves = [make_move_stub(move_number=51, points_lost=0.3)]
        tier, score, count = compute_opening_axis(moves)
        assert count == 0
        assert tier == NEUTRAL_TIER

    def test_endgame_boundary_move_149_excluded(self):
        """move_number=149 is excluded from Endgame."""
        moves = [make_move_stub(move_number=149, points_lost=0.3)]
        tier, score, count = compute_endgame_axis(moves)
        assert count == 0

    def test_endgame_boundary_move_150_included(self):
        """move_number=150 is included in Endgame."""
        moves = [make_move_stub(move_number=150, points_lost=0.3)]
        tier, score, count = compute_endgame_axis(moves)
        assert count == 1
        assert tier == SkillTier.TIER_5

    def test_opening_excludes_only_move(self):
        """Opening excludes ONLY_MOVE positions."""
        moves = [
            make_move_stub(
                move_number=10,
                points_lost=0.3,
                position_difficulty=PositionDifficulty.ONLY_MOVE,
            )
        ]
        tier, score, count = compute_opening_axis(moves)
        assert count == 0

    def test_fighting_only_hard_positions(self):
        """Fighting only includes HARD positions."""
        moves = [
            make_move_stub(
                move_number=100,
                points_lost=0.3,
                position_difficulty=PositionDifficulty.NORMAL,
            ),
            make_move_stub(
                move_number=100,
                points_lost=0.5,
                position_difficulty=PositionDifficulty.HARD,
            ),
        ]
        tier, score, count = compute_fighting_axis(moves)
        assert count == 1

    def test_fighting_excludes_easy(self):
        """Fighting excludes EASY positions."""
        moves = [
            make_move_stub(
                move_number=100,
                points_lost=0.3,
                position_difficulty=PositionDifficulty.EASY,
            )
        ]
        tier, score, count = compute_fighting_axis(moves)
        assert count == 0

    def test_endgame_does_not_exclude_only_move(self):
        """Endgame does NOT exclude ONLY_MOVE (intentional)."""
        moves = [
            make_move_stub(
                move_number=160,
                points_lost=0.3,
                position_difficulty=PositionDifficulty.ONLY_MOVE,
            )
        ]
        tier, score, count = compute_endgame_axis(moves)
        assert count == 1

    def test_awareness_excludes_only_move(self):
        """Awareness excludes ONLY_MOVE positions."""
        moves = [
            make_move_stub(
                move_number=100,
                position_difficulty=PositionDifficulty.ONLY_MOVE,
            ),
            make_move_stub(
                move_number=100,
                position_difficulty=PositionDifficulty.NORMAL,
            ),
        ]
        tier, score, count = compute_awareness_axis(moves)
        assert count == 1


# =============================================================================
# P1: Fighting Axis None Tests
# =============================================================================


class TestFightingAxisNone:
    """P1: Test Fighting axis with position_difficulty=None."""

    def test_none_position_difficulty_excluded(self):
        """position_difficulty=None is excluded from Fighting."""
        moves = [
            make_move_stub(
                move_number=100,
                points_lost=0.3,
                position_difficulty=None,
            )
        ]
        tier, score, count = compute_fighting_axis(moves)
        assert count == 0
        assert tier == NEUTRAL_TIER

    def test_unknown_position_difficulty_excluded(self):
        """position_difficulty=UNKNOWN is excluded from Fighting."""
        moves = [
            make_move_stub(
                move_number=100,
                points_lost=0.3,
                position_difficulty=PositionDifficulty.UNKNOWN,
            )
        ]
        tier, score, count = compute_fighting_axis(moves)
        assert count == 0

    def test_hard_with_none_mixed(self):
        """Only HARD is included when mixed with None."""
        moves = [
            make_move_stub(
                move_number=100,
                points_lost=0.3,
                position_difficulty=None,
            ),
            make_move_stub(
                move_number=100,
                points_lost=0.5,
                position_difficulty=PositionDifficulty.HARD,
            ),
        ]
        tier, score, count = compute_fighting_axis(moves)
        assert count == 1


# =============================================================================
# P1: Awareness Garbage Time Tests
# =============================================================================


class TestAwarenessGarbageTime:
    """P1: Test Awareness axis garbage time exclusion."""

    def test_awareness_excludes_garbage_time_high(self):
        """Awareness excludes winrate >= 0.99."""
        moves = [
            make_move_stub(move_number=100, winrate_before=0.99),
            make_move_stub(move_number=100, winrate_before=0.5),
        ]
        tier, score, count = compute_awareness_axis(moves)
        assert count == 1

    def test_awareness_excludes_garbage_time_low(self):
        """Awareness excludes winrate <= 0.01."""
        moves = [
            make_move_stub(move_number=100, winrate_before=0.01),
            make_move_stub(move_number=100, winrate_before=0.5),
        ]
        tier, score, count = compute_awareness_axis(moves)
        assert count == 1

    def test_awareness_all_garbage_gives_neutral(self):
        """All garbage time moves -> NEUTRAL."""
        moves = [
            make_move_stub(move_number=100, winrate_before=0.99),
            make_move_stub(move_number=100, winrate_before=0.01),
        ]
        tier, score, count = compute_awareness_axis(moves)
        assert count == 0
        assert tier == NEUTRAL_TIER


# =============================================================================
# P1: Points Lost Clamp Tests
# =============================================================================


class TestPointsLostClamp:
    """P1: Test negative points_lost clamping."""

    def test_negative_points_lost_clamped_to_zero(self):
        """Negative points_lost is clamped to 0."""
        moves = [
            make_move_stub(move_number=10, points_lost=-0.5),
            make_move_stub(move_number=20, points_lost=0.5),
        ]
        tier, score, count = compute_opening_axis(moves)
        # APL = (0.0 + 0.5) / 2 = 0.25 < 0.4 -> TIER_5
        assert tier == SkillTier.TIER_5
        assert count == 2

    def test_zero_points_lost_is_valid(self):
        """points_lost=0.0 is valid (best move)."""
        moves = [make_move_stub(move_number=10, points_lost=0.0)]
        tier, score, count = compute_opening_axis(moves)
        assert tier == SkillTier.TIER_5
        assert count == 1


# =============================================================================
# P1: Compute Radar Integration Tests
# =============================================================================


class TestComputeRadar:
    """P1: Test compute_radar_from_moves integration."""

    def test_basic_integration(self):
        """Basic integration test with mixed moves."""
        moves = [
            # Opening moves (1-50)
            make_move_stub(move_number=10, points_lost=0.3, player="B"),
            make_move_stub(move_number=20, points_lost=0.3, player="B"),
            # Fighting moves (HARD) - outside Opening range
            make_move_stub(
                move_number=100,
                points_lost=0.5,
                player="B",
                position_difficulty=PositionDifficulty.HARD,
            ),
            # Endgame moves (150+)
            make_move_stub(move_number=160, points_lost=0.3, player="B"),
            # Blunder outside Opening range (doesn't affect Opening count)
            make_move_stub(
                move_number=80,
                player="B",
                mistake_category=MistakeCategory.BLUNDER,
            ),
        ]
        radar = compute_radar_from_moves(moves)
        assert radar.valid_move_counts[RadarAxis.OPENING] == 2
        assert radar.valid_move_counts[RadarAxis.FIGHTING] == 1
        assert radar.valid_move_counts[RadarAxis.ENDGAME] == 1
        assert radar.valid_move_counts[RadarAxis.STABILITY] == 5
        assert radar.valid_move_counts[RadarAxis.AWARENESS] >= 1

    def test_player_filter_black(self):
        """player='B' filters to black moves only."""
        moves = [
            make_move_stub(move_number=10, points_lost=0.3, player="B"),
            make_move_stub(move_number=20, points_lost=0.5, player="W"),
        ]
        radar = compute_radar_from_moves(moves, player="B")
        assert radar.valid_move_counts[RadarAxis.OPENING] == 1

    def test_player_filter_white(self):
        """player='W' filters to white moves only."""
        moves = [
            make_move_stub(move_number=10, points_lost=0.3, player="B"),
            make_move_stub(move_number=20, points_lost=0.5, player="W"),
        ]
        radar = compute_radar_from_moves(moves, player="W")
        assert radar.valid_move_counts[RadarAxis.OPENING] == 1

    def test_player_filter_none_includes_both(self):
        """player=None includes both B and W."""
        moves = [
            make_move_stub(move_number=10, points_lost=0.3, player="B"),
            make_move_stub(move_number=20, points_lost=0.5, player="W"),
        ]
        radar = compute_radar_from_moves(moves, player=None)
        assert radar.valid_move_counts[RadarAxis.OPENING] == 2

    def test_to_dict_json_serializable(self):
        """to_dict() output is JSON-serializable."""
        import json

        moves = [
            make_move_stub(move_number=10, points_lost=0.3),
        ]
        radar = compute_radar_from_moves(moves)
        d = radar.to_dict()
        # Should not raise
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

    def test_stability_includes_garbage_time(self):
        """Stability axis includes garbage time moves."""
        moves = [
            make_move_stub(
                move_number=100,
                winrate_before=0.99,  # garbage time
                mistake_category=MistakeCategory.BLUNDER,
            ),
            make_move_stub(
                move_number=100,
                winrate_before=0.5,  # normal
                mistake_category=MistakeCategory.GOOD,
            ),
        ]
        radar = compute_radar_from_moves(moves)
        # Stability should count both
        assert radar.valid_move_counts[RadarAxis.STABILITY] == 2


# =============================================================================
# P1: to_dict Contract Tests
# =============================================================================


class TestToDictContract:
    """P1: Test to_dict() JSON contract."""

    def test_complete_structure(self):
        """to_dict() has complete structure."""
        moves = [
            make_move_stub(move_number=10, points_lost=0.3),
        ]
        radar = compute_radar_from_moves(moves)
        d = radar.to_dict()
        assert "scores" in d
        assert "tiers" in d
        assert "overall_tier" in d
        assert "valid_move_counts" in d

    def test_scores_has_all_axes(self):
        """scores dict has all 5 axes."""
        moves = [make_move_stub(move_number=10, points_lost=0.3)]
        radar = compute_radar_from_moves(moves)
        d = radar.to_dict()
        for axis in ["opening", "fighting", "endgame", "stability", "awareness"]:
            assert axis in d["scores"]

    def test_tiers_has_all_axes(self):
        """tiers dict has all 5 axes."""
        moves = [make_move_stub(move_number=10, points_lost=0.3)]
        radar = compute_radar_from_moves(moves)
        d = radar.to_dict()
        for axis in ["opening", "fighting", "endgame", "stability", "awareness"]:
            assert axis in d["tiers"]

    def test_tier_values_are_enum_values(self):
        """Tier values are enum .value strings."""
        moves = [make_move_stub(move_number=10, points_lost=0.3)]
        radar = compute_radar_from_moves(moves)
        d = radar.to_dict()
        valid_tiers = {"tier_1", "tier_2", "tier_3", "tier_4", "tier_5", "unknown"}
        for axis in ["opening", "fighting", "endgame", "stability", "awareness"]:
            assert d["tiers"][axis] in valid_tiers
        assert d["overall_tier"] in valid_tiers


# =============================================================================
# P2: Empty Input Tests
# =============================================================================


class TestEmptyInput:
    """P2: Test empty input handling."""

    def test_empty_list_all_neutral(self):
        """Empty list -> all axes NEUTRAL."""
        radar = compute_radar_from_moves([])
        assert radar.opening_tier == NEUTRAL_TIER
        assert radar.fighting_tier == NEUTRAL_TIER
        assert radar.endgame_tier == NEUTRAL_TIER
        assert radar.stability_tier == NEUTRAL_TIER
        assert radar.awareness_tier == NEUTRAL_TIER
        assert radar.overall_tier == SkillTier.TIER_UNKNOWN

    def test_empty_list_all_zero_counts(self):
        """Empty list -> all valid_move_counts are 0."""
        radar = compute_radar_from_moves([])
        for axis in RadarAxis:
            assert radar.valid_move_counts[axis] == 0

    def test_empty_list_neutral_scores(self):
        """Empty list -> all scores are NEUTRAL_DISPLAY_SCORE."""
        radar = compute_radar_from_moves([])
        assert radar.opening == NEUTRAL_DISPLAY_SCORE
        assert radar.fighting == NEUTRAL_DISPLAY_SCORE
        assert radar.endgame == NEUTRAL_DISPLAY_SCORE
        assert radar.stability == NEUTRAL_DISPLAY_SCORE
        assert radar.awareness == NEUTRAL_DISPLAY_SCORE


# =============================================================================
# P2: Player Filter Tests
# =============================================================================


class TestPlayerFilter:
    """P2: Test player filtering."""

    def test_filter_excludes_none_player(self):
        """player='B' excludes moves with player=None."""
        moves = [
            make_move_stub(move_number=10, points_lost=0.3, player="B"),
            make_move_stub(move_number=20, points_lost=0.5, player=None),  # type: ignore
        ]
        radar = compute_radar_from_moves(moves, player="B")
        assert radar.valid_move_counts[RadarAxis.OPENING] == 1

    def test_filter_b_ignores_w(self):
        """player='B' ignores all W moves."""
        moves = [
            make_move_stub(move_number=10, points_lost=0.1, player="W"),
            make_move_stub(move_number=20, points_lost=0.1, player="W"),
            make_move_stub(move_number=30, points_lost=0.9, player="B"),
        ]
        radar = compute_radar_from_moves(moves, player="B")
        # Only B move counted, APL=0.9
        assert radar.valid_move_counts[RadarAxis.OPENING] == 1
        assert radar.opening_tier == SkillTier.TIER_3  # 0.8-1.2 -> TIER_3

    def test_filter_w_ignores_b(self):
        """player='W' ignores all B moves."""
        moves = [
            make_move_stub(move_number=10, points_lost=0.1, player="B"),
            make_move_stub(move_number=20, points_lost=0.1, player="B"),
            make_move_stub(move_number=30, points_lost=0.9, player="W"),
        ]
        radar = compute_radar_from_moves(moves, player="W")
        assert radar.valid_move_counts[RadarAxis.OPENING] == 1
        assert radar.opening_tier == SkillTier.TIER_3


# =============================================================================
# P1: Opening Axis Test Example from Plan
# =============================================================================


class TestOpeningAxisFromPlan:
    """P1: Test examples from the plan document."""

    def test_opening_axis_basic(self):
        """APL = (0.2 + 0.3 + 0.3) / 3 = 0.267 < 0.4 -> TIER_5."""
        moves = [
            make_move_stub(move_number=10, points_lost=0.2),
            make_move_stub(move_number=20, points_lost=0.3),
            make_move_stub(move_number=30, points_lost=0.3),
        ]
        tier, score, count = compute_opening_axis(moves)
        assert tier == SkillTier.TIER_5
        assert score == 5.0
        assert count == 3

    def test_opening_axis_boundary(self):
        """APL = 0.41 (slightly above 0.4) -> not < 0.4 -> TIER_4.

        Note: Using 0.41 instead of 0.4 exactly to avoid floating-point
        precision issues (e.g., (0.3+0.5+0.4)/3 = 0.39999... due to IEEE 754).
        """
        moves = [
            make_move_stub(move_number=10, points_lost=0.41),
            make_move_stub(move_number=20, points_lost=0.41),
            make_move_stub(move_number=30, points_lost=0.41),
        ]
        tier, score, count = compute_opening_axis(moves)
        assert tier == SkillTier.TIER_4  # 0.41 is NOT < 0.4
        assert score == 4.0
        assert count == 3


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Test that constants have expected values."""

    def test_garbage_time_thresholds(self):
        """Garbage time thresholds are correct."""
        assert GARBAGE_TIME_WINRATE_HIGH == 0.99
        assert GARBAGE_TIME_WINRATE_LOW == 0.01

    def test_phase_boundaries(self):
        """Phase boundaries are correct for 19x19."""
        assert OPENING_END_MOVE == 50
        assert ENDGAME_START_MOVE == 150

    def test_neutral_values(self):
        """Neutral values are correct."""
        assert NEUTRAL_DISPLAY_SCORE == 3.0
        assert NEUTRAL_TIER == SkillTier.TIER_UNKNOWN

    def test_apl_thresholds_count(self):
        """APL thresholds have 5 entries."""
        assert len(APL_TIER_THRESHOLDS) == 5

    def test_blunder_rate_thresholds_count(self):
        """Blunder rate thresholds have 5 entries."""
        assert len(BLUNDER_RATE_TIER_THRESHOLDS) == 5

    def test_match_rate_thresholds_count(self):
        """Match rate thresholds have 5 entries."""
        assert len(MATCH_RATE_TIER_THRESHOLDS) == 5
