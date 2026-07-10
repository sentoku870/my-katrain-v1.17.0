"""Export tab (Tab 2) for the myKatrain settings popup.

Phase 175: Extracted from settings_popup.py into a dedicated submodule.
Split into per-section builders (Phase 165-b pattern) for readability.

This module holds ONLY the ``_build_export_tab`` function and its
section builders. Each section builder appends its widgets to the
shared ``inner`` container and is self-contained.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput

from katrain.core.lang import i18n
from katrain.gui.features.settings_popup_helpers import _add_searchable_label
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button, Label
from katrain.gui.widgets.helpers import create_text_input_row

if TYPE_CHECKING:
    from kivy.uix.boxlayout import BoxLayout as BoxLayoutType

    from katrain.gui.features.settings_popup_state import _SettingsPopupContext


def _build_user_name_row(inner: BoxLayoutType, state: _SettingsPopupContext) -> TextInput:
    """Add the default user name text input row. Returns the TextInput."""
    user_row, user_input, _ = create_text_input_row(
        label_text=i18n._("mykatrain:settings:default_user_name"),
        initial_value=state.current_settings.get("default_user_name", ""),
    )
    inner.add_widget(user_row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:default_user_name", user_row)
    return user_input


def _build_output_dir_row(inner: BoxLayoutType, state: _SettingsPopupContext) -> tuple[TextInput, Button]:
    """Add the karte output directory row. Returns (TextInput, browse Button)."""
    output_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    output_label = Label(
        text=i18n._("mykatrain:settings:karte_output_directory"),
        size_hint_x=0.35,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    output_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    output_input = TextInput(
        text=state.current_settings.get("karte_output_directory", ""),
        multiline=False,
        size_hint_x=0.5,
        font_name=Theme.DEFAULT_FONT,
    )
    output_browse = Button(
        text=i18n._("Browse..."),
        size_hint_x=0.15,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    output_row.add_widget(output_label)
    output_row.add_widget(output_input)
    output_row.add_widget(output_browse)
    inner.add_widget(output_row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:karte_output_directory", output_row)
    return output_input, output_browse


def _build_input_dir_row(inner: BoxLayoutType, state: _SettingsPopupContext) -> tuple[TextInput, Button]:
    """Add the batch export input directory row. Returns (TextInput, browse Button)."""
    input_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    input_label = Label(
        text=i18n._("mykatrain:settings:batch_export_input_directory"),
        size_hint_x=0.35,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    input_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    input_input = TextInput(
        text=state.current_settings.get("batch_export_input_directory", ""),
        multiline=False,
        size_hint_x=0.5,
        font_name=Theme.DEFAULT_FONT,
    )
    input_browse = Button(
        text=i18n._("Browse..."),
        size_hint_x=0.15,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    input_row.add_widget(input_label)
    input_row.add_widget(input_input)
    input_row.add_widget(input_browse)
    inner.add_widget(input_row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:batch_export_input", input_row)
    return input_input, input_browse


def _build_karte_format_section(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Add the karte format radio button group (2x2 grid)."""
    _add_searchable_label(inner, "mykatrain:settings:karte_format", state)

    format_layout = GridLayout(cols=2, spacing=dp(5), size_hint_y=None, height=dp(80))
    format_options = [
        ("both", i18n._("mykatrain:settings:format_both")),
        ("black_only", i18n._("mykatrain:settings:format_black_only")),
        ("white_only", i18n._("mykatrain:settings:format_white_only")),
        ("default_user_only", i18n._("mykatrain:settings:format_default_user_only")),
    ]

    for format_value, format_label_text in format_options:
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36))
        checkbox = CheckBox(
            group="karte_format",
            active=(format_value == state.selected_format[0]),
            size_hint_x=None,
            width=dp(30),
        )
        checkbox.bind(
            active=lambda chk, active, val=format_value: state.selected_format.__setitem__(0, val) if active else None
        )
        label = Label(
            text=format_label_text,
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        row.add_widget(checkbox)
        row.add_widget(label)
        format_layout.add_widget(row)
    inner.add_widget(format_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:karte_format", format_layout)


def _build_opp_info_section(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Add the opponent info mode radio button group (2x2 grid) - Phase 4."""
    _add_searchable_label(inner, "mykatrain:settings:opponent_info_mode", state)

    opp_info_layout = GridLayout(cols=2, spacing=dp(5), size_hint_y=None, height=dp(80))
    opp_info_options = [
        ("auto", i18n._("mykatrain:settings:opponent_info_auto")),
        ("always_detailed", i18n._("mykatrain:settings:opponent_info_detailed")),
        ("always_aggregate", i18n._("mykatrain:settings:opponent_info_aggregate")),
    ]

    for opp_value, opp_label_text in opp_info_options:
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36))
        checkbox = CheckBox(
            group="opponent_info_mode",
            active=(opp_value == state.selected_opp_info[0]),
            size_hint_x=None,
            width=dp(30),
        )
        checkbox.bind(
            active=lambda chk, active, val=opp_value: state.selected_opp_info.__setitem__(0, val) if active else None
        )
        label = Label(
            text=opp_label_text,
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        row.add_widget(checkbox)
        row.add_widget(label)
        opp_info_layout.add_widget(row)
    inner.add_widget(opp_info_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:opponent_info_mode", opp_info_layout)


def _build_reset_button() -> Button:
    """Build the Export tab reset button."""
    return Button(
        text=i18n._("mykatrain:settings:reset"),
        size_hint_y=None,
        height=dp(36),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )


def _build_export_tab(state: _SettingsPopupContext) -> tuple[BoxLayout, Button, dict[str, Any]]:
    """Build the Export tab content (Tab 2).

    Phase 175: Extracted from ``do_mykatrain_settings_popup`` and split
    into per-section builders.

    Args:
        state: Shared mutable state. Mutates ``selected_format`` and
            ``selected_opp_info`` via radio callbacks.

    Returns:
        (inner_layout, reset_button, widget_refs): widget_refs contains
        ``user_input``, ``output_input``, ``input_input``, ``output_browse``,
        ``input_browse``. The orchestrator uses these to wire save_settings
        and browse callbacks.
    """
    inner = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None)
    inner.bind(minimum_height=inner.setter("height"))

    user_input = _build_user_name_row(inner, state)
    output_input, output_browse = _build_output_dir_row(inner, state)
    input_input, input_browse = _build_input_dir_row(inner, state)
    _build_karte_format_section(inner, state)
    _build_opp_info_section(inner, state)

    reset_btn = _build_reset_button()
    inner.add_widget(reset_btn)

    widget_refs = {
        "user_input": user_input,
        "output_input": output_input,
        "input_input": input_input,
        "output_browse": output_browse,
        "input_browse": input_browse,
    }
    return inner, reset_btn, widget_refs
