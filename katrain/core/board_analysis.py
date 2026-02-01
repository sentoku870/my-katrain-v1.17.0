"""
board_analysis.py - 盤面戦術分析モジュール (Phase 5)

このモジュールは盤面の戦術的状況を抽出し、理由タグ(reason tags)を生成します。
- グループ(連結成分)の抽出
- 呼吸点カウント
- 連絡点/切断点の検出
- 危険度スコア計算
- 戦術的理由タグの判定

対象ユーザー: 有段者(G3-G4) - カルテ品質向上(LLMコーチング強化)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Tuple, Dict, Optional, Set

if TYPE_CHECKING:
    from katrain.core.game import Game


# ==================== 危険度スコア計算パラメータ ====================
# 呼吸点による基本危険度 (0-100スケール)
DANGER_ATARI = 60           # 1呼吸点（アタリ）
DANGER_LOW_LIBERTY = 35     # 2呼吸点
DANGER_MEDIUM_LIBERTY = 15  # 3呼吸点

# 切断リスクボーナス
DANGER_CUT_BONUS_PER_POINT = 5   # 切断点1つあたりの危険度増加
DANGER_CUT_BONUS_CAP = 20        # 切断ボーナスの上限

# グループサイズボーナス
LARGE_GROUP_THRESHOLD = 10       # 大石と判定する石数
LARGE_GROUP_BONUS = 10           # 大石の危険度ボーナス
MEDIUM_GROUP_THRESHOLD = 6       # 中石と判定する石数
MEDIUM_GROUP_BONUS = 5           # 中石の危険度ボーナス

# ==================== 切断点検出パラメータ ====================
# 危険度係数（切断の影響度計算用）
CUT_COEFFICIENT_HIGH = 0.8       # 高危険度（60以上）のグループ
CUT_COEFFICIENT_MEDIUM = 0.5     # 中危険度（35以上）のグループ
CUT_COEFFICIENT_LOW = 0.3        # 低危険度のグループ
CUT_DANGER_THRESHOLD_HIGH = 60   # 高危険度判定閾値
CUT_DANGER_THRESHOLD_MEDIUM = 35 # 中危険度判定閾値
CUT_MINIMUM_DANGER_INCREASE = 10 # 切断点として認識する最低危険度増加

# ==================== 連絡点検出パラメータ ====================
CONNECT_IMPROVEMENT_RATIO = 0.3  # 連絡による危険度改善率

# ==================== 理由タグ判定パラメータ ====================
TAG_CUT_RISK_DANGER_THRESHOLD = 40       # cut_risk タグの危険度閾値
TAG_NEED_CONNECT_IMPROVEMENT = 20        # need_connect タグの改善値閾値
TAG_THIN_MIN_LIBERTIES = 3               # thin タグの最低呼吸点数
TAG_THIN_MIN_CUT_POINTS = 3              # thin タグの最低切断点数
TAG_CHASE_MODE_ENEMY_DANGER = 60         # chase_mode の敵危険度閾値
TAG_CHASE_MODE_MY_DANGER_MAX = 35        # chase_mode の自分危険度上限
TAG_READING_FAILURE_DANGER = 40          # reading_failure の危険度閾値
ENDGAME_MOVE_THRESHOLD = 150             # この手数以降をヨセと判定

# ==================== 結果件数パラメータ ====================
MAX_CONNECT_POINTS = 10  # 返す連絡点の最大数
MAX_CUT_POINTS = 10      # 返す切断点の最大数


@dataclass
class Group:
    """連結された石グループ

    Attributes:
        group_id: グループID (game.chains のインデックスに対応)
        color: 石の色 ('B' or 'W')
        stones: グループ内の石の座標リスト [(x, y), ...]
        liberties_count: 呼吸点の数
        liberties: 呼吸点の座標セット {(x, y), ...}
        is_in_atari: アタリかどうか (liberties_count == 1)
        is_low_liberty: 呼吸点が少ないか (liberties_count <= 2)
        adjacent_enemy_groups: 隣接する敵グループのIDリスト
    """
    group_id: int
    color: str  # 'B' or 'W'
    stones: List[Tuple[int, int]]  # [(x, y), ...]
    liberties_count: int
    liberties: Set[Tuple[int, int]]
    is_in_atari: bool  # liberties == 1
    is_low_liberty: bool  # liberties <= 2
    adjacent_enemy_groups: List[int]


@dataclass
class BoardState:
    """局面の戦術的スナップショット

    Attributes:
        groups: 盤面上のすべてのグループ
        connect_points: 連絡点のリスト [(座標, [連絡するgroup_ids], 危険度改善値), ...]
        cut_points: 切断点のリスト [(座標, [リスクのあるgroup_ids], 危険度増加値), ...]
        danger_scores: グループごとの危険度スコア {group_id: danger_score}
                      スコアは 0-100 の範囲 (高いほど危険)
    """
    groups: List[Group]
    connect_points: List[Tuple[Tuple[int, int], List[int], float]]
    # [(座標, [連絡するgroup_ids], 危険度改善値), ...]
    cut_points: List[Tuple[Tuple[int, int], List[int], float]]
    # [(座標, [リスクのあるgroup_ids], 危険度増加値), ...]
    danger_scores: Dict[int, float]  # {group_id: danger_score}


# ==================== Checkpoint 2: グループ抽出 ====================

def extract_groups_from_game(game: Game) -> List[Group]:
    """game.chainsから戦術的グループデータを抽出

    Args:
        game: Game インスタンス

    Returns:
        List[Group]: 盤面上のすべてのグループ（空でないもののみ）
    """
    groups = []
    board = game.board
    chains = game.chains
    board_size_x, board_size_y = game.board_size

    for group_id, chain in enumerate(chains):
        if not chain:  # 空のチェーン（取られた石）
            continue

        color = chain[0].player
        stones = [m.coords for m in chain if m.coords is not None]

        # 呼吸点をカウント
        liberties: set[tuple[int, int]] = set()
        for stone in stones:
            x, y = stone
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < board_size_x and 0 <= ny < board_size_y:
                    if board[ny][nx] == -1:  # 空点
                        liberties.add((nx, ny))

        liberties_count = len(liberties)
        is_in_atari = (liberties_count == 1)
        is_low_liberty = (liberties_count <= 2)

        # 隣接する敵グループを検出
        adjacent_enemy_groups = set()
        for stone in stones:
            x, y = stone
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < board_size_x and 0 <= ny < board_size_y:
                    neighbor_id = board[ny][nx]
                    if neighbor_id >= 0 and neighbor_id < len(chains) and chains[neighbor_id]:
                        if chains[neighbor_id][0].player != color:
                            adjacent_enemy_groups.add(neighbor_id)

        groups.append(Group(
            group_id=group_id,
            color=color,
            stones=stones,
            liberties_count=liberties_count,
            liberties=liberties,
            is_in_atari=is_in_atari,
            is_low_liberty=is_low_liberty,
            adjacent_enemy_groups=list(adjacent_enemy_groups)
        ))

    return groups


# ==================== Checkpoint 3: 危険度スコア計算 ====================

def compute_danger_scores(groups: List[Group], cut_points: List[Tuple[Tuple[int, int], List[int], float]]) -> Dict[int, float]:
    """各グループの危険度スコアを計算

    Args:
        groups: グループのリスト
        cut_points: 切断点のリスト（危険度計算に使用）

    Returns:
        Dict[int, float]: {group_id: danger_score} (0-100の範囲)
    """
    danger_scores = {}

    for group in groups:
        danger = 0.0

        # 呼吸点による基本危険度
        if group.liberties_count == 1:
            danger += DANGER_ATARI
        elif group.liberties_count == 2:
            danger += DANGER_LOW_LIBERTY
        elif group.liberties_count == 3:
            danger += DANGER_MEDIUM_LIBERTY

        # 切断リスクボーナス（近くの切断点をカウント）
        nearby_cuts = sum(
            1 for coords, group_ids, _ in cut_points
            if group.group_id in group_ids
        )
        danger += min(DANGER_CUT_BONUS_CAP, nearby_cuts * DANGER_CUT_BONUS_PER_POINT)

        # サイズボーナス
        if len(group.stones) >= LARGE_GROUP_THRESHOLD:
            danger += LARGE_GROUP_BONUS
        elif len(group.stones) >= MEDIUM_GROUP_THRESHOLD:
            danger += MEDIUM_GROUP_BONUS

        danger_scores[group.group_id] = danger

    return danger_scores


# ==================== Checkpoint 4: 連絡点/切断点検出 ====================

def find_connect_points(
    game: Game,
    groups: List[Group],
    danger_scores: Dict[int, float]
) -> List[Tuple[Tuple[int, int], List[int], float]]:
    """2つ以上の味方グループを連絡する点を検出

    Args:
        game: Game インスタンス
        groups: グループのリスト
        danger_scores: 危険度スコア辞書

    Returns:
        List[Tuple[Tuple[int, int], List[int], float]]:
        [(座標, [連絡するgroup_ids], 危険度改善値), ...] を改善度上位10件
    """
    board = game.board
    board_size_x, board_size_y = game.board_size
    connect_points = []

    # O(1) lookup index for groups by group_id
    group_index = {g.group_id: g for g in groups}

    for y in range(board_size_y):
        for x in range(board_size_x):
            if board[y][x] != -1:  # 空でない
                continue

            # 隣接グループを検出
            adjacent_groups: dict[str, list[int]] = {}  # {color: [group_ids]}
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < board_size_x and 0 <= ny < board_size_y:
                    neighbor_id = board[ny][nx]
                    if neighbor_id >= 0:
                        group = group_index.get(neighbor_id)
                        if group:
                            adjacent_groups.setdefault(group.color, []).append(neighbor_id)

            # この点が同色の2つ以上のグループを連絡するか
            for color, group_ids in adjacent_groups.items():
                unique_groups = list(set(group_ids))
                if len(unique_groups) >= 2:
                    # 危険度改善を計算
                    before_danger = sum(danger_scores.get(gid, 0) for gid in unique_groups)
                    improvement = before_danger * CONNECT_IMPROVEMENT_RATIO
                    connect_points.append(((x, y), unique_groups, improvement))

    # 改善度上位を返す
    connect_points.sort(key=lambda cp: cp[2], reverse=True)
    return connect_points[:MAX_CONNECT_POINTS]


def find_cut_points(
    game: Game,
    groups: List[Group],
    danger_scores: Dict[int, float]
) -> List[Tuple[Tuple[int, int], List[int], float]]:
    """切断点を検出（v0簡易版: ヒューリスティック）

    Args:
        game: Game インスタンス
        groups: グループのリスト
        danger_scores: 危険度スコア辞書

    Returns:
        List[Tuple[Tuple[int, int], List[int], float]]:
        [(座標, [リスクのあるgroup_ids], 危険度増加値), ...] を危険度上位10件
    """
    board = game.board
    board_size_x, board_size_y = game.board_size
    cut_points = []

    # O(1) lookup index for groups by group_id
    group_index = {g.group_id: g for g in groups}

    for y in range(board_size_y):
        for x in range(board_size_x):
            if board[y][x] != -1:  # 空でない
                continue

            # 隣接グループを色ごとに検出
            adjacent_groups: dict[str, list[int]] = {}  # {color: [group_ids]}
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < board_size_x and 0 <= ny < board_size_y:
                    neighbor_id = board[ny][nx]
                    if neighbor_id >= 0:
                        group = group_index.get(neighbor_id)
                        if group:
                            adjacent_groups.setdefault(group.color, []).append(neighbor_id)

            # 各色について、2つ以上のグループが隣接していれば切断候補
            for color, group_ids in adjacent_groups.items():
                unique_groups = list(set(group_ids))
                if len(unique_groups) >= 2:
                    # 危険度増加を計算
                    # ヒューリスティック: 既に危険なグループほど切断リスクが高い
                    current_danger = sum(danger_scores.get(gid, 0) for gid in unique_groups)

                    # 係数: 既に危険度が高いほど切断の影響大
                    if current_danger >= CUT_DANGER_THRESHOLD_HIGH:
                        coefficient = CUT_COEFFICIENT_HIGH
                    elif current_danger >= CUT_DANGER_THRESHOLD_MEDIUM:
                        coefficient = CUT_COEFFICIENT_MEDIUM
                    else:
                        coefficient = CUT_COEFFICIENT_LOW

                    danger_increase = current_danger * coefficient

                    # 最低閾値: 危険度増加が一定以上の場合のみ切断点として認識
                    if danger_increase >= CUT_MINIMUM_DANGER_INCREASE:
                        cut_points.append(((x, y), unique_groups, danger_increase))

    # 危険度上位を返す
    cut_points.sort(key=lambda cp: cp[2], reverse=True)
    return cut_points[:MAX_CUT_POINTS]


# ==================== Checkpoint 5: メインエントリポイント ====================

def analyze_board_at_node(game: Game, node: Any) -> BoardState:
    """特定ノードでの盤面戦術状態を分析

    Args:
        game: Game インスタンス
        node: GameNode（分析対象の局面）

    Returns:
        BoardState: 戦術的スナップショット
    """
    # ゲームポジションをこのノードに設定
    # （注: コストが高い、将来キャッシュを検討）
    game.set_current_node(node)

    # 現在の盤面状態からグループを抽出
    groups = extract_groups_from_game(game)

    # 連絡点/切断点を検出（切断点は空リスト）
    connect_points = find_connect_points(game, groups, {})
    cut_points = find_cut_points(game, groups, {})

    # 危険度スコアを計算（cut_pointsが必要）
    danger_scores = compute_danger_scores(groups, cut_points)

    # 適切な危険度スコアで連絡点を再計算
    connect_points = find_connect_points(game, groups, danger_scores)

    return BoardState(
        groups=groups,
        connect_points=connect_points,
        cut_points=cut_points,
        danger_scores=danger_scores
    )


# ==================== Checkpoint 6: 理由タグ判定関数 ====================

def get_reason_tags_for_move(
    board_state: BoardState,
    move_eval: Any,  # MoveEval インスタンス
    node: Any,  # GameNode
    candidates: List[dict[str, Any]],
    skill_preset: str = "standard"  # Phase 17: プリセット別閾値
) -> List[str]:
    """盤面状態に基づいて理由タグを計算

    Args:
        board_state: BoardState（盤面の戦術的スナップショット）
        move_eval: MoveEval インスタンス
        node: GameNode
        candidates: 候補手のリスト
        skill_preset: スキルプリセット（"beginner" / "standard" / "advanced"）

    Returns:
        List[str]: 理由タグのリスト（例: ["atari", "low_liberties", ...]）
    """
    tags: list[str] = []

    player = move_eval.player
    if not player:
        return tags

    my_groups = [g for g in board_state.groups if g.color == player]
    enemy_groups = [g for g in board_state.groups if g.color != player]

    if not my_groups:
        return tags

    # 最大危険度
    max_my_danger = max(
        (board_state.danger_scores.get(g.group_id, 0) for g in my_groups),
        default=0
    )
    max_enemy_danger = max(
        (board_state.danger_scores.get(g.group_id, 0) for g in enemy_groups),
        default=0
    )

    # タグ 1: atari（打った手の周辺3マス以内のアタリのみ検出）
    move_coord = node.move.coords if node.move else None
    has_atari = False
    if move_coord:
        nearby_atari_groups = [
            g for g in my_groups
            if g.is_in_atari and any(
                abs(stone[0] - move_coord[0]) <= 3 and abs(stone[1] - move_coord[1]) <= 3
                for stone in g.stones
            )
        ]
        if nearby_atari_groups:
            tags.append("atari")
            has_atari = True

    # タグ 2: low_liberties（atari と併存可能に変更）
    if not has_atari and any(g.is_low_liberty for g in my_groups):
        tags.append("low_liberties")

    # タグ 3: cut_risk
    if len(board_state.cut_points) >= 1 and max_my_danger >= TAG_CUT_RISK_DANGER_THRESHOLD:
        tags.append("cut_risk")

    # タグ 4: need_connect
    if board_state.connect_points:
        best_improvement = board_state.connect_points[0][2]
        if best_improvement >= TAG_NEED_CONNECT_IMPROVEMENT:
            tags.append("need_connect")

    # タグ 5: thin
    max_liberties = max((g.liberties_count for g in my_groups), default=0)
    if max_liberties >= TAG_THIN_MIN_LIBERTIES and len(board_state.cut_points) >= TAG_THIN_MIN_CUT_POINTS:
        tags.append("thin")

    # タグ 6: chase_mode
    if max_enemy_danger >= TAG_CHASE_MODE_ENEMY_DANGER and max_my_danger < TAG_CHASE_MODE_MY_DANGER_MAX:
        tags.append("chase_mode")

    # タグ 7: too_many_choices（無効化 - 候補手数は探索パラメータに依存し不安定）
    # 理由: wideRootNoise等の影響で同じ局面でも変動する
    # LLMはpoints_lostやimportanceから「正解が難しい状況」を推測可能
    # if len(candidates) >= 10:
    #     tags.append("too_many_choices")

    # タグ 8: endgame_hint（条件緩和: yoseタグまたは後半70%以降）
    is_endgame = False
    if hasattr(move_eval, 'tag') and move_eval.tag == "yose":
        is_endgame = True
    elif hasattr(move_eval, 'move_number'):
        if move_eval.move_number > ENDGAME_MOVE_THRESHOLD:
            is_endgame = True

    if is_endgame:
        tags.append("endgame_hint")

    # タグ 9: heavy_loss（大損失: プリセット別閾値 - Phase 17, Option 0-B 一元化）
    # 閾値は eval_metrics.SKILL_PRESETS から取得
    if hasattr(move_eval, 'points_lost') and move_eval.points_lost is not None:
        from katrain.core import eval_metrics
        preset = eval_metrics.get_skill_preset(skill_preset)
        if move_eval.points_lost >= preset.reason_tag_thresholds.heavy_loss:
            tags.append("heavy_loss")

    # タグ 10: reading_failure（読み抜け: プリセット別閾値 - Phase 17, Option 0-B 一元化）
    # 閾値は eval_metrics.SKILL_PRESETS から取得
    # 注: 急場見逃しパターン全体の検出は __main__.py で実施済み
    # ここでは簡易版として、大損失 + 危険度高い場合を検出
    if hasattr(move_eval, 'points_lost') and move_eval.points_lost is not None:
        from katrain.core import eval_metrics
        preset = eval_metrics.get_skill_preset(skill_preset)
        if move_eval.points_lost >= preset.reason_tag_thresholds.reading_failure and max_my_danger >= TAG_READING_FAILURE_DANGER:
            tags.append("reading_failure")

    return tags
