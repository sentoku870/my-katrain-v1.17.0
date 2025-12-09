from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    List,
    Optional,
    Tuple,
)

# KaTrain 側の型に依存するのは最小限にする
#   - 型チェック時だけ GameNode を正しく import
#   - ランタイムでは Any として扱う
if TYPE_CHECKING:
    from katrain.core.game_node import GameNode
else:
    GameNode = Any


# ---------------------------------------------------------------------------
# 基本データ構造
# ---------------------------------------------------------------------------


@dataclass
class MoveEval:
    """
    1 手分の評価情報を表す最小単位。

    Phase 1 時点では、score / winrate の視点（黒番視点か手番視点か）は
    KaTrain 側の GameNode に格納されている値に合わせている。
    あとから変換レイヤーを挟めるよう、before/after/delta を分けて持つ。
    """

    move_number: int                    # 手数（1, 2, 3, ...）
    player: Optional[str]               # 'B' / 'W' / None（ルートなど）
    gtp: Optional[str]                  # "D4" のような座標 or "pass" / None

    # 評価値（視点は GameNode.score / winrate に合わせる）
    score_before: Optional[float]       # この手を打つ前の評価
    score_after: Optional[float]        # この手を打った直後の評価
    delta_score: Optional[float]        # score_after - score_before

    winrate_before: Optional[float]     # この手を打つ前の勝率
    winrate_after: Optional[float]      # この手を打った直後の勝率
    delta_winrate: Optional[float]      # winrate_after - winrate_before

    # KaTrain 標準の指標
    points_lost: Optional[float]        # その手で失った期待値（points_lost）
    realized_points_lost: Optional[float]  # 実際の進行で確定した損失
    root_visits: int                    # その局面の root 訪問回数（見ている深さの目安）

    # 将来の拡張用メタ情報
    tag: Optional[str] = None           # "opening"/"middle"/"yose" など自由タグ
    importance_score: Optional[float] = None  # 後で計算する「重要度スコア」


# ---------------------------------------------------------------------------
# 重要局面検出用の設定
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImportantMoveSettings:
    """重要局面の抽出条件をまとめた設定."""
    importance_threshold: float  # importance がこの値を超えたものだけ採用
    max_moves: int               # 最大件数（大きい順に上位だけ残す）


# 棋力イメージ別プリセット（あとで UI から切り替えやすくするための土台）
IMPORTANT_MOVE_SETTINGS_BY_LEVEL = {
    # 級位者向け: 本当に大きな損だけを拾う
    "easy": ImportantMoveSettings(
        importance_threshold=1.0,
        max_moves=10,
    ),
    # 標準: 現在の挙動に近い設定
    "normal": ImportantMoveSettings(
        importance_threshold=0.5,
        max_moves=20,
    ),
    # 段位者向け: 細かいヨセも含めて多めに拾う
    "strict": ImportantMoveSettings(
        importance_threshold=0.3,
        max_moves=40,
    ),
}

DEFAULT_IMPORTANT_MOVE_LEVEL = "normal"


# ---------------------------------------------------------------------------

@dataclass
class EvalSnapshot:
    """
    ある時点での「ゲーム全体の評価一覧」をまとめたスナップショット。
    """

    moves: List[MoveEval] = field(default_factory=list)

    @property
    def total_points_lost(self) -> float:
        return float(
            sum(m.points_lost for m in self.moves if m.points_lost is not None)
        )

    @property
    def max_points_lost(self) -> float:
        vals = [m.points_lost for m in self.moves if m.points_lost is not None]
        return float(max(vals)) if vals else 0.0

    @property
    def worst_move(self) -> Optional[MoveEval]:
        candidates = [m for m in self.moves if m.points_lost is not None]
        if not candidates:
            return None
        return max(candidates, key=lambda m: m.points_lost or 0.0)

    def filtered(self, predicate: Callable[[MoveEval], bool]) -> "EvalSnapshot":
        return EvalSnapshot(moves=[m for m in self.moves if predicate(m)])

    def by_player(self, player: str) -> "EvalSnapshot":
        return self.filtered(lambda m: m.player == player)

    def first_n_moves(self, n: int) -> "EvalSnapshot":
        return EvalSnapshot(moves=self.moves[:n])

    def last_n_moves(self, n: int) -> "EvalSnapshot":
        if n <= 0:
            return EvalSnapshot()
        return EvalSnapshot(moves=self.moves[-n:])

# ---------------------------------------------------------------------------
# KaTrain GameNode とのブリッジ
# ---------------------------------------------------------------------------


def move_eval_from_node(node: GameNode) -> MoveEval:
    """
    KaTrain の GameNode 1 個から MoveEval を生成する。

    - GameNode.comment() 等の文字列には依存せず、
      数値的な評価値だけを見るようにする。
    - before/after/delta は snapshot_from_nodes 側で埋める。
    """
    move = getattr(node, "move", None)
    player = getattr(move, "player", None)
    gtp = move.gtp() if move is not None and hasattr(move, "gtp") else None

    score = getattr(node, "score", None)
    winrate = getattr(node, "winrate", None)
    points_lost = getattr(node, "points_lost", None)
    realized_points_lost = getattr(node, "parent_realized_points_lost", None)
    root_visits = getattr(node, "root_visits", 0) or 0

    return MoveEval(
        move_number=getattr(node, "move_number", 0) or getattr(node, "depth", 0),
        player=player,
        gtp=gtp,
        score_before=None,
        score_after=score,
        delta_score=None,
        winrate_before=None,
        winrate_after=winrate,
        delta_winrate=None,
        points_lost=points_lost,
        realized_points_lost=realized_points_lost,
        root_visits=int(root_visits),
    )



def snapshot_from_nodes(nodes: Iterable[GameNode]) -> EvalSnapshot:
    """
    任意の GameNode 群から EvalSnapshot を作成するユーティリティ。

    - nodes には「実際に打たれた手を持つノード」（move が None でない）を渡す想定。
    - score / winrate の before/after/delta は、この関数内で連鎖的に計算する。
    """
    move_evals: List[MoveEval] = []

    for node in nodes:
        if getattr(node, "move", None) is None:
            continue
        move_evals.append(move_eval_from_node(node))

    # 手数順に並べる
    move_evals.sort(key=lambda m: m.move_number)

    # 連続する手から before / delta を埋める
    prev: Optional[MoveEval] = None
    for m in move_evals:
        if prev is not None:
            m.score_before = prev.score_after
            m.winrate_before = prev.winrate_after

            if m.score_before is not None and m.score_after is not None:
                m.delta_score = m.score_after - m.score_before
            else:
                m.delta_score = None

            if m.winrate_before is not None and m.winrate_after is not None:
                m.delta_winrate = m.winrate_after - m.winrate_before
            else:
                m.delta_winrate = None

        prev = m

    return EvalSnapshot(moves=move_evals)


# ここから下を eval_metrics.py の末尾に追加

def iter_main_branch_nodes(game: Any) -> Iterable[GameNode]:
    """
    KaTrain の Game インスタンスから、
    ルートからメイン分岐（main branch）と思われるノード列を順に返す。

    - root は通常「着手無しノード」なので、move を持つノードのみ yield する。
    - メイン分岐の判定は暫定:
        1) children のうち is_mainline==True のものがあればそれを優先
        2) それがなければ is_main==True を持つものを優先
        3) それもなければ children[0] をメインとみなす
    """
    root = getattr(game, "root", None)
    if root is None:
        return  # 何も yield しないジェネレータ

    node = root

    while True:
        # 実際に打たれた手を持つノードだけを対象にする
        if getattr(node, "move", None) is not None:
            yield node  # type: ignore[misc]

        children = getattr(node, "children", None)
        if not children:
            break

        # 1. is_mainline 優先
        main_children = [
            c for c in children if getattr(c, "is_mainline", False)
        ]
        # 2. 無ければ is_main
        if not main_children:
            main_children = [
                c for c in children if getattr(c, "is_main", False)
            ]

        # 3. それでも空なら、先頭 child をメイン扱い（暫定ルール）
        next_node = main_children[0] if main_children else children[0]
        node = next_node


def snapshot_from_game(game: Any) -> EvalSnapshot:
    """
    Game 全体（メイン分岐）から EvalSnapshot を生成するヘルパー。

    - Phase 1 では UI からは直接呼ばず、
      内部ロジックやデバッグ用途のエントリポイントとして使う想定。
    """
    nodes_iter = iter_main_branch_nodes(game)
    return snapshot_from_nodes(nodes_iter)

def compute_importance_for_moves(
    moves: Iterable[MoveEval],
    *,
    weight_delta_score: float = 1.0,
    weight_delta_winrate: float = 50.0,
    weight_points_lost: float = 1.0,
) -> None:
    """
    各 MoveEval について、delta_score / delta_winrate / points_lost から
    簡易な「重要度スコア」を計算し、importance_score に格納する。

    重みの意味（ざっくり）:
        - weight_delta_score : 形勢の点数変化（目）をどれだけ重く見るか
        - weight_delta_winrate : 勝率 1.0 の変化を「何目分」とみなすか
        - weight_points_lost : points_lost をどれだけ重く見るか
    """
    for m in moves:
        score_term = (
            weight_delta_score * abs(m.delta_score)
            if m.delta_score is not None
            else 0.0
        )
        winrate_term = (
            weight_delta_winrate * abs(m.delta_winrate)
            if m.delta_winrate is not None
            else 0.0
        )
        pl_term = (
            weight_points_lost * max(m.points_lost or 0.0, 0.0)
            if m.points_lost is not None
            else 0.0
        )

        m.importance_score = score_term + winrate_term + pl_term


def pick_important_moves(
    snapshot: EvalSnapshot,
    level: str = DEFAULT_IMPORTANT_MOVE_LEVEL,
    settings: Optional[ImportantMoveSettings] = None,
    recompute: bool = True,
    weight_delta_score: float = 1.0,
    weight_delta_winrate: float = 50.0,
    weight_points_lost: float = 1.0,
) -> List[MoveEval]:
    """
    snapshot から重要局面の手数だけを抽出して返す。

    Args:
        snapshot: 解析済みの EvalSnapshot
        level:
            "easy" / "normal" / "strict" のような棋力イメージを表すキー。
            settings が None の場合に使用される（デフォルト "normal"）。
        settings:
            直接設定を渡したい場合用。通常は None のままでよい。
        recompute: importance_score を再計算するかどうか
        weight_delta_score: delta_score の重み
        weight_delta_winrate: delta_winrate の重み
        weight_points_lost: points_lost の重み

    Returns:
        MoveEval オブジェクトのリスト（手数順）。
    """
    # 設定の決定
    if settings is None:
        settings = IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
            level, IMPORTANT_MOVE_SETTINGS_BY_LEVEL[DEFAULT_IMPORTANT_MOVE_LEVEL]
        )

    threshold = settings.importance_threshold
    max_moves = settings.max_moves

    moves = snapshot.moves
    if not moves:
        # そもそも解析済みの手がない場合は何も返さない
        return []

    # 必要なら importance_score を再計算
    if recompute:
        compute_importance_for_moves(
            moves,
            weight_delta_score=weight_delta_score,
            weight_delta_winrate=weight_delta_winrate,
            weight_points_lost=weight_points_lost,
        )

    # 1) 通常ルート: importance_score ベース
    candidates: List[Tuple[float, MoveEval]] = []
    for move in moves:
        importance = move.importance_score or 0.0
        if importance > threshold:
            candidates.append((importance, move))

    # 2) フォールバック:
    #    1) で 1 手も選ばれなかったときだけ、
    #    「評価変化＋points_lost」が大きい順で上位を取る。
    if not candidates:
        def raw_score(m: MoveEval) -> float:
            score_term = abs(m.delta_score or 0.0)
            winrate_term = 50.0 * abs(m.delta_winrate or 0.0)
            pl_term = max(m.points_lost or 0.0, 0.0)
            return score_term + winrate_term + pl_term

        for move in moves:
            raw_sc = raw_score(move)
            if raw_sc > 0.0:
                candidates.append((raw_sc, move))

    # importance の大きい順に並べ替えて上位だけ残す
    candidates.sort(key=lambda x: x[0], reverse=True)
    top = candidates[:max_moves]
    
    # その後手数順にソート
    important_moves = sorted([m for _, m in top], key=lambda m: m.move_number)
    return important_moves

