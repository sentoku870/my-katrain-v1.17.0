"""Kifunarabe tab (Tab 3) for the myKatrain settings popup.

Holds:
- Directory configuration used when the user picks "棋譜並べ" from the
  menu. It is intentionally separate from ``general/sgf_load`` so the
  user can keep their own games folder and a pro-game folder
  independent.
- Phase 290 candidate-pool controls (Spinner + threshold) so the
  choice set can be tuned between "KataGo top-N" and "actual-hand
  alternatives of similar quality".
- Three display toggles (digits / actual border / uniform colour) for
  the choice markers on the board. All three default to "minimal" so
  the choice set looks like a clean multiple-choice puzzle.

Phase 177: Initial implementation.
Phase 177-E: Added digit/colour/border toggles.
Phase 271-A: Removed the "history directory" row (Phase 249-β) and
  the "auto-export directory" row (Phase 249-γ). The default folders
  (``~/.katrain/kifunarabe_history`` and
  ``~/.katrain/kifunarabe_weaknesses``) are still used internally via
  the existing ``kifunarabe/history_dir`` /
  ``kifunarabe/auto_export_dir`` config keys; only the settings-UI
  rows were removed (the user requested them as "noisy" entries).
Phase 290: Added candidate-pool Spinner + near-threshold numeric
  input. The core layer exposes the same knobs via kwargs; this tab
  is the GUI entry point.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

from katrain.core.lang import i18n
from katrain.core.study.kifunarabe_constants import (
    KIFUNARABE_AUTO_EXPORT_WEAKNESSES_DEFAULT,
    KIFUNARABE_AUTO_EXPORT_WEAKNESSES_KEY,
    KIFUNARABE_AUTO_TOGGLE_MARKERS_DEFAULT,
    KIFUNARABE_AUTO_TOGGLE_MARKERS_KEY,
    KIFUNARABE_CANDIDATE_POOL_DEFAULT,
    KIFUNARABE_CANDIDATE_POOL_KEY,
    KIFUNARABE_CANDIDATE_POOL_NEAR_ACTUAL,
    KIFUNARABE_CANDIDATE_POOL_TOP_KATA,
    KIFUNARABE_NEAR_THRESHOLD_DEFAULT,
    KIFUNARABE_NEAR_THRESHOLD_KEY,
    KIFUNARABE_SHOW_ACTUAL_BORDER_DEFAULT,
    KIFUNARABE_SHOW_ACTUAL_BORDER_KEY,
    KIFUNARABE_SHOW_DIGITS_DEFAULT,
    KIFUNARABE_SHOW_DIGITS_KEY,
    KIFUNARABE_UNIFORM_COLOR_DEFAULT,
    KIFUNARABE_UNIFORM_COLOR_KEY,
    VALID_CANDIDATE_POOLS,
)
from katrain.gui.popups._base import LabelledFloatInput, LabelledSpinner
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button
from katrain.gui.widgets.helpers import create_text_input_row

if TYPE_CHECKING:
    pass


def _build_sgf_load_row(inner: Any, state: Any) -> tuple[TextInput, Button]:
    """Add the kifunarabe SGF browse folder row.

    Returns:
        (input, browse_button) so the orchestrator can wire up the
        folder-browser dialog.
    """
    # Read the current value from the ``kifunarabe`` config section; the
    # settings UI state object doesn't carry it, so resolve directly via state.ctx.
    current = ""
    if state.ctx is not None:
        kif_section = state.ctx.config("kifunarabe") or {}
        current = kif_section.get("sgf_load", "") if isinstance(kif_section, dict) else ""

    row, input_widget, browse_button = create_text_input_row(
        label_text=i18n._("mykatrain:settings:kifunarabe_sgf_load"),
        initial_value=current or "",
        with_browse=True,
    )
    inner.add_widget(row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:kifunarabe_sgf_load", row)
    assert browse_button is not None  # with_browse=True guarantees this
    return input_widget, browse_button


def _build_display_checkbox(
    inner: Any,
    state: Any,
    *,
    config_key: str,
    default: bool,
    i18n_label_key: str,
    searchable_label: str,
) -> CheckBox:
    """Add one labelled checkbox row for a kifunarabe display toggle.

    Args:
        inner: Container BoxLayout the row gets appended to.
        state: Shared popup state (provides ``register_searchable``).
        config_key: The ``kifunarabe/*`` config key whose value drives the box.
        default: Default value if the key is unset.
        i18n_label_key: ``i18n._`` key for the human-readable label.
        searchable_label: Substring used by the settings search bar.

    Returns:
        The created ``CheckBox`` instance so callers can read its state
        on save.
    """
    current_value = default
    if state.ctx is not None:
        kif_section = state.ctx.config("kifunarabe") or {}
        if isinstance(kif_section, dict):
            current_value = bool(kif_section.get(config_key, default))

    # Phase 230-C: Row height grows to fit wrapped label text.
    # Previously a fixed ``dp(36)`` height clipped the longest label
    # (``kifunarabe_auto_toggle_markers`` = 32 JP chars) to 1 line.
    # Bind ``text_size`` height to ``None`` so Kivy wraps vertically,
    # then propagate the resulting ``texture_size[1]`` to the row height
    # (clamped to a one-line minimum of ``dp(36)``).
    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(10))
    checkbox = CheckBox(active=current_value, size_hint_x=None, width=dp(30))
    label = Label(
        text=i18n._(i18n_label_key),
        size_hint_x=0.9,
        size_hint_y=None,
        height=dp(36),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    # Width drives wrapping; height stays unconstrained so 2-line labels
    # grow the label (and the row below). Use a non-tuple statement lambda
    # so mypy doesn't complain about setattr's None return in a tuple.
    label.bind(width=lambda lbl, w: setattr(lbl, "text_size", (w, None)))

    def _on_texture_size(lbl: Label, tex_size: tuple[int, int]) -> None:
        lbl.height = tex_size[1]
        row.height = max(dp(36), tex_size[1])

    label.bind(texture_size=_on_texture_size)
    row.add_widget(checkbox)
    row.add_widget(label)
    inner.add_widget(row)
    if state.register_searchable is not None:
        state.register_searchable(searchable_label, row)
    return checkbox


def _build_candidate_pool_row(inner: BoxLayout, state: Any) -> LabelledSpinner:
    """Phase 290: add the candidate-pool Spinner row.

    The Spinner emits the raw key (e.g. ``"top_kata"`` /
    ``"near_actual"``) via ``input_property`` and ``input_value``. We
    carry the configured value into ``selected_index`` so the saved
    config round-trips through the popup.
    """
    current_value: Any = KIFUNARABE_CANDIDATE_POOL_DEFAULT
    if state.ctx is not None:
        kif_section = state.ctx.config("kifunarabe") or {}
        if isinstance(kif_section, dict):
            stored = kif_section.get(KIFUNARABE_CANDIDATE_POOL_KEY, KIFUNARABE_CANDIDATE_POOL_DEFAULT)
            if stored in VALID_CANDIDATE_POOLS:
                current_value = stored

    value_refs = [
        "mykatrain:settings:kifunarabe_pool_top_kata",
        "mykatrain:settings:kifunarabe_pool_near_actual",
    ]
    # Map back from i18n labels to canonical keys so the spinner's
    # ``selected_index`` stays meaningful even when the labels are
    # localised out-of-order. The order here matches the canonical list
    # in ``VALID_CANDIDATE_POOLS`` (see ``kifunarabe_constants.py``).
    key_order = [KIFUNARABE_CANDIDATE_POOL_TOP_KATA, KIFUNARABE_CANDIDATE_POOL_NEAR_ACTUAL]
    try:
        selected_index = key_order.index(current_value)
    except ValueError:
        selected_index = key_order.index(KIFUNARABE_CANDIDATE_POOL_DEFAULT)

    spinner = LabelledSpinner(
        input_property=KIFUNARABE_CANDIDATE_POOL_KEY,
        value_refs=value_refs,
        selected_index=selected_index,
    )

    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    label = Label(
        text=i18n._("mykatrain:settings:kifunarabe_candidate_pool"),
        size_hint_x=0.5,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    label.bind(width=lambda lbl, w: setattr(lbl, "text_size", (w, None)))
    spinner.size_hint_x = 0.5
    row.add_widget(label)
    row.add_widget(spinner)
    inner.add_widget(row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:kifunarabe_candidate_pool", row)
    return spinner


def _build_near_threshold_row(inner: BoxLayout, state: Any) -> LabelledFloatInput:
    """Phase 290: add the near-threshold numeric input row.

    Floats are clamped to the safe operating range (the core layer
    would clamp again, but giving the user immediate feedback is
    friendlier).
    """
    current_value = KIFUNARABE_NEAR_THRESHOLD_DEFAULT
    if state.ctx is not None:
        kif_section = state.ctx.config("kifunarabe") or {}
        if isinstance(kif_section, dict):
            stored = kif_section.get(KIFUNARABE_NEAR_THRESHOLD_KEY, KIFUNARABE_NEAR_THRESHOLD_DEFAULT)
            try:
                current_value = float(stored)
            except (TypeError, ValueError):
                current_value = KIFUNARABE_NEAR_THRESHOLD_DEFAULT

    text_input = LabelledFloatInput(
        input_property=KIFUNARABE_NEAR_THRESHOLD_KEY,
        text=f"{current_value:g}",
    )

    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    label = Label(
        text=i18n._("mykatrain:settings:kifunarabe_near_threshold"),
        size_hint_x=0.6,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    label.bind(width=lambda lbl, w: setattr(lbl, "text_size", (w, None)))
    text_input.size_hint_x = 0.4
    row.add_widget(label)
    row.add_widget(text_input)
    inner.add_widget(row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:kifunarabe_near_threshold", row)
    return text_input


def _build_help_section(inner: BoxLayout, state: Any) -> None:
    """Add a short explanation block at the bottom.

    Phase 230-C: セクション全体が見えるよう、Label を内容に合わせて
    自動リサイズ（以前は固定 ``dp(80)`` で 4 段落が途切れていた）。
    """
    help_label = Label(
        text=i18n._("mykatrain:settings:kifunarabe_help"),
        size_hint_y=None,
        height=dp(80),
        halign="left",
        valign="top",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    help_label.bind(width=lambda lbl, w: setattr(lbl, "text_size", (w, None)))
    help_label.bind(texture_size=lambda lbl, tex_size: setattr(lbl, "height", tex_size[1]))
    inner.add_widget(help_label)


def _build_kifunarabe_tab(state: Any) -> tuple[BoxLayout, dict[str, Any]]:
    """Build the Kifunarabe tab content (Tab 3).

    Returns:
        (inner_layout, widget_refs): ``widget_refs`` carries
        ``sgf_load_input``, ``sgf_load_browse``, ``show_digits_cb``,
        ``show_actual_border_cb``, ``uniform_color_cb``, ``auto_toggle_cb``,
        ``auto_export_cb``, ``candidate_pool_spinner`` and
        ``near_threshold_input`` so the orchestrator can wire
        save_settings and the folder browser.
    """
    inner = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None)
    inner.bind(minimum_height=inner.setter("height"))

    sgf_load_input, sgf_load_browse = _build_sgf_load_row(inner, state)

    # Phase 290: candidate pool controls come before the per-marker
    # toggles so the choice-mode is the first thing the user sees
    # after the SGF load row.
    candidate_pool_spinner = _build_candidate_pool_row(inner, state)
    near_threshold_input = _build_near_threshold_row(inner, state)

    show_digits_cb = _build_display_checkbox(
        inner,
        state,
        config_key=KIFUNARABE_SHOW_DIGITS_KEY,
        default=KIFUNARABE_SHOW_DIGITS_DEFAULT,
        i18n_label_key="mykatrain:settings:kifunarabe_show_digits",
        searchable_label="mykatrain:settings:kifunarabe_show_digits",
    )
    show_actual_border_cb = _build_display_checkbox(
        inner,
        state,
        config_key=KIFUNARABE_SHOW_ACTUAL_BORDER_KEY,
        default=KIFUNARABE_SHOW_ACTUAL_BORDER_DEFAULT,
        i18n_label_key="mykatrain:settings:kifunarabe_show_actual_border",
        searchable_label="mykatrain:settings:kifunarabe_show_actual_border",
    )
    uniform_color_cb = _build_display_checkbox(
        inner,
        state,
        config_key=KIFUNARABE_UNIFORM_COLOR_KEY,
        default=KIFUNARABE_UNIFORM_COLOR_DEFAULT,
        i18n_label_key="mykatrain:settings:kifunarabe_uniform_color",
        searchable_label="mykatrain:settings:kifunarabe_uniform_color",
    )
    auto_toggle_cb = _build_display_checkbox(
        inner,
        state,
        config_key=KIFUNARABE_AUTO_TOGGLE_MARKERS_KEY,
        default=KIFUNARABE_AUTO_TOGGLE_MARKERS_DEFAULT,
        i18n_label_key="mykatrain:settings:kifunarabe_auto_toggle_markers",
        searchable_label="mykatrain:settings:kifunarabe_auto_toggle_markers",
    )
    auto_export_cb = _build_display_checkbox(
        inner,
        state,
        config_key=KIFUNARABE_AUTO_EXPORT_WEAKNESSES_KEY,
        default=KIFUNARABE_AUTO_EXPORT_WEAKNESSES_DEFAULT,
        i18n_label_key="mykatrain:settings:kifunarabe_auto_export_weaknesses",
        searchable_label="mykatrain:settings:kifunarabe_auto_export_weaknesses",
    )

    _build_help_section(inner, state)

    widget_refs = {
        "sgf_load_input": sgf_load_input,
        "sgf_load_browse": sgf_load_browse,
        "candidate_pool_spinner": candidate_pool_spinner,
        "near_threshold_input": near_threshold_input,
        "show_digits_cb": show_digits_cb,
        "show_actual_border_cb": show_actual_border_cb,
        "uniform_color_cb": uniform_color_cb,
        "auto_toggle_cb": auto_toggle_cb,
        "auto_export_cb": auto_export_cb,
    }
    # Phase 287-B: the orchestrator in settings_popup.py already wraps
    # every tab (analysis / export / kifunarabe / diagnostics) in a
    # ScrollView at lines 174-186. Returning a nested ScrollView here
    # caused:
    #   - two scrollbars stacked at the right edge,
    #   - mouse-wheel events captured by the wrong layer,
    #   - ambiguous touch-scroll ownership on trackpads.
    # Return the inner BoxLayout directly so the layout matches the
    # other tabs and the single outer ScrollView owns scrolling.
    return inner, widget_refs
