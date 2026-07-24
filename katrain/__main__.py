"""isort:skip_file"""
# mypy: ignore-errors
# Note: Contains Windows-specific code paths (ctypes.windll).
# On Linux CI, mypy cannot resolve Windows API calls, but these are guarded by platform checks.

from __future__ import annotations

# first, logging level lower
import os
import sys
from typing import TYPE_CHECKING

os.environ["KCFG_KIVY_LOG_LEVEL"] = os.environ.get("KCFG_KIVY_LOG_LEVEL", "warning")

from kivy.utils import platform as kivy_platform

if TYPE_CHECKING:
    pass

if kivy_platform == "win":
    from ctypes import c_int64, windll

    if hasattr(windll.user32, "SetProcessDpiAwarenessContext"):
        windll.user32.SetProcessDpiAwarenessContext(c_int64(-4))

import kivy

kivy.require("2.0.0")

# Phase 277: KivyMD 1.2.0 ships without its companion .kv files. Install
# stub .kv files and override kivymd.uix_path BEFORE any kivymd.uix.* module
# is imported. See katrain/gui/_kivymd_kv_loader.py for details.
from katrain.gui import _kivymd_kv_loader  # noqa: E402

_kivymd_kv_loader.ensure_kivymd_kv_stubs()

# next, icon
from kivy.config import Config

# Phase PR3: ICON lives in gui/app.py to avoid circular import. Re-export
# here so the rest of __main__.py and external code can still use it.
from katrain.gui.app import ICON  # noqa: E402, F401

Config.set("kivy", "window_icon", ICON)
Config.set("input", "mouse", "mouse,multitouch_on_demand")

# next, certificates on package builds https://github.com/sanderland/katrain/issues/414
if getattr(sys, "frozen", False):
    import ssl

    if ssl.get_default_verify_paths().cafile is None and hasattr(sys, "_MEIPASS"):
        os.environ["SSL_CERT_FILE"] = os.path.join(sys._MEIPASS, "certifi", "cacert.pem")


import signal
import traceback

from kivy.base import ExceptionHandler, ExceptionManager
from kivymd.app import MDApp

# =============================================================================
# Phase PR3: Re-export top-level GUI classes from gui/app.py for
# backwards compatibility with TYPE_CHECKING references in error_handler,
# commands modules, and tests.
# =============================================================================
from katrain.core.constants.metadata import HOMEPAGE  # noqa: F401  (re-export)
from katrain.core.constants.modes import MODE_ANALYZE  # noqa: F401  (re-export)
from katrain.core.constants.output import OUTPUT_DEBUG, OUTPUT_ERROR, OUTPUT_INFO, STATUS_INFO  # noqa: F401
from katrain.gui.app import (  # noqa: E402, F401
    AnalysisController,
    AutoSetupController,
    BatchAnalysisController,
    ConfigManager,
    DialogFactory,
    ErrorHandler,
    GameStateManager,
    GameStateUpdateManager,
    GUIRefreshManager,
    KaTrainApp,
    KaTrainGui,
    KeyboardManager,
    MessageLoopManager,
    PopupManager,
    ScrollHandler,
    SGFManager,
    SummaryManager,
    UIUpdateManager,
    webbrowser,
)
from katrain.gui.sound import play_sound  # noqa: E402, F401


def run_app() -> None:
    class CrashHandler(ExceptionHandler):
        def handle_exception(self, inst: Exception) -> int:
            ex_type, ex, tb = sys.exc_info()
            trace = "".join(traceback.format_tb(tb))
            app = MDApp.get_running_app()

            if app and app.gui:
                app.gui.log(
                    f"Exception {inst.__class__.__name__}: {', '.join(repr(a) for a in inst.args)}\n{trace}",
                    OUTPUT_ERROR,
                )
            else:
                print(f"Exception {inst.__class__}: {inst.args}\n{trace}")
            return ExceptionManager.PASS  # type: ignore[no-any-return]

    ExceptionManager.add_handler(CrashHandler())

    # Phase 163: Apply Kivy log configuration AFTER Kivy is fully loaded
    # (was previously called from core/base_katrain.py via dynamic spec loader).
    from katrain.gui.kivyutils.app_config import apply_kivy_log_config

    apply_kivy_log_config(0)  # default level; the GUI's settings may override

    app = KaTrainApp()
    signal.signal(signal.SIGINT, app.signal_handler)
    app.run()


if __name__ == "__main__":
    run_app()
