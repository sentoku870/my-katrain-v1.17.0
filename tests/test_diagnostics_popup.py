"""Unit tests for ``katrain.gui.features.diagnostics_popup`` (Phase 282-P1B).

The diagnostics popup module (422 LOC) had zero direct tests; only the
underlying ``core.diagnostics`` collectors were tested. This file
locks in the GUI layer's contract via source-static and lightweight
runtime checks.

The popup builders all require a real Kivy font pipeline which the
headless CI cannot provide. We therefore:

- Verify the public function surface via AST
- Verify the popup-bundle assembly contract
- Spot-check the ``_collect_diagnostics`` graceful-degradation paths
  (no engine, no config, no logs) using a real ``DiagnosticsBundle``

Coverage targets:
- All public + private functions exist with expected signatures
- ``_collect_diagnostics`` handles missing engine / config / logs
- i18n strings used in the popup are present in both .po files
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DIAG_POPUP_PATH = REPO_ROOT / "katrain" / "gui" / "features" / "diagnostics_popup.py"


# =============================================================================
# Source-static regression guards
# =============================================================================


def _get_module_tree() -> ast.Module:
    return ast.parse(DIAG_POPUP_PATH.read_text(encoding="utf-8"))


def _function_names(tree: ast.Module) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


class TestDiagnosticsPopupPublicApi:
    """Lock in the public function surface."""

    @pytest.mark.parametrize(
        "func_name",
        [
            "show_diagnostics_popup",
            "_show_diagnostics_popup_impl",
            "_collect_diagnostics",
            "_build_info_display",
            "_on_generate_zip",
            "_on_copy_info",
            "_on_generate_complete",
            "_show_success_popup",
            "_show_error_popup",
        ],
    )
    def test_functions_exist(self, func_name):
        tree = _get_module_tree()
        assert func_name in _function_names(tree), f"diagnostics_popup.py missing function {func_name!r}"

    def test_show_diagnostics_popup_signature(self):
        """Public entry point must accept exactly one FeatureContext."""
        import inspect

        from katrain.gui.features.diagnostics_popup import show_diagnostics_popup

        sig = inspect.signature(show_diagnostics_popup)
        params = list(sig.parameters)
        assert params == ["ctx"]

    def test_uses_clock_schedule_once(self):
        """Phase 230-D: deferred execution via Clock.schedule_once."""
        text = DIAG_POPUP_PATH.read_text(encoding="utf-8")
        assert "Clock.schedule_once" in text

    def test_uses_clipboard_copy(self):
        text = DIAG_POPUP_PATH.read_text(encoding="utf-8")
        assert "Clipboard.copy" in text

    def test_uses_create_diagnostics_zip(self):
        text = DIAG_POPUP_PATH.read_text(encoding="utf-8")
        assert "create_diagnostics_zip" in text

    def test_uses_generate_diagnostics_filename(self):
        text = DIAG_POPUP_PATH.read_text(encoding="utf-8")
        assert "generate_diagnostics_filename" in text

    def test_uses_format_llm_diagnostics_text(self):
        """Phase 2: clipboard copy uses LLM-friendly text format."""
        text = DIAG_POPUP_PATH.read_text(encoding="utf-8")
        assert "format_llm_diagnostics_text" in text


class TestDiagnosticsPopupI18nKeys:
    """Verify the i18n keys used by the popup exist in both .po files."""

    EXPECTED_KEYS = [
        "Diagnostics",
        "Generate Bug Report",
        "Copy Info",
        "Copied!",
        "Generating...",
        "Bug report saved to:\n%s",
        "Bug report generated: %s",
        "Bug Report Generated",
        "Open Folder",
        "Failed to generate bug report:\n%s",
        "Running",
        "Stopped",
        "Not configured",
        "System",
        "KataGo",
        "Application",
    ]

    @pytest.fixture
    def jp_keys(self) -> set[str]:
        import polib

        return {e.msgid for e in polib.pofile(str(REPO_ROOT / "katrain/i18n/locales/jp/LC_MESSAGES/katrain.po"))}

    @pytest.fixture
    def en_keys(self) -> set[str]:
        import polib

        return {e.msgid for e in polib.pofile(str(REPO_ROOT / "katrain/i18n/locales/en/LC_MESSAGES/katrain.po"))}

    @pytest.mark.parametrize("key", EXPECTED_KEYS)
    def test_key_in_jp(self, key, jp_keys):
        assert key in jp_keys, f"i18n key {key!r} missing from jp/LC_MESSAGES/katrain.po"

    @pytest.mark.parametrize("key", EXPECTED_KEYS)
    def test_key_in_en(self, key, en_keys):
        assert key in en_keys, f"i18n key {key!r} missing from en/LC_MESSAGES/katrain.po"


# =============================================================================
# _collect_diagnostics graceful-degradation (lightweight runtime)
# =============================================================================


class TestCollectDiagnosticsGracefulDegradation:
    """``_collect_diagnostics`` must not crash when ctx lacks expected
    attributes. These cover the defensive ``getattr``/``hasattr``
    branches added in Phase 230-D when the popup was reused from
    settings tab."""

    def test_minimal_ctx_no_engine(self):
        """ctx with no engine attribute -> katago_info should be empty."""
        from katrain.core.diagnostics import DiagnosticsBundle

        class MinimalCtx:
            """Bare-minimum FeatureContext for testing."""

            version = "test-1.0"
            config_file = "/tmp/test-config.json"
            _config: dict = {}

        ctx = MinimalCtx()
        bundle = _collect_diagnostics(ctx)
        assert isinstance(bundle, DiagnosticsBundle)
        assert bundle.katago_info.exe_path == ""
        assert bundle.katago_info.is_running is False

    def test_ctx_without_version_attr(self):
        class NoVersionCtx:
            _config: dict = {}

        ctx = NoVersionCtx()
        bundle = _collect_diagnostics(ctx)
        assert bundle.app_info.version == "unknown"

    def test_ctx_with_engine(self):
        """When engine is provided, katago_info is populated from it."""
        from types import SimpleNamespace

        class CtxWithEngine:
            version = "1.0"
            config_file = "/tmp/c.json"
            _config: dict = {}

            engine = SimpleNamespace(
                katago="/path/to/katago",
                model="/path/to/model",
                config={"config": "/path/to/engine-config"},
                katago_process=None,
            )

        ctx = CtxWithEngine()
        bundle = _collect_diagnostics(ctx)
        assert bundle.katago_info.exe_path == "/path/to/katago"
        assert bundle.katago_info.model_path == "/path/to/model"
        assert bundle.katago_info.config_path == "/path/to/engine-config"
        assert bundle.katago_info.is_running is False  # process is None

    def test_ctx_with_engine_running(self):
        from types import SimpleNamespace

        class CtxWithRunning:
            version = "1.0"
            config_file = ""
            _config: dict = {}

            engine = SimpleNamespace(
                katago="katago",
                model="model",
                config={},
                katago_process=SimpleNamespace(pid=1234),
            )

        ctx = CtxWithRunning()
        bundle = _collect_diagnostics(ctx)
        assert bundle.katago_info.is_running is True

    def test_ctx_engine_config_not_a_dict(self):
        """Phase 230-D: engine.config may not be a dict - should not crash."""
        from types import SimpleNamespace

        class CtxWithBadConfig:
            version = "1.0"
            config_file = ""
            _config: dict = {}

            engine = SimpleNamespace(
                katago="",
                model="",
                config="not a dict",  # malformed
                katago_process=None,
            )

        ctx = CtxWithBadConfig()
        bundle = _collect_diagnostics(ctx)
        assert bundle.katago_info.config_path == ""

    def test_ctx_without_get_recent_logs(self):
        """When ctx lacks get_recent_logs, logs field defaults to []."""
        from types import SimpleNamespace

        class CtxNoLogs:
            version = "1.0"
            config_file = ""
            _config: dict = {}
            engine = SimpleNamespace(katago="", model="", config={}, katago_process=None)

        ctx = CtxNoLogs()
        bundle = _collect_diagnostics(ctx)
        assert bundle.logs == []

    def test_ctx_with_get_recent_logs(self):
        class CtxWithLogs:
            version = "1.0"
            config_file = ""
            _config: dict = {}

            def get_recent_logs(self):
                return ["line 1", "line 2"]

        ctx = CtxWithLogs()
        bundle = _collect_diagnostics(ctx)
        assert bundle.logs == ["line 1", "line 2"]

    def test_settings_snapshot_from_config(self):
        class CtxWithConfig:
            version = "1.0"
            config_file = ""
            _config = {"ai/ai/default": {"weaken_fac": 1.0}, "game/rules": "japanese"}

        ctx = CtxWithConfig()
        bundle = _collect_diagnostics(ctx)
        # The settings snapshot should contain our config keys
        # (exact form depends on collect_settings_snapshot impl)
        assert bundle.settings is not None


# =============================================================================
# Late import (requires diagnostics module)
# =============================================================================

from katrain.gui.features.diagnostics_popup import _collect_diagnostics  # noqa: E402
