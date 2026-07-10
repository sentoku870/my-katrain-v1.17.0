"""Ownership-based AI strategy tests (Phase F-1).

Extracted from tests/test_ai_strategies.py. Covers
``OwnershipBaseStrategy`` (base class) and its concrete subclasses
``SimpleOwnershipStrategy`` and ``SettleStonesStrategy``.
"""

from __future__ import annotations

from katrain.core.ai import (
    SettleStonesStrategy,
    SimpleOwnershipStrategy,
)
from katrain.core.constants import (
    AI_SETTLE_STONES,
    AI_SIMPLE_OWNERSHIP,
)
from katrain.core.game import Move
from tests.ai_strategies._helpers import ai_test_context, make_settings


class TestOwnershipBaseStrategy:
    def test_is_attachment_pass_returns_false(self):
        # OwnershipBaseStrategy is abstract; test through SimpleOwnershipStrategy
        with ai_test_context() as (game, cn):
            strategy = SimpleOwnershipStrategy(game, make_settings(AI_SIMPLE_OWNERSHIP))
            pass_move = Move(None, player="B")
            assert strategy.is_attachment(pass_move) is False

    def test_is_attachment_no_coords_returns_false(self):
        with ai_test_context() as (game, cn):
            strategy = SimpleOwnershipStrategy(game, make_settings(AI_SIMPLE_OWNERSHIP))
            m = Move(coords=None, player="B")
            assert strategy.is_attachment(m) is False

    def test_settledness_calculates(self):
        """settledness returns sum of |ownership| where sign matches."""
        with ai_test_context() as (game, cn):
            strategy = SimpleOwnershipStrategy(game, make_settings(AI_SIMPLE_OWNERSHIP))
            d = {"ownership": [0.5, -0.3, 0.8, -0.2]}
            # player_sign(B) = 1 → sum of abs for positive values: 0.5 + 0.8 = 1.3
            result = strategy.settledness(d, 1, "B")
            assert result == 1.3
            # player_sign(W) = -1 → sum of abs for negative values: 0.3 + 0.2 = 0.5
            result_w = strategy.settledness(d, -1, "W")
            assert result_w == 0.5


# ---------------------------------------------------------------------------
# SimpleOwnershipStrategy / SettleStonesStrategy
# ---------------------------------------------------------------------------


class TestSimpleOwnershipStrategy:
    def test_simple_ownership_runs_with_moves(self):
        """SimpleOwnershipStrategy runs without crashing when moves are available."""
        candidates = [
            {
                "move": "D4",
                "order": 0,
                "scoreLead": 0.0,
                "pointsLost": 0.5,
                "visits": 100,
                "winrate": 0.5,
                "prior": 0.5,
                "ownership": [0.1] * 361,
            },
        ]
        with ai_test_context(candidate_moves=candidates) as (game, cn):
            strategy = SimpleOwnershipStrategy(game, make_settings(AI_SIMPLE_OWNERSHIP))
            move, thoughts = strategy.generate_move()
            assert move is not None


class TestSettleStonesStrategy:
    def test_settle_stones_runs_with_moves(self):
        """SettleStonesStrategy runs without crashing when moves are available."""
        candidates = [
            {
                "move": "D4",
                "order": 0,
                "scoreLead": 0.0,
                "pointsLost": 0.5,
                "visits": 100,
                "winrate": 0.5,
                "prior": 0.5,
                "ownership": [0.1] * 361,
            },
        ]
        with ai_test_context(candidate_moves=candidates) as (game, cn):
            strategy = SettleStonesStrategy(game, make_settings(AI_SETTLE_STONES))
            move, thoughts = strategy.generate_move()
            assert move is not None
