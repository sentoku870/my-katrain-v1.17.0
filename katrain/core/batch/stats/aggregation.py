"""Aggregation functions for batch statistics.

Phase 149 C-4: Dead-code removal. Removed:
- _select_evidence_moves / _format_evidence_with_links (Phase 66, unused)
- build_tag_based_hints / detect_color_bias / get_dominant_tags
- All localized helper getters (get_phase_priority_text etc.)
- Associated i18n constants in models.py

Survivors:
- build_batch_summary: Main entry, with lang parameter (Phase 149 B-2)
- Localized PHASE labels: handled directly via lang switch (not via getters)

This module is now purely about producing the batch summary markdown.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from katrain.core.batch.helpers import (
    escape_markdown_table_cell,
    truncate_game_name,
)
from katrain.core.eval_metrics import MistakeCategory

_logger = logging.getLogger("katrain.core.batch.stats")

if TYPE_CHECKING:
    pass


# =============================================================================
# Batch Summary
# =============================================================================


def build_batch_summary(
    game_stats_list: list[dict[str, Any]],
    focus_player: str | None = None,
    lang: str = "jp",
) -> str:
    """Build a multi-game summary markdown from collected stats.

    Args:
        game_stats_list: List of game stats dictionaries
        focus_player: Optional player name to focus on
        lang: Language code ("jp"/"ja" for Japanese, "en" for English).
            Affects markdown headers and labels only. JSON block is
            language-agnostic.

    Returns:
        Markdown string with the summary
    """
    from katrain.common.locale_utils import normalize_lang_code

    normalized_lang = normalize_lang_code(lang)

    if not game_stats_list:
        if normalized_lang == "jp":
            return "# 複数局サマリー\n\n処理対象の対局がありません。"
        return "# Multi-Game Summary\n\nNo games processed."

    if normalized_lang == "jp":
        title = "# 複数局サマリー"
        label_games = "**対象局数**: "
        label_generated = "**生成日時**: "
        section_overview = "## 概要"
        label_total_moves = "- 総手数: "
        label_total_loss = "- 総損失目数: "
        label_avg_loss = "- 1手あたり平均損失: "
        section_phase = "## フェーズ×ミス 内訳"
        section_worst = "## 全対局ワースト10手"
        header_phase = "| フェーズ | ミス | 回数 | 総損失 |"
        header_worst = "| 対局 | 手数 | プレイヤー | 位置 | 損失 | 分類 |"
    else:
        title = "# Multi-Game Summary"
        label_games = "**Games analyzed**: "
        label_generated = "**Generated**: "
        section_overview = "## Overview"
        label_total_moves = "- Total moves: "
        label_total_loss = "- Total points lost: "
        label_avg_loss = "- Average loss per move: "
        section_phase = "## Phase x Mistake Breakdown"
        section_worst = "## Top 10 Worst Moves (All Games)"
        header_phase = "| Phase | Mistake | Count | Total Loss |"
        header_worst = "| Game | Move | Player | Position | Loss | Category |"

    lines = [f"{title}\n"]
    lines.append(f"{label_games}{len(game_stats_list)}\n")
    lines.append(f"{label_generated}{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # Aggregate stats
    total_moves = sum(s["total_moves"] for s in game_stats_list)
    total_loss = sum(s["total_points_lost"] for s in game_stats_list)

    lines.append(f"\n{section_overview}\n")
    lines.append(f"{label_total_moves}{total_moves}")
    lines.append(f"{label_total_loss}{total_loss:.1f}")
    if total_moves > 0:
        lines.append(f"{label_avg_loss}{total_loss / total_moves:.2f}")

    # Phase x Mistake breakdown
    lines.append(f"\n{section_phase}\n")

    phase_mistake_counts: dict[tuple[str, str], int] = {}
    phase_mistake_loss: dict[tuple[str, str], float] = {}
    for stats in game_stats_list:
        for key, count in stats.get("phase_mistake_counts", {}).items():
            phase_mistake_counts[key] = phase_mistake_counts.get(key, 0) + count
        for key, loss in stats.get("phase_mistake_loss", {}).items():
            phase_mistake_loss[key] = phase_mistake_loss.get(key, 0.0) + loss

    if phase_mistake_counts:
        lines.append(header_phase)
        if normalized_lang == "jp":
            lines.append("|---|---|---:|---:|")
        else:
            lines.append("|-------|---------|------:|----------:|")
        for key in sorted(phase_mistake_counts.keys(), key=lambda x: phase_mistake_loss.get(x, 0), reverse=True):
            phase, category = key
            count = phase_mistake_counts[key]
            loss = phase_mistake_loss.get(key, 0.0)
            lines.append(f"| {phase} | {category} | {count} | {loss:.1f} |")

    # Worst moves across all games
    lines.append(f"\n{section_worst}\n")
    all_worst: list[tuple[str, int, str, str, float, MistakeCategory | None]] = []
    for stats in game_stats_list:
        game_name = stats["game_name"]
        for move_num, player, gtp, loss, cat in stats.get("worst_moves", []):
            all_worst.append((game_name, move_num, player, gtp, loss, cat))

    all_worst.sort(key=lambda x: x[4], reverse=True)
    all_worst = all_worst[:10]

    if all_worst:
        lines.append(header_worst)
        if normalized_lang == "jp":
            lines.append("|---|---:|:---:|---|---:|---|")
        else:
            lines.append("|------|-----:|:------:|----------|-----:|----------|")
        for game_name, move_num, player, gtp, loss, cat in all_worst:
            cat_name = cat.name if cat else "—"
            display_name = escape_markdown_table_cell(truncate_game_name(game_name))
            lines.append(f"| {display_name} | {move_num} | {player} | {gtp} | {loss:.1f} | {cat_name} |")

    # Phase 55: Add JSON block for AI readability using the unified SummaryAnalyzer
    from katrain.core.analysis.models import GameSummaryData
    from katrain.core.reports.summary_report import build_summary_report

    # Extract GameSummaryData from the stats list
    game_data_list = []
    for stats in game_stats_list:
        if "summary_data" in stats:
            game_data_list.append(stats["summary_data"])
        elif "snapshot" in stats: # Fallback if only snapshot is present
            game_data_list.append(GameSummaryData(
                game_name=stats.get("game_name", "unknown"),
                player_black=stats.get("player_black", "Black"),
                player_white=stats.get("player_white", "White"),
                snapshot=stats["snapshot"],
                board_size=stats.get("board_size", (19, 19)),
                date=stats.get("date"),
                # Phase 155-C: surface SGF rank tags from the stats dict.
                rank_black=stats.get("rank_black"),
                rank_white=stats.get("rank_white"),
            ))

    # Get the JSON-wrapped report (focus_player=None for entire batch)
    json_report = build_summary_report(game_data_list, focus_player=None)

    # Append the JSON report to the markdown lines
    lines.append("\n" + json_report)

    return "\n".join(lines)

