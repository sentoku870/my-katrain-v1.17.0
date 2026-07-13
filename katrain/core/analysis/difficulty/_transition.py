"""Phase B2: Position difficulty — transition (drop) difficulty.

This module computes the top-1 / top-2 scoreLead **drop**, i.e. how much
quality falls if the second-best move were picked instead of the best.
A large drop means "one move matters" → high transition difficulty.

History: extracted from ``katrain.core.analysis.logic_difficulty``
(Phase 144-C) in Phase B2.
"""

from __future__ import annotations

from typing import Any

from katrain.core.analysis.models import TRANSITION_DROP_MAX


def compute_transition_difficulty(
    candidates: list[dict[str, Any]],
    include_debug: bool = False,
) -> tuple[float | None, dict[str, Any] | None]:
    """評価の急落度から Transition 難易度を計算。

    scoreLead 欠損時は None を返す（UNKNOWN 扱い）。

    Top1 と Top2 の scoreLead 差が大きいほど「崩れやすい」。

    意味:
    - 最善手を逃すとどれだけ損するか
    - 差が大きい = 一手の選択が重要 = 崩れやすい

    Args:
        candidates: 正規化済み候補手リスト（order順）
        include_debug: デバッグ情報を含めるか

    Returns:
        (difficulty, debug_info) タプル。
        difficulty: 0-1 の難易度値。少し外すと急に悪化するほど高い。
                    scoreLead 欠損時は None。
    """
    if len(candidates) < 2:
        debug = {"reason": "insufficient_candidates", "count": len(candidates)} if include_debug else None
        return 0.0, debug

    top1_score = candidates[0].get("scoreLead")
    top2_score = candidates[1].get("scoreLead")

    # None チェック → UNKNOWN 扱い
    if top1_score is None or top2_score is None:
        debug = {"reason": "missing_scoreLead"} if include_debug else None
        return None, debug

    # Top1 と Top2 の差（絶対値）
    drop = abs(top1_score - top2_score)

    # drop が TRANSITION_DROP_MAX 以上なら difficulty=1
    difficulty = max(0.0, min(1.0, drop / TRANSITION_DROP_MAX))

    debug = (
        {
            "top1_score": top1_score,
            "top2_score": top2_score,
            "drop": drop,
            "normalized": difficulty,
        }
        if include_debug
        else None
    )

    return difficulty, debug


__all__ = ["compute_transition_difficulty"]
