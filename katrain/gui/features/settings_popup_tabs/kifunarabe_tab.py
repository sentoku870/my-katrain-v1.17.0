"""Kifunarabe tab (Tab 3) for the myKatrain settings popup.

Holds:
- Directory configuration used when the user picks "棋譜並べ" from the
  menu. It is intentionally separate from ``general/sgf_load`` so the
  user can keep their own games folder and a pro-game folder
  independent.
- Three display toggles (digits / actual border / uniform colour) for
  the choice markers on the board. All three default to "minimal" so
  the choice set looks like a clean multiple-choice puzzle.
- Phase 179-A: history directory + "Clear history" button.
- Phase 179-D: critical-only threshold (5 options + off).

Phase 177: Initial implementation.
Phase 177-E: Added digit/colour/border toggles.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

from katrain.core.constants import (
    KIFUNARABE_AUTO_TOGGLE_MARKERS_DEFAULT,
    KIFUNARABE_AUTO_TOGGLE_MARKERS_KEY,
    KIFUNARABE_HISTORY_DIR_DEFAULT,
    KIFUNARABE_SHOW_ACTUAL_BORDER_DEFAULT,
    KIFUNARABE_SHOW_ACTUAL_BORDER_KEY,
    KIFUNARABE_SHOW_DIGITS_DEFAULT,
    KIFUNARABE_SHOW_DIGITS_KEY,
    KIFUNARABE_UNIFORM_COLOR_DEFAULT,
    KIFUNARABE_UNIFORM_COLOR_KEY,
)
from katrain.core.lang import i18n
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button
from katrain.gui.widgets.helpers import create_text_input_row

# Phase 179-D: labels match the i18n keys for the setup-popup critical_only
# spinner. The first label is "off" (== default). The rest mirror
# ``VALID_CRITICAL_THRESHOLDS`` minus the leading 0.0 entry.
_CRITICAL_THRESHOLD_LABELS: list[str] = [
    "kifunarabe:setup:critical_off",
    "kifunarabe:setup:critical_0_5",
    "kifunarabe:setup:critical_1_0",
    "kifunarabe:setup:critical_2_0",
    "kifunarabe:setup:critical_5_0",
]

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

    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(10))
    checkbox = CheckBox(active=current_value, size_hint_x=None, width=dp(30))
    label = Label(
        text=i18n._(i18n_label_key),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    row.add_widget(checkbox)
    row.add_widget(label)
    inner.add_widget(row)
    if state.register_searchable is not None:
        state.register_searchable(searchable_label, row)
    return checkbox


def _build_help_section(inner: BoxLayout, state: Any) -> None:
    """Add a short explanation block at the bottom."""
    inner.add_widget(
        Label(
            text=i18n._("mykatrain:settings:kifunarabe_help"),
            size_hint_y=None,
            height=dp(80),
            halign="left",
            valign="top",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
    )


def _build_kifunarabe_tab(state: Any) -> tuple[BoxLayout, dict[str, Any]]:
    """Build the Kifunarabe tab content (Tab 3).

    Returns:
        (inner_layout, widget_refs): ``widget_refs`` carries
        ``sgf_load_input``, ``sgf_load_browse``, ``show_digits_cb``,
        ``show_actual_border_cb``, ``uniform_color_cb``,
        ``history_dir_input``, ``history_dir_browse``, ``clear_history_btn``,
        ``critical_only_spinner`` so the orchestrator can wire
        save_settings and the folder browser.
    """
    inner = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None)
    inner.bind(minimum_height=inner.setter("height"))

    sgf_load_input, sgf_load_browse = _build_sgf_load_row(inner, state)

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

    # Phase 179-A: history directory + clear button.
    history_dir_input, history_dir_browse = _build_history_dir_row(inner, state)
    clear_history_btn = _build_clear_history_button(inner, state)

    # Phase 179-D: critical-only threshold spinner (off + 4 thresholds).
    critical_only_spinner = _build_critical_only_spinner(inner, state)

    _build_help_section(inner, state)

    widget_refs = {
        "sgf_load_input": sgf_load_input,
        "sgf_load_browse": sgf_load_browse,
        "show_digits_cb": show_digits_cb,
        "show_actual_border_cb": show_actual_border_cb,
        "uniform_color_cb": uniform_color_cb,
        "auto_toggle_cb": auto_toggle_cb,
        "history_dir_input": history_dir_input,
        "history_dir_browse": history_dir_browse,
        "clear_history_btn": clear_history_btn,
        "critical_only_spinner": critical_only_spinner,
    }
    return inner, widget_refs


# Phase 179-A: history directory row + clear button.
def _build_history_dir_row(inner: Any, state: Any) -> tuple[TextInput, Button]:
    """Phase 179-A: FolderPath input for the kifunarabe history directory.

    Defaults to ``~/.katrain/kifunarabe_history/`` when the stored value
    is empty.
    """
    current = ""
    if state.ctx is not None:
        kif_section = state.ctx.config("kifunarabe") or {}
        if isinstance(kif_section, dict):
            current = kif_section.get("history_dir", KIFUNARABE_HISTORY_DIR_DEFAULT) or ""

    row, input_widget, browse_button = create_text_input_row(
        label_text=i18n._("mykatrain:settings:kifunarabe_history_dir"),
        initial_value=current or "",
        with_browse=True,
    )
    inner.add_widget(row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:kifunarabe_history_dir", row)
    assert browse_button is not None  # with_browse=True guarantees this
    return input_widget, browse_button


def _build_clear_history_button(inner: Any, state: Any) -> Button:
    """Phase 179-A: clear-history button.

    Calls :func:`katrain.core.study.kifunarabe.clear_all_history` directly
    so the user can wipe the directory without having to save settings
    first. The actual deletion is logged to ``ctx.log`` at level 1.
    """
    btn = Button(
        text=i18n._("mykatrain:settings:clear_kifunarabe_history"),
        size_hint_y=None,
        height=dp(36),
        font_name=Theme.DEFAULT_FONT,
    )

    def _on_release(_b: Button) -> None:
        from katrain.core.study.kifunarabe import clear_all_history

        ctx = state.ctx
        if ctx is None:
            return
        count = clear_all_history(katrain=ctx)
        with contextlib.suppress(Exception):
            ctx.log(f"kifunarabe: cleared {count} history files", level=1)

    btn.bind(on_release=_on_release)
    inner.add_widget(btn)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:clear_kifunarabe_history", btn)
    return btn


# Phase 179-D: critical-only threshold spinner.
def _build_critical_only_spinner(inner: Any, state: Any) -> Any:
    """Phase 179-D: default-threshold spinner shown in the kifunarabe tab.

    Selection index maps to ``VALID_CRITICAL_THRESHOLDS`` (see
    ``katrain.core.study.kifunarabe``). Index 0 == off (default). The
    spinner shares the styling used by the setup popup.
    """
    from katrain.core.study.kifunarabe import VALID_CRITICAL_THRESHOLDS
    from katrain.gui.popups._base import LabelledSpinner

    default_index = 0
    if state.ctx is not None:
        kif_section = state.ctx.config("kifunarabe") or {}
        if isinstance(kif_section, dict):
            stored = kif_section.get("critical_only_threshold", 0.0)
            try:
                default_index = list(VALID_CRITICAL_THRESHOLDS).index(float(stored))
            except (ValueError, TypeError):
                default_index = 0

    spinner = LabelledSpinner(
        input_property="critical_only",
        value_refs=_CRITICAL_THRESHOLD_LABELS,
        selected_index=default_index,
    )
    inner.add_widget(spinner)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:kifunarabe_critical_only_threshold", spinner)
    return spinner
