"""katrain.core.analysis.models.move_eval - MoveEval and EvalSnapshot data classes.

Phase 144-B: Extracted from models.py (1230 lines → 6 focused modules).

Contains:
- MoveEval: Per-move evaluation snapshot (dataclass)
- EvalSnapshot: Game-wide evaluation snapshot (dataclass with derived properties)
- get_canonical_loss_from_move: Helper to extract canonical loss from a MoveEval
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from katrain.core.analysis.models.enums import MistakeCategory, PositionDifficulty

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode
else:
    GameNode = Any


# =============================================================================
# MoveEval
# =============================================================================


@dataclass
class MoveEval:
    """
    1 手分の評価情報を表す最小単位。

    Perspective (視点):
    - score_*, winrate_*, delta_*: BLACK-PERSPECTIVE (黒視点)
      - 正の値 = 黒有利 / 黒の方向に変化
    - points_lost: SIDE-TO-MOVE (手番視点)
      - 正の値 = その手を打ったプレイヤーにとっての損失

    損失計算には compute_canonical_loss() を使用すること。
    delta_score/delta_winrate を直接損失として使わないこと。
    """

    move_number: int  # 手数（1, 2, 3, ...）
    player: str | None  # 'B' / 'W' / None（ルートなど）
    gtp: str | None  # "D4" のような座標 or "pass" / None

    # 評価値（BLACK-PERSPECTIVE: 正=黒有利）
    score_before: float | None  # この手を打つ前の評価
    score_after: float | None  # この手を打った直後の評価
    delta_score: float | None  # score_after - score_before (黒視点)

    winrate_before: float | None  # この手を打つ前の勝率
    winrate_after: float | None  # この手を打った直後の勝率
    delta_winrate: float | None  # winrate_after - winrate_before (黒視点)

    # KaTrain 標準の指標（SIDE-TO-MOVE: 手番視点）
    points_lost: float | None  # その手で失った期待値（手番視点、正=損失）
    realized_points_lost: float | None  # 実際の進行で確定した損失
    root_visits: int  # その局面の root 訪問回数（見ている深さの目安）
    is_reliable: bool = False  # visits を根拠にした信頼度フラグ（保守的に False）

    # 将来の拡張用メタ情報
    tag: str | None = None  # "opening"/"middle"/"yose" など自由タグ
    importance_score: float | None = None  # 後で計算する「重要度スコア」

    score_loss: float | None = None
    """その手による地合損失（悪くなった分だけ、目単位）。"""

    winrate_loss: float | None = None
    """その手による勝率損失（悪くなった分だけ、0〜1）。"""

    mistake_category: MistakeCategory = MistakeCategory.GOOD
    """ミス分類（GOOD / INACCURACY / MISTAKE / BLUNDER）。"""

    position_difficulty: PositionDifficulty | None = None
    """局面難易度（EASY / NORMAL / HARD / ONLY_MOVE / UNKNOWN など）。"""

    position_difficulty_score: float | None = None
    """局面難易度を 0.0〜1.0 の連続値で表した補助スコア（大きいほど難しい想定）。"""

    reason_tags: list[str] = field(default_factory=list)
    """戦術的コンテキストの理由タグ（Phase 5: 構造の言語化）。

    例: ["atari", "low_liberties", "need_connect", "chase_mode", ...]
    盤面の戦術的状況に基づいて board_analysis モジュールで計算される。
    """

    leela_loss_est: float | None = None
    """Leela Zero による推定損失（0以上、Noneは非Leela解析）。

    Note:
    - score_loss（目単位）とは異なるセマンティクス
    - K係数でスケール変換済み（デフォルト K=0.5）
    - 0.0 = 最善手、正の値 = 損失
    - 最大値: LEELA_LOSS_EST_MAX（50.0）
    """

    score_stdev: float | None = None
    """KataGo root の scoreStdev（手数終盤判定の指標、Phase 156）。

    Note:
    - None: Leela経路 / 未解析の手
    - 値が小さい = 形勢が読み切れている（終盤の特徴）
    - Phase 156-A: classify_game_phase_dynamic() が使用
    """

    meaning_tag_id: str | None = None
    """意味タグID（Phase 47: Meaning Tags Integration）。

    classify_meaning_tag() で分類された結果のID文字列。
    例: "overplay", "missed_tesuji", "life_death_error", "uncertain"

    Note:
    - str型（循環インポート回避のため MeaningTagId enum は使わない）
    - None = 未分類（classify未呼び出し or 分類不能）
    - MeaningTagId enum の .value と一致する
    """


# =============================================================================
# Canonical loss helper
# =============================================================================


def get_canonical_loss_from_move(m: MoveEval) -> float:
    """
    MoveEval から正準損失 (canonical loss) を取得する。

    優先順位:
      1) score_loss が設定されていればそれを使用（KataGo）
      2) leela_loss_est が設定されていればそれを使用（Leela）
      3) points_lost があれば使用
      4) どちらもなければ 0.0

    Returns:
        float: 常に >= 0 の損失値（負の値は 0 にクランプ）

    Note:
        - Phase 32 で leela_loss_est を追加
        - データ層で一貫してクランプすることで、
          将来の他UI/エクスポートでも安全に利用可能。
    """
    if m.score_loss is not None:
        return max(0.0, m.score_loss)
    if m.leela_loss_est is not None:
        return max(0.0, m.leela_loss_est)
    if m.points_lost is not None:
        return max(0.0, m.points_lost)
    return 0.0


# =============================================================================
# EvalSnapshot
# =============================================================================


@dataclass
class EvalSnapshot:
    """
    ある時点での「ゲーム全体の評価一覧」をまとめたスナップショット。

    プロパティについて:
    - total_points_lost: 生の points_lost 合計（負の値を含む、後方互換）
    - total_canonical_points_lost: score_loss 合計（>=0 のみ、推奨）
    - max_points_lost: 生の points_lost 最大値（後方互換）
    - max_canonical_points_lost: score_loss 最大値（推奨）
    - worst_move: points_lost 最大の手（後方互換）
    - worst_canonical_move: score_loss 最大の手（推奨）
    """

    moves: list[MoveEval] = field(default_factory=list)

    # -------------------------------------------------------------------------
    # Legacy properties (backward compatibility, may include negative values)
    # -------------------------------------------------------------------------

    @property
    def total_points_lost(self) -> float:
        """生の points_lost 合計（負の値を含む可能性あり）。後方互換用。"""
        return float(sum(m.points_lost for m in self.moves if m.points_lost is not None))

    @property
    def max_points_lost(self) -> float:
        """生の points_lost 最大値。後方互換用。"""
        vals = [m.points_lost for m in self.moves if m.points_lost is not None]
        return float(max(vals)) if vals else 0.0

    @property
    def worst_move(self) -> MoveEval | None:
        """points_lost 最大の手を返す。後方互換用。"""
        candidates = [m for m in self.moves if m.points_lost is not None]
        if not candidates:
            return None
        return max(candidates, key=lambda m: m.points_lost or 0.0)

    # -------------------------------------------------------------------------
    # Canonical properties (always >= 0, recommended for loss calculations)
    # -------------------------------------------------------------------------

    @property
    def total_canonical_points_lost(self) -> float:
        """
        score_loss (正準損失) の合計。常に >= 0。

        score_loss が設定されていない場合は max(points_lost, 0) を使用。
        """
        total = 0.0
        for m in self.moves:
            if m.score_loss is not None:
                total += m.score_loss
            elif m.points_lost is not None:
                total += max(0.0, m.points_lost)
        return total

    @property
    def max_canonical_points_lost(self) -> float:
        """score_loss (正準損失) の最大値。"""
        vals = []
        for m in self.moves:
            if m.score_loss is not None:
                vals.append(m.score_loss)
            elif m.points_lost is not None:
                vals.append(max(0.0, m.points_lost))
        return float(max(vals)) if vals else 0.0

    @property
    def worst_canonical_move(self) -> MoveEval | None:
        """score_loss 最大の手を返す。"""
        candidates = [m for m in self.moves if get_canonical_loss_from_move(m) > 0.0]
        if not candidates:
            # 全て良い手の場合は最初の手を返す（または None）
            return self.moves[0] if self.moves else None
        return max(candidates, key=get_canonical_loss_from_move)

    # -------------------------------------------------------------------------
    # Freedom / Position Difficulty statistics
    # -------------------------------------------------------------------------

    @property
    def difficulty_unknown_count(self) -> int:
        """position_difficulty が UNKNOWN の手の数。"""
        return sum(
            1
            for m in self.moves
            if m.position_difficulty is None or m.position_difficulty == PositionDifficulty.UNKNOWN
        )

    @property
    def difficulty_unknown_rate(self) -> float:
        """position_difficulty が UNKNOWN の手の割合 (0.0-1.0)。"""
        if not self.moves:
            return 0.0
        return self.difficulty_unknown_count / len(self.moves)

    @property
    def difficulty_distribution(self) -> dict[PositionDifficulty, int]:
        """局面難易度の分布を返す。"""
        dist: dict[PositionDifficulty, int] = {d: 0 for d in PositionDifficulty}
        for m in self.moves:
            if m.position_difficulty is not None:
                dist[m.position_difficulty] += 1
            else:
                dist[PositionDifficulty.UNKNOWN] += 1
        return dist

    # -------------------------------------------------------------------------
    # Filtering methods
    # -------------------------------------------------------------------------

    def filtered(self, predicate: Callable[[MoveEval], bool]) -> EvalSnapshot:
        return EvalSnapshot(moves=[m for m in self.moves if predicate(m)])

    def by_player(self, player: str) -> EvalSnapshot:
        return self.filtered(lambda m: m.player == player)

    def first_n_moves(self, n: int) -> EvalSnapshot:
        return EvalSnapshot(moves=self.moves[:n])

    def last_n_moves(self, n: int) -> EvalSnapshot:
        if n <= 0:
            return EvalSnapshot()
        return EvalSnapshot(moves=self.moves[-n:])
