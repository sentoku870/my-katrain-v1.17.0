"""Win/Loss analysis section builder (Phase 154-D).

Builds the per-game / per-player win/loss breakdown from a parsed
:class:`GameOutcome` plus per-player loss aggregates.

Output shape (Phase 154-D, ``KarteReport.win_loss_analysis``):

    {
        "game_outcome": {"black": "win|loss|draw|unknown",
                          "white": "win|loss|draw|unknown",
                          "score_diff": float | None,
                          "raw": str},
        "by_outcome": {  # aggregated over the game(s) when available
            "win":  {"count": int, "total_loss": float,
                      "avg_loss": float, "mistake_count": int},
            "loss": {...},
            "draw": {...}
        },
        "status": "computed" | "no_result"
    }
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core.analysis.models.move_eval import get_canonical_loss_from_move
from katrain.core.reports.utils.result_parser import (
    GameOutcome,
    PlayerOutcome,
    parse_result,
)

if TYPE_CHECKING:
    from katrain.core.analysis.models import GameSummaryData, MoveEval


# Threshold for counting a move as a "mistake-or-worse" in the aggregate.
MISTAKE_THRESHOLD: float = 1.0


def _empty_bucket() -> dict[str, float | int]:
    return {"count": 0, "total_loss": 0.0, "avg_loss": 0.0, "mistake_count": 0}


def _bucket_from_moves(moves: list[MoveEval]) -> dict[str, float | int]:
    if not moves:
        return _empty_bucket()
    losses = [get_canonical_loss_from_move(m) for m in moves]
    total = sum(losses)
    mistake_count = sum(1 for x in losses if x >= MISTAKE_THRESHOLD)
    return {
        "count": len(losses),
        "total_loss": round(total, 2),
        "avg_loss": round(total / len(losses), 3),
        "mistake_count": mistake_count,
    }


def build_win_loss_analysis(
    game_summary: GameSummaryData | None,
    snapshot_moves: list[MoveEval] | None = None,
    *,
    outcome: GameOutcome | None = None,
) -> dict[str, Any]:
    """Build the win/loss analysis section.

    Args:
        game_summary: Optional :class:`GameSummaryData` carrying the
            cached outcome. When ``None`` (e.g. Karte input where the
            Game object holds the RE property), the caller should supply
            ``outcome`` directly or rely on a ``raw_result`` string.
        snapshot_moves: Optional list of :class:`MoveEval` used to build
            the ``by_outcome`` bucket. When omitted, ``by_outcome`` is
            ``{}``.
        outcome: Pre-parsed :class:`GameOutcome` (used by the Karte path
            where the outcome is derived from the ``RE`` property). When
            provided, takes precedence over ``game_summary``.

    Returns:
        Dict matching the schema documented at module top.
    """
    if outcome is None and game_summary is not None:
        if game_summary.outcome is not None:
            outcome = game_summary.outcome
        elif game_summary.result:
            outcome = parse_result(game_summary.result)

    if outcome is None:
        outcome = GameOutcome(
            black=PlayerOutcome.UNKNOWN,
            white=PlayerOutcome.UNKNOWN,
            score_diff=None,
            raw="",
        )

    by_outcome: dict[str, dict[str, float | int]] = {}
    if snapshot_moves:
        per_outcome: dict[str, list[MoveEval]] = {"win": [], "loss": [], "draw": []}
        for mv in snapshot_moves:
            player_outcome = (
                outcome.black if mv.player == "B" else outcome.white
            )
            if player_outcome == PlayerOutcome.UNKNOWN:
                continue
            key = player_outcome.value
            if key in per_outcome:
                per_outcome[key].append(mv)
        by_outcome = {k: _bucket_from_moves(v) for k, v in per_outcome.items()}

    status = "no_result" if outcome.black == PlayerOutcome.UNKNOWN else "computed"

    return {
        "game_outcome": {
            "black": outcome.black.value,
            "white": outcome.white.value,
            "score_diff": outcome.score_diff,
            "raw": outcome.raw,
        },
        "by_outcome": by_outcome,
        "status": status,
    }
