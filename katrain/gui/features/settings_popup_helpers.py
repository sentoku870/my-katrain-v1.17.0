# katrain/gui/features/settings_popup_helpers.py
#
# Shared Kivy widget helpers for the settings popup tab builders.
#
# Phase 145-D+: Extracted from settings_popup.py to enable cleaner separation.
# This module holds small helpers that don't depend on the popup's _SettingsPopupContext.

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from katrain.core.lang import i18n
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.features.settings_popup_state import _SettingsPopupContext


def _add_searchable_label(
    container: BoxLayout,
    text_key: str,
    state: _SettingsPopupContext,
    height: int = 25,
    size_hint_x: float | None = None,
) -> Label:
    """Helper: add a labelled section header that registers as searchable.

    Centralizes the repeated pattern of creating a Label with theme defaults
    and registering it for the search bar.

    Args:
        container: Parent layout to add the label to.
        text_key: i18n key for the label text.
        state: Shared popup state. The label is registered via state.register_searchable
            if that closure has been set by the orchestrator.
        height: Label height in dp.
        size_hint_x: Optional explicit width ratio.

    Returns:
        The created Label widget.
    """
    label = Label(
        text=i18n._(text_key),
        size_hint_y=None,
        height=dp(height),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    if size_hint_x is not None:
        label.size_hint_x = size_hint_x
    label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    container.add_widget(label)
    if state.register_searchable is not None:
        state.register_searchable(text_key, label)
    return label
