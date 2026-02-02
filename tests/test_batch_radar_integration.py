"""Tests for Phase 49: Batch Radar Integration.

Test coverage:
- extract_game_stats radar computation
- build_player_summary Skill Profile section
- Practice priorities from radar
- JSON output validation

Test priority:
- P0: Critical - must pass for module to be usable
- P1: Important - covers edge cases and integration
- P2: Nice to have - comprehensive coverage
"""

import json
from types import MappingProxyType, SimpleNamespace

import pytest

from katrain.core.analysis.models import MistakeCategory, PositionDifficulty
from katrain.core.analysis.skill_radar import (
    RadarAxis,
    RadarMetrics,
    SkillTier,
    AggregatedRadarResult,
    MIN_MOVES_FOR_RADAR,
    radar_from_dict,
    aggregate_radar,
    round_score,
)
from katrain.core.batch.stats import (
    _build_skill_profile_section,
    _build_radar_json_section,
    TIER_LABELS,
    AXIS_LABELS,
    AXIS_PRACTICE_HINTS,
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


def make_aggregated_result(
    opening: float | None = 4.0,
    fighting: float | None = 3.0,
    endgame: float | None = 2.0,
    stability: float | None = 4.5,
    awareness: float | None = 3.5,
    opening_tier: SkillTier = SkillTier.TIER_4,
    fighting_tier: SkillTier = SkillTier.TIER_3,
    endgame_tier: SkillTier = SkillTier.TIER_2,
    stability_tier: SkillTier = SkillTier.TIER_5,
    awareness_tier: SkillTier = SkillTier.TIER_4,
    overall_tier: SkillTier = SkillTier.TIER_4,
    games_aggregated: int = 5,
) -> AggregatedRadarResult:
    """Create an AggregatedRadarResult instance for testing."""
    valid_move_counts = {
        RadarAxis.OPENING: 225,
        RadarAxis.FIGHTING: 98,
        RadarAxis.ENDGAME: 150,
        RadarAxis.STABILITY: 612,
        RadarAxis.AWARENESS: 487,
    }
    return AggregatedRadarResult(
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
        games_aggregated=games_aggregated,
    )


# =============================================================================
# P0: Skill Profile Section Tests
# =============================================================================


class TestSkillProfileSection:
    """P0: Test _build_skill_profile_section() function."""

    def test_summary_skill_profile_present(self):
        """Section header '## Skill Profile' present."""
        radar = make_aggregated_result()
        lines = _build_skill_profile_section(radar, lang="en")

        assert any("## Skill Profile" in line for line in lines)

    def test_summary_skill_profile_no_radar_shows_section(self):
        """Section shown with placeholder message when no radar."""
        lines = _build_skill_profile_section(None, lang="en")

        assert any("## Skill Profile" in line for line in lines)
        assert any("No radar data available" in line for line in lines)

    def test_summary_overall_tier_display(self):
        """Overall tier is displayed."""
        radar = make_aggregated_result(overall_tier=SkillTier.TIER_4)
        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        assert "Tier 4" in content

    def test_summary_games_aggregated_display(self):
        """Games aggregated count is displayed."""
        radar = make_aggregated_result(games_aggregated=7)
        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        assert "7 games" in content

    def test_summary_axis_na_display(self):
        """None score shows 'N/A'."""
        radar = make_aggregated_result(
            endgame=None,
            endgame_tier=SkillTier.TIER_UNKNOWN,
        )
        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        # The Endgame row should have N/A
        assert "N/A" in content

    def test_summary_table_format(self):
        """Table has correct headers."""
        radar = make_aggregated_result()
        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        assert "| Axis | Score | Tier | Moves |" in content

    def test_summary_table_uses_round_score(self):
        """Table scores match round_score() output."""
        radar = make_aggregated_result(opening=4.25)  # Should round to 4.3
        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        # round_score(4.25) = 4.3
        assert "4.3" in content


# =============================================================================
# P0: Weak Axes Tests
# =============================================================================


class TestWeakAxes:
    """P0: Test weak axis detection and display."""

    def test_summary_weak_axes_displayed(self):
        """Weak axes (score < 2.5) are listed."""
        radar = make_aggregated_result(
            fighting=2.2,
            fighting_tier=SkillTier.TIER_2,
        )
        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        assert "Weak areas" in content
        assert "Fighting" in content

    def test_summary_weak_axes_uses_raw_score(self):
        """2.45 raw flagged as weak (not rounded first)."""
        radar = make_aggregated_result(
            endgame=2.45,  # Raw is < 2.5, rounds to 2.5 for display
            endgame_tier=SkillTier.TIER_2,
        )
        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        # Should be listed as weak because 2.45 < 2.5
        assert "Weak areas" in content
        assert "Endgame" in content

    def test_summary_weak_axes_sorted_by_score(self):
        """Weak axes sorted by score (lowest first)."""
        radar = make_aggregated_result(
            opening=2.3,
            fighting=1.5,  # Lower
            endgame=2.4,
            opening_tier=SkillTier.TIER_2,
            fighting_tier=SkillTier.TIER_1,
            endgame_tier=SkillTier.TIER_2,
        )
        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        # Find the weak areas line
        weak_line = None
        for line in lines:
            if "Weak areas" in line:
                weak_line = line
                break

        assert weak_line is not None
        # Fighting (1.5) should come before Opening (2.3) and Endgame (2.4)
        fighting_pos = weak_line.find("Fighting")
        opening_pos = weak_line.find("Opening")
        endgame_pos = weak_line.find("Endgame")
        assert fighting_pos < opening_pos < endgame_pos


# =============================================================================
# P1: Practice Priorities Tests
# =============================================================================


class TestPracticePriorities:
    """P1: Test practice priorities from radar."""

    def test_summary_practice_priorities_radar(self):
        """Weak axes appear in practice priorities."""
        radar = make_aggregated_result(
            fighting=2.0,
            fighting_tier=SkillTier.TIER_2,
        )
        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        # Phase 54: English output with lang="en"
        assert "Practice priorities:" in content
        # Should have hint for fighting
        assert AXIS_PRACTICE_HINTS[RadarAxis.FIGHTING] in content

    def test_summary_practice_priorities_max_2(self):
        """At most 2 radar-based priorities."""
        radar = make_aggregated_result(
            opening=1.0,
            fighting=1.5,
            endgame=2.0,
            opening_tier=SkillTier.TIER_1,
            fighting_tier=SkillTier.TIER_1,
            endgame_tier=SkillTier.TIER_2,
        )
        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        # Count practice priority items (Phase 53: Japanese header)
        priority_count = content.count("練習の優先順位")
        hint_count = sum(1 for hint in AXIS_PRACTICE_HINTS.values() if hint in content)
        # Should have max 2 hints
        assert hint_count <= 2


# =============================================================================
# P1: JSON Output Tests
# =============================================================================


class TestRadarJsonOutput:
    """P1: Test JSON output block."""

    def test_summary_json_block_valid(self):
        """JSON parses correctly."""
        radar = make_aggregated_result()
        lines = _build_radar_json_section(radar)

        # Find JSON block
        json_content = None
        in_json = False
        json_lines = []
        for line in lines:
            if line.strip() == "```json":
                in_json = True
                continue
            if line.strip() == "```":
                in_json = False
                break
            if in_json:
                json_lines.append(line)

        assert json_lines, "No JSON content found"
        json_content = "\n".join(json_lines)

        # Should parse without error
        parsed = json.loads(json_content)
        assert parsed is not None

    def test_summary_json_matches_to_dict(self):
        """JSON block == json.dumps(radar.to_dict())."""
        radar = make_aggregated_result()
        lines = _build_radar_json_section(radar)

        # Find JSON block
        in_json = False
        json_lines = []
        for line in lines:
            if line.strip() == "```json":
                in_json = True
                continue
            if line.strip() == "```":
                in_json = False
                break
            if in_json:
                json_lines.append(line)

        json_content = "\n".join(json_lines)
        parsed = json.loads(json_content)

        # Should match to_dict()
        assert parsed == radar.to_dict()

    def test_summary_json_rounding_consistent(self):
        """JSON scores match table scores (both use round_score)."""
        radar = make_aggregated_result(opening=4.25)  # Rounds to 4.3
        lines = _build_radar_json_section(radar)

        # Find JSON block
        in_json = False
        json_lines = []
        for line in lines:
            if line.strip() == "```json":
                in_json = True
                continue
            if line.strip() == "```":
                in_json = False
                break
            if in_json:
                json_lines.append(line)

        json_content = "\n".join(json_lines)
        parsed = json.loads(json_content)

        # Opening score should be rounded
        assert parsed["axes"]["opening"]["score"] == 4.3

    def test_summary_json_no_radar_returns_empty(self):
        """No radar returns empty list."""
        lines = _build_radar_json_section(None)
        assert lines == []


# =============================================================================
# P2: Constants Tests
# =============================================================================


class TestRadarIntegrationConstants:
    """P2: Test radar integration constants."""

    def test_tier_labels_complete(self):
        """All tiers have labels."""
        for tier in SkillTier:
            assert tier in TIER_LABELS

    def test_axis_labels_complete(self):
        """All axes have labels."""
        for axis in RadarAxis:
            assert axis in AXIS_LABELS

    def test_axis_practice_hints_complete(self):
        """All axes have practice hints."""
        for axis in RadarAxis:
            assert axis in AXIS_PRACTICE_HINTS
            assert len(AXIS_PRACTICE_HINTS[axis]) > 0


# =============================================================================
# P2: Edge Cases
# =============================================================================


class TestRadarIntegrationEdgeCases:
    """P2: Test edge cases for radar integration."""

    def test_all_axes_unknown(self):
        """All axes UNKNOWN still shows section."""
        radar = AggregatedRadarResult(
            opening=None,
            fighting=None,
            endgame=None,
            stability=None,
            awareness=None,
            opening_tier=SkillTier.TIER_UNKNOWN,
            fighting_tier=SkillTier.TIER_UNKNOWN,
            endgame_tier=SkillTier.TIER_UNKNOWN,
            stability_tier=SkillTier.TIER_UNKNOWN,
            awareness_tier=SkillTier.TIER_UNKNOWN,
            overall_tier=SkillTier.TIER_UNKNOWN,
            valid_move_counts=MappingProxyType({axis: 0 for axis in RadarAxis}),
            games_aggregated=1,
        )

        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        assert "## Skill Profile" in content
        # Should show N/A for all axes
        assert content.count("N/A") >= 5

    def test_no_weak_axes(self):
        """No weak axes means no weak areas section."""
        radar = make_aggregated_result(
            opening=4.0,
            fighting=3.5,
            endgame=3.0,
            stability=4.5,
            awareness=4.0,
        )

        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        # Should not have weak areas section
        assert "Weak areas" not in content

    def test_single_weak_axis(self):
        """Single weak axis shows correctly."""
        radar = make_aggregated_result(
            opening=4.0,
            fighting=2.0,  # Only weak one
            endgame=3.0,
            stability=4.5,
            awareness=4.0,
            fighting_tier=SkillTier.TIER_2,
        )

        lines = _build_skill_profile_section(radar, lang="en")

        content = "\n".join(lines)
        assert "Weak areas" in content
        assert "Fighting" in content
        # Should only have one practice priority
        assert AXIS_PRACTICE_HINTS[RadarAxis.FIGHTING] in content
