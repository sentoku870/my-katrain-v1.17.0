"""Pure helper functions for karte report generation.

This module contains pure functions with no side effects.
It may import from models.py but not from builder, sections, or context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from katrain.core.analysis.models import EngineType

if TYPE_CHECKING:
    from katrain.core.analysis.models import EvalSnapshot, MoveEval


def has_loss_data(mv: MoveEval) -> bool:
    """MoveEval に損失データが存在するか判定。

    Returns:
        True: score_loss, leela_loss_est, points_lost のいずれかが設定されている
        False: すべて None（解析データなし）

    Note:
        0.0 は有効な損失値（完璧な手）として True を返す。
        これにより「データなし」と「真の 0.0 損失」を区別できる。
    """
    return (
        mv.score_loss is not None
        or mv.leela_loss_est is not None
        or mv.points_lost is not None
    )


def format_loss_with_engine_suffix(
    loss_val: float | None,
    engine_type: EngineType,
) -> str:
    """損失値をフォーマット。Leelaは(推定)サフィックス付き。

    既存 fmt_float 完全互換: 符号なし、単位なし
    - None: "unknown"
    - KataGo/UNKNOWN: "6.0"
    - Leela: "6.0(推定)"

    Args:
        loss_val: 損失値（None は未解析）
        engine_type: エンジン種別

    Returns:
        フォーマット済み文字列

    Note:
        0.0 は有効な損失値（完璧な手）として "0.0" を返す。
        データなし（None）のみ "unknown" を返す。
    """
    if loss_val is None:
        return "unknown"
    base = f"{loss_val:.1f}"  # fmt_float と同一フォーマット
    if engine_type == EngineType.LEELA:
        return f"{base}(推定)"
    return base


def is_single_engine_snapshot(snapshot: EvalSnapshot) -> bool:
    """Check if snapshot contains data from only one engine type.

    Args:
        snapshot: EvalSnapshot to validate

    Returns:
        True if all moves are from a single engine (or no analysis data).
        False if both KataGo and Leela data exist in the same snapshot.

    Allowed patterns:
        - All moves have score_loss (KataGo) -> OK
        - All moves have leela_loss_est (Leela) -> OK
        - All moves have no loss data (unanalyzed) -> OK
        - Some moves analyzed, some not (partial) -> OK
        - At least one KataGo + at least one Leela -> NG (returns False)
    """
    has_katago = any(m.score_loss is not None for m in snapshot.moves)
    has_leela = any(m.leela_loss_est is not None for m in snapshot.moves)
    return not (has_katago and has_leela)
