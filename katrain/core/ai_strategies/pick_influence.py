"""InfluenceStrategy - edge-distance-weighted pick strategy.

Phase 172: Extracted from ``katrain.core.ai_strategies.pick`` for family
organization. Re-uses ``generate_influence_territory_weights`` with the
``AI_INFLUENCE`` mode to favor moves far from the board edges.
"""

from __future__ import annotations

import heapq

from katrain.core.ai.constants import AI_INFLUENCE
from katrain.core.ai_strategies.pick_base import PickBasedStrategy
from katrain.core.ai_strategies_base import generate_influence_territory_weights, register_strategy
from katrain.core.constants import OUTPUT_DEBUG
from katrain.core.game import Move


@register_strategy(AI_INFLUENCE)
class InfluenceStrategy(PickBasedStrategy):
    """Influence strategy - weights moves based on influence (distance from edge)"""

    def generate_weighted_coords(
        self,
        legal_policy_moves: list[tuple[float, Move | None]],
        policy_grid: list[list[float | None]],
        size: tuple[int, int],
    ) -> tuple[list[tuple[float, float, int, int]], str]:
        """Generate influence-based weights"""
        self.game.katrain.log("[InfluenceStrategy] Generating influence-based weights", OUTPUT_DEBUG)
        self.game.katrain.log(
            f"[InfluenceStrategy] Settings: threshold={self.settings['threshold']}, line_weight={self.settings['line_weight']}",
            OUTPUT_DEBUG,
        )
        weighted_coords, ai_thoughts = generate_influence_territory_weights(
            AI_INFLUENCE, self.settings, policy_grid, size
        )
        self.game.katrain.log(
            f"[InfluenceStrategy] Generated {len(weighted_coords)} weighted coordinates", OUTPUT_DEBUG
        )
        if weighted_coords:
            top5 = heapq.nlargest(5, weighted_coords, key=lambda t: t[0] * t[1])
            self.game.katrain.log("[InfluenceStrategy] Top 5 weighted coordinates (by policy*weight):", OUTPUT_DEBUG)
            for i, (pol, wt, x, y) in enumerate(top5):
                self.game.katrain.log(
                    f"[InfluenceStrategy] #{i + 1}: ({x},{y}) - policy={pol:.2%}, weight={wt}, combined={pol * wt:.2%}",
                    OUTPUT_DEBUG,
                )
        return weighted_coords, ai_thoughts
