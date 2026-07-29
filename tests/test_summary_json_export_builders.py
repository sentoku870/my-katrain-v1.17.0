"""Unit tests for ``katrain.core.reports.summary_json_export`` (Phase 282-P2A).

The ``summary_json_export`` module (768 LOC) had 14/16 ``_build_*``
internal helpers without direct tests — only ``build_summary_json``
itself was exercised via downstream consumer tests. This file locks in
the contract of each pure helper.

The orchestrating ``_build_player_stats_block`` is integration-tested
by the existing ``build_summary_json`` tests, so we focus here on the
4-state and 3-state status logic, distribution math, and edge cases
that the consumer tests gloss over.

Coverage targets:
- ``_data_status_for`` 3-state contract
- ``_build_overall_block`` 5-field structure
- ``_build_mistake_distribution`` per-category iteration
- ``_build_phase_distribution`` yose -> endgame mapping
- ``_build_reason_tags_block`` 3-state (computed / computed_empty)
- ``_build_mistake_sequences_block`` 3-state status
- ``_build_empty_player_stats_block`` zero-data fallback
- ``_derive_basic_reason_tags`` heuristic threshold + phase
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from katrain.core.analysis import MistakeCategory
from katrain.core.reports.summary_json_export import (
    _build_empty_player_stats_block,
    _build_mistake_distribution,
    _build_mistake_sequences_block,
    _build_overall_block,
    _build_phase_distribution,
    _build_reason_tags_block,
    _data_status_for,
    _derive_basic_reason_tags,
)

# =============================================================================
# Fixtures / helpers
# =============================================================================


def _make_stats(
    *,
    total_games: int = 5,
    total_moves: int = 100,
    total_points_lost: float = 50.0,
    avg_points_lost_per_move: float = 0.5,
    mistake_counts: dict | None = None,
    phase_moves: dict | None = None,
    phase_loss: dict | None = None,
    reason_tags_counts: dict | None = None,
    tagged_moves_count: int = 0,
    tag_occurrences_total: int = 0,
) -> SimpleNamespace:
    """Create a SimpleNamespace stand-in for SummaryStats with the
    minimum attributes used by the ``_build_*`` helpers.

    Using SimpleNamespace (not a real SummaryStats) avoids needing
    to construct an EvalSnapshot and lets each test specify only the
    fields it exercises.
    """
    mistake_counts = mistake_counts or {}
    return SimpleNamespace(
        total_games=total_games,
        total_moves=total_moves,
        total_points_lost=total_points_lost,
        avg_points_lost_per_move=avg_points_lost_per_move,
        mistake_counts=mistake_counts,
        phase_moves=phase_moves or {},
        phase_loss=phase_loss or {},
        reason_tags_counts=reason_tags_counts or {},
        tagged_moves_count=tagged_moves_count,
        tag_occurrences_total=tag_occurrences_total,
        # Methods used by helpers
        get_mistake_percentage=lambda cat: 100.0 * mistake_counts.get(cat, 0) / max(total_moves, 1),
        get_mistake_avg_loss=lambda cat: 0.0,  # not exercised by these tests
        get_phase_avg_loss=lambda phase: (
            (phase_loss or {}).get(phase, 0.0) / max((phase_moves or {}).get(phase, 0), 1)
            if (phase_moves or {}).get(phase, 0) > 0
            else 0.0
        ),
    )


def _make_move(
    *,
    move_number: int = 1,
    score_loss: float = 1.0,
    points_lost: float | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        move_number=move_number,
        score_loss=score_loss,
        points_lost=points_lost if points_lost is not None else score_loss,
    )


# =============================================================================
# _data_status_for
# =============================================================================


class TestDataStatusFor:
    @pytest.mark.parametrize(
        "count,expected",
        [
            (0, "not_applicable_no_games"),
            (1, "insufficient_data"),
            (2, "computed"),
            (10, "computed"),
        ],
    )
    def test_state_mapping(self, count, expected):
        assert _data_status_for(count) == expected

    def test_min_threshold_is_2(self):
        """Boundary: 1 -> insufficient, 2 -> computed."""
        assert _data_status_for(1) == "insufficient_data"
        assert _data_status_for(2) == "computed"


# =============================================================================
# _build_overall_block
# =============================================================================


class TestBuildOverallBlock:
    def test_all_fields_present(self):
        stats = _make_stats(
            total_games=5,
            total_moves=100,
            total_points_lost=50.0,
            avg_points_lost_per_move=0.5,
        )
        block = _build_overall_block(stats, "high")
        assert block == {
            "total_games": 5,
            "total_moves": 100,
            "total_loss": 50.0,
            "avg_loss": 0.5,
            "confidence": "high",
        }

    def test_total_loss_rounded_to_2_decimals(self):
        # PR-06 unified summary rounding at 2 decimals (Phase 158-H policy).
        stats = _make_stats(total_points_lost=50.45678)
        block = _build_overall_block(stats, "medium")
        assert block["total_loss"] == 50.46

    def test_avg_loss_rounded_to_3_decimal(self):
        stats = _make_stats(avg_points_lost_per_move=0.45678)
        block = _build_overall_block(stats, "medium")
        assert block["avg_loss"] == 0.457

    def test_confidence_passthrough(self):
        for c in ("high", "medium", "low"):
            assert _build_overall_block(_make_stats(), c)["confidence"] == c


# =============================================================================
# _build_mistake_distribution
# =============================================================================


class TestBuildMistakeDistribution:
    def test_includes_all_categories(self):
        """All 4 MistakeCategory values must appear in output."""
        stats = _make_stats()
        dist = _build_mistake_distribution(stats)
        # 4 categories: GOOD, INACCURACY, MISTAKE, BLUNDER
        assert len(dist) == len(list(MistakeCategory))
        for cat in MistakeCategory:
            assert cat.value.lower() in dist

    def test_each_category_has_required_keys(self):
        stats = _make_stats()
        dist = _build_mistake_distribution(stats)
        for _cat_key, entry in dist.items():
            assert set(entry.keys()) == {"count", "pct", "denominator", "avg_loss"}

    def test_count_from_mistake_counts(self):
        from katrain.core.analysis.models.enums import MistakeCategory

        stats = _make_stats(
            mistake_counts={
                MistakeCategory.BLUNDER: 3,
                MistakeCategory.MISTAKE: 10,
                MistakeCategory.INACCURACY: 5,
            }
        )
        dist = _build_mistake_distribution(stats)
        assert dist["blunder"]["count"] == 3
        assert dist["mistake"]["count"] == 10
        assert dist["inaccuracy"]["count"] == 5
        assert dist["good"]["count"] == 0

    def test_denominator_is_total_moves(self):
        stats = _make_stats(total_moves=200)
        dist = _build_mistake_distribution(stats)
        for cat in MistakeCategory:
            assert dist[cat.value.lower()]["denominator"] == 200

    def test_pct_calculation(self):
        from katrain.core.analysis.models.enums import MistakeCategory

        # 5 blunders out of 100 moves -> 5.0%
        stats = _make_stats(
            total_moves=100,
            mistake_counts={MistakeCategory.BLUNDER: 5},
        )
        dist = _build_mistake_distribution(stats)
        assert dist["blunder"]["pct"] == 5.0


# =============================================================================
# _build_phase_distribution
# =============================================================================


class TestBuildPhaseDistribution:
    def test_uses_public_phase_keys(self):
        """Output keys must be opening/middle/endgame, not internal yose."""
        stats = _make_stats(phase_moves={"opening": 10, "middle": 30, "yose": 20})
        dist = _build_phase_distribution(stats)
        assert "opening" in dist
        assert "middle" in dist
        assert "endgame" in dist
        assert "yose" not in dist

    def test_yose_aggregated_as_endgame(self):
        stats = _make_stats(
            phase_moves={"yose": 20},
            phase_loss={"yose": 8.0},
        )
        dist = _build_phase_distribution(stats)
        assert dist["endgame"]["moves"] == 20
        assert dist["endgame"]["total_loss"] == 8.0

    def test_missing_phase_defaults_to_zero(self):
        stats = _make_stats(phase_moves={}, phase_loss={})
        dist = _build_phase_distribution(stats)
        for phase in ("opening", "middle", "endgame"):
            assert dist[phase]["moves"] == 0
            assert dist[phase]["total_loss"] == 0.0

    def test_total_loss_rounded_to_2_decimals(self):
        """Phase 158-H: 2-decimal rounding for total_loss (matches rest of JSON)."""
        stats = _make_stats(phase_loss={"middle": 8.456789})
        dist = _build_phase_distribution(stats)
        assert dist["middle"]["total_loss"] == 8.46

    def test_avg_loss_rounded_to_3_decimals(self):
        stats = _make_stats(
            phase_moves={"middle": 10},
            phase_loss={"middle": 5.1234567},
        )
        dist = _build_phase_distribution(stats)
        # 5.1234567 / 10 = 0.51234567, rounded to 3 decimals = 0.512
        assert dist["middle"]["avg_loss"] == 0.512


# =============================================================================
# _build_reason_tags_block
# =============================================================================


class TestBuildReasonTagsBlock:
    def test_empty_input_returns_computed_empty(self):
        """tag_occurrences_total == 0 -> computed_empty."""
        stats = _make_stats(tag_occurrences_total=0, reason_tags_counts={})
        block = _build_reason_tags_block(stats)
        assert block["status"] == "computed_empty"
        assert block["data"] == {}
        assert block["stats"] == {"tagged_moves_count": 0, "tag_occurrences_total": 0}

    def test_normalized_counts_aggregate(self):
        """REASON_CODE_ALIASES maps raw tags to canonical names.

        Format is ``{raw_tag: canonical_tag}``. Both raw and canonical
        keys in the input should be merged under the canonical key.
        """
        from katrain.core.reports.definitions import REASON_CODE_ALIASES

        if not REASON_CODE_ALIASES:
            pytest.skip("No aliases defined; skipping normalization test")

        # Pick any pair: alias (key) -> canonical (value)
        raw_tag = next(iter(REASON_CODE_ALIASES))
        canonical_tag = REASON_CODE_ALIASES[raw_tag]
        if isinstance(canonical_tag, list):
            pytest.skip("Complex alias mapping; skipping simple test")

        stats = _make_stats(
            tag_occurrences_total=10,
            reason_tags_counts={raw_tag: 5, canonical_tag: 3},
            tagged_moves_count=8,
        )
        block = _build_reason_tags_block(stats)
        # Both raw and canonical should be merged under canonical
        assert block["data"][canonical_tag]["count"] == 8

    def test_data_sorted_by_count_desc(self):
        stats = _make_stats(
            tag_occurrences_total=100,
            reason_tags_counts={"a": 10, "b": 50, "c": 20},
            tagged_moves_count=80,
        )
        block = _build_reason_tags_block(stats)
        counts_in_order = [entry["count"] for entry in block["data"].values()]
        assert counts_in_order == sorted(counts_in_order, reverse=True)

    def test_pct_is_share_of_total(self):
        stats = _make_stats(
            tag_occurrences_total=200,
            reason_tags_counts={"x": 50},
            tagged_moves_count=100,
        )
        block = _build_reason_tags_block(stats)
        assert block["data"]["x"]["pct"] == 25.0
        assert block["data"]["x"]["denominator_type"] == "tag_occurrences"
        assert block["data"]["x"]["total_tag_occurrences"] == 200


# =============================================================================
# _build_mistake_sequences_block
# =============================================================================


class TestBuildMistakeSequencesBlock:
    def test_empty_game_list_not_applicable(self):
        block = _build_mistake_sequences_block(sequences=[], game_data_list=[])
        assert block["status"] == "not_applicable_no_games"
        assert block["data"] == []

    def test_no_sequences_no_streak_detected(self):
        block = _build_mistake_sequences_block(
            sequences=[],
            game_data_list=[MagicMock()],  # non-empty
        )
        assert block["status"] == "no_streak_detected"
        assert block["data"] == []

    def test_with_sequences_status_computed(self):
        block = _build_mistake_sequences_block(
            sequences=[
                {
                    "game": "g1",
                    "start": 10,
                    "end": 12,
                    "count": 3,
                    "total_loss": 4.5,
                }
            ],
            game_data_list=[MagicMock()],
        )
        assert block["status"] == "computed"
        assert len(block["data"]) == 1

    def test_sequence_formatted_correctly(self):
        block = _build_mistake_sequences_block(
            sequences=[
                {
                    "game": "g1",
                    "start": 10,
                    "end": 12,
                    "count": 3,
                    "total_loss": 4.5,
                }
            ],
            game_data_list=[MagicMock()],
        )
        item = block["data"][0]
        assert item["game_name"] == "g1"
        assert item["move_range"] == [10, 12]
        assert item["count"] == 3
        assert item["total_loss"] == 4.5
        # 4.5 / 3 = 1.5
        assert item["avg_loss"] == 1.5

    def test_total_loss_rounded_to_1_decimal(self):
        block = _build_mistake_sequences_block(
            sequences=[{"game": "g1", "start": 1, "end": 2, "count": 2, "total_loss": 4.567}],
            game_data_list=[MagicMock()],
        )
        assert block["data"][0]["total_loss"] == 4.6

    def test_multiple_sequences_preserved(self):
        sequences = [
            {"game": "g1", "start": 1, "end": 2, "count": 2, "total_loss": 2.0},
            {"game": "g2", "start": 5, "end": 7, "count": 3, "total_loss": 6.0},
            {"game": "g1", "start": 50, "end": 52, "count": 3, "total_loss": 4.0},
        ]
        block = _build_mistake_sequences_block(sequences, game_data_list=[MagicMock()])
        assert len(block["data"]) == 3
        assert [d["game_name"] for d in block["data"]] == ["g1", "g2", "g1"]


# =============================================================================
# _build_empty_player_stats_block
# =============================================================================


class TestBuildEmptyPlayerStatsBlock:
    def test_overall_zeroed(self):
        block = _build_empty_player_stats_block(game_data_list=[], player_name="nobody")
        assert block["overall"]["total_games"] == 0
        assert block["overall"]["total_moves"] == 0
        assert block["overall"]["total_loss"] == 0.0
        assert block["overall"]["avg_loss"] == 0.0
        assert block["overall"]["confidence"] == "low"

    def test_mistake_distribution_empty_dict(self):
        block = _build_empty_player_stats_block(game_data_list=[], player_name="nobody")
        assert block["mistakes"] == {}

    def test_reason_tags_computed_empty(self):
        block = _build_empty_player_stats_block(game_data_list=[], player_name="nobody")
        assert block["reason_tags"]["status"] == "computed_empty"
        assert block["reason_tags"]["data"] == {}

    def test_mistake_sequences_no_streak(self):
        """Non-empty game_data_list + empty sequences = no_streak_detected."""
        block = _build_empty_player_stats_block(game_data_list=[MagicMock()], player_name="nobody")
        assert block["mistake_sequences"]["status"] == "no_streak_detected"

    def test_top_mistakes_empty(self):
        block = _build_empty_player_stats_block(game_data_list=[], player_name="nobody")
        assert block["top_mistakes"] == []

    def test_has_required_keys(self):
        """Empty block must have the same top-level shape as non-empty."""
        block = _build_empty_player_stats_block(game_data_list=[], player_name="nobody")
        for key in (
            "overall",
            "mistakes",
            "phases",
            "reason_tags",
            "mistake_sequences",
            "top_mistakes",
            "win_loss_analysis",
        ):
            assert key in block, f"Missing key {key!r} in empty player stats block"


# =============================================================================
# _derive_basic_reason_tags
# =============================================================================


class TestDeriveBasicReasonTags:
    def test_no_loss_above_threshold(self):
        move = _make_move(score_loss=0.3)
        tags = _derive_basic_reason_tags(move)
        # Below 2.0 threshold and not in yose
        assert "heavy_loss" not in tags

    def test_loss_above_threshold(self):
        """loss >= 2.0 (BAD_MOVE_LOSS_THRESHOLD * 4) -> heavy_loss tag."""
        move = _make_move(score_loss=2.5, move_number=10)
        tags = _derive_basic_reason_tags(move)
        assert "heavy_loss" in tags

    def test_yose_move_adds_endgame_hint(self):
        """Late game (move_number > 200 on 19x19) -> endgame_hint."""
        # classify_game_phase on 19x19: yose starts at move_number > 200
        move = _make_move(score_loss=0.5, move_number=201)
        tags = _derive_basic_reason_tags(move)
        assert "endgame_hint" in tags

    def test_opening_move_no_endgame_hint(self):
        move = _make_move(score_loss=0.5, move_number=10)
        tags = _derive_basic_reason_tags(move)
        assert "endgame_hint" not in tags

    def test_combined_tags_when_loss_in_yose(self):
        move = _make_move(score_loss=3.0, move_number=201)
        tags = _derive_basic_reason_tags(move)
        assert "heavy_loss" in tags
        assert "endgame_hint" in tags

    def test_uses_canonical_loss(self):
        """Phase 159A: uses get_canonical_loss_from_move, not just score_loss.

        ``get_canonical_loss_from_move`` returns ``score_loss`` for
        canonical loss, but ``points_lost`` (when set explicitly) is
        also valid input. We test by checking the threshold logic
        against score_loss=3.0 (above the 2.0 threshold).
        """
        move = SimpleNamespace(move_number=10, score_loss=3.0, points_lost=None)
        tags = _derive_basic_reason_tags(move)
        assert "heavy_loss" in tags

    def test_zero_move_number_treated_as_opening(self):
        """move_number=0 falls through to non-yose (not in endgame)."""
        move = _make_move(score_loss=1.0, move_number=0)
        tags = _derive_basic_reason_tags(move)
        assert "endgame_hint" not in tags


# =============================================================================
# Structural guard
# =============================================================================


class TestPublicSurface:
    """Lock in the public function surface of summary_json_export.py."""

    @pytest.mark.parametrize(
        "func_name",
        [
            "build_summary_json",
            "_data_status_for",
            "_build_player_stats_block",
            "_build_empty_player_stats_block",
            "_build_overall_block",
            "_build_mistake_distribution",
            "_build_phase_distribution",
            "_build_reason_tags_block",
            "_build_mistake_sequences_block",
            "_build_top_mistakes_block",
            "_format_top_mistake_item",
            "_build_opponent_correlation_block",
            "_compute_loss_progression_block",
            "_compute_player_win_loss_analysis",
            "_ensure_tags_for_top_moves",
            "_derive_basic_reason_tags",
        ],
    )
    def test_function_exists(self, func_name):
        from katrain.core.reports import summary_json_export

        assert hasattr(summary_json_export, func_name), f"summary_json_export.py missing {func_name!r}"
