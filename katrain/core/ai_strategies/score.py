"""Score-based and ownership-based AI strategies.

Phase 158+: Extracted from ``katrain.core.ai`` for family-based organization.

Strategies:
- ScoreLossStrategy: weights moves based on point loss (exponential decay)
- OwnershipBaseStrategy: base class for ownership-based strategies
- SimpleOwnershipStrategy: weights moves based on settledness (territory control)
- SettleStonesStrategy: focuses on moves that solidify existing stones
"""

from __future__ import annotations

import math
from typing import Any

from katrain.core.ai_strategies_base import AIStrategy, register_strategy
from katrain.core.constants import (
    AI_PASS_LOSS_THRESHOLD,
    AI_SCORELOSS,
    AI_SETTLE_STONES,
    AI_SIMPLE_OWNERSHIP,
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
)
from katrain.core.game import Move
from katrain.core.utils import var_to_grid, weighted_selection_without_replacement


@register_strategy(AI_SCORELOSS)
class ScoreLossStrategy(AIStrategy):
    """ScoreLoss strategy - weights moves based on point loss"""

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log("[ScoreLossStrategy] Starting move generation", OUTPUT_DEBUG)
        self.wait_for_analysis()

        candidate_moves = self.cn.candidate_moves
        self.game.katrain.log(
            f"[ScoreLossStrategy] Analysis found {len(candidate_moves)} candidate moves", OUTPUT_DEBUG
        )

        if not candidate_moves:
            self.game.katrain.log("[ScoreLossStrategy] No candidate moves found, will play pass", OUTPUT_DEBUG)
            return Move(None, player=self.cn.next_player), "No candidate moves found, passing"

        top_cand = Move.from_gtp(candidate_moves[0]["move"], player=self.cn.next_player)
        self.game.katrain.log(f"[ScoreLossStrategy] Top engine move would be: {top_cand.gtp()}", OUTPUT_DEBUG)

        # Check if top move is pass
        if top_cand.is_pass:
            self.game.katrain.log(
                "[ScoreLossStrategy] Top move is pass, so passing regardless of strategy", OUTPUT_DEBUG
            )
            return top_cand, "Top move is pass, so passing regardless of strategy."

        # Get strength parameter
        c = self.settings["strength"]
        self.game.katrain.log(f"[ScoreLossStrategy] Strength parameter: {c}", OUTPUT_DEBUG)

        # Calculate weights for moves based on point loss
        self.game.katrain.log("[ScoreLossStrategy] Calculating weights for candidate moves", OUTPUT_DEBUG)

        moves = []
        for i, d in enumerate(candidate_moves):
            move = Move.from_gtp(d["move"], player=self.cn.next_player)
            points_lost = d["pointsLost"]
            weight = math.exp(min(200, -c * max(0, points_lost)))

            self.game.katrain.log(
                f"[ScoreLossStrategy] Move {i + 1}: {move.gtp()} - Points lost: {points_lost:.2f}, Weight: {weight:.6f}",
                OUTPUT_DEBUG,
            )
            moves.append((points_lost, weight, move))

        # Select move based on weights
        self.game.katrain.log("[ScoreLossStrategy] Selecting move with weighted selection", OUTPUT_DEBUG)
        topmove = weighted_selection_without_replacement(moves, 1)[0]
        aimove = topmove[2]

        self.game.katrain.log(f"[ScoreLossStrategy] Selected move: {aimove.gtp()}", OUTPUT_DEBUG)
        self.game.katrain.log(f"[ScoreLossStrategy] Selected move points lost: {topmove[0]:.2f}", OUTPUT_DEBUG)
        self.game.katrain.log(f"[ScoreLossStrategy] Selected move weight: {topmove[1]:.6f}", OUTPUT_DEBUG)

        ai_thoughts = f"ScoreLoss strategy found {len(candidate_moves)} candidate moves (best {top_cand.gtp()}) and chose {aimove.gtp()} (weight {topmove[1]:.3f}, point loss {topmove[0]:.1f}) based on score weights."

        self.game.katrain.log(f"[ScoreLossStrategy] Final decision: {aimove.gtp()}", OUTPUT_DEBUG)
        return aimove, ai_thoughts


class OwnershipBaseStrategy(AIStrategy):
    """Base class for ownership-based strategies"""

    def settledness(self, d: dict[str, Any], player_sign: int, player: str) -> float:
        """Calculate settledness for Simple Ownership strategy"""
        ownership: list[float] = d["ownership"]
        ownership_sum = sum([abs(o) for o in ownership if player_sign * o > 0])
        self.game.katrain.log(
            f"[{self.strategy_name}] Calculating settledness for {player}, sign={player_sign}: {ownership_sum:.2f}",
            OUTPUT_DEBUG,
        )
        return ownership_sum

    def is_attachment(self, move: Move) -> bool:
        """Check if a move is an attachment"""
        if move.is_pass or move.coords is None:
            return False

        stones_with_player = {(*s.coords, s.player) for s in self.game.stones if s.coords is not None}

        attach_opponent_stones = sum(
            (move.coords[0] + dx, move.coords[1] + dy, self.cn.player) in stones_with_player
            for dx in [-1, 0, 1]
            for dy in [-1, 0, 1]
            if abs(dx) + abs(dy) == 1
        )

        nearby_own_stones = sum(
            (move.coords[0] + dx, move.coords[1] + dy, self.cn.next_player) in stones_with_player
            for dx in [-2, 0, 1, 2]
            for dy in [-2 - 1, 0, 1, 2]
            if abs(dx) + abs(dy) <= 2  # allows clamps/jumps
        )

        is_attach = attach_opponent_stones >= 1 and nearby_own_stones == 0
        self.game.katrain.log(
            f"[{self.strategy_name}] Is move {move.gtp()} an attachment? {is_attach} (opponent stones: {attach_opponent_stones}, own stones: {nearby_own_stones})",
            OUTPUT_DEBUG,
        )
        return is_attach

    def is_tenuki(self, move: Move) -> bool:
        """Check if a move is a tenuki (far from previous moves)"""
        if move.is_pass or move.coords is None:
            return False

        result = not any(
            not node
            or not node.move
            or node.move.is_pass
            or node.move.coords is None
            or max(abs(last_c - cand_c) for last_c, cand_c in zip(node.move.coords, move.coords, strict=False)) < 5
            for node in [self.cn, self.cn.parent]
        )

        distances: list[int] = []
        for node in [self.cn, self.cn.parent]:
            if node and node.move and not node.move.is_pass and node.move.coords is not None:
                dist = max(abs(last_c - cand_c) for last_c, cand_c in zip(node.move.coords, move.coords, strict=False))
                distances.append(dist)

        if distances:
            self.game.katrain.log(
                f"[{self.strategy_name}] Is move {move.gtp()} a tenuki? {result} (distances: {distances})", OUTPUT_DEBUG
            )
        else:
            self.game.katrain.log(
                f"[{self.strategy_name}] Is move {move.gtp()} a tenuki? {result} (no valid previous moves)",
                OUTPUT_DEBUG,
            )

        return result

    def get_moves_with_settledness(self) -> list[tuple[Move, float, float, bool, bool, dict[str, Any]]]:
        """Get moves with ownership and settledness information"""
        self.game.katrain.log(f"[{self.strategy_name}] Getting moves with settledness information", OUTPUT_DEBUG)

        next_player_sign = self.cn.player_sign(self.cn.next_player)
        candidate_moves = self.cn.candidate_moves

        self.game.katrain.log(f"[{self.strategy_name}] Processing {len(candidate_moves)} candidate moves", OUTPUT_DEBUG)
        self.game.katrain.log(
            f"[{self.strategy_name}] Settings: max_points_lost={self.settings['max_points_lost']}, min_visits={self.settings.get('min_visits', 1)}",
            OUTPUT_DEBUG,
        )
        self.game.katrain.log(
            f"[{self.strategy_name}] Penalties: attach={self.settings['attach_penalty']}, tenuki={self.settings['tenuki_penalty']}",
            OUTPUT_DEBUG,
        )
        self.game.katrain.log(
            f"[{self.strategy_name}] Weights: settled={self.settings['settled_weight']}, opponent_fac={self.settings['opponent_fac']}",
            OUTPUT_DEBUG,
        )

        moves_data = []
        for d in candidate_moves:
            # Check basic filtering conditions
            if "pointsLost" not in d:
                self.game.katrain.log(
                    f"[{self.strategy_name}] Move {d['move']} has no pointsLost, skipping", OUTPUT_DEBUG
                )
                continue

            if d["pointsLost"] >= self.settings["max_points_lost"]:
                self.game.katrain.log(
                    f"[{self.strategy_name}] Move {d['move']} has pointsLost={d['pointsLost']}, which exceeds max_points_lost={self.settings['max_points_lost']}, skipping",
                    OUTPUT_DEBUG,
                )
                continue

            if "ownership" not in d:
                self.game.katrain.log(
                    f"[{self.strategy_name}] Move {d['move']} has no ownership data, skipping", OUTPUT_DEBUG
                )
                continue

            if not (d["order"] <= 1 or d["visits"] >= self.settings.get("min_visits", 1)):
                self.game.katrain.log(
                    f"[{self.strategy_name}] Move {d['move']} has order={d['order']} and visits={d.get('visits', 'N/A')}, doesn't meet criteria, skipping",
                    OUTPUT_DEBUG,
                )
                continue

            move = Move.from_gtp(d["move"], player=self.cn.next_player)
            if move.is_pass and d["pointsLost"] > AI_PASS_LOSS_THRESHOLD:
                self.game.katrain.log(
                    f"[{self.strategy_name}] Move {move.gtp()} is pass with high point loss ({d['pointsLost']}), skipping",
                    OUTPUT_DEBUG,
                )
                continue

            # Calculate metrics
            own_settledness = self.settledness(d, next_player_sign, self.cn.next_player)
            opp_settledness = self.settledness(d, -next_player_sign, self.cn.player)
            is_attach = self.is_attachment(move)
            is_tenuki = self.is_tenuki(move)

            # Calculate total score for sorting
            score = (
                d["pointsLost"]
                + self.settings["attach_penalty"] * is_attach
                + self.settings["tenuki_penalty"] * is_tenuki
                - self.settings["settled_weight"] * (own_settledness + self.settings["opponent_fac"] * opp_settledness)
            )

            self.game.katrain.log(
                f"[{self.strategy_name}] Move {move.gtp()}: points_lost={d['pointsLost']:.2f}, own_settled={own_settledness:.2f}, opp_settled={opp_settledness:.2f}, attach={is_attach}, tenuki={is_tenuki}, score={score:.2f}",
                OUTPUT_DEBUG,
            )

            moves_data.append(
                (
                    move,
                    own_settledness,
                    opp_settledness,
                    is_attach,
                    is_tenuki,
                    d,
                    score,  # Store the score for debugging
                )
            )

        # Sort moves by score
        sorted_moves = sorted(
            moves_data,
            key=lambda t: t[6],  # Sort by the precalculated score
        )

        self.game.katrain.log(
            f"[{self.strategy_name}] Found {len(sorted_moves)} valid moves with settledness data", OUTPUT_DEBUG
        )
        if sorted_moves:
            self.game.katrain.log(
                f"[{self.strategy_name}] Top move after sorting: {sorted_moves[0][0].gtp()} with score {sorted_moves[0][6]:.2f}",
                OUTPUT_DEBUG,
            )

        # Return all data except the score which was just for debugging
        return [
            (move, own_settled, opp_settled, is_attach, is_tenuki, d)
            for move, own_settled, opp_settled, is_attach, is_tenuki, d, _ in sorted_moves
        ]


@register_strategy(AI_SIMPLE_OWNERSHIP)
class SimpleOwnershipStrategy(OwnershipBaseStrategy):
    """Simple Ownership strategy - weights moves based on territory control"""

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log("[SimpleOwnershipStrategy] Starting move generation", OUTPUT_DEBUG)
        self.wait_for_analysis()

        candidate_moves = self.cn.candidate_moves
        self.game.katrain.log(
            f"[SimpleOwnershipStrategy] Analysis found {len(candidate_moves)} candidate moves", OUTPUT_DEBUG
        )

        if not candidate_moves:
            self.game.katrain.log("[SimpleOwnershipStrategy] No candidate moves found, will play pass", OUTPUT_DEBUG)
            return Move(None, player=self.cn.next_player), "No candidate moves found, passing"

        top_cand = Move.from_gtp(candidate_moves[0]["move"], player=self.cn.next_player)
        self.game.katrain.log(f"[SimpleOwnershipStrategy] Top engine move would be: {top_cand.gtp()}", OUTPUT_DEBUG)

        # Check if top move is pass
        if top_cand.is_pass:
            self.game.katrain.log(
                "[SimpleOwnershipStrategy] Top move is pass, so passing regardless of strategy", OUTPUT_DEBUG
            )
            return top_cand, "Top move is pass, so passing regardless of strategy."

        # Get moves sorted by settledness criteria
        self.game.katrain.log("[SimpleOwnershipStrategy] Getting moves with settledness info", OUTPUT_DEBUG)
        moves_with_settledness = self.get_moves_with_settledness()

        if moves_with_settledness:
            self.game.katrain.log(
                f"[SimpleOwnershipStrategy] Found {len(moves_with_settledness)} moves with settledness info",
                OUTPUT_DEBUG,
            )

            # Log top 5 candidates in detail
            self.game.katrain.log("[SimpleOwnershipStrategy] Top 5 candidates:", OUTPUT_DEBUG)
            for i, (move, settled, oppsettled, isattach, istenuki, d) in enumerate(moves_with_settledness[:5]):
                self.game.katrain.log(
                    f"[SimpleOwnershipStrategy] #{i + 1}: {move.gtp()} - pt_lost: {d['pointsLost']:.1f}, visits: {d.get('visits', 'N/A')}, settledness: {settled:.1f}, opp_settled: {oppsettled:.1f}, attach: {isattach}, tenuki: {istenuki}",
                    OUTPUT_DEBUG,
                )

            # Format candidate moves for ai_thoughts
            cands = [
                f"{move.gtp()} ({d['pointsLost']:.1f} pt lost, {d.get('visits', 'N/A')} visits, {settled:.1f} settledness, {oppsettled:.1f} opponent settledness{', attachment' if isattach else ''}{', tenuki' if istenuki else ''})"
                for move, settled, oppsettled, isattach, istenuki, d in moves_with_settledness[:5]
            ]

            ai_thoughts = f"{AI_SIMPLE_OWNERSHIP} strategy. Top 5 Candidates {', '.join(cands)} "
            aimove = moves_with_settledness[0][0]

            self.game.katrain.log(f"[SimpleOwnershipStrategy] Selected move: {aimove.gtp()}", OUTPUT_DEBUG)
        else:
            error_msg = "No moves found - are you using an older KataGo with no per-move ownership info?"
            self.game.katrain.log(f"[SimpleOwnershipStrategy] Error: {error_msg}", OUTPUT_ERROR)
            raise Exception(error_msg)

        self.game.katrain.log(f"[SimpleOwnershipStrategy] Final decision: {aimove.gtp()}", OUTPUT_DEBUG)
        return aimove, ai_thoughts


@register_strategy(AI_SETTLE_STONES)
class SettleStonesStrategy(OwnershipBaseStrategy):
    """Settle Stones strategy - focuses on settled stones"""

    def settledness(self, d: dict[str, Any], player_sign: int, player: str) -> float:
        """Calculate settledness for Settle Stones strategy"""
        board_size_x, board_size_y = self.game.board_size
        ownership_grid: list[list[float]] = var_to_grid(d["ownership"], (board_size_x, board_size_y))

        # Sum the absolute ownership values of existing stones
        stone_ownership_values: list[float] = [
            abs(ownership_grid[s.coords[0]][s.coords[1]])
            for s in self.game.stones
            if s.player == player and s.coords is not None
        ]
        total_settledness: float = sum(stone_ownership_values)

        self.game.katrain.log(
            f"[SettleStonesStrategy] Calculating settledness for {player}, sign={player_sign}", OUTPUT_DEBUG
        )
        self.game.katrain.log(
            f"[SettleStonesStrategy] Number of stones considered: {len(stone_ownership_values)}", OUTPUT_DEBUG
        )
        self.game.katrain.log(f"[SettleStonesStrategy] Total settledness: {total_settledness:.2f}", OUTPUT_DEBUG)

        if stone_ownership_values:
            self.game.katrain.log(
                f"[SettleStonesStrategy] Min stone ownership: {min(stone_ownership_values):.2f}", OUTPUT_DEBUG
            )
            self.game.katrain.log(
                f"[SettleStonesStrategy] Max stone ownership: {max(stone_ownership_values):.2f}", OUTPUT_DEBUG
            )
            self.game.katrain.log(
                f"[SettleStonesStrategy] Avg stone ownership: {total_settledness / len(stone_ownership_values):.2f}",
                OUTPUT_DEBUG,
            )

        return total_settledness

    def generate_move(self) -> tuple[Move, str]:
        self.game.katrain.log("[SettleStonesStrategy] Starting move generation", OUTPUT_DEBUG)
        self.wait_for_analysis()

        candidate_moves = self.cn.candidate_moves
        self.game.katrain.log(
            f"[SettleStonesStrategy] Analysis found {len(candidate_moves)} candidate moves", OUTPUT_DEBUG
        )

        if not candidate_moves:
            self.game.katrain.log("[SettleStonesStrategy] No candidate moves found, will play pass", OUTPUT_DEBUG)
            return Move(None, player=self.cn.next_player), "No candidate moves found, passing"

        top_cand = Move.from_gtp(candidate_moves[0]["move"], player=self.cn.next_player)
        self.game.katrain.log(f"[SettleStonesStrategy] Top engine move would be: {top_cand.gtp()}", OUTPUT_DEBUG)

        # Check if top move is pass
        if top_cand.is_pass:
            self.game.katrain.log(
                "[SettleStonesStrategy] Top move is pass, so passing regardless of strategy", OUTPUT_DEBUG
            )
            return top_cand, "Top move is pass, so passing regardless of strategy."

        # Log the number of stones on the board
        black_stones = sum(1 for s in self.game.stones if s.player == "B")
        white_stones = sum(1 for s in self.game.stones if s.player == "W")
        self.game.katrain.log(
            f"[SettleStonesStrategy] Stones on board: B={black_stones}, W={white_stones}", OUTPUT_DEBUG
        )

        # Get moves sorted by settledness criteria
        self.game.katrain.log("[SettleStonesStrategy] Getting moves with settledness info", OUTPUT_DEBUG)
        moves_with_settledness = self.get_moves_with_settledness()

        if moves_with_settledness:
            self.game.katrain.log(
                f"[SettleStonesStrategy] Found {len(moves_with_settledness)} moves with settledness info",
                OUTPUT_DEBUG,
            )

            # Log top 5 candidates in detail
            self.game.katrain.log("[SettleStonesStrategy] Top 5 candidates:", OUTPUT_DEBUG)
            for i, (move, settled, oppsettled, isattach, istenuki, d) in enumerate(moves_with_settledness[:5]):
                self.game.katrain.log(
                    f"[SettleStonesStrategy] #{i + 1}: {move.gtp()} - pt_lost: {d['pointsLost']:.1f}, visits: {d.get('visits', 'N/A')}, settledness: {settled:.1f}, opp_settled: {oppsettled:.1f}, attach: {isattach}, tenuki: {istenuki}",
                    OUTPUT_DEBUG,
                )

            # Format candidate moves for ai_thoughts
            cands = [
                f"{move.gtp()} ({d['pointsLost']:.1f} pt lost, {d.get('visits', 'N/A')} visits, {settled:.1f} settledness, {oppsettled:.1f} opponent settledness{', attachment' if isattach else ''}{', tenuki' if istenuki else ''})"
                for move, settled, oppsettled, isattach, istenuki, d in moves_with_settledness[:5]
            ]

            ai_thoughts = f"{AI_SETTLE_STONES} strategy. Top 5 Candidates {', '.join(cands)} "
            aimove = moves_with_settledness[0][0]

            self.game.katrain.log(f"[SettleStonesStrategy] Selected move: {aimove.gtp()}", OUTPUT_DEBUG)
        else:
            error_msg = "No moves found - are you using an older KataGo with no per-move ownership info?"
            self.game.katrain.log(f"[SettleStonesStrategy] Error: {error_msg}", OUTPUT_ERROR)
            raise Exception(error_msg)

        self.game.katrain.log(f"[SettleStonesStrategy] Final decision: {aimove.gtp()}", OUTPUT_DEBUG)
        return aimove, ai_thoughts
