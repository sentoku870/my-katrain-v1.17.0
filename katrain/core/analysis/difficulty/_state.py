"""Phase B2: Position difficulty — state (board complexity) difficulty.

Currently a no-op (always returns 0.0) — placeholder for future
"board complexity from candidate diversity" signal. Kept here so the
public aggregator in :mod:`katrain.core.analysis.difficulty.api` has
a uniform composition shape across the four difficulty axes.

History: extracted from ``katrain.core.analysis.logic_difficulty``
(Phase 144-C) in Phase B2.
"""

from __future__ import annotations

from typing import Any


def compute_state_difficulty(
    candidates: list[dict[str, Any]],
    include_debug: bool = False,
) -> tuple[float, dict[str, Any] | None]:
    """盤面の複雑さから State 難易度を計算。

    v1: 仕様書の「控えめに扱う」に従い、常に 0.0 を返す。
    将来の拡張で候補数・分岐多様性を考慮予定。

    Args:
        candidates: 正規化済み候補手リスト
        include_debug: デバッグ情報を含めるか

    Returns:
        (difficulty, debug_info) タプル。v1 では常に (0.0, debug)。
    """
    debug = (
        {
            "v1_note": "state_difficulty disabled in v1",
            "candidate_count": len(candidates),
        }
        if include_debug
        else None
    )

    return 0.0, debug


__all__ = ["compute_state_difficulty"]
