"""Policy-based AI strategies.

Phase 158+: Extracted from ``katrain.core.ai`` for family-based organization.

Strategies:
- PolicyStrategy: plays the top policy move, falls back to WeightedStrategy
  during opening (configurable number of moves)
- WeightedStrategy: plays a policy-weighted random move above a lower bound,
  with a weakening factor for randomness
"""

from __future__ import annotations

from katrain.core.ai_strategies.basic import DefaultStrategy
from katrain.core.ai_strategies_base import AIStrategy, register_strategy
from katrain.core.constants import (
    AI_POLICY,
    AI_WEIGHTED,
    OUTPUT_DEBUG,
)
from katrain.core.game import Move
from katrain.core.utils import weighted_selection_without_replacement


@register_strategy(AI_POLICY)
class PolicyStrategy(AIStrategy):
    """Policy strategy - plays the top move suggested by policy network"""

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log("[PolicyStrategy] Starting move generation", OUTPUT_DEBUG)
        self.wait_for_analysis()

        # Ensure policy is available
        if not self.cn.policy:
            self.game.katrain.log(
                "[PolicyStrategy] No policy data available, falling back to DefaultStrategy", OUTPUT_DEBUG
            )
            return DefaultStrategy(self.game, self.settings).generate_move()

        policy_moves = self.cn.policy_ranking
        if policy_moves is None:
            self.game.katrain.log(
                "[PolicyStrategy] No policy ranking available, falling back to DefaultStrategy", OUTPUT_DEBUG
            )
            return DefaultStrategy(self.game, self.settings).generate_move()

        pass_policy = self.cn.policy[-1]
        self.game.katrain.log(f"[PolicyStrategy] Got {len(policy_moves)} policy moves", OUTPUT_DEBUG)
        self.game.katrain.log(f"[PolicyStrategy] Current move depth: {self.cn.depth}", OUTPUT_DEBUG)
        self.game.katrain.log(
            f"[PolicyStrategy] Opening moves setting: {self.settings.get('opening_moves', 0)}", OUTPUT_DEBUG
        )

        # Log top 5 policy moves
        self.game.katrain.log("[PolicyStrategy] Top 5 policy moves:", OUTPUT_DEBUG)
        for i, (prob, move) in enumerate(policy_moves[:5]):
            move_str = move.gtp() if move is not None else "None"
            self.game.katrain.log(f"[PolicyStrategy] #{i + 1}: {move_str} - {prob:.2%}", OUTPUT_DEBUG)

        self.game.katrain.log(f"[PolicyStrategy] Pass policy: {pass_policy:.2%}", OUTPUT_DEBUG)

        # Check for pass in top 5
        top_5_pass = any([polmove[1] is not None and polmove[1].is_pass for polmove in policy_moves[:5]])
        self.game.katrain.log(f"[PolicyStrategy] Pass in top 5: {top_5_pass}", OUTPUT_DEBUG)

        # Handle opening moves override
        if self.cn.depth <= self.settings.get("opening_moves", 0):
            self.game.katrain.log("[PolicyStrategy] In opening phase, using WeightedStrategy instead", OUTPUT_DEBUG)
            weighted_settings = {"pick_override": 0.9, "weaken_fac": 1, "lower_bound": 0.02}
            self.game.katrain.log(f"[PolicyStrategy] Weighted settings: {weighted_settings}", OUTPUT_DEBUG)
            return WeightedStrategy(self.game, weighted_settings).generate_move()

        # Check for pass in top 5
        if top_5_pass:
            aimove_opt = policy_moves[0][1]
            aimove = aimove_opt if aimove_opt is not None else Move(None)
            self.game.katrain.log(
                f"[PolicyStrategy] Playing top move {aimove.gtp()} because pass in top 5", OUTPUT_DEBUG
            )
            ai_thoughts = "Playing top one because one of them is pass."
            return aimove, ai_thoughts

        # Otherwise play top policy move
        aimove_opt = policy_moves[0][1]
        aimove = aimove_opt if aimove_opt is not None else Move(None)
        self.game.katrain.log(
            f"[PolicyStrategy] Playing top policy move {aimove.gtp()} with probability {policy_moves[0][0]:.2%}",
            OUTPUT_DEBUG,
        )
        ai_thoughts = f"Playing top policy move {aimove.gtp()}."

        self.game.katrain.log(f"[PolicyStrategy] Final decision: {aimove.gtp()}", OUTPUT_DEBUG)
        return aimove, ai_thoughts


@register_strategy(AI_WEIGHTED)
class WeightedStrategy(AIStrategy):
    """Weighted strategy - weights moves based on policy and a weakening factor"""

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log("[WeightedStrategy] Starting move generation", OUTPUT_DEBUG)
        self.wait_for_analysis()

        # Ensure policy is available
        if not self.cn.policy:
            self.game.katrain.log(
                "[WeightedStrategy] No policy data available, falling back to DefaultStrategy", OUTPUT_DEBUG
            )
            return DefaultStrategy(self.game, self.settings).generate_move()

        policy_moves = self.cn.policy_ranking
        if policy_moves is None:
            self.game.katrain.log(
                "[WeightedStrategy] No policy ranking available, falling back to DefaultStrategy", OUTPUT_DEBUG
            )
            return DefaultStrategy(self.game, self.settings).generate_move()

        pass_policy = self.cn.policy[-1]
        self.game.katrain.log(f"[WeightedStrategy] Got {len(policy_moves)} policy moves", OUTPUT_DEBUG)

        # Log top 5 policy moves
        self.game.katrain.log("[WeightedStrategy] Top 5 policy moves:", OUTPUT_DEBUG)
        for i, (prob, mv) in enumerate(policy_moves[:5]):
            mv_str = mv.gtp() if mv is not None else "None"
            self.game.katrain.log(f"[WeightedStrategy] #{i + 1}: {mv_str} - {prob:.2%}", OUTPUT_DEBUG)

        self.game.katrain.log(f"[WeightedStrategy] Pass policy: {pass_policy:.2%}", OUTPUT_DEBUG)

        # Check for pass in top 5
        top_5_pass = any([polmove[1] is not None and polmove[1].is_pass for polmove in policy_moves[:5]])
        self.game.katrain.log(f"[WeightedStrategy] Pass in top 5: {top_5_pass}", OUTPUT_DEBUG)

        # Get override threshold
        override = self.settings.get("pick_override", 0.0)
        self.game.katrain.log(f"[WeightedStrategy] Override threshold: {override:.2%}", OUTPUT_DEBUG)

        # Check if we should override with top move
        override_move, override_thoughts = self.should_play_top_move(policy_moves, top_5_pass, override=override)

        if override_move:
            self.game.katrain.log(f"[WeightedStrategy] Using override move: {override_move.gtp()}", OUTPUT_DEBUG)
            return override_move, override_thoughts

        # Apply weighted policy move selection
        lower_bound = self.settings.get("lower_bound", 0.02)
        weaken_fac = self.settings.get("weaken_fac", 1.0)

        self.game.katrain.log(
            f"[WeightedStrategy] Using weighted selection with lower_bound={lower_bound:.2%}, weaken_fac={weaken_fac}",
            OUTPUT_DEBUG,
        )

        # Generate list of weighted coordinates
        weighted_coords = [
            (pv, pv ** (1 / weaken_fac), mv)
            for pv, mv in policy_moves
            if mv is not None and pv > lower_bound and not mv.is_pass
        ]

        self.game.katrain.log(f"[WeightedStrategy] Found {len(weighted_coords)} moves above lower bound", OUTPUT_DEBUG)

        move: Move
        if weighted_coords:
            self.game.katrain.log("[WeightedStrategy] Performing weighted selection", OUTPUT_DEBUG)
            top = weighted_selection_without_replacement(weighted_coords, 1)[0]
            move = top[2]
            prob = top[0]

            self.game.katrain.log(
                f"[WeightedStrategy] Selected move {move.gtp()} with probability {prob:.2%}", OUTPUT_DEBUG
            )
            ai_thoughts = f"Playing policy-weighted random move {move.gtp()} ({prob:.1%}) from {len(weighted_coords)} moves above lower_bound of {lower_bound:.1%}."
        else:
            move_opt = policy_moves[0][1]
            move = move_opt if move_opt is not None else Move(None)
            self.game.katrain.log(
                f"[WeightedStrategy] No moves above lower bound, playing top policy move {move.gtp()}", OUTPUT_DEBUG
            )
            ai_thoughts = f"Playing top policy move because no non-pass move > above lower_bound of {lower_bound:.1%}."

        self.game.katrain.log(f"[WeightedStrategy] Final decision: {move.gtp()}", OUTPUT_DEBUG)
        return move, ai_thoughts
