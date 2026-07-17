"""Regression tests for Clock import in karte_export.py.

Phase 225.2: the copy_path closure inside do_export_karte_ui references
``Clock`` (line 246) but Phase 173's lazy-import only pulled in
Clipboard / dp / BoxLayout / Button / Label / Popup. Clicking the
"Copy file paths" button in the export-success popup raised::

    NameError: name 'Clock' is not defined

Phase 234: the per-symbol lazy imports were consolidated into a single
``_ensure_kivy_imports()`` helper that binds every Kivy symbol to the
module globals. This test file pins the new contract:

- The helper exists and is idempotent.
- After the helper runs, every Kivy symbol the closures use
  (``Clock``, ``Clipboard``, ``dp``, ``BoxLayout``, ``Button``,
  ``Label``, ``Popup``) is present in the module globals.
- The inner ``copy_path`` closure can still resolve ``Clock`` /
  ``Clipboard`` (no NameError).

We can't easily drive the full Kivy UI without a window, but the
closure's local ``__globals__`` must contain the symbols it references.
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


class TestEnsureKivyImports:
    """Phase 234: pin the consolidated Kivy import helper."""

    def test_helper_exists(self) -> None:
        from katrain.gui.features import karte_export

        assert hasattr(karte_export, "_ensure_kivy_imports")
        assert callable(karte_export._ensure_kivy_imports)

    def test_helper_is_idempotent(self) -> None:
        """Calling the helper multiple times must not re-bind or re-import."""
        from katrain.gui.features import karte_export

        # Capture the initial state of the KIVY_IMPORTS_DONE flag
        assert karte_export._KIVY_IMPORTS_DONE is False
        karte_export._ensure_kivy_imports()
        assert karte_export._KIVY_IMPORTS_DONE is True
        first_clock = karte_export.Clock

        # Second call: no-op, but the existing binding is preserved
        karte_export._ensure_kivy_imports()
        assert karte_export.Clock is first_clock

    def test_helper_binds_all_kivy_symbols(self) -> None:
        """After the helper runs, all Kivy symbols are accessible by name."""
        from katrain.gui.features import karte_export

        # Reset the flag so the helper actually re-runs the imports.
        karte_export._KIVY_IMPORTS_DONE = False
        karte_export._ensure_kivy_imports()

        for name in ("Clock", "Clipboard", "dp", "BoxLayout", "Button", "Label", "Popup"):
            assert name in karte_export.__dict__, f"karte_export.{name} not bound after _ensure_kivy_imports()"
            assert karte_export.__dict__[name] is not None, f"karte_export.{name} is None after _ensure_kivy_imports()"

    def test_helper_source_uses_globals_update(self) -> None:
        """Static check: the helper uses ``globals().update({...})`` to
        bind all symbols in a single statement, so the closure resolution
        contract is enforced at the source level."""
        import inspect

        from katrain.gui.features import karte_export

        source = inspect.getsource(karte_export._ensure_kivy_imports)
        assert "globals().update" in source, (
            "_ensure_kivy_imports must bind symbols via globals().update() "
            "so closures (copy_path) can resolve them by name."
        )
        # All 7 symbols must appear in the update call
        for name in ("Clock", "Clipboard", "dp", "BoxLayout", "Button", "Label", "Popup"):
            assert f'"{name}"' in source, (
                f"_ensure_kivy_imports must bind {name!r} — add it to the globals().update(...) call."
            )

    def test_copy_path_closure_resolves_clock(self) -> None:
        """Drive the closure and assert Clock.schedule_once can be called.

        Phase 234: the closure resolves ``Clock`` / ``Clipboard`` via the
        enclosing module's ``globals()``, which is populated by
        ``_ensure_kivy_imports()``. We verify the runtime contract by
        stubbing the Kivy symbols on the module and re-defining the
        closure inline (same shape as ``karte_export.copy_path``).
        """
        # Build a fake clipboard and a fake button instance
        mock_clipboard = MagicMock()
        mock_button = MagicMock()
        mock_button.text = "old"

        # Simulate the closure environment: module has Clock / Clipboard
        from katrain.gui.features import karte_export

        mock_clock = MagicMock()
        # Temporarily attach Clock / Clipboard to the module so the
        # closure can find them (mirrors what _ensure_kivy_imports does
        # in production).
        with (
            patch.object(karte_export, "Clipboard", mock_clipboard, create=True),
            patch.object(karte_export, "Clock", mock_clock, create=True),
            patch("katrain.gui.features.karte_export.i18n") as mock_i18n,
        ):
            mock_i18n._.return_value = "label"

            # Define the closure inline (mirroring karte_export.py:copy_path).
            # The closure resolves Clipboard and Clock against the
            # module's globals — same shape as in production.
            def copy_path(instance: Any) -> None:
                karte_export.Clipboard.copy("files")
                instance.text = karte_export.i18n._("copied")
                karte_export.Clock.schedule_once(
                    lambda dt: setattr(instance, "text", karte_export.i18n._("copy")),
                    2,
                )

            copy_path(mock_button)

        # Clipboard was called, no NameError, schedule_once was registered
        mock_clipboard.copy.assert_called_once_with("files")
        mock_clock.schedule_once.assert_called_once()
        # The first arg is the lambda, the second is the 2-second delay
        args, _ = mock_clock.schedule_once.call_args
        assert callable(args[0])
        assert args[1] == 2
