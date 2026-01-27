"""Metadata section generators for karte report.

Contains:
- definitions_section(): Generate definitions section with thresholds
- data_quality_section(): Generate data quality section with reliability stats
- risk_management_section(): Generate risk management section
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from katrain.core import eval_metrics
from katrain.core.analysis.presentation import get_auto_confidence_label
from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.core.eval_metrics import AutoStrictnessResult
    from katrain.core.reports.karte.sections.context import KarteContext

logger = logging.getLogger(__name__)


def definitions_section(
    ctx: KarteContext,
    auto_recommendation: Optional[AutoStrictnessResult],
) -> List[str]:
    """Generate definitions section with thresholds from SKILL_PRESETS.

    Args:
        ctx: Karte context
        auto_recommendation: Auto strictness recommendation (if skill_preset == "auto")

    Returns:
        List of markdown lines for definitions section
    """
    preset = eval_metrics.SKILL_PRESETS.get(
        ctx.effective_preset,
        eval_metrics.SKILL_PRESETS[eval_metrics.DEFAULT_SKILL_PRESET],
    )
    t1, t2, t3 = preset.score_thresholds

    # Get phase thresholds for this board size
    opening_end, middle_end = eval_metrics.get_phase_thresholds(ctx.board_x)

    # Get JP labels
    preset_labels = eval_metrics.SKILL_PRESET_LABELS
    conf_labels = eval_metrics.CONFIDENCE_LABELS

    # Build strictness info line with JP labels
    if ctx.skill_preset == "auto" and auto_recommendation:
        preset_jp = preset_labels.get(
            auto_recommendation.recommended_preset,
            auto_recommendation.recommended_preset,
        )
        conf_label = get_auto_confidence_label(auto_recommendation.confidence.value)
        strictness_info = (
            f"自動 → {preset_jp} "
            f"({conf_label}, "
            f"ブランダー={auto_recommendation.blunder_count}, "
            f"重要={auto_recommendation.important_count})"
        )
    else:
        preset_jp = preset_labels.get(ctx.effective_preset, ctx.effective_preset)
        strictness_info = f"{preset_jp} (手動)"

    lines = [
        "## Definitions",
        "",
        f"- Strictness: {strictness_info}",
    ]

    # Add auto hint for manual mode
    if ctx.skill_preset != "auto":
        # Compute auto recommendation for hint
        if ctx.focus_color:
            hint_moves = [m for m in ctx.snapshot.moves if m.player == ctx.focus_color]
        else:
            hint_moves = list(ctx.snapshot.moves)
        hint_rec = eval_metrics.recommend_auto_strictness(hint_moves, game_count=1)
        hint_preset_jp = preset_labels.get(
            hint_rec.recommended_preset, hint_rec.recommended_preset
        )
        hint_conf_label = get_auto_confidence_label(hint_rec.confidence.value)
        lines.append(f"- Auto recommended: {hint_preset_jp} ({hint_conf_label})")

    # Phase 54: Localized definitions
    if ctx.lang == "ja":
        lines.extend(
            [
                "",
                "| 指標 | 定義 |",
                "|------|------|",
                "| 目数損失 | 実際の手と最善手との目数差（0以上にクランプ） |",
                "| WR Gap | 勝率変化（着手前→着手後）。大きな目数損でも勝率変化が小さい場合あり |",
                f"| Good | 損失 < {t1:.1f}目 |",
                f"| Inaccuracy | 損失 {t1:.1f} - {t2:.1f}目 |",
                f"| Mistake | 損失 {t2:.1f} - {t3:.1f}目 |",
                f"| Blunder | 損失 ≥ {t3:.1f}目 |",
                f"| Phase ({ctx.board_x}x{ctx.board_y}) | "
                f"序盤: <{opening_end}手, 中盤: {opening_end}-{middle_end-1}手, "
                f"終盤: ≥{middle_end}手 |",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "| Metric | Definition |",
                "|--------|------------|",
                "| Points Lost | Score difference between actual move and best move "
                "(clamped to ≥0) |",
                "| WR Gap | Winrate change (before → after move). Large point loss "
                "may have small WR change |",
                f"| Good | Loss < {t1:.1f} pts |",
                f"| Inaccuracy | Loss {t1:.1f} - {t2:.1f} pts |",
                f"| Mistake | Loss {t2:.1f} - {t3:.1f} pts |",
                f"| Blunder | Loss ≥ {t3:.1f} pts |",
                f"| Phase ({ctx.board_x}x{ctx.board_y}) | "
                f"Opening: <{opening_end}, Middle: {opening_end}-{middle_end-1}, "
                f"Endgame: ≥{middle_end} |",
                "",
            ]
        )
    return lines


def data_quality_section(ctx: KarteContext) -> List[str]:
    """Generate data quality section with reliability statistics.

    Args:
        ctx: Karte context

    Returns:
        List of markdown lines for data quality section
    """
    # Pass target_visits for consistent reliability threshold
    rel_stats = eval_metrics.compute_reliability_stats(
        ctx.snapshot.moves, target_visits=ctx.target_visits
    )

    # Confidence level label
    confidence_label = eval_metrics.get_confidence_label(
        ctx.confidence_level, lang=ctx.lang
    )

    lines = [
        "## Data Quality",
        "",
        f"- **{confidence_label}**",
        f"- Moves analyzed: {rel_stats.total_moves}",
        f"- Coverage: {rel_stats.moves_with_visits} / {rel_stats.total_moves} "
        f"({rel_stats.coverage_pct:.1f}%)",
        f"- Reliable (visits ≥ {rel_stats.effective_threshold}): "
        f"{rel_stats.reliable_count} ({rel_stats.reliability_pct:.1f}%)",
        f"- Low-confidence: {rel_stats.low_confidence_count} "
        f"({rel_stats.low_confidence_pct:.1f}%)",
    ]

    if rel_stats.moves_with_visits > 0:
        lines.append(f"- Avg visits: {rel_stats.avg_visits:,.0f}")
        if rel_stats.max_visits > 0:
            lines.append(f"- Max visits: {rel_stats.max_visits:,}")
    if rel_stats.zero_visits_count > 0:
        lines.append(f"- No visits data: {rel_stats.zero_visits_count}")

    # LOW confidence warning
    if ctx.confidence_level == eval_metrics.ConfidenceLevel.LOW:
        lines.append("")
        lines.append(
            "⚠️ 解析訪問数が少ないため、結果が不安定な可能性があります。再解析を推奨します。"
        )
    elif rel_stats.is_low_reliability:
        lines.append("")
        lines.append("⚠ Low analysis reliability (<20%). Results may be unstable.")

    # Note about measured vs configured values
    lines.append("")
    lines.append("*Visits are measured from KataGo analysis (root_visits).*")

    lines.append("")
    return lines


def risk_management_section(ctx: KarteContext) -> List[str]:
    """Generate risk management section (Phase 62).

    Args:
        ctx: Karte context

    Returns:
        List of markdown lines for risk management section
    """
    try:
        from katrain.core.analysis import analyze_risk
        from katrain.core.reports.sections.risk_section import (
            extract_risk_display_data,
            format_risk_stats,
            get_section_title,
        )
    except ImportError as e:
        logger.warning(f"Risk section import failed: {e}", exc_info=True)
        return []

    try:
        risk_result = analyze_risk(ctx.game)
        if not risk_result.contexts:
            return []

        lines = [f"## {get_section_title()}", ""]

        for player, label_key in [("B", "risk:black"), ("W", "risk:white")]:
            data = extract_risk_display_data(risk_result, player)
            if data.has_winning_data or data.has_losing_data:
                lines.append(f"### {i18n._(label_key)}")
                lines.extend(format_risk_stats(data, risk_result.fallback_used))
                lines.append("")

        return lines if len(lines) > 2 else []
    except Exception as e:
        logger.debug(f"Risk section generation failed: {e}", exc_info=True)
        return []
