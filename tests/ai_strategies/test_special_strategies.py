"""Specialist AI strategy tests (Phase F-1).

Extracted from tests/test_ai_strategies.py. Covers the board-shape
specialists: ``InfluenceStrategy``, ``TerritoryStrategy``,
``LocalStrategy``, ``TenukiStrategy``, ``HumanStyleStrategy``.
"""

from __future__ import annotations

from unittest.mock import patch

from katrain.core.ai import (
    HumanStyleStrategy,
    InfluenceStrategy,
    LocalStrategy,
    TenukiStrategy,
    TerritoryStrategy,
)
from katrain.core.ai.constants import (
    AI_HUMAN,
    AI_INFLUENCE,
    AI_LOCAL,
    AI_TENUKI,
    AI_TERRITORY,
)
from katrain.core.game import Move
from tests.ai_strategies._helpers import ai_test_context, make_settings


class TestInfluenceStrategy:
    def test_influence_runs(self):
        policy = [0.0] * (19 * 19 + 1)
        policy[10] = 0.5
        with ai_test_context(policy=policy) as (game, cn):
            strategy = InfluenceStrategy(game, make_settings(AI_INFLUENCE))
            move, thoughts = strategy.generate_move()
            assert move is not None


class TestTerritoryStrategy:
    def test_territory_runs(self):
        policy = [0.0] * (19 * 19 + 1)
        policy[10] = 0.5
        with ai_test_context(policy=policy) as (game, cn):
            strategy = TerritoryStrategy(game, make_settings(AI_TERRITORY))
            move, thoughts = strategy.generate_move()
            assert move is not None


class TestLocalStrategy:
    def test_local_runs(self):
        policy = [0.0] * (19 * 19 + 1)
        policy[10] = 0.5
        prev_move = Move.from_gtp("D4", player="B")
        with ai_test_context(policy=policy, move=prev_move) as (game, cn):
            strategy = LocalStrategy(game, make_settings(AI_LOCAL))
            move, thoughts = strategy.generate_move()
            assert move is not None


class TestTenukiStrategy:
    def test_tenuki_runs(self):
        policy = [0.0] * (19 * 19 + 1)
        policy[10] = 0.5
        prev_move = Move.from_gtp("D4", player="B")
        with ai_test_context(policy=policy, move=prev_move) as (game, cn):
            strategy = TenukiStrategy(game, make_settings(AI_TENUKI))
            move, thoughts = strategy.generate_move()
            assert move is not None


# ---------------------------------------------------------------------------
# HumanStyleStrategy
# ---------------------------------------------------------------------------


class TestHumanStyleStrategy:
    def test_human_style_runs(self):
        """HumanStyleStrategy.generate_move returns a move."""
        candidates = [
            {
                "move": "D4",
                "order": 0,
                "scoreLead": 0.0,
                "pointsLost": 0.0,
                "visits": 100,
                "winrate": 0.5,
                "prior": 0.5,
            },
        ]
        with ai_test_context(candidate_moves=candidates) as (game, cn):
            # Mock request_analysis to immediately call the callback
            def fake_request(*args, **kwargs):
                callback = kwargs.get("callback")
                if callback:
                    callback(
                        {
                            "humanPolicy": [0.1] * 362,
                            "moveInfos": candidates,
                            "rootInfo": {"scoreLead": 0.0, "winrate": 0.5},
                        },
                        False,
                    )

            with patch.object(game.engines[cn.player], "request_analysis", side_effect=fake_request):
                strategy = HumanStyleStrategy(game, make_settings(AI_HUMAN))
                move, thoughts = strategy.generate_move()
                assert move is not None


# ---------------------------------------------------------------------------
# request_analysis timeout / engine-death handling (P1-S7)
# ---------------------------------------------------------------------------
