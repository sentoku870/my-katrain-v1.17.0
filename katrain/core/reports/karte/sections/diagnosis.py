"""Diagnosis section generators for karte report.

Contains:
- weakness_hypothesis_for(): Generate weakness hypothesis section
- practice_priorities_for(): Generate practice priorities section
- mistake_streaks_for(): Detect and display mistake streaks
- urgent_miss_section_for(): Detect urgent misses
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List

from katrain.core import eval_metrics
from katrain.core.analysis.logic_loss import detect_engine_type
from katrain.core.analysis.presentation import format_loss_label
from katrain.core.eval_metrics import (
    aggregate_phase_mistake_stats,
    detect_mistake_streaks,
    get_canonical_loss_from_move,
    get_practice_priorities_from_stats,
)

if TYPE_CHECKING:
    from katrain.core.reports.karte.sections.context import KarteContext


def weakness_hypothesis_for(
    ctx: KarteContext,
    player: str,
    label: str,
) -> List[str]:
    """Generate weakness hypothesis section for a player (skill_preset thresholds).

    Args:
        ctx: Karte context
        player: "B" or "W"
        label: Display label

    Returns:
        List of markdown lines for weakness hypothesis section
    """
    player_moves = [mv for mv in ctx.snapshot.moves if mv.player == player]
    if not player_moves:
        return [f"## Weakness Hypothesis ({label})", "- No data available.", ""]

    # Get board size
    board_x = ctx.board_x

    # Get thresholds from skill_preset
    preset = eval_metrics.get_skill_preset(ctx.skill_preset)
    score_thresholds = preset.score_thresholds

    # Aggregate Phase × Mistake stats using shared aggregator
    stats = aggregate_phase_mistake_stats(
        player_moves,
        score_thresholds=score_thresholds,
        board_size=board_x,
    )

    # Sort by loss descending (exclude GOOD)
    sorted_combos = sorted(
        [(k, v) for k, v in stats.phase_mistake_loss.items() if k[1] != "GOOD" and v > 0],
        key=lambda x: x[1],
        reverse=True,
    )

    phase_names = {"opening": "Opening", "middle": "Middle game", "yose": "Endgame"}
    cat_names_ja = {
        "BLUNDER": "大悪手",
        "MISTAKE": "悪手",
        "INACCURACY": "軽微なミス",
    }

    # Confidence-based wording
    is_low_conf = ctx.confidence_level == eval_metrics.ConfidenceLevel.LOW
    is_medium_conf = ctx.confidence_level == eval_metrics.ConfidenceLevel.MEDIUM

    # Add "(※参考情報)" suffix for LOW confidence
    header_suffix = " (※参考情報)" if is_low_conf else ""
    lines = [f"## Weakness Hypothesis ({label}){header_suffix}", ""]

    # Get evidence count based on confidence level
    evidence_count = eval_metrics.get_evidence_count(ctx.confidence_level)

    if sorted_combos:
        # Top 2 weaknesses
        for i, (key, loss) in enumerate(sorted_combos[:2]):
            phase, category = key
            count = stats.phase_mistake_counts.get(key, 0)

            # Select representative moves for this phase/category
            def phase_cat_filter(mv: Any) -> bool:
                mv_phase = mv.tag or "unknown"
                mv_cat = mv.mistake_category.name if mv.mistake_category else "GOOD"
                return mv_phase == phase and mv_cat == category

            evidence_moves = eval_metrics.select_representative_moves(
                player_moves,
                max_count=evidence_count,
                category_filter=phase_cat_filter,
            )
            evidence_str = eval_metrics.format_evidence_examples(evidence_moves, lang=ctx.lang)

            # Confidence-based wording
            if is_low_conf:
                # LOW: "～の傾向が見られる"
                lines.append(
                    f"{i+1}. {phase_names.get(phase, phase)}の"
                    f"{cat_names_ja.get(category, category)}の傾向が見られる "
                    f"({count}回、損失{loss:.1f}目)"
                )
            elif is_medium_conf:
                # MEDIUM: "～の傾向あり"
                lines.append(
                    f"{i+1}. **{phase_names.get(phase, phase)}の"
                    f"{cat_names_ja.get(category, category)}** 傾向あり "
                    f"({count}回、損失{loss:.1f}目)"
                )
            else:
                # HIGH: Assertive wording
                lines.append(
                    f"{i+1}. **{phase_names.get(phase, phase)}の"
                    f"{cat_names_ja.get(category, category)}** "
                    f"({count}回、損失{loss:.1f}目)"
                )

            # Add evidence examples on next line (indented)
            if evidence_str:
                lines.append(f"   {evidence_str}")
    else:
        lines.append("- 明確な弱点パターンは検出されませんでした。")

    # Add re-analysis recommendation for LOW confidence
    if is_low_conf:
        lines.append("")
        lines.append("⚠️ 解析訪問数が少ないため、visits増で再解析を推奨します。")

    lines.append("")
    return lines


def practice_priorities_for(
    ctx: KarteContext,
    player: str,
    label: str,
) -> List[str]:
    """Generate practice priorities section for a player.

    Args:
        ctx: Karte context
        player: "B" or "W"
        label: Display label

    Returns:
        List of markdown lines for practice priorities section
    """
    # LOW confidence → placeholder only
    if ctx.confidence_level == eval_metrics.ConfidenceLevel.LOW:
        return [
            f"## 練習の優先順位 ({label})",
            "",
            "- ※ データ不足のため練習優先度は保留。visits増で再解析を推奨します。",
            "",
        ]

    player_moves = [mv for mv in ctx.snapshot.moves if mv.player == player]
    if not player_moves:
        return [f"## 練習の優先順位 ({label})", "- No data available.", ""]

    # Get board size
    board_x = ctx.board_x

    # Get thresholds from skill_preset (matching Weakness Hypothesis)
    preset = eval_metrics.get_skill_preset(ctx.skill_preset)
    score_thresholds = preset.score_thresholds

    # Aggregate Phase × Mistake stats
    stats = aggregate_phase_mistake_stats(
        player_moves,
        score_thresholds=score_thresholds,
        board_size=board_x,
    )

    # Get priorities
    # MEDIUM confidence → shortened version (max 1)
    max_priorities = (
        1 if ctx.confidence_level == eval_metrics.ConfidenceLevel.MEDIUM else 2
    )
    priorities = get_practice_priorities_from_stats(stats, max_priorities=max_priorities)

    lines = [f"## 練習の優先順位 ({label})", ""]
    lines.append("Based on the data above, consider focusing on:")
    lines.append("")
    if priorities:
        for i, priority in enumerate(priorities, 1):
            lines.append(f"- {i}. {priority}")

            # Try to find anchor move for this priority
            anchor_move = None
            for phase_key, phase_name in [
                ("opening", "Opening"),
                ("middle", "Middle"),
                ("yose", "Endgame"),
            ]:
                if (
                    phase_name.lower() in priority.lower()
                    or phase_key in priority.lower()
                ):
                    # Find worst move in this phase
                    phase_moves = [
                        mv
                        for mv in player_moves
                        if (mv.tag or "unknown") == phase_key
                        and mv.score_loss is not None
                    ]
                    if phase_moves:
                        anchor_move = max(
                            phase_moves,
                            key=lambda m: (m.score_loss or 0, -m.move_number),
                        )
                    break

            if anchor_move:
                loss = get_canonical_loss_from_move(anchor_move)
                if loss > 0.0:
                    engine_type = detect_engine_type(anchor_move)
                    loss_label = format_loss_label(loss, engine_type, lang=ctx.lang)
                    lines.append(
                        f"   (#{anchor_move.move_number} {anchor_move.gtp or '-'} で "
                        f"{loss_label}の損失)"
                    )
    else:
        lines.append("- No specific priorities identified. Keep up the good work!")
    lines.append("")
    return lines


def mistake_streaks_for(
    ctx: KarteContext,
    player: str,
    label: str,
) -> List[str]:
    """Detect and display consecutive mistakes by the same player.

    Args:
        ctx: Karte context
        player: "B" or "W"
        label: Display label

    Returns:
        List of markdown lines for mistake streaks section
    """
    player_moves = [mv for mv in ctx.snapshot.moves if mv.player == player]
    if not player_moves:
        return []

    # Get thresholds from URGENT_MISS_CONFIGS
    urgent_config = eval_metrics.get_urgent_miss_config(ctx.skill_preset)

    # Detect consecutive mistakes
    streaks = detect_mistake_streaks(
        player_moves,
        loss_threshold=urgent_config.threshold_loss,
        min_consecutive=urgent_config.min_consecutive,
    )

    if not streaks:
        return []

    lines = [f"## Mistake Streaks ({label})", ""]
    lines.append("Consecutive mistakes by the same player:")
    lines.append("")
    for i, s in enumerate(streaks, 1):
        lines.append(
            f"- **Streak {i}**: moves {s.start_move}-{s.end_move} "
            f"({s.move_count} mistakes, {s.total_loss:.1f} pts lost, "
            f"avg {s.avg_loss:.1f} pts)"
        )
    lines.append("")
    return lines


def urgent_miss_section_for(
    ctx: KarteContext,
    player: str,
    label: str,
) -> List[str]:
    """Detect urgent misses (consecutive mistakes indicating missed urgency).

    Args:
        ctx: Karte context
        player: "B" or "W"
        label: Display label

    Returns:
        List of markdown lines for urgent miss section
    """
    player_moves = [mv for mv in ctx.snapshot.moves if mv.player == player]
    if not player_moves:
        return []

    # Get thresholds from skill_preset
    urgent_config = eval_metrics.get_urgent_miss_config(ctx.skill_preset)

    # Detect consecutive mistakes
    streaks = detect_mistake_streaks(
        player_moves,
        loss_threshold=urgent_config.threshold_loss,
        min_consecutive=urgent_config.min_consecutive,
    )

    if not streaks:
        return []

    # Add "※要再解析" annotation for LOW confidence
    is_low_conf = ctx.confidence_level == eval_metrics.ConfidenceLevel.LOW
    header_suffix = " (※要再解析)" if is_low_conf else ""
    lines = [f"## Urgent Miss Detection ({label}){header_suffix}", ""]
    lines.append("**Warning**: 以下の連続手は急場見逃しの可能性があります:")
    lines.append("")
    # Table with Coords column for coordinate sequence
    lines.append("| Move Range | Consecutive | Total Loss | Avg Loss | Coords |")
    lines.append("|------------|-------------|------------|----------|--------|")
    for s in streaks:
        # Build coordinate sequence from streak moves
        coords = "→".join(mv.gtp or "-" for mv in s.moves) if s.moves else "-"
        lines.append(
            f"| #{s.start_move}-{s.end_move} | {s.move_count} moves | "
            f"{s.total_loss:.1f} pts | {s.avg_loss:.1f} pts | {coords} |"
        )
    lines.append("")
    return lines
