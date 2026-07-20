"""AI subsystem for KaTrain.

Phase 280: Slimmed down to only the two survivor strategies
(`ai:default` / `ai:handicap`). Module structure remains:
- ``ai_strategies_base.py``: Base class (`AIStrategy`), `STRATEGY_REGISTRY`,
  `register_strategy` decorator.
- ``ai_strategies/`` subpackage: Concrete strategy classes (only `basic.py`
  with `DefaultStrategy` / `HandicapStrategy` now).

Public API:
    from katrain.core.ai import STRATEGY_REGISTRY, generate_ai_move
    strategy_class = STRATEGY_REGISTRY[strategy_name]
    strategy = strategy_class(game, ai_settings)
    move, thoughts = strategy.generate_move()
"""

import math
from typing import Any

from katrain.core.ai.constants import (
    AI_ACCURACY_DECAY_BASE,
    AI_STRATEGIES,
)
from katrain.core.ai_strategies_base import (
    STRATEGY_REGISTRY,
    register_strategy,  # noqa: F401  (re-exported for back-compat)
)
from katrain.core.constants import ADDITIONAL_MOVE_ORDER, OUTPUT_DEBUG
from katrain.core.game import Game, GameNode, Move
from katrain.core.utils import evaluation_class


def ai_rank_estimation(strategy: str, settings: dict[str, Any]) -> float:
    """Estimate the dan rank for a given AI strategy and its settings.

    Phase 280: After the strategy slim-down, both remaining strategies report
    a fixed strength (9 dan) without interpolation. Hook is preserved so
    the GUI and tests can still call it.
    """
    del settings  # unused; kept for API compatibility
    if strategy in AI_STRATEGIES:
        return 9.0
    return 9.0


def game_report(
    game: "Game",
    thresholds: list[float],
    depth_filter: tuple[float, float] | None = None,
) -> tuple[dict[str, dict[str, float]], list[dict[str, int]], dict[str, list[float]]]:
    cn: GameNode = game.current_node
    nodes: list[GameNode] = [n for n in cn.nodes_from_root if isinstance(n, GameNode)]
    while cn.children:  # main branch
        child = cn.children[0]
        if isinstance(child, GameNode):
            cn = child
            nodes.append(cn)
        else:
            break

    x, y = game.board_size
    depth_filter_list = [math.ceil(board_frac * x * y) for board_frac in depth_filter or (0, 1e9)]
    nodes = [n for n in nodes if n.move and not n.is_root and depth_filter_list[0] <= n.depth < depth_filter_list[1]]
    histogram: list[dict[str, int]] = [{"B": 0, "W": 0} for _ in thresholds]
    ai_top_move_count: dict[str, int] = {"B": 0, "W": 0}
    ai_approved_move_count: dict[str, int] = {"B": 0, "W": 0}
    player_ptloss: dict[str, list[float]] = {"B": [], "W": []}
    weights: dict[str, list[tuple[float, float]]] = {"B": [], "W": []}

    for n in nodes:
        points_lost = n.points_lost
        if points_lost is None:
            continue
        else:
            points_lost = max(0.0, points_lost)
        bucket = len(thresholds) - 1 - evaluation_class(points_lost, thresholds)
        player_ptloss[n.player].append(points_lost)
        histogram[bucket][n.player] += 1

        parent = n.parent
        if parent is None or not isinstance(parent, GameNode):
            continue

        cands = parent.candidate_moves
        filtered_cands = [d for d in cands if d["order"] < ADDITIONAL_MOVE_ORDER and "prior" in d]
        weight = min(
            1.0,
            sum([max(d["pointsLost"], 0) * d["prior"] for d in filtered_cands])
            / (sum(d["prior"] for d in filtered_cands) or 1e-6),
        )  # complexity capped at 1
        # adj_weight between 0.05 - 1, dependent on difficulty and points lost
        adj_weight = max(0.05, min(1.0, max(weight, points_lost / 4)))
        weights[n.player].append((weight, adj_weight))

        move = n.move
        if move is None:
            continue

        if parent.analysis_complete:
            ai_top_move_count[n.player] += int(cands[0]["move"] == move.gtp())
            ai_approved_move_count[n.player] += int(
                move.gtp()
                in [d["move"] for d in filtered_cands if d["order"] == 0 or (d["pointsLost"] < 0.5 and d["order"] < 5)]
            )

    wt_loss = {
        bw: sum(s * aw for s, (w, aw) in zip(player_ptloss[bw], weights[bw], strict=False))
        / (sum(aw for _, aw in weights[bw]) or 1e-6)
        for bw in "BW"
    }
    sum_stats = {
        bw: (
            {
                "accuracy": 100 * AI_ACCURACY_DECAY_BASE ** wt_loss[bw],
                "complexity": sum(w for w, aw in weights[bw]) / len(player_ptloss[bw]),
                "mean_ptloss": sum(player_ptloss[bw]) / len(player_ptloss[bw]),
                "weighted_ptloss": wt_loss[bw],
                "ai_top_move": ai_top_move_count[bw] / len(player_ptloss[bw]),
                "ai_top5_move": ai_approved_move_count[bw] / len(player_ptloss[bw]),
            }
            if len(player_ptloss[bw]) > 0
            else {}
        )
        for bw in "BW"
    }
    return sum_stats, histogram, player_ptloss


# =============================================================================
# Strategy implementations have been extracted to ai_strategies/ subpackage.
# Importing it populates STRATEGY_REGISTRY via @register_strategy decorators.
# =============================================================================
from katrain.core.ai_strategies import (  # noqa: F401, E402  (registry side-effect)
    DefaultStrategy,
    HandicapStrategy,
)


def generate_ai_move(game: Game, ai_mode: str, ai_settings: dict[str, Any]) -> tuple[Move, GameNode]:
    """Generate a move using the selected AI strategy"""
    game.katrain.log(f"Generate AI move called with mode: {ai_mode}", OUTPUT_DEBUG)

    strategy = STRATEGY_REGISTRY[ai_mode](game, ai_settings)

    game.katrain.log(f"Generating move using {strategy.__class__.__name__}", OUTPUT_DEBUG)
    move, ai_thoughts = strategy.generate_move()

    game.katrain.log(f"Playing move {move.gtp()} and creating game node", OUTPUT_DEBUG)
    played_node = game.play(move)
    game.katrain.log(f"AI thoughts: {ai_thoughts}", OUTPUT_DEBUG)
    played_node.ai_thoughts = ai_thoughts

    game.katrain.log(f"Move generation complete: {move.gtp()}", OUTPUT_DEBUG)
    return move, played_node


__all__ = [
    "STRATEGY_REGISTRY",
    "ai_rank_estimation",
    "game_report",
    "generate_ai_move",
]
