"""Basic AI strategy tests (Phase F-1).

Extracted from tests/test_ai_strategies.py. Covers the most
straightforward strategies: ``DefaultStrategy``, ``HandicapStrategy``,
``AntimirrorStrategy``, ``JigoStrategy``, ``ScoreLossStrategy``,
``HumanStyleStrategy``.
"""

from __future__ import annotations

from unittest.mock import patch

from katrain.core.ai import (
    AntimirrorStrategy,
    DefaultStrategy,
    HandicapStrategy,
    JigoStrategy,
    ScoreLossStrategy,
)
from katrain.core.ai.constants import (
    AI_ANTIMIRROR,
    AI_DEFAULT,
    AI_HANDICAP,
    AI_SCORELOSS,
)
from tests.ai_strategies._helpers import ai_test_context, make_settings


class TestDefaultStrategy:
    def test_default_with_candidates(self):
        """DefaultStrategy plays the top candidate."""
        candidates = [
            {
                "move": "D4",
                "order": 0,
                "scoreLead": 5.0,
                "pointsLost": 0.0,
                "visits": 100,
                "winrate": 0.6,
                "prior": 0.5,
            },
            {
                "move": "Q16",
                "order": 1,
                "scoreLead": -1.0,
                "pointsLost": 6.0,
                "visits": 80,
                "winrate": 0.4,
                "prior": 0.3,
            },
        ]
        with ai_test_context(candidate_moves=candidates) as (game, cn):
            strategy = DefaultStrategy(game, make_settings(AI_DEFAULT))
            move, thoughts = strategy.generate_move()
            assert move.gtp() == "D4"


# ---------------------------------------------------------------------------
# HandicapStrategy
# ---------------------------------------------------------------------------


class TestHandicapStrategy:
    def test_handicap_manual_pda(self):
        """HandicapStrategy with manual PDA uses the given value."""
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

            def fake_request(*args, **kwargs):
                callback = kwargs.get("callback")
                if callback:
                    callback(
                        {
                            "rootInfo": {"scoreLead": 1.0, "winrate": 0.5},
                            "moveInfos": candidates,
                        },
                        False,
                    )

            with patch.object(game.engines[cn.player], "request_analysis", side_effect=fake_request):
                strategy = HandicapStrategy(game, make_settings(AI_HANDICAP))
                move, thoughts = strategy.generate_move()
                assert move.gtp() == "D4"


# ---------------------------------------------------------------------------
# AntimirrorStrategy
# ---------------------------------------------------------------------------


class TestAntimirrorStrategy:
    def test_antimirror_with_analysis(self):
        """AntimirrorStrategy uses antimirror analysis to pick top move."""
        candidates = [
            {
                "move": "E5",
                "order": 0,
                "scoreLead": 2.0,
                "pointsLost": 0.0,
                "visits": 100,
                "winrate": 0.55,
                "prior": 0.5,
            },
        ]
        with ai_test_context() as (game, cn):

            def fake_request(*args, **kwargs):
                callback = kwargs.get("callback")
                if callback:
                    callback(
                        {
                            "rootInfo": {"scoreLead": 2.0, "winrate": 0.55},
                            "moveInfos": candidates,
                        },
                        False,
                    )

            with patch.object(game.engines[cn.player], "request_analysis", side_effect=fake_request):
                strategy = AntimirrorStrategy(game, make_settings(AI_ANTIMIRROR))
                move, thoughts = strategy.generate_move()
                assert move.gtp() == "E5"


# ---------------------------------------------------------------------------
# JigoStrategy
# ---------------------------------------------------------------------------


class TestJigoStrategy:
    def test_jigo_picks_closest_to_target(self):
        """JigoStrategy picks the move closest to target_score."""
        candidates = [
            {
                "move": "D4",
                "order": 0,
                "scoreLead": 5.0,
                "pointsLost": 0.0,
                "visits": 100,
                "winrate": 0.5,
                "prior": 0.5,
            },
            {
                "move": "Q16",
                "order": 1,
                "scoreLead": 0.5,
                "pointsLost": 4.5,
                "visits": 80,
                "winrate": 0.5,
                "prior": 0.3,
            },
            {
                "move": "D16",
                "order": 2,
                "scoreLead": 10.0,
                "pointsLost": 5.0,
                "visits": 60,
                "winrate": 0.5,
                "prior": 0.2,
            },
        ]
        with ai_test_context(candidate_moves=candidates) as (game, cn):
            # target_score=0.5, B player perspective → Q16 (scoreLead 0.5) closest
            strategy = JigoStrategy(game, {"target_score": 0.5})
            move, thoughts = strategy.generate_move()
            assert move.gtp() == "Q16"


# ---------------------------------------------------------------------------
# ScoreLossStrategy
# ---------------------------------------------------------------------------


class TestScoreLossStrategy:
    def test_scoreloss_picks_top_when_pass(self):
        """When top move is pass, pass regardless of strategy."""
        candidates = [
            {
                "move": "pass",
                "order": 0,
                "scoreLead": 0.0,
                "pointsLost": 0.0,
                "visits": 100,
                "winrate": 0.5,
                "prior": 0.5,
            },
        ]
        with ai_test_context(candidate_moves=candidates) as (game, cn):
            strategy = ScoreLossStrategy(game, make_settings(AI_SCORELOSS))
            move, thoughts = strategy.generate_move()
            assert move.is_pass
