"""Summary and distribution section generators for karte report.

Contains:
- worst_move_for(): Find worst move for a player
- summary_lines_for(): Generate summary section for a player
- opponent_summary_for(): Generate opponent summary section
- common_difficult_positions(): Detect positions where both players struggled
- distribution_lines_for(): Generate mistake distribution section
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from katrain.core.analysis.logic_loss import detect_engine_type
from katrain.core.eval_metrics import classify_mistake, get_canonical_loss_from_move
from katrain.core.reports.karte.helpers import (
    format_loss_with_engine_suffix,
    has_loss_data,
)

if TYPE_CHECKING:
    from katrain.core.analysis.models import MoveEval
    from katrain.core.reports.karte.sections.context import KarteContext


def _fmt_float(val: float | None) -> str:
    """Format float value or return 'unknown'."""
    return "unknown" if val is None else f"{val:.1f}"


def _mistake_label_from_loss(
    loss_val: float | None,
    thresholds: tuple[float, float, float],
) -> str:
    """Classify a loss value using thresholds."""
    if loss_val is None:
        return "unknown"
    category = classify_mistake(score_loss=loss_val, winrate_loss=None, score_thresholds=thresholds)
    return category.value


def worst_move_for(ctx: KarteContext, player: str) -> MoveEval | None:
    """Find worst move for a player using canonical loss (KataGo/Leela compatible).

    Args:
        ctx: Karte context
        player: "B" or "W"

    Returns:
        MoveEval with highest loss, or None if no loss data exists
    """
    player_moves = [mv for mv in ctx.snapshot.moves if mv.player == player]
    # Only consider moves with loss data (0.0 is valid, None is excluded)
    moves_with_data = [mv for mv in player_moves if has_loss_data(mv)]
    if not moves_with_data:
        return None
    return max(moves_with_data, key=get_canonical_loss_from_move)


def summary_lines_for(ctx: KarteContext, player: str) -> list[str]:
    """Generate summary lines for a player.

    Args:
        ctx: Karte context
        player: "B" or "W"

    Returns:
        List of markdown lines for summary section
    """
    player_moves = [mv for mv in ctx.snapshot.moves if mv.player == player]
    total_lost = sum(max(0.0, mv.points_lost) for mv in player_moves if mv.points_lost is not None)
    worst = worst_move_for(ctx, player)
    if worst:
        worst_loss = get_canonical_loss_from_move(worst)
        worst_engine = detect_engine_type(worst)
        worst_display = (
            f"#{worst.move_number} {worst.player or '-'} {worst.gtp or '-'} "
            f"loss {format_loss_with_engine_suffix(worst_loss, worst_engine)} "
            f"({_mistake_label_from_loss(worst_loss, ctx.effective_thresholds)})"
        )
    else:
        worst_display = "unknown"
    return [
        f"- Moves analyzed: {len(player_moves)}",
        f"- Total points lost: {_fmt_float(total_lost)}",
        f"- Worst move: {worst_display}",
    ]


def opponent_summary_for(ctx: KarteContext, focus_player: str) -> list[str]:
    """Generate opponent summary section (Phase 4: opponent info).

    Args:
        ctx: Karte context
        focus_player: Focus player color ("B" or "W")

    Returns:
        List of markdown lines for opponent summary section
    """
    opponent = "W" if focus_player == "B" else "B"
    opponent_moves = [mv for mv in ctx.snapshot.moves if mv.player == opponent]
    if not opponent_moves:
        return []

    total_lost = sum(max(0.0, mv.points_lost) for mv in opponent_moves if mv.points_lost is not None)
    worst = worst_move_for(ctx, opponent)
    opponent_name = ctx.pw if opponent == "W" else ctx.pb
    if worst:
        worst_loss = get_canonical_loss_from_move(worst)
        worst_engine = detect_engine_type(worst)
        worst_display = (
            f"#{worst.move_number} {worst.player or '-'} {worst.gtp or '-'} "
            f"loss {format_loss_with_engine_suffix(worst_loss, worst_engine)} "
            f"({_mistake_label_from_loss(worst_loss, ctx.effective_thresholds)})"
        )
    else:
        worst_display = "unknown"
    return [
        f"## Opponent Summary ({opponent_name})",
        f"- Moves analyzed: {len(opponent_moves)}",
        f"- Total points lost: {_fmt_float(total_lost)}",
        f"- Worst move: {worst_display}",
        "",
    ]


def common_difficult_positions(ctx: KarteContext) -> list[str]:
    """Detect positions where both players made significant errors (Phase 4).

    Args:
        ctx: Karte context

    Returns:
        List of markdown lines for common difficult positions section
    """
    # Detect consecutive moves where both players lost 2+ points
    difficult = []
    moves_list = list(ctx.snapshot.moves)
    for i in range(len(moves_list) - 1):
        mv = moves_list[i]
        next_mv = moves_list[i + 1]
        # Both players lost 2+ points each
        if (
            mv.points_lost is not None
            and mv.points_lost >= 2.0
            and next_mv.points_lost is not None
            and next_mv.points_lost >= 2.0
        ):
            # Verify turn alternation
            if mv.player != next_mv.player:
                total = mv.points_lost + next_mv.points_lost
                # Assign losses correctly to black/white
                if mv.player == "B":
                    b_loss, w_loss = mv.points_lost, next_mv.points_lost
                else:
                    b_loss, w_loss = next_mv.points_lost, mv.points_lost
                difficult.append((mv.move_number, b_loss, w_loss, total))

    if not difficult:
        return []

    difficult.sort(key=lambda x: x[3], reverse=True)
    lines = ["## Common Difficult Positions", ""]
    lines.append("Both players made significant errors (2+ points) in consecutive moves:")
    lines.append("")
    lines.append("| Move # | Black Loss | White Loss | Total Loss |")
    lines.append("|--------|------------|------------|------------|")
    for move_num, b_loss, w_loss, total in difficult[:5]:
        lines.append(f"| {move_num}-{move_num + 1} | {b_loss:.1f} | {w_loss:.1f} | {total:.1f} |")
    lines.append("")
    return lines


def distribution_lines_for(
    ctx: KarteContext,
    player: str,
    bucket_label_func: Callable[[Any], str],
) -> list[str]:
    """Generate mistake distribution lines for a player.

    Args:
        ctx: Karte context
        player: "B" or "W"
        bucket_label_func: Function to generate bucket labels (from builder)

    Returns:
        List of markdown lines for distribution section
    """
    if ctx.histogram is None:
        return ["- Mistake buckets: unknown"]
    lines = ["- Mistake buckets (points lost):"]
    for idx, bucket in enumerate(ctx.histogram):
        label = bucket_label_func(idx)
        lines.append(f"  - {label}: {bucket[player]}")
    return lines
