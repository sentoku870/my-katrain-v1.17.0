"""Quiz helper functions.

PR #128: Phase B4 - logic_quiz.py作成

logic.pyから抽出されたクイズ生成関連の関数。
- quiz_items_from_snapshot: スナップショットからクイズアイテムを生成
- quiz_points_lost_from_candidate: 候補手から損失値を抽出
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from katrain.core.analysis.models import (
    DEFAULT_QUIZ_ITEM_LIMIT,
    DEFAULT_QUIZ_LOSS_THRESHOLD,
    EvalSnapshot,
    QuizItem,
    SKILL_PRESETS,
    DEFAULT_SKILL_PRESET,
    get_canonical_loss_from_move,
)


def get_skill_preset_quiz_config(name: str):
    """Return quiz config from skill preset."""
    preset = SKILL_PRESETS.get(name, SKILL_PRESETS[DEFAULT_SKILL_PRESET])
    return preset.quiz


def quiz_items_from_snapshot(
    snapshot: EvalSnapshot,
    *,
    loss_threshold: float = DEFAULT_QUIZ_LOSS_THRESHOLD,
    limit: int = DEFAULT_QUIZ_ITEM_LIMIT,
    preset: Optional[str] = None,
) -> List[QuizItem]:
    """
    EvalSnapshot から「大きなミス」をクイズ形式で取り出す簡易ヘルパー。

    Args:
        snapshot: 評価スナップショット
        loss_threshold: この閾値以上の損失を持つ手をクイズ対象とする
        limit: 最大クイズ数
        preset: スキルプリセット名（指定時はpresetの設定を使用）

    Returns:
        QuizItemのリスト（損失順にソート）
    """
    if not snapshot.moves or limit <= 0:
        return []

    if preset is not None:
        preset_cfg = get_skill_preset_quiz_config(preset)
        loss_threshold = preset_cfg.loss_threshold
        limit = preset_cfg.limit

    items: List[QuizItem] = []
    for move in snapshot.moves:
        if move.score_loss is None and move.points_lost is None:
            continue
        loss_val = get_canonical_loss_from_move(move)
        if loss_val < loss_threshold:
            continue
        items.append(
            QuizItem(
                move_number=move.move_number,
                player=move.player,
                loss=float(loss_val),
            )
        )

    items.sort(key=lambda qi: qi.loss, reverse=True)
    return items[:limit]


def quiz_points_lost_from_candidate(
    candidate_move: Dict[str, Any],
    *,
    root_score: Optional[float],
    next_player: Optional[str],
) -> Optional[float]:
    """
    Extract a points-lost style metric from an existing candidate move entry.

    Args:
        candidate_move: KataGoの候補手データ
        root_score: ルートノードのスコア
        next_player: 次の手番（"B" or "W"）

    Returns:
        損失値（計算できない場合はNone）
    """
    if candidate_move.get("pointsLost") is not None:
        return float(candidate_move["pointsLost"])

    if candidate_move.get("relativePointsLost") is not None:
        return float(candidate_move["relativePointsLost"])

    if (
        root_score is not None
        and next_player is not None
        and candidate_move.get("scoreLead") is not None
    ):
        sign = 1 if next_player == "B" else -1
        return sign * (root_score - float(candidate_move["scoreLead"]))

    return None
