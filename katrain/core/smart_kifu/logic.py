"""Smart Kifu Learning - Business Logic (Phase 13).

This module contains pure calculation functions for Smart Kifu Learning.
All functions are stateless and UI-independent.

v0.2 Scope:
- bucket_key computation
- engine_profile_id computation
- game_id computation (normalized hash)
- confidence calculation
- viewer level estimation
- handicap adjustment suggestion
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from katrain.core.smart_kifu.models import (
    CONFIDENCE_HIGH_MIN_ANALYZED_RATIO,
    CONFIDENCE_HIGH_MIN_SAMPLES,
    CONFIDENCE_MEDIUM_MIN_ANALYZED_RATIO,
    CONFIDENCE_MEDIUM_MIN_SAMPLES,
    Confidence,
    EngineProfileSnapshot,
    TrainingSetManifest,
    TrainingSetSummary,
    ViewerPreset,
)

if TYPE_CHECKING:
    from katrain.core.game import Game
    from katrain.core.game_node import GameNode
    from katrain.core.sgf_parser import SGFNode

logger = logging.getLogger(__name__)


# =============================================================================
# Bucket Key Computation
# =============================================================================


def compute_bucket_key(board_size: int, handicap: int) -> str:
    """Bucketキーを計算。

    Bucket = board_size × handicap_group の組み合わせ。
    - handicap_group: "even" (HA <= 1) / "handicap" (HA >= 2)

    Args:
        board_size: 盤サイズ（9, 13, 19等）
        handicap: 置石数（0-9）

    Returns:
        Bucketキー（例: "19_even", "9_handicap"）
    """
    handicap_group = "even" if handicap <= 1 else "handicap"
    return f"{board_size}_{handicap_group}"


# =============================================================================
# Engine Profile ID Computation
# =============================================================================


def compute_engine_profile_id(snapshot: EngineProfileSnapshot) -> str:
    """engine_profile_id を計算。

    canonical JSON: キー昇順、float丸め、None/空文字除外

    Args:
        snapshot: エンジン設定スナップショット

    Returns:
        engine_profile_id（ep_{16hex}）

    Note:
        - None チェックは `is not None` を使う（0も有効値）
        - 空文字列は除外（model_name="" は含めない）
        - JSONキー: model, visits, komi（アルファベット順でソート）
    """
    d: dict[str, Any] = {}

    # model_name: None と空文字列は除外
    if snapshot.model_name is not None and snapshot.model_name != "":
        d["model"] = snapshot.model_name

    # max_visits: None は除外、0 は有効値として含める
    if snapshot.max_visits is not None:
        d["visits"] = snapshot.max_visits

    # komi: None は除外、0.0 も有効値として含める
    if snapshot.komi is not None:
        d["komi"] = round(snapshot.komi, 2)

    canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
    hash_full = hashlib.sha1(canonical.encode()).hexdigest()
    return f"ep_{hash_full[:16]}"


# =============================================================================
# Game ID Computation
# =============================================================================


def compute_game_id(sgf_content: str) -> str:
    """game_id を計算。正規化後のSGF内容をハッシュ。

    正規化:
      1. CRLF/CR → LF に統一
      2. 末尾の空白・改行を除去（rstrip）
      3. UTF-8 でエンコード

    Args:
        sgf_content: SGFファイルの内容

    Returns:
        game_id（sha1:{40hex}）
    """
    normalized = sgf_content.replace("\r\n", "\n").replace("\r", "\n").rstrip()
    hash_full = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
    return f"sha1:{hash_full}"


# =============================================================================
# Analyzed Ratio Computation
# =============================================================================


def iter_main_branch_nodes(root: GameNode | SGFNode) -> Iterator[GameNode | SGFNode]:
    """メインラインのノードを走査（root自体は含めない）。

    Args:
        root: 走査開始ノード（通常は game.root）

    Yields:
        メインライン上の各ノード（children[0] を辿る）

    Note:
        - root 自体は yield しない（着手ではないため）
        - pass ノードも含める
        - 分岐は無視（children[0] のみ）
    """
    node: GameNode | SGFNode = root
    while node.children:
        node = node.children[0]
        yield node


def compute_analyzed_ratio_from_game(game: Game) -> float | None:
    """Gameオブジェクトからanalyzed_ratioを計算。

    Args:
        game: Gameオブジェクト

    Returns:
        0.0-1.0 の比率。Gameが無効/空の場合はNone。

    Note:
        - root ノードは数えない（着手ではない）
        - pass ノードは数える
        - 着手がない場合（root のみ）は None
    """
    if not game or not game.root:
        return None
    nodes = list(iter_main_branch_nodes(game.root))
    if not nodes:
        return None  # 着手がない場合
    analyzed = sum(1 for n in nodes if getattr(n, "analysis", None) is not None)
    return analyzed / len(nodes)


def has_analysis_data(node: GameNode) -> bool:
    """ノードに解析データが存在するかチェック（軽量）。

    KTプロパティ（analysis_from_sgf）の存在と非空をチェック。
    load_analysis() を呼ばないため高速。

    Args:
        node: GameNode

    Returns:
        True if KT property exists and is non-empty list

    Note:
        - None → False
        - [] → False（不完全データとして扱う）
        - [data...] → True
    """
    return bool(getattr(node, "analysis_from_sgf", None))


def compute_analyzed_ratio_from_sgf_file(sgf_path: str) -> float | None:
    """SGFファイルから解析率を計算（軽量版）。

    Args:
        sgf_path: SGFファイルパス

    Returns:
        0.0-1.0: 解析率（着手あり）
        None: ファイル無効/着手なし

    Spec:
        - パース失敗 → None
        - rootのみ → None
        - 解析ノード0個 → 0.0
        - メインラインのみ、root除外、pass含む、分岐無視
    """
    # 遅延インポート（循環依存回避）
    from katrain.core.game import KaTrainSGF

    try:
        root = KaTrainSGF.parse_file(sgf_path)
    except Exception as e:
        logger.debug(f"Failed to parse SGF {sgf_path}: {e}")
        return None

    nodes = list(iter_main_branch_nodes(root))

    if not nodes:
        return None  # 着手なし

    # Use getattr for SGFNode compatibility (analysis_from_sgf may not exist)
    analyzed = sum(1 for n in nodes if bool(getattr(n, "analysis_from_sgf", None)))
    return analyzed / len(nodes)


def compute_training_set_summary(manifest: TrainingSetManifest) -> TrainingSetSummary:
    """Training Set のサマリーを計算（オンデマンド）。

    Args:
        manifest: TrainingSetManifest

    Returns:
        TrainingSetSummary

    Note:
        - analyzed_ratio が None のゲームは「未解析」としてカウント
        - average は None を除外して計算
        - 全て None → average = None（not 0.0）
    """
    total = len(manifest.games)
    if total == 0:
        return TrainingSetSummary(total_games=0)

    ratios = [g.analyzed_ratio for g in manifest.games if g.analyzed_ratio is not None]
    analyzed = len(ratios)
    fully = sum(1 for r in ratios if r >= 1.0)
    avg = sum(ratios) / len(ratios) if ratios else None

    return TrainingSetSummary(
        total_games=total,
        analyzed_games=analyzed,
        fully_analyzed_games=fully,
        average_analyzed_ratio=avg,
        unanalyzed_games=total - analyzed,
    )


# =============================================================================
# Confidence Computation
# =============================================================================


def compute_confidence(samples: int, analyzed_ratio: float | None) -> Confidence:
    """データ品質の信頼度を計算。

    v4.1: engine_consistent引数を削除（不一致データは集計前に除外するため）

    Args:
        samples: 集計に使用した局数
        analyzed_ratio: 平均解析率（None=解析データなし）

    Returns:
        Confidence レベル

    Note:
        - analyzed_ratio=None → Confidence.LOW
        - High: samples >= 30 かつ analyzed_ratio >= 0.7
        - Medium: samples >= 10 かつ analyzed_ratio >= 0.4
        - Low: それ以外
    """
    # analyzed_ratio が None の場合は常に LOW
    if analyzed_ratio is None:
        return Confidence.LOW

    # High: samples >= 30 かつ analyzed_ratio >= 0.7
    if samples >= CONFIDENCE_HIGH_MIN_SAMPLES and analyzed_ratio >= CONFIDENCE_HIGH_MIN_ANALYZED_RATIO:
        return Confidence.HIGH

    # Medium: samples >= 10 かつ analyzed_ratio >= 0.4
    if samples >= CONFIDENCE_MEDIUM_MIN_SAMPLES and analyzed_ratio >= CONFIDENCE_MEDIUM_MIN_ANALYZED_RATIO:
        return Confidence.MEDIUM

    return Confidence.LOW


# =============================================================================
# Viewer Level Estimation
# =============================================================================


def estimate_viewer_level(avg_loss: float, blunder_rate: float) -> int:
    """平均損失とブランダー率からviewer_levelを推定。

    Args:
        avg_loss: 平均損失（目数）
        blunder_rate: 大悪手率（0.0-1.0）

    Returns:
        viewer_level（1-10）

    Note:
        v0.2では簡易推定。将来的にはより複雑なモデルを使用。
        - 低損失・低ブランダー → 高レベル（詳細な解説が必要）
        - 高損失・高ブランダー → 低レベル（基本的な解説が必要）
    """
    # 損失ベースのスコア（0-5）
    if avg_loss <= 0.5:
        loss_score = 5
    elif avg_loss <= 1.0:
        loss_score = 4
    elif avg_loss <= 2.0:
        loss_score = 3
    elif avg_loss <= 3.0:
        loss_score = 2
    elif avg_loss <= 5.0:
        loss_score = 1
    else:
        loss_score = 0

    # ブランダー率ベースのスコア（0-5）
    if blunder_rate <= 0.02:
        blunder_score = 5
    elif blunder_rate <= 0.05:
        blunder_score = 4
    elif blunder_rate <= 0.10:
        blunder_score = 3
    elif blunder_rate <= 0.15:
        blunder_score = 2
    elif blunder_rate <= 0.20:
        blunder_score = 1
    else:
        blunder_score = 0

    # 合計スコアをviewer_levelに変換（1-10）
    total_score = loss_score + blunder_score  # 0-10
    return max(1, min(10, total_score))


def map_viewer_level_to_preset(level: int) -> ViewerPreset:
    """viewer_levelをViewerPresetに変換。

    Args:
        level: viewer_level（1-10）

    Returns:
        ViewerPreset

    Mapping:
        - 1-3: Lite
        - 4-7: Standard
        - 8-10: Deep
    """
    if level <= 3:
        return ViewerPreset.LITE
    elif level <= 7:
        return ViewerPreset.STANDARD
    else:
        return ViewerPreset.DEEP


# =============================================================================
# Handicap Adjustment Suggestion
# =============================================================================


def suggest_handicap_adjustment(winrate: float, current_handicap: int) -> tuple[int, str]:
    """勝率に基づいて置石調整を提案。

    Args:
        winrate: 直近N局の勝率（0.0-1.0）
        current_handicap: 現在の置石数

    Returns:
        (提案置石数, 理由メッセージ) のタプル

    Rules:
        - 勝率 > 70%: 置石-1（強くなったので難易度UP）
        - 勝率 < 30%: 置石+1（難しすぎるので難易度DOWN）
        - 勝率 40-60%: 現状維持（適正難易度）
        - それ以外（30-40%, 60-70%）: 現状維持（様子見）
    """
    if winrate > 0.70:
        new_handicap = max(0, current_handicap - 1)
        if new_handicap == current_handicap:
            return (current_handicap, "勝率が高いですが、置石は既に最小です")
        return (new_handicap, f"勝率{winrate:.0%}と高いため、置石を{current_handicap}→{new_handicap}に減らすことを推奨")

    if winrate < 0.30:
        new_handicap = min(9, current_handicap + 1)
        if new_handicap == current_handicap:
            return (current_handicap, "勝率が低いですが、置石は既に最大です")
        return (new_handicap, f"勝率{winrate:.0%}と低いため、置石を{current_handicap}→{new_handicap}に増やすことを推奨")

    if 0.40 <= winrate <= 0.60:
        return (current_handicap, f"勝率{winrate:.0%}は適正範囲内です。現状維持を推奨")

    # 30-40% or 60-70%: 様子見
    return (current_handicap, f"勝率{winrate:.0%}は境界付近です。しばらく様子を見ることを推奨")


# =============================================================================
# __all__
# =============================================================================

__all__ = [
    # Bucket
    "compute_bucket_key",
    # Engine Profile
    "compute_engine_profile_id",
    # Game ID
    "compute_game_id",
    # Analyzed Ratio
    "iter_main_branch_nodes",
    "compute_analyzed_ratio_from_game",
    "has_analysis_data",
    "compute_analyzed_ratio_from_sgf_file",
    # Training Set Summary
    "compute_training_set_summary",
    # Confidence
    "compute_confidence",
    # Viewer Level
    "estimate_viewer_level",
    "map_viewer_level_to_preset",
    # Handicap
    "suggest_handicap_adjustment",
]
