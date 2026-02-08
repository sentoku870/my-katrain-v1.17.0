"""オートセットアップ制御マネージャー（Phase 133）

エンジン欠損時のCPUフォールバックや、初回起動時の検証ロジックを担当。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, Protocol

from katrain.core.analysis_result import EngineTestResult as TestAnalysisResult
from katrain.core.analysis_result import ErrorCategory, classify_engine_error
from katrain.core.auto_setup import find_cpu_katago


class EngineProtocol(Protocol):
    """AutoSetupControllerが使用するEngineの最小インターフェース"""

    def shutdown(self, finish: bool = False) -> None: ...
    def check_alive(self) -> bool: ...
    def create_minimal_analysis_query(self) -> dict[str, Any]: ...
    def request_analysis(
        self, analysis_node: Any, callback: Callable[[dict[str, Any]], None], override_queries: list[dict[str, Any]]
    ) -> None: ...


class AutoSetupContext(Protocol):
    """AutoSetupControllerが動作するために必要な外部インターフェース"""

    engine: EngineProtocol | None
    engine_unhealthy: bool

    def config(self, section: str, default: Any = None) -> Any: ...
    def save_config(self, section: str) -> None: ...
    def update_engine_config(self, **kwargs: Any) -> None: ...
    def log(self, message: str, level: int) -> None: ...


class AutoSetupController:
    """エンジンの自動セットアップと検証の制御。

    責務:
    - CPUフォールバックの実行
    - エンジンの生存確認と検証解析
    - 検証結果の保存
    """

    def __init__(self, ctx: AutoSetupContext) -> None:
        self._ctx = ctx

    def restart_engine_with_fallback(self, fallback_type: str, engine_factory: Callable[[dict[str, Any]], EngineProtocol]) -> tuple[bool, TestAnalysisResult]:
        """エンジンをフォールバック設定で再起動し検証する。"""
        if fallback_type != "cpu":
            return False, TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.UNKNOWN,
                error_message=f"Unknown fallback type: {fallback_type}",
            )

        cpu_katago = find_cpu_katago()
        if cpu_katago is None:
            return False, TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.ENGINE_START_FAILED,
                error_message="CPU KataGo binary not found",
            )

        if self._ctx.engine:
            self._ctx.engine.shutdown(finish=False)
            self._ctx.engine = None

        try:
            engine_config = dict(self._ctx.config("engine"))
            engine_config["katago"] = cpu_katago
            self._ctx.engine = engine_factory(engine_config)
        except Exception as e:
            return False, TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.ENGINE_START_FAILED,
                error_message=f"Failed to start CPU engine: {e}",
            )

        result = self.verify_engine_works()
        if result.success:
            self.save_engine_katago_path(cpu_katago)
            self._ctx.engine_unhealthy = False

        return result.success, result

    def restart_engine(self, engine_factory: Callable[[dict[str, Any]], EngineProtocol]) -> bool:
        """現在の設定でエンジンを再起動する。"""
        if self._ctx.engine:
            self._ctx.engine.shutdown(finish=False)
            self._ctx.engine = None

        try:
            engine_config = self._ctx.config("engine")
            self._ctx.engine = engine_factory(engine_config)
            self._ctx.engine_unhealthy = False
            return self._ctx.engine.check_alive()
        except Exception:
            return False

    def save_auto_setup_result(self, success: bool) -> None:
        """オートセットアップの結果を保存する。"""
        # Note: KaTrainGui.save_auto_setup_result uses self._config directly,
        # here we assume the context can handle the logic or provide access.
        # For simplicity, we re-implement it using available context methods.
        auto_setup = dict(self._ctx.config("auto_setup") or {})
        auto_setup["first_run_completed"] = True
        auto_setup["last_test_result"] = "success" if success else "failed"
        # We need a way to set config. If KaTrainGui doesn't have it, we might need to add it to Protocol
        # But KaTrainBase has set_config_section.
        if hasattr(self._ctx, "set_config_section"):
            self._ctx.set_config_section("auto_setup", auto_setup) # type: ignore[attr-defined]
            self._ctx.save_config("auto_setup")

    def verify_engine_works(self, timeout_seconds: float = 10.0) -> TestAnalysisResult:
        """エンジンが実際に解析可能か最小限のクエリで検証する。"""
        engine = self._ctx.engine
        if not engine:
            return TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.ENGINE_START_FAILED,
                error_message="Engine is None",
            )

        if not engine.check_alive():
            error_text = ""
            if hasattr(engine, "stderr_queue"):
                q = getattr(engine, "stderr_queue")
                while not q.empty():
                    try:
                        error_text += q.get_nowait() + "\n"
                    except Exception:
                        break

            error_category = classify_engine_error(error_text) if error_text else ErrorCategory.ENGINE_START_FAILED
            return TestAnalysisResult(
                success=False,
                error_category=error_category,
                error_message=error_text[:200] if error_text else "Engine not alive",
            )

        query = engine.create_minimal_analysis_query()
        result_event = threading.Event()
        analysis_result: dict[str, Any] = {}

        def on_result(analysis: dict[str, Any]) -> None:
            analysis_result.update(analysis)
            result_event.set()

        try:
            engine.request_analysis(
                analysis_node=None,
                callback=on_result,
                override_queries=[query],
            )
        except Exception as e:
            return TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.ENGINE_START_FAILED,
                error_message=f"Failed to request analysis: {e}",
            )

        is_timeout = not result_event.wait(timeout=timeout_seconds)
        if is_timeout:
            return TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.TIMEOUT,
                error_message=f"Analysis did not respond within {timeout_seconds}s",
            )

        if "error" in analysis_result:
            error_text = str(analysis_result.get("error", ""))
            return TestAnalysisResult(
                success=False,
                error_category=classify_engine_error(error_text),
                error_message=error_text[:200],
            )

        return TestAnalysisResult(
            success=True,
            error_category=None,
            error_message=None,
        )

    def save_engine_katago_path(self, katago_path: str) -> None:
        """エンジンの実行パスを保存する。"""
        self._ctx.update_engine_config(katago=katago_path)
