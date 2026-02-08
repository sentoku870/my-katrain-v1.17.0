"""Diagnosis section generators for karte report.

Contains:
- weakness_hypothesis_for(): Generate weakness hypothesis section
- practice_priorities_for(): Generate practice priorities section
- mistake_streaks_for(): Detect and display mistake streaks
- urgent_miss_section_for(): Detect urgent misses
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core import eval_metrics
from katrain.core.analysis.logic_loss import detect_engine_type
from katrain.core.analysis.presentation import format_loss_label
from katrain.core.eval_metrics import (
    aggregate_phase_mistake_stats,
    detect_mistake_streaks,
    get_canonical_loss_from_move,
    get_practice_priorities_from_stats,
)
from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.core.reports.karte.sections.context import KarteContext


def weakness_hypothesis_for(
    ctx: KarteContext,
    player: str,
    label: str,
) -> list[str]:
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
        return [f"## {i18n._('summary:weakness')} ({label})", f"- {i18n._('summary:no_data')}", ""]

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

    phase_names = {
        "opening": i18n._("phase:opening"),
        "middle": i18n._("phase:middle"),
        "yose": i18n._("phase:yose"),
    }
    cat_names = {
        "BLUNDER": i18n._("mistake:blunder"),
        "MISTAKE": i18n._("mistake:mistake"),
        "INACCURACY": i18n._("mistake:inaccuracy"),
    }

    # Confidence-based wording
    is_low_conf = ctx.confidence_level == eval_metrics.ConfidenceLevel.LOW
    is_medium_conf = ctx.confidence_level == eval_metrics.ConfidenceLevel.MEDIUM

    # Add "(※参考情報)" suffix for LOW confidence
    header_suffix = f" ({i18n._('summary:suffix:ref')})" if is_low_conf else ""
    lines = [f"## {i18n._('summary:weakness')} ({label}){header_suffix}", ""]

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

            phase_label = phase_names.get(phase, phase)
            cat_label = cat_names.get(category, category)

            # Confidence-based wording
            if is_low_conf:
                # LOW: "～の傾向が見られる"
                lines.append(
                    f"{i + 1}. {i18n._('diagnosis:weakness:trend_ref').format(phase=phase_label, category=cat_label)} "
                    f"({count}{i18n._('summary:unit:times')}, {i18n._('summary:loss')}{loss:.1f}{i18n._('summary:unit:points')})"
                )
            elif is_medium_conf:
                # MEDIUM: "～の傾向あり"
                lines.append(
                    f"{i + 1}. **{i18n._('diagnosis:weakness:trend').format(phase=phase_label, category=cat_label)}** "
                    f"({count}{i18n._('summary:unit:times')}, {i18n._('summary:loss')}{loss:.1f}{i18n._('summary:unit:points')})"
                )
            else:
                # HIGH: Assertive wording
                msg = i18n._("diagnosis:weakness:assertive").format(phase=phase_label, category=cat_label)
                # Fallback if key missing or same as trend
                if msg == "diagnosis:weakness:assertive":
                    msg = f"{phase_label} の {cat_label}"
                
                lines.append(
                    f"{i + 1}. **{msg}** "
                    f"({count}{i18n._('summary:unit:times')}, {i18n._('summary:loss')}{loss:.1f}{i18n._('summary:unit:points')})"
                )

            # Add evidence examples on next line (indented)
            if evidence_str:
                lines.append(f"   {evidence_str}")
    else:
        lines.append(f"- {i18n._('summary:weakness:none')}")

    # Add re-analysis recommendation for LOW confidence
    if is_low_conf:
        lines.append("")
        lines.append(f"⚠️ {i18n._('summary:warning:low_visits')}")

    lines.append("")
    return lines


def practice_priorities_for(
    ctx: KarteContext,
    player: str,
    label: str,
) -> list[str]:
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
            f"## {i18n._('summary:practice')} ({label})",
            "",
            f"- {i18n._('summary:practice:low_data_msg')}",
            "",
        ]

    player_moves = [mv for mv in ctx.snapshot.moves if mv.player == player]
    if not player_moves:
        return [f"## {i18n._('summary:practice')} ({label})", f"- {i18n._('summary:no_data')}", ""]

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
    max_priorities = 1 if ctx.confidence_level == eval_metrics.ConfidenceLevel.MEDIUM else 2
    priorities = get_practice_priorities_from_stats(stats, max_priorities=max_priorities)

    lines = [f"## {i18n._('summary:practice')} ({label})", ""]
    lines.append(i18n._('summary:practice:intro'))
    lines.append("")
    if priorities:
        for i, priority in enumerate(priorities, 1):
            lines.append(f"- {i}. {priority}")

            # Try to find anchor move for this priority
            anchor_move = None
            for phase_key, phase_name in [
                ("opening", i18n._("phase:opening")),
                ("middle", i18n._("phase:middle")),
                ("yose", i18n._("phase:yose")),
            ]:
                if phase_name.lower() in priority.lower() or phase_key in priority.lower():
                    # Find worst move in this phase
                    phase_moves = [
                        mv for mv in player_moves if (mv.tag or "unknown") == phase_key and mv.score_loss is not None
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
                    lines.append(f"   (#{anchor_move.move_number} {anchor_move.gtp or '-'} : {loss_label})")
    else:
        lines.append(f"- {i18n._('summary:practice:none')}")
    lines.append("")
    return lines


def mistake_streaks_for(
    ctx: KarteContext,
    player: str,
    label: str,
) -> list[str]:
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

    lines = [f"## {i18n._('diagnosis:streaks')} ({label})", ""]
    lines.append(i18n._('diagnosis:streaks:intro'))
    lines.append("")
    for i, s in enumerate(streaks, 1):
        lines.append(
            f"- **Streak {i}**: {i18n._('diagnosis:streak_desc').format(start=s.start_move, end=s.end_move, count=s.move_count, loss=s.total_loss, avg=s.avg_loss)}"
        )
    lines.append("")
    return lines


def urgent_miss_section_for(
    ctx: KarteContext,
    player: str,
    label: str,
) -> list[str]:
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
    header_suffix = f" ({i18n._('summary:suffix:reanalyze')})" if is_low_conf else ""
    lines = [f"## {i18n._('diagnosis:urgent_miss')} ({label}){header_suffix}", ""]
    lines.append(f"**{i18n._('summary:warning')}**: {i18n._('diagnosis:urgent_miss:intro')}")
    lines.append("")
    # Table with Coords column for coordinate sequence
    lines.append(f"| {i18n._('summary:table:range')} | {i18n._('summary:table:consecutive')} | {i18n._('summary:table:total_loss')} | {i18n._('summary:table:avg_loss')} | {i18n._('summary:table:coord')} |")
    lines.append("|------------|-------------|------------|----------|--------|")
    for s in streaks:
        # Build coordinate sequence from streak moves
        coords = "→".join(mv.gtp or "-" for mv in s.moves) if s.moves else "-"
        lines.append(
            f"| #{s.start_move}-{s.end_move} | {s.move_count} {i18n._('summary:unit:moves')} | "
            f"{s.total_loss:.1f} {i18n._('summary:unit:points')} | {s.avg_loss:.1f} {i18n._('summary:unit:points')} | {coords} |"
        )
    lines.append("")
    return lines
