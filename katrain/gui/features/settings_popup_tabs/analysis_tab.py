"""Analysis tab (Tab 1) for the myKatrain settings popup.

Phase 175: Extracted from settings_popup.py into a dedicated submodule.
Split into per-section builders (Phase 165-b pattern) for readability.

This module holds ONLY the ``_build_analysis_tab`` function and its
section builders. Each section builder appends its widgets to the
shared ``inner`` container and is self-contained.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox

from katrain.core.lang import i18n
from katrain.gui.features.settings_popup_helpers import _add_searchable_label
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button, Label

if TYPE_CHECKING:
    from kivy.uix.boxlayout import BoxLayout as BoxLayoutType

    from katrain.gui.features.settings_popup_state import _SettingsPopupContext


def _build_engine_section(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Add the KataGo engine selection row (Phase 171: fixed display).

    Phase 171 で Leela を廃止したため、KataGo 固定の表示に整理。
    ``selected_engine`` は呼び出し側の初期化互換のため残しているが、
    値は常に ``"katago"`` が入る。
    """
    from katrain.core.analysis import EngineType  # Phase 34

    _add_searchable_label(inner, "mykatrain:settings:analysis_engine", state)

    engine_label = Label(
        text=i18n._("mykatrain:settings:engine_katago"),
        size_hint_x=0.4,  # Flexible width for i18n (Issue 16)
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    engine_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    engine_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(3))
    engine_layout.add_widget(Label(size_hint_x=None, width=dp(30)))  # spacer (no checkbox needed)
    engine_layout.add_widget(engine_label)
    inner.add_widget(engine_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:analysis_engine", engine_layout)
    # Phase 171: KataGo 固定（後方互換のため EngineType は参照だけ残す）
    _ = EngineType.KATAGO


def _build_disable_katago_section(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Add the 'Disable KataGo' checkbox row (Phase 3 Extension)."""
    _add_searchable_label(inner, "mykatrain:settings:disable_katago", state)

    disable_katago_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8))
    disable_katago_checkbox = CheckBox(
        active=state.selected_disable_katago[0],
        size_hint_x=None,
        width=dp(30),
    )
    disable_katago_checkbox.bind(active=lambda chk, active: state.selected_disable_katago.__setitem__(0, active))
    disable_katago_layout.add_widget(disable_katago_checkbox)
    disable_katago_layout.add_widget(Label())  # Spacer
    inner.add_widget(disable_katago_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:disable_katago", disable_katago_layout)


def _build_skill_preset_section(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Add the skill preset radio button group."""
    _add_searchable_label(inner, "mykatrain:settings:skill_preset", state)

    skill_options = [
        ("auto", i18n._("mykatrain:settings:skill_auto")),
        ("relaxed", i18n._("mykatrain:settings:skill_relaxed")),
        ("beginner", i18n._("mykatrain:settings:skill_beginner")),
        ("standard", i18n._("mykatrain:settings:skill_standard")),
        ("advanced", i18n._("mykatrain:settings:skill_advanced")),
        ("pro", i18n._("mykatrain:settings:skill_pro")),
    ]

    skill_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(3))
    for skill_value, skill_label_text in skill_options:
        checkbox = CheckBox(
            group="skill_preset_setting",
            active=(skill_value == state.selected_skill_preset[0]),
            size_hint_x=None,
            width=dp(30),
        )
        checkbox.bind(
            active=lambda chk, active, val=skill_value: (
                state.selected_skill_preset.__setitem__(0, val) if active else None
            )
        )
        label = Label(
            text=skill_label_text,
            size_hint_x=None,
            width=dp(60),
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        skill_layout.add_widget(checkbox)
        skill_layout.add_widget(label)
    inner.add_widget(skill_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:skill_preset", skill_layout)


def _build_pv_filter_section(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Add the PV filter level radio button group."""
    _add_searchable_label(inner, "mykatrain:settings:pv_filter_level", state)

    pv_filter_options = [
        ("auto", i18n._("mykatrain:settings:pv_filter_auto")),
        ("off", i18n._("mykatrain:settings:pv_filter_off")),
        ("weak", i18n._("mykatrain:settings:pv_filter_weak")),
        ("medium", i18n._("mykatrain:settings:pv_filter_medium")),
        ("strong", i18n._("mykatrain:settings:pv_filter_strong")),
    ]

    pv_filter_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(3))
    for pv_value, pv_label_text in pv_filter_options:
        checkbox = CheckBox(
            group="pv_filter_setting",
            active=(pv_value == state.selected_pv_filter[0]),
            size_hint_x=None,
            width=dp(30),
        )
        checkbox.bind(
            active=lambda chk, active, val=pv_value: state.selected_pv_filter.__setitem__(0, val) if active else None
        )
        label = Label(
            text=pv_label_text,
            size_hint_x=None,
            width=dp(70),
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        pv_filter_layout.add_widget(checkbox)
        pv_filter_layout.add_widget(label)
    inner.add_widget(pv_filter_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:pv_filter_level", pv_filter_layout)


def _build_beginner_hints_section(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Add the Beginner Hints toggle row (Phase 91) + summary category rows (Phase 179)."""
    _add_searchable_label(inner, "mykatrain:settings:beginner_hints", state)

    beginner_hints_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8))
    beginner_hints_checkbox = CheckBox(
        active=state.selected_beginner_hints[0],
        size_hint_x=None,
        width=dp(30),
    )
    beginner_hints_checkbox.bind(active=lambda chk, active: state.selected_beginner_hints.__setitem__(0, active))
    beginner_hints_desc = Label(
        text=i18n._("mykatrain:settings:beginner_hints_desc"),
        size_hint_x=0.9,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    beginner_hints_desc.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    beginner_hints_layout.add_widget(beginner_hints_checkbox)
    beginner_hints_layout.add_widget(beginner_hints_desc)
    inner.add_widget(beginner_hints_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:beginner_hints", beginner_hints_layout)

    # Phase 179: per-category summary toggles. Indented by adding a spacer
    # label on the left so the visual hierarchy is clear.
    _build_summary_hints_subtoggles(inner, state)


def _build_summary_hints_subtoggles(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Phase 179 + 182 + 186: 7 per-category-group toggles under the master switch."""
    summary_rows = [
        (
            "mykatrain:settings:summary_mistake",
            "selected_summary_mistake",
            state.selected_summary_mistake,
        ),
        (
            "mykatrain:settings:summary_freedom",
            "selected_summary_freedom",
            state.selected_summary_freedom,
        ),
        (
            "mykatrain:settings:summary_difficulty",
            "selected_summary_difficulty",
            state.selected_summary_difficulty,
        ),
        (
            "mykatrain:settings:katago_uncertain",
            "selected_katago_uncertain",
            state.selected_katago_uncertain,
        ),
        (
            "mykatrain:settings:summary_ownership",
            "selected_summary_ownership",
            state.selected_summary_ownership,
        ),
        (
            "mykatrain:settings:summary_policy",
            "selected_summary_policy",
            state.selected_summary_policy,
        ),
        (
            "mykatrain:settings:curator_hint",
            "selected_curator_hint",
            state.selected_curator_hint,
        ),
    ]
    for label_key, _field_name, selected_ref in summary_rows:
        _add_searchable_label(inner, label_key, state)
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(32), spacing=dp(8))
        spacer = Label(size_hint_x=None, width=dp(20))  # indent under master
        row.add_widget(spacer)
        checkbox = CheckBox(
            active=selected_ref[0],
            size_hint_x=None,
            width=dp(30),
        )
        checkbox.bind(active=lambda chk, active, ref=selected_ref: ref.__setitem__(0, active))
        row.add_widget(checkbox)
        desc = Label(
            text=i18n._(f"{label_key}_desc"),
            size_hint_x=0.9,
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        desc.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        row.add_widget(desc)
        inner.add_widget(row)
        if state.register_searchable is not None:
            state.register_searchable(label_key, row)


def _build_reset_button() -> Button:
    """Build the Analysis tab reset button."""
    return Button(
        text=i18n._("mykatrain:settings:reset"),
        size_hint_y=None,
        height=dp(36),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )


def _build_analysis_tab(state: _SettingsPopupContext) -> tuple[BoxLayout, Button]:
    """Build the Analysis tab content (Tab 1).

    Phase 175: Extracted from ``do_mykatrain_settings_popup`` and split
    into per-section builders.

    Args:
        state: Shared mutable state. Mutates selected_engine,
            selected_disable_katago, selected_skill_preset, selected_pv_filter,
            selected_beginner_hints via checkbox callbacks.

    Returns:
        (inner_layout, reset_button): ``inner_layout`` is a BoxLayout ready
        to be wrapped in a ScrollView and added to a TabbedPanelItem. The
        reset button should be bound by the orchestrator to
        ``_reset_tab_settings(ctx, "analysis", popup, reopen_popup)``.
    """
    inner = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None)
    inner.bind(minimum_height=inner.setter("height"))

    _build_engine_section(inner, state)
    _build_disable_katago_section(inner, state)
    _build_skill_preset_section(inner, state)
    _build_pv_filter_section(inner, state)
    _build_beginner_hints_section(inner, state)

    reset_btn = _build_reset_button()
    inner.add_widget(reset_btn)

    return inner, reset_btn
