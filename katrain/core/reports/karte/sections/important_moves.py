"""Important moves section generators for karte report.

Contains:
- get_context_info_for_move(): Extract context info (candidates, best gap, danger)
- important_lines_for(): Generate important moves table
- reason_tags_distribution_for(): Generate reason tags distribution
- critical_3_section_for(): Generate Critical 3 section for focused review
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from katrain.core import eval_metrics
from katrain.core.analysis.cluster_classifier import (
    StoneCache,
    _get_cluster_context_for_move,
)
from katrain.core.analysis.critical_moves import select_critical_moves
from katrain.core.analysis.logic_loss import detect_engine_type
from katrain.core.analysis.meaning_tags import get_meaning_tag_label_safe
from katrain.core.analysis.reason_generator import generate_reason_safe
from katrain.core.analysis.time import get_pacing_icon
from katrain.core.batch.helpers import format_wr_gap
from katrain.core.batch.stats import get_area_from_gtp
from katrain.core.constants import OUTPUT_DEBUG
from katrain.core.eval_metrics import classify_mistake, get_canonical_loss_from_move
from katrain.core.reports.karte.helpers import format_loss_with_engine_suffix

if TYPE_CHECKING:
    from katrain.core.analysis.models import MoveEval
    from katrain.core.reports.karte.sections.context import KarteContext

logger = logging.getLogger(__name__)


def _mistake_label_from_loss(
    loss_val: float | None,
    thresholds: tuple[float, float, float],
) -> str:
    """Classify a loss value using thresholds."""
    if loss_val is None:
        return "unknown"
    category = classify_mistake(score_loss=loss_val, winrate_loss=None, score_thresholds=thresholds)
    return category.value


def get_context_info_for_move(game: Any, move_eval: MoveEval) -> dict[str, Any]:
    """Extract context info (candidates, best gap, danger, best move) for a move.

    CRITICAL FIX: Best move and candidates are extracted from PRE-MOVE node
    (node.parent), not the post-move node. This ensures we see the candidate
    moves that were available BEFORE the move was played.

    Args:
        game: Game object
        move_eval: MoveEval to get context for

    Returns:
        Dict with keys: candidates, best_gap, danger, best_move
    """
    context: dict[str, Any] = {
        "candidates": None,
        "best_gap": None,
        "danger": None,
        "best_move": None,
    }

    try:
        node = game._find_node_by_move_number(move_eval.move_number)
        if not node:
            return context

        # CRITICAL: Use parent node for candidate moves (PRE-MOVE position)
        parent_node = getattr(node, "parent", None)

        if parent_node and hasattr(parent_node, "candidate_moves"):
            candidate_moves = parent_node.candidate_moves
            if candidate_moves:
                context["candidates"] = len(candidate_moves)

                # Best move is the first candidate (order=0)
                if candidate_moves:
                    best_candidate = candidate_moves[0]
                    context["best_move"] = best_candidate.get("move")

                # Best gap: find the played move in parent's candidates
                actual_move_gtp = move_eval.gtp
                if actual_move_gtp:
                    for candidate in candidate_moves:
                        if candidate.get("move") == actual_move_gtp:
                            winrate_lost = candidate.get("winrateLost")
                            if winrate_lost is not None:
                                context["best_gap"] = winrate_lost
                            break

        # Danger assessment from board_analysis - uses current node
        from katrain.core import board_analysis

        board_state = board_analysis.analyze_board_at_node(game, node)

        # Max danger of player's groups
        player = move_eval.player
        if player:
            my_groups = [g for g in board_state.groups if g.color == player]
            if my_groups:
                max_danger = max(
                    (board_state.danger_scores.get(g.group_id, 0) for g in my_groups),
                    default=0,
                )
                if max_danger >= 50:
                    context["danger"] = "High"
                elif max_danger >= 25:
                    context["danger"] = "Mid"
                else:
                    context["danger"] = "Low"

    except KeyError as e:
        # Expected: SGF tree structure issue (missing node data)
        if game.katrain:
            game.katrain.log(
                f"Context extraction skipped for move #{move_eval.move_number}: {e}",
                OUTPUT_DEBUG,
            )
    except Exception as e:
        # Unexpected: Internal bug - traceback required
        import traceback

        if game.katrain:
            game.katrain.log(
                f"Unexpected context error for move #{move_eval.move_number}: {e}\n{traceback.format_exc()}",
                OUTPUT_DEBUG,
            )

    return context


def important_lines_for(
    ctx: KarteContext,
    player: str,
    label: str,
) -> list[str]:
    """Generate important moves table for a player.

    Args:
        ctx: Karte context
        player: "B" or "W"
        label: Display label (e.g., "Black", "White", "Focus")

    Returns:
        List of markdown lines for important moves table
    """
    # Confidence-based limit on displayed moves
    confidence_limit = eval_metrics.get_important_moves_limit(ctx.confidence_level)
    max_count = min(ctx.settings.max_moves, confidence_limit)
    player_moves = [mv for mv in ctx.important_moves if mv.player == player][:max_count]

    # Add "(候補)" suffix for LOW confidence
    title_suffix = " (候補)" if ctx.confidence_level == eval_metrics.ConfidenceLevel.LOW else ""
    lines = [f"## Important Moves ({label}){title_suffix} Top {len(player_moves) or max_count}"]

    if player_moves:
        # Table header
        lines.append("| # | Time | P | Coord | Loss | Best | Candidates | WR Gap | Danger | Mistake | MTag | Reason |")
        lines.append(
            "|---|------|---|-------|------|------|------------|----------|--------|---------|------|--------|"
        )

        for mv in player_moves:
            # Canonical loss (always >= 0)
            loss = get_canonical_loss_from_move(mv)
            mistake = _mistake_label_from_loss(loss, ctx.effective_thresholds)
            reason_str = ", ".join(mv.reason_tags) if mv.reason_tags else "-"

            # Meaning tag label
            meaning_tag_label = get_meaning_tag_label_safe(mv.meaning_tag_id, ctx.lang) or "-"

            # Context info (from PRE-MOVE node)
            context = get_context_info_for_move(ctx.game, mv)
            best_move_str = context["best_move"] or "-"
            candidates_str = str(context["candidates"]) if context["candidates"] is not None else "-"
            wr_gap_str = format_wr_gap(context["best_gap"])
            danger_str = context["danger"] or "-"

            # Pacing icon from time analysis
            pacing_metrics = ctx.pacing_map.get(mv.move_number) if ctx.pacing_map else None
            time_icon = get_pacing_icon(pacing_metrics)

            # Leela data gets (推定) suffix
            loss_display = format_loss_with_engine_suffix(loss, detect_engine_type(mv))

            lines.append(
                f"| {mv.move_number} | {time_icon} | {mv.player or '-'} | "
                f"{mv.gtp or '-'} | {loss_display} | {best_move_str} | "
                f"{candidates_str} | {wr_gap_str} | {danger_str} | "
                f"{mistake} | {meaning_tag_label} | {reason_str} |"
            )
    else:
        lines.append("- No important moves found.")

    return lines


def reason_tags_distribution_for(
    ctx: KarteContext,
    player: str,
    label: str,
) -> list[str]:
    """Generate reason tags distribution for a player (Phase 12).

    Args:
        ctx: Karte context
        player: "B" or "W"
        label: Display label

    Returns:
        List of markdown lines for reason tags distribution
    """
    player_moves = [mv for mv in ctx.important_moves if mv.player == player]

    # Count tags
    reason_tags_counts: dict[str, int] = {}
    for mv in player_moves:
        for tag in mv.reason_tags:
            reason_tags_counts[tag] = reason_tags_counts.get(tag, 0) + 1

    lines = [f"## Reason Tags Distribution ({label})"]
    if reason_tags_counts:
        # Sort by count descending
        sorted_tags = sorted(
            reason_tags_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        lines.append("")
        for tag, count in sorted_tags:
            label_text = eval_metrics.REASON_TAG_LABELS.get(tag, tag)
            lines.append(f"- {label_text}: {count}")
    else:
        lines.append("")
        lines.append("- No reason tags detected.")

    lines.append("")
    return lines


def critical_3_section_for(
    ctx: KarteContext,
    player: str,
    label: str,
    level: str,
) -> list[str]:
    """Generate Critical 3 section for focused review (Phase 50).

    Selects top 3 critical mistakes using weighted scoring with
    MeaningTag weights and diversity penalty.

    Args:
        ctx: Karte context
        player: "B" or "W"
        label: Display label (e.g., "Black", "White", "Focus")
        level: Important move level setting

    Returns:
        List of markdown lines for Critical 3 section (empty if no critical moves)
    """
    try:
        critical_moves = select_critical_moves(
            ctx.game,
            max_moves=3,
            lang=ctx.lang,
            level=level,
        )
    except KeyError as exc:
        # Expected: Game data structure issue
        if ctx.game.katrain:
            ctx.game.katrain.log(f"Critical 3 skipped: {exc}", OUTPUT_DEBUG)
        return []
    except Exception as exc:
        # Unexpected: Internal bug - traceback required
        import traceback

        if ctx.game.katrain:
            ctx.game.katrain.log(f"Unexpected Critical 3 error: {exc}\n{traceback.format_exc()}", OUTPUT_DEBUG)
        return []

    # Filter by player
    player_critical = [cm for cm in critical_moves if cm.player == player]
    if not player_critical:
        return []

    unit = "目" if ctx.lang == "ja" else " pts"
    intro = "最も重要なミス（重点復習用）:" if ctx.lang == "ja" else "Most impactful mistakes for focused review:"

    lines = [f"## Critical 3 ({label})", ""]
    lines.append(intro)
    lines.append("")

    # Phase 82: Create cache for stone positions (shared across Critical Moves)
    stone_cache = StoneCache(ctx.game)

    for i, cm in enumerate(player_critical, 1):
        lines.append(f"### {i}. Move #{cm.move_number} ({cm.player}) {cm.gtp_coord}")
        lines.append(f"- **Loss**: {cm.score_loss:.1f}{unit}")
        lines.append(f"- **Type**: {cm.meaning_tag_label}")

        # Phase 86: Add reason line if available
        try:
            area = get_area_from_gtp(cm.gtp_coord, ctx.game.board_size)
        except Exception:
            area = None
        reason = generate_reason_safe(
            cm.meaning_tag_id,
            phase=cm.game_phase,
            area=area,
            lang=ctx.lang,
        )
        if reason:
            lines.append(f"- **Reason**: {reason}")

        lines.append(f"- **Phase**: {cm.game_phase}")
        lines.append(f"- **Difficulty**: {cm.position_difficulty.upper()}")

        # Phase 83: Show complexity note (using ctx.lang for consistency)
        if cm.complexity_discounted:
            chaos_note = "乱戦局面（評価の変動大）" if ctx.lang == "ja" else "Complex position (high volatility)"
            lines.append(f"- **Note**: {chaos_note}")

        if cm.reason_tags:
            lines.append(f"- **Context**: {', '.join(cm.reason_tags)}")
        else:
            # Phase 82: Inject cluster classification when reason_tags is empty
            cluster_context = _get_cluster_context_for_move(ctx.game, cm.move_number, ctx.lang, stone_cache)
            if cluster_context:
                lines.append(f"- **Context**: {cluster_context}")
            else:
                lines.append("- **Context**: (none)")
        lines.append("")

    return lines
