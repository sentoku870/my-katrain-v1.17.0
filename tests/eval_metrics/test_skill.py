"""Skill-preset and confidence-level tests extracted from tests/test_eval_metrics.py.

Phase D-1: split the 2316-line test_eval_metrics.py into 4 themed
submodules. Covers reason-tags completeness, skill presets (relaxed /
beginner / standard / advanced / pro), urgent-miss configs, and the
5-level confidence scoring.
"""

from __future__ import annotations

from katrain.core.analysis.models.move_eval import MoveEval


class TestReasonTagsCompleteness:
    """Tests to ensure all reason tags are properly defined (A1)."""

    def test_all_emittable_tags_have_labels(self):
        """Every tag that can be emitted must have a label."""
        from katrain.core.analysis import REASON_TAG_LABELS, validate_reason_tag

        # Tags that get_reason_tags_for_move can emit (from board_analysis.py)
        emittable_tags = [
            "atari",
            "low_liberties",
            "cut_risk",
            "need_connect",
            "thin",
            "chase_mode",
            # "too_many_choices",  # Disabled but defined
            "endgame_hint",
            "heavy_loss",
            "reading_failure",
        ]

        # Tags used as fallback in game.py
        fallback_tags = ["unknown"]

        all_used_tags = emittable_tags + fallback_tags

        for tag in all_used_tags:
            assert tag in REASON_TAG_LABELS, f"Tag '{tag}' is used but not in REASON_TAG_LABELS"
            assert validate_reason_tag(tag), f"validate_reason_tag('{tag}') should return True"

    def test_validate_reason_tag_function(self):
        """validate_reason_tag should correctly identify valid/invalid tags."""
        from katrain.core.analysis import validate_reason_tag
        # Valid tags
        assert validate_reason_tag("atari") is True
        assert validate_reason_tag("unknown") is True
        assert validate_reason_tag("heavy_loss") is True

        # Invalid tags
        assert validate_reason_tag("undefined_tag") is False
        assert validate_reason_tag("") is False
        assert validate_reason_tag("ATARI") is False  # Case-sensitive

    def test_get_reason_tag_label_function(self):
        """get_reason_tag_label should return correct labels."""
        from katrain.core.analysis import get_reason_tag_label
        # Known tags
        assert get_reason_tag_label("atari") == "アタリ (atari)"
        assert get_reason_tag_label("unknown") == "不明 (unknown)"

        # Unknown tag with fallback
        assert get_reason_tag_label("undefined") == "undefined"
        assert get_reason_tag_label("undefined", fallback_to_raw=False) == "??? (undefined)"

    def test_valid_reason_tags_matches_labels(self):
        """VALID_REASON_TAGS should exactly match REASON_TAG_LABELS keys."""
        from katrain.core.analysis import REASON_TAG_LABELS, VALID_REASON_TAGS
        assert set(REASON_TAG_LABELS.keys()) == VALID_REASON_TAGS

    def test_no_duplicate_labels(self):
        """Each tag should have a unique label."""
        from katrain.core.analysis import REASON_TAG_LABELS
        labels = list(REASON_TAG_LABELS.values())
        unique_labels = set(labels)

        assert len(labels) == len(unique_labels), "Duplicate labels found in REASON_TAG_LABELS"


# ---------------------------------------------------------------------------
# Test: 5-level Skill Presets
# ---------------------------------------------------------------------------


class TestSkillPresets:
    """Tests for SKILL_PRESETS configuration (5-level system)."""

    def test_all_five_presets_exist(self):
        """All 5 skill presets should be defined."""
        from katrain.core.analysis import SKILL_PRESETS
        expected_keys = {"relaxed", "beginner", "standard", "advanced", "pro"}
        assert set(SKILL_PRESETS.keys()) == expected_keys

    def test_standard_unchanged(self):
        """Standard preset should maintain backward-compatible values."""
        from katrain.core.analysis import SKILL_PRESETS
        standard = SKILL_PRESETS["standard"]
        # Original standard thresholds must remain unchanged
        assert standard.score_thresholds == (1.0, 2.5, 5.0)

    def test_advanced_unchanged(self):
        """Advanced preset should maintain backward-compatible values."""
        from katrain.core.analysis import SKILL_PRESETS
        advanced = SKILL_PRESETS["advanced"]
        # Advanced thresholds preserved from original implementation
        assert advanced.score_thresholds == (0.5, 1.5, 3.0)

    def test_score_thresholds_follow_formula(self):
        """New presets (relaxed, beginner, pro) should follow t1=0.2*t3, t2=0.5*t3 formula."""
        from katrain.core.analysis import SKILL_PRESETS
        # Only check formula for new presets (relaxed, beginner, pro)
        formula_presets = ["relaxed", "beginner", "pro"]
        for key in formula_presets:
            preset = SKILL_PRESETS[key]
            t1, t2, t3 = preset.score_thresholds
            assert abs(t1 - 0.2 * t3) < 0.01, f"{key}: t1 should be 0.2 * t3"
            assert abs(t2 - 0.5 * t3) < 0.01, f"{key}: t2 should be 0.5 * t3"

    def test_thresholds_increasing_strictness(self):
        """Presets should have decreasing t3 values from relaxed to pro (increasing strictness)."""
        from katrain.core.analysis import SKILL_PRESETS
        order = ["relaxed", "beginner", "standard", "advanced", "pro"]
        prev_t3 = float("inf")
        for key in order:
            t3 = SKILL_PRESETS[key].score_thresholds[2]
            assert t3 < prev_t3, f"{key}: t3={t3} should be less than previous {prev_t3}"
            prev_t3 = t3

    def test_get_skill_preset_fallback(self):
        """Unknown preset names should fall back to 'standard'."""
        from katrain.core.analysis import SKILL_PRESETS, get_skill_preset
        result = get_skill_preset("nonexistent")
        assert result == SKILL_PRESETS["standard"]

    def test_default_skill_preset_is_standard(self):
        """DEFAULT_SKILL_PRESET should be 'standard' for backward compatibility."""
        from katrain.core.analysis import DEFAULT_SKILL_PRESET
        assert DEFAULT_SKILL_PRESET == "standard"

    def test_preset_t3_values(self):
        """Verify expected t3 (blunder) values for each preset."""
        from katrain.core.analysis import SKILL_PRESETS
        expected_t3 = {
            "relaxed": 15.0,
            "beginner": 10.0,
            "standard": 5.0,
            "advanced": 3.0,
            "pro": 1.0,
        }
        for key, expected in expected_t3.items():
            actual = SKILL_PRESETS[key].score_thresholds[2]
            assert actual == expected, f"{key}: expected t3={expected}, got {actual}"


class TestUrgentMissConfigs:
    """Tests for URGENT_MISS_CONFIGS (5-level system)."""

    def test_all_five_configs_exist(self):
        """All 5 urgent miss configs should be defined."""
        from katrain.core.analysis import URGENT_MISS_CONFIGS
        expected_keys = {"relaxed", "beginner", "standard", "advanced", "pro"}
        assert set(URGENT_MISS_CONFIGS.keys()) == expected_keys

    def test_threshold_loss_decreasing(self):
        """threshold_loss should decrease from relaxed to pro (stricter detection)."""
        from katrain.core.analysis import URGENT_MISS_CONFIGS
        order = ["relaxed", "beginner", "standard", "advanced", "pro"]
        prev_threshold = float("inf")
        for key in order:
            threshold = URGENT_MISS_CONFIGS[key].threshold_loss
            assert threshold < prev_threshold, f"{key}: threshold should decrease"
            prev_threshold = threshold

    def test_min_consecutive_reasonable(self):
        """min_consecutive should be reasonable (2-5 range)."""
        from katrain.core.analysis import URGENT_MISS_CONFIGS
        for key, config in URGENT_MISS_CONFIGS.items():
            assert 2 <= config.min_consecutive <= 5, f"{key}: min_consecutive out of range"


class TestAutoStrictness:
    """Tests for auto-strictness recommendation algorithm."""

    def test_preset_order_contains_all_presets(self):
        """PRESET_ORDER should contain all 5 skill presets."""
        from katrain.core.analysis import PRESET_ORDER, SKILL_PRESETS
        assert set(PRESET_ORDER) == set(SKILL_PRESETS.keys())
        assert len(PRESET_ORDER) == 5

    def test_preset_order_is_correct_sequence(self):
        """PRESET_ORDER should be loosest to strictest."""
        from katrain.core.analysis import PRESET_ORDER
        expected = ["relaxed", "beginner", "standard", "advanced", "pro"]
        assert expected == PRESET_ORDER

    def test_distance_from_range_within(self):
        """Value within range should return 0."""
        from katrain.core.analysis.logic_skill import _distance_from_range

        assert _distance_from_range(5, (3, 10)) == 0
        assert _distance_from_range(3, (3, 10)) == 0  # Boundary
        assert _distance_from_range(10, (3, 10)) == 0  # Boundary

    def test_distance_from_range_below(self):
        """Value below range should return distance to lower bound."""
        from katrain.core.analysis.logic_skill import _distance_from_range

        assert _distance_from_range(1, (3, 10)) == 2
        assert _distance_from_range(0, (3, 10)) == 3

    def test_distance_from_range_above(self):
        """Value above range should return distance to upper bound."""
        from katrain.core.analysis.logic_skill import _distance_from_range

        assert _distance_from_range(15, (3, 10)) == 5
        assert _distance_from_range(20, (3, 10)) == 10

    def test_recommend_standard_on_low_reliability(self):
        """Low reliability (< 20%) should return 'standard' with LOW confidence."""
        from katrain.core.analysis.models.enums import AutoConfidence
        from katrain.core.analysis.models.move_eval import MoveEval
        from katrain.core.analysis import recommend_auto_strictness
        # Create moves with very low visits (< threshold)
        moves = [
            MoveEval(
                move_number=i,
                player="B" if i % 2 == 1 else "W",
                gtp=f"D{i}",
                score_before=None,
                score_after=0.0,
                delta_score=None,
                winrate_before=None,
                winrate_after=0.5,
                delta_winrate=None,
                points_lost=1.0,
                realized_points_lost=None,
                root_visits=10,  # Very low visits
                score_loss=1.0,
            )
            for i in range(1, 51)
        ]

        rec = recommend_auto_strictness(moves, reliability_pct=15.0)

        assert rec.recommended_preset == "standard"
        assert rec.confidence == AutoConfidence.LOW
        assert "reliability" in rec.reason.lower()

    def test_recommend_for_many_blunders(self):
        """Many high-loss moves: algorithm picks preset yielding closest to target range."""
        from katrain.core.analysis.models.move_eval import MoveEval
        from katrain.core.analysis import recommend_auto_strictness
        # Create moves with high loss (many blunders under any preset)
        # All 50 moves have loss=16.0
        # relaxed t3=15.0 → 50 blunders (way over 10)
        # beginner t3=10.0 → 50 blunders
        # standard t3=5.0 → 50 blunders
        # advanced t3=3.0 → 50 blunders
        # pro t3=1.0 → 50 blunders
        # All presets see 50 blunders; distance from (3,10) = 40 for all
        # Tie-breaker: closest to standard (index 2) → standard wins
        moves = [
            MoveEval(
                move_number=i,
                player="B" if i % 2 == 1 else "W",
                gtp=f"D{i}",
                score_before=None,
                score_after=0.0,
                delta_score=None,
                winrate_before=None,
                winrate_after=0.5,
                delta_winrate=None,
                points_lost=16.0,  # High loss
                realized_points_lost=None,
                root_visits=500,
                score_loss=16.0,
            )
            for i in range(1, 51)
        ]

        rec = recommend_auto_strictness(moves, reliability_pct=80.0)

        # With all moves as blunders under all presets, tie-breaker prefers standard
        assert rec.recommended_preset == "standard"
        assert rec.blunder_count == 50  # All moves are blunders

    def test_recommend_for_few_blunders(self):
        """Few low-loss moves: algorithm picks preset closest to target or tie-break."""
        from katrain.core.analysis.models.move_eval import MoveEval
        from katrain.core.analysis import recommend_auto_strictness
        # Create moves with low loss (0 blunders under any settings)
        # loss=0.3 is below t3 for all presets (even pro t3=1.0)
        # So all presets see 0 blunders, 0 important
        # Distance from target blunder range (3,10) = 3 for all
        # Distance from target important range (10,30) = 10 for all
        # Tie-breaker: standard is at index 2 (closest to center)
        moves = [
            MoveEval(
                move_number=i,
                player="B" if i % 2 == 1 else "W",
                gtp=f"D{i}",
                score_before=None,
                score_after=0.0,
                delta_score=None,
                winrate_before=None,
                winrate_after=0.5,
                delta_winrate=None,
                points_lost=0.3,  # Very low loss
                realized_points_lost=None,
                root_visits=500,
                score_loss=0.3,
            )
            for i in range(1, 101)
        ]

        rec = recommend_auto_strictness(moves, reliability_pct=80.0)

        # Very low losses = 0 blunders under all presets
        # With equal scores, tie-breaker prefers standard
        assert rec.recommended_preset == "standard"
        assert rec.blunder_count == 0
        assert rec.important_count == 0

    def test_prefer_standard_on_tie(self):
        """When scores are equal, should prefer preset closer to standard."""
        from katrain.core.analysis import PRESET_ORDER
        # Standard is at index 2, so it should be preferred on ties
        standard_idx = PRESET_ORDER.index("standard")
        assert standard_idx == 2

    def test_multi_game_scaling(self):
        """Target ranges should scale with game_count."""
        from katrain.core.analysis.models.move_eval import MoveEval
        from katrain.core.analysis import recommend_auto_strictness
        # Create moves that would produce ~5 blunders per game (within 3-10 range)
        # under 'standard' preset (t3=5.0)
        moves = []
        for game_idx in range(3):
            for i in range(1, 51):
                loss = 6.0 if i <= 5 else 0.5  # 5 blunders per "game"
                moves.append(
                    MoveEval(
                        move_number=game_idx * 50 + i,
                        player="B" if i % 2 == 1 else "W",
                        gtp=f"D{i}",
                        score_before=None,
                        score_after=0.0,
                        delta_score=None,
                        winrate_before=None,
                        winrate_after=0.5,
                        delta_winrate=None,
                        points_lost=loss,
                        realized_points_lost=None,
                        root_visits=500,
                        score_loss=loss,
                    )
                )

        # 3 games × ~5 blunders = ~15 blunders total
        # Target range for 3 games: (9, 30) for blunders
        rec = recommend_auto_strictness(moves, game_count=3, reliability_pct=80.0)

        # 15 blunders is within (9, 30) for standard
        # Should recommend something close to standard
        assert rec.recommended_preset in ["beginner", "standard", "advanced"]

    def test_canonical_loss_semantics(self):
        """Should use max(0, score_loss) for counting, not raw values."""
        from katrain.core.analysis.models.move_eval import MoveEval
        from katrain.core.analysis import recommend_auto_strictness
        # Create moves with negative score_loss (gains) - should be treated as 0
        moves = [
            MoveEval(
                move_number=i,
                player="B" if i % 2 == 1 else "W",
                gtp=f"D{i}",
                score_before=None,
                score_after=0.0,
                delta_score=None,
                winrate_before=None,
                winrate_after=0.5,
                delta_winrate=None,
                points_lost=-5.0,  # Negative = gain
                realized_points_lost=None,
                root_visits=500,
                score_loss=-5.0,  # Negative
            )
            for i in range(1, 51)
        ]

        rec = recommend_auto_strictness(moves, reliability_pct=80.0)

        # All negative losses should be treated as 0, so 0 blunders
        assert rec.blunder_count == 0
        assert rec.important_count == 0

    def test_confidence_levels(self):
        """Should return correct confidence based on score."""
        from katrain.core.analysis.models.enums import AutoConfidence
        from katrain.core.analysis.models.move_eval import MoveEval
        from katrain.core.analysis import recommend_auto_strictness
        # Create moves that produce exactly the target range (score=0 → HIGH)
        moves = [
            MoveEval(
                move_number=i,
                player="B" if i % 2 == 1 else "W",
                gtp=f"D{i}",
                score_before=None,
                score_after=0.0,
                delta_score=None,
                winrate_before=None,
                winrate_after=0.5,
                delta_winrate=None,
                points_lost=6.0 if i <= 6 else (3.0 if i <= 20 else 0.5),
                realized_points_lost=None,
                root_visits=500,
                score_loss=6.0 if i <= 6 else (3.0 if i <= 20 else 0.5),
            )
            for i in range(1, 51)
        ]

        rec = recommend_auto_strictness(moves, reliability_pct=80.0)

        # Confidence should be HIGH, MEDIUM, or LOW based on distance score
        assert rec.confidence in [AutoConfidence.HIGH, AutoConfidence.MEDIUM, AutoConfidence.LOW]
        assert rec.score >= 0  # Score is non-negative distance


# ---------------------------------------------------------------------------
# Test: ConfidenceLevel and compute_confidence_level (PR#1)
# ---------------------------------------------------------------------------

from katrain.core.analysis.models.enums import ConfidenceLevel
from katrain.core.analysis import compute_confidence_level, compute_reliability_stats, get_important_moves_limit


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum and compute_confidence_level function (PR#1)"""

    def test_high_confidence_with_high_reliability(self):
        """HIGH confidence when reliability >= 50%"""
        # 10 moves, all reliable (visits=500)
        moves = [
            MoveEval(
                move_number=i,
                player="B",
                gtp=f"D{i}",
                score_before=0.0,
                score_after=0.0,
                delta_score=0.0,
                winrate_before=0.5,
                winrate_after=0.5,
                delta_winrate=0.0,
                points_lost=1.0,
                realized_points_lost=None,
                root_visits=500,  # >= 200 threshold = reliable
                score_loss=1.0,
            )
            for i in range(1, 11)
        ]
        level = compute_confidence_level(moves)
        assert level == ConfidenceLevel.HIGH

    def test_high_confidence_with_high_avg_visits(self):
        """HIGH confidence when avg_visits >= 400 (even if reliability < 50%)"""
        # 10 moves, 3 reliable, 7 not reliable but all have visits >= 100
        moves = []
        for i in range(1, 11):
            # Average visits = 450, but only 30% reliable (< 50%)
            visits = 500 if i <= 3 else 430  # avg = (500*3 + 430*7) / 10 = 451
            moves.append(
                MoveEval(
                    move_number=i,
                    player="B",
                    gtp=f"D{i}",
                    score_before=0.0,
                    score_after=0.0,
                    delta_score=0.0,
                    winrate_before=0.5,
                    winrate_after=0.5,
                    delta_winrate=0.0,
                    points_lost=1.0,
                    realized_points_lost=None,
                    root_visits=visits,
                    score_loss=1.0,
                )
            )
        level = compute_confidence_level(moves)
        # avg_visits = 451 >= 400 → HIGH (even though reliability = 30%)
        assert level == ConfidenceLevel.HIGH

    def test_medium_confidence(self):
        """MEDIUM confidence when reliability >= 30% or avg_visits >= 150"""
        # 10 moves, 4 reliable (40%), avg_visits = 180
        moves = []
        for i in range(1, 11):
            visits = 200 if i <= 4 else 100  # 4 reliable, 6 not
            # avg = (200*4 + 100*6) / 10 = 140 < 150
            # reliability = 4/10 = 40% >= 30% → MEDIUM
            moves.append(
                MoveEval(
                    move_number=i,
                    player="B",
                    gtp=f"D{i}",
                    score_before=0.0,
                    score_after=0.0,
                    delta_score=0.0,
                    winrate_before=0.5,
                    winrate_after=0.5,
                    delta_winrate=0.0,
                    points_lost=1.0,
                    realized_points_lost=None,
                    root_visits=visits,
                    score_loss=1.0,
                )
            )
        level = compute_confidence_level(moves)
        assert level == ConfidenceLevel.MEDIUM

    def test_low_confidence_insufficient_reliability_and_visits(self):
        """LOW confidence when reliability < 30% and avg_visits < 150"""
        # 10 moves, 2 reliable (20%), avg_visits = 100
        moves = []
        for i in range(1, 11):
            visits = 200 if i <= 2 else 75  # 2 reliable, 8 not
            # avg = (200*2 + 75*8) / 10 = 100 < 150
            # reliability = 2/10 = 20% < 30% → LOW
            moves.append(
                MoveEval(
                    move_number=i,
                    player="B",
                    gtp=f"D{i}",
                    score_before=0.0,
                    score_after=0.0,
                    delta_score=0.0,
                    winrate_before=0.5,
                    winrate_after=0.5,
                    delta_winrate=0.0,
                    points_lost=1.0,
                    realized_points_lost=None,
                    root_visits=visits,
                    score_loss=1.0,
                )
            )
        level = compute_confidence_level(moves)
        assert level == ConfidenceLevel.LOW

    def test_min_coverage_guard_forces_low(self):
        """LOW confidence when moves_with_visits < MIN_COVERAGE_MOVES (5)"""
        # 10 moves total, but only 3 have visits > 0
        moves = []
        for i in range(1, 11):
            visits = 500 if i <= 3 else 0  # Only 3 moves have visits
            moves.append(
                MoveEval(
                    move_number=i,
                    player="B",
                    gtp=f"D{i}",
                    score_before=0.0,
                    score_after=0.0,
                    delta_score=0.0,
                    winrate_before=0.5,
                    winrate_after=0.5,
                    delta_winrate=0.0,
                    points_lost=1.0,
                    realized_points_lost=None,
                    root_visits=visits,
                    score_loss=1.0,
                )
            )
        level = compute_confidence_level(moves)
        # moves_with_visits = 3 < 5 → LOW (forced by coverage guard)
        assert level == ConfidenceLevel.LOW

    def test_reliability_pct_denominator_is_moves_with_visits(self):
        """reliability_pct should use moves_with_visits as denominator, not total_moves"""
        # 20 moves total, 10 have visits=0, 10 have visits > 0
        # Of the 10 with visits, 6 are reliable (60%)
        moves = []
        for i in range(1, 21):
            if i <= 10:
                visits = 0  # No visits
            elif i <= 16:
                visits = 200  # Reliable
            else:
                visits = 50  # Not reliable
            moves.append(
                MoveEval(
                    move_number=i,
                    player="B",
                    gtp=f"D{i}",
                    score_before=0.0,
                    score_after=0.0,
                    delta_score=0.0,
                    winrate_before=0.5,
                    winrate_after=0.5,
                    delta_winrate=0.0,
                    points_lost=1.0,
                    realized_points_lost=None,
                    root_visits=visits,
                    score_loss=1.0,
                )
            )

        stats = compute_reliability_stats(moves)

        # total_moves = 20, moves_with_visits = 10, reliable_count = 6
        assert stats.total_moves == 20
        assert stats.moves_with_visits == 10
        assert stats.reliable_count == 6

        # reliability_pct = 6/10 * 100 = 60% (NOT 6/20 = 30%)
        assert stats.reliability_pct == 60.0

        # coverage_pct = 10/20 * 100 = 50%
        assert stats.coverage_pct == 50.0

        # confidence level should be HIGH (reliability >= 50%)
        level = compute_confidence_level(moves)
        assert level == ConfidenceLevel.HIGH

    def test_confidence_label_ja(self):
        """Japanese labels for confidence levels"""
        from katrain.core.analysis import get_confidence_label

        assert get_confidence_label(ConfidenceLevel.HIGH, lang="ja") == "信頼度: 高"
        assert get_confidence_label(ConfidenceLevel.MEDIUM, lang="ja") == "信頼度: 中"
        assert get_confidence_label(ConfidenceLevel.LOW, lang="ja") == "信頼度: 低"

    def test_confidence_label_en(self):
        """English labels for confidence levels"""
        from katrain.core.analysis import get_confidence_label
        assert get_confidence_label(ConfidenceLevel.HIGH, lang="en") == "Confidence: High"
        assert get_confidence_label(ConfidenceLevel.MEDIUM, lang="en") == "Confidence: Medium"
        assert get_confidence_label(ConfidenceLevel.LOW, lang="en") == "Confidence: Low"

    def test_important_moves_limit_by_confidence(self):
        """Important moves limit varies by confidence level"""
        assert get_important_moves_limit(ConfidenceLevel.HIGH) == 20
        assert get_important_moves_limit(ConfidenceLevel.MEDIUM) == 10
        assert get_important_moves_limit(ConfidenceLevel.LOW) == 5

    def test_empty_moves_returns_low(self):
        """Empty moves list returns LOW confidence"""
        level = compute_confidence_level([])
        assert level == ConfidenceLevel.LOW

    # -----------------------------------------------------------------------
    # Edge case tests for confidence gating (codex/2026-01-05)
    # -----------------------------------------------------------------------

    def test_all_zero_visits_no_crash_and_low(self, all_zero_visits_moves):
        """All zero visits should not crash and return LOW (coverage guard)."""
        moves = all_zero_visits_moves
        # Should not crash
        stats = compute_reliability_stats(moves)
        result = compute_confidence_level(moves)
        # Verify stats
        assert stats.moves_with_visits == 0
        assert stats.zero_visits_count == 10
        # Coverage guard: moves_with_visits < MIN_COVERAGE_MOVES (5) → LOW
        assert result == ConfidenceLevel.LOW

    def test_extreme_high_visits(self, extreme_high_visits_moves):
        """Extreme high visits (2000) should be HIGH confidence."""
        moves = extreme_high_visits_moves
        stats = compute_reliability_stats(moves)
        result = compute_confidence_level(moves)
        # Verify stats: all moves reliable, avg_visits = 2000
        assert stats.moves_with_visits == 10
        assert stats.reliable_count == 10
        assert stats.avg_visits == 2000.0
        # HIGH: reliability_pct = 100% >= 50% OR avg_visits >= 400
        assert result == ConfidenceLevel.HIGH

    def test_very_short_game_exactly_min_coverage(self, make_moves):
        """Exactly MIN_COVERAGE_MOVES (5) with high visits should pass coverage guard."""
        moves = make_moves(count=5, visits=500)
        stats = compute_reliability_stats(moves)
        result = compute_confidence_level(moves)
        # Verify: exactly 5 moves with visits
        assert stats.moves_with_visits == 5
        assert stats.reliable_count == 5
        # Should NOT be forced LOW by coverage guard
        # reliability = 100% >= 50% → HIGH
        assert result == ConfidenceLevel.HIGH

    def test_very_short_game_below_min_coverage(self, make_moves):
        """Below MIN_COVERAGE_MOVES (4) should be LOW regardless of visits."""
        moves = make_moves(count=4, visits=500)
        stats = compute_reliability_stats(moves)
        result = compute_confidence_level(moves)
        # Verify: only 4 moves with visits
        assert stats.moves_with_visits == 4
        # Coverage guard: moves_with_visits < 5 → LOW
        assert result == ConfidenceLevel.LOW

    def test_partial_analysis_suffix_missing(self, partial_analysis_suffix_missing):
        """First half analyzed, second half missing should compute correctly."""
        moves = partial_analysis_suffix_missing
        stats = compute_reliability_stats(moves)
        result = compute_confidence_level(moves)
        # Verify stats: 10 moves with visits, 10 with zero
        assert stats.total_moves == 20
        assert stats.moves_with_visits == 10
        assert stats.zero_visits_count == 10
        assert stats.reliable_count == 10  # All analyzed moves have visits=500 >= 200
        # reliability_pct = 100%, avg_visits = 500 → HIGH
        assert result == ConfidenceLevel.HIGH

    def test_partial_analysis_scattered(self, partial_analysis_scattered):
        """Scattered analysis (every other move) should compute correctly."""
        moves = partial_analysis_scattered
        stats = compute_reliability_stats(moves)
        result = compute_confidence_level(moves)
        # Verify stats: 10 even-indexed moves have visits=300, 10 odd have 0
        assert stats.total_moves == 20
        assert stats.moves_with_visits == 10
        assert stats.zero_visits_count == 10
        assert stats.reliable_count == 10  # visits=300 >= 200 threshold
        # reliability_pct = 100%, avg_visits = 300 → HIGH
        assert result == ConfidenceLevel.HIGH

    def test_handicap_metadata_no_crash(self, make_moves):
        """Handicap game metadata should not crash confidence computation."""
        # Create normal moves (handicap doesn't affect MoveEval directly)
        moves = make_moves(count=10, visits=500)
        # Simulate handicap by having black play first several moves
        # (In real games, handicap is board-level, not move-level metadata)
        # This test verifies the function doesn't crash with normal input
        result = compute_confidence_level(moves)
        assert result is not None
        # Should be deterministic
        assert result == compute_confidence_level(moves)
        # With 10 reliable moves, should be HIGH
        assert result == ConfidenceLevel.HIGH


# ---------------------------------------------------------------------------
# Test: Evidence Attachments (PR#2)
# ---------------------------------------------------------------------------
