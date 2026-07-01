"""Leela Zero tab (Tab 3) for the myKatrain settings popup.

Phase 145-D+: Extracted from settings_popup.py to enable per-tab file separation.
Phase 165-b: Split _build_leela_tab into per-section builders.

This module holds ONLY the _build_leela_tab function and its section
builders. Each section builder is independent and self-contained.
"""
from __future__ import annotations

from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput

from katrain.core.constants import (
    LEELA_K_DEFAULT,
    LEELA_TOP_MOVE_OPTIONS,
    LEELA_TOP_MOVE_OPTIONS_SECONDARY,
)
from katrain.core.lang import i18n
from katrain.gui.features.settings_popup_state import _SettingsPopupContext
from katrain.gui.kivyutils import I18NSpinner
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button, Label


def _bind_text_size(label: Label) -> None:
    """Bind label size to update its text_size for proper alignment."""
    label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))


def _build_leela_path_section(state: _SettingsPopupContext, leela: dict[str, Any]) -> tuple[BoxLayout, TextInput, Button]:
    """Build the Leela executable path section (row + input + browse button)."""
    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    label = Label(
        text=i18n._("mykatrain:settings:leela_exe_path"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    _bind_text_size(label)
    path_input = TextInput(
        text=leela.get("exe_path", ""),
        multiline=False,
        size_hint_x=0.55,
        font_name=Theme.DEFAULT_FONT,
    )
    browse = Button(
        text="...",
        size_hint_x=0.15,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    row.add_widget(label)
    row.add_widget(path_input)
    row.add_widget(browse)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:leela_exe_path", row)
    return row, path_input, browse


def _build_leela_k_slider_section(state: _SettingsPopupContext, leela: dict[str, Any]) -> tuple[BoxLayout, Slider]:
    """Build the Leela K value slider section (row + slider)."""
    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    label = Label(
        text=i18n._("mykatrain:settings:leela_k_value"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    _bind_text_size(label)
    slider = Slider(
        min=0.1,  # Practical minimum
        max=1.0,  # Practical maximum (reduced from 2.0)
        value=leela.get("loss_scale_k", LEELA_K_DEFAULT),
        step=0.05,  # Finer adjustment (changed from 0.1)
        size_hint_x=0.50,
    )
    value_label = Label(
        text=f"{slider.value:.2f}",  # Show 2 decimal places for 0.05 step
        size_hint_x=0.20,
        halign="center",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    slider.bind(value=lambda inst, val: setattr(value_label, "text", f"{val:.2f}"))
    row.add_widget(label)
    row.add_widget(slider)
    row.add_widget(value_label)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:leela_k_value", row)
    return row, slider


def _build_leela_visits_section(
    state: _SettingsPopupContext,
    leela: dict[str, Any],
    i18n_key: str,
    default: int,
    config_key: str,
) -> tuple[BoxLayout, TextInput]:
    """Build a Leela visits input section (row + int TextInput)."""
    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    label = Label(
        text=i18n._(f"mykatrain:settings:{i18n_key}"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    _bind_text_size(label)
    text_input = TextInput(
        text=str(leela.get(config_key, default)),
        multiline=False,
        input_filter="int",
        size_hint_x=0.70,
        font_name=Theme.DEFAULT_FONT,
    )
    row.add_widget(label)
    row.add_widget(text_input)
    if state.register_searchable is not None:
        state.register_searchable(f"mykatrain:settings:{i18n_key}", row)
    return row, text_input


def _build_leela_cand_section(state: _SettingsPopupContext, leela: dict[str, Any]) -> tuple[BoxLayout, I18NSpinner]:
    """Build the Leela max candidates spinner section."""
    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    label = Label(
        text=i18n._("mykatrain:settings:leela_max_candidates"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    _bind_text_size(label)
    spinner = I18NSpinner(
        size_hint_x=0.70,
        height=dp(36),
    )
    spinner.value_refs = ["3", "5", "7", "auto"]
    spinner.build_values()
    current_val = leela.get("max_candidates", 5)
    if current_val == -1 or str(current_val).lower() == "auto":
        spinner.select_key("auto")
    else:
        spinner.select_key(str(current_val))
    row.add_widget(label)
    row.add_widget(spinner)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:leela_max_candidates", row)
    return row, spinner


def _build_leela_top_moves_section(
    state: _SettingsPopupContext, leela: dict[str, Any]
) -> tuple[BoxLayout, I18NSpinner, I18NSpinner]:
    """Build the Leela top moves display section (row + 2 spinners)."""
    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    label = Label(
        text=i18n._("mykatrain:settings:leela_top_moves_show"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    _bind_text_size(label)

    spinner_primary = I18NSpinner(size_hint_x=0.35)
    spinner_primary.value_refs = LEELA_TOP_MOVE_OPTIONS
    spinner_primary.build_values()
    spinner_primary.select_key(leela.get("top_moves_show", "leela_top_move_loss"))

    spinner_secondary = I18NSpinner(size_hint_x=0.35)
    spinner_secondary.value_refs = LEELA_TOP_MOVE_OPTIONS_SECONDARY
    spinner_secondary.build_values()
    spinner_secondary.select_key(leela.get("top_moves_show_secondary", "leela_top_move_winrate"))

    row.add_widget(label)
    row.add_widget(spinner_primary)
    row.add_widget(spinner_secondary)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:leela_top_moves_show", row)
    return row, spinner_primary, spinner_secondary


def _build_leela_reset_button() -> Button:
    """Build the Leela reset button."""
    return Button(
        text=i18n._("mykatrain:settings:reset"),
        size_hint_y=None,
        height=dp(36),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )


def _build_leela_tab(state: _SettingsPopupContext) -> tuple[BoxLayout, Button, dict[str, Any]]:
    """Build the Leela Zero tab content (Tab 3).

    Phase 145-D+: Extracted from ``do_mykatrain_settings_popup``.
    Phase 165-b: Split into per-section builders for readability.

    Args:
        state: Shared state. Reads ``state.leela_config`` for initial values.

    Returns:
        (inner_layout, reset_button, widget_refs): widget_refs contains
        ``leela_path_input``, ``leela_path_browse``, ``leela_k_slider``,
        ``leela_visits_input``, ``leela_fast_visits_input``, ``leela_cand_spinner``,
        ``leela_top_moves_spinner``, ``leela_top_moves_spinner_2``.
    """
    leela = state.leela_config
    inner = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None)
    inner.bind(minimum_height=inner.setter("height"))

    # Note: leela_enabled checkbox REMOVED in Phase 123, replaced by the
    # Analysis Engine selection in the Analysis tab.

    # --- Leela Executable Path ---
    path_row, leela_path_input, leela_path_browse = _build_leela_path_section(state, leela)
    inner.add_widget(path_row)

    # --- Leela K Value Slider ---
    k_row, leela_k_slider = _build_leela_k_slider_section(state, leela)
    inner.add_widget(k_row)

    # --- Leela Max Visits ---
    visits_row, leela_visits_input = _build_leela_visits_section(state, leela, "leela_max_visits", 1000, "max_visits")
    inner.add_widget(visits_row)

    # --- Leela Max Candidates ---
    cand_row, leela_cand_spinner = _build_leela_cand_section(state, leela)
    inner.add_widget(cand_row)

    # --- Leela Fast Visits ---
    fast_row, leela_fast_visits_input = _build_leela_visits_section(
        state, leela, "leela_fast_visits", 200, "fast_visits"
    )
    inner.add_widget(fast_row)

    # --- Leela Top Moves Display ---
    top_row, leela_top_moves_spinner, leela_top_moves_spinner_2 = _build_leela_top_moves_section(state, leela)
    inner.add_widget(top_row)

    # --- Reset button ---
    reset_btn = _build_leela_reset_button()
    inner.add_widget(reset_btn)

    widget_refs = {
        "leela_path_input": leela_path_input,
        "leela_path_browse": leela_path_browse,
        "leela_k_slider": leela_k_slider,
        "leela_visits_input": leela_visits_input,
        "leela_fast_visits_input": leela_fast_visits_input,
        "leela_cand_spinner": leela_cand_spinner,
        "leela_top_moves_spinner": leela_top_moves_spinner,
        "leela_top_moves_spinner_2": leela_top_moves_spinner_2,
    }
    return inner, reset_btn, widget_refs
