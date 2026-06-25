"""Tests for AI strategies and helpers in katrain/core/ai.py (Phase 139).

Covers:
- ai_rank_estimation() all branches
- game_report() basic flow
- All strategy classes' generate_move() with heavy cn mocking
- OwnershipBaseStrategy.is_attachment / settledness
- PickBasedStrategy helpers
- generate_ai_move() through the registry
- AI base utility functions (interp1d, interp2d, policy_weighted_move)
"""

import os
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.ai import (
    AntimirrorStrategy,
    DefaultStrategy,
    HandicapStrategy,
    HumanStyleStrategy,
    InfluenceStrategy,
    JigoStrategy,
    LocalStrategy,
    OwnershipBaseStrategy,
    PickBasedStrategy,
    PickStrategy,
    PolicyStrategy,
    RankStrategy,
    ScoreLossStrategy,
    SettleStonesStrategy,
    SimpleOwnershipStrategy,
    STRATEGY_REGISTRY,
    TenukiStrategy,
    TerritoryStrategy,
    WeightedStrategy,
    ai_rank_estimation,
    game_report,
    generate_ai_move,
)
from katrain.core.ai_strategies_base import (
    AIStrategy,
    generate_influence_territory_weights,
    generate_local_tenuki_weights,
    interp1d,
    interp2d,
    interp_ix,
    policy_weighted_move,
    register_strategy,
)
from katrain.core.constants import (
    AI_ANTIMIRROR,
    AI_DEFAULT,
    AI_HANDICAP,
    AI_HUMAN,
    AI_INFLUENCE,
    AI_JIGO,
    AI_LOCAL,
    AI_PICK,
    AI_POLICY,
    AI_PRO,
    AI_RANK,
    AI_SCORELOSS,
    AI_SETTLE_STONES,
    AI_SIMPLE_OWNERSHIP,
    AI_STRENGTH,
    AI_TENUKI,
    AI_TERRITORY,
    AI_WEIGHTED,
)
from katrain.core.game import Game, Move
from katrain.core.game_node import GameNode


# ---------------------------------------------------------------------------
# Test fixture: MockedCn wraps a Game + mocked current_node
# ---------------------------------------------------------------------------


class MockedCn:
    """A simple object that mimics the parts of GameNode used by AI strategies.

    It uses SimpleNamespace-style attribute setting to avoid the property
    restrictions of GameNode.
    """

    def __init__(
        self,
        analysis_complete: bool = True,
        candidate_moves: list[dict] | None = None,
        policy: list[float] | None = None,
        ownership: list[float] | None = None,
        next_player: str = "B",
        player: str = "B",
        depth: int = 1,
        move: Move | None = None,
        komi: float = 6.5,
        format_score_value: str = "B+0.0",
        format_winrate_value: str = "B 50.0%",
        board_size: tuple[int, int] = (19, 19),
    ):
        self.next_player = next_player
        self.player = player
        self.depth = depth
        self.move = move
        self.komi = komi
        self.board_size = board_size
        self.ownership = ownership
        self.policy = policy
        self.format_score = lambda *args, **kwargs: format_score_value
        self.format_winrate = lambda *args, **kwargs: format_winrate_value
        self.player_sign = lambda p: {"B": 1, "W": -1, None: 0}.get(p, 0)
        # analysis dict
        self.analysis = {
            "root": {"scoreLead": 0.0, "winrate": 0.5, "visits": 500},
            "moves": {m["move"]: m for m in (candidate_moves or [])},
            "completed": analysis_complete,
            "ownership": ownership,
            "policy": policy,
        }
        self.analysis_from_sgf = True
        # properties
        self.properties = {"B": [], "W": []} if not move else {move.player: [move.sgf(board_size)]}
        # nodes_from_root for game_report (just self for mocked)
        self._nodes_from_root = [self]

    def points_lost(self):
        return None

    @property
    def nodes_from_root(self):
        return self._nodes_from_root

    @property
    def is_root(self):
        return True  # mocked cn acts as root

    @property
    def parent(self):
        return None

    def parent_realized_points_lost(self):
        return None

    @property
    def children(self):
        return []

    @property
    def analysis_exists(self) -> bool:
        return self.analysis["root"] is not None

    @property
    def analysis_complete(self) -> bool:
        return self.analysis["completed"] and self.analysis["root"] is not None

    @property
    def score(self):
        if self.analysis_exists:
            return float(self.analysis["root"].get("scoreLead", 0))
        return None

    @property
    def policy_ranking(self):
        if not self.policy:
            return []
        szx, szy = self.board_size
        moves = [
            (self.policy[y * szx + x], Move((x, y), player=self.next_player))
            for x in range(szx)
            for y in range(szy)
        ]
        moves.append((self.policy[-1], Move(None, player=self.next_player)))
        return sorted(moves, key=lambda pm: -pm[0])

    @property
    def candidate_moves(self):
        if not self.analysis["moves"]:
            return []
        root_score = self.analysis["root"]["scoreLead"]
        root_winrate = self.analysis["root"]["winrate"]
        move_dicts = list(self.analysis["moves"].values())
        top_move = [d for d in move_dicts if d["order"] == 0]
        top_score_lead = top_move[0]["scoreLead"] if top_move else root_score
        return sorted(
            [
                {
                    "pointsLost": max(0, self.player_sign(self.next_player) * (root_score - d["scoreLead"])),
                    "relativePointsLost": max(
                        0, self.player_sign(self.next_player) * (top_score_lead - d["scoreLead"])
                    ),
                    "winrateLost": self.player_sign(self.next_player) * (root_winrate - d["winrate"]),
                    **d,
                }
                for d in move_dicts
            ],
            key=lambda d: (d["order"], d["pointsLost"]),
        )


@contextmanager
def ai_test_context(
    analysis_complete: bool = True,
    candidate_moves: list[dict] | None = None,
    policy: list[float] | None = None,
    ownership: list[float] | None = None,
    next_player: str = "B",
    player: str = "B",
    depth: int = 1,
    move: Move | None = None,
    komi: float = 6.5,
    format_score_value: str = "B+0.0",
    format_winrate_value: str = "B 50.0%",
    board_size: tuple[int, int] = (19, 19),
    stones: list[Move] | None = None,
):
    """Context manager that returns (game, cn) for AI strategy tests.

    `game` is a real Game instance (needed for game.engines, etc.).
    `cn` is a MockedCn that exposes the properties AI strategies need.
    """
    from tests.conftest import MockEngine, MockKaTrainStub

    katrain = MockKaTrainStub()
    engine = MockEngine()
    root = GameNode(properties={"SZ": board_size[0], "KM": komi, "RU": "japanese"})
    game = Game(katrain, engine, move_tree=root)

    # Set the current_node of the game
    cn = MockedCn(
        analysis_complete=analysis_complete,
        candidate_moves=candidate_moves,
        policy=policy,
        ownership=ownership,
        next_player=next_player,
        player=player,
        depth=depth,
        move=move,
        komi=komi,
        format_score_value=format_score_value,
        format_winrate_value=format_winrate_value,
        board_size=board_size,
    )

    # Patch game's current_node and the strategy's cn
    with patch.object(game, "current_node", new=cn):
        # Make wait_for_analysis a no-op
        with patch.object(AIStrategy, "wait_for_analysis", lambda self: None):
            if stones is not None:
                with patch.object(game, "stones", new=stones):
                    yield game, cn
            else:
                yield game, cn


def make_settings(strategy_name: str) -> dict:
    """Build default settings for a strategy."""
    defaults = {
        AI_DEFAULT: {"weaken_fac": 1.0},
        AI_HANDICAP: {"pda": 0.0, "automatic": False},
        AI_ANTIMIRROR: {},
        AI_JIGO: {"target_score": 0.5},
        AI_SCORELOSS: {"strength": 5.0},
        AI_SIMPLE_OWNERSHIP: {
            "max_points_lost": 2.0, "min_visits": 1,
            "attach_penalty": 0.0, "tenuki_penalty": 0.0,
            "settled_weight": 0.5, "opponent_fac": 0.5,
        },
        AI_SETTLE_STONES: {
            "max_points_lost": 2.0, "min_visits": 1, "settledness_threshold": 0.5,
            "attach_penalty": 0.0, "tenuki_penalty": 0.0,
            "settled_weight": 0.5, "opponent_fac": 0.5,
        },
        AI_POLICY: {"lower_bound": 0.0, "weaken_fac": 1.0, "override": 0.0, "overridetwo": 1.0, "opening_moves": 0},
        AI_WEIGHTED: {"lower_bound": 0.0, "weaken_fac": 1.0, "override": 0.0, "overridetwo": 1.0},
        AI_PICK: {"pick_frac": 0.5, "pick_n": 3, "override": 0.0, "overridetwo": 1.0},
        AI_RANK: {"kyu_rank": 5, "pick_frac": 0.5, "pick_n": 3, "override": 0.0, "overridetwo": 1.0},
        AI_INFLUENCE: {"threshold": 4, "line_weight": 0.5, "pick_frac": 0.5, "pick_n": 3, "override": 0.0, "overridetwo": 1.0},
        AI_TERRITORY: {"threshold": 3, "line_weight": 0.5, "pick_frac": 0.5, "pick_n": 3, "override": 0.0, "overridetwo": 1.0},
        AI_LOCAL: {"stddev": 3.0, "pick_frac": 0.5, "pick_n": 3, "override": 0.0, "overridetwo": 1.0},
        AI_TENUKI: {"stddev": 3.0, "pick_frac": 0.5, "pick_n": 3, "override": 0.0, "overridetwo": 1.0},
        AI_HUMAN: {"human_kyu_rank": 5, "lower_bound": 0.0, "weaken_fac": 1.0, "override": 0.0, "overridetwo": 1.0, "modern_style": False},
    }
    return defaults.get(strategy_name, {})


# ---------------------------------------------------------------------------
# ai_rank_estimation
# ---------------------------------------------------------------------------


class TestAiRankEstimation:
    def test_default_strategies_return_9(self):
        """AI_DEFAULT, AI_HANDICAP, AI_JIGO, AI_PRO all return 9.0."""
        for s in [AI_DEFAULT, AI_HANDICAP, AI_JIGO, AI_PRO]:
            assert ai_rank_estimation(s, {}) == 9.0

    def test_rank_strategy(self):
        """AI_RANK: 1 - kyu_rank."""
        assert ai_rank_estimation(AI_RANK, {"kyu_rank": 5}) == 1 - 5

    def test_human_strategy(self):
        """AI_HUMAN: 1 - human_kyu_rank."""
        assert ai_rank_estimation(AI_HUMAN, {"human_kyu_rank": 8}) == 1 - 8

    def test_weighted_uses_weaken_fac(self):
        """AI_WEIGHTED: interpolate from AI_WEIGHTED_ELO using weaken_fac."""
        result = ai_rank_estimation(AI_WEIGHTED, {"weaken_fac": 1.0})
        assert isinstance(result, float)
        assert -30 <= result <= 9

    def test_scoreloss_uses_strength(self):
        """AI_SCORELOSS: interpolate from AI_SCORELOSS_ELO using strength."""
        result = ai_rank_estimation(AI_SCORELOSS, {"strength": 5.0})
        assert isinstance(result, float)
        assert -30 <= result <= 9

    def test_pick_uses_pick_frac_pick_n(self):
        """AI_PICK: 2D interpolation from AI_PICK_ELO_GRID."""
        result = ai_rank_estimation(AI_PICK, {"pick_frac": 0.5, "pick_n": 3})
        assert isinstance(result, float)
        assert -30 <= result <= 9

    def test_local_tenuki_territory_influence(self):
        """2D interpolation strategies all return a float."""
        for s in [AI_LOCAL, AI_TENUKI, AI_TERRITORY, AI_INFLUENCE]:
            result = ai_rank_estimation(s, {"pick_frac": 0.5, "pick_n": 3})
            assert isinstance(result, float)
            assert -30 <= result <= 9

    def test_unknown_uses_ai_strength(self):
        """Unknown strategy falls back to AI_STRENGTH dict."""
        AI_STRENGTH["custom_xyz"] = 5.0
        try:
            result = ai_rank_estimation("custom_xyz", {})
            assert result == 5.0
        finally:
            AI_STRENGTH.pop("custom_xyz", None)


# ---------------------------------------------------------------------------
# game_report
# ---------------------------------------------------------------------------


class TestGameReport:
    def test_game_report_empty_game(self):
        """game_report on empty game returns empty stats."""
        with ai_test_context() as (game, cn):
            sum_stats, histogram, ptloss = game_report(game, [0, 1, 2, 5])
            for bw in "BW":
                assert sum_stats[bw] == {} or "mean_ptloss" not in sum_stats.get(bw, {})

    def test_game_report_with_no_points_lost(self):
        """game_report handles nodes with no points_lost gracefully."""
        with ai_test_context() as (game, cn):
            sum_stats, histogram, ptloss = game_report(game, [0, 1, 2, 5])
            assert ptloss == {"B": [], "W": []}

    def test_game_report_depth_filter_no_passes(self):
        """depth_filter restricts but no moves are analyzed."""
        with ai_test_context(depth=1) as (game, cn):
            sum_stats, histogram, ptloss = game_report(game, [0, 1, 2, 5], depth_filter=(0, 0.1))
            assert isinstance(sum_stats, dict)


# ---------------------------------------------------------------------------
# DefaultStrategy
# ---------------------------------------------------------------------------


class TestDefaultStrategy:
    def test_default_with_candidates(self):
        """DefaultStrategy plays the top candidate."""
        candidates = [
            {"move": "D4", "order": 0, "scoreLead": 5.0, "pointsLost": 0.0, "visits": 100, "winrate": 0.6, "prior": 0.5},
            {"move": "Q16", "order": 1, "scoreLead": -1.0, "pointsLost": 6.0, "visits": 80, "winrate": 0.4, "prior": 0.3},
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
            {"move": "D4", "order": 0, "scoreLead": 0.0, "pointsLost": 0.0, "visits": 100, "winrate": 0.5, "prior": 0.5},
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
            {"move": "E5", "order": 0, "scoreLead": 2.0, "pointsLost": 0.0, "visits": 100, "winrate": 0.55, "prior": 0.5},
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
            {"move": "D4", "order": 0, "scoreLead": 5.0, "pointsLost": 0.0, "visits": 100, "winrate": 0.5, "prior": 0.5},
            {"move": "Q16", "order": 1, "scoreLead": 0.5, "pointsLost": 4.5, "visits": 80, "winrate": 0.5, "prior": 0.3},
            {"move": "D16", "order": 2, "scoreLead": 10.0, "pointsLost": 5.0, "visits": 60, "winrate": 0.5, "prior": 0.2},
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
            {"move": "pass", "order": 0, "scoreLead": 0.0, "pointsLost": 0.0, "visits": 100, "winrate": 0.5, "prior": 0.5},
        ]
        with ai_test_context(candidate_moves=candidates) as (game, cn):
            strategy = ScoreLossStrategy(game, make_settings(AI_SCORELOSS))
            move, thoughts = strategy.generate_move()
            assert move.is_pass


# ---------------------------------------------------------------------------
# OwnershipBaseStrategy.is_attachment / settledness
# ---------------------------------------------------------------------------


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
            {"move": "D4", "order": 0, "scoreLead": 0.0, "pointsLost": 0.5, "visits": 100, "winrate": 0.5, "prior": 0.5, "ownership": [0.1] * 361},
        ]
        with ai_test_context(candidate_moves=candidates) as (game, cn):
            strategy = SimpleOwnershipStrategy(game, make_settings(AI_SIMPLE_OWNERSHIP))
            move, thoughts = strategy.generate_move()
            assert move is not None


class TestSettleStonesStrategy:
    def test_settle_stones_runs_with_moves(self):
        """SettleStonesStrategy runs without crashing when moves are available."""
        candidates = [
            {"move": "D4", "order": 0, "scoreLead": 0.0, "pointsLost": 0.5, "visits": 100, "winrate": 0.5, "prior": 0.5, "ownership": [0.1] * 361},
        ]
        with ai_test_context(candidate_moves=candidates) as (game, cn):
            strategy = SettleStonesStrategy(game, make_settings(AI_SETTLE_STONES))
            move, thoughts = strategy.generate_move()
            assert move is not None


# ---------------------------------------------------------------------------
# PolicyStrategy
# ---------------------------------------------------------------------------


class TestPolicyStrategy:
    def test_policy_no_policy_falls_back(self):
        """PolicyStrategy with no policy falls back to DefaultStrategy."""
        with ai_test_context(policy=None) as (game, cn):
            cn.analysis["moves"] = {
                "D4": {"move": "D4", "order": 0, "scoreLead": 0.0, "pointsLost": 0.0, "visits": 100, "winrate": 0.5, "prior": 0.5}
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
            {"move": "D4", "order": 0, "scoreLead": 0.0, "pointsLost": 0.0, "visits": 100, "winrate": 0.5, "prior": 0.5},
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
# generate_ai_move
# ---------------------------------------------------------------------------


class TestGenerateAiMove:
    def test_registry_has_all_strategies(self):
        """All known strategies are in the registry."""
        for name in [AI_DEFAULT, AI_HANDICAP, AI_ANTIMIRROR, AI_JIGO, AI_SCORELOSS,
                     AI_SIMPLE_OWNERSHIP, AI_SETTLE_STONES, AI_POLICY, AI_WEIGHTED,
                     AI_PICK, AI_RANK, AI_INFLUENCE, AI_TERRITORY, AI_LOCAL,
                     AI_TENUKI, AI_HUMAN, AI_PRO]:
            assert name in STRATEGY_REGISTRY, f"{name} not in registry"

    def test_generate_ai_move_default(self):
        """generate_ai_move creates the right strategy and plays a move."""
        candidates = [
            {"move": "D4", "order": 0, "scoreLead": 0.0, "pointsLost": 0.0, "visits": 100, "winrate": 0.5, "prior": 0.5},
        ]
        with ai_test_context(candidate_moves=candidates) as (game, cn):
            # Patch game.play so we don't actually mutate state
            with patch.object(game, "play") as mock_play:
                mock_node = MagicMock()
                mock_node.ai_thoughts = None
                mock_play.return_value = mock_node
                move, played_node = generate_ai_move(game, AI_DEFAULT, make_settings(AI_DEFAULT))
                assert move.gtp() == "D4"
                assert played_node is mock_node
                # generate_ai_move sets ai_thoughts on the played_node
                assert "Default strategy" in mock_node.ai_thoughts


# ---------------------------------------------------------------------------
# AI base utility functions
# ---------------------------------------------------------------------------


class TestInterpolationUtils:
    def test_interp_ix_basic(self):
        result = interp_ix([1.0, 2.0, 3.0, 4.0], 2.5)
        i, t = result
        assert i == 1
        assert t == 0.5

    def test_interp_ix_at_boundary(self):
        result = interp_ix([1.0, 2.0, 3.0], 1.0)
        i, t = result
        assert t == 0.0

    def test_interp1d(self):
        result = interp1d([(1.0, 10.0), (2.0, 20.0), (3.0, 30.0)], 1.5)
        assert abs(result - 15.0) < 0.01

    def test_interp2d_bilinear(self):
        gridspec = ([1.0, 2.0, 3.0], [10.0, 20.0], [[100.0, 200.0, 300.0], [400.0, 500.0, 600.0]])
        # x=2.0 is at index 1 exactly (t=0), y=15.0 is between 10 and 20 (s=0.5)
        # (1-t)(1-s)*m[0][1] + t(1-s)*m[0][2] + (1-t)s*m[1][1] + t*s*m[1][2]
        # = 1*0.5*200 + 0*0.5*300 + 1*0.5*500 + 0*0.5*600 = 100 + 0 + 250 + 0 = 350
        result = interp2d(gridspec, 2.0, 15.0)
        assert result == 350.0


class TestPolicyWeightedMove:
    def test_policy_weighted_move_picks(self):
        """policy_weighted_move returns a move from the candidates."""
        moves = [
            (0.5, Move.from_gtp("D4", player="B")),
            (0.3, Move.from_gtp("Q16", player="B")),
        ]
        move, thoughts = policy_weighted_move(moves, 0.0, 1.0)
        assert move.gtp() in ("D4", "Q16")

    def test_policy_weighted_move_no_above_bound(self):
        """When no moves are above lower_bound, return top policy move."""
        moves = [
            (0.01, Move.from_gtp("D4", player="B")),
            (0.005, Move.from_gtp("Q16", player="B")),
        ]
        move, thoughts = policy_weighted_move(moves, 0.5, 1.0)
        # No moves above 0.5 → top policy move (D4)
        assert move.gtp() == "D4"

    def test_policy_weighted_move_skips_pass(self):
        """Pass moves are excluded from weighted selection."""
        pass_move = Move(None, player="B")
        moves = [
            (0.5, pass_move),  # Pass at top
            (0.3, Move.from_gtp("D4", player="B")),
        ]
        move, thoughts = policy_weighted_move(moves, 0.0, 1.0)
        # Pass is filtered out → D4 is picked
        assert move.gtp() == "D4"


class TestGenerateWeights:
    def test_generate_influence_territory_weights_influence(self):
        """Influence weights higher for positions far from edge."""
        grid = [[0.1, 0.2, 0.3], [0.05, 0.5, 0.05], [0.0, 0.0, 0.0]]
        coords, thoughts = generate_influence_territory_weights(
            AI_INFLUENCE, {"threshold": 1, "line_weight": 0.5}, grid, (3, 3)
        )
        assert len(coords) >= 1

    def test_generate_influence_territory_weights_territory(self):
        """Territory weights higher for positions near center/edge."""
        grid = [[0.1, 0.2, 0.3], [0.05, 0.5, 0.05], [0.0, 0.0, 0.0]]
        coords, thoughts = generate_influence_territory_weights(
            AI_TERRITORY, {"threshold": 1, "line_weight": 0.5}, grid, (3, 3)
        )
        assert len(coords) >= 1

    def test_generate_local_tenuki_weights(self):
        """Local/Tenuki weights based on distance from previous move."""
        grid = [[0.5, 0.3, 0.1], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        prev_move = Move.from_gtp("A19", player="B")
        with ai_test_context(move=prev_move) as (game, cn):
            coords, thoughts = generate_local_tenuki_weights(
                AI_LOCAL, {"stddev": 2.0}, grid, cn, (3, 3)
            )
            assert len(coords) >= 1


# ---------------------------------------------------------------------------
# register_strategy decorator
# ---------------------------------------------------------------------------


class TestRegisterStrategy:
    def test_register_strategy_adds_to_registry(self):
        """register_strategy adds a class to the registry under the given name."""

        @register_strategy("test:custom_strategy")
        class CustomTestStrategy(AIStrategy):
            def generate_move(self):
                return Move(None, player="B"), "test"

        assert "test:custom_strategy" in STRATEGY_REGISTRY
        assert STRATEGY_REGISTRY["test:custom_strategy"] is CustomTestStrategy
        del STRATEGY_REGISTRY["test:custom_strategy"]
