"""Tests for Phase 154-B loss progression analyzer."""
from __future__ import annotations

import pytest

from katrain.core.analysis.models import MistakeCategory, MoveEval
from katrain.core.reports.utils.loss_progression import (
    MISTAKE_THRESHOLD,
    LossBucket,
    compute_loss_progression,
)


def make_move(
    move_number: int,
    loss: float,
    *,
    player: str = "B",
) -> MoveEval:
    """Build a minimal MoveEval with the given canonical loss."""
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


class TestLossProgressionBasic:
    """Bucket generation and basic aggregates."""

    def test_empty_returns_empty(self):
        assert compute_loss_progression([]) == []

    def test_single_bucket(self):
        moves = [make_move(1, 0.5), make_move(2, 1.5), make_move(3, 0.3)]
        buckets = compute_loss_progression(moves, bucket_size=10)
        assert len(buckets) == 1
        b = buckets[0]
        assert b.start_move == 1
        assert b.move_count == 3
        assert b.total_loss == pytest.approx(2.3)
        assert b.avg_loss == pytest.approx(2.3 / 3, rel=1e-3)
        assert b.mistake_count == 1  # only move 2 (loss 1.5)

    def test_three_buckets(self):
        moves = [make_move(i, 0.5) for i in range(1, 26)]
        buckets = compute_loss_progression(moves, bucket_size=10)
        assert len(buckets) == 3
        assert [b.start_move for b in buckets] == [1, 11, 21]
        assert [b.end_move for b in buckets] == [10, 20, 25]
        assert [b.move_count for b in buckets] == [10, 10, 5]

    def test_final_bucket_size_smaller_than_bucket_size(self):
        """Final bucket may be smaller than bucket_size when total_moves is not a multiple."""
        moves = [make_move(i, 0.5) for i in range(1, 26)]
        buckets = compute_loss_progression(moves, bucket_size=10)
        assert buckets[-1].move_count == 5


class TestLossProgressionMistakeCount:
    """mistake_count threshold semantics."""

    def test_mistake_threshold_is_one(self):
        """Default threshold aligns with the standard preset inaccuracy floor."""
        assert MISTAKE_THRESHOLD == 1.0

    def test_at_threshold_counts_as_mistake(self):
        moves = [make_move(1, 1.0)]
        buckets = compute_loss_progression(moves)
        assert buckets[0].mistake_count == 1

    def test_below_threshold_not_mistake(self):
        moves = [make_move(1, 0.99)]
        buckets = compute_loss_progression(moves)
        assert buckets[0].mistake_count == 0


class TestLossProgressionValidation:
    """Argument validation."""

    def test_zero_bucket_size_raises(self):
        with pytest.raises(ValueError):
            compute_loss_progression([make_move(1, 0.5)], bucket_size=0)

    def test_negative_bucket_size_raises(self):
        with pytest.raises(ValueError):
            compute_loss_progression([make_move(1, 0.5)], bucket_size=-1)


class TestLossProgressionShape:
    """Output shape conforms to LossBucket dataclass."""

    def test_loss_bucket_dataclass(self):
        moves = [make_move(1, 0.5)]
        buckets = compute_loss_progression(moves)
        assert isinstance(buckets[0], LossBucket)
        for field in ("start_move", "end_move", "move_count", "total_loss", "avg_loss", "mistake_count"):
            assert hasattr(buckets[0], field)