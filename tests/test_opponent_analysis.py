"""Tests for Phase 155-D opponent-strength loss correlation builder."""
from __future__ import annotations

import pytest

from katrain.core.analysis.models import EvalSnapshot, MistakeCategory, MoveEval
from katrain.core.analysis.models.skill import GameSummaryData
from katrain.core.reports.sections.opponent_analysis import (
    MIN_SAMPLE_SIZE,
    MISTAKE_THRESHOLD,
    build_opponent_strength_loss_correlation,
)


def make_move(move_number: int, loss: float, player: str = "B") -> MoveEval:
    move = MoveEval(
        move_number=move_number,
        player=player,
        gtp=f"D{move_number}",
        score_before=0.0,
        score_after=-loss if player == "B" else loss,
        delta_score=-loss if player == "B" else loss,
        winrate_before=0.5,
        winrate_after=0.5,
        delta_winrate=0.0,
        points_lost=loss,
        realized_points_lost=None,
        root_visits=200,
    )
    move.score_loss = loss
    move.mistake_category = (
        MistakeCategory.MISTAKE if loss >= 1.0 else MistakeCategory.GOOD
    )
    return move


def make_summary(
    name: str,
    black: str,
    white: str,
    moves_b: list[MoveEval],
    moves_w: list[MoveEval],
    rank_black: str | None = None,
    rank_white: str | None = None,
) -> GameSummaryData:
    snapshot = EvalSnapshot(moves=moves_b + moves_w)
    return GameSummaryData(
        game_name=name,
        player_black=black,
        player_white=white,
        snapshot=snapshot,
        board_size=(19, 19),
        rank_black=rank_black,
        rank_white=rank_white,
    )


class TestStatusEmpty:
    """Empty input / no opponent info returns the appropriate status."""

    def test_empty_list(self):
        result = build_opponent_strength_loss_correlation([], "Alice")
        assert result["status"] == "no_opponent_info"
        assert result["sample_count"] == 0

    def test_no_rank_info(self):
        games = [
            make_summary("g1", "Alice", "Bob", [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")]),
            make_summary("g2", "Alice", "Charlie", [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")]),
        ]
        result = build_opponent_strength_loss_correlation(games, "Alice")
        assert result["status"] == "no_opponent_info"


class TestStatusInsufficientData:
    """Below MIN_SAMPLE_SIZE returns insufficient_data."""

    def test_below_threshold(self):
        games = [
            make_summary(
                "g1", "Alice", "Bob",
                [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")],
                rank_white="5k",
            ),
        ]
        result = build_opponent_strength_loss_correlation(games, "Alice")
        assert result["status"] == "insufficient_data"
        assert result["sample_count"] == 1

    def test_exactly_threshold_computed(self):
        """At or above MIN_SAMPLE_SIZE returns computed."""
        games = [
            make_summary(
                f"g{i}", "Alice", "Bob",
                [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")],
                rank_white="5k",
            )
            for i in range(MIN_SAMPLE_SIZE)
        ]
        result = build_opponent_strength_loss_correlation(games, "Alice")
        assert result["status"] == "computed"
        assert result["sample_count"] == MIN_SAMPLE_SIZE


class TestBucketing:
    """Bucket assignment is correct for each rank tier."""

    def test_kyu_bucket(self):
        games = [
            make_summary(
                f"g{i}", "Alice", "Bob",
                [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")],
                rank_white="5k",
            )
            for i in range(MIN_SAMPLE_SIZE)
        ]
        result = build_opponent_strength_loss_correlation(games, "Alice")
        kyu = result["by_bucket"]["kyu"]
        assert kyu["games"] == MIN_SAMPLE_SIZE
        # Alice (black) made one move per game with loss 0.5; aggregate over
        # MIN_SAMPLE_SIZE games is 0.5 * MIN_SAMPLE_SIZE.
        assert kyu["total_loss"] == pytest.approx(0.5 * MIN_SAMPLE_SIZE, rel=1e-3)

    def test_dan_bucket(self):
        games = [
            make_summary(
                f"g{i}", "Alice", "Bob",
                [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")],
                rank_white="3d",
            )
            for i in range(MIN_SAMPLE_SIZE)
        ]
        result = build_opponent_strength_loss_correlation(games, "Alice")
        assert result["by_bucket"]["dan"]["games"] == MIN_SAMPLE_SIZE

    def test_high_dan_bucket(self):
        games = [
            make_summary(
                f"g{i}", "Alice", "Bob",
                [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")],
                rank_white="9d",
            )
            for i in range(MIN_SAMPLE_SIZE)
        ]
        result = build_opponent_strength_loss_correlation(games, "Alice")
        assert result["by_bucket"]["high_dan"]["games"] == MIN_SAMPLE_SIZE

    def test_mixed_buckets(self):
        games = [
            make_summary(
                "g1", "Alice", "Bob",
                [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")],
                rank_white="5k",
            ),
            make_summary(
                "g2", "Alice", "Charlie",
                [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")],
                rank_white="3d",
            ),
            make_summary(
                "g3", "Alice", "Dave",
                [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")],
                rank_white="5k",
            ),
            make_summary(
                "g4", "Alice", "Eve",
                [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")],
                rank_white="7d",
            ),
            make_summary(
                "g5", "Alice", "Frank",
                [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")],
                rank_white="3d",
            ),
            make_summary(
                "g6", "Alice", "Gina",
                [make_move(1, 0.5, "B")], [make_move(2, 0.5, "W")],
                rank_white="5k",
            ),
        ]
        result = build_opponent_strength_loss_correlation(games, "Alice")
        assert result["by_bucket"]["kyu"]["games"] == 3
        assert result["by_bucket"]["dan"]["games"] == 2
        assert result["by_bucket"]["high_dan"]["games"] == 1


class TestMistakeCount:
    """mistake_count uses MISTAKE_THRESHOLD (1.0)."""

    def test_threshold(self):
        assert MISTAKE_THRESHOLD == 1.0

    def test_aggregates_mistakes(self):
        games = [
            make_summary(
                f"g{i}", "Alice", "Bob",
                [make_move(1, 1.5, "B"), make_move(2, 0.3, "B"), make_move(3, 2.0, "B")],
                [make_move(4, 0.5, "W")],
                rank_white="5k",
            )
            for i in range(MIN_SAMPLE_SIZE)
        ]
        result = build_opponent_strength_loss_correlation(games, "Alice")
        kyu = result["by_bucket"]["kyu"]
        # Each game has 2 mistakes (>=1.0: 1.5 and 2.0; <1.0: 0.3).
        assert kyu["mistake_count"] == 2 * MIN_SAMPLE_SIZE


class TestPlayerFiltering:
    """Only the requested player's moves are aggregated."""

    def test_only_player_moves_count(self):
        games = [
            make_summary(
                f"g{i}", "Alice", "Bob",
                [make_move(1, 5.0, "B"), make_move(2, 0.3, "B")],
                [make_move(3, 5.0, "W"), make_move(4, 0.3, "W")],
                rank_white="5k",
            )
            for i in range(MIN_SAMPLE_SIZE)
        ]
        result = build_opponent_strength_loss_correlation(games, "Alice")
        kyu = result["by_bucket"]["kyu"]
        # Alice is black; only her moves count: 5.0 + 0.3 = 5.3 per game
        assert kyu["total_loss"] == pytest.approx(5.3 * MIN_SAMPLE_SIZE, rel=1e-3)