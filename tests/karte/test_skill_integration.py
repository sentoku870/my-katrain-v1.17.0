"""Skill-preset and weakness-hypothesis integration tests (Phase E-1).

Extracted from tests/test_karte_structure.py. Covers the urgent-miss
configuration per skill level, the weakness-hypothesis generation
pipeline, and label/threshold consistency across skill levels.

Phase 237: added ``TestWeaknessesMetaFor`` for the O(N+M) refactor of
``katrain.core.reports.karte.json_export._weaknesses_meta_for``.
"""

from __future__ import annotations

from dataclasses import dataclass

from katrain.core.analysis import aggregate_phase_mistake_stats
from katrain.core.analysis.models.move_eval import MoveEval

# ---------------------------------------------------------------------------
# Phase 237 test helpers
# ---------------------------------------------------------------------------


def _make_mistake_category(name: str):
    """Build a ``MistakeCategory`` enum member by name (e.g. ``"MISTAKE"``)."""
    from katrain.core.analysis.models.enums import MistakeCategory

    return MistakeCategory[name]


@dataclass
class _FakeSnapshot:
    """Minimal stand-in for ``EvalSnapshot`` carrying only ``moves``."""

    moves: list[MoveEval]


@dataclass
class _FakeCtx:
    """Minimal stand-in for ``KarteContext`` carrying the fields
    ``_weaknesses_meta_for`` actually reads."""

    snapshot: _FakeSnapshot
    board_x: int = 19


def _make_ctx(*moves: MoveEval) -> _FakeCtx:
    """Wrap a list of moves in a context shaped like the production one."""
    return _FakeCtx(snapshot=_FakeSnapshot(moves=list(moves)))


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


class TestWeaknessesMetaFor:
    """Phase 237: ``_weaknesses_meta_for`` must produce identical results
    to the legacy O(N×M) implementation while running in O(N+M) time.

    The function is purely about coverage accounting: how many of the
    player's non-zero-loss moves landed in a (phase, category) bucket
    that the weakness aggregation surfaced, and how much loss those
    covered moves carry. The output shape is part of the Karte v3.x
    JSON contract (see ``docs/karte-schema.md``)
    so the refactor must be a pure speed-up.
    """

    @staticmethod
    def _make_move(move_number: int, player: str, loss: float, mistake_category_name: str = "MISTAKE"):
        """Build a minimal ``MoveEval``-shaped object for the test."""
        from katrain.core.analysis.models.move_eval import MoveEval

        return MoveEval(
            move_number=move_number,
            player=player,
            gtp="D4",
            score_before=0.0,
            score_after=-loss,
            delta_score=-loss,
            winrate_before=0.5,
            winrate_after=0.45,
            delta_winrate=-0.05,
            points_lost=loss,
            realized_points_lost=None,
            root_visits=100,
            mistake_category=_make_mistake_category(mistake_category_name),
        )

    def test_empty_weaknesses_returns_zero_coverage(self):
        """When no weakness items are emitted, every metric is zero / 0.0."""
        from katrain.core.reports.karte.json_export import _weaknesses_meta_for

        ctx = _make_ctx(self._make_move(1, "B", loss=2.0))
        result = _weaknesses_meta_for(ctx, "B", weakness_items=[])
        assert result["covered_count"] == 0
        assert result["total_count"] == 1
        assert result["coverage_pct"] == 0.0
        assert result["covered_loss"] == 0.0
        assert result["total_loss"] == 2.0
        assert result["loss_coverage_pct"] == 0.0

    def test_all_moves_covered(self):
        """All non-zero-loss moves match the weakness buckets."""
        from katrain.core.reports.karte.json_export import _weaknesses_meta_for

        # Move numbers 60/70 are firmly in the "middle" band (50 < n ≤ 200)
        # so the bucket ``(middle, MISTAKE)`` covers both.
        moves = [
            self._make_move(60, "B", loss=3.0, mistake_category_name="MISTAKE"),
            self._make_move(70, "B", loss=4.0, mistake_category_name="MISTAKE"),
        ]
        ctx = _make_ctx(*moves)
        result = _weaknesses_meta_for(
            ctx,
            "B",
            weakness_items=[{"phase": "middle", "category": "MISTAKE"}],
        )
        assert result["covered_count"] == 2
        assert result["total_count"] == 2
        assert result["coverage_pct"] == 100.0
        assert result["covered_loss"] == 7.0
        assert result["total_loss"] == 7.0
        assert result["loss_coverage_pct"] == 100.0

    def test_partial_coverage(self):
        """Only the moves that match a weakness bucket count toward coverage."""
        from katrain.core.reports.karte.json_export import _weaknesses_meta_for

        moves = [
            # 2 in the "middle:mistake" bucket
            self._make_move(60, "B", loss=3.0, mistake_category_name="MISTAKE"),
            self._make_move(70, "B", loss=2.0, mistake_category_name="MISTAKE"),
            # 1 in a different bucket
            self._make_move(80, "B", loss=5.0, mistake_category_name="BLUNDER"),
        ]
        ctx = _make_ctx(*moves)
        result = _weaknesses_meta_for(
            ctx,
            "B",
            weakness_items=[{"phase": "middle", "category": "MISTAKE"}],
        )
        # 2 of 3 non-zero-loss moves are covered
        assert result["covered_count"] == 2
        assert result["total_count"] == 3
        assert result["coverage_pct"] == round(100.0 * 2 / 3, 1)
        assert result["covered_loss"] == 5.0
        assert result["total_loss"] == 10.0
        assert result["loss_coverage_pct"] == 50.0

    def test_phase_classification_opens_at_low_move_numbers(self):
        """Phase boundary at move 50: the function must use the same
        classifier as ``weakness_hypothesis_for`` so coverage matches
        the buckets actually emitted."""
        from katrain.core.reports.karte.json_export import _weaknesses_meta_for

        moves = [
            self._make_move(10, "B", loss=2.0, mistake_category_name="MISTAKE"),  # opening
            self._make_move(60, "B", loss=3.0, mistake_category_name="MISTAKE"),  # middle
        ]
        ctx = _make_ctx(*moves)
        # Only the middle move is in the bucket.
        result = _weaknesses_meta_for(
            ctx,
            "B",
            weakness_items=[{"phase": "middle", "category": "MISTAKE"}],
        )
        assert result["covered_count"] == 1
        assert result["covered_loss"] == 3.0

    def test_zero_loss_moves_excluded_from_denominator(self):
        """Moves with ``points_lost=None`` or below the threshold must not
        inflate the denominator or the total_loss."""
        from katrain.core.reports.karte.json_export import _weaknesses_meta_for

        # Move 20 (opening) has loss 0.0 → excluded.
        # Move 60 (middle)  has loss 4.0 → included, matches the bucket.
        moves = [
            self._make_move(20, "B", loss=0.0, mistake_category_name="GOOD"),
            self._make_move(60, "B", loss=4.0, mistake_category_name="MISTAKE"),
        ]
        ctx = _make_ctx(*moves)
        result = _weaknesses_meta_for(
            ctx,
            "B",
            weakness_items=[{"phase": "middle", "category": "MISTAKE"}],
        )
        # Only the second move counts in the denominator.
        assert result["total_count"] == 1
        assert result["total_loss"] == 4.0
        assert result["covered_count"] == 1
        assert result["covered_loss"] == 4.0

    def test_handles_large_loss_moves_efficiently(self):
        """Smoke test: with many loss moves the refactor must complete
        without quadratic blow-up. The exact coverage numbers are
        irrelevant — we only assert the function returns the correct
        total_count and that coverage is bounded by [0, 1].
        """
        from katrain.core.reports.karte.json_export import _weaknesses_meta_for

        # 150 non-zero-loss moves + 1 weakness bucket.
        # All moves are in the 51..200 range → all "middle" phase
        # (board_size=19 default, middle_end=200, inclusive).
        moves = [self._make_move(i, "B", loss=2.0, mistake_category_name="MISTAKE") for i in range(51, 201)]
        ctx = _make_ctx(*moves)
        result = _weaknesses_meta_for(
            ctx,
            "B",
            weakness_items=[{"phase": "middle", "category": "MISTAKE"}],
        )
        assert result["total_count"] == 150
        assert result["covered_count"] == 150
        assert result["coverage_pct"] == 100.0
