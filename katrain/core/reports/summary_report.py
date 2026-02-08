"""Summary report generation for multiple game analysis.

PR #116: Phase B2 - summary_report.py extraction from game.py
Refactored (Phase 128): Logic separated into summary_logic.py, constants moved to constants.py.

All functions in this module:
- Are static (no self parameter)
- Do not modify any state
- Do not import from katrain.gui (core layer only)
"""

from datetime import datetime
from typing import Any, Optional

from katrain.core import eval_metrics
from katrain.core.batch.helpers import format_game_display_label, truncate_game_name
from katrain.core.eval_metrics import (
    GameSummaryData,
    MistakeCategory,
    PositionDifficulty,
    SummaryStats,
)
from katrain.core.game_node import Move
from katrain.core.lang import i18n
from katrain.core.reports.constants import (
    BAD_MOVE_LOSS_THRESHOLD,
    SUMMARY_DEFAULT_MAX_WORST_MOVES,
    URGENT_MISS_MIN_CONSECUTIVE,
    URGENT_MISS_THRESHOLD_LOSS,
)
from katrain.core.reports.summary_logic import SummaryAnalyzer


def build_summary_report(
    game_data_list: list["GameSummaryData"], focus_player: str | None = None
) -> str:
    """
    複数局から統計まとめを生成（Phase 6）

    Args:
        game_data_list: 各対局のデータリスト
        focus_player: 集計対象プレイヤー名（Noneなら全プレイヤー）

    Returns:
        Markdown形式のまとめレポート
    """
    if not game_data_list:
        # Return empty JSON-like structure or specific message
        return f"```json\n{{\n  \"meta\": {{\n    \"games_analyzed\": 0\n  }}\n}}\n```"

    from katrain.core.reports.summary_json_export import build_summary_json
    import json
    
    json_data = build_summary_json(game_data_list, focus_player)
    
    # Phase v6 Stage 1: Return raw JSON string (no Markdown wrapping)
    json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
    return json_str


def _format_meta_section(
    game_data_list: list["GameSummaryData"], focus_player: str | None
) -> str:
    """メタ情報セクションを生成"""
    lines = [f"## {i18n._('summary:meta')}"]
    lines.append(f"- {i18n._('summary:meta:games_analyzed')}: {len(game_data_list)}")

    # プレイヤー情報
    all_players = set()
    for gd in game_data_list:
        all_players.add(gd.player_black)
        all_players.add(gd.player_white)

    if focus_player:
        lines.append(f"- {i18n._('summary:meta:focus_player')}: {focus_player}")
    else:
        lines.append(
            f"- {i18n._('summary:meta:players')}: {', '.join(sorted(all_players))}"
        )

    # 日付範囲
    dates = [gd.date for gd in game_data_list if gd.date]
    if dates:
        lines.append(
            f"- {i18n._('summary:meta:date_range')}: {min(dates)} to {max(dates)}"
        )

    # 生成日時
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"- {i18n._('summary:meta:generated')}: {now}")

    return "\n".join(lines)


def _format_overall_stats(
    player_name: str,
    stats: SummaryStats,
    confidence_level: Optional["eval_metrics.ConfidenceLevel"] = None,
) -> str:
    """総合統計セクションを生成"""
    # PR#1: Import ConfidenceLevel for default handling
    if confidence_level is None:
        confidence_level = eval_metrics.ConfidenceLevel.HIGH

    # PR#1: Show confidence level prominently
    # Note: get_confidence_label likely handles i18n internally or returns a key?
    # Checking usage, it seems to expect lang arg, but here using global i18n
    # Let's assume we pass lang explicitly if needed, or use a method that uses i18n
    confidence_label = eval_metrics.get_confidence_label(
        confidence_level, lang=i18n.lang or "en"
    )

    lines = [f"## {i18n._('summary:overall')} ({player_name})"]
    lines.append(f"- **{confidence_label}**")  # PR#1: Confidence level
    lines.append(f"- {i18n._('summary:overall:total_games')}: {stats.total_games}")
    lines.append(
        f"- {i18n._('summary:overall:total_moves')}: {stats.total_moves}"
    )
    lines.append(
        f"- {i18n._('summary:overall:total_loss')}: {stats.total_points_lost:.1f}"
    )
    lines.append(
        f"- {i18n._('summary:overall:avg_loss')}: {stats.avg_points_lost_per_move:.2f}"
    )

    if stats.worst_moves:
        worst_game, worst_move = stats.worst_moves[0]
        loss = (
            worst_move.points_lost if worst_move.points_lost else worst_move.score_loss
        )
        lines.append(
            f"- {i18n._('summary:overall:worst_move')}: {worst_game} #{worst_move.move_number} {worst_move.gtp or '-'} ({loss:.1f} {i18n._('summary:points')})"
        )

    # PR#1: Add LOW confidence warning
    if confidence_level == eval_metrics.ConfidenceLevel.LOW:
        lines.append("")
        lines.append(f"⚠️ {i18n._('summary:warning:low_confidence')}")

    return "\n".join(lines)


def _format_mistake_distribution(player_name: str, stats: SummaryStats) -> str:
    """ミス分類分布セクションを生成"""
    lines = [f"## {i18n._('summary:mistake_dist')} ({player_name})"]
    lines.append(
        f"| {i18n._('summary:table:category')} | {i18n._('summary:table:count')} | {i18n._('summary:table:percentage')} | {i18n._('summary:table:avg_loss')} |"
    )
    lines.append("|----------|-------|------------|----------|")

    category_labels = {
        MistakeCategory.GOOD: i18n._("mistake:good"),
        MistakeCategory.INACCURACY: i18n._("mistake:inaccuracy"),
        MistakeCategory.MISTAKE: i18n._("mistake:mistake"),
        MistakeCategory.BLUNDER: i18n._("mistake:blunder"),
    }

    for cat in [
        MistakeCategory.GOOD,
        MistakeCategory.INACCURACY,
        MistakeCategory.MISTAKE,
        MistakeCategory.BLUNDER,
    ]:
        count = stats.mistake_counts.get(cat, 0)
        pct = stats.get_mistake_percentage(cat)
        avg_loss = stats.get_mistake_avg_loss(cat)
        lines.append(
            f"| {category_labels[cat]} | {count} | {pct:.1f}% | {avg_loss:.2f} |"
        )

    return "\n".join(lines)


def _format_freedom_distribution(player_name: str, stats: SummaryStats) -> str:
    """Freedom（手の自由度）分布セクションを生成"""
    lines = [f"## {i18n._('summary:freedom_dist')} ({player_name})"]
    lines.append(
        f"| {i18n._('summary:table:difficulty')} | {i18n._('summary:table:count')} | {i18n._('summary:table:percentage')} |"
    )
    lines.append("|------------|-------|------------|")

    difficulty_labels = {
        PositionDifficulty.EASY: i18n._("freedom:easy"),
        PositionDifficulty.NORMAL: i18n._("freedom:normal"),
        PositionDifficulty.HARD: i18n._("freedom:hard"),
        PositionDifficulty.ONLY_MOVE: i18n._("freedom:only_move"),
    }

    for diff in [
        PositionDifficulty.EASY,
        PositionDifficulty.NORMAL,
        PositionDifficulty.HARD,
        PositionDifficulty.ONLY_MOVE,
    ]:
        count = stats.freedom_counts.get(diff, 0)
        pct = stats.get_freedom_percentage(diff)
        lines.append(f"| {difficulty_labels[diff]} | {count} | {pct:.1f}% |")

    return "\n".join(lines)


def _format_phase_breakdown(player_name: str, stats: SummaryStats) -> str:
    """局面タイプ別内訳セクションを生成"""
    lines = [f"## {i18n._('summary:phase_breakdown')} ({player_name})"]
    lines.append(
        f"| {i18n._('summary:table:phase')} | {i18n._('summary:table:moves')} | {i18n._('summary:table:points_lost')} | {i18n._('summary:table:avg_loss')} |"
    )
    lines.append("|-------|-------|-------------|----------|")

    phase_labels = {
        "opening": i18n._("phase:opening"),
        "middle": i18n._("phase:middle"),
        "yose": i18n._("phase:yose"),
        "unknown": i18n._("phase:unknown"),
    }

    for phase in ["opening", "middle", "yose", "unknown"]:
        count = stats.phase_moves.get(phase, 0)
        loss = stats.phase_loss.get(phase, 0.0)
        avg_loss = stats.get_phase_avg_loss(phase)
        lines.append(
            f"| {phase_labels.get(phase, phase)} | {count} | {loss:.1f} | {avg_loss:.2f} |"
        )

    return "\n".join(lines)


def _format_phase_mistake_breakdown(player_name: str, stats: SummaryStats) -> str:
    """Phase × Mistake クロス集計セクションを生成"""
    lines = [f"## {i18n._('summary:phase_mistake_breakdown')} ({player_name})"]
    lines.append(
        f"| {i18n._('summary:table:phase')} | {i18n._('mistake:good')} | {i18n._('mistake:inaccuracy')} | {i18n._('mistake:mistake')} | {i18n._('mistake:blunder')} | {i18n._('summary:table:total_loss')} |"
    )
    lines.append("|-------|------|------------|---------|---------|------------|")

    phase_labels = {
        "opening": i18n._("phase:opening"),
        "middle": i18n._("phase:middle"),
        "yose": i18n._("phase:yose"),
        "unknown": i18n._("phase:unknown"),
    }

    for phase in ["opening", "middle", "yose"]:
        cells = [phase_labels.get(phase, phase)]

        for cat in [
            MistakeCategory.GOOD,
            MistakeCategory.INACCURACY,
            MistakeCategory.MISTAKE,
            MistakeCategory.BLUNDER,
        ]:
            count = stats.phase_mistake_counts.get((phase, cat), 0)
            loss = stats.phase_mistake_loss.get((phase, cat), 0.0)

            if count > 0 and cat != MistakeCategory.GOOD:
                cells.append(f"{count} ({loss:.1f})")
            else:
                cells.append(str(count))

        # Total loss for this phase
        phase_total_loss = stats.phase_loss.get(phase, 0.0)
        cells.append(f"{phase_total_loss:.1f}")

        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def _convert_sgf_to_gtp_coord(sgf_coord: str, board_size: int = 19) -> str:
    """
    SGF座標（例: 'll', 'rf'）を人間用座標（例: 'L12', 'R6'）に変換

    Args:
        sgf_coord: SGF形式の座標（2文字のアルファベット）
        board_size: 盤面サイズ（デフォルト19路）

    Returns:
        GTP形式の座標（例: 'R6'）、変換失敗時は元の文字列
    """
    if not sgf_coord or len(sgf_coord) != 2:
        return sgf_coord

    try:
        # Move.SGF_COORD を使って変換
        x = Move.SGF_COORD.index(sgf_coord[0])
        y = board_size - Move.SGF_COORD.index(sgf_coord[1]) - 1
        return f"{Move.GTP_COORD[x]}{y + 1}"
    except (ValueError, IndexError):
        return sgf_coord


def _format_top_worst_moves(
    player_name: str,
    stats: SummaryStats,
    analyzer: SummaryAnalyzer,
    confidence_level: Optional["eval_metrics.ConfidenceLevel"] = None,
) -> str:
    """最悪手Top 10セクションを生成（急場見逃しパターンを分離）"""
    # PR#1: Default to HIGH if not provided
    if confidence_level is None:
        confidence_level = eval_metrics.ConfidenceLevel.HIGH

    # PR#1: Limit worst moves count based on confidence
    max_count = eval_metrics.get_important_moves_limit(confidence_level)
    title_suffix = (
        f" ({i18n._('summary:suffix:candidate')})"
        if confidence_level == eval_metrics.ConfidenceLevel.LOW
        else ""
    )
    lines = [f"## {i18n._('summary:top_worst')} ({player_name}){title_suffix}"]

    if not stats.worst_moves:
        lines.append(f"- {i18n._('summary:no_mistakes')}")
        return "\n".join(lines)

    # 急場見逃しパターンを検出 (using Logic class)
    # Using hardcoded values in logic class impl, so no args needed if using default
    # But SummaryAnalyzer._detect_urgent_miss_sequences_impl takes args.
    # The public method wrapper uses defaults.
    sequences, filtered_moves = analyzer.detect_urgent_miss_sequences(player_name)

    # 急場見逃しパターンがあれば表示
    if sequences:
        lines.append("")
        lines.append(f"**{i18n._('summary:warning')}**: {i18n._('summary:urgent_miss_warning').format(loss=URGENT_MISS_THRESHOLD_LOSS, count=URGENT_MISS_MIN_CONSECUTIVE)}")
        lines.append(
            f"| {i18n._('summary:table:game')} | {i18n._('summary:table:range')} | {i18n._('summary:table:consecutive')} | {i18n._('summary:table:total_loss')} | {i18n._('summary:table:avg_loss')} |"
        )
        lines.append("|------|---------|------|--------|------------|")

        for seq in sequences:
            # Use full game name (Phase V4)
            game_full_id = seq["game"]
            avg_loss = seq["total_loss"] / seq["count"]
            lines.append(
                f"| {game_full_id} | #{seq['start']}-{seq['end']} | "
                f"{seq['count']}{i18n._('summary:unit:moves')} | {seq['total_loss']:.1f}{i18n._('summary:unit:points')} | {avg_loss:.1f}{i18n._('summary:unit:points')} |"
            )
        lines.append("")

    # 通常のワースト手を表示
    if filtered_moves:
        # 損失でソートして confidence level に応じた件数を取得
        filtered_moves.sort(
            key=lambda x: x[1].points_lost or x[1].score_loss or 0, reverse=True
        )
        # PR#1: Use max_count from confidence level (default was 10)
        display_limit = min(SUMMARY_DEFAULT_MAX_WORST_MOVES, max_count)
        display_moves = filtered_moves[:display_limit]

        if sequences:
            lines.append(f"{i18n._('summary:normal_worst')} ({i18n._('summary:less_than').format(val=URGENT_MISS_THRESHOLD_LOSS)}):")
        lines.append(
            f"| {i18n._('summary:table:game')} | # | P | {i18n._('summary:table:coord')} | {i18n._('summary:table:loss')} | {i18n._('summary:table:importance')} | {i18n._('summary:table:category')} |"
        )
        lines.append("|------|---|---|-------|------|------------|----------|")

        mistake_labels = {
            MistakeCategory.GOOD: "GOOD",
            MistakeCategory.INACCURACY: "INACCURACY",
            MistakeCategory.MISTAKE: "MISTAKE",
            MistakeCategory.BLUNDER: "BLUNDER",
        }

        for game_name, move in display_moves:
            loss = move.points_lost if move.points_lost else move.score_loss
            importance = (
                move.importance
                if hasattr(move, "importance") and move.importance
                else loss
            )
            mistake = mistake_labels.get(move.mistake_category, "UNKNOWN")

            # 座標変換（SGF座標→GTP座標）
            coord = move.gtp or "-"
            # move.gtp が2文字の小文字アルファベット（SGF座標）の場合、変換
            if coord and len(coord) == 2 and coord.isalpha() and coord.islower():
                coord = _convert_sgf_to_gtp_coord(coord, 19)

            # Importance score (v128+)
            importance = move.importance_score or 0.0

            # ゲーム名が長い場合でも短縮しない (Phase V4: Pure Data)
            game_full_id = game_name
            lines.append(
                f"| {game_full_id} | {move.move_number} | {move.player or '-'} | "
                f"{coord or '-'} | {loss:.1f} | {importance:.1f} | {mistake} |"
            )
    else:
        if sequences:
            lines.append(f"{i18n._('summary:normal_worst')}: {i18n._('summary:none_urgent_only')}")

    return "\n".join(lines)


def _format_weakness_hypothesis(
    player_name: str,
    stats: SummaryStats,
    analyzer: SummaryAnalyzer,
    confidence_level: Optional["eval_metrics.ConfidenceLevel"] = None,
) -> str:
    """弱点仮説セクションを生成（複数局サマリー用）"""
    # PR#1: Default to HIGH if not provided
    if confidence_level is None:
        confidence_level = eval_metrics.ConfidenceLevel.HIGH

    # PR#1: Confidence-based wording
    is_low_conf = confidence_level == eval_metrics.ConfidenceLevel.LOW
    is_medium_conf = confidence_level == eval_metrics.ConfidenceLevel.MEDIUM

    # PR#1: Add "(※参考情報)" suffix for LOW confidence
    header_suffix = f" ({i18n._('summary:suffix:ref')})" if is_low_conf else ""
    lines = [f"## {i18n._('summary:weakness')} ({player_name}){header_suffix}", ""]

    # 急場見逃しパターンを検出 (using Logic class)
    sequences, _ = analyzer.detect_urgent_miss_sequences(player_name)

    # クロス集計から弱点を抽出
    priorities = stats.get_practice_priorities()

    if priorities:
        # PR#1: Use hedged wording for MEDIUM/LOW confidence
        if is_low_conf:
            lines.append(f"{i18n._('summary:weakness:trend_ref')}:")
        elif is_medium_conf:
            lines.append(f"{i18n._('summary:weakness:trend')}:")
        else:
            lines.append(f"{i18n._('summary:weakness:analysis')}:")
        lines.append("")
        for priority in priorities:
            lines.append(f"- {priority}")
    else:
        lines.append(f"- {i18n._('summary:weakness:none')}")

    # 急場見逃しがあれば追加
    if sequences:
        lines.append("")
        lines.append(f"**{i18n._('summary:urgent_miss')}**:")
        for seq in sequences:
            # Use full identifier (Phase V4)
            game_full_id = seq["game"]
            avg_loss = seq["total_loss"] / seq["count"]
            lines.append(
                f"- {game_full_id} #{seq['start']}-{seq['end']}: "
                f"{seq['count']}{i18n._('summary:unit:moves_continuous')}, {i18n._('summary:total_loss')}{seq['total_loss']:.1f}{i18n._('summary:unit:points')} ({i18n._('summary:avg')}{avg_loss:.1f}{i18n._('summary:unit:points_per_move')})"
            )

        lines.append("")
        lines.append(f"**{i18n._('summary:recommendation')}**:")
        lines.append(f"- {i18n._('summary:rec:tsumego')}")
        lines.append(f"- {i18n._('summary:rec:safety')}")
        lines.append(f"- {i18n._('summary:rec:review')}")

    # PR#1: Add re-analysis recommendation for LOW confidence
    if is_low_conf:
        lines.append("")
        lines.append(f"⚠️ {i18n._('summary:warning:low_visits')}")

    return "\n".join(lines)


def _format_practice_priorities(
    player_name: str,
    stats: SummaryStats,
    confidence_level: Optional["eval_metrics.ConfidenceLevel"] = None,
) -> str:
    """練習優先事項セクションを生成"""
    # PR#1: Default to HIGH if not provided
    if confidence_level is None:
        confidence_level = eval_metrics.ConfidenceLevel.HIGH

    # PR#1: LOW confidence → placeholder only
    if confidence_level == eval_metrics.ConfidenceLevel.LOW:
        return "\n".join(
            [
                f"## {i18n._('summary:practice')} ({player_name})",
                "",
                f"- {i18n._('summary:practice:low_data_msg')}",
            ]
        )

    lines = [f"## {i18n._('summary:practice')} ({player_name})"]
    lines.append("")
    lines.append(i18n._('summary:practice:intro'))
    lines.append("")

    priorities = stats.get_practice_priorities()

    # PR#1: MEDIUM confidence → limit to 1 priority
    if confidence_level == eval_metrics.ConfidenceLevel.MEDIUM and len(priorities) > 1:
        priorities = priorities[:1]

    if not priorities:
        lines.append(f"- {i18n._('summary:practice:none')}")
    else:
        for i, priority in enumerate(priorities, 1):
            lines.append(f"- {i}. {priority}")

    return "\n".join(lines)

