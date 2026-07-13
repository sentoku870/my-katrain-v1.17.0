"""Phase B2: Position difficulty — policy-based assessment.

This module computes the policy entropy / top-5 mass signal and the
top-1 / top-2 scoreLead gap signal. Both are pure functions over the
candidate list — no I/O, no GLobals.

History: extracted from ``katrain.core.analysis.logic_difficulty``
(Phase 144-C) in Phase B2.
"""

from __future__ import annotations

import math
from typing import Any

from katrain.core.analysis.models import (
    POLICY_GAP_MAX,
    PositionDifficulty,
)

# =============================================================================
# Heuristic difficulty assessment (policy entropy fallback)
# =============================================================================


def assess_difficulty_from_policy(
    policy: list[float],
    *,
    board_size: Any = 19,
    entropy_easy_threshold: float = 2.5,
    entropy_hard_threshold: float = 1.0,
    top5_easy_threshold: float = 0.5,
    top5_hard_threshold: float = 0.9,
) -> tuple[PositionDifficulty, float]:
    """
    Policy entropy から局面難易度を推定する（fallback用）。
    """
    if not policy:
        return PositionDifficulty.UNKNOWN, 0.5

    # Handle both int and tuple board_size
    board_points = board_size[0] * board_size[1] if isinstance(board_size, tuple) else board_size * board_size

    # Safety check
    if board_points < 9:
        board_points = 361

    REF_BOARD_POINTS = 361
    ref_max_entropy = math.log(REF_BOARD_POINTS)
    current_max_entropy = math.log(board_points + 1)
    scale_factor = current_max_entropy / ref_max_entropy

    adjusted_easy = entropy_easy_threshold * scale_factor
    adjusted_hard = entropy_hard_threshold * scale_factor

    # Policy entropy 計算
    entropy = 0.0
    for p in policy:
        if p > 0:
            entropy -= p * math.log(p)

    # Top-5 cumulative mass
    sorted_probs = sorted(policy, reverse=True)
    top5_mass = sum(sorted_probs[:5])

    if entropy >= adjusted_easy and top5_mass <= top5_easy_threshold:
        return PositionDifficulty.EASY, 0.2
    elif entropy <= adjusted_hard or top5_mass >= top5_hard_threshold:
        if sorted_probs[0] >= 0.8:
            return PositionDifficulty.ONLY_MOVE, 1.0
        return PositionDifficulty.HARD, 0.8
    elif entropy >= (adjusted_easy + adjusted_hard) / 2:
        return PositionDifficulty.EASY, 0.3
    else:
        return PositionDifficulty.NORMAL, 0.5


# =============================================================================
# Top-1 / Top-2 scoreLead gap
# =============================================================================


def compute_policy_difficulty(
    candidates: list[dict[str, Any]],
    include_debug: bool = False,
) -> tuple[float | None, dict[str, Any] | None]:
    """候補手の拮抗度から Policy 難易度を計算。

    scoreLead 欠損時は None を返す（UNKNOWN 扱い）。

    Top1 と Top2 の scoreLead 差が小さいほど「迷いやすい」。
    差の絶対値を使用（scoreLead の符号は BLACK 視点だが、
    差を取れば手番に関係なく評価できる）。

    Args:
        candidates: 正規化済み候補手リスト（order順）
        include_debug: デバッグ情報を含めるか

    Returns:
        (difficulty, debug_info) タプル。
        difficulty: 0-1 の難易度値。候補が拮抗しているほど高い。
                    scoreLead 欠損時は None。
    """
    if len(candidates) < 2:
        debug = {"reason": "insufficient_candidates", "count": len(candidates)} if include_debug else None
        return 0.0, debug

    # scoreLead を取得（存在しない場合は None）
    top1_score = candidates[0].get("scoreLead")
    top2_score = candidates[1].get("scoreLead")

    # None チェック → UNKNOWN 扱い
    if top1_score is None or top2_score is None:
        debug = {"reason": "missing_scoreLead"} if include_debug else None
        return None, debug

    # 差の絶対値を使用（符号に依存しない）
    gap = abs(top1_score - top2_score)

    # gap が 0 なら difficulty=1、POLICY_GAP_MAX 以上なら difficulty=0
    difficulty = max(0.0, min(1.0, 1.0 - gap / POLICY_GAP_MAX))

    debug = (
        {
            "top1_score": top1_score,
            "top2_score": top2_score,
            "gap": gap,
            "normalized": difficulty,
        }
        if include_debug
        else None
    )

    return difficulty, debug


__all__ = [
    "assess_difficulty_from_policy",
    "compute_policy_difficulty",
]
