"""PickStrategy - default pick-based strategy.

Phase 172: Extracted from ``katrain.core.ai_strategies.pick`` for family
organization. This is the canonical ``AI_PICK`` strategy: it relies entirely
on the base-class pipeline without overriding the endgame or weighting logic.
"""

from __future__ import annotations

from katrain.core.ai_strategies.pick_base import PickBasedStrategy
from katrain.core.ai_strategies_base import register_strategy
from katrain.core.constants import AI_PICK, OUTPUT_DEBUG
from katrain.core.game import Move


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
