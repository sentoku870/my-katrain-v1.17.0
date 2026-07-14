"""Skill-preset and weakness-hypothesis integration tests (Phase E-1).

Extracted from tests/test_karte_structure.py. Covers the urgent-miss
configuration per skill level, the weakness-hypothesis generation
pipeline, and label/threshold consistency across skill levels.
"""

from __future__ import annotations

from katrain.core.analysis.models.move_eval import MoveEval
from katrain.core.analysis import aggregate_phase_mistake_stats


class TestUrgentMissConfigsIntegration:
    """Tests for URGENT_MISS_CONFIGS usage."""

    def test_get_urgent_miss_config_all_presets(self):
        """All skill presets should have urgent miss configs."""
        from katrain.core.analysis import PRESET_ORDER, get_urgent_miss_config
        for preset in PRESET_ORDER:
            config = get_urgent_miss_config(preset)
            assert config is not None
            assert config.threshold_loss > 0
            assert config.min_consecutive >= 2

    def test_urgent_miss_threshold_varies_by_preset(self):
        """Stricter presets should have lower thresholds."""
        from katrain.core.analysis import get_urgent_miss_config
        relaxed = get_urgent_miss_config("relaxed")
        standard = get_urgent_miss_config("standard")
        pro = get_urgent_miss_config("pro")

        # Stricter presets have lower threshold (detect smaller losses)
        assert relaxed.threshold_loss > standard.threshold_loss
        assert standard.threshold_loss > pro.threshold_loss


class TestWeaknessHypothesisSkillPreset:
    """Tests for weakness_hypothesis_for using skill_preset thresholds."""

    def test_aggregate_uses_score_thresholds(self):
        """aggregate_phase_mistake_stats should respect custom thresholds."""
        from katrain.core.analysis import get_skill_preset
        # Create a move with 3.0 loss
        move = MoveEval(
            move_number=100,
            player="B",
            gtp="D4",
            score_before=0.0,
            score_after=-3.0,
            delta_score=-3.0,
            winrate_before=0.5,
            winrate_after=0.45,
            delta_winrate=-0.05,
            points_lost=3.0,
            realized_points_lost=None,
            root_visits=100,
        )

        # Standard: thresholds [1.0, 2.5, 5.0] -> 3.0 is MISTAKE
        standard = get_skill_preset("standard")
        stats_standard = aggregate_phase_mistake_stats([move], score_thresholds=standard.score_thresholds)

        # Beginner: thresholds [2.0, 5.0, 10.0] -> 3.0 is INACCURACY
        beginner = get_skill_preset("beginner")
        stats_beginner = aggregate_phase_mistake_stats([move], score_thresholds=beginner.score_thresholds)

        # Verify classification differs based on thresholds
        assert ("middle", "MISTAKE") in stats_standard.phase_mistake_counts
        assert ("middle", "INACCURACY") in stats_beginner.phase_mistake_counts

    def test_preset_thresholds_consistency(self):
        """Verify preset threshold values are as documented."""
        from katrain.core.analysis import get_skill_preset
        standard = get_skill_preset("standard")
        assert standard.score_thresholds == (1.0, 2.5, 5.0)

        beginner = get_skill_preset("beginner")
        assert beginner.score_thresholds == (2.0, 5.0, 10.0)

        pro = get_skill_preset("pro")
        assert pro.score_thresholds == (0.2, 0.5, 1.0)


# ==============================================================================
# PR#2 Tests: Label-Threshold Consistency Fix
# ==============================================================================


class TestLabelThresholdConsistency:
    """Regression tests for PR#2: Labels must match selected preset thresholds.

    Bug: Summary and Important Moves used default "standard" thresholds
    regardless of the selected strictness preset, while Definitions showed
    the correct preset-specific thresholds.

    Fix: Pass effective_thresholds to mistake_label_from_loss() everywhere.
    """

    def test_lenient_thresholds_classify_correctly(self):
        """Under relaxed thresholds, 3.7 should be inaccuracy, 12.7 should be mistake."""
        from katrain.core.analysis import classify_mistake, get_skill_preset
        relaxed = get_skill_preset("relaxed")
        # relaxed thresholds: (3.0, 7.5, 15.0)
        assert relaxed.score_thresholds == (3.0, 7.5, 15.0)

        # 3.7 loss under relaxed: 3.0 <= 3.7 < 7.5 → INACCURACY
        result = classify_mistake(score_loss=3.7, winrate_loss=None, score_thresholds=relaxed.score_thresholds)
        assert result.value == "inaccuracy"

        # 12.7 loss under relaxed: 7.5 <= 12.7 < 15.0 → MISTAKE (not BLUNDER)
        result = classify_mistake(score_loss=12.7, winrate_loss=None, score_thresholds=relaxed.score_thresholds)
        assert result.value == "mistake"

    def test_strict_thresholds_classify_correctly(self):
        """Under pro thresholds, 3.9 should be blunder."""
        from katrain.core.analysis import classify_mistake, get_skill_preset
        pro = get_skill_preset("pro")
        # pro thresholds: (0.2, 0.5, 1.0)
        assert pro.score_thresholds == (0.2, 0.5, 1.0)

        # 3.9 loss under pro: 3.9 >= 1.0 → BLUNDER
        result = classify_mistake(score_loss=3.9, winrate_loss=None, score_thresholds=pro.score_thresholds)
        assert result.value == "blunder"

    def test_same_loss_differs_by_preset(self):
        """Same loss value should classify differently under different presets."""
        from katrain.core.analysis import classify_mistake, get_skill_preset
        standard = get_skill_preset("standard")  # (1.0, 2.5, 5.0)
        relaxed = get_skill_preset("relaxed")  # (3.0, 7.5, 15.0)

        loss = 3.0

        # Under standard: 2.5 <= 3.0 < 5.0 → MISTAKE
        standard_result = classify_mistake(
            score_loss=loss, winrate_loss=None, score_thresholds=standard.score_thresholds
        )

        # Under relaxed: 3.0 <= 3.0 < 7.5 → INACCURACY
        relaxed_result = classify_mistake(score_loss=loss, winrate_loss=None, score_thresholds=relaxed.score_thresholds)

        assert standard_result.value == "mistake"
        assert relaxed_result.value == "inaccuracy"

    def test_boundary_values(self):
        """Test classification at exact threshold boundaries."""
        from katrain.core.analysis import classify_mistake, get_skill_preset
        standard = get_skill_preset("standard")  # (1.0, 2.5, 5.0)

        # At exactly t1 (1.0): should be INACCURACY (>= t1)
        result = classify_mistake(score_loss=1.0, winrate_loss=None, score_thresholds=standard.score_thresholds)
        assert result.value == "inaccuracy"

        # Just below t1 (0.99): should be GOOD
        result = classify_mistake(score_loss=0.99, winrate_loss=None, score_thresholds=standard.score_thresholds)
        assert result.value == "good"

        # At exactly t3 (5.0): should be BLUNDER (>= t3)
        result = classify_mistake(score_loss=5.0, winrate_loss=None, score_thresholds=standard.score_thresholds)
        assert result.value == "blunder"

        # Just below t3 (4.99): should be MISTAKE
        result = classify_mistake(score_loss=4.99, winrate_loss=None, score_thresholds=standard.score_thresholds)
        assert result.value == "mistake"

    def test_none_loss_returns_good(self):
        """None loss should return GOOD (not error or unknown)."""
        from katrain.core.analysis import classify_mistake, get_skill_preset
        standard = get_skill_preset("standard")

        result = classify_mistake(score_loss=None, winrate_loss=None, score_thresholds=standard.score_thresholds)
        assert result.value == "good"
