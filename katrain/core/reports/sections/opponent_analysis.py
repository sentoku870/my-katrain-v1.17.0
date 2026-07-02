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
            "narrative": "No opponent rank information available.",
        }

    # Finalize averages (rounded) for every bucket with at least one game.
    # ``MIN_SAMPLE_SIZE`` gates only the ``status`` field (so consumers know
    # whether the aggregate is statistically meaningful); the per-bucket
    # averages are still populated so Karte (single-game) and small-sample
    # Summary runs don't report ``avg_loss: 0.0`` alongside non-zero totals.
    #
    # Phase 158-H: round ``total_loss`` BEFORE dividing so the displayed
    # ``avg_loss`` matches ``total_loss`` for the single-game Karte case
    # (the previous order — divide then round each — could yield
    # ``total_loss=99.58`` and ``avg_loss=99.579`` for the same 1-game
    # bucket, which is mathematically inconsistent).
    for bucket_dict in by_bucket.values():
        games = int(bucket_dict["games"])
        if games:
            rounded_total = round(float(bucket_dict["total_loss"]), 2)
            bucket_dict["total_loss"] = rounded_total
            bucket_dict["avg_loss"] = round(rounded_total / games, 3)

    if sample_count < MIN_SAMPLE_SIZE:
        return {
            "by_bucket": by_bucket,
            "sample_count": sample_count,
            "status": "insufficient_data",
            "narrative": _build_opponent_narrative(by_bucket, sample_count),
        }
    return {
        "by_bucket": by_bucket,
        "sample_count": sample_count,
        "status": "computed",
        "narrative": _build_opponent_narrative(by_bucket, sample_count),
    }


def _build_opponent_narrative(
    by_bucket: dict[str, dict[str, Any]],
    sample_count: int,
) -> str:
    """Build a short natural-language summary of the opponent-strength
    correlation (Phase 158-I).

    The narrative lets an LLM consumer answer "what does the
    correlation say about this player?" without re-parsing the
    ``by_bucket`` numbers. The output is intentionally short (one or
    two sentences) so it fits inside a system prompt without bloating
    the JSON.

    Examples:
        - "3 games, all against dan opponents; avg_loss 4.42"
        - "1 game against a high-dan opponent; avg_loss 9.58"
        - "No opponent rank information available"
    """
    active_buckets = [
        (name, data) for name, data in by_bucket.items() if int(data.get("games", 0)) > 0
    ]
    if not active_buckets:
        return "No opponent rank information available."
    bucket_labels = {
        "kyu": "kyu",
        "dan": "dan",
        "high_dan": "high-dan",
        "unknown": "unranked",
    }
    if len(active_buckets) == 1:
        name, data = active_buckets[0]
        label = bucket_labels.get(name, name)
        plural = "" if sample_count == 1 else "s"
        return (
            f"{sample_count} game{plural} against {label} opponents; "
            f"avg_loss {float(data['avg_loss']):.2f}"
        )
    parts = []
    for name, data in active_buckets:
        label = bucket_labels.get(name, name)
        parts.append(
            f"{int(data['games'])} vs {label} (avg {float(data['avg_loss']):.2f})"
        )
    return f"{sample_count} games; " + ", ".join(parts)
