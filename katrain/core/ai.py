"""AI strategy implementations for KaTrain.

This module contains all AI strategy classes for generating moves.

Module structure (Phase B5 refactoring):
- ai_strategies_base.py: Base class (AIStrategy) and utilities
- ai.py (this file): All strategy implementations

Strategy categories:
- Basic: DefaultStrategy, HandicapStrategy, AntimirrorStrategy, JigoStrategy
- Score-based: ScoreLossStrategy
- Ownership-based: OwnershipBaseStrategy, SimpleOwnershipStrategy, SettleStonesStrategy
- Policy-based: PolicyStrategy, WeightedStrategy
- Pick-based: PickBasedStrategy, PickStrategy, RankStrategy, InfluenceStrategy,
              TerritoryStrategy, LocalStrategy, TenukiStrategy
- Human-style: HumanStyleStrategy

Usage:
    from katrain.core.ai import STRATEGY_REGISTRY, generate_ai_move
    strategy_class = STRATEGY_REGISTRY[strategy_name]
    strategy = strategy_class(game, ai_settings)
    move, thoughts = strategy.generate_move()
"""

import math
from typing import Any, cast

# =============================================================================
# Base classes and utilities (extracted to ai_strategies_base.py, re-exported)
# =============================================================================
from katrain.core.ai_strategies_base import (
    # Registry
    STRATEGY_REGISTRY,
    # Base class
    interp1d,
    interp2d,
)
from katrain.core.constants import (
    ADDITIONAL_MOVE_ORDER,
    AI_ACCURACY_DECAY_BASE,
    AI_DEFAULT,
    AI_HANDICAP,
    AI_HUMAN,
    AI_INFLUENCE,
    AI_INFLUENCE_ELO_GRID,
    AI_JIGO,
    AI_LOCAL,
    AI_LOCAL_ELO_GRID,
    AI_PICK,
    AI_PICK_ELO_GRID,
    AI_PRO,
    AI_RANK,
    AI_SCORELOSS,
    AI_SCORELOSS_ELO,
    AI_STRENGTH,
    AI_TENUKI,
    AI_TENUKI_ELO_GRID,
    AI_TERRITORY,
    AI_TERRITORY_ELO_GRID,
    AI_WEIGHTED,
    AI_WEIGHTED_ELO,
    CALIBRATED_RANK_ELO,
    OUTPUT_DEBUG,
)
from katrain.core.game import Game, GameNode, Move
from katrain.core.utils import evaluation_class


def ai_rank_estimation(strategy: str, settings: dict[str, Any]) -> float:
    if strategy in [AI_DEFAULT, AI_HANDICAP, AI_JIGO, AI_PRO]:
        return 9.0
    if strategy == AI_RANK:
        return 1 - float(settings["kyu_rank"])
    if strategy == AI_HUMAN:
        return 1 - float(settings["human_kyu_rank"])

    elo: float = 0.0
    if strategy in [AI_WEIGHTED, AI_SCORELOSS, AI_LOCAL, AI_TENUKI, AI_TERRITORY, AI_INFLUENCE, AI_PICK]:
        if strategy == AI_WEIGHTED:
            elo = interp1d(AI_WEIGHTED_ELO, settings["weaken_fac"])
        if strategy == AI_SCORELOSS:
            # Convert int ELO values to float for type compatibility
            scoreloss_elo: list[tuple[float, float]] = [(x, float(y)) for x, y in AI_SCORELOSS_ELO]
            elo = interp1d(scoreloss_elo, settings["strength"])
        Interp2DGrid = tuple[list[float], list[float], list[list[float]]]
        if strategy == AI_PICK:
            elo = interp2d(cast(Interp2DGrid, tuple(AI_PICK_ELO_GRID)), settings["pick_frac"], settings["pick_n"])
        if strategy == AI_LOCAL:
            elo = interp2d(cast(Interp2DGrid, tuple(AI_LOCAL_ELO_GRID)), settings["pick_frac"], settings["pick_n"])
        if strategy == AI_TENUKI:
            elo = interp2d(cast(Interp2DGrid, tuple(AI_TENUKI_ELO_GRID)), settings["pick_frac"], settings["pick_n"])
        if strategy == AI_TERRITORY:
            elo = interp2d(cast(Interp2DGrid, tuple(AI_TERRITORY_ELO_GRID)), settings["pick_frac"], settings["pick_n"])
        if strategy == AI_INFLUENCE:
            elo = interp2d(cast(Interp2DGrid, tuple(AI_INFLUENCE_ELO_GRID)), settings["pick_frac"], settings["pick_n"])

        # Convert CALIBRATED_RANK_ELO to proper type
        calibrated_elo: list[tuple[float, float]] = [(x, float(y)) for x, y in CALIBRATED_RANK_ELO]
        kyu = interp1d(calibrated_elo, elo)
        return 1 - kyu
    else:
        return float(AI_STRENGTH[strategy])


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

# =============================================================================
# Strategy implementations have been extracted to ai_strategies/ subpackage
# (Phase 158+: family-based organization). Importing the subpackage
# populates STRATEGY_REGISTRY via @register_strategy decorators.
# =============================================================================
from katrain.core.ai_strategies import (  # noqa: F401  (registry side-effect)
    AntimirrorStrategy,
    DefaultStrategy,
    HandicapStrategy,
    HumanStyleStrategy,
    InfluenceStrategy,
    JigoStrategy,
    LocalStrategy,
    OwnershipBaseStrategy,
    PickBasedStrategy,
    PickStrategy,
    PolicyStrategy,
    RankStrategy,
    ScoreLossStrategy,
    SettleStonesStrategy,
    SimpleOwnershipStrategy,
    TenukiStrategy,
    TerritoryStrategy,
    WeightedStrategy,
)


def generate_ai_move(game: Game, ai_mode: str, ai_settings: dict[str, Any]) -> tuple[Move, GameNode]:
    """Generate a move using the selected AI strategy"""
    game.katrain.log(f"Generate AI move called with mode: {ai_mode}", OUTPUT_DEBUG)

    # Create the appropriate strategy based on mode

    strategy = STRATEGY_REGISTRY[ai_mode](game, ai_settings)

    # Generate the move
    game.katrain.log(f"Generating move using {strategy.__class__.__name__}", OUTPUT_DEBUG)
    move, ai_thoughts = strategy.generate_move()

    # Play the move and return
    game.katrain.log(f"Playing move {move.gtp()} and creating game node", OUTPUT_DEBUG)
    played_node = game.play(move)
    game.katrain.log(f"AI thoughts: {ai_thoughts}", OUTPUT_DEBUG)
    played_node.ai_thoughts = ai_thoughts

    game.katrain.log(f"Move generation complete: {move.gtp()}", OUTPUT_DEBUG)
    return move, played_node


# =============================================================================
#
