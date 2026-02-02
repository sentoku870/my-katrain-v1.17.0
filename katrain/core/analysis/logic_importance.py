"""Importance calculation functions.

PR #127: Phase B4 - logic_importance.py作成

logic.pyから抽出された重要度計算関連の関数。
- get_difficulty_modifier: 難易度に応じた重要度修正値を取得
- get_reliability_scale: 訪問数に基づく信頼度スケールを取得
- compute_importance_for_moves: 各手の重要度スコアを計算
- pick_important_moves: 重要局面を抽出
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, List, Optional, Set, Tuple

from katrain.core.analysis.models import (
    ConfidenceLevel,
    DEFAULT_IMPORTANT_MOVE_LEVEL,
    DIFFICULTY_MODIFIER_HARD,
    DIFFICULTY_MODIFIER_ONLY_MOVE,
    DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_BONUS,
    DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_THRESHOLD,
    EvalSnapshot,
    IMPORTANT_MOVE_SETTINGS_BY_LEVEL,
    ImportantMoveSettings,
    MoveEval,
    PositionDifficulty,
    RELIABILITY_SCALE_THRESHOLDS,
    STREAK_START_BONUS,
    SWING_MAGNITUDE_WEIGHT,
    get_canonical_loss_from_move,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Reliability and difficulty helpers
# =============================================================================


def get_difficulty_modifier(
    difficulty: PositionDifficulty | None,
    canonical_loss: float = 0.0,
) -> float:
    """
    Get the importance modifier based on position difficulty.

    Phase 23: ONLY_MOVE の緩和
    - HARD: +1.0 (difficult positions have higher learning value)
    - ONLY_MOVE: -1.0 (was -2.0, relaxed for learning value)
      - 大損失 (>= 2.0目) の場合: さらに +0.5 緩和 → 実質 -0.5
    - EASY/NORMAL/UNKNOWN/None: 0.0 (no modifier)

    Args:
        difficulty: 局面の難易度
        canonical_loss: 正規化された損失（目数、0以上）

    Returns:
        重要度への修正値
    """
    if difficulty is None:
        return 0.0
    if difficulty == PositionDifficulty.HARD:
        return DIFFICULTY_MODIFIER_HARD
    if difficulty == PositionDifficulty.ONLY_MOVE:
        modifier = DIFFICULTY_MODIFIER_ONLY_MOVE
        # 大損失なら緩和（一択でも大きなミスは学習価値あり）
        if canonical_loss >= DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_THRESHOLD:
            modifier += DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_BONUS
        return modifier
    return 0.0


def get_reliability_scale(root_visits: int) -> float:
    """
    Get the reliability scale factor based on visit count.

    Returns a value between 0.3 and 1.0:
    - visits >= 500: 1.0 (full confidence)
    - visits >= 200: 0.8
    - visits >= 100: 0.5
    - visits < 100: 0.3 (low confidence)
    """
    visits = root_visits or 0
    for threshold, scale in RELIABILITY_SCALE_THRESHOLDS:
        if visits >= threshold:
            return scale
    return 0.3  # Default minimum


# =============================================================================
# Importance calculation
# =============================================================================


def compute_importance_for_moves(
    moves: Iterable[MoveEval],
    *,
    streak_start_moves: set[int | None] | None = None,
    confidence_level: ConfidenceLevel | None = None,
) -> None:
    """
    各 MoveEval について重要度スコアを計算し、importance_score に格納する。

    Args:
        moves: 評価対象の手のリスト
        streak_start_moves: 連続ミス開始手番の集合（ボーナス付与用）
        confidence_level: 信頼度レベル（HIGH/MEDIUM/LOW）
    """
    # Default to HIGH if not specified
    if confidence_level is None:
        confidence_level = ConfidenceLevel.HIGH

    # Determine which components to use based on confidence
    use_all_components = confidence_level == ConfidenceLevel.HIGH
    use_swing = confidence_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    if streak_start_moves is None:
        streak_start_moves = set()

    for m in moves:
        # 1. Canonical loss (主成分) - always used
        canonical_loss = m.score_loss if m.score_loss is not None else 0.0
        canonical_loss = max(0.0, canonical_loss)

        # 2. Swing magnitude (ターニングポイント)
        swing_magnitude = 0.0
        if use_swing and m.score_before is not None and m.score_after is not None:
            score_sign_changed = (
                (m.score_before > 0) != (m.score_after > 0)
                or m.score_before == 0.0
                or m.score_after == 0.0
            )
            if score_sign_changed:
                swing_magnitude = abs(m.score_before - m.score_after)

        # 3. Difficulty modifier - only for HIGH confidence
        difficulty_modifier = 0.0
        if use_all_components:
            difficulty_modifier = get_difficulty_modifier(m.position_difficulty, canonical_loss)

        # 4. Streak start bonus - only for HIGH confidence
        streak_bonus = 0.0
        if use_all_components and m.move_number in streak_start_moves:
            streak_bonus = STREAK_START_BONUS

        # Compute base importance
        base_importance = (
            1.0 * canonical_loss +
            SWING_MAGNITUDE_WEIGHT * swing_magnitude +
            difficulty_modifier +
            streak_bonus
        )

        # Apply reliability scale
        reliability_scale = get_reliability_scale(m.root_visits)
        final_importance = base_importance * reliability_scale

        m.importance_score = max(0.0, final_importance)


def pick_important_moves(
    snapshot: EvalSnapshot,
    level: str = DEFAULT_IMPORTANT_MOVE_LEVEL,
    settings: ImportantMoveSettings | None = None,
    recompute: bool = True,
    streak_start_moves: set[int | None] | None = None,
    confidence_level: ConfidenceLevel | None = None,
) -> list[MoveEval]:
    """
    snapshot から重要局面の手数だけを抽出して返す。

    Args:
        snapshot: 評価スナップショット
        level: 重要度レベル（"easy", "normal", "strict"）
        settings: 重要局面設定（Noneの場合はlevelから決定）
        recompute: 重要度スコアを再計算するか
        streak_start_moves: 連続ミス開始手番の集合
        confidence_level: 信頼度レベル

    Returns:
        重要局面のリスト（手番順にソート済み）
    """
    if settings is None:
        settings = IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
            level, IMPORTANT_MOVE_SETTINGS_BY_LEVEL[DEFAULT_IMPORTANT_MOVE_LEVEL]
        )

    threshold = settings.importance_threshold
    max_moves = settings.max_moves

    moves = snapshot.moves
    if not moves:
        return []

    if recompute:
        compute_importance_for_moves(
            moves,
            streak_start_moves=streak_start_moves,
            confidence_level=confidence_level,
        )

    # 1) 通常ルート: importance_score ベース
    candidates: list[tuple[float, int, MoveEval]] = []
    for move in moves:
        importance = move.importance_score or 0.0
        if importance > threshold:
            candidates.append((importance, move.move_number, move))

    # 2) フォールバック
    if not candidates:
        def raw_score(m: MoveEval) -> float:
            score_term = abs(m.delta_score or 0.0)
            winrate_term = 50.0 * abs(m.delta_winrate or 0.0)
            pl_term = get_canonical_loss_from_move(m)
            base = score_term + winrate_term + pl_term
            base *= get_reliability_scale(m.root_visits)
            return base

        for move in moves:
            raw_sc = raw_score(move)
            if raw_sc > 0.0:
                candidates.append((raw_sc, move.move_number, move))

    # Sort and pick top
    candidates.sort(key=lambda x: (-x[0], x[1]))
    top = candidates[:max_moves]

    important_moves = sorted([m for _, _, m in top], key=lambda m: m.move_number)
    return important_moves
