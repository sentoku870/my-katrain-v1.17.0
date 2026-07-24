"""Tests for AutoSetupController (Phase PR4 coverage).

The controller handles engine fallback (CPU / custom), engine restart, and
result persistence. All external collaborators are injected via
``AutoSetupContext`` (Protocol), so the tests use MagicMock contexts and
factories to exercise each branch.

This file targets >60% coverage on
``katrain.gui.managers.auto_setup_controller``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from katrain.core.analysis_result import EngineTestResult, ErrorCategory
from katrain.gui.managers.auto_setup_controller import AutoSetupController

TestAnalysisResult = EngineTestResult


def _make_ctx(engine=None, config_side_effect=None):
    """Build a MagicMock that satisfies the AutoSetupContext Protocol.

    ``config_side_effect`` lets a test pre-load the dict returned by
    ``ctx.config('engine')``.
    """
    ctx = MagicMock(name="ctx")
    ctx.engine = engine
    if config_side_effect is not None:
        ctx.config.side_effect = config_side_effect
    return ctx


def _make_engine(*, alive=True):
    engine = MagicMock(name="engine")
    engine.check_alive.return_value = alive
    return engine


class TestRestartEngineWithFallback:
    def test_unknown_fallback_type_returns_failure(self):
        ctx = _make_ctx()
        controller = AutoSetupController(ctx)
        ok, result = controller.restart_engine_with_fallback("not_a_type", engine_factory=MagicMock())
        assert ok is False
        assert result.success is False
        assert result.error_category == ErrorCategory.UNKNOWN
        assert "Unknown fallback type" in result.error_message

    def test_cpu_katago_not_found(self):
        ctx = _make_ctx()
        controller = AutoSetupController(ctx)
        with patch("katrain.gui.managers.auto_setup_controller.find_cpu_katago", return_value=None):
            ok, result = controller.restart_engine_with_fallback("cpu", engine_factory=MagicMock())
        assert ok is False
        assert result.error_category == ErrorCategory.ENGINE_START_FAILED
        assert "CPU KataGo binary not found" in result.error_message

    def test_engine_factory_exception(self):
        ctx = _make_ctx(
            config_side_effect=lambda section, default=None: {"katago": "x"} if section == "engine" else default
        )
        controller = AutoSetupController(ctx)
        engine_factory = MagicMock(side_effect=RuntimeError("boom"))
        with patch("katrain.gui.managers.auto_setup_controller.find_cpu_katago", return_value="/cpu/path"):
            ok, result = controller.restart_engine_with_fallback("cpu", engine_factory=engine_factory)
        assert ok is False
        assert result.error_category == ErrorCategory.ENGINE_START_FAILED
        assert "Failed to start CPU engine" in result.error_message

    def test_existing_engine_is_shut_down_before_replacement(self):
        """``ctx.engine.shutdown`` runs before the new engine is constructed."""
        old_engine = MagicMock(name="old_engine")
        ctx = _make_ctx(
            engine=old_engine,
            config_side_effect=lambda section, default=None: {"katago": "x"} if section == "engine" else default,
        )
        new_engine = _make_engine(alive=True)
        engine_factory = MagicMock(return_value=new_engine)
        controller = AutoSetupController(ctx)

        with (
            patch("katrain.gui.managers.auto_setup_controller.find_cpu_katago", return_value="/cpu/path"),
            patch.object(
                controller,
                "verify_engine_works",
                return_value=EngineTestResult(success=True, error_category=None, error_message=None),
            ),
        ):
            ok, _ = controller.restart_engine_with_fallback("cpu", engine_factory=engine_factory)
        old_engine.shutdown.assert_called_once_with(finish=False)
        assert ctx.engine is new_engine
        assert ok is True

    def test_success_saves_katago_path(self):
        ctx = _make_ctx(
            config_side_effect=lambda section, default=None: {"katago": "x"} if section == "engine" else default
        )
        engine_factory = MagicMock(return_value=_make_engine(alive=True))
        controller = AutoSetupController(ctx)

        with (
            patch("katrain.gui.managers.auto_setup_controller.find_cpu_katago", return_value="/cpu/path"),
            patch.object(
                controller,
                "verify_engine_works",
                return_value=EngineTestResult(success=True, error_category=None, error_message=None),
            ),
        ):
            ok, _ = controller.restart_engine_with_fallback("cpu", engine_factory=engine_factory)
        ctx.update_engine_config.assert_called_once_with(katago="/cpu/path")
        assert ok is True


class TestRestartEngine:
    def test_returns_true_when_alive(self):
        engine = _make_engine(alive=True)
        ctx = _make_ctx(
            engine=engine,
            config_side_effect=lambda section, default=None: {"x": 1} if section == "engine" else default,
        )
        controller = AutoSetupController(ctx)
        engine_factory = MagicMock(return_value=engine)
        assert controller.restart_engine(engine_factory) is True

    def test_returns_false_when_engine_factory_raises(self):
        ctx = _make_ctx()
        controller = AutoSetupController(ctx)
        engine_factory = MagicMock(side_effect=RuntimeError("boom"))
        assert controller.restart_engine(engine_factory) is False

    def test_returns_false_when_check_alive_false(self):
        engine = _make_engine(alive=False)
        ctx = _make_ctx(
            engine=engine,
            config_side_effect=lambda section, default=None: {} if section == "engine" else default,
        )
        controller = AutoSetupController(ctx)
        engine_factory = MagicMock(return_value=engine)
        assert controller.restart_engine(engine_factory) is False

    def test_shuts_down_existing_engine(self):
        old_engine = MagicMock(name="old_engine")
        new_engine = _make_engine(alive=True)
        ctx = _make_ctx(
            engine=old_engine,
            config_side_effect=lambda section, default=None: {} if section == "engine" else default,
        )
        controller = AutoSetupController(ctx)
        engine_factory = MagicMock(return_value=new_engine)
        controller.restart_engine(engine_factory)
        old_engine.shutdown.assert_called_once_with(finish=False)


class TestSaveAutoSetupResult:
    def test_writes_first_run_completed_and_last_result(self):
        ctx = _make_ctx(
            config_side_effect=lambda section, default=None: (
                {"existing": "value"} if section == "auto_setup" else default
            )
        )
        controller = AutoSetupController(ctx)
        controller.save_auto_setup_result(success=True)
        ctx.set_config_section.assert_called_once()
        args = ctx.set_config_section.call_args[0]
        assert args[0] == "auto_setup"
        assert args[1]["first_run_completed"] is True
        assert args[1]["last_test_result"] == "success"
        ctx.save_config.assert_called_once_with("auto_setup")

    def test_failed_result_writes_failed_string(self):
        ctx = _make_ctx(config_side_effect=lambda section, default=None: {} if section == "auto_setup" else default)
        controller = AutoSetupController(ctx)
        controller.save_auto_setup_result(success=False)
        args = ctx.set_config_section.call_args[0]
        assert args[1]["last_test_result"] == "failed"

    def test_no_set_config_section_method(self):
        """When the context has no ``set_config_section`` method, the
        call is silently skipped (graceful degradation)."""
        ctx = MagicMock(name="ctx")
        ctx.config.return_value = {}
        # Explicitly remove the attribute so hasattr() returns False.
        del ctx.set_config_section
        controller = AutoSetupController(ctx)
        controller.save_auto_setup_result(success=True)
        ctx.save_config.assert_not_called()


class TestVerifyEngineWorks:
    def test_engine_none_returns_failure(self):
        ctx = _make_ctx(engine=None)
        controller = AutoSetupController(ctx)
        result = controller.verify_engine_works()
        assert result.success is False
        assert result.error_category == ErrorCategory.ENGINE_START_FAILED
        assert "Engine is None" in result.error_message

    def test_engine_not_alive_classifies_error_from_stderr(self):
        engine = MagicMock(name="engine")
        engine.check_alive.return_value = False
        engine.stderr_queue = MagicMock()
        engine.stderr_queue.empty.return_value = False
        engine.stderr_queue.get_nowait.side_effect = ["OOM error", IndexError]
        ctx = _make_ctx(engine=engine)
        controller = AutoSetupController(ctx)
        result = controller.verify_engine_works()
        assert result.success is False
        assert result.error_category is not None

    def test_engine_not_alive_no_stderr_returns_engine_start_failed(self):
        engine = MagicMock(name="engine")
        engine.check_alive.return_value = False
        ctx = _make_ctx(engine=engine)
        controller = AutoSetupController(ctx)
        result = controller.verify_engine_works()
        assert result.success is False
        assert result.error_category == ErrorCategory.ENGINE_START_FAILED

    def test_engine_request_analysis_raises(self):
        engine = MagicMock(name="engine")
        engine.check_alive.return_value = True
        engine.request_analysis.side_effect = RuntimeError("send failed")
        ctx = _make_ctx(engine=engine)
        controller = AutoSetupController(ctx)
        result = controller.verify_engine_works()
        assert result.success is False
        assert "Failed to request analysis" in result.error_message

    def test_timeout_returns_timeout_error(self):
        engine = MagicMock(name="engine")
        engine.check_alive.return_value = True
        engine.create_minimal_analysis_query.return_value = {"k": "v"}

        # Callback that never fires → verify_engine_works times out.
        def _no_callback(analysis_node=None, callback=None, override_queries=None):
            pass

        engine.request_analysis.side_effect = _no_callback
        ctx = _make_ctx(engine=engine)
        controller = AutoSetupController(ctx)
        result = controller.verify_engine_works(timeout_seconds=0.05)
        assert result.success is False
        assert result.error_category == ErrorCategory.TIMEOUT

    def test_analysis_returns_error_key(self):
        engine = MagicMock(name="engine")
        engine.check_alive.return_value = True
        engine.create_minimal_analysis_query.return_value = {}

        def _fire_callback(analysis_node=None, callback=None, override_queries=None):
            callback({"error": "bad query"})

        engine.request_analysis.side_effect = _fire_callback
        ctx = _make_ctx(engine=engine)
        controller = AutoSetupController(ctx)
        result = controller.verify_engine_works()
        assert result.success is False
        assert "bad query" in result.error_message

    def test_success_path(self):
        engine = MagicMock(name="engine")
        engine.check_alive.return_value = True
        engine.create_minimal_analysis_query.return_value = {}

        def _fire_callback(analysis_node=None, callback=None, override_queries=None):
            callback({"winrate": 0.5, "scoreLead": 0.0})

        engine.request_analysis.side_effect = _fire_callback
        ctx = _make_ctx(engine=engine)
        controller = AutoSetupController(ctx)
        result = controller.verify_engine_works()
        assert result.success is True


class TestSaveEngineKatagoPath:
    def test_forwards_to_ctx(self):
        ctx = _make_ctx()
        controller = AutoSetupController(ctx)
        controller.save_engine_katago_path("/path/to/katago")
        ctx.update_engine_config.assert_called_once_with(katago="/path/to/katago")
