"""Phase 179-B1: Critical 3 toast popup.

A short-lived modal-less popup that appears when the user lands on a
position flagged as Critical 3. It uses the same ``I18NPopup`` wrapper as
other kifunarabe popups and auto-dismisses after 1.5 seconds so it never
blocks the main flow.
"""

from __future__ import annotations

from typing import Any


def show_critical_3_badge(ctx: Any, move_number: int) -> None:
    """Show a short Critical 3 toast for the given move number.

    Args:
        ctx: KaTrainGui instance (currently unused, kept for symmetry
            with other kifunarabe popups and future sound hooks).
        move_number: 1-indexed move number to display.
    """
    from kivy.clock import Clock
    from kivy.metrics import dp
    from kivy.uix.label import Label

    from katrain.core.lang import i18n
    from katrain.gui.popups._base import I18NPopup
    from katrain.gui.theme import Theme

    body = Label(
        text=i18n._("kifunarabe:critical3_badge").format(move=move_number),
        font_name=Theme.DEFAULT_FONT,
    )
    popup = I18NPopup(
        title_key="kifunarabe:critical3_badge_title",
        size_hint=(None, None),
        size=[dp(280), dp(120)],
        content=body,
    ).__self__
    popup.auto_dismiss = True
    popup.open()
    Clock.schedule_once(lambda _dt: popup.dismiss(), 1.5)
