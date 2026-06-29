"""Pick-based AI strategies.

Phase 158+: Extracted from ``katrain.core.ai`` for family-based organization.

Strategies (all inherit from PickBasedStrategy):
- PickStrategy: picks a random move weighted by policy
- RankStrategy: like Pick but n_moves calibrated by kyu rank
- InfluenceStrategy: weights moves by distance from board edge
- TerritoryStrategy: weights moves by distance from board center
- LocalStrategy: weights moves by proximity to last move
- TenukiStrategy: weights moves by distance from last move (inverse of Local)
"""

from __future__ import annotations

import heapq
import math

from katrain.core.ai_strategies.basic import DefaultStrategy
from katrain.core.ai_strategies.policy import WeightedStrategy
from katrain.core.ai_strategies_base import (
    AIStrategy,
    fmt_moves,
    generate_influence_territory_weights,
    generate_local_tenuki_weights,
    register_strategy,
)
from katrain.core.constants import (
    AI_ENDGAME_FILL_RATIO_DEFAULT,
    AI_INFLUENCE,
    AI_LOCAL,
    AI_PICK,
    AI_RANK,
    AI_TENUKI,
    AI_TERRITORY,
    OUTPUT_DEBUG,
)
from katrain.core.game import Move
from katrain.core.utils import var_to_grid, weighted_selection_without_replacement


class PickBasedStrategy(AIStrategy):
    """Base class for pick-based strategies"""

    def get_n_moves(self, legal_policy_moves: list[tuple[float, Move | None]]) -> int:
        """Calculate the number of moves to consider"""
        self.game.board_size[0] * self.game.board_size[1]

        if self.settings.get("pick_frac") is not None:
            n_moves = max(1, int(self.settings["pick_frac"] * len(legal_policy_moves) + self.settings["pick_n"]))
            self.game.katrain.log(
                f"[{self.strategy_name}] Calculated n_moves={n_moves} from pick_frac={self.settings['pick_frac']}, pick_n={self.settings['pick_n']}, legal_moves={len(legal_policy_moves)}",
                OUTPUT_DEBUG,
            )
        else:
            n_moves = 1  # Default
            self.game.katrain.log(
                f"[{self.strategy_name}] Using default n_moves={n_moves} (no pick_frac in settings)", OUTPUT_DEBUG
            )

        return n_moves

    def generate_weighted_coords(
        self,
        legal_policy_moves: list[tuple[float, Move | None]],
        policy_grid: list[list[float | None]],
        size: tuple[int, int],
    ) -> tuple[list[tuple[float, float, int, int]], str]:
        """Generate weighted coordinates for selection"""
        self.game.katrain.log(
            f"[{self.strategy_name}] Generating weighted coordinates (default equal weights implementation)",
            OUTPUT_DEBUG,
        )

        # Default implementation for AI_PICK - equal weights
        weighted_coords: list[tuple[float, float, int, int]] = []
        for x in range(size[0]):
            for y in range(size[1]):
                pval = policy_grid[y][x]
                if pval is not None and pval > 0:
                    weighted_coords.append((pval, 1.0, x, y))

        self.game.katrain.log(
            f"[{self.strategy_name}] Generated {len(weighted_coords)} weighted coordinates", OUTPUT_DEBUG
        )

        if weighted_coords:
            top5 = heapq.nlargest(5, weighted_coords, key=lambda t: t[0])
            self.game.katrain.log(f"[{self.strategy_name}] Top 5 weighted coordinates by policy value:", OUTPUT_DEBUG)
            for i, (pol, wt, x, y) in enumerate(top5):
                self.game.katrain.log(
                    f"[{self.strategy_name}] #{i + 1}: ({x},{y}) - policy={pol:.2%}, weight={wt}", OUTPUT_DEBUG
                )

        return weighted_coords, "Generated equal weights for all moves. "

    def handle_endgame(
        self,
        legal_policy_moves: list[tuple[float, Move | None]],
        policy_grid: list[list[float | None]],
        size: tuple[int, int],
    ) -> tuple[list[tuple[float, float, int, int]] | None, str, int | None, bool]:
        """Handle special endgame case"""
        board_squares = size[0] * size[1]
        endgame_threshold = self.settings.get("endgame", AI_ENDGAME_FILL_RATIO_DEFAULT) * board_squares

        self.game.katrain.log(
            f"[{self.strategy_name}] Checking endgame condition: move depth {self.cn.depth} vs threshold {endgame_threshold}",
            OUTPUT_DEBUG,
        )

        if self.cn.depth > endgame_threshold:
            self.game.katrain.log(
                f"[{self.strategy_name}] In endgame phase (move {self.cn.depth} > {endgame_threshold})", OUTPUT_DEBUG
            )

            weighted_coords: list[tuple[float, float, int, int]] = [
                (pol, 1, mv.coords[0], mv.coords[1])
                for pol, mv in legal_policy_moves
                if mv is not None and mv.coords is not None
            ]
            ai_thoughts = f"Generated equal weights as move number >= {self.settings['endgame'] * size[0] * size[1]}. "

            n_moves = int(max(self.get_n_moves(legal_policy_moves), len(legal_policy_moves) // 2))
            self.game.katrain.log(f"[{self.strategy_name}] Using endgame n_moves={n_moves}", OUTPUT_DEBUG)

            self.game.katrain.log(
                f"[{self.strategy_name}] Generated {len(weighted_coords)} weighted coordinates for endgame",
                OUTPUT_DEBUG,
            )

            return weighted_coords, ai_thoughts, n_moves, True

        self.game.katrain.log(f"[{self.strategy_name}] Not in endgame phase yet", OUTPUT_DEBUG)
        return None, "", None, False

    def select_from_weighted_coords(
        self,
        weighted_coords: list[tuple[float, float, int, int]] | None,
        n_moves: int,
        pass_policy: float | None,
    ) -> tuple[Move, str]:
        """Select moves from weighted coordinates"""
        if weighted_coords is None:
            weighted_coords = []
        self.game.katrain.log(
            f"[{self.strategy_name}] Selecting from {len(weighted_coords)} weighted coordinates, n_moves={n_moves}",
            OUTPUT_DEBUG,
        )

        # Perform weighted selection
        pick_moves = weighted_selection_without_replacement(weighted_coords, n_moves)
        self.game.katrain.log(f"[{self.strategy_name}] Picked {len(pick_moves)} moves", OUTPUT_DEBUG)

        if pick_moves:
            # Get top 5 from picked moves
            top_picked = heapq.nlargest(5, pick_moves)
            self.game.katrain.log(f"[{self.strategy_name}] Top 5 after selection:", OUTPUT_DEBUG)
            for i, (p, wt, x, y) in enumerate(top_picked):
                self.game.katrain.log(
                    f"[{self.strategy_name}] #{i + 1}: ({x},{y}) - policy={p:.2%}, weight={wt}", OUTPUT_DEBUG
                )

            # Convert to move objects
            new_top = [(p, Move((x, y), player=self.cn.next_player)) for p, wt, x, y in top_picked]

            aimove = new_top[0][1]
            ai_thoughts = f"Top 5 among these were {fmt_moves(new_top)} and picked top {aimove.gtp()}. "

            self.game.katrain.log(
                f"[{self.strategy_name}] Top picked move: {aimove.gtp()} ({new_top[0][0]:.2%})", OUTPUT_DEBUG
            )
            self.game.katrain.log(f"[{self.strategy_name}] Pass policy: {pass_policy}", OUTPUT_DEBUG)

            # Check if pass is better
            if pass_policy is not None and new_top[0][0] < pass_policy:
                self.game.katrain.log(
                    f"[{self.strategy_name}] Pass policy {pass_policy:.2%} is better than top move {aimove.gtp()} ({new_top[0][0]:.2%}), switching to top policy move",
                    OUTPUT_DEBUG,
                )

                policy_moves = self.cn.policy_ranking
                if policy_moves is None:
                    return DefaultStrategy(self.game, self.settings).generate_move()
                top_policy_move_opt = policy_moves[0][1]
                top_policy_move = top_policy_move_opt if top_policy_move_opt is not None else Move(None)

                ai_thoughts += f"But found pass ({pass_policy:.2%} to be higher rated than {aimove.gtp()} ({new_top[0][0]:.2%}) so will play top policy move instead."
                aimove = top_policy_move

                self.game.katrain.log(
                    f"[{self.strategy_name}] Final move (after pass check): {aimove.gtp()}", OUTPUT_DEBUG
                )
            else:
                self.game.katrain.log(f"[{self.strategy_name}] Top move is better than pass, keeping it", OUTPUT_DEBUG)
        else:
            self.game.katrain.log(
                f"[{self.strategy_name}] No moves selected, falling back to top policy move", OUTPUT_DEBUG
            )

            policy_moves = self.cn.policy_ranking
            if policy_moves is None:
                return DefaultStrategy(self.game, self.settings).generate_move()
            top_policy_move_opt = policy_moves[0][1]
            aimove = top_policy_move_opt if top_policy_move_opt is not None else Move(None)

            ai_thoughts = (
                f"Pick policy strategy failed to find legal moves, so is playing top policy move {aimove.gtp()}."
            )

            self.game.katrain.log(f"[{self.strategy_name}] Final move (fallback): {aimove.gtp()}", OUTPUT_DEBUG)

        return aimove, ai_thoughts

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log(f"[{self.strategy_name}] Starting move generation", OUTPUT_DEBUG)
        self.wait_for_analysis()

        # Ensure policy is available
        if not self.cn.policy:
            self.game.katrain.log(
                f"[{self.strategy_name}] No policy data available, falling back to DefaultStrategy", OUTPUT_DEBUG
            )
            return DefaultStrategy(self.game, self.settings).generate_move()

        policy_moves = self.cn.policy_ranking
        if policy_moves is None:
            self.game.katrain.log(
                f"[{self.strategy_name}] No policy ranking available, falling back to DefaultStrategy", OUTPUT_DEBUG
            )
            return DefaultStrategy(self.game, self.settings).generate_move()

        pass_policy = self.cn.policy[-1]
        self.game.katrain.log(f"[{self.strategy_name}] Got {len(policy_moves)} policy moves", OUTPUT_DEBUG)

        # Log top 5 policy moves
        self.game.katrain.log(f"[{self.strategy_name}] Top 5 policy moves:", OUTPUT_DEBUG)
        for i, (prob, move) in enumerate(policy_moves[:5]):
            move_str = move.gtp() if move is not None else "None"
            self.game.katrain.log(f"[{self.strategy_name}] #{i + 1}: {move_str} - {prob:.2%}", OUTPUT_DEBUG)

        self.game.katrain.log(f"[{self.strategy_name}] Pass policy: {pass_policy}", OUTPUT_DEBUG)

        # Check for pass in top 5
        top_5_pass = any([polmove[1] is not None and polmove[1].is_pass for polmove in policy_moves[:5]])
        self.game.katrain.log(f"[{self.strategy_name}] Pass in top 5: {top_5_pass}", OUTPUT_DEBUG)

        # Get override settings
        override = self.settings.get("pick_override", 0.0)
        overridetwo = self.settings.get("pick_override_two", 1.0)
        self.game.katrain.log(
            f"[{self.strategy_name}] Override settings: single={override:.2%}, combined={overridetwo:.2%}", OUTPUT_DEBUG
        )

        # Check if we should override with top move
        override_move, override_thoughts = self.should_play_top_move(
            policy_moves, top_5_pass, override=override, overridetwo=overridetwo
        )

        if override_move:
            self.game.katrain.log(f"[{self.strategy_name}] Using override move: {override_move.gtp()}", OUTPUT_DEBUG)
            return override_move, override_thoughts

        # Get legal policy moves (filter out None and pass moves)
        legal_policy_moves: list[tuple[float, Move | None]] = []
        for pol, mv in policy_moves:
            if mv is not None and not mv.is_pass and pol > 0:
                legal_policy_moves.append((pol, mv))
        self.game.katrain.log(
            f"[{self.strategy_name}] Found {len(legal_policy_moves)} legal non-pass policy moves", OUTPUT_DEBUG
        )

        # Create policy grid
        size = self.game.board_size
        self.game.katrain.log(f"[{self.strategy_name}] Board size: {size}", OUTPUT_DEBUG)
        policy_grid = var_to_grid(self.cn.policy, size)

        # Check for endgame
        end_coords, end_thoughts, end_n_moves, is_endgame = self.handle_endgame(legal_policy_moves, policy_grid, size)

        if is_endgame:
            self.game.katrain.log(f"[{self.strategy_name}] Using endgame logic", OUTPUT_DEBUG)
            assert end_coords is not None and end_n_moves is not None
            return self.select_from_weighted_coords(end_coords, end_n_moves, pass_policy)

        # Get weighted coordinates
        self.game.katrain.log(f"[{self.strategy_name}] Generating weighted coordinates", OUTPUT_DEBUG)
        weighted_coords, weight_thoughts = self.generate_weighted_coords(legal_policy_moves, policy_grid, size)

        # Get number of moves to consider
        n_moves = self.get_n_moves(legal_policy_moves)
        self.game.katrain.log(f"[{self.strategy_name}] Using n_moves={n_moves}", OUTPUT_DEBUG)

        ai_thoughts = (
            weight_thoughts + f"Picked {min(n_moves, len(weighted_coords))} random moves according to weights. "
        )

        # Select and return move
        self.game.katrain.log(f"[{self.strategy_name}] Selecting move from weighted coordinates", OUTPUT_DEBUG)
        move, thoughts = self.select_from_weighted_coords(weighted_coords, n_moves, pass_policy)

        self.game.katrain.log(f"[{self.strategy_name}] Final decision: {move.gtp()}", OUTPUT_DEBUG)
        return move, ai_thoughts + thoughts


@register_strategy(AI_PICK)
class PickStrategy(PickBasedStrategy):
    """Pick strategy - picks a move from a subset of legal moves"""

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log(
            "[PickStrategy] Starting move generation using base PickBasedStrategy implementation", OUTPUT_DEBUG
        )
        return super().generate_move()

    def handle_endgame(
        self,
        legal_policy_moves: list[tuple[float, Move | None]],
        policy_grid: list[list[float | None]],
        size: tuple[int, int],
    ) -> tuple[list[tuple[float, float, int, int]] | None, str, int | None, bool]:
        return None, "", None, False


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
            f"[RankStrategy] Calculated override: {override:.2%} (from board filling ratio {ratio:.2f})", OUTPUT_DEBUG
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


@register_strategy(AI_TERRITORY)
class TerritoryStrategy(PickBasedStrategy):
    """Territory strategy - weights moves based on territory (distance from center)"""

    def generate_weighted_coords(
        self,
        legal_policy_moves: list[tuple[float, Move | None]],
        policy_grid: list[list[float | None]],
        size: tuple[int, int],
    ) -> tuple[list[tuple[float, float, int, int]], str]:
        """Generate territory-based weights"""
        self.game.katrain.log("[TerritoryStrategy] Generating territory-based weights", OUTPUT_DEBUG)
        self.game.katrain.log(
            f"[TerritoryStrategy] Settings: threshold={self.settings['threshold']}, line_weight={self.settings['line_weight']}",
            OUTPUT_DEBUG,
        )
        weighted_coords, ai_thoughts = generate_influence_territory_weights(
            AI_TERRITORY, self.settings, policy_grid, size
        )
        self.game.katrain.log(
            f"[TerritoryStrategy] Generated {len(weighted_coords)} weighted coordinates", OUTPUT_DEBUG
        )
        if weighted_coords:
            top5 = heapq.nlargest(5, weighted_coords, key=lambda t: t[0] * t[1])
            self.game.katrain.log("[TerritoryStrategy] Top 5 weighted coordinates (by policy*weight):", OUTPUT_DEBUG)
            for i, (pol, wt, x, y) in enumerate(top5):
                self.game.katrain.log(
                    f"[TerritoryStrategy] #{i + 1}: ({x},{y}) - policy={pol:.2%}, weight={wt}, combined={pol * wt:.2%}",
                    OUTPUT_DEBUG,
                )
        return weighted_coords, ai_thoughts


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


@register_strategy(AI_TENUKI)
class TenukiStrategy(PickBasedStrategy):
    """Tenuki strategy - weights moves based on distance from the last move"""

    def generate_move(self) -> tuple[Move, str]:
        # Handle the case where there's no previous move
        if not (self.cn.move and self.cn.move.coords):
            self.game.katrain.log(
                "[TenukiStrategy] No previous move with valid coordinates found, falling back to WeightedStrategy",
                OUTPUT_DEBUG,
            )
            self.game.katrain.log(
                "[TenukiStrategy] Using default weighted settings: pick_override=0.9, weaken_fac=1, lower_bound=0.02",
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
        """Generate tenuki-based weights"""
        self.game.katrain.log("[TenukiStrategy] Generating tenuki-based weights (far from previous move)", OUTPUT_DEBUG)
        assert self.cn.move is not None, "Move cannot be None at this point"
        self.game.katrain.log(f"[TenukiStrategy] Previous move: {self.cn.move.gtp()}", OUTPUT_DEBUG)
        self.game.katrain.log(f"[TenukiStrategy] Variance setting: {self.settings['stddev']}", OUTPUT_DEBUG)
        weighted_coords, ai_thoughts = generate_local_tenuki_weights(
            AI_TENUKI, self.settings, policy_grid, self.cn, size
        )
        self.game.katrain.log(f"[TenukiStrategy] Generated {len(weighted_coords)} weighted coordinates", OUTPUT_DEBUG)
        if weighted_coords:
            top5 = heapq.nlargest(5, weighted_coords, key=lambda t: t[0] * t[1])
            self.game.katrain.log("[TenukiStrategy] Top 5 weighted coordinates (by policy*weight):", OUTPUT_DEBUG)
            for i, (pol, wt, x, y) in enumerate(top5):
                self.game.katrain.log(
                    f"[TenukiStrategy] #{i + 1}: ({x},{y}) - policy={pol:.2%}, weight={wt}, combined={pol * wt:.2%}",
                    OUTPUT_DEBUG,
                )
        return weighted_coords, ai_thoughts
