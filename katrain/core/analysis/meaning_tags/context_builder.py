"""Build ClassificationContext from GameNode analysis data.

Phase 148-B'1: Supply move_distance and score_stdev to ClassificationContext.
Phase 148-B'2: Also supply best_move_policy / actual_move_policy via
               moveInfos ``prior`` (KataGo policy prior).

Previously all production callers passed only ``total_moves`` to
ClassificationContext, leaving the other fields as None, which silently
skipped the related tag rules (close/far move, high uncertainty, trap,
very-low-policy, certain-best, etc.).
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


def _get_best_move_and_policy_from_node(node: GameNode) -> tuple[str | None, float | None]:
    """Extract the best move (GTP) and its policy prior from moveInfos.

    Best move = the moveInfo with the smallest ``order`` (KataGo strength rank).

    Returns:
        (best_gtp, best_policy). Either/both may be None when unavailable.
    """
    if not getattr(node, "analysis_exists", False):
        return None, None
    analysis = getattr(node, "analysis", None)
    if analysis is None:
        return None, None
    move_infos = analysis.get("moveInfos") or []
    if not move_infos:
        return None, None
    best = min(move_infos, key=lambda m: m.get("order", 999))
    move = best.get("move")
    prior = best.get("prior")
    best_gtp = str(move) if move is not None else None
    best_policy = float(prior) if prior is not None else None
    return best_gtp, best_policy


def _get_actual_move_policy_from_node(node: GameNode, actual_gtp: str) -> float | None:
    """Extract the policy prior of the actually-played move from moveInfos.

    Returns None when the move is not among the candidate moveInfos (e.g. a
    gross blunder that fell outside KataGo's candidate list), in which case
    policy-dependent tag rules are skipped for that move.
    """
    if not getattr(node, "analysis_exists", False):
        return None
    analysis = getattr(node, "analysis", None)
    if analysis is None:
        return None
    for mi in analysis.get("moveInfos") or []:
        if mi.get("move") == actual_gtp:
            prior = mi.get("prior")
            return float(prior) if prior is not None else None
    return None


def build_classification_context_from_node(
    node: GameNode | None,
    actual_gtp: str | None,
    total_moves: int | None = None,
) -> ClassificationContext:
    """Build a ClassificationContext from a GameNode.

    Phase 148-B'1+B'2: supplies ``move_distance``, ``score_stdev``,
    ``best_move_policy`` and ``actual_move_policy`` when available.

    Args:
        node: GameNode for the move (its moveInfos / root analysis are used).
            None when the node cannot be resolved; returns a total_moves-only context.
        actual_gtp: GTP coordinate of the actual move played (e.g. "D4").
        total_moves: Total moves in the game (for endgame detection).

    Returns:
        ClassificationContext populated with distance/stdev/policy when available.
    """
    if node is None:
        return ClassificationContext(total_moves=total_moves)

    score_stdev = _get_score_stdev_from_node(node)
    best_gtp, best_move_policy = _get_best_move_and_policy_from_node(node)
    actual_move_policy: float | None = None
    if actual_gtp:
        actual_move_policy = _get_actual_move_policy_from_node(node, actual_gtp)

    move_distance: int | None = None
    if best_gtp and is_classifiable_move(actual_gtp):
        move_distance = compute_move_distance(best_gtp, actual_gtp)

    return ClassificationContext(
        best_move_policy=best_move_policy,
        actual_move_policy=actual_move_policy,
        move_distance=move_distance,
        score_stdev=score_stdev,
        total_moves=total_moves,
    )
