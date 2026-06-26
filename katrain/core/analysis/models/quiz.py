"""katrain.core.analysis.models.quiz - Quiz and important-move data structures.

Phase 144-B: Extracted from models.py (1230 lines → 6 focused modules).

Contains:
- QuizConfig, QuizItem, QuizChoice, QuizQuestion: Quiz generation
- ImportantMoveSettings + IMPORTANT_MOVE_SETTINGS_BY_LEVEL: Important move extraction
- DEFAULT_QUIZ_LOSS_THRESHOLD, DEFAULT_QUIZ_ITEM_LIMIT, DEFAULT_IMPORTANT_MOVE_LEVEL
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode
else:
    GameNode = Any


# =============================================================================
# Quiz Defaults (Phase 98)
# =============================================================================

DEFAULT_QUIZ_LOSS_THRESHOLD = 3.0
DEFAULT_QUIZ_ITEM_LIMIT = 10


# =============================================================================
# Quiz dataclasses
# =============================================================================


@dataclass(frozen=True)
class QuizConfig:
    """Quiz generation configuration."""

    loss_threshold: float
    limit: int


@dataclass
class QuizItem:
    """A generated quiz item."""

    move_number: int
    player: str | None
    loss: float


@dataclass
class QuizChoice:
    move: str
    points_lost: float | None


@dataclass
class QuizQuestion:
    item: QuizItem
    choices: list[QuizChoice]
    best_move: str | None
    node_before_move: GameNode | None

    @property
    def has_analysis(self) -> bool:
        return self.node_before_move is not None and getattr(self.node_before_move, "analysis_exists", False)


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
