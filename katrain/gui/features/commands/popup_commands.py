# katrain/gui/features/commands/popup_commands.py
from __future__ import annotations

"""Popup-related command handlers extracted from KaTrainGui (Phase 41-B).

These functions handle opening various popup dialogs.
The ctx parameter is expected to be a KaTrainGui instance (satisfies FeatureContext).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui


def do_config_popup(ctx: "KaTrainGui") -> None:
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
