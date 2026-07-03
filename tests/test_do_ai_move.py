"""Tests for ``game_commands.do_ai_move`` (Phase 159 fix).

Background
----------
Before Phase 159 the dispatcher used ``ctx.config(f"ai/{mode}")`` directly,
which only worked when ``mode`` happened to be a top-level ``ai:<key>`` entry
in ``config.json``. KataGo paths never hit the dispatcher because the engine
itself produces the move via the analysis poll, so the bug stayed hidden.

Phase 159 routes the dispatcher through STRATEGY_REGISTRY for the Leela
strategy only (``AI_LEELA = "ai:leela"``). KataGo paths now skip the
dispatcher entirely and rely on the engine.

The tests below stub ``ctx`` enough to verify each branch:

  * ``mode == "ai:leela"`` -> ``generate_ai_move`` is called with the
    strategy id (and any settings). ``STRATEGY_REGISTRY`` is not consulted
    by the dispatcher except for the ``KeyError``-equivalent lookup we
    pre-validate before dispatch.
  * ``mode == "game:normal"`` (KataGo default) -> ``generate_ai_move`` is
    *not* called. No ``"AI Mode ... not found"`` log appears.
  * Strategy present in registry but settings missing -> ``{}`` is
    passed; the dispatcher survives the ``or {}`` fallback.

We deliberately use ``unittest.mock.MagicMock`` for ``ctx`` so the test
does not need to import the full ``KaTrainGui`` Kivy root (which would
require a running Kivy app).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from katrain.core.constants import AI_LEELA


@pytest.fixture
def ctx_fixture(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return a MagicMock ctx with a real ``config`` method.

    We do not import ``KaTrainGui`` because it pulls in Kivy's event loop;
    the dispatcher under test only touches ``ctx.config``, ``ctx.game``,
    ``ctx.next_player_info``, ``ctx.controls`` and ``ctx.log``.
    """

    class _StubCtx:
        def __init__(self) -> None:
            self.game = MagicMock()
            # current_node identity is checked against the passed-in node
            self.game.current_node = object()

            self.controls = MagicMock()

            self._config: dict[str, dict[str, Any]] = {
                "ai": {
                    "ai:leela": {},
                }
            }

        def config(self, setting: str, default: Any = None) -> Any:
            if "/" in setting:
                cat, key = setting.split("/", 1)
                return self._config.get(cat, {}).get(key, default)
            return self._config.get(setting, default)

        def log(self, message: str, level: Any = None) -> None:
            # Tests assert on this via the mock attribute below.
            self.last_log = (message, level)

        def next_player_info_setter(self, strategy: str) -> None:
            self._next_player_strategy = strategy

        @property
        def next_player_info(self) -> Any:
            return MagicMock(strategy=self._next_player_strategy)

    ctx = _StubCtx()
    # Default to Leela strategy so the test starts in the interesting
    # branch. Individual tests override ``next_player_info_setter``.
    ctx.next_player_info_setter(AI_LEELA)
    return ctx


def test_do_ai_move_routes_leela_to_generate_ai_move(
    ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leela strategy should be the only strategy that lands at ``generate_ai_move``."""
    from katrain.gui.features.commands import game_commands

    called_with: dict[str, Any] = {}

    def _fake_generate(game: Any, ai_mode: str, ai_settings: dict[str, Any]) -> tuple[Any, Any]:
        called_with["game"] = game
        called_with["ai_mode"] = ai_mode
        called_with["ai_settings"] = ai_settings
        return (MagicMock(), MagicMock())

    monkeypatch.setattr(
        "katrain.core.ai.generate_ai_move",
        _fake_generate,
    )

    game_commands.do_ai_move(ctx_fixture, node=None)

    assert called_with == {
        "game": ctx_fixture.game,
        "ai_mode": AI_LEELA,
        "ai_settings": {},
    }


def test_do_ai_move_skips_katago_normal_mode(
    ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KataGo ``game:normal`` is handled by the engine; the dispatcher must noop."""
    from katrain.gui.features.commands import game_commands

    ctx_fixture.next_player_info_setter("game:normal")

    called: dict[str, Any] = {}

    def _should_not_call(*_args: Any, **_kwargs: Any) -> None:
        called["yes"] = True

    monkeypatch.setattr(
        "katrain.core.ai.generate_ai_move",
        _should_not_call,
    )

    game_commands.do_ai_move(ctx_fixture, node=None)

    assert "yes" not in called
    # ``ctx_fixture.log`` should not have surfaced "AI Mode ..." (no
    # else-branch was taken). The ``last_log`` attribute is only set
    # when ``log`` was actually called.
    assert not hasattr(ctx_fixture, "last_log")


def test_do_ai_move_skips_other_ai_modes(
    ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Other KataGo strategies (rank / handicap / etc.) also skip the dispatcher.

    The registered KataGo strategies historically carried ``ai:`` keys
    in config.json (e.g. ``ai:rank``, ``ai:handicap``). The dispatcher
    never observed them because KataGo engine.poll already produced a
    move; verifying the skip in code protects against future KataGo
    strategies accidentally entering this branch.
    """
    from katrain.gui.features.commands import game_commands

    called: dict[str, Any] = {}

    def _should_not_call(*_args: Any, **_kwargs: Any) -> None:
        called["yes"] = True

    monkeypatch.setattr(
        "katrain.core.ai.generate_ai_move",
        _should_not_call,
    )

    for strategy_id in ("ai:rank", "ai:default", "ai:handicap", "ai:pro"):
        ctx_fixture.next_player_info_setter(strategy_id)
        game_commands.do_ai_move(ctx_fixture, node=None)
        assert "yes" not in called, (
            f"generate_ai_move was unexpectedly called for {strategy_id}"
        )


def test_do_ai_move_surfaces_settings_when_present(
    ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``ai:leela`` settings are stored, the dispatcher forwards them.

    ``ctx.config("ai/ai:leela")`` returns the registered dict, and the
    dispatcher passes that dict (not a falsy value) to ``generate_ai_move``.
    """
    from katrain.gui.features.commands import game_commands

    ctx_fixture._config["ai"]["ai:leela"] = {"play_visits": 750}

    captured: dict[str, Any] = {}

    def _capture(game: Any, ai_mode: str, ai_settings: dict[str, Any]) -> tuple[Any, Any]:
        captured["settings"] = ai_settings
        return (MagicMock(), MagicMock())

    monkeypatch.setattr(
        "katrain.core.ai.generate_ai_move",
        _capture,
    )

    game_commands.do_ai_move(ctx_fixture, node=None)

    assert captured["settings"] == {"play_visits": 750}


def test_do_ai_move_does_not_log_when_key_missing_but_registry_present(
    ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing settings branch falls back to {}; no 'AI Mode ... not found!' log.

    The previous implementation emitted a misleading 'AI Mode ... not
    found!' even when the strategy existed in the registry; the new
    dispatcher uses ``STRATEGY_REGISTRY`` as the source of truth and
    never raises the 'not found' message for Leela.
    """
    from katrain.core.ai_strategies_base import STRATEGY_REGISTRY
    from katrain.gui.features.commands import game_commands

    # If a future cleanup removed AI_LEELA from the registry, the dispatcher
    # *should* log; here we double-check that AI_LEELA is registered before
    # running the no-op assertion (the dispatcher short-circuits only when
    # the strategy is registered).
    assert AI_LEELA in STRATEGY_REGISTRY

    # Strip the config so the dispatcher hits its ``or {}`` fallback.
    ctx_fixture._config["ai"].pop("ai:leela", None)

    captured: dict[str, Any] = {}

    def _capture(game: Any, ai_mode: str, ai_settings: dict[str, Any]) -> tuple[Any, Any]:
        captured["settings"] = ai_settings
        return (MagicMock(), MagicMock())

    monkeypatch.setattr(
        "katrain.core.ai.generate_ai_move",
        _capture,
    )

    game_commands.do_ai_move(ctx_fixture, node=None)

    assert captured["settings"] == {}
    assert not hasattr(ctx_fixture, "last_log")


def test_do_ai_move_propagates_strategy_exceptions(
    ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exceptions from ``generate_ai_move`` propagate to ctx.log + status."""

    from katrain.gui.features.commands import game_commands

    def _explode(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("leela fixture down")

    monkeypatch.setattr(
        "katrain.core.ai.generate_ai_move",
        _explode,
    )

    game_commands.do_ai_move(ctx_fixture, node=None)

    # ``_StubCtx.log`` set ``last_log`` when invoked.
    assert getattr(ctx_fixture, "last_log", ("", None))[0] == "leela fixture down"
    ctx_fixture.controls.set_status.assert_called_once_with("leela fixture down")


def test_do_ai_move_respects_node_pin(
    ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the caller's ``node`` does not match the current node, the dispatcher aborts."""
    from katrain.gui.features.commands import game_commands

    called: dict[str, Any] = {}

    def _should_not_call(*_args: Any, **_kwargs: Any) -> None:
        called["yes"] = True

    monkeypatch.setattr(
        "katrain.core.ai.generate_ai_move",
        _should_not_call,
    )

    other_node = object()
    assert other_node is not ctx_fixture.game.current_node

    game_commands.do_ai_move(ctx_fixture, node=other_node)
    assert "yes" not in called
