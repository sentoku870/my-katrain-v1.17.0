"""katrain.core.analysis.models.important_moves - Important-move data structures.

Phase 144-B: Extracted from models.py (1230 lines → 6 focused modules).

Contains:
- ImportantMoveSettings + IMPORTANT_MOVE_SETTINGS_BY_LEVEL: Important move extraction
- DEFAULT_IMPORTANT_MOVE_LEVEL: Default importance level

Note: QuizConfig/QuizItem/QuizChoice/QuizQuestion were removed in
Phase 176 (PR 2 cleanup). Phase 138-D removed the Quiz feature from the
GUI; this cleans up the residual data classes.
"""

from __future__ import annotations

from dataclasses import dataclass

# =============================================================================
# Important Move settings
# =============================================================================


@dataclass(frozen=True)
class ImportantMoveSettings:
    """重要局面の抽出条件をまとめた設定."""

    importance_threshold: float  # importance がこの値を超えたものだけ採用
    max_moves: int  # 最大件数（大きい順に上位だけ残す）


# 棋力イメージ別プリセット（あとで UI から切り替えやすくするための土台）
IMPORTANT_MOVE_SETTINGS_BY_LEVEL = {
    # 級位者向け: 本当に大きな損だけを拾う
    "easy": ImportantMoveSettings(
        importance_threshold=1.0,
        max_moves=10,
    ),
    # 標準: 現在の挙動に近い設定
    "normal": ImportantMoveSettings(
        importance_threshold=0.5,
        max_moves=20,
    ),
    # 段位者向け: 細かいヨセも含めて多めに拾う
    "strict": ImportantMoveSettings(
        importance_threshold=0.3,
        max_moves=40,
    ),
}

DEFAULT_IMPORTANT_MOVE_LEVEL = "normal"


# Phase 148-B2: importance フォールバックの最小損失閾値。
# pick_important_moves で importance_score が閾値を超える手が1つもない場合、
# raw_score（score + winrate + loss）でフォールバックするが、従来 raw_score > 0.0
# により軽微損失を全件拾っていた（懸念③）のを防ぐための下限。
# Phase 252: this stays as the 19x19 default; the board-size-aware
# variant is :func:`min_loss_display_for_board_size` below.
MIN_LOSS_DISPLAY: float = 0.3


# Phase 252: per-board-size fallback threshold.
# 9x9 losses are typically smaller (the board is 1/4 the area), so a
# 0.3 threshold would over-trigger on a small board. 13x13 sits in
# the middle; 19x19 keeps the Phase 148-B2 default.
_MIN_LOSS_DISPLAY_BY_SIZE: dict[int, float] = {
    9: 0.15,
    13: 0.2,
    19: 0.3,
}


def min_loss_display_for_board_size(
    board_size: int | tuple[int, int] | None,
) -> float:
    """Phase 252: return the fallback raw-score threshold for a given board size.

    Used by :func:`pick_important_moves` when no importance-based
    candidates exist. The threshold guards against a flood of
    trivially-small losses (e.g. every joseki move on a 19x19 board)
    when the importance formula can't find any meaningful winners.

    Falls back to :data:`MIN_LOSS_DISPLAY` (0.3) for unknown sizes
    (rectangular, custom, ``None``) so legacy callers and tests
    preserve their pre-Phase-252 behaviour.

    Args:
        board_size: Either an int (square board) or a ``(width, height)``
            tuple. ``None`` falls back to the 19x19 default.

    Returns:
        The raw-score threshold (>= 0.0).

    Examples:
        >>> min_loss_display_for_board_size(19)
        0.3
        >>> min_loss_display_for_board_size(13)
        0.2
        >>> min_loss_display_for_board_size(9)
        0.15
        >>> min_loss_display_for_board_size(None)
        0.3
    """
    if board_size is None:
        return MIN_LOSS_DISPLAY
    if isinstance(board_size, (tuple, list)):
        if not board_size:
            return MIN_LOSS_DISPLAY
        try:
            size = min(int(board_size[0]), int(board_size[1] or board_size[0]))
        except (TypeError, ValueError):
            return MIN_LOSS_DISPLAY
    else:
        try:
            size = int(board_size)
        except (TypeError, ValueError):
            return MIN_LOSS_DISPLAY
    return _MIN_LOSS_DISPLAY_BY_SIZE.get(size, MIN_LOSS_DISPLAY)
