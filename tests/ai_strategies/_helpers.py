"""Shared fixtures for AI-strategy tests (Phase F-1).

Extracted from tests/test_ai_strategies.py. Provides:
- :class:`MockedCn` - a SimpleNamespace-style stand-in for ``GameNode``
  that exposes the properties every AI strategy reads.
- :func:`ai_test_context` - context manager that returns ``(game, cn)``
  with a real ``Game`` and a mocked current_node.
- :func:`make_settings` - default settings dict per strategy name.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

from katrain.core.ai import (
    AntimirrorStrategy,
    DefaultStrategy,
    HandicapStrategy,
    HumanStyleStrategy,
    InfluenceStrategy,
    JigoStrategy,
    LocalStrategy,
    PickBasedStrategy,
    PickStrategy,
    PolicyStrategy,
    RankStrategy,
    ScoreLossStrategy,
    SettleStonesStrategy,
    SimpleOwnershipStrategy,
    TenukiStrategy,
    TerritoryStrategy,
    WeightedStrategy,
)
from katrain.core.ai_strategies_base import AIStrategy
from katrain.core.ai.constants import (
    AI_ANTIMIRROR,
    AI_DEFAULT,
    AI_HANDICAP,
    AI_HUMAN,
    AI_INFLUENCE,
    AI_JIGO,
    AI_LOCAL,
    AI_PICK,
    AI_POLICY,
    AI_RANK,
    AI_SCORELOSS,
    AI_SETTLE_STONES,
    AI_SIMPLE_OWNERSHIP,
    AI_TENUKI,
    AI_TERRITORY,
    AI_WEIGHTED,
)
from katrain.core.game import Game, Move
from katrain.core.game_node import GameNode

# Re-export strategy classes so existing ``from tests._helpers import
# DefaultStrategy``-style imports keep working.
__all__ = [
    "AntimirrorStrategy",
    "DefaultStrategy",
    "HandicapStrategy",
    "HumanStyleStrategy",
    "InfluenceStrategy",
    "JigoStrategy",
    "LocalStrategy",
    "MockedCn",
    "PickBasedStrategy",
    "PickStrategy",
    "PolicyStrategy",
    "RankStrategy",
    "ScoreLossStrategy",
    "SettleStonesStrategy",
    "SimpleOwnershipStrategy",
    "TenukiStrategy",
    "TerritoryStrategy",
    "WeightedStrategy",
    "ai_test_context",
    "make_settings",
]


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
            (self.policy[y * szx + x], Move((x, y), player=self.next_player)) for x in range(szx) for y in range(szy)
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
    with patch.object(game, "current_node", new=cn), patch.object(AIStrategy, "wait_for_analysis", lambda self: None):
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
            "max_points_lost": 2.0,
            "min_visits": 1,
            "attach_penalty": 0.0,
            "tenuki_penalty": 0.0,
            "settled_weight": 0.5,
            "opponent_fac": 0.5,
        },
        AI_SETTLE_STONES: {
            "max_points_lost": 2.0,
            "min_visits": 1,
            "settledness_threshold": 0.5,
            "attach_penalty": 0.0,
            "tenuki_penalty": 0.0,
            "settled_weight": 0.5,
            "opponent_fac": 0.5,
        },
        AI_POLICY: {"lower_bound": 0.0, "weaken_fac": 1.0, "override": 0.0, "overridetwo": 1.0, "opening_moves": 0},
        AI_WEIGHTED: {"lower_bound": 0.0, "weaken_fac": 1.0, "override": 0.0, "overridetwo": 1.0},
        AI_PICK: {"pick_frac": 0.5, "pick_n": 3, "override": 0.0, "overridetwo": 1.0},
        AI_RANK: {"kyu_rank": 5, "pick_frac": 0.5, "pick_n": 3, "override": 0.0, "overridetwo": 1.0},
        AI_INFLUENCE: {
            "threshold": 4,
            "line_weight": 0.5,
            "pick_frac": 0.5,
            "pick_n": 3,
            "override": 0.0,
            "overridetwo": 1.0,
        },
        AI_TERRITORY: {
            "threshold": 3,
            "line_weight": 0.5,
            "pick_frac": 0.5,
            "pick_n": 3,
            "override": 0.0,
            "overridetwo": 1.0,
        },
        AI_LOCAL: {"stddev": 3.0, "pick_frac": 0.5, "pick_n": 3, "override": 0.0, "overridetwo": 1.0},
        AI_TENUKI: {"stddev": 3.0, "pick_frac": 0.5, "pick_n": 3, "override": 0.0, "overridetwo": 1.0},
        AI_HUMAN: {
            "human_kyu_rank": 5,
            "lower_bound": 0.0,
            "weaken_fac": 1.0,
            "override": 0.0,
            "overridetwo": 1.0,
            "modern_style": False,
        },
    }
    return defaults.get(strategy_name, {})
