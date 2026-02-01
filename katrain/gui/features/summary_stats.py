# katrain/gui/features/summary_stats.py
#
# サマリ統計計算モジュール
#
# __main__.py から抽出したサマリ統計関連のPure関数を配置します。
# - extract_analysis_from_sgf_node: SGFノードから解析データを抽出
# - extract_sgf_statistics: SGFファイルから統計データを抽出

import base64
import binascii
import gzip
import json
import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from katrain.core import eval_metrics
from katrain.core.game import KaTrainSGF
from katrain.gui.features.types import LogFunction

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine
    from katrain.gui.features.context import FeatureContext


def extract_analysis_from_sgf_node(node) -> Optional[dict]:
    """SGFノードのKTプロパティから解析データを抽出。

    Args:
        node: SGFノード（analysis_from_sgf属性を持つ）

    Returns:
        解析データ辞書（{"root": {...}, "moves": {...}}）、または None
    """
    # CRITICAL: GameNode.add_list_property() は KT プロパティを
    # node.properties ではなく node.analysis_from_sgf に保存する
    kt_data = getattr(node, 'analysis_from_sgf', None)

    if not kt_data:
        return None

    try:
        # KTプロパティは複数の圧縮データのリスト
        if not isinstance(kt_data, list):
            return None

        if len(kt_data) < 3:
            return None

        # KaTrain SGF format: [ownership_data, policy_data, main_data]
        # Only main_data is JSON, ownership and policy are binary floats
        main_data = gzip.decompress(base64.standard_b64decode(kt_data[2]))
        analysis = json.loads(main_data)

        # analysis already contains {"root": {...}, "moves": {...}}
        # Cast is safe: json.loads returns dict for valid JSON object
        return analysis  # type: ignore[no-any-return]

    except (gzip.BadGzipFile, binascii.Error, json.JSONDecodeError, KeyError, IndexError) as e:
        logger.debug("Failed to extract analysis from SGF node: %s", type(e).__name__)
        return None
    except Exception:
        # Unexpected error - log with full traceback for investigation
        logger.warning("Unexpected error extracting analysis from SGF node", exc_info=True)
        return None


def extract_sgf_statistics(
    path: str,
    ctx: "FeatureContext",
    engine: "KataGoEngine",
    log_fn: LogFunction,
) -> Optional[dict]:
    """SGFファイルから統計データを直接抽出（KTプロパティ解析）。

    Args:
        path: SGFファイルパス
        ctx: FeatureContext（config取得用）
        engine: KataGoEngine（一時Game作成用）
        log_fn: ログ出力関数（message, level）

    Returns:
        統計データ辞書、または None（エラー時）
    """
    from katrain.core.constants import OUTPUT_ERROR

    try:
        move_tree = KaTrainSGF.parse_file(path)
        nodes = list(move_tree.nodes_in_tree)

        # メタデータ
        player_black = move_tree.get_property("PB", "Black")
        player_white = move_tree.get_property("PW", "White")
        handicap = int(move_tree.get_property("HA", "0"))
        date = move_tree.get_property("DT", None)
        board_size_prop = move_tree.get_property("SZ", "19")
        try:
            board_size = (int(board_size_prop), int(board_size_prop))
        except (ValueError, TypeError):
            # int() conversion can raise ValueError (non-numeric) or TypeError (None)
            board_size = (19, 19)

        # 段級位情報を抽出（Phase 10-C）
        rank_black = move_tree.get_property("BR", None)
        rank_white = move_tree.get_property("WR", None)

        # 統計用カウンター
        stats = {
            "game_name": os.path.basename(path),
            "player_black": player_black,
            "player_white": player_white,
            "rank_black": rank_black,  # Phase 10-C
            "rank_white": rank_white,  # Phase 10-C
            "handicap": handicap,
            "date": date,
            "board_size": board_size,
            "total_moves": 0,
            "total_points_lost": 0.0,
            # Phase 4: プレイヤー別の統計
            "moves_by_player": {"B": 0, "W": 0},
            "loss_by_player": {"B": 0.0, "W": 0.0},
            "mistake_counts": {cat: 0 for cat in eval_metrics.MistakeCategory},
            "mistake_total_loss": {cat: 0.0 for cat in eval_metrics.MistakeCategory},
            "freedom_counts": {diff: 0 for diff in eval_metrics.PositionDifficulty},
            "phase_moves": {"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
            "phase_loss": {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0},
            "phase_mistake_counts": {},  # {(phase, category): count}
            "phase_mistake_loss": {},  # {(phase, category): loss}
            "worst_moves": [],  # (move_number, player, gtp, points_lost, category)
        }

        prev_score = None
        moves_with_kt = 0
        moves_with_analysis = 0
        move_count = 0
        for i, node in enumerate(nodes):
            # 手があるノードのみ処理
            move_prop = node.get_property("B") or node.get_property("W")
            if not move_prop:
                continue

            move_count += 1
            player = "B" if node.get_property("B") else "W"
            gtp = move_prop

            # KTプロパティから解析データを取得
            analysis = extract_analysis_from_sgf_node(node)
            if analysis:
                moves_with_kt += 1
            if not analysis or "root" not in analysis or not analysis["root"]:
                continue
            moves_with_analysis += 1

            score = analysis["root"].get("scoreLead")
            if score is None:
                prev_score = None
                continue

            # points_lost を計算（親ノードとのスコア差）
            points_lost = None
            if prev_score is not None:
                player_sign = 1 if player == "B" else -1
                points_lost = player_sign * (prev_score - score)

            prev_score = score

            # 解析データがある手は全てカウント
            if points_lost is not None:
                stats["total_moves"] += 1
                # Phase 4: プレイヤー別にカウント
                stats["moves_by_player"][player] += 1

                # 損失は正の値のみ加算
                if points_lost > 0:
                    stats["total_points_lost"] += points_lost
                    # Phase 4: プレイヤー別に損失を記録
                    stats["loss_by_player"][player] += points_lost

                # ミス分類（負の損失は"良い手"としてカウント）
                # canonical loss: 常に >= 0
                canonical_loss = max(0.0, points_lost)
                category = eval_metrics.classify_mistake(canonical_loss, None)
                stats["mistake_counts"][category] += 1
                stats["mistake_total_loss"][category] += canonical_loss

                # Freedom（未実装の場合はUNKNOWN）
                freedom = eval_metrics.PositionDifficulty.UNKNOWN
                stats["freedom_counts"][freedom] += 1

                # Phase（簡易版：手数ベース）
                move_number = i
                phase = eval_metrics.classify_game_phase(move_number)

                stats["phase_moves"][phase] += 1
                if canonical_loss > 0:
                    stats["phase_loss"][phase] += canonical_loss

                # Phase × Mistake クロス集計（Phase 6.5で追加）
                key = (phase, category)
                stats["phase_mistake_counts"][key] = stats["phase_mistake_counts"].get(key, 0) + 1
                if canonical_loss > 0:
                    stats["phase_mistake_loss"][key] = stats["phase_mistake_loss"].get(key, 0.0) + canonical_loss

                # Importance を簡易計算（points_lost をベースに）
                # 本来は delta_score, delta_winrate, swing_bonus を考慮するが、
                # SGF直接パースではそれらが取れないため、points_lost をそのまま使用
                importance = max(0, points_lost)

                # Worst moves記録（損失がある手のみ）
                if points_lost > 0.5:  # 閾値: 0.5目以上の損失
                    stats["worst_moves"].append((move_number, player, gtp, points_lost, importance, category))

        # Worst movesをソート（損失の大きい順）
        stats["worst_moves"].sort(key=lambda x: x[3], reverse=True)
        stats["worst_moves"] = stats["worst_moves"][:10]  # Top 10

        # Extract reason_tags counts from important moves (Phase 10-B)
        reason_tags_counts: Dict[str, int] = {}
        try:
            # Create a temporary Game object to compute reason_tags
            from katrain.core.game import Game
            # Note: Game expects GameNode but SGFNode works at runtime
            temp_game = Game(ctx, engine, move_tree=move_tree)  # type: ignore[arg-type]

            # Load analysis data from SGF into Game nodes
            sgf_nodes = list(move_tree.nodes_in_tree)
            game_nodes = list(temp_game.root.nodes_in_tree)

            for sgf_node, game_node in zip(sgf_nodes, game_nodes):
                # Extract analysis from SGF node
                analysis = extract_analysis_from_sgf_node(sgf_node)
                if analysis:
                    # Directly set analysis dict (already in correct format)
                    game_node.analysis = analysis

            # Get skill preset for tag threshold calculation (Option 0-B: Problem 3 fix)
            skill_preset = ctx.config("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET

            # Get important moves with reason_tags
            important_moves = temp_game.get_important_move_evals(level=skill_preset, compute_reason_tags=True)

            # Count reason_tags
            for move_eval in important_moves:
                for tag in move_eval.reason_tags:
                    reason_tags_counts[tag] = reason_tags_counts.get(tag, 0) + 1

        except Exception as e:
            # If reason_tags computation fails, log but continue
            log_fn(f"Failed to compute reason_tags for {path}: {e}", OUTPUT_ERROR)
            import traceback
            log_fn(traceback.format_exc(), OUTPUT_ERROR)
            reason_tags_counts = {}

        # Add to stats dict
        stats["reason_tags_counts"] = reason_tags_counts  # {tag: count}

        # Phase 60: Time analysis (pacing/tilt)
        try:
            from katrain.core.analysis.time import (
                parse_time_data,
                analyze_pacing,
                extract_pacing_stats_for_summary,
            )
            from katrain.core.analysis.logic import snapshot_from_game

            time_data = parse_time_data(move_tree)
            if time_data.has_time_data:
                # Reuse temp_game from reason_tags if available, otherwise create it
                if "temp_game" not in dir():
                    from katrain.core.game import Game
                    # Note: Game expects GameNode but SGFNode works at runtime
                    temp_game = Game(ctx, engine, move_tree=move_tree)  # type: ignore[arg-type]
                    # Load analysis data
                    sgf_nodes = list(move_tree.nodes_in_tree)
                    game_nodes = list(temp_game.root.nodes_in_tree)
                    for sgf_node, game_node in zip(sgf_nodes, game_nodes):
                        analysis = extract_analysis_from_sgf_node(sgf_node)
                        if analysis:
                            game_node.analysis = analysis

                snapshot = snapshot_from_game(temp_game)
                pacing_result = analyze_pacing(time_data, list(snapshot.moves))
                stats["pacing_stats"] = extract_pacing_stats_for_summary(pacing_result)
            else:
                stats["pacing_stats"] = {"has_time_data": False}
        except Exception as e:
            logger.debug(f"Time analysis failed for {path}: {e}")
            stats["pacing_stats"] = {"has_time_data": False}

        return stats

    except Exception as e:
        log_fn(f"Failed to extract statistics from {path}: {e}", OUTPUT_ERROR)
        import traceback
        log_fn(traceback.format_exc(), OUTPUT_ERROR)
        return None
