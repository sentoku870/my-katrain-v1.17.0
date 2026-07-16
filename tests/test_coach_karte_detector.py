"""Phase 215: Tests for katrain.core.coach.karte_detector.

Covers:
- Aggregator helpers (avg_points_lost, max_score_stdev, etc.)
- build_symptom_context_from_karte (full SymptomContext population)
- detect_symptoms_from_karte (auto-detect + weakness category mapping)
- Robustness on missing / empty / malformed karte data
"""

from __future__ import annotations

import pytest

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.beginner.models import HintCategory
from katrain.core.coach.karte_detector import (
    build_symptom_context_from_karte,
    detect_symptoms_from_karte,
    extract_avg_points_lost,
    extract_avg_streak_loss,
    extract_avg_winrate_lost,
    extract_consecutive_loss_run,
    extract_critical_move_count,
    extract_game_count,
    extract_good_move_count,
    extract_longest_streak,
    extract_max_overall_difficulty,
    extract_max_score_stdev,
    extract_max_winrate_drop,
    extract_streak_count,
    extract_total_streak_loss,
    extract_weakness_concentration,
)
from katrain.core.coach.symptom_index import (
    SymptomContext,
    SymptomId,
)

# --- Fixtures ---


@pytest.fixture
def sample_karte() -> dict:
    return {
        "schema_version": "3.4",
        "meta": {"board_size": 19, "game_count": 1},
        "summary": {"total_moves": 200},
        "important_moves": [
            {
                "meaning_tag_id": "atari_blindness",
                "points_lost": 1.5,
                "winrate_lost": 0.05,
                "move_number": 30,
            },
            {
                "meaning_tag_id": "big_point_blindness",
                "points_lost": 3.0,
                "winrate_lost": 0.08,
                "move_number": 100,
            },
            {
                "meaning_tag_id": "overplay",
                "points_lost": 4.0,
                "winrate_lost": 0.10,
                "move_number": 150,
                "score_stdev": 2.0,
                "overall_difficulty": 0.8,
                "good_move_count": 2,
            },
        ],
        "weaknesses": {
            "black": [
                # Sorted by total_loss descending (Phase 149-C-2 sort key)
                {"category": "big_point_blindness", "total_loss": 8.0},
                {"category": "atari_blindness", "total_loss": 5.0},
            ],
            "white": [],
        },
        "weaknesses_meta": {
            "black": {"total_loss": 15.0, "covered_loss": 13.0},
            "white": {"total_loss": 0.0, "covered_loss": 0.0},
        },
        "critical_3": {
            "black": {"moves": [{"move_number": 100}, {"move_number": 150}, {"move_number": 200}]},
            "white": {"moves": []},
        },
        "reason_tags_distribution": {
            "black": {"total_count": 5},
            "white": {"total_count": 0},
        },
    }


@pytest.fixture
def empty_karte() -> dict:
    return {"schema_version": "3.4"}


# --- Aggregator helpers ---


class TestAggregators:
    def test_avg_points_lost(self, sample_karte):
        # (1.5 + 3.0 + 4.0) / 3 = 2.833...
        result = extract_avg_points_lost(sample_karte)
        assert result is not None
        assert abs(result - 2.8333333) < 0.01

    def test_avg_points_lost_empty(self, empty_karte):
        assert extract_avg_points_lost(empty_karte) is None

    def test_avg_winrate_lost(self, sample_karte):
        # (0.05 + 0.08 + 0.10) / 3 = 0.0766...
        result = extract_avg_winrate_lost(sample_karte)
        assert result is not None
        assert abs(result - 0.0766) < 0.001

    def test_max_winrate_drop(self, sample_karte):
        result = extract_max_winrate_drop(sample_karte)
        assert result == pytest.approx(0.10)

    def test_max_score_stdev(self, sample_karte):
        # Only one move has score_stdev (2.0)
        assert extract_max_score_stdev(sample_karte) == 2.0

    def test_max_overall_difficulty(self, sample_karte):
        assert extract_max_overall_difficulty(sample_karte) == 0.8

    def test_good_move_count(self, sample_karte):
        # Max over all moves — only one has good_move_count=2
        assert extract_good_move_count(sample_karte) == 2

    def test_critical_move_count(self, sample_karte):
        # 3 from black critical_3 + 5 from reason_tags = 8
        assert extract_critical_move_count(sample_karte) == 8

    def test_weakness_concentration(self, sample_karte):
        # top weakness: 8.0 / 15.0 = 0.533
        result = extract_weakness_concentration(sample_karte)
        assert result is not None
        assert abs(result - 0.533) < 0.01

    def test_game_count(self, sample_karte):
        # meta.game_count = 1
        assert extract_game_count(sample_karte) == 1

    def test_game_count_fallback(self, empty_karte):
        # No meta.game_count but has schema_version → 1
        assert extract_game_count(empty_karte) == 1

    def test_aggregators_no_crash_on_empty(self, empty_karte):
        # All should return None / 0 / safe defaults
        assert extract_avg_points_lost(empty_karte) is None
        assert extract_avg_winrate_lost(empty_karte) is None
        assert extract_max_winrate_drop(empty_karte) is None
        assert extract_max_score_stdev(empty_karte) is None
        assert extract_max_overall_difficulty(empty_karte) is None
        assert extract_good_move_count(empty_karte) == 0
        assert extract_critical_move_count(empty_karte) == 0
        assert extract_weakness_concentration(empty_karte) is None


# --- build_symptom_context_from_karte ---


class TestBuildSymptomContext:
    def test_returns_symptom_context(self, sample_karte):
        ctx = build_symptom_context_from_karte(sample_karte)
        assert isinstance(ctx, SymptomContext)

    def test_populates_aggregates(self, sample_karte):
        ctx = build_symptom_context_from_karte(sample_karte)
        assert ctx.avg_points_lost is not None
        assert ctx.avg_points_lost > 0
        assert ctx.score_stdev == 2.0
        assert ctx.overall_difficulty == 0.8
        assert ctx.weakness_concentration is not None

    def test_collects_meaning_tags(self, sample_karte):
        ctx = build_symptom_context_from_karte(sample_karte)
        # atari_blindness, big_point_blindness, overplay are NOT
        # MeaningTagId values, so only OVERPLAY should be collected
        assert MeaningTagId.OVERPLAY in ctx.meaning_tag_ids

    def test_collects_hint_categories(self, sample_karte):
        ctx = build_symptom_context_from_karte(sample_karte)
        # OVERPLAY tag → HEAVY_GROUP hint
        assert HintCategory.HEAVY_GROUP in ctx.hint_categories

    def test_endgame_detection(self):
        # Use a fresh karte with move_number > 200 to ensure endgame trigger
        karte = {
            "schema_version": "3.4",
            "summary": {"total_moves": 250},
            "important_moves": [
                {"move_number": 250, "points_lost": 1.0},
            ],
        }
        ctx = build_symptom_context_from_karte(karte)
        assert ctx.is_endgame is True

    def test_endgame_detection_false(self, sample_karte):
        ctx = build_symptom_context_from_karte(sample_karte)
        # sample_karte's max move_number is 200, which is not > 200
        assert ctx.is_endgame is False

    def test_endgame_detection_no(self, empty_karte):
        ctx = build_symptom_context_from_karte(empty_karte)
        assert ctx.is_endgame is False

    def test_board_size_default(self, sample_karte):
        ctx = build_symptom_context_from_karte(sample_karte)
        assert ctx.board_size == 19

    def test_board_size_from_meta_list(self):
        karte = {
            "schema_version": "3.4",
            "meta": {"board_size": [13, 13]},
        }
        ctx = build_symptom_context_from_karte(karte)
        assert ctx.board_size == 13

    def test_board_size_default_fallback(self, empty_karte):
        ctx = build_symptom_context_from_karte(empty_karte)
        assert ctx.board_size == 19

    # --- Phase 226-F (F-A): current_phase field ---

    def test_current_phase_opening_when_most_mistakes_are_opening(self):
        karte = {
            "schema_version": "3.4",
            "summary": {"total_moves": 60},
            "important_moves": [
                {"move_number": 10, "points_lost": 3.0},
                {"move_number": 20, "points_lost": 4.0},
                {"move_number": 30, "points_lost": 5.0},
                {"move_number": 80, "points_lost": 2.0},
            ],
        }
        ctx = build_symptom_context_from_karte(karte)
        # 3 of 4 mistakes are in the opening range → "opening"
        assert ctx.current_phase == "opening"

    def test_current_phase_middle_when_range_spans_middle(self):
        karte = {
            "schema_version": "3.4",
            "summary": {"total_moves": 200},
            "important_moves": [
                {"move_number": 60, "points_lost": 3.0},
                {"move_number": 100, "points_lost": 4.0},
                {"move_number": 150, "points_lost": 5.0},
            ],
        }
        ctx = build_symptom_context_from_karte(karte)
        # No high concentration of opening / endgame → "middle"
        assert ctx.current_phase == "middle"

    def test_current_phase_endgame_when_mistakes_concentrated_endgame(self):
        karte = {
            "schema_version": "3.4",
            "summary": {"total_moves": 250},
            "important_moves": [
                {"move_number": 210, "points_lost": 3.0},
                {"move_number": 220, "points_lost": 4.0},
                {"move_number": 240, "points_lost": 5.0},
                {"move_number": 50, "points_lost": 2.0},
            ],
        }
        ctx = build_symptom_context_from_karte(karte)
        # 3 of 4 mistakes in endgame range → "endgame"
        assert ctx.current_phase == "endgame"

    def test_current_phase_unknown_when_no_move_numbers(self):
        karte = {
            "schema_version": "3.4",
            "important_moves": [
                {"points_lost": 3.0},
                {"points_lost": 4.0},
            ],
        }
        ctx = build_symptom_context_from_karte(karte)
        assert ctx.current_phase == "unknown"

    def test_current_phase_scales_with_board_size(self):
        # On a 9x9 board the opening range is much shorter.
        karte = {
            "schema_version": "3.4",
            "meta": {"board_size": 9},
            "summary": {"total_moves": 60},
            "important_moves": [
                {"move_number": 5, "points_lost": 3.0},
                {"move_number": 8, "points_lost": 4.0},
                {"move_number": 10, "points_lost": 5.0},
            ],
        }
        ctx = build_symptom_context_from_karte(karte)
        # On 9x9, opening_max = max(15, int(50 * 9/19)) = 23
        # All 3 moves are in the opening range on a 9x9 board.
        assert ctx.current_phase == "opening"

    def test_is_phase_uses_current_phase_when_move_number_unknown(self):
        # Phase 226-F (F-A): when move_number is None, is_phase()
        # falls back to current_phase so phase-gated detectors fire.
        karte = {
            "schema_version": "3.4",
            "summary": {"total_moves": 60},
            "important_moves": [
                {"move_number": 10, "points_lost": 3.0},
                {"move_number": 20, "points_lost": 4.0},
                {"move_number": 30, "points_lost": 5.0},
            ],
        }
        ctx = build_symptom_context_from_karte(karte)
        assert ctx.move_number is None  # karte context
        assert ctx.current_phase == "opening"
        assert ctx.is_phase("opening") is True
        assert ctx.is_phase("middle") is False


# --- detect_symptoms_from_karte ---


class TestDetectFromKarte:
    def test_returns_tuple(self, sample_karte):
        fired = detect_symptoms_from_karte(sample_karte)
        assert isinstance(fired, tuple)
        assert all(isinstance(s, SymptomId) for s in fired)

    def test_weakness_categories_appear(self, sample_karte):
        fired = detect_symptoms_from_karte(sample_karte)
        # atari_blindness + big_point_blindness are weakness categories
        assert SymptomId.ATARI_BLINDNESS in fired
        assert SymptomId.BIG_POINT_BLINDNESS in fired

    def test_per_move_signals_appear(self, sample_karte):
        fired = detect_symptoms_from_karte(sample_karte)
        # OVERPLAY + score_stdev 2.0 → OVERPLAY_RECKLESS_ATTACK
        assert SymptomId.OVERPLAY_RECKLESS_ATTACK in fired

    def test_no_duplicates(self, sample_karte):
        fired = detect_symptoms_from_karte(sample_karte)
        assert len(fired) == len(set(fired))

    def test_empty_karte(self, empty_karte):
        fired = detect_symptoms_from_karte(empty_karte)
        # Empty karte → no detected symptoms
        assert fired == ()

    def test_stable_ordering(self, sample_karte):
        fired_a = detect_symptoms_from_karte(sample_karte)
        fired_b = detect_symptoms_from_karte(sample_karte)
        assert fired_a == fired_b  # same order

    def test_subset_of_symptom_table(self, sample_karte):
        fired = detect_symptoms_from_karte(sample_karte)
        for sid in fired:
            assert isinstance(sid, SymptomId)


# --- Integration with CLI ---


class TestCliIntegration:
    def test_cli_uses_karte_detector(self, sample_karte, tmp_path):
        """The CLI's build_prompt should pick up the karte_detector output."""
        import json

        from katrain.core.coach import cli

        karte_path = tmp_path / "karte.json"
        karte_path.write_text(json.dumps(sample_karte), encoding="utf-8")

        # Use a low --rank to ensure the AYAKA voice (which gives the
        # LLM prompt the §5.3 contract). This bypasses the human-facing
        # __main__ dispatch.
        prompt = cli.build_prompt(sample_karte, rank="5k")
        ids = {s.value for s in prompt.referenced_symptom_ids}
        # atari_blindness / big_point_blindness should be detected
        # from weaknesses categories by the karte_detector
        assert "atari_blindness" in ids
        assert "big_point_blindness" in ids


# --- Phase 216: streak aggregators ---


class TestStreakAggregators:
    def test_longest_streak_single(self):
        karte = {"mistake_streaks": {"black": [{"move_count": 3}]}}
        assert extract_longest_streak(karte) == 3

    def test_longest_streak_max(self):
        karte = {
            "mistake_streaks": {
                "black": [
                    {"move_count": 2},
                    {"move_count": 5},
                    {"move_count": 3},
                ],
                "white": [{"move_count": 4}],
            }
        }
        assert extract_longest_streak(karte) == 5

    def test_longest_streak_empty(self):
        assert extract_longest_streak({}) == 0
        assert extract_longest_streak({"mistake_streaks": {}}) == 0

    def test_total_streak_loss(self):
        karte = {
            "mistake_streaks": {
                "black": [
                    {"total_loss": 5.0},
                    {"total_loss": 3.5},
                ],
                "white": [{"total_loss": 2.0}],
            }
        }
        assert extract_total_streak_loss(karte) == 10.5

    def test_total_streak_loss_empty(self):
        assert extract_total_streak_loss({}) == 0.0

    def test_streak_count(self):
        karte = {
            "mistake_streaks": {
                "black": [{}, {}, {}],
                "white": [{}],
            }
        }
        assert extract_streak_count(karte) == 4

    def test_consecutive_loss_run(self):
        karte = {
            "loss_progression": [
                {"mistake_count": 2},
                {"mistake_count": 1},
                {"mistake_count": 3},
                {"mistake_count": 0},
                {"mistake_count": 2},
                {"mistake_count": 1},
                {"mistake_count": 2},
            ]
        }
        # First run = 3 (positions 0,1,2), second = 3 (positions 4,5,6)
        assert extract_consecutive_loss_run(karte) == 3

    def test_consecutive_loss_run_empty(self):
        assert extract_consecutive_loss_run({}) == 0

    def test_consecutive_loss_run_all_wins(self):
        karte = {
            "loss_progression": [
                {"mistake_count": 0},
                {"mistake_count": 0},
                {"mistake_count": 0},
            ]
        }
        assert extract_consecutive_loss_run(karte) == 0

    def test_avg_streak_loss(self):
        karte = {
            "mistake_streaks": {
                "black": [{"total_loss": 4.0}, {"total_loss": 6.0}],
            }
        }
        assert extract_avg_streak_loss(karte) == 5.0

    def test_avg_streak_loss_empty(self):
        assert extract_avg_streak_loss({}) == 0.0


# --- Phase 216: streak-based symptom detection ---


class TestStreakSymptoms:
    def test_overfight_fires(self):
        karte = {
            "mistake_streaks": {"black": [{"move_count": 4, "total_loss": 10.0}]},
        }
        fired = detect_symptoms_from_karte(karte)
        assert SymptomId.OVERFIGHT in fired

    def test_small_move_addiction_fires(self):
        karte = {
            "mistake_streaks": {
                "black": [
                    {"move_count": 2, "total_loss": 4.0},
                    {"move_count": 2, "total_loss": 5.0},
                    {"move_count": 2, "total_loss": 3.0},
                    {"move_count": 2, "total_loss": 4.0},
                    {"move_count": 2, "total_loss": 3.0},
                ],
            },
        }
        fired = detect_symptoms_from_karte(karte)
        assert SymptomId.SMALL_MOVE_ADDICTION in fired

    def test_tilt_chain_fires(self):
        karte = {
            "mistake_streaks": {"black": [{"move_count": 4, "total_loss": 20.0}]},
            "loss_progression": [
                {"mistake_count": 2},
                {"mistake_count": 1},
                {"mistake_count": 3},
                {"mistake_count": 2},
            ],
        }
        fired = detect_symptoms_from_karte(karte)
        assert SymptomId.TILT_CHAIN in fired

    def test_tilt_discouragement_fires(self):
        karte = {
            "mistake_streaks": {"black": [{"move_count": 4, "total_loss": 12.0}]},
            "loss_progression": [
                {"mistake_count": 2},
                {"mistake_count": 1},
                {"mistake_count": 3},
                {"mistake_count": 2},
                {"mistake_count": 1},
            ],
        }
        fired = detect_symptoms_from_karte(karte)
        assert SymptomId.TILT_DISCOURAGEMENT in fired

    def test_streak_symptoms_no_false_positive(self):
        # No streaks + perfect game → no streak-based symptoms
        karte = {
            "mistake_streaks": {"black": [], "white": []},
            "loss_progression": [
                {"mistake_count": 0},
                {"mistake_count": 0},
            ],
        }
        fired = detect_symptoms_from_karte(karte)
        # None of the streak-only symptoms should fire (this assertion
        # documents the intent — the local variable is unused but
        # keeping it makes the relationship between "what we expect
        # not to fire" and "what the detector sees" explicit).
        expected_no_fire = {
            SymptomId.OVERFIGHT,
            SymptomId.SMALL_MOVE_ADDICTION,
            SymptomId.TILT_CHAIN,
            SymptomId.TILT_DISCOURAGEMENT,
        }
        assert set(fired).isdisjoint(expected_no_fire)

    def test_streak_combined_with_weakness(self):
        # Weakness category + streak both contribute
        karte = {
            "weaknesses": {"black": [{"category": "atari_blindness"}], "white": []},
            "mistake_streaks": {"black": [{"move_count": 4, "total_loss": 10.0}]},
        }
        fired = detect_symptoms_from_karte(karte)
        assert SymptomId.ATARI_BLINDNESS in fired
        assert SymptomId.OVERFIGHT in fired
