"""Build ClassificationContext from GameNode analysis data.

Phase 148-B'1: Supply move_distance and score_stdev to ClassificationContext
so that distance/stdev-dependent meaning tags fire correctly.

Previously all production callers passed only ``total_moves`` to
ClassificationContext, leaving move_distance / score_stdev (and policy) as
None, which silently skipped the related tag rules.

policy (best_move_policy / actual_move_policy) is intentionally left as None
here and will be populated in Phase 148-B'2 via moveInfos policyPrior.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core.analysis.meaning_tags.classifier import (
    ClassificationContext,
    compute_move_distance,
    is_classifiable_move,
)

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode
else:
    GameNode = Any


def _get_score_stdev_from_node(node: GameNode) -> float | None:
    """Extract scoreStdev from node analysis.

    KataGo: node.analysis["root"]["scoreStdev"]
    Leela Zero / unanalyzed: None
    """
    if not getattr(node, "analysis_exists", False):
        return None
    analysis = getattr(node, "analysis", None)
    if analysis is None:
        return None
    root_info = analysis.get("root")
    if root_info is None:
        return None
    sd = root_info.get("scoreStdev")
    return float(sd) if sd is not None else None


def _get_best_move_gtp_from_node(node: GameNode) -> str | None:
    """Extract the best move GTP coordinate from moveInfos (smallest order)."""
    if not getattr(node, "analysis_exists", False):
        return None
    analysis = getattr(node, "analysis", None)
    if analysis is None:
        return None
    move_infos = analysis.get("moveInfos") or []
    if not move_infos:
        return None
    best = min(move_infos, key=lambda m: m.get("order", 999))
    move = best.get("move")
    return str(move) if move is not None else None


def build_classification_context_from_node(
    node: GameNode | None,
    actual_gtp: str | None,
    total_moves: int | None = None,
) -> ClassificationContext:
    """Build a ClassificationContext from a GameNode.

    Phase 148-B'1: supplies ``move_distance`` and ``score_stdev``.
    ``best_move_policy`` / ``actual_move_policy`` remain None (B'2 will extend).

    Args:
        node: GameNode for the move (parent candidate_moves / analysis used).
            None when the node cannot be resolved; returns a total_moves-only context.
        actual_gtp: GTP coordinate of the actual move played (e.g. "D4").
        total_moves: Total moves in the game (for endgame detection).

    Returns:
        ClassificationContext populated with distance/stdev when available.
    """
    if node is None:
        return ClassificationContext(total_moves=total_moves)

    score_stdev = _get_score_stdev_from_node(node)
    best_gtp = _get_best_move_gtp_from_node(node)
    move_distance: int | None = None
    if best_gtp and is_classifiable_move(actual_gtp):
        move_distance = compute_move_distance(best_gtp, actual_gtp)

    return ClassificationContext(
        move_distance=move_distance,
        score_stdev=score_stdev,
        total_moves=total_moves,
    )
