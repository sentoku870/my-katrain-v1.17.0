"""Summary section data builders for karte report (JSON output).

Phase 149 C-2: Refactored from markdown-line generators (list[str]) to JSON
data builders.

Phase 153-B: Removed `common_difficult_positions()` (section removed from
output). Kept as a stub returning [] to avoid breaking callers.

Functions:
- worst_move_for(): Find worst move for a player (helper, unchanged)
- common_difficult_positions(): Stub returning [] (section removed in 153-B)

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
    """Stub returning [].

    Phase 153-B: The `common_difficult_positions` section has been removed
    from the Karte JSON output (redundant with critical_3 / important_moves).
    Kept as a stub so existing imports do not break; will be removed in a
    follow-up cleanup pass.

    Args:
        ctx: Karte context (unused)

    Returns:
        Empty list.
    """
    return []