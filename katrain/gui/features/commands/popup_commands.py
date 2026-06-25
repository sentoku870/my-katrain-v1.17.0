# katrain/gui/features/commands/popup_commands.py
from __future__ import annotations

"""Popup-related command handlers extracted from KaTrainGui (Phase 41-B, 140).

These functions handle opening various popup dialogs.
The ctx parameter is expected to be a KaTrainGui instance (satisfies FeatureContext).
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui


def do_select_box(ctx: KaTrainGui) -> None:
    """Begin region-of-interest selection on the board.

    Args:
        ctx: KaTrainGui instance
    """
    from katrain.core.constants import STATUS_INFO
    from katrain.core.lang import i18n

    ctx.controls.set_status(i18n._("analysis:region:start"), STATUS_INFO)
    ctx.board_gui.selecting_region_of_interest = True


def do_diagnostics_popup(ctx: KaTrainGui) -> None:
    """Show the diagnostics popup for bug report generation.

    Args:
        ctx: KaTrainGui instance
    """
    from katrain.gui.features.diagnostics_popup import show_diagnostics_popup

    show_diagnostics_popup(ctx)


def do_engine_recovery_popup(ctx: KaTrainGui, error_message: str, code: Any) -> None:
    """Show the engine recovery popup after a KataGo crash.

    Args:
        ctx: KaTrainGui instance
        error_message: Human-readable error description
        code: Engine exit code (or similar)
    """
    ctx._popup_manager.open_engine_recovery_popup(error_message, code)


def do_config_popup(ctx: KaTrainGui) -> None:
    """Open the general settings popup.

    Args:
        ctx: KaTrainGui instance
    """
    from kivy.metrics import dp

    from katrain.gui.popups import ConfigPopup, I18NPopup

    ctx.controls.timer.paused = True
    if not ctx.config_popup:
        ctx.config_popup = I18NPopup(
            title_key="general settings title", size=[dp(1200), dp(950)], content=ConfigPopup(ctx)
        ).__self__

    assert ctx.config_popup is not None
    ctx.config_popup.content.popup = ctx.config_popup
    ctx.config_popup.title += ": " + ctx.config_file
    ctx.config_popup.open()
