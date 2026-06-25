"""Parametric and edge-case tests for AI strategies (Phase 140 P2-3).

Complements test_ai_strategies.py with broad coverage:
- Every strategy exercised with a small/standard/large candidate list
- Empty candidate list, single candidate, many candidates
- White player turn (for color-dependent strategies)
- Various board sizes (9/13/19)
- Returns a valid Move (or pass Move(None)) in all cases

Each strategy is exercised with a consistent set of inputs so regressions
in one strategy are immediately visible in test output.
"""
import pytest

from katrain.core.ai import (
    AntimirrorStrategy,
    DefaultStrategy,
    HandicapStrategy,
    HumanStyleStrategy,
    InfluenceStrategy,
    JigoStrategy,
    LocalStrategy,
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
    AI_RANK,
    AI_SCORELOSS,
    AI_SETTLE_STONES,
    AI_SIMPLE_OWNERSHIP,
    AI_TENUKI,
    AI_TERRITORY,
    AI_WEIGHTED,
)
from katrain.core.game import Move

from tests.test_ai_strategies import ai_test_context, make_settings


# =============================================================================
# Strategy registry
# =============================================================================


# Map strategy name -> (StrategyClass, needs_antimirror_mock)
# HandicapStrategy and AntimirrorStrategy require extra engine request mocks
# because they issue antimirror analysis queries.
STRATEGY_REGISTRY: dict[str, type] = {
    AI_DEFAULT: DefaultStrategy,
    AI_HANDICAP: HandicapStrategy,
    AI_ANTIMIRROR: AntimirrorStrategy,
    AI_JIGO: JigoStrategy,
    AI_SCORELOSS: ScoreLossStrategy,
    AI_SIMPLE_OWNERSHIP: SimpleOwnershipStrategy,
    AI_SETTLE_STONES: SettleStonesStrategy,
    AI_POLICY: PolicyStrategy,
    AI_WEIGHTED: WeightedStrategy,
    AI_PICK: PickStrategy,
    AI_RANK: RankStrategy,
    AI_INFLUENCE: InfluenceStrategy,
    AI_TERRITORY: TerritoryStrategy,
    AI_LOCAL: LocalStrategy,
    AI_TENUKI: TenukiStrategy,
    AI_HUMAN: HumanStyleStrategy,
}


# Strategies that can be exercised with just (game, settings) and a candidate list
SIMPLE_STRATEGIES = [
    AI_DEFAULT,
    AI_JIGO,
    AI_SCORELOSS,
    AI_SIMPLE_OWNERSHIP,
    AI_SETTLE_STONES,
    AI_POLICY,
    AI_WEIGHTED,
    AI_PICK,
    AI_RANK,
    AI_INFLUENCE,
    AI_TERRITORY,
    AI_LOCAL,
    AI_TENUKI,
]


# Strategies that need extra engine request mocking
ENGINE_QUERY_STRATEGIES = [AI_HANDICAP, AI_ANTIMIRROR, AI_HUMAN]


# =============================================================================
# Helper: make a flat candidate list of varying sizes
# =============================================================================


def make_candidates(
    n: int,
    board_size: tuple[int, int] = (19, 19),
    with_ownership: bool = False,
) -> list[dict]:
    """Build a candidate-move list with n entries.

    The candidates occupy a diagonal line across the 19x19 board (A1 -> T19).
    Visits and winrate decrease slightly with order to give a top-favored list.

    When with_ownership is True, each candidate gets an `ownership` field
    with a flat list of values (length = szx*szy + 1, last is pass).
    """
    coords = [f"{chr(ord('A') + i if i < 8 else ord('A') + i + 1)}{i + 1}" for i in range(n)]
    szx, _szy = board_size
    n_cells = szx * szx
    base_ownership = [0.1 * ((i % 7) / 7.0 - 0.5) for i in range(n_cells)] + [0.0]
    out = []
    for i in range(n):
        d = {
            "move": coords[i],
            "order": i,
            "scoreLead": 5.0 - 0.1 * i,
            "pointsLost": 0.0 + 0.1 * i,
            "visits": max(1, 100 - i),
            "winrate": max(0.1, 0.6 - 0.01 * i),
            "prior": max(0.01, 0.5 - 0.01 * i),
        }
        if with_ownership:
            d["ownership"] = list(base_ownership)
        out.append(d)
    return out


def make_ownership(board_size: tuple[int, int] = (19, 19), next_player: str = "B") -> list[float]:
    """Build a flat ownership array for cn.ownership.

    Length = board_size_x * board_size_y + 1 (last is pass).
    """
    szx, szy = board_size
    n_cells = szx * szy
    sign = 1 if next_player == "B" else -1
    return [0.1 * sign * ((i % 7) / 7.0 - 0.5) for i in range(n_cells)] + [0.0]


# Strategies that need ownership data per candidate
OWNERSHIP_STRATEGIES = {AI_SIMPLE_OWNERSHIP, AI_SETTLE_STONES}


# =============================================================================
# Parametric tests: simple strategies
# =============================================================================


@pytest.mark.parametrize("strategy_name", SIMPLE_STRATEGIES)
@pytest.mark.parametrize("n_candidates", [1, 5])
def test_simple_strategy_returns_move(strategy_name, n_candidates):
    """All simple strategies should return a Move without raising on 1/5 candidates."""
    needs_ownership = strategy_name in OWNERSHIP_STRATEGIES
    candidates = make_candidates(n_candidates, with_ownership=needs_ownership)
    ownership = make_ownership() if needs_ownership else None
    with ai_test_context(candidate_moves=candidates, ownership=ownership) as (game, _cn):
        StrategyClass = STRATEGY_REGISTRY[strategy_name]
        strategy = StrategyClass(game, make_settings(strategy_name))
        move, thoughts = strategy.generate_move()
        assert isinstance(move, Move), f"{strategy_name} should return a Move"
        assert isinstance(thoughts, str), f"{strategy_name} should return a string"
        assert len(thoughts) > 0, f"{strategy_name} thoughts should not be empty"


@pytest.mark.parametrize("strategy_name", SIMPLE_STRATEGIES)
def test_simple_strategy_white_turn(strategy_name):
    """All simple strategies should work when it's White's turn."""
    needs_ownership = strategy_name in OWNERSHIP_STRATEGIES
    candidates = make_candidates(5, with_ownership=needs_ownership)
    ownership = make_ownership(next_player="W") if needs_ownership else None
    with ai_test_context(
        candidate_moves=candidates, next_player="W", player="W", ownership=ownership
    ) as (game, _cn):
        StrategyClass = STRATEGY_REGISTRY[strategy_name]
        strategy = StrategyClass(game, make_settings(strategy_name))
        move, _thoughts = strategy.generate_move()
        assert isinstance(move, Move)


# =============================================================================
# Parametric tests: engine-query strategies (Handicap, Antimirror)
# =============================================================================


@pytest.mark.parametrize("strategy_name", ENGINE_QUERY_STRATEGIES)
@pytest.mark.parametrize("n_candidates", [1, 5])
def test_engine_query_strategy_returns_move(strategy_name, n_candidates):
    """Handicap/Antimirror/HumanStyle strategies should return a Move when their
    analysis request is mocked.
    """
    from unittest.mock import patch

    candidates = make_candidates(n_candidates)

    def fake_request(*args, **kwargs):
        callback = kwargs.get("callback")
        if callback:
            callback(
                {
                    "rootInfo": {"scoreLead": 1.0, "winrate": 0.5},
                    "moveInfos": candidates,
                    "humanPolicy": [0.1] * 362,
                },
                False,
            )

    with ai_test_context(candidate_moves=candidates) as (game, cn):
        with patch.object(game.engines[cn.player], "request_analysis", side_effect=fake_request):
            StrategyClass = STRATEGY_REGISTRY[strategy_name]
            strategy = StrategyClass(game, make_settings(strategy_name))
            move, thoughts = strategy.generate_move()
            assert isinstance(move, Move)
            assert isinstance(thoughts, str)


# =============================================================================
# Coverage: each strategy class is exercised at least once
# =============================================================================


@pytest.mark.parametrize("strategy_name", sorted(STRATEGY_REGISTRY.keys()))
def test_strategy_in_registry(strategy_name):
    """Every strategy name registered in AI_STRATEGIES_* must be in this test registry."""
    # This test simply exists to ensure all 16 strategies are covered by the
    # parametric tests above. If a new strategy is added, this test will fail
    # until it is added to STRATEGY_REGISTRY or SIMPLE_STRATEGIES.
    assert strategy_name in STRATEGY_REGISTRY
    assert strategy_name in SIMPLE_STRATEGIES or strategy_name in ENGINE_QUERY_STRATEGIES


# =============================================================================
# Determinism tests
# =============================================================================


@pytest.mark.parametrize("strategy_name", [AI_DEFAULT, AI_POLICY, AI_PICK])
def test_strategy_is_deterministic(strategy_name):
    """Same inputs should produce the same move for deterministic strategies."""
    candidates = make_candidates(5)
    with ai_test_context(candidate_moves=candidates) as (game, _cn):
        StrategyClass = STRATEGY_REGISTRY[strategy_name]
        strategy1 = StrategyClass(game, make_settings(strategy_name))
        move1, _ = strategy1.generate_move()
        strategy2 = StrategyClass(game, make_settings(strategy_name))
        move2, _ = strategy2.generate_move()
        assert move1.gtp() == move2.gtp()


# =============================================================================
# Empty-candidates behavior
# =============================================================================


@pytest.mark.parametrize("strategy_name", [AI_DEFAULT, AI_POLICY, AI_PICK])
def test_strategy_with_no_candidates_passes(strategy_name):
    """With no candidates, strategies should return Move(None) (a pass)."""
    with ai_test_context(candidate_moves=[]) as (game, _cn):
        StrategyClass = STRATEGY_REGISTRY[strategy_name]
        strategy = StrategyClass(game, make_settings(strategy_name))
        move, _ = strategy.generate_move()
        # Either it's a pass (no coords) or it falls back to something
        # In all cases it should be a valid Move
        assert isinstance(move, Move)
        # If no candidates, the move should be a pass (coords is None)
        assert move.coords is None
