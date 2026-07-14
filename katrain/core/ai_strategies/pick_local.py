"""LocalStrategy - proximity-weighted pick strategy.

Phase 172: Extracted from ``katrain.core.ai_strategies.pick`` for family
organization. Falls back to ``WeightedStrategy`` when there is no previous
move to anchor the locality calculation.
"""

from __future__ import annotations

import heapq

from katrain.core.ai.constants import AI_LOCAL
from katrain.core.ai_strategies.pick_base import PickBasedStrategy
from katrain.core.ai_strategies.policy import WeightedStrategy
from katrain.core.ai_strategies_base import generate_local_tenuki_weights, register_strategy
from katrain.core.constants import OUTPUT_DEBUG
from katrain.core.game import Move


@register_strategy(AI_LOCAL)
class LocalStrategy(PickBasedStrategy):
    """Local strategy - weights moves based on proximity to the last move"""

    def generate_move(self) -> tuple[Move, str]:
        # Handle the case where there's no previous move
        if not (self.cn.move and self.cn.move.coords):
            self.game.katrain.log(
                "[LocalStrategy] No previous move with valid coordinates found, falling back to WeightedStrategy",
                OUTPUT_DEBUG,
            )
            self.game.katrain.log(
                "[LocalStrategy] Using default weighted settings: pick_override=0.9, weaken_fac=1, lower_bound=0.02",
                OUTPUT_DEBUG,
            )
            return WeightedStrategy(
                self.game, {"pick_override": 0.9, "weaken_fac": 1, "lower_bound": 0.02}
            ).generate_move()

        return super().generate_move()

    def generate_weighted_coords(
        self,
        legal_policy_moves: list[tuple[float, Move | None]],
        policy_grid: list[list[float | None]],
        size: tuple[int, int],
    ) -> tuple[list[tuple[float, float, int, int]], str]:
        """Generate local-based weights"""
        self.game.katrain.log("[LocalStrategy] Generating local-based weights around previous move", OUTPUT_DEBUG)
        assert self.cn.move is not None, "Move cannot be None at this point"
        self.game.katrain.log(f"[LocalStrategy] Previous move: {self.cn.move.gtp()}", OUTPUT_DEBUG)
        self.game.katrain.log(f"[LocalStrategy] Variance setting: {self.settings['stddev']}", OUTPUT_DEBUG)
        weighted_coords, ai_thoughts = generate_local_tenuki_weights(
            AI_LOCAL, self.settings, policy_grid, self.cn, size
        )
        self.game.katrain.log(f"[LocalStrategy] Generated {len(weighted_coords)} weighted coordinates", OUTPUT_DEBUG)
        if weighted_coords:
            top5 = heapq.nlargest(5, weighted_coords, key=lambda t: t[0] * t[1])
            self.game.katrain.log("[LocalStrategy] Top 5 weighted coordinates (by policy*weight):", OUTPUT_DEBUG)
            for i, (pol, wt, x, y) in enumerate(top5):
                self.game.katrain.log(
                    f"[LocalStrategy] #{i + 1}: ({x},{y}) - policy={pol:.2%}, weight={wt}, combined={pol * wt:.2%}",
                    OUTPUT_DEBUG,
                )
        return weighted_coords, ai_thoughts
