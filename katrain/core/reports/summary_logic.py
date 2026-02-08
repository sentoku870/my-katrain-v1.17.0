"""Summary Report Logic.

This module contains the logic for aggregating game data and calculating
statistics for the multi-game summary report. It separates the data
processing from the Markdown presentation layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core import eval_metrics
from katrain.core.eval_metrics import (
    GameSummaryData,
    MistakeCategory,
    PositionDifficulty,
    SummaryStats,
    get_canonical_loss_from_move,
)
from katrain.core.reports.constants import (
    BAD_MOVE_LOSS_THRESHOLD,
    URGENT_MISS_MIN_CONSECUTIVE,
    URGENT_MISS_THRESHOLD_LOSS,
)

if TYPE_CHECKING:
    from katrain.core.game_node import Move


class SummaryAnalyzer:
    """Analyzes multiple games to produce summary statistics."""

    def __init__(self, game_data_list: list[GameSummaryData], focus_player: str | None = None):
        self.game_data_list = game_data_list
        self.focus_player = focus_player
        self.player_stats: dict[str, SummaryStats] = {}
        self._aggregate_stats()

    def _aggregate_stats(self) -> None:
        """Aggregate stats for each player across all games."""
        for game_data in self.game_data_list:
            for player_color in ["B", "W"]:
                player_name = game_data.player_black if player_color == "B" else game_data.player_white

                # focus_player指定がある場合、それ以外はスキップ
                if self.focus_player and player_name != self.focus_player:
                    continue

                # プレイヤー統計を初期化
                if player_name not in self.player_stats:
                    self.player_stats[player_name] = SummaryStats(
                        player_name=player_name,
                        mistake_counts={cat: 0 for cat in MistakeCategory},
                        mistake_total_loss={cat: 0.0 for cat in MistakeCategory},
                        freedom_counts={diff: 0 for diff in PositionDifficulty},
                        phase_moves={"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
                        phase_loss={
                            "opening": 0.0,
                            "middle": 0.0,
                            "yose": 0.0,
                            "unknown": 0.0,
                        },
                    )

                stats = self.player_stats[player_name]
                stats.total_games += 1

                # このプレイヤーの手のみを集計
                player_moves = [m for m in game_data.snapshot.moves if m.player == player_color]
                stats.total_moves += len(player_moves)

                # Store moves for confidence level computation
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
                            stats.phase_mistake_loss[key] = (
                                stats.phase_mistake_loss.get(key, 0.0) + loss
                            )

                    # 最悪手を記録（Top 10を保持）
                    if loss > BAD_MOVE_LOSS_THRESHOLD:
                        stats.worst_moves.append((game_data.game_name, move))

                    # Reason Tags Aggregation (v6)
                    if move.reason_tags:
                        stats.tag_occurrences_total += len(move.reason_tags)
                        stats.tagged_moves_count += 1
                        for tag in move.reason_tags:
                            stats.reason_tags_counts[tag] = stats.reason_tags_counts.get(tag, 0) + 1

                # Aggregate Reason Tags from GameSummaryData (if available)
                # Note: GameSummaryData has snapshot, but extraction.py typically 
                # provides aggregated reason_tags_by_player in the raw stats dict.
                # Here we assume GameSummaryData is enriched with these if possible,
                # or we rely on what was extracted during batch processing.
                # In build_summary_json context, we might need to ensure these are passed.
                if hasattr(game_data, "reason_tags_by_player") and player_color in game_data.reason_tags_by_player:
                    rt_counts = game_data.reason_tags_by_player[player_color]
                    for tag, count in rt_counts.items():
                        stats.reason_tags_counts[tag] = stats.reason_tags_counts.get(tag, 0) + count
                
                if hasattr(game_data, "important_moves_stats_by_player") and player_color in game_data.important_moves_stats_by_player:
                    im_stats = game_data.important_moves_stats_by_player[player_color]
                    stats.important_moves_count += im_stats.get("important_count", 0)
                    stats.tagged_moves_count += im_stats.get("tagged_count", 0)
                    stats.tag_occurrences_total += im_stats.get("tag_occurrences", 0)

        # 各プレイヤーの統計を完成させる
        for stats in self.player_stats.values():
            if stats.total_moves > 0:
                stats.avg_points_lost_per_move = stats.total_points_lost / stats.total_moves

            # 最悪手をソートする
            stats.worst_moves.sort(
                key=lambda x: x[1].points_lost or x[1].score_loss or 0, reverse=True
            )

    def get_player_stats(self, player_name: str) -> SummaryStats | None:
        return self.player_stats.get(player_name)

    def get_all_player_stats(self) -> dict[str, SummaryStats]:
        return self.player_stats

    def detect_mistake_sequences(self, player_name: str) -> tuple[list[Any], list[tuple[str, Any]]]:
        """Detect successive mistake sequences for a player."""
        stats = self.player_stats.get(player_name)
        if not stats or not stats.worst_moves:
            return [], []

        return self._detect_mistake_sequences_impl(
            stats.worst_moves,
            URGENT_MISS_THRESHOLD_LOSS,
            URGENT_MISS_MIN_CONSECUTIVE,
        )

    def _detect_mistake_sequences_impl(
        self,
        worst_moves: list[tuple[str, Any]],
        threshold_loss: float,
        min_consecutive: int,
    ) -> tuple[list[Any], list[tuple[str, Any]]]:
        """
        連続する大損失手を「ミス連続パターン（mistake sequences）」として検出
        Implementation moved from summary_report.py
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
                elif (
                    current_seq["game"] == game_name
                    and move.move_number <= current_seq["end"] + 2
                ):
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
