"""Opponent strength loss correlation (Phase 155-D).

Builds a per-player breakdown of canonical loss bucketed by the opponent's
rank bucket (``kyu`` / ``dan`` / ``high_dan`` / ``unknown``).

Output shape (Phase 155-D, ``KarteReport.opponent_strength_loss_correlation``
and ``SummaryReport.players[...].opponent_strength_loss_correlation``):

    {
        "by_bucket": {
            "kyu":      {"games": int, "total_loss": float,
                          "avg_loss": float, "mistake_count": int},
            "dan":      {...},
            "high_dan": {...},
            "unknown":  {...},
        },
        "sample_count": int,
        "status": "computed" | "insufficient_data" | "no_opponent_info"
    }

``status="insufficient_data"`` is returned when fewer than
``MIN_SAMPLE_SIZE`` games have a parseable opponent rank for the requested
player; ``status="no_opponent_info"`` when none of the games carry a
rank tag.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core.analysis.models.move_eval import get_canonical_loss_from_move
from katrain.core.reports.utils.rank_classifier import (
    RankBucket,
    classify_rank_to_bucket,
)

if TYPE_CHECKING:
    from katrain.core.analysis.models import GameSummaryData


# Threshold for counting a move as a "mistake-or-worse" in the aggregate.
MISTAKE_THRESHOLD: float = 1.0

# Minimum sample size to emit "computed" status; below this we emit
# "insufficient_data" so downstream consumers (LLMs) don't over-interpret.
MIN_SAMPLE_SIZE: int = 5


def _empty_bucket_dict() -> dict[str, float | int]:
    return {"games": 0, "total_loss": 0.0, "avg_loss": 0.0, "mistake_count": 0}


def _bucket_for_opponent(
    gd: GameSummaryData,
    player_name: str,
) -> RankBucket:
    """Return the opponent's rank bucket for the given player in this game."""
    if player_name == gd.player_black:
        return classify_rank_to_bucket(gd.rank_white).bucket
    if player_name == gd.player_white:
        return classify_rank_to_bucket(gd.rank_black).bucket
    return RankBucket.UNKNOWN


def build_opponent_strength_loss_correlation(
    game_data_list: list[GameSummaryData],
    player_name: str,
) -> dict[str, Any]:
    """Build the per-player opponent-strength loss correlation block.

    Args:
        game_data_list: Source games (each carrying ``rank_black`` /
            ``rank_white``).
        player_name: Player whose perspective to aggregate.

    Returns:
        Dict matching the schema documented at module top. The
        ``status`` field reflects data sufficiency:

        - ``"no_opponent_info"`` — no game carries an opponent rank for
          the requested player.
        - ``"insufficient_data"`` — fewer than :data:`MIN_SAMPLE_SIZE`
          games have a parseable rank.
        - ``"computed"`` — at least ``MIN_SAMPLE_SIZE`` samples.
    """
    by_bucket: dict[str, dict[str, float | int]] = {
        b.value: _empty_bucket_dict() for b in RankBucket
    }
    sample_count = 0

    for gd in game_data_list:
        bucket = _bucket_for_opponent(gd, player_name)
        if bucket == RankBucket.UNKNOWN:
            continue
        sample_count += 1
        player_color = "B" if player_name == gd.player_black else "W"
        agg = by_bucket[bucket.value]
        agg["games"] = int(agg["games"]) + 1
        game_total = 0.0
        game_mistakes = 0
        for mv in gd.snapshot.moves:
            if mv.player != player_color:
                continue
            loss_v = get_canonical_loss_from_move(mv)
            game_total += loss_v
            if loss_v >= MISTAKE_THRESHOLD:
                game_mistakes += 1
        agg["total_loss"] = float(agg["total_loss"]) + game_total
        agg["mistake_count"] = int(agg["mistake_count"]) + game_mistakes

    if sample_count == 0:
        return {
            "by_bucket": by_bucket,
            "sample_count": 0,
            "status": "no_opponent_info",
        }
    if sample_count < MIN_SAMPLE_SIZE:
        return {
            "by_bucket": by_bucket,
            "sample_count": sample_count,
            "status": "insufficient_data",
        }

    # Finalize averages (rounded)
    for bucket_dict in by_bucket.values():
        games = int(bucket_dict["games"])
        if games:
            bucket_dict["avg_loss"] = round(
                float(bucket_dict["total_loss"]) / games, 3
            )
            bucket_dict["total_loss"] = round(float(bucket_dict["total_loss"]), 2)
    return {
        "by_bucket": by_bucket,
        "sample_count": sample_count,
        "status": "computed",
    }
