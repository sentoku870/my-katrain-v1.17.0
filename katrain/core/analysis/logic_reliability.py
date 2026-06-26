"""Reliability functions, MoveEval creation, and confidence level computation.

Phase 144-C: Extracted from logic.py (1494 lines → 6 focused modules).

Contains:
- compute_effective_threshold: Compute effective reliability threshold
- is_reliable_from_visits: Simple reliability check based on visits
- compute_reliability_stats: Compute reliability statistics for a move set
- move_eval_from_node: Create a MoveEval from a GameNode
- (Re-exports) get_difficulty_modifier, get_reliability_scale from logic_importance
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from katrain.core.analysis.models import (
    MIN_COVERAGE_MOVES,
    RELIABILITY_RATIO,
    RELIABILITY_VISITS_THRESHOLD,
    _CONFIDENCE_THRESHOLDS,
    ConfidenceLevel,
    MoveEval,
    PositionDifficulty,
    ReliabilityStats,
)
from katrain.core.analysis.models.move_eval import get_canonical_loss_from_move

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode

# Re-export for backward compatibility
from katrain.core.analysis.logic_importance import (  # noqa: E402
    get_difficulty_modifier,
    get_reliability_scale,
)


# =============================================================================
# GameNode bridge
# =============================================================================


def move_eval_from_node(node: GameNode) -> MoveEval:
    """
    KaTrain の GameNode 1 個から MoveEval を生成する。

    - GameNode.comment() 等の文字列には依存せず、
      数値的な評価値だけを見るようにする。
    - before/after/delta は snapshot_from_nodes 側で埋める。
    """
    # Lazy import to avoid circular dependency with logic_difficulty
    from katrain.core.analysis.logic_difficulty import assess_position_difficulty_from_parent

    move = getattr(node, "move", None)
    player = getattr(move, "player", None)
    gtp = move.gtp() if move is not None and hasattr(move, "gtp") else None

    score = getattr(node, "score", None)
    winrate = getattr(node, "winrate", None)
    points_lost = getattr(node, "points_lost", None)
    realized_points_lost = getattr(node, "parent_realized_points_lost", None)
    root_visits = getattr(node, "root_visits", 0) or 0

    # Position difficulty 計算（親ノードの候補手から判定）
    difficulty, difficulty_score = assess_position_difficulty_from_parent(node)

    # move_number の取得
    _move_number = getattr(node, "depth", None)
    if _move_number is None:
        _move_number = getattr(node, "move_number", 0) or 0

    return MoveEval(
        move_number=_move_number,
        player=player,
        gtp=gtp,
        score_before=None,
        score_after=score,
        delta_score=None,
        winrate_before=None,
        winrate_after=winrate,
        delta_winrate=None,
        points_lost=points_lost,
        realized_points_lost=realized_points_lost,
        root_visits=int(root_visits),
        position_difficulty=difficulty,
        position_difficulty_score=difficulty_score,
    )


# =============================================================================
# Reliability functions
# =============================================================================


def compute_effective_threshold(
    target_visits: int | None = None,
    max_threshold: int = RELIABILITY_VISITS_THRESHOLD,
    ratio: float = RELIABILITY_RATIO,
) -> int:
    """Compute effective reliability threshold based on target visits.

    Formula: max(1, min(max_threshold, round(target_visits * ratio)))

    When target_visits=100 and ratio=0.9: threshold=90
    When target_visits=300 and ratio=0.9: threshold=200 (capped)
    When target_visits=None or <=0: threshold=max_threshold (default 200)

    Args:
        target_visits: Configured/selected visits value (or None)
        max_threshold: Maximum threshold cap (default: 200)
        ratio: Fraction of target_visits to use (default: 0.9)

    Returns:
        Effective threshold for reliability determination.
    """
    if target_visits is not None and target_visits > 0:
        relative = max(1, round(target_visits * ratio))
        return min(max_threshold, relative)
    return max_threshold


def is_reliable_from_visits(
    root_visits: int,
    *,
    threshold: int = RELIABILITY_VISITS_THRESHOLD,
    target_visits: int | None = None,
) -> bool:
    """
    visits のみを根拠にした簡易信頼度判定。

    - threshold 未満は False（保守的）。
    - target_visits が指定された場合、effective threshold を使用。
    """
    effective = compute_effective_threshold(target_visits, threshold)
    return int(root_visits or 0) >= effective


def compute_reliability_stats(
    moves: Iterable[MoveEval],
    *,
    threshold: int = RELIABILITY_VISITS_THRESHOLD,
    target_visits: int | None = None,
) -> ReliabilityStats:
    """
    Compute reliability statistics for a collection of moves.

    Args:
        moves: Iterable of MoveEval objects
        threshold: Max visits threshold for reliability (default: RELIABILITY_VISITS_THRESHOLD=200)
        target_visits: Target/configured visits (for relative threshold calculation)

    Returns:
        ReliabilityStats with counts, percentages, and effective_threshold
    """
    effective = compute_effective_threshold(target_visits, threshold)
    stats = ReliabilityStats()
    stats.effective_threshold = effective

    for m in moves:
        stats.total_moves += 1
        visits = m.root_visits or 0

        if visits == 0:
            stats.zero_visits_count += 1
            stats.low_confidence_count += 1
        elif visits >= effective:
            stats.reliable_count += 1
            stats.total_visits += visits
            stats.moves_with_visits += 1
        else:
            stats.low_confidence_count += 1
            stats.total_visits += visits
            stats.moves_with_visits += 1

        # Track max visits
        if visits > stats.max_visits:
            stats.max_visits = visits

    return stats


# =============================================================================
# Confidence level
# =============================================================================


def compute_confidence_level(
    moves: Iterable[MoveEval],
    *,
    min_coverage: int = MIN_COVERAGE_MOVES,
    threshold: int = RELIABILITY_VISITS_THRESHOLD,
) -> ConfidenceLevel:
    """Compute confidence level for a set of moves.

    The confidence level determines how much trust we can place in the analysis
    results. It affects section visibility and wording in output.

    Args:
        moves: Iterable of MoveEval objects
        min_coverage: Minimum moves_with_visits required (default: 5)
        threshold: Visits threshold for reliability (default: RELIABILITY_VISITS_THRESHOLD)

    Returns:
        ConfidenceLevel (HIGH, MEDIUM, or LOW)

    Algorithm:
        1. If moves_with_visits < min_coverage: return LOW (coverage guard)
        2. HIGH if: (reliability_pct >= 50% OR avg_visits >= 400)
        3. MEDIUM if: (reliability_pct >= 30% OR avg_visits >= 150)
        4. Otherwise: LOW
    """
    stats = compute_reliability_stats(moves, threshold=threshold)

    # Coverage guard: too few analyzed moves = LOW
    if stats.moves_with_visits < min_coverage:
        return ConfidenceLevel.LOW

    reliability = stats.reliability_pct
    avg_visits = stats.avg_visits

    # HIGH: reliability >= 50% OR avg_visits >= 400
    if (
        reliability >= _CONFIDENCE_THRESHOLDS["high_reliability_pct"]
        or avg_visits >= _CONFIDENCE_THRESHOLDS["high_avg_visits"]
    ):
        return ConfidenceLevel.HIGH

    # MEDIUM: reliability >= 30% OR avg_visits >= 150
    if (
        reliability >= _CONFIDENCE_THRESHOLDS["medium_reliability_pct"]
        or avg_visits >= _CONFIDENCE_THRESHOLDS["medium_avg_visits"]
    ):
        return ConfidenceLevel.MEDIUM

    return ConfidenceLevel.LOW
