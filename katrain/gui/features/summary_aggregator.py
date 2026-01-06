# katrain/gui/features/summary_aggregator.py
#
# サマリ集計ロジックモジュール
#
# __main__.py から抽出したサマリ集計関連のPure関数を配置します。
# - scan_player_names: SGFファイルからプレイヤー名をスキャン
# - categorize_games_by_stats: 統計データから対局を分類
# - collect_rank_info: focus_playerの段級位情報を収集

from collections import Counter
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from katrain.core.game import KaTrainSGF

if TYPE_CHECKING:
    pass


def scan_player_names(
    sgf_files: List[str],
    log_fn: Callable[[str, int], None],
) -> Dict[str, int]:
    """SGFファイルから全プレイヤー名をスキャン（出現回数付き）

    Args:
        sgf_files: SGFファイルパスのリスト
        log_fn: ログ出力関数（message, level）

    Returns:
        {player_name: count} の辞書
    """
    from katrain.core.constants import OUTPUT_ERROR

    player_counts: Dict[str, int] = {}

    for path in sgf_files:
        try:
            move_tree = KaTrainSGF.parse_file(path)
            player_black = move_tree.get_property("PB", "").strip()
            player_white = move_tree.get_property("PW", "").strip()

            # 空でないプレイヤー名をカウント
            if player_black:
                player_counts[player_black] = player_counts.get(player_black, 0) + 1
            if player_white:
                player_counts[player_white] = player_counts.get(player_white, 0) + 1

        except Exception as e:
            log_fn(f"Failed to scan {path}: {e}", OUTPUT_ERROR)

    return player_counts


def categorize_games_by_stats(
    game_stats_list: List[dict],
    focus_player: Optional[str],
) -> Dict[str, List[dict]]:
    """統計データから対局を分類（互先/置碁）

    Args:
        game_stats_list: 統計データ辞書のリスト
        focus_player: 対象プレイヤー名（Noneの場合は全ゲーム）

    Returns:
        {
            "even": [...],        # 互先
            "handi_weak": [...],  # 置碁（下手・黒）
            "handi_strong": [...] # 置碁（上手・白）
        }
    """
    categories: Dict[str, List[dict]] = {
        "even": [],          # 互先
        "handi_weak": [],    # 置碁（下手・黒）
        "handi_strong": [],  # 置碁（上手・白）
    }

    for stats in game_stats_list:
        handicap = stats["handicap"]

        # focus_playerが設定されている場合のみフィルタリング
        if focus_player:
            is_black = (stats["player_black"] == focus_player)
            is_white = (stats["player_white"] == focus_player)

            # focus_playerが対局者でない場合はスキップ
            if not is_black and not is_white:
                continue

            # 分類
            if handicap == 0:
                # 互先（黒白統合）
                categories["even"].append(stats)
            elif handicap >= 2:
                # 置碁
                if is_black:
                    categories["handi_weak"].append(stats)  # 下手（黒）
                else:
                    categories["handi_strong"].append(stats)  # 上手（白）
        else:
            # focus_playerが未設定の場合は全ゲームを分類
            if handicap == 0:
                categories["even"].append(stats)
            elif handicap >= 2:
                # ハンデ戦は黒が下手、白が上手
                # 両方のプレイヤーのゲームを適切なカテゴリに入れる
                # （後でfocus_playerなしでレポート生成するため）
                categories["handi_weak"].append(stats)
                # 注: focus_playerなしの場合、上手/下手を分けるのは困難なため、
                # 下手（黒）のみを集計する

    return categories


def collect_rank_info(
    stats_list: List[dict],
    focus_player: Optional[str],
) -> Optional[str]:
    """focus_player の段級位情報を収集（Phase 10-C）

    Args:
        stats_list: 統計dictのリスト
        focus_player: 対象プレイヤー名

    Returns:
        str: 段級位文字列（例: "5段", "8級"）、見つからない場合は None
    """
    if not focus_player:
        return None

    # 全ゲームから focus_player の段級位を探す
    ranks: List[str] = []
    for stats in stats_list:
        if stats["player_black"] == focus_player and stats.get("rank_black"):
            ranks.append(stats["rank_black"])
        elif stats["player_white"] == focus_player and stats.get("rank_white"):
            ranks.append(stats["rank_white"])

    # 最も頻出する段級位を返す（複数ある場合は最初のもの）
    if ranks:
        most_common = Counter(ranks).most_common(1)[0][0]
        return most_common

    return None
