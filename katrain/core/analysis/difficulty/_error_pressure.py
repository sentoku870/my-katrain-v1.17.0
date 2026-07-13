"""Phase B2: Position difficulty — KataGo self-uncertainty (error_pressure).

Normalises KataGo's ``shorttermScoreError`` (rawStdev-class signal) into
a 0-1 score. Phase 154 addition: when KataGo itself is uncertain, the
human player probably is too.

History: extracted from ``katrain.core.analysis.logic_difficulty``
(Phase 144-C) in Phase B2.
"""

from __future__ import annotations

from typing import Any

from katrain.core.analysis.models import SHORTTERM_SCORE_ERROR_MAX


def compute_error_pressure(
    candidates: list[dict[str, Any]],
    root_info: dict[str, Any] | None = None,
    include_debug: bool = False,
) -> tuple[float | None, dict[str, Any] | None]:
    """KataGo 自身の短期 error から error_pressure を計算。

    shorttermScoreError を SHORTTERM_SCORE_ERROR_MAX で正規化。
    KataGo も読み切れない局面 = ユーザーも迷うはず、という仮説に基づく。

    Args:
        candidates: 正規化済み候補手リスト（order順）
        root_info: KataGo rootInfo（shorttermScoreError, rawStdev などを含む）
        include_debug: デバッグ情報を含めるか

    Returns:
        (error_pressure, debug_info) タプル。
        error_pressure: 0-1、値が大きいほど KataGo も読み切れない。
                        shorttermScoreError 欠損時は None。
    """
    if not candidates:
        return None, {"reason": "no_candidates"} if include_debug else None

    ste: Any = None
    if isinstance(root_info, dict):
        ste = root_info.get("shorttermScoreError")

    if ste is None:
        return None, {"reason": "missing_shorttermScoreError"} if include_debug else None

    try:
        ste_val = float(ste)
    except (TypeError, ValueError):
        return None, {"reason": "invalid_shorttermScoreError"} if include_debug else None

    error_pressure = max(0.0, min(1.0, abs(ste_val) / SHORTTERM_SCORE_ERROR_MAX))

    debug = (
        {
            "shorttermScoreError": ste_val,
            "normalized": error_pressure,
        }
        if include_debug
        else None
    )

    return error_pressure, debug


__all__ = ["compute_error_pressure"]
