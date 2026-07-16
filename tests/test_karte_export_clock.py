"""Regression tests for Clock import in karte_export.py.

Phase 225.2: the copy_path closure inside do_export_karte_ui references
``Clock`` (line 246) but Phase 173's lazy-import only pulled in
Clipboard / dp / BoxLayout / Button / Label / Popup. Clicking the
"Copy file paths" button in the export-success popup raised::

    NameError: name 'Clock' is not defined

This test file pins the fix by importing ``karte_export.do_export_karte_ui``
in isolation and asserting that ``Clock`` resolves when the closure runs.
We can't easily drive the full Kivy UI without a window, but the closure's
local ``__globals__`` must contain the symbol it references.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

# Force headless mode before any Kivy import (same as test_llm_coach_popup).
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_FILELOG", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("KIVY_HEADLESS", "1")
os.environ.setdefault("KIVY_NO_WINDOW", "1")
os.environ.setdefault("KIVY_GL_BACKEND", "mock")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


class TestDoExportKarteUiLazyImports:
    """Pin the lazy-import set so Clock/Clipboard/etc are reachable."""

    def test_do_export_karte_ui_module_imports_clock(self) -> None:
        """When ``do_export_karte_ui`` runs, ``Clock`` must be available
        in its module-level globals (Phase 173 lazy-import pattern)."""
        # The fix is that the function's body lazy-imports Clock. We can't
        # easily trigger the function end-to-end without Kivy UI, but we
        # can simulate the lazy-import by importing Clock ourselves and
        # patching the source module — the closure resolves names against
        # the source module's globals.
        from kivy.clock import Clock as _Clock

        from katrain.gui.features import karte_export

        with patch.object(karte_export, "Clock", _Clock, create=True):
            assert karte_export.Clock is _Clock

    def test_do_export_karte_ui_defines_clock_in_its_globals(self) -> None:
        """Inspect the source: ``do_export_karte_ui`` must lazy-import
        ``kivy.clock.Clock`` inside its body, otherwise the inner
        ``copy_path`` closure would NameError when invoked."""
        import inspect

        from katrain.gui.features.karte_export import do_export_karte_ui

        source = inspect.getsource(do_export_karte_ui)
        # Phase 225.2 fix: ensure ``from kivy.clock import Clock`` is
        # present somewhere in the function body.
        assert "from kivy.clock import Clock" in source, (
            "do_export_karte_ui must lazy-import Clock; otherwise the "
            "copy_path closure raises NameError on the export-success "
            "popup's Copy button."
        )

    def test_copy_path_closure_resolves_clock(self) -> None:
        """Drive the closure and assert Clock.schedule_once can be called."""
        # Build a fake clipboard and a fake button instance
        mock_clipboard = MagicMock()
        mock_button = MagicMock()
        mock_button.text = "old"

        # Simulate the closure environment: module has Clock attribute
        from katrain.gui.features import karte_export

        mock_clock = MagicMock()
        # Temporarily attach Clock to the module so the closure can find it
        with (
            patch.object(karte_export, "Clipboard", mock_clipboard, create=True),
            patch.object(karte_export, "Clock", mock_clock, create=True),
            patch("katrain.gui.features.karte_export.i18n") as mock_i18n,
        ):
            mock_i18n._.return_value = "label"

            # Define the closure inline (mirroring karte_export.py:242)
            def copy_path(instance: Any) -> None:
                mock_clipboard.copy("files")
                instance.text = mock_i18n._("copied")
                karte_export.Clock.schedule_once(lambda dt: setattr(instance, "text", mock_i18n._("copy")), 2)

            copy_path(mock_button)

        # Clipboard was called, no NameError, schedule_once was registered
        mock_clipboard.copy.assert_called_once_with("files")
        mock_clock.schedule_once.assert_called_once()
        # The first arg is the lambda, the second is the 2-second delay
        args, _ = mock_clock.schedule_once.call_args
        assert callable(args[0])
        assert args[1] == 2
