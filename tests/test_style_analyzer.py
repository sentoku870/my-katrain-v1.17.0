# -*- coding: utf-8 -*-
"""Tests for Style Archetype Analyzer.

Part of Phase 56: Style Archetype Core.
"""

import math
from types import MappingProxyType

import pytest

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.analysis.skill_radar import RadarAxis, RadarMetrics, SkillTier
from katrain.core.analysis.style import (
    STYLE_ARCHETYPES,
    StyleArchetypeId,
    StyleResult,
    determine_style,
)


# =============================================================================
# Test Helper
# =============================================================================


def make_radar(
    opening: float = 3.0,
    fighting: float = 3.0,
    endgame: float = 3.0,
    stability: float = 3.0,
    awareness: float = 3.0,
) -> RadarMetrics:
    """Create RadarMetrics for testing.

    Scale: 1.0-5.0 (neutral=3.0, high=4.0+, low=2.0-)
    Deviation threshold: +/-0.5 from 5-axis mean

    All tier fields set to TIER_3, valid_move_counts to 10 per axis.
    """
    return RadarMetrics(
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
        valid_move_counts=MappingProxyType(
            {
                RadarAxis.OPENING: 10,
                RadarAxis.FIGHTING: 10,
                RadarAxis.ENDGAME: 10,
                RadarAxis.STABILITY: 10,
                RadarAxis.AWARENESS: 10,
            }
        ),
    )


# =============================================================================
# P0: Acceptance Criteria Tests
# =============================================================================


class TestAcceptanceCriteria:
    """Tests for acceptance criteria from the plan."""

    def test_returns_one_of_six_archetypes(self):
        """RadarMetrics input returns one of 6 archetypes."""
        radar = make_radar()
        result = determine_style(radar, {})
        assert result.archetype.id in StyleArchetypeId

    def test_fighting_high_with_reinforcing_tag_returns_kiai_fighter(self):
        """Fighting axis high + at least 1 reinforcing tag significant -> KIAI_FIGHTER."""
        # Mean = (3.0+4.5+3.0+2.0+3.0)/5 = 3.1
        # FIGHTING deviation = +1.4 (>= 0.5), STABILITY deviation = -1.1 (<= -0.5)
        # OVERPLAY count = 3 (>= TAG_SIGNIFICANT_COUNT=2) -> tag_score contribution
        radar = make_radar(fighting=4.5, stability=2.0)
        result = determine_style(radar, {MeaningTagId.OVERPLAY: 3})
        assert result.archetype.id == StyleArchetypeId.KIAI_FIGHTER

    def test_balanced_axes_returns_balance_master(self):
        """max |deviation| < 0.5 -> BALANCE_MASTER."""
        # All axes near mean -> no deviation >= 0.5
        radar = make_radar(opening=3.1, fighting=3.0, endgame=2.9, stability=3.0, awareness=3.0)
        result = determine_style(radar, {})
        assert result.archetype.id == StyleArchetypeId.BALANCE_MASTER

    def test_balanced_axes_with_strong_tags_still_returns_balance_master(self):
        """BALANCE-FIRST RULE: balanced radar ignores tags."""
        # All axes at 3.0 -> max |deviation| = 0 < 0.5
        # Even with many OVERPLAY tags, should return BALANCE_MASTER
        radar = make_radar(3.0, 3.0, 3.0, 3.0, 3.0)
        result = determine_style(radar, {MeaningTagId.OVERPLAY: 100})
        assert result.archetype.id == StyleArchetypeId.BALANCE_MASTER
        assert math.isclose(result.confidence, 0.5, abs_tol=1e-9)


# =============================================================================
# P0: Confidence Computation Tests
# =============================================================================


class TestConfidenceComputation:
    """Tests for confidence calculation."""

    def test_tie_score_returns_zero_confidence(self):
        """Two archetypes with same score (within tolerance) -> confidence = 0.0."""
        # Mean = (4.0+4.0+2.5+2.5+2.5)/5 = 3.1
        # FIGHTING deviation = +0.9, OPENING deviation = +0.9 -> both high
        # KIAI_FIGHTER and COSMIC_ARCHITECT will have equal high_axis_score
        radar = make_radar(fighting=4.0, opening=4.0, endgame=2.5, stability=2.5, awareness=2.5)
        result = determine_style(radar, {})
        assert math.isclose(result.confidence, 0.0, abs_tol=1e-9)

    def test_large_margin_returns_high_confidence(self):
        """Clear dominant archetype -> confidence >= 0.8."""
        # Mean = (3.0+4.5+3.0+2.5+3.0)/5 = 3.2
        # FIGHTING deviation = +1.3 (clearly high, others not high)
        radar = make_radar(fighting=4.5, stability=2.5)
        result = determine_style(radar, {MeaningTagId.OVERPLAY: 3})
        assert result.confidence >= 0.8

    def test_balance_master_confidence_is_half(self):
        """BALANCE_MASTER (via balance-first rule) has confidence = 0.5."""
        radar = make_radar(3.0, 3.0, 3.0, 3.0, 3.0)
        result = determine_style(radar, {})
        assert result.archetype.id == StyleArchetypeId.BALANCE_MASTER
        assert math.isclose(result.confidence, 0.5, abs_tol=1e-9)


# =============================================================================
# P0: Dominant Axis Tests
# =============================================================================


class TestDominantAxis:
    """Tests for dominant_axis determination."""

    def test_clear_dominant_axis(self):
        """Single highest axis -> returns that axis."""
        radar = make_radar(fighting=4.5)  # Mean=3.3, FIGHTING dev=+1.2
        result = determine_style(radar, {})
        assert result.dominant_axis == RadarAxis.FIGHTING

    def test_dominant_axis_none_on_tie(self):
        """Two axes with identical max deviation -> dominant_axis is None."""
        # OPENING and FIGHTING both have deviation +0.9
        radar = make_radar(opening=4.0, fighting=4.0, endgame=2.5, stability=2.5, awareness=2.5)
        result = determine_style(radar, {})
        assert result.dominant_axis is None

    def test_dominant_axis_none_when_balanced(self):
        """No axis meets threshold -> dominant_axis is None."""
        radar = make_radar(3.0, 3.0, 3.0, 3.0, 3.0)
        result = determine_style(radar, {})
        assert result.dominant_axis is None


# =============================================================================
# P1: Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_tag_counts(self):
        """Empty tag_counts still returns valid archetype."""
        radar = make_radar(fighting=4.5)
        result = determine_style(radar, {})
        assert result.archetype is not None

    def test_irrelevant_tags_ignored(self):
        """MeaningTagId not in reinforcing_tags does not affect scoring."""
        radar = make_radar(fighting=4.5, stability=2.0)
        result_without = determine_style(radar, {})
        result_with = determine_style(radar, {MeaningTagId.ENDGAME_SLIP: 100})
        assert result_without.archetype.id == result_with.archetype.id

    def test_all_axes_max_score(self):
        """All axes at maximum (5.0) -> BALANCE_MASTER (no deviation)."""
        radar = make_radar(5.0, 5.0, 5.0, 5.0, 5.0)
        result = determine_style(radar, {})
        assert result.archetype.id == StyleArchetypeId.BALANCE_MASTER

    def test_all_axes_min_score(self):
        """All axes at minimum (1.0) -> BALANCE_MASTER (no deviation)."""
        radar = make_radar(1.0, 1.0, 1.0, 1.0, 1.0)
        result = determine_style(radar, {})
        assert result.archetype.id == StyleArchetypeId.BALANCE_MASTER

    def test_deterministic_output(self):
        """Same input always produces same output."""
        radar = make_radar(fighting=4.5, stability=2.0)
        tags = {MeaningTagId.OVERPLAY: 3}
        result1 = determine_style(radar, tags)
        result2 = determine_style(radar, tags)
        assert result1.archetype.id == result2.archetype.id
        assert result1.confidence == result2.confidence


# =============================================================================
# P1: Type Safety Tests
# =============================================================================


class TestTypeSafety:
    """Tests for type safety."""

    def test_axis_deviations_uses_radar_axis_keys(self):
        """axis_deviations has RadarAxis enum keys."""
        result = determine_style(make_radar(), {})
        for key in result.axis_deviations.keys():
            assert isinstance(key, RadarAxis)

    def test_dominant_axis_is_radar_axis_or_none(self):
        """dominant_axis is RadarAxis or None."""
        result = determine_style(make_radar(fighting=4.5), {})
        assert result.dominant_axis is None or isinstance(result.dominant_axis, RadarAxis)

    def test_confidence_not_pre_rounded(self):
        """Confidence stored as raw float; to_dict() rounds."""
        radar = make_radar(fighting=4.5, stability=2.5)
        result = determine_style(radar, {MeaningTagId.OVERPLAY: 3})
        assert isinstance(result.confidence, float)
        d = result.to_dict()
        assert d["confidence"] == round(result.confidence, 2)


# =============================================================================
# Archetype-Specific Tests
# =============================================================================


class TestArchetypeSpecific:
    """Tests for specific archetype detection."""

    def test_cosmic_architect_high_opening_low_endgame(self):
        """High OPENING + low ENDGAME -> COSMIC_ARCHITECT."""
        # Mean = (4.5+3.0+2.0+3.0+3.0)/5 = 3.1
        radar = make_radar(opening=4.5, endgame=2.0)
        result = determine_style(radar, {MeaningTagId.DIRECTION_ERROR: 3})
        assert result.archetype.id == StyleArchetypeId.COSMIC_ARCHITECT

    def test_precision_machine_high_endgame_low_fighting(self):
        """High ENDGAME + low FIGHTING -> PRECISION_MACHINE."""
        radar = make_radar(endgame=4.5, fighting=2.0)
        result = determine_style(radar, {MeaningTagId.TERRITORIAL_LOSS: 3})
        assert result.archetype.id == StyleArchetypeId.PRECISION_MACHINE

    def test_shinobi_survivor_high_stability_low_opening(self):
        """High STABILITY + low OPENING -> SHINOBI_SURVIVOR."""
        radar = make_radar(stability=4.5, opening=2.0)
        result = determine_style(radar, {MeaningTagId.SHAPE_MISTAKE: 3})
        assert result.archetype.id == StyleArchetypeId.SHINOBI_SURVIVOR

    def test_ai_native_high_awareness(self):
        """High AWARENESS -> AI_NATIVE (no low axis requirement)."""
        # Mean = (3.0+3.0+3.0+3.0+4.5)/5 = 3.3
        radar = make_radar(awareness=4.5)
        result = determine_style(radar, {})
        assert result.archetype.id == StyleArchetypeId.AI_NATIVE


# =============================================================================
# StyleResult.to_dict() Tests
# =============================================================================


class TestStyleResultToDict:
    """Tests for StyleResult.to_dict() serialization."""

    def test_to_dict_structure(self):
        """to_dict returns expected structure."""
        result = determine_style(make_radar(fighting=4.5), {})
        d = result.to_dict()

        assert "archetype_id" in d
        assert "confidence" in d
        assert "axis_deviations" in d
        assert "dominant_axis" in d

    def test_to_dict_archetype_id_is_string(self):
        """archetype_id in to_dict is string value."""
        result = determine_style(make_radar(fighting=4.5), {})
        d = result.to_dict()
        assert isinstance(d["archetype_id"], str)

    def test_to_dict_axis_deviations_keys_are_strings(self):
        """axis_deviations keys in to_dict are string values."""
        result = determine_style(make_radar(), {})
        d = result.to_dict()
        for key in d["axis_deviations"].keys():
            assert isinstance(key, str)

    def test_to_dict_confidence_rounded(self):
        """confidence in to_dict is rounded to 2 decimals."""
        radar = make_radar(fighting=4.5, stability=2.5)
        result = determine_style(radar, {MeaningTagId.OVERPLAY: 3})
        d = result.to_dict()
        # Check it's rounded (no more than 2 decimal places)
        assert d["confidence"] == round(d["confidence"], 2)

    def test_to_dict_deviations_rounded(self):
        """axis_deviations in to_dict are rounded to 3 decimals."""
        result = determine_style(make_radar(fighting=4.5), {})
        d = result.to_dict()
        for value in d["axis_deviations"].values():
            assert value == round(value, 3)


# =============================================================================
# Registry Tests
# =============================================================================


class TestStyleArchetypesRegistry:
    """Tests for STYLE_ARCHETYPES registry."""

    def test_registry_has_all_archetypes(self):
        """Registry contains all 6 archetypes."""
        assert len(STYLE_ARCHETYPES) == 6
        for archetype_id in StyleArchetypeId:
            assert archetype_id in STYLE_ARCHETYPES

    def test_registry_archetypes_are_frozen(self):
        """All archetypes in registry are frozen dataclasses."""
        for archetype in STYLE_ARCHETYPES.values():
            # frozen dataclass raises FrozenInstanceError on assignment
            with pytest.raises(Exception):  # FrozenInstanceError
                archetype.id = StyleArchetypeId.BALANCE_MASTER  # type: ignore

    def test_balance_master_has_no_requirements(self):
        """BALANCE_MASTER has empty high_axes, low_axes, reinforcing_tags."""
        balance = STYLE_ARCHETYPES[StyleArchetypeId.BALANCE_MASTER]
        assert len(balance.high_axes) == 0
        assert len(balance.low_axes) == 0
        assert len(balance.reinforcing_tags) == 0
