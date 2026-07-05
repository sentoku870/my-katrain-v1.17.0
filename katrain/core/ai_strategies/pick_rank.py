"""RankStrategy - rank-calibrated pick-based AI strategy.

Phase 172: Extracted from ``katrain.core.ai_strategies.pick`` for family
organization. Calibrates the number of candidate moves and the override
thresholds using the player's kyu rank from settings.
"""

from __future__ import annotations

import math

from katrain.core.ai_strategies.pick_base import PickBasedStrategy
from katrain.core.ai_strategies_base import register_strategy
from katrain.core.constants import AI_RANK, OUTPUT_DEBUG
from katrain.core.game import Move


@register_strategy(AI_RANK)
class RankStrategy(PickBasedStrategy):
    """Rank strategy - similar to Pick but calibrated based on rank"""

    def get_n_moves(self, legal_policy_moves: list[tuple[float, Move | None]]) -> int:
        """Calculate n_moves based on rank"""
        self.game.katrain.log("[RankStrategy] Calculating n_moves based on rank", OUTPUT_DEBUG)

        size = self.game.board_size
        board_squares = size[0] * size[1]
        norm_leg_moves = len(legal_policy_moves) / board_squares

        self.game.katrain.log(f"[RankStrategy] Board squares: {board_squares}", OUTPUT_DEBUG)
        self.game.katrain.log(f"[RankStrategy] Legal moves: {len(legal_policy_moves)}", OUTPUT_DEBUG)
        self.game.katrain.log(f"[RankStrategy] Normalized legal moves: {norm_leg_moves:.4f}", OUTPUT_DEBUG)
        self.game.katrain.log(f"[RankStrategy] Kyu rank: {self.settings['kyu_rank']}", OUTPUT_DEBUG)

        # Calculate n_moves using the rank formula
        orig_calib_avemodrank = 0.063015 + 0.7624 * board_squares / (
            10 ** (-0.05737 * self.settings["kyu_rank"] + 1.9482)
        )

        self.game.katrain.log(
            f"[RankStrategy] Original calibrated average mod rank: {orig_calib_avemodrank:.4f}", OUTPUT_DEBUG
        )

        exponent_term = (
            3.002 * norm_leg_moves * norm_leg_moves - norm_leg_moves - 0.034889 * self.settings["kyu_rank"] - 0.5097
        )
        self.game.katrain.log(f"[RankStrategy] Exponent term: {exponent_term:.4f}", OUTPUT_DEBUG)

        modified_calib_avemodrank = (
            0.3931 + 0.6559 * norm_leg_moves * math.exp(-1 * exponent_term**2) - 0.01093 * self.settings["kyu_rank"]
        ) * orig_calib_avemodrank

        self.game.katrain.log(
            f"[RankStrategy] Modified calibrated average mod rank: {modified_calib_avemodrank:.4f}", OUTPUT_DEBUG
        )

        denominator = 1.31165 * (modified_calib_avemodrank + 1) - 0.082653
        self.game.katrain.log(f"[RankStrategy] Denominator: {denominator:.4f}", OUTPUT_DEBUG)

        n_moves_float = board_squares * norm_leg_moves / denominator
        n_moves: int = max(1, int(round(n_moves_float)))

        self.game.katrain.log(f"[RankStrategy] Calculated n_moves: {n_moves}", OUTPUT_DEBUG)

        return n_moves

    def should_play_top_move(
        self,
        policy_moves: list[tuple[float, Move | None]],
        top_5_pass: bool,
        override: float = 0.0,
        overridetwo: float = 1.0,
    ) -> tuple[Move | None, str]:
        """Special override logic for rank-based"""
        self.game.katrain.log("[RankStrategy] Calculating special override thresholds based on rank", OUTPUT_DEBUG)

        size = self.game.board_size
        board_squares = size[0] * size[1]
        legal_policy_moves = [(pol, mv) for pol, mv in policy_moves if mv is not None and not mv.is_pass and pol > 0]

        # Parameters for calculating the overrides
        self.game.katrain.log(f"[RankStrategy] Board squares: {board_squares}", OUTPUT_DEBUG)
        self.game.katrain.log(f"[RankStrategy] Legal non-pass moves: {len(legal_policy_moves)}", OUTPUT_DEBUG)
        self.game.katrain.log(f"[RankStrategy] Kyu rank: {self.settings['kyu_rank']}", OUTPUT_DEBUG)

        # Calibrated override based on board filling
        ratio = (board_squares - len(legal_policy_moves)) / board_squares
        override = 0.8 * (1 - 0.5 * ratio)
        self.game.katrain.log(
            f"[RankStrategy] Calculated override: {override:.2%} (from board filling ratio {ratio:.2%})", OUTPUT_DEBUG
        )

        overridetwo = 0.85 + max(0, 0.02 * (self.settings["kyu_rank"] - 8))
        self.game.katrain.log(
            f"[RankStrategy] Calculated overridetwo: {overridetwo:.2%} (from kyu rank adjustment)", OUTPUT_DEBUG
        )

        # Call the parent class method with calculated overrides
        return super().should_play_top_move(policy_moves, top_5_pass, override, overridetwo)

    def handle_endgame(
        self,
        legal_policy_moves: list[tuple[float, Move | None]],
        policy_grid: list[list[float | None]],
        size: tuple[int, int],
    ) -> tuple[list[tuple[float, float, int, int]] | None, str, int | None, bool]:
        return None, "", None, False
