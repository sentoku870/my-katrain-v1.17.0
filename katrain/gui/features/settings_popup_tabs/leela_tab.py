# katrain/gui/features/settings_popup_tabs/leela_tab.py
#
# Leela Zero tab (Tab 3) for the myKatrain settings popup.
#
# Phase 145-D+: Extracted from settings_popup.py to enable per-tab file separation.
# This module holds ONLY the _build_leela_tab function and its direct imports.

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


def _build_leela_tab(state: _SettingsPopupContext) -> tuple[BoxLayout, Button, dict[str, Any]]:
    """Build the Leela Zero tab content (Tab 3).

    Phase 145-D+: Extracted from ``do_mykatrain_settings_popup``.

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
    leela_path_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    leela_path_label = Label(
        text=i18n._("mykatrain:settings:leela_exe_path"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_path_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    leela_path_input = TextInput(
        text=leela.get("exe_path", ""),
        multiline=False,
        size_hint_x=0.55,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_path_browse = Button(
        text="...",
        size_hint_x=0.15,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    leela_path_row.add_widget(leela_path_label)
    leela_path_row.add_widget(leela_path_input)
    leela_path_row.add_widget(leela_path_browse)
    inner.add_widget(leela_path_row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:leela_exe_path", leela_path_row)

    # --- Leela K Value Slider ---
    leela_k_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    leela_k_label = Label(
        text=i18n._("mykatrain:settings:leela_k_value"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_k_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    leela_k_slider = Slider(
        min=0.1,  # Practical minimum
        max=1.0,  # Practical maximum (reduced from 2.0)
        value=leela.get("loss_scale_k", LEELA_K_DEFAULT),
        step=0.05,  # Finer adjustment (changed from 0.1)
        size_hint_x=0.50,
    )
    leela_k_value_label = Label(
        text=f"{leela_k_slider.value:.2f}",  # Show 2 decimal places for 0.05 step
        size_hint_x=0.20,
        halign="center",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_k_slider.bind(value=lambda inst, val: setattr(leela_k_value_label, "text", f"{val:.2f}"))
    leela_k_row.add_widget(leela_k_label)
    leela_k_row.add_widget(leela_k_slider)
    leela_k_row.add_widget(leela_k_value_label)
    inner.add_widget(leela_k_row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:leela_k_value", leela_k_row)

    # --- Leela Max Visits ---
    leela_visits_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    leela_visits_label = Label(
        text=i18n._("mykatrain:settings:leela_max_visits"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_visits_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    leela_visits_input = TextInput(
        text=str(leela.get("max_visits", 1000)),
        multiline=False,
        input_filter="int",
        size_hint_x=0.70,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_visits_row.add_widget(leela_visits_label)
    leela_visits_row.add_widget(leela_visits_input)
    inner.add_widget(leela_visits_row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:leela_max_visits", leela_visits_row)

    # --- Leela Max Candidates (Phase 3) ---
    leela_cand_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    leela_cand_label = Label(
        text=i18n._("mykatrain:settings:leela_max_candidates"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_cand_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    leela_cand_spinner = I18NSpinner(
        size_hint_x=0.70,
        height=dp(36),
    )
    leela_cand_spinner.value_refs = ["3", "5", "7", "auto"]
    leela_cand_spinner.build_values()
    current_val = leela.get("max_candidates", 5)
    # Handle both integer and "auto" string values
    if current_val == -1 or str(current_val).lower() == "auto":
        leela_cand_spinner.select_key("auto")
    else:
        leela_cand_spinner.select_key(str(current_val))
    leela_cand_row.add_widget(leela_cand_label)
    leela_cand_row.add_widget(leela_cand_spinner)
    inner.add_widget(leela_cand_row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:leela_max_candidates", leela_cand_row)

    # --- Leela Fast Visits (Phase 30) ---
    leela_fast_visits_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    leela_fast_visits_label = Label(
        text=i18n._("mykatrain:settings:leela_fast_visits"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_fast_visits_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    leela_fast_visits_input = TextInput(
        text=str(leela.get("fast_visits", 200)),
        multiline=False,
        input_filter="int",
        size_hint_x=0.70,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_fast_visits_row.add_widget(leela_fast_visits_label)
    leela_fast_visits_row.add_widget(leela_fast_visits_input)
    inner.add_widget(leela_fast_visits_row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:leela_fast_visits", leela_fast_visits_row)

    # --- Leela Top Moves Display ---
    # leela_play_visits REMOVED (Phase 123)
    leela_top_moves_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    leela_top_moves_label = Label(
        text=i18n._("mykatrain:settings:leela_top_moves_show"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_top_moves_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    leela_top_moves_spinner = I18NSpinner(size_hint_x=0.35)
    leela_top_moves_spinner.value_refs = LEELA_TOP_MOVE_OPTIONS
    leela_top_moves_spinner.build_values()
    leela_top_moves_spinner.select_key(leela.get("top_moves_show", "leela_top_move_loss"))

    leela_top_moves_spinner_2 = I18NSpinner(size_hint_x=0.35)
    leela_top_moves_spinner_2.value_refs = LEELA_TOP_MOVE_OPTIONS_SECONDARY
    leela_top_moves_spinner_2.build_values()
    leela_top_moves_spinner_2.select_key(leela.get("top_moves_show_secondary", "leela_top_move_winrate"))

    leela_top_moves_row.add_widget(leela_top_moves_label)
    leela_top_moves_row.add_widget(leela_top_moves_spinner)
    leela_top_moves_row.add_widget(leela_top_moves_spinner_2)
    inner.add_widget(leela_top_moves_row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:leela_top_moves_show", leela_top_moves_row)

    # --- Reset button ---
    reset_btn = Button(
        text=i18n._("mykatrain:settings:reset"),
        size_hint_y=None,
        height=dp(36),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
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
