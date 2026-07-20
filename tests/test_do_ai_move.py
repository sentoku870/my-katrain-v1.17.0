"""Tests for ``game_commands.do_ai_move`` (Phase 170, updated Phase 280).

Background
----------
After Phase 170 the dispatcher uses ``STRATEGY_REGISTRY`` as the single
source of truth: any ``Player.strategy`` value that *is* registered
(``ai:default``, ``ai:handicap`` after Phase 280 slim-down) is forwarded
to ``generate_ai_move``. Strategies that are NOT in the registry
(notably ``"game:normal"`` and the bare KataGo engine strategy id)
are skipped because ``KataGoEngine.poll`` already produces a move in its
own loop.

The tests below stub ``ctx`` enough to verify each branch:

  * Registered strategy (``ai:default``) -> ``generate_ai_move`` is
    called with the strategy id and the settings dict.
  * ``mode == "game:normal"`` -> ``generate_ai_move`` is *not* called
    and no "AI Mode ... not found" log appears.
  * Other KataGo-internal strategy ids (e.g. ``ai:rank``,
    ``ai:scoreloss`` after Phase 280) -> also skipped.
  * Settings missing -> ``{}`` is passed; the dispatcher survives
    the ``or {}`` fallback.
  * Exception -> ``ctx.log`` + ``ctx.controls.set_status`` are
    populated.
  * ``node`` argument that does not match the current node -> abort
    before any dispatch.

We deliberately use ``unittest.mock.MagicMock`` for ``ctx`` so the
test does not need to import the full ``KaTrainGui`` Kivy root
(which would require a running Kivy app).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def ctx_fixture(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return a stub ``ctx`` with a real ``config`` method.

    We do not import ``KaTrainGui`` because it pulls in Kivy's event
    loop; the dispatcher under test only touches ``ctx.config``,
    ``ctx.game``, ``ctx.next_player_info``, ``ctx.controls`` and
    ``ctx.log``.
    """

    class _StubCtx:
        def __init__(self) -> None:
            self.game = MagicMock()
            # current_node identity is checked against the passed-in node
            self.game.current_node = object()

            self.controls = MagicMock()

            self._config: dict[str, dict[str, Any]] = {
                "ai": {
                    "ai:default": {},
                }
            }
            self._next_player_strategy = "ai:default"

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

    return _StubCtx()


def test_do_ai_move_routes_registered_strategy_to_generate_ai_move(
    ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A strategy present in ``STRATEGY_REGISTRY`` is forwarded to ``generate_ai_move``."""
    from katrain.core.ai_strategies_base import STRATEGY_REGISTRY
    from katrain.gui.features.commands import game_commands

    # Sanity: ai:default is registered, otherwise the test is meaningless.
    assert "ai:default" in STRATEGY_REGISTRY

    called_with: dict[str, Any] = {}

    def _fake_generate(game: Any, ai_mode: str, ai_settings: dict[str, Any]) -> tuple[Any, Any]:
        called_with["game"] = game
        called_with["ai_mode"] = ai_mode
        called_with["ai_settings"] = ai_settings
        return (MagicMock(), MagicMock())

    monkeypatch.setattr("katrain.core.ai.generate_ai_move", _fake_generate)

    game_commands.do_ai_move(ctx_fixture, node=None)

    assert called_with == {
        "game": ctx_fixture.game,
        "ai_mode": "ai:default",
        "ai_settings": {},
    }


def test_do_ai_move_skips_game_normal_mode(ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """KataGo ``game:normal`` is handled by the engine; the dispatcher must noop."""
    from katrain.core.ai_strategies_base import STRATEGY_REGISTRY
    from katrain.gui.features.commands import game_commands

    assert "game:normal" not in STRATEGY_REGISTRY
    ctx_fixture.next_player_info_setter("game:normal")

    called: dict[str, Any] = {}

    def _should_not_call(*_args: Any, **_kwargs: Any) -> None:
        called["yes"] = True

    monkeypatch.setattr("katrain.core.ai.generate_ai_move", _should_not_call)

    game_commands.do_ai_move(ctx_fixture, node=None)

    assert "yes" not in called
    # ``ctx_fixture.log`` should not have surfaced "AI Mode ..." (no
    # else-branch was taken). The ``last_log`` attribute is only set
    # when ``log`` was actually called.
    assert not hasattr(ctx_fixture, "last_log")


def test_do_ai_move_skips_unknown_modes(ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Strategies not in ``STRATEGY_REGISTRY`` are also skipped.

    This protects against future KataGo-internal ids (e.g. ``ai:rank``
    or ``ai:scoreloss`` after the Phase 280 slim-down) accidentally
    entering the dispatcher branch.
    """
    from katrain.core.ai_strategies_base import STRATEGY_REGISTRY
    from katrain.gui.features.commands import game_commands

    called: dict[str, Any] = {}

    def _should_not_call(*_args: Any, **_kwargs: Any) -> None:
        called["yes"] = True

    monkeypatch.setattr("katrain.core.ai.generate_ai_move", _should_not_call)

    for strategy_id in ("game:normal", "game:teach", "ai:leela", "ai:unknown"):
        if strategy_id == "ai:leela":
            assert strategy_id not in STRATEGY_REGISTRY, (
                "Phase 170 removed ai:leela from the registry; if you "
                "re-added it, update the test and explain why Leela "
                "play is back."
            )
        ctx_fixture.next_player_info_setter(strategy_id)
        game_commands.do_ai_move(ctx_fixture, node=None)
        assert "yes" not in called, f"generate_ai_move was unexpectedly called for {strategy_id}"


def test_do_ai_move_surfaces_settings_when_present(ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """When ``ai:default`` settings are stored, the dispatcher forwards them."""
    from katrain.gui.features.commands import game_commands

    # ai:default uses an empty settings dict, but the dispatcher should
    # still forward it.
    captured: dict[str, Any] = {}

    def _capture(game: Any, ai_mode: str, ai_settings: dict[str, Any]) -> tuple[Any, Any]:
        captured["settings"] = ai_settings
        return (MagicMock(), MagicMock())

    monkeypatch.setattr("katrain.core.ai.generate_ai_move", _capture)

    game_commands.do_ai_move(ctx_fixture, node=None)

    assert captured["settings"] == {}


def test_do_ai_move_falls_back_to_empty_settings(ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing settings branch falls back to ``{}``; no 'AI Mode ... not found!' log.

    The previous implementation emitted a misleading 'AI Mode ... not
    found!' even when the strategy existed in the registry; the new
    dispatcher uses ``STRATEGY_REGISTRY`` as the source of truth and
    only logs when the strategy is actually missing.
    """
    from katrain.gui.features.commands import game_commands

    # Strip the config so the dispatcher hits its ``or {}`` fallback.
    ctx_fixture._config["ai"].pop("ai:default", None)

    captured: dict[str, Any] = {}

    def _capture(game: Any, ai_mode: str, ai_settings: dict[str, Any]) -> tuple[Any, Any]:
        captured["settings"] = ai_settings
        return (MagicMock(), MagicMock())

    monkeypatch.setattr("katrain.core.ai.generate_ai_move", _capture)

    game_commands.do_ai_move(ctx_fixture, node=None)

    assert captured["settings"] == {}
    assert not hasattr(ctx_fixture, "last_log")


def test_do_ai_move_propagates_strategy_exceptions(ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exceptions from ``generate_ai_move`` propagate to ``ctx.log`` + status."""

    from katrain.gui.features.commands import game_commands

    def _explode(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("strategy fixture down")

    monkeypatch.setattr("katrain.core.ai.generate_ai_move", _explode)

    game_commands.do_ai_move(ctx_fixture, node=None)

    # ``_StubCtx.log`` set ``last_log`` when invoked.
    assert getattr(ctx_fixture, "last_log", ("", None))[0] == "strategy fixture down"
    ctx_fixture.controls.set_status.assert_called_once_with("strategy fixture down")


def test_do_ai_move_respects_node_pin(ctx_fixture: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """When the caller's ``node`` does not match the current node, the dispatcher aborts."""
    from katrain.gui.features.commands import game_commands

    called: dict[str, Any] = {}

    def _should_not_call(*_args: Any, **_kwargs: Any) -> None:
        called["yes"] = True

    monkeypatch.setattr("katrain.core.ai.generate_ai_move", _should_not_call)

    other_node = object()
    assert other_node is not ctx_fixture.game.current_node

    game_commands.do_ai_move(ctx_fixture, node=other_node)
    assert "yes" not in called
