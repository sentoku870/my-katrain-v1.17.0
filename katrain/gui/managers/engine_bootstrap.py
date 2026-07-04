"""Engine bootstrap coordinator (Phase 173 P0-①-D).

Phase 158+ extracted numerous managers/controllers from KaTrainGui, but the
``start()`` method still inlined 40+ lines of engine-initialization glue:

  - error_handler wiring
  - main-thread scheduler lambda
  - KataGoEngine construction
  - set_analysis_focus(None) initial state
  - message_loop_manager.start()

This module extracts that glue into ``EngineBootstrap``. The class is
intentionally tiny: it takes lambdas for the cross-cutting dependencies
(error_handler, status callback, main_thread_scheduler) and exposes a
single ``create()`` method that builds the KataGoEngine and assigns it
to a target ``engine`` attribute.

Usage::

    bootstrap = EngineBootstrap(
        ctx=gui,
        config_getter=gui.config,
        status_callback=gui._on_engine_status,
        error_handler=gui.error_handler,
        main_thread_scheduler=lambda fn: Clock.schedule_once(lambda _dt: fn(), 0),
    )
    gui.engine = bootstrap.create()
    bootstrap.reset_initial_focus(gui.engine)

After Phase 173 the KaTrainGui.start() method becomes a thin orchestrator
and the engine-construction surface is testable without booting Kivy.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any, Protocol


class _BootstrapContext(Protocol):
    """Minimal surface EngineBootstrap needs from the KaTrainGui-like ctx.

    Holding a Protocol rather than the full KaTrainGui keeps the surface
    area narrow and lets tests pass a simple MagicMock.
    """

    error_handler: Any

    def config(self, key: str, default: Any = ...) -> Any: ...


class EngineBootstrap:
    """Construct the KataGoEngine with the wiring the orchestrator expects.

    Centralises:
      - the engine error_handler closure (rich-context translation)
      - the main_thread_scheduler wrapper (Kivy Clock.schedule_once)
      - the initial ``analysis_focus = None`` reset (matches upstream's
        default startup state).
    """

    def __init__(
        self,
        ctx: _BootstrapContext,
        config_getter: Callable[[str], Any],
        status_callback: Callable[[str, str], None],
        error_handler: Any,
        main_thread_scheduler: Callable[[Callable[[], None]], None],
    ) -> None:
        self._ctx = ctx
        self._config_getter = config_getter
        self._status_callback = status_callback
        self._error_handler = error_handler
        self._main_thread_scheduler = main_thread_scheduler

    def _handle_engine_error(self, message: Any, code: Any = None, allow_popup: bool = True) -> None:
        """Translate engine errors into structured EngineError + status display."""
        # Local import to avoid top-level circular reference between
        # katrain.core.errors and the gui layer.
        from katrain.core.errors import EngineError

        context = {
            "original_error": repr(message),
            "error_code": code,
        }
        self._error_handler.handle(
            EngineError(
                str(message),
                user_message="Engine error occurred",
                context=context,
            ),
            notify_user=allow_popup,
        )

    def create(self) -> Any:
        """Instantiate KataGoEngine with the project-standard wiring.

        Returns the engine instance. Caller is responsible for assigning it
        to ``ctx.engine`` (so the orchestrator can keep its own field).
        """
        from katrain.core.engine import KataGoEngine

        return KataGoEngine(
            self._ctx,
            self._config_getter("engine"),
            status_callback=self._status_callback,
            error_callback=self._handle_engine_error,
            main_thread_scheduler=self._main_thread_scheduler,
        )

    @staticmethod
    def reset_initial_focus(engine: Any) -> None:
        """Reset engine's analysis_focus to ``None`` on startup.

        Mirrors the upstream KaTrain behaviour where a fresh boot starts
        with "no priority" regardless of the persisted value.
        """
        if engine is None or not hasattr(engine, "set_analysis_focus"):
            return
        with contextlib.suppress(Exception):
            engine.set_analysis_focus(None)
