"""Summary report generation for multiple game analysis.

PR #116: Phase B2 - summary_report.py extraction from game.py

This module contains all static methods related to multi-game summary
report generation. These were previously in the Game class but are
stateless and can be extracted without any changes to the interface.

All functions in this module:
- Are static (no self parameter)
- Do not modify any state
- Do not import from katrain.gui (core layer only)
"""

from datetime import datetime
from typing import Any, Optional

from katrain.core import eval_metrics
from katrain.core.batch.helpers import truncate_game_name
from katrain.core.eval_metrics import (
    GameSummaryData,
    MistakeCategory,
    PositionDifficulty,
    SummaryStats,
    get_canonical_loss_from_move,
)
from katrain.core.game_node import Move


def build_summary_report(game_data_list: list["GameSummaryData"], focus_player: str | None = None) -> str:
    """
    複数局から統計まとめを生成（Phase 6）

    Args:
        game_data_list: 各対局のデータリスト
        focus_player: 集計対象プレイヤー名（Noneなら全プレイヤー）

    Returns:
        Markdown形式のまとめレポート
    """
    if not game_data_list:
        return "# Multi-Game Summary\n\nNo games provided."

    # プレイヤー別に統計を集計
    player_stats = _aggregate_player_stats(game_data_list, focus_player)

    # Markdownセクションをフォーマット
    sections = ["# Multi-Game Summary\n"]
    sections.append(_format_meta_section(game_data_list, focus_player))

    for player, stats in player_stats.items():
        # PR#1: Compute confidence level per player
        confidence_level = eval_metrics.compute_confidence_level(stats.all_moves)

        sections.append("")
        sections.append(_format_overall_stats(player, stats, confidence_level))
        sections.append("")
        sections.append(_format_mistake_distribution(player, stats))
        sections.append("")
        sections.append(_format_freedom_distribution(player, stats))
        sections.append("")
        sections.append(_format_phase_breakdown(player, stats))
        sections.append("")
        # Phase × Mistake クロス集計テーブル追加
        sections.append(_format_phase_mistake_breakdown(player, stats))
        sections.append("")
        sections.append(_format_top_worst_moves(player, stats, confidence_level))
        sections.append("")
        sections.append(_format_weakness_hypothesis(player, stats, confidence_level))
        sections.append("")
        sections.append(_format_practice_priorities(player, stats, confidence_level))

    return "\n".join(sections)


def _aggregate_player_stats(
    game_data_list: list["GameSummaryData"], focus_player: str | None = None
) -> dict[str, "SummaryStats"]:
    """プレイヤー別に統計を集計"""
    player_stats: dict[str, SummaryStats] = {}

    for game_data in game_data_list:
        for player_color in ["B", "W"]:
            player_name = game_data.player_black if player_color == "B" else game_data.player_white

            # focus_player指定がある場合、それ以外はスキップ
            if focus_player and player_name != focus_player:
                continue

            # プレイヤー統計を初期化
            if player_name not in player_stats:
                player_stats[player_name] = SummaryStats(
                    player_name=player_name,
                    mistake_counts={cat: 0 for cat in MistakeCategory},
                    mistake_total_loss={cat: 0.0 for cat in MistakeCategory},
                    freedom_counts={diff: 0 for diff in PositionDifficulty},
                    phase_moves={"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
                    phase_loss={"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0},
                )

            stats = player_stats[player_name]
            stats.total_games += 1

            # このプレイヤーの手のみを集計
            player_moves = [m for m in game_data.snapshot.moves if m.player == player_color]
            stats.total_moves += len(player_moves)

            # PR#1: Store moves for confidence level computation
            stats.all_moves.extend(player_moves)

            for move in player_moves:
                # 損失を集計（canonical loss: 常に >= 0）
                loss = get_canonical_loss_from_move(move)
                if loss > 0:
                    stats.total_points_lost += loss

                # ミス分類を集計
                if move.mistake_category:
                    stats.mistake_counts[move.mistake_category] += 1
                    if loss > 0:
                        stats.mistake_total_loss[move.mistake_category] += loss

                # Freedom（手の自由度）を集計
                if move.position_difficulty:
                    stats.freedom_counts[move.position_difficulty] += 1

                # 局面タイプを集計
                phase = move.tag or "unknown"
                stats.phase_moves[phase] = stats.phase_moves.get(phase, 0) + 1
                if loss > 0:
                    stats.phase_loss[phase] = stats.phase_loss.get(phase, 0.0) + loss

                # Phase × MistakeCategory クロス集計
                if move.mistake_category:
                    key = (phase, move.mistake_category)
                    stats.phase_mistake_counts[key] = stats.phase_mistake_counts.get(key, 0) + 1
                    if loss > 0:
                        stats.phase_mistake_loss[key] = stats.phase_mistake_loss.get(key, 0.0) + loss

                # 最悪手を記録（Top 10を保持）
                if loss > 0.5:  # 0.5目以上の損失のみ
                    stats.worst_moves.append((game_data.game_name, move))

    # 各プレイヤーの統計を完成させる
    for stats in player_stats.values():
        if stats.total_moves > 0:
            stats.avg_points_lost_per_move = stats.total_points_lost / stats.total_moves

        # 最悪手をソートする（Top 10への絞り込みは _format_top_worst_moves で実施）
        stats.worst_moves.sort(key=lambda x: x[1].points_lost or x[1].score_loss or 0, reverse=True)

    return player_stats


def _format_meta_section(game_data_list: list["GameSummaryData"], focus_player: str | None) -> str:
    """メタ情報セクションを生成"""
    lines = ["## Meta"]
    lines.append(f"- Games analyzed: {len(game_data_list)}")

    # プレイヤー情報
    all_players = set()
    for gd in game_data_list:
        all_players.add(gd.player_black)
        all_players.add(gd.player_white)

    if focus_player:
        lines.append(f"- Focus player: {focus_player}")
    else:
        lines.append(f"- Players: {', '.join(sorted(all_players))}")

    # 日付範囲
    dates = [gd.date for gd in game_data_list if gd.date]
    if dates:
        lines.append(f"- Date range: {min(dates)} to {max(dates)}")

    # 生成日時
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"- Generated: {now}")

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
    confidence_label = eval_metrics.get_confidence_label(confidence_level, lang="ja")

    lines = [f"## Overall Statistics ({player_name})"]
    lines.append(f"- **{confidence_label}**")  # PR#1: Confidence level
    lines.append(f"- Total games: {stats.total_games}")
    lines.append(f"- Total moves analyzed: {stats.total_moves}")
    lines.append(f"- Total points lost: {stats.total_points_lost:.1f}")
    lines.append(f"- Average points lost per move: {stats.avg_points_lost_per_move:.2f}")

    if stats.worst_moves:
        worst_game, worst_move = stats.worst_moves[0]
        loss = worst_move.points_lost if worst_move.points_lost else worst_move.score_loss
        lines.append(
            f"- Worst single move: {worst_game} #{worst_move.move_number} {worst_move.gtp or '-'} ({loss:.1f} points)"
        )

    # PR#1: Add LOW confidence warning
    if confidence_level == eval_metrics.ConfidenceLevel.LOW:
        lines.append("")
        lines.append("⚠️ 解析訪問数が少ないため、結果が不安定な可能性があります。再解析を推奨します。")

    return "\n".join(lines)


def _format_mistake_distribution(player_name: str, stats: SummaryStats) -> str:
    """ミス分類分布セクションを生成"""
    lines = [f"## Mistake Distribution ({player_name})"]
    lines.append("| Category | Count | Percentage | Avg Loss |")
    lines.append("|----------|-------|------------|----------|")

    category_labels = {
        MistakeCategory.GOOD: "Good",
        MistakeCategory.INACCURACY: "Inaccuracy",
        MistakeCategory.MISTAKE: "Mistake",
        MistakeCategory.BLUNDER: "Blunder",
    }

    for cat in [MistakeCategory.GOOD, MistakeCategory.INACCURACY, MistakeCategory.MISTAKE, MistakeCategory.BLUNDER]:
        count = stats.mistake_counts.get(cat, 0)
        pct = stats.get_mistake_percentage(cat)
        avg_loss = stats.get_mistake_avg_loss(cat)
        lines.append(f"| {category_labels[cat]} | {count} | {pct:.1f}% | {avg_loss:.2f} |")

    return "\n".join(lines)


def _format_freedom_distribution(player_name: str, stats: SummaryStats) -> str:
    """Freedom（手の自由度）分布セクションを生成"""
    lines = [f"## Freedom Distribution ({player_name})"]
    lines.append("| Difficulty | Count | Percentage |")
    lines.append("|------------|-------|------------|")

    difficulty_labels = {
        PositionDifficulty.EASY: "Easy (wide)",
        PositionDifficulty.NORMAL: "Normal",
        PositionDifficulty.HARD: "Hard (narrow)",
        PositionDifficulty.ONLY_MOVE: "Only move",
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
    lines = [f"## Phase Breakdown ({player_name})"]
    lines.append("| Phase | Moves | Points Lost | Avg Loss |")
    lines.append("|-------|-------|-------------|----------|")

    phase_labels = {
        "opening": "Opening",
        "middle": "Middle game",
        "yose": "Endgame",
        "unknown": "Unknown",
    }

    for phase in ["opening", "middle", "yose", "unknown"]:
        count = stats.phase_moves.get(phase, 0)
        loss = stats.phase_loss.get(phase, 0.0)
        avg_loss = stats.get_phase_avg_loss(phase)
        lines.append(f"| {phase_labels.get(phase, phase)} | {count} | {loss:.1f} | {avg_loss:.2f} |")

    return "\n".join(lines)


def _format_phase_mistake_breakdown(player_name: str, stats: SummaryStats) -> str:
    """Phase × Mistake クロス集計セクションを生成"""
    lines = [f"## Phase × Mistake Breakdown ({player_name})"]
    lines.append("| Phase | Good | Inaccuracy | Mistake | Blunder | Total Loss |")
    lines.append("|-------|------|------------|---------|---------|------------|")

    phase_labels = {
        "opening": "Opening",
        "middle": "Middle game",
        "yose": "Endgame",
        "unknown": "Unknown",
    }

    for phase in ["opening", "middle", "yose"]:
        cells = [phase_labels.get(phase, phase)]

        for cat in [MistakeCategory.GOOD, MistakeCategory.INACCURACY, MistakeCategory.MISTAKE, MistakeCategory.BLUNDER]:
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


def _detect_urgent_miss_sequences(
    worst_moves: list[tuple[str, Any]], threshold_loss: float = 20.0, min_consecutive: int = 3
) -> tuple[list[Any], list[tuple[str, Any]]]:
    """
    連続する大損失手を「急場見逃しパターン」として検出

    Args:
        worst_moves: [(game_name, move), ...] のリスト
        threshold_loss: 損失閾値（デフォルト20目）
        min_consecutive: 最小連続手数（デフォルト3手）

    Returns:
        sequences: 検出されたシーケンスのリスト
        filtered_moves: 急場見逃し区間を除外した通常のワースト手リスト
    """
    sequences = []
    filtered_moves = []
    current_seq = None

    # worst_movesを手数でソート（同じゲーム内で連続しているかチェックするため）
    sorted_moves = sorted(worst_moves, key=lambda x: (x[0], x[1].move_number))

    for _i, (game_name, move) in enumerate(sorted_moves):
        loss = move.points_lost if move.points_lost else move.score_loss or 0

        if loss >= threshold_loss:
            if current_seq is None:
                # 新しいシーケンス開始
                current_seq = {
                    "game": game_name,
                    "start": move.move_number,
                    "end": move.move_number,
                    "moves": [(game_name, move)],
                    "total_loss": loss,
                    "count": 1,
                }
            elif current_seq["game"] == game_name and move.move_number <= current_seq["end"] + 2:
                # 連続している（1手スキップまで許容）
                current_seq["end"] = move.move_number
                current_seq["moves"].append((game_name, move))
                current_seq["total_loss"] += loss
                current_seq["count"] += 1
            else:
                # 連続が途切れた
                if current_seq["count"] >= min_consecutive:
                    sequences.append(current_seq)
                else:
                    # 閾値を超えているが連続していない → 通常のワースト手に追加
                    filtered_moves.extend(current_seq["moves"])

                # 新しいシーケンス開始
                current_seq = {
                    "game": game_name,
                    "start": move.move_number,
                    "end": move.move_number,
                    "moves": [(game_name, move)],
                    "total_loss": loss,
                    "count": 1,
                }
        else:
            # 閾値未満
            if current_seq:
                if current_seq["count"] >= min_consecutive:
                    sequences.append(current_seq)
                else:
                    # 閾値を超えているが連続していない → 通常のワースト手に追加
                    filtered_moves.extend(current_seq["moves"])
                current_seq = None

            # 通常のワースト手に追加
            filtered_moves.append((game_name, move))

    # 最後のシーケンス処理
    if current_seq:
        if current_seq["count"] >= min_consecutive:
            sequences.append(current_seq)
        else:
            filtered_moves.extend(current_seq["moves"])

    return sequences, filtered_moves


def _format_top_worst_moves(
    player_name: str,
    stats: SummaryStats,
    confidence_level: Optional["eval_metrics.ConfidenceLevel"] = None,
) -> str:
    """最悪手Top 10セクションを生成（急場見逃しパターンを分離）"""
    # PR#1: Default to HIGH if not provided
    if confidence_level is None:
        confidence_level = eval_metrics.ConfidenceLevel.HIGH

    # PR#1: Limit worst moves count based on confidence
    max_count = eval_metrics.get_important_moves_limit(confidence_level)
    title_suffix = " (候補)" if confidence_level == eval_metrics.ConfidenceLevel.LOW else ""
    lines = [f"## Top Worst Moves ({player_name}){title_suffix}"]

    if not stats.worst_moves:
        lines.append("- No significant mistakes found.")
        return "\n".join(lines)

    # 急場見逃しパターンを検出
    sequences, filtered_moves = _detect_urgent_miss_sequences(stats.worst_moves, threshold_loss=20.0, min_consecutive=3)

    # 急場見逃しパターンがあれば表示
    if sequences:
        lines.append("")
        lines.append("**注意**: 以下の区間は双方が急場を見逃した可能性があります（損失20目超が3手以上連続）")
        lines.append("| Game | 手数範囲 | 連続 | 総損失 | 平均損失/手 |")
        lines.append("|------|---------|------|--------|------------|")

        for seq in sequences:
            short_game = truncate_game_name(seq["game"])
            avg_loss = seq["total_loss"] / seq["count"]
            lines.append(
                f"| {short_game} | #{seq['start']}-{seq['end']} | "
                f"{seq['count']}手 | {seq['total_loss']:.1f}目 | {avg_loss:.1f}目 |"
            )
        lines.append("")

    # 通常のワースト手を表示
    if filtered_moves:
        # 損失でソートして confidence level に応じた件数を取得
        filtered_moves.sort(key=lambda x: x[1].points_lost or x[1].score_loss or 0, reverse=True)
        # PR#1: Use max_count from confidence level (default was 10)
        display_limit = min(10, max_count)
        display_moves = filtered_moves[:display_limit]

        if sequences:
            lines.append("通常のワースト手（損失20目以下 or 単発）:")
        lines.append("| Game | # | P | Coord | Loss | Importance | Category |")
        lines.append("|------|---|---|-------|------|------------|----------|")

        mistake_labels = {
            MistakeCategory.GOOD: "GOOD",
            MistakeCategory.INACCURACY: "INACCURACY",
            MistakeCategory.MISTAKE: "MISTAKE",
            MistakeCategory.BLUNDER: "BLUNDER",
        }

        for game_name, move in display_moves:
            loss = move.points_lost if move.points_lost else move.score_loss
            importance = move.importance if hasattr(move, "importance") and move.importance else loss
            mistake = mistake_labels.get(move.mistake_category, "UNKNOWN")

            # 座標変換（SGF座標→GTP座標）
            coord = move.gtp or "-"
            # move.gtp が2文字の小文字アルファベット（SGF座標）の場合、変換
            if coord and len(coord) == 2 and coord.isalpha() and coord.islower():
                coord = _convert_sgf_to_gtp_coord(coord, 19)

            # ゲーム名が長い場合は短縮
            short_game = truncate_game_name(game_name)
            lines.append(
                f"| {short_game} | {move.move_number} | {move.player or '-'} | "
                f"{coord or '-'} | {loss:.1f} | {importance:.1f} | {mistake} |"
            )
    else:
        if sequences:
            lines.append("通常のワースト手: なし（すべて急場見逃しパターン）")

    return "\n".join(lines)


def _format_weakness_hypothesis(
    player_name: str,
    stats: SummaryStats,
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
    header_suffix = " (※参考情報)" if is_low_conf else ""
    lines = [f"## Weakness Hypothesis ({player_name}){header_suffix}", ""]

    # 急場見逃しパターンを検出（棋力別閾値を使用）
    # Note: このメソッドは static なので config にアクセスできない
    # 現在 UI では使われていないため、標準設定をデフォルトとする
    urgent_config = eval_metrics.get_urgent_miss_config("standard")

    sequences, _ = _detect_urgent_miss_sequences(
        stats.worst_moves, threshold_loss=urgent_config.threshold_loss, min_consecutive=urgent_config.min_consecutive
    )

    # クロス集計から弱点を抽出
    priorities = stats.get_practice_priorities()

    if priorities:
        # PR#1: Use hedged wording for MEDIUM/LOW confidence
        if is_low_conf:
            lines.append("傾向が見られる項目（※参考情報）:")
        elif is_medium_conf:
            lines.append("傾向が見られる項目（Based on cross-tabulation analysis）:")
        else:
            lines.append("Based on cross-tabulation analysis:")
        lines.append("")
        for priority in priorities:
            lines.append(f"- {priority}")
    else:
        lines.append("- 明確な弱点パターンは検出されませんでした。")

    # 急場見逃しがあれば追加
    if sequences:
        lines.append("")
        lines.append("**急場見逃しパターン**:")
        for seq in sequences:
            short_game = truncate_game_name(seq["game"])
            avg_loss = seq["total_loss"] / seq["count"]
            lines.append(
                f"- {short_game} #{seq['start']}-{seq['end']}: "
                f"{seq['count']}手連続、総損失{seq['total_loss']:.1f}目（平均{avg_loss:.1f}目/手）"
            )

        lines.append("")
        lines.append("**推奨アプローチ**:")
        lines.append("- 詰碁（死活）訓練で読みの精度向上")
        lines.append("- 対局中、戦いの前に「自分の石は安全か？」「相手の弱点はどこか？」を確認")
        lines.append("- 急場見逃し区間のSGFを重点的に復習")

    # PR#1: Add re-analysis recommendation for LOW confidence
    if is_low_conf:
        lines.append("")
        lines.append("⚠️ 解析訪問数が少ないため、visits増で再解析を推奨します。")

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
                f"## 練習の優先順位 ({player_name})",
                "",
                "- ※ データ不足のため練習優先度は保留。visits増で再解析を推奨します。",
            ]
        )

    lines = [f"## 練習の優先順位 ({player_name})"]
    lines.append("")
    lines.append("Based on the data above, consider focusing on:")
    lines.append("")

    priorities = stats.get_practice_priorities()

    # PR#1: MEDIUM confidence → limit to 1 priority
    if confidence_level == eval_metrics.ConfidenceLevel.MEDIUM and len(priorities) > 1:
        priorities = priorities[:1]

    if not priorities:
        lines.append("- No specific priorities identified. Keep up the good work!")
    else:
        for i, priority in enumerate(priorities, 1):
            lines.append(f"- {i}. {priority}")

    return "\n".join(lines)
