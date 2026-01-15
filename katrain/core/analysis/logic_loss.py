"""Loss calculation functions.

PR #126: Phase B4 - logic_loss.py作成

logic.pyから抽出された損失計算関連の関数。
- compute_loss_from_delta: delta_score/delta_winrateから損失を計算
- compute_canonical_loss: 正準的な損失量を計算
- classify_mistake: 損失からMistakeCategoryを決定
"""

from typing import Optional, Tuple

from katrain.core.analysis.models import (
    MistakeCategory,
    SCORE_THRESHOLDS,
    WINRATE_THRESHOLDS,
)


def compute_loss_from_delta(
    delta_score: Optional[float],
    delta_winrate: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    """
    手番視点の delta_score / delta_winrate から損失量 (>=0) を計算する。

    Args:
        delta_score: スコアの変化（手番視点、正=改善、負=悪化）
        delta_winrate: 勝率の変化（手番視点、正=改善、負=悪化）

    Returns:
        (score_loss, winrate_loss): 損失量のタプル（>=0、Noneの場合は計算不可）
    """
    score_loss: Optional[float] = None
    winrate_loss: Optional[float] = None

    if delta_score is not None:
        score_loss = max(0.0, -delta_score)

    if delta_winrate is not None:
        winrate_loss = max(0.0, -delta_winrate)

    return score_loss, winrate_loss


def compute_canonical_loss(
    points_lost: Optional[float],
    delta_score: Optional[float] = None,
    delta_winrate: Optional[float] = None,
    player: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """
    正準的な損失量 (>=0) を計算する。

    優先順位:
      1) points_lost が利用可能なら max(points_lost, 0) を使用
      2) delta_score/delta_winrate が利用可能ならフォールバック

    Args:
        points_lost: KaTrain標準の損失値
        delta_score: スコアの変化
        delta_winrate: 勝率の変化
        player: プレイヤー（"B" or "W"）、perspective補正用

    Returns:
        (score_loss, winrate_loss): 損失量のタプル（>=0）
    """
    score_loss: Optional[float] = None
    winrate_loss: Optional[float] = None

    # Primary: use points_lost if available
    if points_lost is not None:
        score_loss = max(0.0, points_lost)

    # Fallback: use delta with perspective correction
    if score_loss is None and delta_score is not None:
        player_sign = {"B": 1, "W": -1, None: 1}.get(player, 1)
        side_to_move_delta = player_sign * delta_score
        score_loss = max(0.0, -side_to_move_delta)

    # Winrate loss
    if delta_winrate is not None:
        player_sign = {"B": 1, "W": -1, None: 1}.get(player, 1)
        side_to_move_delta = player_sign * delta_winrate
        winrate_loss = max(0.0, -side_to_move_delta)

    return score_loss, winrate_loss


def classify_mistake(
    score_loss: Optional[float],
    winrate_loss: Optional[float],
    *,
    score_thresholds: Tuple[float, float, float] = SCORE_THRESHOLDS,
    winrate_thresholds: Tuple[float, float, float] = WINRATE_THRESHOLDS,
) -> MistakeCategory:
    """
    損失量から MistakeCategory を決定する。

    Args:
        score_loss: スコア損失（目数）
        winrate_loss: 勝率損失（%）
        score_thresholds: (GOOD/INACCURACY, INACCURACY/MISTAKE, MISTAKE/BLUNDER)
        winrate_thresholds: 同上（勝率用）

    Returns:
        MistakeCategory: GOOD, INACCURACY, MISTAKE, BLUNDER のいずれか
    """
    if score_loss is not None:
        loss = max(score_loss, 0.0)
        t1, t2, t3 = score_thresholds
        if loss < t1:
            return MistakeCategory.GOOD
        if loss < t2:
            return MistakeCategory.INACCURACY
        if loss < t3:
            return MistakeCategory.MISTAKE
        return MistakeCategory.BLUNDER

    if winrate_loss is not None:
        loss = max(winrate_loss, 0.0)
        t1, t2, t3 = winrate_thresholds
        if loss < t1:
            return MistakeCategory.GOOD
        if loss < t2:
            return MistakeCategory.INACCURACY
        if loss < t3:
            return MistakeCategory.MISTAKE
        return MistakeCategory.BLUNDER

    return MistakeCategory.GOOD
