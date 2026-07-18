"""Analysis tab (Tab 1) for the myKatrain settings popup.

Phase 175: Extracted from settings_popup.py into a dedicated submodule.
Split into per-section builders (Phase 165-b pattern) for readability.

This module holds ONLY the ``_build_analysis_tab`` function and its
section builders. Each section builder appends its widgets to the
shared ``inner`` container and is self-contained.
"""

from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING, Any

from kivy.metrics import dp, sp
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

    # Phase 247-B (H3): position-aware preview label below the static
    # status. Shows "現在の局面: 12 → 5 (best 1件込み)" using the
    # latest ``widget.last_pv_filter_preview`` value. Refreshed when
    # the filter or rank changes (via ``_refresh_pv_filter_status``).
    preview_label = Label(
        text=_format_pv_filter_preview_line(state),
        size_hint_y=None,
        height=dp(24),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size="12sp",
    )
    preview_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    state._pv_filter_preview_label = preview_label
    inner.add_widget(preview_label)

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

    Phase 247-B (H3): also refreshes the position-aware preview label
    that shows the N → M count for the current node.
    """
    label = getattr(state, "_pv_filter_status_label", None)
    if label is not None:
        label.text = _format_pv_filter_status(
            state.selected_pv_filter[0],
            state.selected_player_rank[0],
        )
    preview_label = getattr(state, "_pv_filter_preview_label", None)
    if preview_label is not None:
        preview_label.text = _format_pv_filter_preview_line(state)


def _format_pv_filter_preview_line(state: _SettingsPopupContext) -> str:
    """Render the position-aware N → M line for the current node (H3).

    The preview count is stashed on the board widget by
    :func:`prepare_hint_moves`. We read it via the badukpan widget
    to avoid coupling the popup to the renderer.

    Returns the i18n-localized string:
    - "(未解析)" — node has no analysis yet
    - "現在の局面: 12 → 5 (best 1件込み, フィルタ ON)" — filter active
    - "現在の局面: 12 件 (フィルタ OFF)" — filter inactive (OFF level or
      kifunarabe bypass)
    """
    # Lazy import to avoid pulling Kivy at module load time.
    from katrain.core.lang import i18n as _i18n

    board = getattr(state.ctx, "controls", None)
    board_widget = getattr(board, "board_widget", None) if board else None
    preview = getattr(board_widget, "last_pv_filter_preview", None) if board_widget else None
    if preview is None or preview.raw_count == 0:
        return _i18n._("mykatrain:settings:pv_filter_preview_no_analysis")
    if not preview.config_active:
        return _i18n._("mykatrain:settings:pv_filter_preview_inactive").format(n=preview.raw_count)
    return _i18n._("mykatrain:settings:pv_filter_preview_active").format(
        n=preview.raw_count,
        m=preview.filtered_count,
        best=preview.best_count,
    )


def _build_important_moves_level_section(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Phase 248-B1: radio button group for ``important_moves_level``.

    Three options aligned with :data:`IMPORTANT_MOVE_SETTINGS_BY_LEVEL`:
    - ``easy``:    threshold 1.0, max 10 moves (kyu-level)
    - ``normal``:  threshold 0.5, max 20 moves (default, Phase 50 baseline)
    - ``strict``:  threshold 0.3, max 40 moves (dan-level)

    The selected value flows into ``build_karte_json_string(level=...)``
    via :data:`state.selected_important_moves_level`, so it affects
    both ``important_moves`` and ``critical_3`` sections of the Karte
    output.

    Layout mirrors the PV filter section (Phase 246-A): 3 equal-width
    cells, each with CheckBox + Label.
    """
    _add_searchable_label(inner, "mykatrain:settings:important_moves_level", state)

    important_moves_options = [
        ("easy", i18n._("mykatrain:settings:important_moves_level_easy")),
        ("normal", i18n._("mykatrain:settings:important_moves_level_normal")),
        ("strict", i18n._("mykatrain:settings:important_moves_level_strict")),
    ]

    # Mirror the PV filter section (Phase 246-A M8): equal-width cells
    # so a long i18n string can wrap rather than overflow.
    n_options = len(important_moves_options)
    cell_hint = 1.0 / n_options
    level_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(3))
    for level_value, level_label_text in important_moves_options:
        cell = BoxLayout(orientation="horizontal", size_hint_x=cell_hint, spacing=dp(2))
        checkbox = CheckBox(
            group="important_moves_level_setting",
            active=(level_value == state.selected_important_moves_level[0]),
            size_hint_x=0.3,
        )

        # Each cell needs its own handler so the closure captures the
        # correct ``level_value`` (mirrors _build_pv_filter_section).
        def _on_level_active(
            _chk: Any,
            active: bool,
            val: str = level_value,  # noqa: B008
        ) -> None:
            if active:
                state.selected_important_moves_level[0] = val

        checkbox.bind(active=_on_level_active)
        cell.add_widget(checkbox)
        cell.add_widget(
            Label(
                text=level_label_text,
                size_hint_x=0.7,
                halign="left",
                valign="middle",
                color=Theme.TEXT_COLOR,
                font_name=Theme.DEFAULT_FONT,
                shorten=True,
            )
        )
        level_layout.add_widget(cell)
    inner.add_widget(level_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:important_moves_level", level_layout)


def _build_critical_3_max_moves_section(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Phase 248-B2: spinner for the critical_3 selection count per player.

    Users can pick 1-10 (default 3). The selected value flows into
    :func:`critical_3_section_for` via
    :data:`state.selected_critical_3_max_moves`. Out-of-range values
    (typos, negative numbers) are normalised to 3 in the saver.

    Layout: label + Spinner next to the "重要度レベル" radio group.
    """
    _add_searchable_label(inner, "mykatrain:settings:critical_3_max_moves", state)

    # Local imports to keep the module import-time Kivy footprint small.
    from kivy.uix.spinner import Spinner

    max_moves_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8))
    spinner = Spinner(
        text=str(state.selected_critical_3_max_moves[0]),
        values=[str(i) for i in range(1, 11)],
        size_hint_x=0.3,
        font_name=Theme.DEFAULT_FONT,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )

    def _on_spinner_select(_sp: Any, value: str) -> None:
        try:
            state.selected_critical_3_max_moves[0] = int(value)
        except (TypeError, ValueError):
            state.selected_critical_3_max_moves[0] = 3

    spinner.bind(text=_on_spinner_select)
    max_moves_row.add_widget(spinner)
    max_moves_row.add_widget(Label(size_hint_x=0.7))
    inner.add_widget(max_moves_row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:critical_3_max_moves", max_moves_row)


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
    """Phase 179 + 182 + 186: 7 per-category-group toggles under the master switch.

    Phase 251: extended to also expose the 10 individual category
    toggles (4 structural + 6 meaning-tag) so users can suppress a
    single category (e.g. turn off ``CUT_RISK`` while keeping
    ``SELF_ATARI``).
    """
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
        _add_toggle_row(inner, label_key, selected_ref, state)

    # Phase 266: live status line below the curator_hint toggle. Tells
    # the user whether a Curator profile is currently loaded and how
    # many weak tags it tracks. Without this, users would have to dig
    # through logs to confirm their curator_ranking.json was picked up.
    _build_curator_status_label(inner, state)

    # Phase 251: per-category toggles for the 4 structural detectors
    # (Phase 91) and 6 meaning-tag fallbacks (Phase 92). These
    # previously had no individual control; users could only flip the
    # master ``beginner_hints/enabled`` switch.
    individual_rows = [
        # Structural (Phase 91)
        ("mykatrain:settings:self_atari", state.selected_self_atari),
        ("mykatrain:settings:ignore_atari", state.selected_ignore_atari),
        ("mykatrain:settings:missed_capture", state.selected_missed_capture),
        ("mykatrain:settings:cut_risk", state.selected_cut_risk),
        # Meaning-tag (Phase 92)
        ("mykatrain:settings:low_liberties", state.selected_low_liberties),
        ("mykatrain:settings:self_capture_like", state.selected_self_capture_like),
        ("mykatrain:settings:bad_shape", state.selected_bad_shape),
        ("mykatrain:settings:heavy_group", state.selected_heavy_group),
        ("mykatrain:settings:missed_defense", state.selected_missed_defense),
        ("mykatrain:settings:urgent_vs_big", state.selected_urgent_vs_big),
    ]
    for label_key, selected_ref in individual_rows:
        _add_toggle_row(inner, label_key, selected_ref, state)


def _build_curator_status_label(inner: BoxLayoutType, state: _SettingsPopupContext) -> None:
    """Phase 266: live Curator profile status line.

    Rendered right below the ``curator_hint`` checkbox. Tells the user
    whether a profile is currently loaded and how many weak tags it
    carries. Without this, users would have to dig through logs to
    confirm their curator_ranking.json was picked up after Batch
    analysis.

    Phase 267: when no profile is loaded, gives a concrete recovery
    hint pointing at the two settings that decide where the loader
    looks (``karte_output_directory`` and ``batch_options.output_dir``).

    Phase 268: adds a "参照..." button that lets the user pick a
    curator_ranking_*.json file via a file browser — escape hatch
    when the auto-detect heuristics miss.
    """
    from katrain.core.lang import i18n
    from katrain.gui.widgets.factory import Button as _Button

    curator_profile = getattr(state.ctx, "curator_profile", None)
    n_tags = len(curator_profile.weak_tags) if curator_profile is not None else 0
    if curator_profile is not None and n_tags > 0:
        text = i18n._("mykatrain:settings:curator_hint_loaded").format(count=n_tags)
    else:
        # Check both candidate directories to give the user a
        # specific recovery hint.
        settings = state.ctx.config("mykatrain_settings") or {}
        karte_dir = settings.get("karte_output_directory") or ""
        batch_options = settings.get("batch_options") or {}
        batch_dir = batch_options.get("output_dir") or ""
        if karte_dir or batch_dir:
            text = i18n._("mykatrain:settings:curator_hint_not_loaded_with_dirs").format(
                karte_dir=karte_dir or "—", batch_dir=batch_dir or "—"
            )
        else:
            text = i18n._("mykatrain:settings:curator_hint_not_loaded")

    # Status row (text + browse button) for Phase 268.
    from kivy.uix.boxlayout import BoxLayout as _BoxLayout

    status_row = _BoxLayout(orientation="horizontal", size_hint_x=0.97, spacing=dp(6))
    desc = Label(
        text=text,
        size_hint_x=0.78,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=sp(11),
    )
    desc.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    status_row.add_widget(desc)

    browse_btn = _Button(
        text=i18n._("mykatrain:settings:curator_hint_browse"),
        size_hint_x=0.22,
        font_name=Theme.DEFAULT_FONT,
    )

    # Phase 268: file browser for curator_ranking_*.json. We use the
    # same FileBrowser widget the rest of the GUI uses, with a JSON
    # filter. On selection, call back into ``KaTrainGui.update_curator_profile``
    # with a path override.
    def _on_browse(_btn: Any) -> None:
        from katrain.gui.widgets.filebrowser import I18NFileBrowser

        # Phase 268: ``I18NFileBrowser`` accepts ``path=`` (not
        # ``initialdir=``) and ``filters=`` for the JSON filter. There
        # is no ``select_directory=`` kwarg — that key is silently
        # dropped by Kivy's property layer, which is why an earlier
        # version of this helper did not actually open in the
        # expected directory.
        initial = karte_dir or batch_dir or os.path.expanduser("~")
        if not os.path.isdir(initial):
            initial = os.path.expanduser("~")
        browser = I18NFileBrowser(
            path=initial,
            filters=["*.json", "*.JSON"],
            select_string=i18n._("button:ok"),
        )
        browser.bind(
            on_success=lambda inst, _touch: _load_curator_from_path(
                state.ctx, inst.selection[0] if inst.selection else None
            ),
            on_submit=lambda inst, selection, _touch: _load_curator_from_path(
                state.ctx, selection[0] if selection else None
            ),
        )
        browser.open()

    browse_btn.bind(on_release=_on_browse)
    status_row.add_widget(browse_btn)
    inner.add_widget(status_row)


def _load_curator_from_path(ctx: Any, path: str | None) -> None:
    """Phase 268: load a curator_ranking_*.json file picked by the user.

    Bypasses the auto-detect heuristics entirely; useful when the
    user keeps curator files in a non-standard location.
    """
    from katrain.core.curator.profile import load_curator_profile

    if not path or not os.path.isfile(path):
        return
    try:
        profile = load_curator_profile(path)
    except Exception as e:  # noqa: BLE001
        with contextlib.suppress(Exception):
            ctx.log(f"Curator manual load failed ({path}): {e}")
        ctx.curator_profile = None
        return
    if profile is not None:
        ctx.curator_profile = profile
        with contextlib.suppress(Exception):
            n = len(profile.weak_tags or {})
            ctx.log(
                f"Curator profile (manual): {path} ({n} weak tag(s))",
            )
    else:
        ctx.curator_profile = None
    # Trigger a re-render of the comment panel so the footer updates.
    with contextlib.suppress(Exception):
        ctx.update_state()


def _add_toggle_row(
    inner: BoxLayoutType,
    label_key: str,
    selected_ref: list[bool],
    state: _SettingsPopupContext,
) -> None:
    """Add a single ``[checkbox] [description]`` toggle row (Phase 251 helper).

    Consolidates the per-row layout code that was previously inline in
    :func:`_build_summary_hints_subtoggles` so the 7 group toggles and
    10 individual toggles share the same Kivy hierarchy.
    """
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
    _build_important_moves_level_section(inner, state)
    _build_critical_3_max_moves_section(inner, state)
    _build_beginner_hints_section(inner, state)

    reset_btn = _build_reset_button()
    inner.add_widget(reset_btn)

    return inner, reset_btn
