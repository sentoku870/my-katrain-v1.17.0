"""Move-selection AI strategy tests (Phase F-1).

Extracted from tests/test_ai_strategies.py. Covers ``PolicyStrategy``,
``WeightedStrategy``, ``PickBasedStrategy``, ``PickStrategy``,
``RankStrategy``, ``InfluenceStrategy`` - all of which share the
pick-from-candidates flow.
"""

from __future__ import annotations

from katrain.core.ai import (
    PickBasedStrategy,
    PickStrategy,
    PolicyStrategy,
    RankStrategy,
    WeightedStrategy,
)
from katrain.core.constants import (
    AI_PICK,
    AI_POLICY,
    AI_RANK,
    AI_WEIGHTED,
)
from katrain.core.game import Move
from tests.ai_strategies._helpers import ai_test_context, make_settings


class TestPolicyStrategy:
    def test_policy_no_policy_falls_back(self):
        """PolicyStrategy with no policy falls back to DefaultStrategy."""
        with ai_test_context(policy=None) as (game, cn):
            cn.analysis["moves"] = {
                "D4": {
                    "move": "D4",
                    "order": 0,
                    "scoreLead": 0.0,
                    "pointsLost": 0.0,
                    "visits": 100,
                    "winrate": 0.5,
                    "prior": 0.5,
                }
            }
            strategy = PolicyStrategy(game, make_settings(AI_POLICY))
            move, thoughts = strategy.generate_move()
            assert move.gtp() == "D4"

    def test_policy_with_high_top_move(self):
        """PolicyStrategy with high top move plays it."""
        # 19x19 policy with high weight at (0, 0) → GTP A1
        policy = [0.0] * (19 * 19 + 1)
        policy[0] = 0.5
        policy[19 * 19] = 0.01  # low pass
        with ai_test_context(policy=policy) as (game, cn):
            strategy = PolicyStrategy(game, make_settings(AI_POLICY))
            move, thoughts = strategy.generate_move()
            # Top move is (0, 0) = A1 in GTP
            assert move.gtp() == "A1"

    def test_policy_pass_in_top_5(self):
        """PolicyStrategy plays top move (not pass) when pass is in top 5."""
        policy = [0.0] * (19 * 19 + 1)
        # Top moves by policy
        policy[0] = 0.30  # (0, 0) = A1
        policy[1] = 0.20  # (1, 0) = B1
        policy[19] = 0.10  # (0, 1) = A2
        policy[20] = 0.05  # (1, 1) = B2
        # Pass has high weight (in top 5)
        policy[19 * 19] = 0.15  # pass
        with ai_test_context(policy=policy) as (game, cn):
            strategy = PolicyStrategy(game, make_settings(AI_POLICY))
            move, thoughts = strategy.generate_move()
            # Should not play pass
            assert not move.is_pass


# ---------------------------------------------------------------------------
# WeightedStrategy
# ---------------------------------------------------------------------------


class TestWeightedStrategy:
    def test_weighted_no_candidates_uses_policy(self):
        """WeightedStrategy with no analysis candidates returns top policy move."""
        policy = [0.0] * (19 * 19 + 1)
        policy[0] = 0.5
        with ai_test_context(policy=policy) as (game, cn):
            cn.analysis["moves"] = {}
            strategy = WeightedStrategy(game, make_settings(AI_WEIGHTED))
            move, thoughts = strategy.generate_move()
            # (0, 0) = A1 in GTP
            assert move.gtp() == "A1"


# ---------------------------------------------------------------------------
# PickBasedStrategy helpers
# ---------------------------------------------------------------------------


class TestPickBasedStrategy:
    def test_get_n_moves_with_pick_frac(self):
        """get_n_moves uses pick_frac * len + pick_n."""
        with ai_test_context() as (game, cn):
            strategy = PickBasedStrategy(game, {"pick_frac": 0.5, "pick_n": 3})
            moves = [(0.1, Move(coords=(i, 0))) for i in range(10)]
            n = strategy.get_n_moves(moves)
            assert n == 8

    def test_get_n_moves_default(self):
        """get_n_moves returns 1 when pick_frac is not set."""
        with ai_test_context() as (game, cn):
            strategy = PickBasedStrategy(game, {})
            n = strategy.get_n_moves([(0.1, Move(coords=(0, 0)))])
            assert n == 1

    def test_generate_weighted_coords(self):
        """generate_weighted_coords returns coords with equal weights for PICK."""
        with ai_test_context() as (game, cn):
            strategy = PickBasedStrategy(game, {"pick_frac": 0.5, "pick_n": 3})
            moves = [(0.3, Move(coords=(0, 0))), (0.2, Move(coords=(1, 1)))]
            # 2x3 grid with 3 positive values
            grid = [[0.3, 0.2, None], [None, 0.2, None]]
            coords, thoughts = strategy.generate_weighted_coords(moves, grid, (3, 2))
            # Grid has 3 positive values: (0,0)=0.3, (1,0)=0.2, (1,1)=0.2
            assert len(coords) == 3

    def test_handle_endgame_no_endgame(self):
        """handle_endgame returns False when not in endgame."""
        with ai_test_context() as (game, cn):
            strategy = PickBasedStrategy(game, {"pick_frac": 0.5, "pick_n": 3, "endgame": 0.75})
            moves = [(0.1, Move(coords=(0, 0)))]
            weighted, thoughts, n, is_endgame = strategy.handle_endgame(moves, [[0.1]], (19, 19))
            assert is_endgame is False

    def test_handle_endgame_in_endgame(self):
        """handle_endgame returns True when in endgame (move > threshold)."""
        with ai_test_context(depth=300) as (game, cn):
            strategy = PickBasedStrategy(game, {"pick_frac": 0.5, "pick_n": 3, "endgame": 0.75})
            moves = [(0.1, Move(coords=(0, 0)))]
            weighted, thoughts, n, is_endgame = strategy.handle_endgame(moves, [[0.1]], (19, 19))
            assert is_endgame is True


# ---------------------------------------------------------------------------
# PickStrategy / RankStrategy
# ---------------------------------------------------------------------------


class TestPickStrategy:
    def test_pick_strategy_runs(self):
        """PickStrategy.generate_move returns a move without crashing."""
        policy = [0.0] * (19 * 19 + 1)
        policy[0] = 0.5
        with ai_test_context(policy=policy) as (game, cn):
            strategy = PickStrategy(game, make_settings(AI_PICK))
            move, thoughts = strategy.generate_move()
            assert move is not None


class TestRankStrategy:
    def test_rank_strategy_runs(self):
        """RankStrategy.generate_move returns a move without crashing."""
        policy = [0.0] * (19 * 19 + 1)
        policy[0] = 0.5
        prev_move = Move.from_gtp("D4", player="B")
        with ai_test_context(policy=policy, move=prev_move) as (game, cn):
            strategy = RankStrategy(game, make_settings(AI_RANK))
            move, thoughts = strategy.generate_move()
            assert move is not None


# ---------------------------------------------------------------------------
# InfluenceStrategy / TerritoryStrategy / LocalStrategy / TenukiStrategy
# ---------------------------------------------------------------------------
