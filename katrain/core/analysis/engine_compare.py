"""
katrain.core.analysis.engine_compare - エンジン比較ロジック

Phase 39: KataGoとLeela Zeroの解析結果を比較するための機能。

このモジュールはKivy非依存で、以下を提供:
- MoveComparison: 1手分の両エンジン比較
- EngineStats: エンジン別統計
- EngineComparisonResult: 全局の比較結果
- build_comparison_from_game(): Gameから比較結果を構築
- compute_spearman_manual(): 手動Spearman相関（scipy不使用）

Note:
- KataGo score_loss（目単位）とLeela leela_loss_est（推定損失）は
  セマンティクスが異なるため、比較は参考値として扱う
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    cast,
)

if TYPE_CHECKING:
    from katrain.core.game import Game

# =============================================================================
# Enums and Constants
# =============================================================================


class ComparisonWarning(Enum):
    """比較時の警告種別。

    Attributes:
        KATAGO_ONLY: KataGoのみ解析済み
        LEELA_ONLY: Leelaのみ解析済み
        PARTIAL_OVERLAP: 両エンジン解析手数 < 全手数の80%
        SEMANTICS_DIFFER: 常に付与（損失セマンティクスが異なる）
    """

    KATAGO_ONLY = "katago_only"
    LEELA_ONLY = "leela_only"
    PARTIAL_OVERLAP = "partial_overlap"
    SEMANTICS_DIFFER = "semantics_differ"


# 警告判定の閾値定数
# playable_moves の定義:
#   - root node: 除外
#   - 投了（is_resign=True）: 除外
#   - パス（is_pass=True）: 含める
#   - 通常手（coords有り）: 含める
PARTIAL_OVERLAP_THRESHOLD = 0.8  # both_count / playable_moves < 0.8 で警告


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class MoveComparison:
    """1手分の両エンジン比較。

    Attributes:
        move_number: 手数（1-indexed）
        player: "B" or "W"（GameNodeから取得）
        gtp: "D4", "pass", etc.（GameNodeから取得）
        katago_loss: score_loss (points)、未解析はNone
        leela_loss: leela_loss_est (estimated)、未解析はNone
        loss_diff: katago - leela (signed)、片方でもNoneならNone
    """

    move_number: int
    player: str
    gtp: str
    katago_loss: float | None
    leela_loss: float | None
    loss_diff: float | None

    @property
    def abs_diff(self) -> float:
        """絶対差分（ソート用）。Noneは0.0として扱う。"""
        return abs(self.loss_diff) if self.loss_diff is not None else 0.0

    @property
    def has_both(self) -> bool:
        """両エンジンのデータがあるか。"""
        return self.katago_loss is not None and self.leela_loss is not None

    def sort_key_divergent(self) -> tuple[float, int, float]:
        """乖離Top5用ソートキー。

        Returns:
            (abs_diff降順, move_number昇順, katago_loss降順)
        """
        return (
            -self.abs_diff,
            self.move_number,
            -(self.katago_loss or 0.0),
        )


@dataclass
class EngineStats:
    """エンジン別統計。

    Attributes:
        total_loss: 総損失
        avg_loss: 平均損失（0除算回避済み）
        blunder_count: 大悪手数 (loss >= t3)
        mistake_count: 悪手数 (t2 <= loss < t3)
        inaccuracy_count: 軽微ミス数 (t1 <= loss < t2)
        analyzed_moves: 解析手数
    """

    total_loss: float
    avg_loss: float
    blunder_count: int
    mistake_count: int
    inaccuracy_count: int
    analyzed_moves: int

    @classmethod
    def empty(cls) -> "EngineStats":
        """空の統計を返す（解析手0の場合用）。"""
        return cls(0.0, 0.0, 0, 0, 0, 0)


@dataclass
class EngineComparisonResult:
    """全局の比較結果。

    Attributes:
        move_comparisons: 全手の比較リスト
        katago_stats: KataGo統計
        leela_stats: Leela統計
        correlation: Spearman相関係数（-1.0〜+1.0、N<5でNone）
        divergent_moves: 乖離Top5
        mean_diff: 平均差分（傾向判定用）
        warnings: 警告リスト
        total_moves: 全手数（playable_moves）
    """

    move_comparisons: list[MoveComparison]
    katago_stats: EngineStats
    leela_stats: EngineStats
    correlation: float | None
    divergent_moves: list[MoveComparison]
    mean_diff: float | None
    warnings: list[ComparisonWarning] = field(default_factory=list)
    total_moves: int = 0


# =============================================================================
# Helper Functions
# =============================================================================


def compute_engine_stats(
    losses: list[float],
    thresholds: tuple[float, float, float],
) -> EngineStats:
    """損失リストから統計を計算。

    Args:
        losses: 損失値のリスト
        thresholds: (inaccuracy, mistake, blunder) の閾値

    Returns:
        EngineStats インスタンス
    """
    if not losses:
        return EngineStats.empty()

    t1, t2, t3 = thresholds
    total = sum(losses)
    count = len(losses)

    blunder = sum(1 for loss in losses if loss >= t3)
    mistake = sum(1 for loss in losses if t2 <= loss < t3)
    inaccuracy = sum(1 for loss in losses if t1 <= loss < t2)

    return EngineStats(
        total_loss=total,
        avg_loss=total / count,
        blunder_count=blunder,
        mistake_count=mistake,
        inaccuracy_count=inaccuracy,
        analyzed_moves=count,
    )


def compute_spearman_manual(paired: list[tuple[float, float]]) -> float | None:
    """手動Spearman順位相関係数（scipy不使用）。

    アルゴリズム:
    1. 各リストを順位に変換（中央順位法でタイ処理）
    2. 順位のPearson相関を計算

    Args:
        paired: (x, y) のタプルリスト

    Returns:
        相関係数（-1.0〜1.0）、またはNone（N<5、分散ゼロ、NaN発生時）
    """
    if len(paired) < 5:
        return None

    x = [p[0] for p in paired]
    y = [p[1] for p in paired]

    def to_ranks(values: list[float]) -> list[float]:
        """中央順位法で順位を計算。"""
        n = len(values)
        sorted_idx = sorted(range(n), key=lambda i: values[i])
        ranks = [0.0] * n

        i = 0
        while i < n:
            j = i
            # 同値グループを検出
            while j < n - 1 and values[sorted_idx[j]] == values[sorted_idx[j + 1]]:
                j += 1
            # 中央順位 = (開始順位 + 終了順位) / 2 (1-indexed)
            avg_rank = (i + j + 2) / 2
            for k in range(i, j + 1):
                ranks[sorted_idx[k]] = avg_rank
            i = j + 1

        return ranks

    rank_x = to_ranks(x)
    rank_y = to_ranks(y)

    # Pearson相関
    n = len(rank_x)
    mean_x = sum(rank_x) / n
    mean_y = sum(rank_y) / n

    num = sum((rx - mean_x) * (ry - mean_y) for rx, ry in zip(rank_x, rank_y))
    den_x = sum((rx - mean_x) ** 2 for rx in rank_x) ** 0.5
    den_y = sum((ry - mean_y) ** 2 for ry in rank_y) ** 0.5

    if den_x == 0 or den_y == 0:
        return None  # 分散ゼロ（全値同一）

    corr = num / (den_x * den_y)

    # NaN/無限大チェック
    if math.isnan(corr) or math.isinf(corr):
        return None

    return cast(float, corr)


def _extract_leela_loss(node: Any) -> float | None:
    """GameNodeからLeela損失を抽出。

    Args:
        node: GameNode インスタンス

    Returns:
        leela_loss_est または None
    """
    leela_analysis = getattr(node, "leela_analysis", None)
    if leela_analysis is None:
        return None

    # LeelaPositionEvalから候補手を取得し、打った手の損失を計算
    # 簡易実装: 既にMoveEvalに変換済みの場合はそちらを使用
    # Phase 31のconversion.pyで変換されたデータを参照

    # GameNode._leela_analysisはLeelaPositionEval
    # 損失は親ノードとの比較で計算する必要があるため、
    # ここでは親ノードの候補手から計算する
    parent = getattr(node, "parent", None)
    if parent is None:
        return None

    parent_leela = getattr(parent, "leela_analysis", None)
    if parent_leela is None:
        return None

    # 打った手を取得
    move = getattr(node, "move", None)
    if move is None:
        return None

    # パス判定
    if getattr(move, "coords", None) is None:
        if getattr(move, "is_pass", False):
            played_gtp = "pass"
        else:
            return None
    else:
        played_gtp = move.gtp()

    # 候補手から損失を計算（K=0.5）
    candidates = getattr(parent_leela, "candidates", [])
    if not candidates:
        return None

    best_wr = candidates[0].winrate if candidates else None
    if best_wr is None:
        return None

    # 打った手の勝率を検索
    played_wr = None
    for cand in candidates:
        if cand.move == played_gtp:
            played_wr = cand.winrate
            break

    if played_wr is None:
        # 候補手にない場合は最悪手として扱う
        # または None を返す（保守的）
        return None

    # 損失 = (best_wr - played_wr) * K * 100
    # K=0.5 がデフォルト
    K = 0.5
    loss = (best_wr - played_wr) * K * 100
    return cast(float, max(0.0, loss))


# =============================================================================
# Main Function
# =============================================================================


def build_comparison_from_game(
    game: "Game",
    score_thresholds: tuple[float, float, float | None] | None = None,
    divergent_threshold: float = 1.0,
    divergent_limit: int = 5,
) -> EngineComparisonResult:
    """Gameオブジェクトから両エンジンの比較結果を構築。

    Args:
        game: Gameオブジェクト
        score_thresholds: (inaccuracy, mistake, blunder) の閾値
        divergent_threshold: 乖離Top5の最低閾値
        divergent_limit: 乖離Top5の最大件数

    Returns:
        EngineComparisonResult インスタンス
    """
    from katrain.core.analysis.logic import iter_main_branch_nodes, snapshot_from_game
    from katrain.core.analysis.models import SCORE_THRESHOLDS

    if score_thresholds is None:
        score_thresholds = SCORE_THRESHOLDS

    warnings: list[ComparisonWarning] = [ComparisonWarning.SEMANTICS_DIFFER]

    # Step 1: GameNodeからmove_info（player, gtp）を収集
    # → これがマスターリスト（エンジン解析有無に依存しない）
    move_info_by_num: dict[int, tuple[str, str]] = {}
    for node in iter_main_branch_nodes(game):
        move = getattr(node, "move", None)
        if move is None:
            continue  # rootノード

        # 投了チェック（KaTrainでは通常is_resignはないが念のため）
        if getattr(node, "is_resign", False):
            continue

        move_num = node.depth  # depth = move_number for main branch
        player = "B" if move.player == 1 else "W"

        # パス判定
        if getattr(move, "coords", None) is None:
            if getattr(move, "is_pass", False):
                gtp = "pass"
            else:
                continue  # 不明な座標なし手は除外
        else:
            gtp = move.gtp()

        move_info_by_num[move_num] = (player, gtp)

    total_moves = len(move_info_by_num)

    # Step 2: KataGo snapshot取得
    katago_snapshot = snapshot_from_game(game)
    katago_by_move: dict[int, float] = {}
    for m in katago_snapshot.moves:
        if m.score_loss is not None:
            katago_by_move[m.move_number] = m.score_loss

    # Step 3: Leela分析を収集（GameNode._leela_analysis）
    leela_by_move: dict[int, float] = {}
    for node in iter_main_branch_nodes(game):
        loss_est = _extract_leela_loss(node)
        if loss_est is not None:
            leela_by_move[node.depth] = loss_est

    # Step 4: MoveComparison構築（マスターリストベース）
    comparisons: list[MoveComparison] = []
    for move_num in sorted(move_info_by_num.keys()):
        player, gtp = move_info_by_num[move_num]
        katago_loss = katago_by_move.get(move_num)
        leela_loss = leela_by_move.get(move_num)

        # 差分計算（両方ある場合のみ）
        loss_diff: float | None = None
        if katago_loss is not None and leela_loss is not None:
            loss_diff = katago_loss - leela_loss

        comparisons.append(
            MoveComparison(
                move_number=move_num,
                player=player,
                gtp=gtp,
                katago_loss=katago_loss,
                leela_loss=leela_loss,
                loss_diff=loss_diff,
            )
        )

    # Step 5: 統計計算
    # Use default thresholds if not provided
    thresholds = score_thresholds if score_thresholds is not None else (1.0, 3.0, 5.0)
    katago_stats = compute_engine_stats(
        [c.katago_loss for c in comparisons if c.katago_loss is not None],
        thresholds,  # type: ignore[arg-type]
    )
    leela_stats = compute_engine_stats(
        [c.leela_loss for c in comparisons if c.leela_loss is not None],
        thresholds,  # type: ignore[arg-type]
    )

    # Step 6: 相関係数（手動Spearman、N<5でNone）
    # Note: Equivalent to `if c.has_both` but enables mypy type narrowing
    paired = [
        (c.katago_loss, c.leela_loss)
        for c in comparisons
        if c.katago_loss is not None and c.leela_loss is not None
    ]
    correlation = compute_spearman_manual(paired) if len(paired) >= 5 else None

    # Step 7: 乖離Top5（タイブレーク付きソート）
    with_diff = [
        c for c in comparisons if c.has_both and c.abs_diff >= divergent_threshold
    ]
    divergent = sorted(with_diff, key=lambda c: c.sort_key_divergent())[:divergent_limit]

    # Step 8: 平均差分
    diffs = [c.loss_diff for c in comparisons if c.loss_diff is not None]
    mean_diff = sum(diffs) / len(diffs) if diffs else None

    # Step 9: 警告判定
    has_katago = katago_stats.analyzed_moves > 0
    has_leela = leela_stats.analyzed_moves > 0
    both_count = len(paired)

    if has_katago and not has_leela:
        warnings.append(ComparisonWarning.KATAGO_ONLY)
    elif has_leela and not has_katago:
        warnings.append(ComparisonWarning.LEELA_ONLY)
    elif total_moves > 0 and both_count < total_moves * PARTIAL_OVERLAP_THRESHOLD:
        warnings.append(ComparisonWarning.PARTIAL_OVERLAP)

    return EngineComparisonResult(
        move_comparisons=comparisons,
        katago_stats=katago_stats,
        leela_stats=leela_stats,
        correlation=correlation,
        divergent_moves=divergent,
        mean_diff=mean_diff,
        warnings=warnings,
        total_moves=total_moves,
    )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "ComparisonWarning",
    "MoveComparison",
    "EngineStats",
    "EngineComparisonResult",
    "build_comparison_from_game",
    "compute_engine_stats",
    "compute_spearman_manual",
    "PARTIAL_OVERLAP_THRESHOLD",
]
