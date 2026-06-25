# katrain/gui/features/commands/export_commands.py
from __future__ import annotations

"""Export-related command handlers extracted from KaTrainGui (Phase 41-B).

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


def do_export_karte(ctx: KaTrainGui, settings_popup_callback: Callable[[], None]) -> None:
    """Export karte report.

    Args:
        ctx: KaTrainGui instance
        settings_popup_callback: Callback to open settings popup
    """
    from katrain.gui.features.karte_export import do_export_karte as _do_export_karte

    _do_export_karte(ctx, settings_popup_callback)


def do_open_latest_report(ctx: KaTrainGui, *args: Any, **kwargs: Any) -> None:
    """Open the most recent report file in the system viewer.

    Args:
        ctx: KaTrainGui instance
    """
    from katrain.gui.features.report_navigator import open_latest_report

    open_latest_report(ctx)


def do_open_output_folder(ctx: KaTrainGui, *args: Any, **kwargs: Any) -> None:
    """Open the output folder in the system file manager.

    Args:
        ctx: KaTrainGui instance
    """
    from katrain.gui.features.report_navigator import open_output_folder

    open_output_folder(ctx)
