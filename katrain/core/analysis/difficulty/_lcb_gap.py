"""Phase B2: Position difficulty — LCB (lower-confidence-bound) gap.

Normalises the LCB gap between the top-1 and top-2 candidates into a
0-1 score. A large LCB gap means KataGo clearly prefers one move
(trustworthy) → contributes positively to overall difficulty when
combined with error_pressure (KataGo is also certain). A small LCB
gap means KataGo is uncertain.

Phase 154 addition.

History: extracted from ``katrain.core.analysis.logic_difficulty``
(Phase 144-C) in Phase B2.
"""

from __future__ import annotations

from typing import Any

from katrain.core.analysis.models import LCB_GAP_MAX


def compute_lcb_gap(
    candidates: list[dict[str, Any]],
    include_debug: bool = False,
) -> tuple[float | None, dict[str, Any] | None]:
    """最善手と次善手の LCB 差から lcb_gap を計算。

    lcb_gap が大きい = 最善手が他より明確に信頼できる（KataGo の自信）。
    小さい = 候補手が拮抗していてKataGoも自信がない。

    注: 現状は「KataGoの候補手信頼度差」として利用。
    絶対値が大きいほど「KataGoは明確に読み切っている」と解釈可能。

    Args:
        candidates: 正規化済み候補手リスト（order順）
        include_debug: デバッグ情報を含めるか

    Returns:
        (lcb_gap, debug_info) タプル。
        lcb_gap: 0-1、値が大きいほどKataGoの候補手信頼度差が大きい。
                 lcb 欠損時は None。
    """
    if len(candidates) < 2:
        return None, {"reason": "insufficient_candidates"} if include_debug else None

    top1 = candidates[0]
    top2 = candidates[1]
    if not isinstance(top1, dict) or not isinstance(top2, dict):
        return None, {"reason": "invalid_candidate_format"} if include_debug else None

    top1_lcb = top1.get("lcb")
    top2_lcb = top2.get("lcb")

    if top1_lcb is None or top2_lcb is None:
        return None, {"reason": "missing_lcb"} if include_debug else None

    try:
        top1_val = float(top1_lcb)
        top2_val = float(top2_lcb)
    except (TypeError, ValueError):
        return None, {"reason": "invalid_lcb"} if include_debug else None

    lcb_diff = abs(top1_val - top2_val)
    lcb_gap = max(0.0, min(1.0, lcb_diff / LCB_GAP_MAX))

    debug = (
        {
            "top1_lcb": top1_val,
            "top2_lcb": top2_val,
            "diff": lcb_diff,
            "normalized": lcb_gap,
        }
        if include_debug
        else None
    )

    return lcb_gap, debug


__all__ = ["compute_lcb_gap"]
