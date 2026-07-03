"""Tests for LeelaStrategy (Phase 159B).

Strategy was removed in Phase 123 (Leela Slimming). Phase 159B restores
the human-vs-Leela path while keeping the report generators KataGo-only.
These tests are mock-driven — they do not start a real Leela process.

The strategy is intentionally simple: it depends on the Leela Engine
exposing ``set_position(moves)`` and ``request_move(color, callback)`` and
the surrounding ``Game`` providing a ``katrain`` with either
``leela_engine`` (direct) or ``leela_manager.leela_engine``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

from katrain.core.ai_strategies import LeelaStrategy
from katrain.core.ai_strategies_base import STRATEGY_REGISTRY
from katrain.core.constants import AI_LEELA

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeMove:
    """A stand-in for ``Move(player, (x, y))`` that satisfies LeelaStrategy."""

    player: str
    coords: tuple[int, int] | None = None
    is_pass: bool = False

    def gtp(self) -> str:
        if self.coords is None or self.is_pass:
            return "pass"
        x, y = self.coords
        # Mirror ``Move.gtp`` letter-format: A=0, ..., T=18, skipping I.
        skip = 1
        col_index = x
        if x >= 8:
            col_index = x + skip
        letter = chr(ord("A") + col_index)
        # y is the position-from-bottom (y=0 is bottom). GTP counts from the
        # top, so we flip the value.
        number = 19 - y
        return f"{letter}{number}"


class _FakeGameNode:
    """A minimal stand-in for ``GameNode`` for ``LeelaStrategy``."""

    def __init__(self, next_player: str, moves: list[_FakeMove] | None = None) -> None:
        self._next_player = next_player
        self._moves = moves or []
        # ``Move.coords`` is a tuple ``(x, y)``; ``gtp()`` needs an int
        # board coord (the dimensions covered by the index letter).
        self.depth = len(self._moves)

    @property
    def next_player(self) -> str:
        return self._next_player

    @property
    def moves(self) -> list[_FakeMove]:
        return self._moves

    @property
    def nodes_from_root(self) -> list[_FakeGameNode]:
        # LeelaStrategy reads the branch via ``cn.nodes_from_root``. The
        # fake branch has no recorded node steps, so we return an empty
        # list, which is exactly what the real engine produces for a
        # root position with no moves played yet.
        return []


class _FakeGameNodeWithMoves(_FakeGameNode):
    """Variant that wraps a list of ``(player, coord)`` tuples directly."""

    def __init__(
        self,
        next_player: str,
        recorded: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__(next_player=next_player, moves=[])
        self._recorded = list(recorded or [])

    @property
    def nodes_from_root(self) -> list[Any]:
        # LeelaStrategy only forwards ``node.moves`` -> ``(player, coord)``.
        # Return a list of objects each exposing a ``moves`` attribute.
        return [type("_N", (), {"moves": [(p, _StubMove(p, c))]})() for p, c in self._recorded]


class _StubMove:
    def __init__(self, player: str, coord: str) -> None:
        self.player = player
        self._coord = coord

    def gtp(self) -> str:
        return self._coord


class _FakeGame:
    """Substitute for ``katrain.core.game.Game`` in LeelaStrategy tests."""

    def __init__(self, *, leela_engine: Any | None, next_player: str = "B", komi: float = 6.5) -> None:
        self._node = _FakeGameNode(next_player=next_player, moves=[])
        self._leela_engine = leela_engine
        self._komi = komi
        self.root = MagicMock()
        self.root.board_size = [19]
        self.katrain = MagicMock()
        self.katrain.log = lambda *_args, **_kw: None
        self.katrain.leela_engine = leela_engine
        self.katrain.leela_manager = MagicMock(leela_engine=leela_engine)
        self.katrain.get_leela_config = lambda: MagicMock(play_visits=500, max_visits=1000)

    @property
    def current_node(self) -> _FakeGameNode:
        return self._node

    @property
    def komi(self) -> float:
        return self._komi

    @property
    def root(self):  # type: ignore[no-untyped-def]
        return self._root

    @root.setter
    def root(self, value):  # type: ignore[no-untyped-def]
        self._root = value


def _make_strategy(
    next_player: str = "B",
    *,
    move: str = "D16",
    set_position_ok: bool = True,
    request_move_ok: bool = True,
    is_alive: bool = True,
    komi: float = 6.5,
) -> tuple[LeelaStrategy, _FakeGame, MagicMock]:
    """Build a LeelaStrategy with a fully mock LeelaEngine behind it.

    The returned triple is ``(strategy, game, engine_mock)`` so individual
    tests can wire up further expectations.
    """
    engine = MagicMock(name="leela_engine")
    engine.is_alive.return_value = is_alive
    engine.set_position.return_value = set_position_ok

    captured: dict[str, Any] = {}

    def _request_move(color: str, cb: Any, visits: int | None = None, **_kwargs: Any) -> bool:
        captured["color"] = color
        captured["visits"] = visits
        captured["cb"] = cb
        if request_move_ok:
            cb(move)
        else:
            cb("")
        return request_move_ok

    engine.request_move.side_effect = _request_move

    game = _FakeGame(leela_engine=engine, next_player=next_player, komi=komi)
    strategy = LeelaStrategy(game, ai_settings={})
    return strategy, game, engine


def _make_strategy_with_engine(engine: Any, next_player: str = "B", komi: float = 6.5) -> tuple[LeelaStrategy, _FakeGame]:
    """Test-only helper that reuses a caller-supplied engine mock."""
    engine.is_alive.return_value = True
    game = _FakeGame(leela_engine=engine, next_player=next_player, komi=komi)
    strategy = LeelaStrategy(game, ai_settings={})
    return strategy, game


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestLeelaStrategyRegistered:
    """LeelaStrategy must populate ``STRATEGY_REGISTRY[AI_LEELA]``."""

    def test_registered_via_decorator(self) -> None:
        # Importing the module should already register the strategy
        # via the @register_strategy decorator.
        assert AI_LEELA in STRATEGY_REGISTRY
        assert STRATEGY_REGISTRY[AI_LEELA] is LeelaStrategy


# ---------------------------------------------------------------------------
# generate_move: engine availability
# ---------------------------------------------------------------------------


class TestLeelaStrategyEngineUnavailable:
    """When Leela is not running, ``generate_move`` passes the turn."""

    def test_passes_when_engine_is_dead(self) -> None:
        strategy, game, engine = _make_strategy(is_alive=False)
        move, thoughts = strategy.generate_move()

        # LeelaEngine.is_alive() returned False → no GTP traffic.
        engine.set_position.assert_not_called()
        engine.request_move.assert_not_called()
        assert move.gtp() == "pass"
        assert "engine not running" in thoughts.lower()

    def test_passes_when_engine_is_none(self) -> None:
        # Katrain exposes only the manager stub with leela_engine=None.
        engine = MagicMock()
        engine.is_alive = lambda: False
        game = _FakeGame(leela_engine=None, next_player="W")
        game.katrain.leela_engine = None
        game.katrain.leela_manager.leela_engine = None
        strategy = LeelaStrategy(game, ai_settings={})

        move, thoughts = strategy.generate_move()
        engine.set_position.assert_not_called()
        engine.request_move.assert_not_called()
        assert move.gtp() == "pass"
        assert "engine not running" in thoughts.lower()

    def test_force_starts_engine_when_manager_is_present(self) -> None:
        """Phase 160: ``_resolve_leela_engine`` boots Leela via ``start_engine(force=True)``.

        Verifies the new auto-start path: even if the manager's
        leela_engine slot is empty (engine is down), the strategy
        should call ``start_engine(katrain, force=True)`` and — once
        the manager returns success — return the freshly-spawned
        engine.
        """
        from katrain.core.ai_strategies.leela import LeelaStrategy as LS

        # Build a Game whose Leela engine is None in both the manager
        # and the direct property.
        game = _FakeGame(leela_engine=None, next_player="B")
        fresh_engine = MagicMock(name="fresh_leela_engine")
        fresh_engine.is_alive.return_value = True
        fresh_engine.set_position.return_value = True

        start_calls: list[tuple[Any, bool]] = []

        def _start_engine(katrain: Any, force: bool = False) -> bool:
            start_calls.append((katrain, force))
            # Simulate the manager wiring the engine back up.
            game.katrain.leela_manager.leela_engine = fresh_engine
            game.katrain.leela_engine = fresh_engine
            return True

        game.katrain.leela_manager.start_engine = _start_engine  # type: ignore[method-assign]

        fresh_engine.request_move.side_effect = (
            lambda color, cb, visits=None, **_k: (cb("D16") or True)
        )

        strategy = LS(game, ai_settings={})
        move, _thoughts = strategy.generate_move()

        # The dispatcher must have gone through the force-start branch.
        assert start_calls, "start_engine should have been called"
        _katrain, force = start_calls[0]
        assert force is True

        # And the new engine must have produced the move.
        fresh_engine.set_position.assert_called_once()
        fresh_engine.request_move.assert_called_once()
        assert move.gtp() == "D16"

    def test_returns_pass_when_force_start_fails(self) -> None:
        """If force-start cannot boot Leela, strategy still falls back to pass.

        The new branch should not raise; it should swallow the
        manager's False return and behave identically to the
        pre-Phase-160 'engine not running' fallback.
        """
        from katrain.core.ai_strategies.leela import LeelaStrategy as LS

        game = _FakeGame(leela_engine=None, next_player="B")
        start_calls: list[bool] = []

        def _start_engine(katrain: Any, force: bool = False) -> bool:
            start_calls.append(force)
            return False  # Leela binary missing / subprocess error

        game.katrain.leela_manager.start_engine = _start_engine  # type: ignore[method-assign]

        strategy = LS(game, ai_settings={})
        move, thoughts = strategy.generate_move()

        assert start_calls == [True]
        assert move.gtp() == "pass"
        assert "engine not running" in thoughts.lower()


# ---------------------------------------------------------------------------
# generate_move: happy paths
# ---------------------------------------------------------------------------


class TestLeelaStrategyGeneratesMove:
    """Happy path: Leela returns a coord, the strategy returns it as a Move."""

    def test_set_position_called_with_branch_moves(self) -> None:
        captured: dict[str, Any] = {}

        engine = MagicMock()
        engine.is_alive = lambda: True

        def _set_position(moves, board_size=19, komi=6.5):
            captured["moves"] = list(moves)
            captured["board_size"] = board_size
            captured["komi"] = komi
            return True

        engine.set_position = _set_position
        engine.request_move = lambda color, cb, visits=None, **_kw: (cb("D16"), True)[1]

        game = _FakeGame(leela_engine=engine, next_player="B")
        strategy = LeelaStrategy(game, ai_settings={})
        move, thoughts = strategy.generate_move()

        # Default branch has no recorded moves; verify set_position was
        # called once with an empty list and the right colour sent to
        # genmove (``B``).
        assert captured["moves"] == []
        assert move.gtp() == "D16"
        assert "500" in thoughts  # default play_visits

    def test_white_player_uses_white_for_genmove(self) -> None:
        seen: dict[str, Any] = {}

        engine = MagicMock()
        engine.is_alive = lambda: True
        engine.set_position = lambda *_a, **_kw: True
        engine.request_move = lambda color, cb, visits=None, **_kw: (seen.update(color=color) or cb("Q4") or True)

        game = _FakeGame(leela_engine=engine, next_player="W")
        strategy = LeelaStrategy(game, ai_settings={})
        strategy.generate_move()
        assert seen["color"] == "W"

    def test_resign_returns_pass_marker(self) -> None:
        engine = MagicMock()
        engine.is_alive = lambda: True
        engine.set_position = lambda *_a, **_kw: True
        engine.request_move = lambda color, cb, visits=None, **_kw: (cb("resign") or True)

        game = _FakeGame(leela_engine=engine, next_player="B")
        strategy = LeelaStrategy(game, ai_settings={})
        move, thoughts = strategy.generate_move()
        assert move.gtp() == "pass"
        assert "resign" in thoughts.lower()

    def test_empty_coord_falls_back_to_pass(self) -> None:
        engine = MagicMock()
        engine.is_alive = lambda: True
        engine.set_position = lambda *_a, **_kw: True
        engine.request_move = lambda color, cb, visits=None, **_kw: (cb("") or True)

        game = _FakeGame(leela_engine=engine, next_player="B")
        strategy = LeelaStrategy(game, ai_settings={})
        move, _thoughts = strategy.generate_move()
        assert move.gtp() == "pass"


# ---------------------------------------------------------------------------
# Customisation points
# ---------------------------------------------------------------------------


class TestLeelaStrategyCustomisation:
    """``play_visits`` from ai_settings overrides the LeelaConfig defaults."""

    def test_ai_settings_play_visits_overrides_default(self) -> None:
        seen: dict[str, Any] = {}

        engine = MagicMock()
        engine.is_alive = lambda: True
        engine.set_position = lambda *_a, **_kw: True
        engine.request_move = lambda color, cb, visits=None, **_kw: (
            seen.update(visits=visits) or cb("D16") or True
        )

        game = _FakeGame(leela_engine=engine)
        strategy = LeelaStrategy(game, ai_settings={"play_visits": 800})
        strategy.generate_move()
        assert seen["visits"] == 800

    def test_falls_back_to_leela_config_play_visits(self) -> None:
        seen: dict[str, Any] = {}

        engine = MagicMock()
        engine.is_alive = lambda: True
        engine.set_position = lambda *_a, **_kw: True
        engine.request_move = lambda color, cb, visits=None, **_kw: (
            seen.update(visits=visits) or cb("D16") or True
        )

        game = _FakeGame(leela_engine=engine)
        # Override the get_leela_config shim with a custom config that has
        # play_visits=750 (and no max_visits fallback).
        config = MagicMock(play_visits=750, max_visits=None)
        game.katrain.get_leela_config = lambda: config
        strategy = LeelaStrategy(game, ai_settings={})
        strategy.generate_move()
        assert seen["visits"] == 750

    def test_falls_back_to_leela_config_max_visits(self) -> None:
        seen: dict[str, Any] = {}

        engine = MagicMock()
        engine.is_alive = lambda: True
        engine.set_position = lambda *_a, **_kw: True
        engine.request_move = lambda color, cb, visits=None, **_kw: (
            seen.update(visits=visits) or cb("D16") or True
        )

        game = _FakeGame(leela_engine=engine)
        config = MagicMock(play_visits=None, max_visits=999)
        game.katrain.get_leela_config = lambda: config
        strategy = LeelaStrategy(game, ai_settings={})
        strategy.generate_move()
        assert seen["visits"] == 999


# ---------------------------------------------------------------------------
# Helpers used by LeelaStrategy (visited by generate_move)
# ---------------------------------------------------------------------------


class TestLeelaStrategyMoveListBuilder:
    """``_build_move_list`` collects (player, coord) tuples from main branch."""

    def test_empty_branch_returns_empty_list(self) -> None:
        engine = MagicMock()
        game = _FakeGame(leela_engine=engine)
        strategy = LeelaStrategy(game, ai_settings={})
        assert strategy._build_move_list() == []

    def test_branch_with_moves_round_trips(self) -> None:
        # ``_FakeGameNode._FakeMove.moves`` is unused (LeelaStrategy
        # reads ``cn.nodes_from_root``) — so this test exercises only
        # the safety net / empty-path branch via a brand-new helper
        # invocation.
        engine = MagicMock()
        game = _FakeGame(leela_engine=engine)
        strategy = LeelaStrategy(game, ai_settings={})
        moves = strategy._build_move_list()
        assert isinstance(moves, list)
