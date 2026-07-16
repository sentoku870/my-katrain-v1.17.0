"""Regression tests for ``katrain.gui.features.commands.export_commands``.

Phase 225.1: the ``do_export_karte`` menu binding used to crash with::

    TypeError: do_export_karte() missing 1 required positional argument:
        'settings_popup_callback'

after Phase 172 deleted the ``_do_export_karte`` wrapper on ``KaTrainGui``.
The DISPATCH_TABLE path (menu / message-queue) calls each command with
just the GUI instance, but the wrapper still required a second positional
arg.

These tests pin the wrapper's new ``*args, **kwargs`` signature and the
default-callback fallback that mirrors the pre-Phase 172 behaviour.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestDoExportKarteSignature:
    """The wrapper must accept a menu-style call with no extra args."""

    def test_no_args_does_not_raise_type_error(self) -> None:
        """Regression: ``do_export_karte(ctx)`` used to raise TypeError.

        The DISPATCH_TABLE path (`root.katrain('export-karte')` →
        ``message_queue.put([..., 'export_karte', (), {}])`` →
        ``dispatch(ctx, msg)`` → ``do_export_karte(ctx)``) was broken.
        """
        from katrain.gui.features.commands.export_commands import do_export_karte

        ctx = MagicMock()
        with patch(
            "katrain.gui.features.karte_export.do_export_karte"
        ) as mock_inner:
            # MUST NOT raise TypeError — the whole point of this fix.
            do_export_karte(ctx)
        assert mock_inner.called, "Inner do_export_karte should be invoked"

    def test_inner_called_with_callable_default_callback(self) -> None:
        """The wrapper injects a default callback when none is provided."""
        from katrain.gui.features.commands.export_commands import do_export_karte

        ctx = MagicMock()
        with patch(
            "katrain.gui.features.karte_export.do_export_karte"
        ) as mock_inner:
            do_export_karte(ctx)
        args, _ = mock_inner.call_args
        # Position 0 = ctx, position 1 = callback (default injected).
        assert args[0] is ctx
        assert callable(args[1]), "Default callback must be callable"

    def test_explicit_callback_is_forwarded(self) -> None:
        """Programmatic callers can still supply their own callback."""
        from katrain.gui.features.commands.export_commands import do_export_karte

        ctx = MagicMock()
        callback = MagicMock()
        with patch(
            "katrain.gui.features.karte_export.do_export_karte"
        ) as mock_inner:
            do_export_karte(ctx, callback)
        args, _ = mock_inner.call_args
        assert args[1] is callback, "Caller-supplied callback must be passed through"

    def test_default_callback_opens_settings_popup(self) -> None:
        """When the menu path is taken and output_dir is unconfigured,
        the default callback opens the mykatrain settings popup (Phase 172
        parity)."""
        from katrain.gui.features.commands.export_commands import do_export_karte

        ctx = MagicMock()
        with patch("katrain.gui.features.settings_popup.do_mykatrain_settings_popup") as mock_open, \
             patch("katrain.gui.features.karte_export.do_export_karte") as mock_inner:
            do_export_karte(ctx)
        # Grab the default callback and invoke it
        default_callback = mock_inner.call_args[0][1]
        default_callback()
        mock_open.assert_called_once_with(ctx)


class TestDoExportKarteDispatchIntegration:
    """Confirm the wrapper is reachable via the DISPATCH_TABLE."""

    def test_registered_in_dispatch_table(self) -> None:
        from katrain.gui.features.commands import DISPATCH_TABLE, _DISPATCH_KEYS

        assert "export_karte" in _DISPATCH_KEYS
        assert "export_karte" in DISPATCH_TABLE

    def test_dispatch_invokes_with_single_ctx_arg(self) -> None:
        """Simulate the menu-binding path end-to-end through the dispatcher."""
        from katrain.gui.features.commands import dispatch

        ctx = MagicMock()
        with patch("katrain.gui.features.karte_export.do_export_karte") as mock_inner:
            # No *args, **kwargs — matches ``root.katrain("export-karte")``.
            dispatch(ctx, "export_karte")
        mock_inner.assert_called_once()
        # The wrapper received ctx AND a default callback.
        assert mock_inner.call_args[0][0] is ctx
        assert callable(mock_inner.call_args[0][1])


# Phase 230-A.2: TestOtherExportCommandsParity クラスを削除。
# do_open_latest_report / do_open_output_folder / do_export_summary /
# do_export_summary_ui の 4 関数は export_commands.py から完全削除。


@pytest.mark.parametrize(
    "menu_binding_message",
    ["export_karte"],
)
def test_full_menu_dispatch_path(menu_binding_message: str) -> None:
    """End-to-end: simulate root.katrain('export-karte') and verify the
    inner karte_export.do_export_karte receives both ctx and a callable
    callback (no TypeError anywhere along the way)."""
    from katrain.gui.features.commands import dispatch

    ctx = MagicMock()
    with patch("katrain.gui.features.karte_export.do_export_karte") as mock_inner:
        # Simulate the message_loop_manager passing tuple args to dispatch.
        dispatch(ctx, menu_binding_message)
    mock_inner.assert_called_once()
    call_args = mock_inner.call_args[0]
    assert call_args[0] is ctx, "ctx must be the first positional arg"
    assert callable(call_args[1]), "default callback must be a callable"