"""Analysis tab (Tab 1) for the myKatrain settings popup.

Phase 175: Extracted from settings_popup.py into a dedicated submodule.
Split into per-section builders (Phase 165-b pattern) for readability.

This module holds ONLY the ``_build_analysis_tab`` function and its
section builders. Each section builder appends its widgets to the
shared ``inner`` container and is self-contained.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    Phase 230-B で Leela 検証用の disable_katago チェックボックスを削除。
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
    engine_layout.add_widget(engine_label)
    inner.add_widget(engine_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:analysis_engine", engine_layout)
    # Phase 171: KataGo 固定（後方互換のため EngineType は参照だけ残す）
    _ = EngineType.KATAGO


def _build_player_rank_section(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Add the player_rank text input + auto-derived preset label (Phase 229).

    Before Phase 229 this section was a 6-way radio button group
    (``auto`` / ``relaxed`` / ``beginner`` / ``standard`` / ``advanced``
    / ``pro``).  The replacement is a single text field for the user's
    rank; the analysis-side preset is derived from it via
    :func:`katrain.core.analysis.resolve_skill_preset` and shown as a
    label below the input.
    """
    _add_searchable_label(inner, "mykatrain:settings:player_rank", state)

    rank_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8))

    # Kivy imports — kept local to avoid pulling them at module import
    # time (mirrors the pattern used elsewhere in this module).
    from kivy.uix.textinput import TextInput

    rank_input = TextInput(
        text=state.selected_player_rank[0],
        multiline=False,
        size_hint_x=0.4,
        hint_text=i18n._("mykatrain:settings:player_rank_example"),
        font_name=Theme.DEFAULT_FONT,
        foreground_color=Theme.TEXT_COLOR,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
    )

    def _on_rank_text(instance: TextInput, value: str) -> None:
        # Phase 229: persist user input and refresh the derived preset
        # label.  We resolve via the same helper the analysis code uses,
        # so the UI can never disagree with the runtime preset.
        from katrain.core.analysis import resolve_skill_preset

        new_value = value.strip()
        state.selected_player_rank[0] = new_value
        state.selected_skill_preset[0] = resolve_skill_preset(
            state.ctx.config("general/skill_preset"),
            new_value,
        )
        # Update the inferred label without rebuilding the layout.
        if hasattr(state, "_rank_inferred_label"):
            state._rank_inferred_label.text = _format_rank_inferred_label(new_value, state.selected_skill_preset[0])
        # Phase 246-A (H2): also refresh the PV filter status because
        # AUTO mode depends on the resolved preset, which itself depends
        # on the rank string.
        _refresh_pv_filter_status(state)

    rank_input.bind(text=_on_rank_text)
    rank_layout.add_widget(rank_input)

    # Spacer so the inferred label has room to render next to the input.
    rank_layout.add_widget(Label(size_hint_x=0.6))

    inner.add_widget(rank_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:player_rank", rank_layout)

    # Inferred preset label (Phase 229): shows what the runtime will use.
    inferred_label = Label(
        text=_format_rank_inferred_label(
            state.selected_player_rank[0],
            state.selected_skill_preset[0],
        ),
        size_hint_y=None,
        height=dp(24),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size="13sp",
    )
    inferred_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    # Phase 229: stash the label on state so the text callback above
    # can refresh it without rebuilding the layout (avoids focus loss).
    state._rank_inferred_label = inferred_label
    inner.add_widget(inferred_label)

    # Phase 230-E: usage help. ``player_rank`` now also serves as the
    # LLM Coach fallback (Phase 229-D fallback chain), so make that
    # explicit in the UI rather than hiding a second rank field in the
    # export tab (which caused user confusion).
    usage_label = Label(
        text=i18n._("mykatrain:settings:player_rank_usage"),
        size_hint_y=None,
        height=dp(36),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size="12sp",
    )
    usage_label.bind(width=lambda lbl, w: setattr(lbl, "text_size", (w, None)))
    usage_label.bind(texture_size=lambda lbl, tex_size: setattr(lbl, "height", tex_size[1]))
    inner.add_widget(usage_label)


def _format_rank_inferred_label(rank_str: str, resolved_preset: str) -> str:
    """Render the "現在: standard (5d より自動推定)" string for the analysis tab."""
    from katrain.core.analysis import SKILL_PRESET_LABELS

    preset_label = SKILL_PRESET_LABELS.get(resolved_preset, resolved_preset)
    if rank_str:
        return i18n._("mykatrain:settings:player_rank_inferred").format(rank=rank_str, preset=preset_label)
    return i18n._("mykatrain:settings:player_rank_default").format(preset=preset_label)


def _build_pv_filter_section(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Add the PV filter level radio button group (Phase 246-A).

    Phase 246-A refresh:
    - (M8) 5-option row uses size_hint_x proportional layout so labels
      do not get truncated on narrow windows / i18n variants.
    - (H2) Adds a status label below the row that shows the *effective*
      level (resolving AUTO via ``player_rank``) and the candidate cap.
      The label re-renders when the user changes the radio selection or
      the rank input, giving a live preview of what the filter will do.
    """
    _add_searchable_label(inner, "mykatrain:settings:pv_filter_level", state)

    pv_filter_options = [
        ("auto", i18n._("mykatrain:settings:pv_filter_auto")),
        ("off", i18n._("mykatrain:settings:pv_filter_off")),
        ("weak", i18n._("mykatrain:settings:pv_filter_weak")),
        ("medium", i18n._("mykatrain:settings:pv_filter_medium")),
        ("strong", i18n._("mykatrain:settings:pv_filter_strong")),
    ]

    # Phase 246-A (M8): each option is one cell that takes 1/N of the
    # available width. Within the cell, the CheckBox is ~30% and the
    # Label takes the rest, so a long i18n string can wrap rather than
    # overflow. The previous fixed-width ``dp(70)`` layout overflowed
    # on 768px windows with JP locale.
    n_options = len(pv_filter_options)
    cell_hint = 1.0 / n_options
    pv_filter_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(3))
    for pv_value, pv_label_text in pv_filter_options:
        cell = BoxLayout(orientation="horizontal", size_hint_x=cell_hint, spacing=dp(2))
        checkbox = CheckBox(
            group="pv_filter_setting",
            active=(pv_value == state.selected_pv_filter[0]),
            size_hint_x=0.3,
        )
        # Each cell needs its own handler so the closure captures the
        # correct ``pv_value`` (Phase 226-B 対策: explicit handler factory).
        def _on_pv_active(_chk: Any, active: bool, val: str = pv_value) -> None:  # noqa: B008
            if active:
                state.selected_pv_filter[0] = val
                _refresh_pv_filter_status(state)

        checkbox.bind(active=_on_pv_active)
        cell.add_widget(checkbox)
        cell.add_widget(
            Label(
                text=pv_label_text,
                size_hint_x=0.7,
                halign="left",
                valign="middle",
                color=Theme.TEXT_COLOR,
                font_name=Theme.DEFAULT_FONT,
                shorten=True,
            )
        )
        pv_filter_layout.add_widget(cell)
    inner.add_widget(pv_filter_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:pv_filter_level", pv_filter_layout)

    # Phase 246-A (H2): effective-level status label below the radio row.
    # Stored on state so the rank-input callback can refresh it in place.
    status_label = Label(
        text=_format_pv_filter_status(state.selected_pv_filter[0], state.selected_player_rank[0]),
        size_hint_y=None,
        height=dp(24),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size="12sp",
    )
    status_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    state._pv_filter_status_label = status_label
    inner.add_widget(status_label)

    # Phase 246-B (M4): a small legend explaining the marker colour /
    # size / border semantics so users can decode the on-board hints
    # without opening external docs. Kept short to fit the popup width.
    legend_label = Label(
        text=i18n._("mykatrain:settings:pv_filter_marker_legend"),
        size_hint_y=None,
        height=dp(60),
        halign="left",
        valign="top",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size="11sp",
    )
    legend_label.bind(width=lambda lbl, w: setattr(lbl, "text_size", (w, None)))
    legend_label.bind(texture_size=lambda lbl, tex_size: setattr(lbl, "height", tex_size[1]))
    inner.add_widget(legend_label)

    # Phase 246-D (H4): kifunarabe-mode bypass note. Pinned here so
    # users aren't confused when their STRONG filter "stops working"
    # mid-puzzle. The runtime bypass is in ``prepare_hint_moves``;
    # this label is the user-facing explanation.
    kifu_note = Label(
        text=i18n._("mykatrain:settings:pv_filter_kifunarabe_note"),
        size_hint_y=None,
        height=dp(32),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size="11sp",
    )
    kifu_note.bind(width=lambda lbl, w: setattr(lbl, "text_size", (w, None)))
    kifu_note.bind(texture_size=lambda lbl, tex_size: setattr(lbl, "height", tex_size[1]))
    inner.add_widget(kifu_note)


def _format_pv_filter_status(pv_filter_level: str, player_rank: str) -> str:
    """Render the "現在: MEDIUM (最大 8 件)" string for the PV filter row.

    Phase 246-A: lives next to ``_format_rank_inferred_label`` so the
    analysis tab can show two parallel status lines (preset + filter).
    Kept as a free function so unit tests can call it without spinning
    up a popup.
    """
    from katrain.core.analysis import (
        SKILL_PRESET_LABELS,
        get_effective_pv_filter_info,
    )

    info = get_effective_pv_filter_info(pv_filter_level, player_rank)
    if info.effective_level == "off":
        return i18n._("mykatrain:settings:pv_filter_status_off")
    level_label = i18n._(f"mykatrain:settings:pv_filter_{info.effective_level}")
    if info.is_auto:
        preset_label = SKILL_PRESET_LABELS.get(info.resolved_preset or "", info.resolved_preset or "")
        return i18n._("mykatrain:settings:pv_filter_status_auto").format(
            level=level_label,
            preset=preset_label,
            max_n=info.max_candidates,
        )
    return i18n._("mykatrain:settings:pv_filter_status_explicit").format(
        level=level_label,
        max_n=info.max_candidates,
    )


def _refresh_pv_filter_status(state: _SettingsPopupContext) -> None:
    """Re-render the PV filter status label from the current state values.

    Phase 246-A: pulled out of ``_build_pv_filter_section`` so the
    player-rank text callback can reuse it. The label reference is
    stashed on ``state._pv_filter_status_label`` by the section builder.
    """
    label = getattr(state, "_pv_filter_status_label", None)
    if label is None:
        return
    label.text = _format_pv_filter_status(
        state.selected_pv_filter[0],
        state.selected_player_rank[0],
    )


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

    Phase 230-B: Leela 残滓 (disable_katago checkbox) を削除。

    Args:
        state: Shared mutable state. Mutates selected_engine,
            selected_skill_preset, selected_pv_filter,
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
    _build_player_rank_section(inner, state)
    _build_pv_filter_section(inner, state)
    _build_beginner_hints_section(inner, state)

    reset_btn = _build_reset_button()
    inner.add_widget(reset_btn)

    return inner, reset_btn
