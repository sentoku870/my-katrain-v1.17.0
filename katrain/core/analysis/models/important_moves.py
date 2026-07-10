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
MIN_LOSS_DISPLAY: float = 0.3
