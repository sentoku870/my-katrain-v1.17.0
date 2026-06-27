"""Summary section data builders for karte report (JSON output).

Phase 149 C-2: Refactored from markdown-line generators (list[str]) to JSON
data builders.

Functions:
- worst_move_for(): Find worst move for a player (helper, unchanged)
- common_difficult_positions(): Returns list[CommonDifficultItem]

Removed in Phase 149 C-2 (no JSON equivalent needed):
- summary_lines_for(): redundant with build_karte_json's `summary` block
- opponent_summary_for(): redundant with build_karte_json's `summary` block
- distribution_lines_for(): redundant with build_karte_json's
  `summary.mistake_distribution` block
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core.eval_metrics import get_canonical_loss_from_move
from katrain.core.reports.karte.helpers import has_loss_data

if TYPE_CHECKING:
    from katrain.core.analysis.models import MoveEval
    from katrain.core.reports.karte.sections.context import KarteContext


def worst_move_for(ctx: "KarteContext", player: str) -> "MoveEval | None":
    """Find worst move for a player using canonical loss (KataGo/Leela compatible).

    Args:
        ctx: Karte context
        player: "B" or "W"

    Returns:
        MoveEval with highest loss, or None if no loss data exists
    """
    player_moves = [mv for mv in ctx.snapshot.moves if mv.player == player]
    moves_with_data = [mv for mv in player_moves if has_loss_data(mv)]
    if not moves_with_data:
        return None
    return max(moves_with_data, key=get_canonical_loss_from_move)


def common_difficult_positions(ctx: "KarteContext") -> list[dict[str, Any]]:
    """Detect positions where both players made significant errors (>= 2 points).

    Args:
        ctx: Karte context

    Returns:
        List of CommonDifficultItem dicts, sorted by total_loss desc.
        Empty list when no qualifying positions found.
    """
    difficult: list[tuple[int, float, float, float]] = []
    moves_list = list(ctx.snapshot.moves)
    for i in range(len(moves_list) - 1):
        mv = moves_list[i]
        next_mv = moves_list[i + 1]
        if (
            mv.points_lost is not None
            and mv.points_lost >= 2.0
            and next_mv.points_lost is not None
            and next_mv.points_lost >= 2.0
        ):
            if mv.player != next_mv.player:
                total = mv.points_lost + next_mv.points_lost
                if mv.player == "B":
                    b_loss, w_loss = mv.points_lost, next_mv.points_lost
                else:
                    b_loss, w_loss = next_mv.points_lost, mv.points_lost
                difficult.append((mv.move_number, b_loss, w_loss, total))

    if not difficult:
        return []

    difficult.sort(key=lambda x: x[3], reverse=True)

    return [
        {
            "move_range": [move_num, move_num + 1],
            "black_loss": round(b_loss, 2),
            "white_loss": round(w_loss, 2),
            "total_loss": round(total, 2),
        }
        for move_num, b_loss, w_loss, total in difficult[:5]
    ]