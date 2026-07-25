"""Phase 270: Tests for katrain.core.coach.karte_aggregator.

Covers the six pure aggregator functions plus the integrated
``build_summary_weakness_prompt`` extension (schema 3.5 when
``config.kartes`` is provided). Pure-data tests — no Kivy, no I/O.
"""

from __future__ import annotations

import pytest

from katrain.core.coach import (
    AggregatedKarteView,
    aggregate_area_difficulty,
    aggregate_data_quality,
    aggregate_kartes,
    aggregate_reason_tags_by_color,
    build_meaning_tag_label_map,
    detect_loss_spike_windows,
    group_representative_moves_by_tag,
)
from katrain.core.coach.karte_aggregator import (
    _LOSS_SPIKE_MULTIPLIER_DEFAULT,
)
from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.summary_prompt_builder import (
    SCHEMA_VERSION_WITH_KARTES,
    SummaryPromptConfig,
    build_summary_weakness_prompt,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_karte(
    *,
    game_id: str = "g1",
    reason_tags: dict | None = None,
    important_moves: list | None = None,
    critical_3: dict | None = None,
    data_quality: dict | None = None,
    loss_progression: list | None = None,
    top_mistakes: list | None = None,
) -> dict:
    """Build a minimal karte JSON for testing.

    Only the fields relevant to the aggregator are populated;
    everything else is a placeholder so :func:`_iter_kartes`
    accepts the dict (it requires a ``schema_version`` key).
    """
    karte: dict = {
        "schema_version": "3.4",
        "meta": {"game_id": game_id},
    }
    if reason_tags is not None:
        karte["reason_tags_distribution"] = reason_tags
    if important_moves is not None:
        karte["important_moves"] = important_moves
    if critical_3 is not None:
        karte["critical_3"] = critical_3
    if data_quality is not None:
        karte["data_quality"] = data_quality
    if loss_progression is not None:
        karte["loss_progression"] = loss_progression
    if top_mistakes is not None:
        karte["top_mistakes"] = top_mistakes
    return karte


# ---------------------------------------------------------------------------
# 1. aggregate_reason_tags_by_color
# ---------------------------------------------------------------------------


class TestReasonTagsByColor:
    def test_empty_input(self):
        assert aggregate_reason_tags_by_color([]) == {}

    def test_single_karte(self):
        k = _make_karte(reason_tags={"black": {"endgame_hint": 3, "heavy_loss": 2}})
        out = aggregate_reason_tags_by_color([k])
        assert out == {"black": {"endgame_hint": 3, "heavy_loss": 2}}

    def test_two_kartes_same_color_sum(self):
        k1 = _make_karte(reason_tags={"black": {"endgame_hint": 3}})
        k2 = _make_karte(reason_tags={"black": {"endgame_hint": 4, "heavy_loss": 1}})
        out = aggregate_reason_tags_by_color([k1, k2])
        assert out == {"black": {"endgame_hint": 7, "heavy_loss": 1}}

    def test_two_kartes_split_colors(self):
        k1 = _make_karte(reason_tags={"black": {"endgame_hint": 3}})
        k2 = _make_karte(reason_tags={"white": {"endgame_hint": 5}})
        out = aggregate_reason_tags_by_color([k1, k2])
        assert out == {"black": {"endgame_hint": 3}, "white": {"endgame_hint": 5}}

    def test_missing_block_is_skipped(self):
        k1 = _make_karte(reason_tags={"black": {"endgame_hint": 3}})
        k2 = _make_karte()  # no reason_tags
        out = aggregate_reason_tags_by_color([k1, k2])
        assert out == {"black": {"endgame_hint": 3}}

    def test_non_karte_filtered(self):
        # Summary-shape dicts (no schema_version) are filtered out.
        k = _make_karte(reason_tags={"black": {"x": 1}})
        s = {"meta": {"games_analyzed": 3}}  # no schema_version
        out = aggregate_reason_tags_by_color([k, s])
        assert out == {"black": {"x": 1}}

    def test_non_dict_color_value_skipped(self):
        k = _make_karte(reason_tags={"black": {"x": 1}, "white": "not-a-dict"})
        out = aggregate_reason_tags_by_color([k])
        assert out == {"black": {"x": 1}}

    def test_non_numeric_count_skipped(self):
        k = _make_karte(reason_tags={"black": {"x": 1, "y": "nope", "z": 2.5}})
        out = aggregate_reason_tags_by_color([k])
        # "y" is skipped, "x" and "z" are kept (z is float but accepted)
        assert out == {"black": {"x": 1, "z": 2}}


# ---------------------------------------------------------------------------
# 2. aggregate_area_difficulty
# ---------------------------------------------------------------------------


class TestAreaDifficulty:
    def test_empty_input(self):
        out = aggregate_area_difficulty([])
        # The function always returns the full 3x5 grid (zero-filled)
        # so renderers can iterate without None-checks.
        assert set(out.keys()) == {"corner", "edge", "center"}
        for area_dict in out.values():
            assert area_dict == {"only": 0, "hard": 0, "normal": 0, "easy": 0, "unknown": 0}

    def test_important_moves_basic(self):
        k = _make_karte(
            important_moves=[
                {"area": "corner", "position_difficulty": "only"},
                {"area": "corner", "position_difficulty": "hard"},
                {"area": "edge", "position_difficulty": "normal"},
                {"area": "center", "position_difficulty": "easy"},
            ]
        )
        out = aggregate_area_difficulty([k])
        assert out["corner"]["only"] == 1
        assert out["corner"]["hard"] == 1
        assert out["edge"]["normal"] == 1
        assert out["center"]["easy"] == 1
        # The grid stays complete (zero cells stay zero).
        assert out["center"]["only"] == 0

    def test_critical_3_contributes(self):
        k = _make_karte(
            critical_3={
                "black": [{"area": "center", "position_difficulty": "hard"}],
                "white": [],
            }
        )
        out = aggregate_area_difficulty([k])
        assert out["center"]["hard"] == 1

    def test_unknown_area_skipped(self):
        k = _make_karte(
            important_moves=[
                {"area": "mystery", "position_difficulty": "normal"},
            ]
        )
        out = aggregate_area_difficulty([k])
        # No "mystery" area created; everything stays at 0.
        assert sum(v for d in out.values() for v in d.values()) == 0

    def test_unknown_difficulty_normalized_to_unknown(self):
        k = _make_karte(
            important_moves=[
                {"area": "corner", "position_difficulty": "weird_value"},
                {"area": "corner", "position_difficulty": ""},
                {"area": "corner"},  # missing key
            ]
        )
        out = aggregate_area_difficulty([k])
        assert out["corner"]["unknown"] == 3
        assert out["corner"]["normal"] == 0

    def test_area_is_uppercased_normalized(self):
        k = _make_karte(
            important_moves=[
                {"area": "CORNER", "position_difficulty": "EASY"},
            ]
        )
        out = aggregate_area_difficulty([k])
        assert out["corner"]["easy"] == 1

    def test_non_dict_move_skipped(self):
        k = _make_karte(
            important_moves=[
                "not-a-dict",
                {"area": "corner", "position_difficulty": "easy"},
                None,
            ]
        )
        out = aggregate_area_difficulty([k])
        assert out["corner"]["easy"] == 1


# ---------------------------------------------------------------------------
# 3. detect_loss_spike_windows
# ---------------------------------------------------------------------------


class TestLossSpikeWindows:
    def test_empty_input(self):
        assert detect_loss_spike_windows([]) == []

    def test_karte_without_loss_progression(self):
        k = _make_karte()
        assert detect_loss_spike_windows([k]) == []

    def test_no_spike_when_flat(self):
        # avg_loss is constant — no bucket exceeds 2x overall.
        k = _make_karte(
            loss_progression=[
                {"start_move": 1, "end_move": 10, "avg_loss": 0.5, "total_loss": 5.0},
                {"start_move": 11, "end_move": 20, "avg_loss": 0.5, "total_loss": 5.0},
                {"start_move": 21, "end_move": 30, "avg_loss": 0.5, "total_loss": 5.0},
            ]
        )
        assert detect_loss_spike_windows([k]) == []

    def test_single_spike_detected(self):
        # With 3 buckets (1 spike + 2 normal), the spike needs to
        # exceed 2 × the overall mean. We use a very low base
        # (0.1) and a high spike (5.0) so the inequality is met.
        k = _make_karte(
            loss_progression=[
                {"start_move": 1, "end_move": 10, "avg_loss": 0.1, "total_loss": 1.0},
                {"start_move": 11, "end_move": 20, "avg_loss": 5.0, "total_loss": 50.0},
                {"start_move": 21, "end_move": 30, "avg_loss": 0.1, "total_loss": 1.0},
            ]
        )
        # overall avg = (0.1 + 5.0 + 0.1) / 3 = 1.733
        # threshold = 1.733 * 2.0 = 3.467
        # 5.0 > 3.467 → yes, bucket 1 is a spike
        out = detect_loss_spike_windows([k])
        assert len(out) == 1
        assert out[0]["game_id"] == "g1"
        assert out[0]["start_move"] == 11
        assert out[0]["end_move"] == 20
        assert out[0]["bucket_count"] == 1
        assert out[0]["total_loss"] == 50.0

    def test_consecutive_spikes_merged(self):
        # Two adjacent spike buckets should merge into one window.
        k = _make_karte(
            loss_progression=[
                {"start_move": 1, "end_move": 10, "avg_loss": 0.1, "total_loss": 1.0},
                {"start_move": 11, "end_move": 20, "avg_loss": 5.0, "total_loss": 50.0},
                {"start_move": 21, "end_move": 30, "avg_loss": 5.0, "total_loss": 50.0},
                {"start_move": 31, "end_move": 40, "avg_loss": 0.1, "total_loss": 1.0},
            ]
        )
        # overall avg = (0.1 + 5.0 + 5.0 + 0.1) / 4 = 2.55
        # threshold = 2.55 * 2.0 = 5.1
        # 5.0 > 5.1 → no, neither spike triggers with default multiplier.
        # Use multiplier=1.5 to confirm the merge logic:
        # threshold = 2.55 * 1.5 = 3.825 → both spikes trigger, merged.
        out = detect_loss_spike_windows([k], multiplier=1.5)
        assert len(out) == 1
        assert out[0]["start_move"] == 11
        assert out[0]["end_move"] == 30
        assert out[0]["bucket_count"] == 2

    def test_multiplier_changes_threshold(self):
        k = _make_karte(
            loss_progression=[
                {"start_move": 1, "end_move": 10, "avg_loss": 0.5},
                {"start_move": 11, "end_move": 20, "avg_loss": 1.5},
            ]
        )
        # overall avg = 1.0; 1.5 > 1.0*2.0 = 2.0? No.
        # But 1.5 > 1.0*1.3 = 1.3? Yes.
        assert detect_loss_spike_windows([k]) == []
        out = detect_loss_spike_windows([k], multiplier=1.3)
        assert len(out) == 1

    def test_invalid_multiplier_raises(self):
        with pytest.raises(ValueError):
            detect_loss_spike_windows([], multiplier=0)
        with pytest.raises(ValueError):
            detect_loss_spike_windows([], multiplier=-1.0)

    def test_two_kartes_independent_runs(self):
        # Each karte has 3 buckets (1 spike + 2 normal) so the
        # 2.0x multiplier can mathematically fire. (See the math
        # in test_single_spike_detected — with 2 buckets the
        # threshold collapses to (s + n) and a strict > is
        # impossible.)
        k1 = _make_karte(
            game_id="g1",
            loss_progression=[
                {"start_move": 1, "end_move": 10, "avg_loss": 0.1},
                {"start_move": 11, "end_move": 20, "avg_loss": 5.0},
                {"start_move": 21, "end_move": 30, "avg_loss": 0.1},
            ],
        )
        k2 = _make_karte(
            game_id="g2",
            loss_progression=[
                {"start_move": 1, "end_move": 10, "avg_loss": 0.1},
                {"start_move": 11, "end_move": 20, "avg_loss": 5.0},
                {"start_move": 21, "end_move": 30, "avg_loss": 0.1},
            ],
        )
        out = detect_loss_spike_windows([k1, k2])
        assert len(out) == 2
        assert {o["game_id"] for o in out} == {"g1", "g2"}

    def test_default_multiplier(self):
        # Sanity: the default is exposed and matches expectations.
        assert _LOSS_SPIKE_MULTIPLIER_DEFAULT == 2.0


# ---------------------------------------------------------------------------
# 4. group_representative_moves_by_tag
# ---------------------------------------------------------------------------


class TestGroupRepresentativeMoves:
    def test_empty(self):
        assert group_representative_moves_by_tag([]) == {}

    def test_basic_grouping(self):
        k = _make_karte(
            important_moves=[
                {
                    "primary_tag": "life_death_error",
                    "coords": "Q16",
                    "move_number": 87,
                    "loss_clamped": 19.0,
                    "meaning_tag_label": "死活ミス",
                },
                {
                    "primary_tag": "reading_failure",
                    "coords": "D4",
                    "move_number": 62,
                    "loss_clamped": 8.5,
                    "meaning_tag_label": "読み抜け",
                },
            ]
        )
        out = group_representative_moves_by_tag([k])
        assert set(out.keys()) == {"life_death_error", "reading_failure"}
        assert out["life_death_error"][0]["coords"] == "Q16"
        assert out["life_death_error"][0]["loss"] == 19.0
        assert out["life_death_error"][0]["meaning_tag_label"] == "死活ミス"

    def test_top_n_caps(self):
        moves = [
            {
                "primary_tag": "x",
                "coords": f"X{i}",
                "move_number": i,
                "loss_clamped": float(i),
            }
            for i in range(10)
        ]
        k = _make_karte(important_moves=moves)
        out = group_representative_moves_by_tag([k], top_n=2)
        assert len(out["x"]) == 2
        # Highest loss first.
        assert out["x"][0]["loss"] == 9.0
        assert out["x"][1]["loss"] == 8.0

    def test_top_n_zero_means_unlimited(self):
        moves = [{"primary_tag": "x", "coords": "X1", "move_number": 1, "loss_clamped": 1.0} for _ in range(5)]
        k = _make_karte(important_moves=moves)
        out = group_representative_moves_by_tag([k], top_n=0)
        assert len(out["x"]) == 5

    def test_no_tag_skipped(self):
        k = _make_karte(
            important_moves=[
                {"primary_tag": None, "coords": "X1", "move_number": 1},
                {"primary_tag": "x", "coords": "X2", "move_number": 2, "loss_clamped": 1.0},
            ]
        )
        out = group_representative_moves_by_tag([k])
        assert list(out.keys()) == ["x"]

    def test_critical_3_contributes(self):
        k = _make_karte(
            critical_3={
                "black": [
                    {
                        "primary_tag": "life_death_error",
                        "gtp_coord": "Q16",
                        "move_number": 50,
                        "score_loss": 15.0,
                        "meaning_tag_label": "死活ミス",
                    }
                ],
            }
        )
        out = group_representative_moves_by_tag([k])
        assert "life_death_error" in out
        assert out["life_death_error"][0]["coords"] == "Q16"
        assert out["life_death_error"][0]["loss"] == 15.0

    def test_loss_fallback_chain(self):
        # loss_clamped > score_loss > points_lost > 0
        k = _make_karte(  # keep lint happy
            important_moves=[
                {"primary_tag": "a", "coords": "X1", "move_number": 1, "loss_clamped": 10.0},
                {"primary_tag": "b", "coords": "X2", "move_number": 2, "score_loss": 5.0},
                {"primary_tag": "c", "coords": "X3", "move_number": 3, "points_lost": 2.0},
                {"primary_tag": "d", "coords": "X4", "move_number": 4},
            ]
        )
        out = group_representative_moves_by_tag([k])
        assert out["a"][0]["loss"] == 10.0
        assert out["b"][0]["loss"] == 5.0
        assert out["c"][0]["loss"] == 2.0
        assert out["d"][0]["loss"] == 0.0

    def test_severity_order_in_output(self):
        k = _make_karte(
            important_moves=[
                {"primary_tag": "low_severity", "coords": "X1", "move_number": 1, "loss_clamped": 1.0},
                {"primary_tag": "high_severity", "coords": "X2", "move_number": 2, "loss_clamped": 10.0},
            ]
        )
        out = group_representative_moves_by_tag([k])
        keys = list(out.keys())
        assert keys[0] == "high_severity"
        assert keys[1] == "low_severity"


# ---------------------------------------------------------------------------
# 5. aggregate_data_quality
# ---------------------------------------------------------------------------


class TestAggregateDataQuality:
    def test_empty(self):
        out = aggregate_data_quality([])
        assert out["games_count"] == 0
        assert out["avg_visits"] == 0.0
        assert out["confidence_level"] == "unknown"

    def test_single_karte(self):
        k = _make_karte(
            data_quality={
                "avg_visits": 200,
                "reliability_pct": 95.0,
                "coverage_pct": 100.0,
                "total_moves": 200,
                "moves_with_visits": 200,
                "reliable_count": 190,
                "low_confidence_count": 10,
                "confidence_level": "high",
            }
        )
        out = aggregate_data_quality([k])
        assert out["games_count"] == 1
        assert out["avg_visits"] == 200.0
        assert out["reliability_pct"] == 95.0
        assert out["total_moves"] == 200
        assert out["confidence_level"] == "high"

    def test_two_kartes_mean(self):
        k1 = _make_karte(
            data_quality={
                "avg_visits": 100,
                "reliability_pct": 80.0,
                "coverage_pct": 90.0,
                "total_moves": 200,
                "moves_with_visits": 180,
                "reliable_count": 160,
                "low_confidence_count": 20,
                "confidence_level": "high",
            }
        )
        k2 = _make_karte(
            data_quality={
                "avg_visits": 300,
                "reliability_pct": 100.0,
                "coverage_pct": 100.0,
                "total_moves": 200,
                "moves_with_visits": 200,
                "reliable_count": 200,
                "low_confidence_count": 0,
                "confidence_level": "low",
            }
        )
        out = aggregate_data_quality([k1, k2])
        assert out["games_count"] == 2
        assert out["avg_visits"] == 200.0  # (100+300)/2
        assert out["reliability_pct"] == 90.0  # (80+100)/2
        assert out["total_moves"] == 400
        # Tie at 1-1; "medium" wins.
        assert out["confidence_level"] == "medium"

    def test_missing_data_quality(self):
        k = _make_karte()  # no data_quality
        out = aggregate_data_quality([k])
        assert out["games_count"] == 0
        assert out["confidence_level"] == "unknown"


# ---------------------------------------------------------------------------
# 6. build_meaning_tag_label_map
# ---------------------------------------------------------------------------


class TestMeaningTagLabelMap:
    def test_empty(self):
        # Falls back to the registry, so non-empty.
        out = build_meaning_tag_label_map([])
        assert "life_death_error" in out

    def test_uses_karte_label_first(self):
        k = _make_karte(important_moves=[{"primary_tag": "life_death_error", "meaning_tag_label": "カスタム死活"}])
        out = build_meaning_tag_label_map([k])
        assert out["life_death_error"] == "カスタム死活"

    def test_falls_back_to_registry(self):
        k = _make_karte()  # no labels
        out = build_meaning_tag_label_map([k])
        # All 12 MeaningTagId values should be present via the registry.
        assert len(out) >= 12

    def test_no_meaning_tag_label_skipped(self):
        k = _make_karte(
            important_moves=[
                {"primary_tag": "x", "meaning_tag_label": None},
                {"primary_tag": "y"},  # no label key
            ]
        )
        out = build_meaning_tag_label_map([k])
        # Labels from kartes are missing; registry fills in canonical ones.
        # The "x"/"y" tags may not be in the registry — that's fine.
        # The point: the function does not crash.
        assert isinstance(out, dict)


# ---------------------------------------------------------------------------
# 7. aggregate_kartes (one-shot entry point)
# ---------------------------------------------------------------------------


class TestAggregateKartes:
    def test_empty(self):
        view = aggregate_kartes([])
        assert isinstance(view, AggregatedKarteView)
        assert view.games_count == 0
        assert view.schema_version == "3.6"
        assert view.reason_tags_by_color == {}
        # area_difficulty_matrix always returns the full 3x5 grid
        # (zero-filled) so renderers can iterate without None-checks.
        assert set(view.area_difficulty_matrix.keys()) == {"corner", "edge", "center"}
        for area_dict in view.area_difficulty_matrix.values():
            assert area_dict == {"only": 0, "hard": 0, "normal": 0, "easy": 0, "unknown": 0}
        assert view.loss_spike_windows == []
        assert view.representative_moves_by_tag == {}
        assert view.data_quality_aggregate["games_count"] == 0
        # Registry still fills the label map.
        assert "life_death_error" in view.meaning_tag_label_map

    def test_full_flow(self):
        k1 = _make_karte(
            game_id="g1",
            reason_tags={"black": {"endgame_hint": 3}},
            important_moves=[
                {
                    "primary_tag": "life_death_error",
                    "area": "corner",
                    "position_difficulty": "only",
                    "coords": "Q16",
                    "move_number": 87,
                    "loss_clamped": 19.0,
                    "meaning_tag_label": "死活ミス",
                }
            ],
            data_quality={
                "avg_visits": 200,
                "reliability_pct": 95.0,
                "coverage_pct": 100.0,
                "total_moves": 200,
                "moves_with_visits": 200,
                "reliable_count": 190,
                "low_confidence_count": 10,
                "confidence_level": "high",
            },
            loss_progression=[
                # 3 buckets so the 2.0x multiplier can mathematically
                # fire (2-bucket inputs are degenerate: the
                # threshold collapses to (s + n) and a strict >
                # is impossible for positive losses).
                {"start_move": 1, "end_move": 10, "avg_loss": 0.1},
                {"start_move": 11, "end_move": 20, "avg_loss": 5.0},
                {"start_move": 21, "end_move": 30, "avg_loss": 0.1},
            ],
        )
        view = aggregate_kartes([k1])
        assert view.games_count == 1
        assert view.reason_tags_by_color == {"black": {"endgame_hint": 3}}
        assert view.area_difficulty_matrix["corner"]["only"] == 1
        assert len(view.loss_spike_windows) == 1
        assert "life_death_error" in view.representative_moves_by_tag
        assert view.data_quality_aggregate["games_count"] == 1
        assert view.meaning_tag_label_map["life_death_error"] == "死活ミス"

    def test_representative_top_n_parameter(self):
        moves = [{"primary_tag": "x", "coords": f"X{i}", "move_number": i, "loss_clamped": float(i)} for i in range(10)]
        k = _make_karte(important_moves=moves)
        view = aggregate_kartes([k], representative_top_n=3)
        assert len(view.representative_moves_by_tag["x"]) == 3

    def test_loss_spike_multiplier_parameter(self):
        # 3 buckets, low base + one elevated middle.
        k = _make_karte(
            loss_progression=[
                {"start_move": 1, "end_move": 10, "avg_loss": 0.5},
                {"start_move": 11, "end_move": 20, "avg_loss": 1.5},
                {"start_move": 21, "end_move": 30, "avg_loss": 0.5},
            ]
        )
        # overall avg = (0.5 + 1.5 + 0.5) / 3 = 0.833
        # multiplier 10.0: threshold = 8.33 → 1.5 not > 8.33 → no spike
        # multiplier 1.0: threshold = 0.833 → 1.5 > 0.833 → spike
        view_low = aggregate_kartes([k], loss_spike_multiplier=10.0)
        assert view_low.loss_spike_windows == []
        view_high = aggregate_kartes([k], loss_spike_multiplier=1.0)
        assert len(view_high.loss_spike_windows) == 1


# ---------------------------------------------------------------------------
# 8. Summary prompt integration
# ---------------------------------------------------------------------------


class TestSummaryPromptIntegration:
    """Tests that confirm the prompt builder uses the aggregator when
    ``kartes`` is provided, and that it stays back-compatible when
    it is not.
    """

    @pytest.fixture
    def sample_summary(self) -> dict:
        return {
            "schema_version": "3.4",
            "meta": {
                "games_analyzed": 2,
                "date_range": ["2026-07-10", "2026-07-15"],
            },
            "phase_x_mistake": {
                "middle:blunder": 4,
            },
            "weaknesses": {
                "black": [
                    {"phase": "middle", "category": "blunder", "count": 3, "total_loss": 18.0},
                ],
            },
        }

    @pytest.fixture
    def sample_karte(self) -> dict:
        return _make_karte(
            game_id="g1",
            reason_tags={"black": {"endgame_hint": 3}},
            important_moves=[
                {
                    "primary_tag": "life_death_error",
                    "area": "corner",
                    "position_difficulty": "only",
                    "coords": "Q16",
                    "move_number": 87,
                    "loss_clamped": 19.0,
                    "meaning_tag_label": "死活ミス",
                }
            ],
            data_quality={
                "avg_visits": 200,
                "reliability_pct": 95.0,
                "coverage_pct": 100.0,
                "total_moves": 200,
                "moves_with_visits": 200,
                "reliable_count": 190,
                "low_confidence_count": 10,
                "confidence_level": "high",
            },
            loss_progression=[
                {"start_move": 1, "end_move": 10, "avg_loss": 0.5},
                {"start_move": 11, "end_move": 20, "avg_loss": 2.0},
            ],
        )

    @pytest.fixture
    def base_config(self) -> SummaryPromptConfig:
        return SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=2,
        )

    # --- Back-compat ---

    def test_no_kartes_keeps_schema_3_5(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "> Schema: 3.5" in prompt.body_markdown
        assert "Aggregated Karte View" not in prompt.body_markdown

    def test_no_kartes_default_config(self, base_config):
        assert base_config.kartes is None
        assert base_config.schema_version == "3.5"

    # --- Phase 270 active path ---

    def test_kartes_bumps_schema_to_3_6(self, sample_summary, sample_karte, base_config):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=2,
            kartes=(sample_karte,),
        )
        prompt = build_summary_weakness_prompt(sample_summary, cfg)
        assert f"> Schema: {SCHEMA_VERSION_WITH_KARTES}" in prompt.body_markdown
        assert SCHEMA_VERSION_WITH_KARTES == "3.6"

    def test_kartes_renders_aggregated_section(self, sample_summary, sample_karte, base_config):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=2,
            kartes=(sample_karte,),
        )
        prompt = build_summary_weakness_prompt(sample_summary, cfg)
        body = prompt.body_markdown
        assert "Aggregated Karte View (Phase 270, schema 3.5)" in body
        assert "reason_tags_by_color" in body
        assert "endgame_hint=3" in body
        assert "area_difficulty_matrix" in body
        assert "loss_spike_windows" in body
        assert "representative_moves_by_tag" in body
        assert "Q16" in body
        assert "data_quality_aggregate" in body
        assert "meaning_tag_label_map" in body
        assert "死活ミス" in body

    def test_kartes_with_empty_tuple_is_no_op(self, sample_summary, base_config):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=2,
            kartes=(),
        )
        # Empty kartes → bool(kartes) is False → aggregated view off,
        # schema stays at the base 3.5.
        prompt = build_summary_weakness_prompt(sample_summary, cfg)
        assert "> Schema: 3.5" in prompt.body_markdown
        assert "Aggregated Karte View" not in prompt.body_markdown

    def test_two_kartes_aggregated(self, sample_summary, base_config):
        k1 = _make_karte(
            game_id="g1",
            reason_tags={"black": {"endgame_hint": 3}},
        )
        k2 = _make_karte(
            game_id="g2",
            reason_tags={"black": {"endgame_hint": 5}},
        )
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=2,
            kartes=(k1, k2),
        )
        prompt = build_summary_weakness_prompt(sample_summary, cfg)
        # The 3+5=8 total should appear.
        assert "endgame_hint=8" in prompt.body_markdown

    def test_kartes_appears_after_loss_progression(self, sample_summary, sample_karte, base_config):
        """Order in body: Summary → ... → Loss Progression → Aggregated View → 最終出力形式."""
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=2,
            kartes=(sample_karte,),
        )
        prompt = build_summary_weakness_prompt(sample_summary, cfg)
        lp_idx = prompt.body_markdown.find("### Loss Progression")
        agg_idx = prompt.body_markdown.find("### Aggregated Karte View")
        out_idx = prompt.body_markdown.find("## 最終出力形式")
        assert 0 <= lp_idx < agg_idx < out_idx

    def test_kartes_list_dict_skipped(self, sample_summary, base_config):
        """Non-karte entries in the kartes tuple are filtered out."""
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=2,
            # Two kartes plus a bogus non-karte dict (no schema_version).
            kartes=(_make_karte(game_id="g1"), _make_karte(game_id="g2"), {"meta": {}}),
        )
        prompt = build_summary_weakness_prompt(sample_summary, cfg)
        # Schema still bumped because at least one karte survived.
        assert "> Schema: 3.6" in prompt.body_markdown
