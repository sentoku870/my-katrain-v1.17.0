# katrain/gui/features/commands/export_commands.py
from __future__ import annotations

"""Export-related command handlers extracted from KaTrainGui (Phase 41-B).

Phase 230-A.2: メニューから ``open_latest_report`` / ``open_output_folder`` /
``export_summary`` / ``export_summary_ui`` の 4 ハンドラを削除。
残ったのは ``do_save_game`` と ``do_export_karte`` のみ。

These functions handle saving games and exporting reports.
The ctx parameter is expected to be a KaTrainGui instance (satisfies FeatureContext).
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui


def do_save_game(ctx: KaTrainGui, filename: str | None = None) -> None:
    """Save game to SGF file.

    Args:
        ctx: KaTrainGui instance
        filename: Optional filename; if None, uses default
    """
    ctx._sgf_manager.save_game(filename)


def do_export_karte(ctx: KaTrainGui, *args: Any, **kwargs: Any) -> None:
    """Export karte report.

    Args:
        ctx: KaTrainGui instance.
        *args, **kwargs: Optional first positional arg may be a callable
            that opens the settings popup (programmatic callers can pass
            their own callback).  When omitted — as is the case for the
            ``root.katrain("export-karte")`` menu binding routed through
            the DISPATCH_TABLE — we fall back to the mykatrain settings
            popup as the default.  This restores the pre-Phase 172
            behaviour where ``_do_export_karte`` injected
            ``self._do_mykatrain_settings_popup`` internally.

    Phase 225.1 regression fix: the previous signature was
    ``do_export_karte(ctx, settings_popup_callback)`` (required keyword),
    which crashed with ``TypeError: missing 1 required positional
    argument: 'settings_popup_callback'`` whenever the user clicked the
    "Export Karte" menu entry.
    """
    from katrain.gui.features.karte_export import do_export_karte as _do_export_karte
    from katrain.gui.features.settings_popup import do_mykatrain_settings_popup

    # Resolve the settings-popup callback. Menu dispatch passes no args,
    # so the default must still be callable when ``karte_output_directory``
    # is unconfigured.
    if args and callable(args[0]):
        settings_popup_callback: Callable[[], None] = args[0]
    else:

        def _open_mykatrain_settings_popup() -> None:
            do_mykatrain_settings_popup(ctx)

        settings_popup_callback = _open_mykatrain_settings_popup

    _do_export_karte(ctx, settings_popup_callback)


# Phase 230-A.2: do_open_latest_report / do_open_output_folder /
# do_export_summary / do_export_summary_ui は完全削除。
# メニューからのみアクセスされており、他に呼び出し経路なし。
