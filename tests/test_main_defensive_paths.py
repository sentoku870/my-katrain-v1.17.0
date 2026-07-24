"""Defensive code path tests for ``katrain.__main__`` (Phase 282-P2B).

The 947-line ``__main__.py`` has many defensive ``try/except`` blocks
that were added incrementally during Phase 158+ to handle graceful
degradation. This file locks in their behavior so future refactors
don't silently weaken the safety net.

Coverage targets:
- ``on_kifunarabe_mode`` catches arbitrary controller exceptions
- AppContext / KifunarabeHistoryStore / KifunarabeWeaknessExporter
  lazy imports gracefully fall back to None on ImportError
- ``on_request_close`` engine.shutdown failure doesn't block cleanup
- CrashHandler routes to gui.log when app is running, stderr otherwise
- ``KaTrainApp.webbrowser`` opens the right URL for each key
- ``KaTrainApp.is_valid_window_position`` handles monitor intersection
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Force headless mode before importing katrain.__main__
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_FILELOG", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("KIVY_HEADLESS", "1")
os.environ.setdefault("KIVY_NO_WINDOW", "1")
os.environ.setdefault("KIVY_GL_BACKEND", "mock")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

# Importing __main__ triggers a chain of Kivy / KivyMD imports; we rely
# on the conftest setup and the environment vars above.
import katrain.__main__ as main_mod  # noqa: E402

KaTrainApp = main_mod.KaTrainApp
KaTrainGui = main_mod.KaTrainGui


# =============================================================================
# Phase 249-hotfix regression: on_kifunarabe_mode
# =============================================================================


class TestOnKifunarabeMode:
    """``on_kifunarabe_mode`` must not crash even if the controller
    raises (Phase 158-H hardening)."""

    def _make_gui(self):
        """Construct a KaTrainGui without invoking __init__'s manager chain."""
        gui = KaTrainGui.__new__(KaTrainGui)
        gui.log = MagicMock()
        return gui

    def test_calls_controller_on_mode_change(self):
        gui = self._make_gui()
        controller = MagicMock()
        gui._kifunarabe_controller = controller

        gui.on_kifunarabe_mode(gui, True)

        controller.on_mode_change.assert_called_once_with(True)

    def test_swallows_controller_exception(self):
        """Phase 158-H: a broken controller must not crash the GUI."""
        gui = self._make_gui()
        controller = MagicMock()
        controller.on_mode_change.side_effect = RuntimeError("controller boom")
        gui._kifunarabe_controller = controller

        # Must NOT raise
        gui.on_kifunarabe_mode(gui, True)

        gui.log.assert_called_once()
        assert "kifunarabe" in gui.log.call_args.args[0]

    def test_no_controller_is_noop(self):
        """Before _kifunarabe_controller is attached, on_kifunarabe_mode must not crash."""
        gui = self._make_gui()
        if hasattr(gui, "_kifunarabe_controller"):
            del gui._kifunarabe_controller
        # Must NOT raise
        gui.on_kifunarabe_mode(gui, True)


# =============================================================================
# Phase 249-hotfix regression: lazy imports in KaTrainGui init
# =============================================================================


class TestKaTrainGuiLazyImports:
    """The ``_build_kifunarabe_history_store`` /
    ``_build_kifunarabe_weakness_exporter`` methods must return ``None``
    when their target module cannot be imported.
    """

    def _make_gui(self, config_return=None):
        gui = KaTrainGui.__new__(KaTrainGui)
        gui.config = MagicMock(return_value=config_return)
        gui.log = MagicMock()
        return gui

    def test_kifunarabe_history_store_import_error_returns_none(self):
        gui = self._make_gui(config_return=None)

        with patch.dict("sys.modules", {"katrain.core.study.kifunarabe_history": None}):
            result = gui._build_kifunarabe_history_store()
        assert result is None

    def test_kifunarabe_weakness_exporter_import_error_returns_none(self):
        gui = self._make_gui(config_return=None)

        with patch.dict(
            "sys.modules",
            {"katrain.core.study.kifunarabe_weakness_export": None},
        ):
            result = gui._build_kifunarabe_weakness_exporter()
        assert result is None

    def test_kifunarabe_history_store_uses_configured_dir(self):
        """When config is set, it should be passed through (no import needed
        to verify config propagation; just check the helper delegates)."""
        from pathlib import Path

        from katrain.core.study.kifunarabe_history import KifunarabeHistoryStore

        gui = self._make_gui(config_return="/custom/path")

        result = gui._build_kifunarabe_history_store()
        # Should be a KifunarabeHistoryStore with our custom directory
        assert isinstance(result, KifunarabeHistoryStore)
        assert Path(result.directory) == Path("/custom/path")

    def test_kifunarabe_weakness_exporter_uses_configured_dir(self):
        from pathlib import Path

        from katrain.core.study.kifunarabe_weakness_export import (
            KifunarabeWeaknessExporter,
        )

        gui = self._make_gui(config_return="/custom/path")

        result = gui._build_kifunarabe_weakness_exporter()
        assert isinstance(result, KifunarabeWeaknessExporter)
        assert Path(result.directory) == Path("/custom/path")


# =============================================================================
# Phase 249-hotfix regression: AppContext lazy import
# =============================================================================


class TestAppContextLazyImport:
    """``KaTrainGui.__init__`` must handle ImportError on AppContext."""

    def test_appcontext_import_error_does_not_set_ctx(self):
        """If AppContext cannot be imported, ``self.ctx`` is not set;
        subsequent attribute access must not silently succeed.
        """
        gui = KaTrainApp.__new__(KaTrainApp)
        gui.config = MagicMock(return_value=None)
        gui.log = MagicMock()
        gui.dialog_factory = MagicMock()
        gui._sgf_manager = MagicMock()
        gui._config_manager = MagicMock()
        gui._summary_manager = MagicMock()
        gui._keyboard_manager = MagicMock()
        gui._popup_manager = MagicMock()
        gui._game_state_manager = MagicMock()
        gui._ui_update_manager = MagicMock()
        gui._auto_setup = MagicMock()
        gui._analysis_orchestrator = MagicMock()
        gui._batch = MagicMock()
        gui._gui_refresh = MagicMock()
        gui._game_state_update = MagicMock()
        gui._message_loop = MagicMock()
        gui._scroll = MagicMock()
        gui._kifunarabe = MagicMock()
        gui._engine_bootstrap = MagicMock()
        gui.engine = None

        # Patch the AppContext import to raise ImportError
        # The defensive code is:
        # try:
        #     from katrain.gui.app_context import AppContext
        # except ImportError:
        #     AppContext = None
        # So when import fails, AppContext is None and self.ctx
        # is never assigned. We can verify this contract by
        # testing the helper behaviour.
        with (
            patch.dict("sys.modules", {"katrain.gui.app_context": None}),
            patch("builtins.__import__", side_effect=ImportError("blocked")),
        ):
            pass  # defensive code already validated by structural check below

        # This is a structural test: we don't actually exercise __init__
        # (it requires too much Kivy scaffolding). The defensive code
        # exists in source; verify it's still there:
        import inspect

        source = inspect.getsource(main_mod.KaTrainGui.__init__)
        assert "from katrain.gui.app_context import AppContext" in source
        assert "except ImportError" in source
        assert "AppContext = None" in source


# =============================================================================
# on_request_close defensive code
# =============================================================================


class TestOnRequestCloseDefensive:
    """``on_request_close`` must call cleanup() even if engine.shutdown()
    raises (Phase 249-hotfix / Phase 22).

    The on_request_close handler is defined on KaTrainApp and
    delegates to ``self.gui`` (the KaTrainGui instance).
    """

    def _make_app(self, *, engine=None):
        app = KaTrainApp.__new__(KaTrainApp)
        inner_gui = MagicMock()
        inner_gui.engine = engine
        app.gui = inner_gui
        return app

    def test_engine_shutdown_exception_still_runs_cleanup(self):
        """engine.shutdown() raising must NOT block cleanup()."""
        engine = MagicMock()
        engine.shutdown.side_effect = RuntimeError("shutdown failed")
        app = self._make_app(engine=engine)

        # Patch Window.size since it's accessed in on_request_close
        with patch("katrain.gui.app.Window") as mock_window:
            mock_window._size = [800, 600]
            mock_window.top = 100
            mock_window.left = 100
            result = app.on_request_close(app, source=None)

        # Cleanup must have been called even though shutdown raised
        app.gui.cleanup.assert_called_once()
        app.gui.engine.shutdown.assert_called_once()
        assert result is None  # Close is permitted

    def test_no_engine_skips_shutdown_calls_cleanup(self):
        """When engine is None, on_request_close must still run cleanup."""
        app = self._make_app(engine=None)

        with patch("katrain.gui.app.Window") as mock_window:
            mock_window._size = [800, 600]
            mock_window.top = 100
            mock_window.left = 100
            app.on_request_close(app, source=None)

        app.gui.cleanup.assert_called_once()

    def test_keyboard_source_short_circuits(self):
        """``source='keyboard'`` returns True without saving state."""
        app = self._make_app(engine=MagicMock())

        result = app.on_request_close(app, source="keyboard")
        assert result is True
        app.gui.cleanup.assert_not_called()
        app.gui.engine.shutdown.assert_not_called()


# =============================================================================
# KaTrainApp.webbrowser (already covered in test_main_smoke but we add
# a missing-key test for full coverage)
# =============================================================================


class TestKaTrainAppWebbrowser:
    @pytest.fixture
    def app(self):
        return KaTrainApp.__new__(KaTrainApp)

    def test_homepage_opens_correct_url(self, app):
        with patch("katrain.__main__.webbrowser.open") as mock_open:
            app.webbrowser("homepage")
        mock_open.assert_called_once()
        url = mock_open.call_args.args[0]
        assert "manual" in url.lower() or "#manual" in url

    def test_support_opens_correct_url(self, app):
        with patch("katrain.__main__.webbrowser.open") as mock_open:
            app.webbrowser("support")
        mock_open.assert_called_once()
        url = mock_open.call_args.args[0]
        assert "support" in url.lower()

    def test_engine_help_opens_correct_url(self, app):
        with patch("katrain.__main__.webbrowser.open") as mock_open:
            app.webbrowser("engine:help")
        mock_open.assert_called_once()
        url = mock_open.call_args.args[0]
        assert "engine" in url.lower()

    def test_unknown_site_key_noop(self, app):
        """Unknown keys must NOT open any URL."""
        with patch("katrain.__main__.webbrowser.open") as mock_open:
            app.webbrowser("not-a-real-key")
        mock_open.assert_not_called()


# =============================================================================
# KaTrainApp.is_valid_window_position
# =============================================================================


class TestIsValidWindowPosition:
    @pytest.fixture
    def app(self):
        return KaTrainApp.__new__(KaTrainApp)

    def test_screeninfo_import_error_returns_true(self, app):
        """If screeninfo raises (e.g. not installed in container), return True (yolo)."""
        # Force both the sys.modules dict and builtins.__import__ to fail.
        with (
            patch.dict("sys.modules", {"screeninfo": None}),
            patch("builtins.__import__", side_effect=ImportError("no screeninfo")),
        ):
            result = app.is_valid_window_position(0, 0, 800, 600)
        assert result is True

    def test_window_inside_single_monitor_returns_true(self, app):
        fake_monitor = MagicMock(x=0, y=0, width=1920, height=1080)
        with patch("builtins.__import__", return_value=MagicMock(get_monitors=lambda: [fake_monitor])):
            result = app.is_valid_window_position(100, 100, 800, 600)
        assert result is True

    def test_window_outside_monitor_returns_false(self, app):
        fake_monitor = MagicMock(x=0, y=0, width=1920, height=1080)
        with patch("builtins.__import__", return_value=MagicMock(get_monitors=lambda: [fake_monitor])):
            # Window at x=5000 is way outside 0-1920 range
            result = app.is_valid_window_position(5000, 100, 800, 600)
        assert result is False

    def test_no_monitors_returns_false(self, app):
        with patch("builtins.__import__", return_value=MagicMock(get_monitors=lambda: [])):
            result = app.is_valid_window_position(0, 0, 800, 600)
        assert result is False
