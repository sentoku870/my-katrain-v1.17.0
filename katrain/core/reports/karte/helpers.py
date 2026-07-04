"""Pure helper functions for karte report generation.

This module contains pure functions with no side effects.
It may import from models.py but not from builder, sections, or context.

Phase 171: KataGo 専用化に伴い Leela 関連の分岐を削除。
``format_loss_with_engine_suffix`` / ``is_single_engine_snapshot`` は
KataGo 単一エンジン前提となったため削除し、``has_loss_data`` のみ残す。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.core.analysis.models import EvalSnapshot, MoveEval


def has_loss_data(mv: MoveEval) -> bool:
    """MoveEval に損失データが存在するか判定。

    Returns:
        True: score_loss, points_lost のいずれかが設定されている
        False: すべて None（解析データなし）

    Note:
        0.0 は有効な損失値（完璧な手）として True を返す。
        これにより「データなし」と「真の 0.0 損失」を区別できる。
        Phase 171 で ``leela_loss_est`` を削除（KataGo 専用化）。
    """
    return mv.score_loss is not None or mv.points_lost is not None

