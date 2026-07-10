"""Tests for EngineBootstrap (Phase 173 P0-①-D).

Phase 173 P0-①-D extracted engine-initialization glue out of
``KaTrainGui.start()`` into a small ``EngineBootstrap`` class. These tests
verify the bootstrap's wiring — error translation, main-thread scheduler
injection, and the initial ``analysis_focus = None`` reset — without
booting Kivy or touching the real KataGo binary.

The KataGoEngine itself is imported lazily inside ``EngineBootstrap.create``
so we patch that import to verify the call surface.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from katrain.gui.managers.engine_bootstrap import EngineBootstrap


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.config = MagicMock(return_value={"key": "value"})
    ctx.error_handler.handle = MagicMock()
    return ctx


class TestEngineBootstrap:
    def _make_bootstrap(
        self,
        config: dict | None = None,
    ) -> tuple[EngineBootstrap, dict]:
        ctx = _make_ctx()
        if config is not None:
            ctx.config.return_value = config
        status_calls: list[tuple[str, str]] = []
        scheduler_calls: list = []

        def status_callback(event_type: str, message: str) -> None:
            status_calls.append((event_type, message))

        def main_thread_scheduler(fn):
            scheduler_calls.append(fn)

        bs = EngineBootstrap(
            ctx=ctx,
            config_getter=ctx.config,
            status_callback=status_callback,
            error_handler=ctx.error_handler,
            main_thread_scheduler=main_thread_scheduler,
        )
        return bs, {
            "ctx": ctx,
            "status_calls": status_calls,
            "scheduler_calls": scheduler_calls,
        }

    def test_create_passes_engine_config(self):
        bs, ctx = self._make_bootstrap(config={"k": "v"})
        # KataGoEngine is imported lazily inside create().
        with patch("katrain.core.engine.KataGoEngine") as MockEngine:
            MockEngine.return_value = MagicMock(name="engine")
            bs.create()
        MockEngine.assert_called_once()
        # Second positional = engine config dict.
        args, kwargs = MockEngine.call_args
        assert args[1] == {"k": "v"}

    def test_create_wires_callbacks(self):
        bs, ctx = self._make_bootstrap()
        with patch("katrain.core.engine.KataGoEngine") as MockEngine:
            MockEngine.return_value = MagicMock(name="engine")
            bs.create()
        # Status / error / scheduler all flowed into KataGoEngine.
        kwargs = MockEngine.call_args.kwargs
        assert callable(kwargs["status_callback"])
        assert callable(kwargs["error_callback"])
        assert callable(kwargs["main_thread_scheduler"])

    def test_error_callback_invokes_error_handler(self):
        bs, ctx = self._make_bootstrap()
        with patch("katrain.core.engine.KataGoEngine") as MockEngine:
            MockEngine.return_value = MagicMock(name="engine")
            bs.create()
        kwargs = MockEngine.call_args.kwargs
        error_callback = kwargs["error_callback"]

        with patch("katrain.core.errors.EngineError") as MockErr:
            MockErr.return_value = MagicMock(name="err-instance")
            error_callback("boom happened", code=42, allow_popup=False)

        ctx["ctx"].error_handler.handle.assert_called_once()
        # First positional argument: the EngineError instance.
        assert ctx["ctx"].error_handler.handle.call_args.args[0] is MockErr.return_value
        # notify_user kwarg reflects allow_popup=False.
        assert ctx["ctx"].error_handler.handle.call_args.kwargs["notify_user"] is False

    def test_error_callback_propagates_code_in_context(self):
        bs, ctx = self._make_bootstrap()
        with patch("katrain.core.engine.KataGoEngine") as MockEngine:
            MockEngine.return_value = MagicMock(name="engine")
            bs.create()
        kwargs = MockEngine.call_args.kwargs
        error_callback = kwargs["error_callback"]

        with patch("katrain.core.errors.EngineError") as MockErr:
            MockErr.return_value = MagicMock(name="err-instance")
            error_callback("msg", code="XYZ")

        sent_err = MockErr.call_args
        # The constructed EngineError carries rich context.
        context = sent_err.kwargs["context"]
        assert context["original_error"] == repr("msg")
        assert context["error_code"] == "XYZ"


class TestResetInitialFocus:
    def test_calls_engine_set_analysis_focus_none(self):
        engine = MagicMock()
        EngineBootstrap.reset_initial_focus(engine)
        engine.set_analysis_focus.assert_called_once_with(None)

    def test_none_engine_is_safe(self):
        # No engine → no-op (with no exception).
        assert EngineBootstrap.reset_initial_focus(None) is None

    def test_missing_method_is_safe(self):
        # A "duck-typed" engine without set_analysis_focus should not raise.
        engine = MagicMock(spec=[])  # no methods
        assert EngineBootstrap.reset_initial_focus(engine) is None

    def test_exception_in_set_analysis_focus_is_swallowed(self):
        engine = MagicMock()
        engine.set_analysis_focus.side_effect = RuntimeError("oops")
        # Contextlib.suppress ensures this does not raise.
        EngineBootstrap.reset_initial_focus(engine)
        engine.set_analysis_focus.assert_called_once_with(None)
