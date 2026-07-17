# katrain/gui/features/settings_popup.py
#
# 設定ポップアップ機能モジュール（オーケストレーター）
#
# Phase 175: タブビルダーは settings_popup_tabs/ パッケージへ、
# _save_* ヘルパーは settings_popup_savers.py へ分離済み。
# Phase 173: I/O ヘルパー（export / import）は settings_popup_io.py へ、
# リセットアクションは settings_popup_reset.py へ分離。
# 本モジュールは popup オーケストレーターのみを保持する。
#
# 公開API: do_mykatrain_settings_popup, _SettingsPopupContext

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.textinput import TextInput

from katrain.core import analysis
from katrain.core.constants import STATUS_INFO
from katrain.core.lang import i18n
from katrain.gui.features.settings_popup_io import (  # noqa: F401 (re-export for backward compat)
    _do_export_settings,
    _do_import_settings,
)
from katrain.gui.features.settings_popup_reset import (  # noqa: F401 (re-export for backward compat)
    _reset_tab_settings,
)
from katrain.gui.features.settings_popup_savers import (  # noqa: F401 (re-export for backward compat)
    _save_beginner_hints_settings,
    _save_engine_settings,
    _save_general_settings,
    _save_mykatrain_settings,
    migrate_default_user_rank,
)
from katrain.gui.features.settings_popup_state import _SettingsPopupContext
from katrain.gui.popups import I18NPopup
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button, Popup

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


# =============================================================================
# Phase 175: tab builders now live in settings_popup_tabs/ package.
# They are imported lazily inside do_mykatrain_settings_popup() to keep
# Kivy initialization deferred (required by tests/test_import_resolution.py).
# =============================================================================

__all__ = ["do_mykatrain_settings_popup", "_SettingsPopupContext"]


def do_mykatrain_settings_popup(
    ctx: FeatureContext,
    initial_tab: str | None = None,  # Phase 87.5: "analysis", "export"; "leela" は Phase 171 で削除
) -> None:
    """myKatrain設定ポップアップを表示

    Phase 145-D+: Refactored from a 809-line closure into a thin orchestrator
    that delegates tab content generation to ``_build_analysis_tab`` and
    ``_build_export_tab``. Shared mutable state is passed via
    ``_SettingsPopupContext``.

    Phase 171: Leela タブを削除し、KataGo 専用（Tab 1 / Tab 2）に整理。
    Phase 175: タブビルダーを settings_popup_tabs/ パッケージへ分離。

    Args:
        ctx: FeatureContext providing config, save_config, controls
        initial_tab: Optional tab to select on open ("analysis", "export")
    """
    from katrain.core.analysis import get_analysis_engine

    current_settings = ctx.config("mykatrain_settings") or {}
    engine_config = ctx.config("engine") or {}
    current_engine = get_analysis_engine(engine_config)

    # Phase 230-E: Migrate legacy ``mykatrain_settings.default_user_rank``
    # into ``general.player_rank`` so a single field drives both analysis
    # thresholds and the LLM Coach fallback chain (Phase 229-D).
    migrate_default_user_rank(ctx, current_settings)

    # Phase 145-D+: Initialize shared state container
    state = _SettingsPopupContext(
        ctx=ctx,
        current_settings=current_settings,
        engine_config=engine_config,
        current_engine=current_engine,
        selected_engine=[current_engine],
        selected_skill_preset=[
            analysis.resolve_skill_preset(
                ctx.config("general/skill_preset"),
                ctx.config("general/player_rank"),
            )
        ],
        # Phase 229: player_rank is the new primary input.  We still
        # honour an explicit preset override stored in
        # ``general/skill_preset`` (Phase 229-D does the same), but the
        # UI no longer exposes the preset radio buttons.
        selected_player_rank=[ctx.config("general/player_rank") or ""],
        selected_pv_filter=[ctx.config("general/pv_filter_level") or analysis.DEFAULT_PV_FILTER_LEVEL],
        selected_beginner_hints=[ctx.config("beginner_hints/enabled", False)],
        selected_summary_mistake=[ctx.config("beginner_hints/summary_mistake", True)],
        selected_summary_freedom=[ctx.config("beginner_hints/summary_freedom", True)],
        selected_summary_difficulty=[ctx.config("beginner_hints/summary_difficulty", True)],
        selected_katago_uncertain=[ctx.config("beginner_hints/katago_uncertain", True)],
        selected_summary_ownership=[ctx.config("beginner_hints/summary_ownership", True)],
        selected_summary_policy=[ctx.config("beginner_hints/summary_policy", True)],
        selected_curator_hint=[ctx.config("beginner_hints/curator_hint", True)],
        selected_format=[current_settings.get("karte_format", "both")],
        selected_opp_info=[current_settings.get("opponent_info_mode", "auto")],
        # Phase 248-B1: important-moves level surfaced to the analysis
        # tab. Falls back to "normal" so users with pre-248 configs
        # (or empty string) get the historical behaviour.
        selected_important_moves_level=[
            (current_settings.get("important_moves_level") or "normal")
        ],
    )

    def register_searchable(label_text: str, *widgets: Any) -> None:
        """検索対象としてウィジェットを登録"""
        for widget in widgets:
            state.searchable_widgets.append({"label_text": label_text, "widget": widget})

    def reopen_popup() -> None:
        """ポップアップをリロードして再表示"""
        from kivy.clock import Clock

        Clock.schedule_once(lambda dt: do_mykatrain_settings_popup(ctx), 0.1)

    state.register_searchable = register_searchable
    state.reopen_popup = reopen_popup

    # --- Build search bar ---
    search_layout, search_input = _build_search_bar(state.searchable_widgets, register_searchable)

    # --- Build 4 tabs (Phase 171: Leela タブ削除; Phase 175: tab builders split into package;
    #                 Phase 177: Kifunarabe タブ追加; Phase 230-D: Diagnostics タブ追加) ---
    from katrain.gui.features.settings_popup_tabs import (
        _build_analysis_tab,
        _build_diagnostics_tab,
        _build_export_tab,
        _build_kifunarabe_tab,
    )

    tab1_inner, tab1_reset_btn = _build_analysis_tab(state)
    tab2_inner, tab2_reset_btn, export_widgets = _build_export_tab(state)
    tab3_inner, kif_widgets = _build_kifunarabe_tab(state)
    tab4_inner = _build_diagnostics_tab(state)
    widget_refs = {**export_widgets, **kif_widgets}

    tab1 = TabbedPanelItem(text=i18n._("mykatrain:settings:tab_analysis"))
    tab1_scroll = ScrollView(do_scroll_x=False)
    tab1_scroll.add_widget(tab1_inner)
    tab1.add_widget(tab1_scroll)

    tab2 = TabbedPanelItem(text=i18n._("mykatrain:settings:tab_export"))
    tab2_scroll = ScrollView(do_scroll_x=False)
    tab2_scroll.add_widget(tab2_inner)
    tab2.add_widget(tab2_scroll)

    tab3 = TabbedPanelItem(text=i18n._("mykatrain:settings:tab_kifunarabe"))
    tab3_scroll = ScrollView(do_scroll_x=False)
    tab3_scroll.add_widget(tab3_inner)
    tab3.add_widget(tab3_scroll)

    tab4 = TabbedPanelItem(text=i18n._("mykatrain:settings:tab_diagnostics"))
    tab4.add_widget(tab4_inner)

    tabbed_panel = TabbedPanel(
        do_default_tab=False,
        tab_width=dp(120),
        tab_height=dp(40),
        size_hint_y=0.9,
    )
    tabbed_panel.add_widget(tab1)
    tabbed_panel.add_widget(tab2)
    tabbed_panel.add_widget(tab3)
    tabbed_panel.add_widget(tab4)

    # Phase 87.5 + Phase 89: Tab lookup dictionary (Phase 171: "leela" 削除;
    #                         Phase 177: "kifunarabe" 追加; Phase 230-D: "diagnostics" 追加)
    tab_by_id = {
        "analysis": tab1,
        "export": tab2,
        "kifunarabe": tab3,
        "diagnostics": tab4,
    }

    # Phase 87.5 + Phase 89: Switch to initial_tab if specified
    from kivy.clock import Clock

    if initial_tab and initial_tab in tab_by_id:
        target_tab = tab_by_id[initial_tab]
        Clock.schedule_once(lambda dt: tabbed_panel.switch_to(target_tab), 0.1)

    tabbed_panel.default_tab = tab1

    def _set_tab_fonts(dt: float) -> None:
        """Apply Japanese-capable font to tab headers (tofu fix)."""
        for tab in tabbed_panel.tab_list:
            if hasattr(tab, "font_name"):
                tab.font_name = Theme.DEFAULT_FONT
            if hasattr(tab, "_label") and tab._label:
                tab._label.font_name = Theme.DEFAULT_FONT

    Clock.schedule_once(_set_tab_fonts, 0)

    # --- Build button row ---
    buttons_layout, export_button, import_button, save_button, cancel_button = _build_button_row()

    # --- Assemble main layout ---
    main_layout = BoxLayout(orientation="vertical", spacing=dp(8))
    main_layout.add_widget(search_layout)
    main_layout.add_widget(tabbed_panel)
    main_layout.add_widget(buttons_layout)

    popup = I18NPopup(
        title_key="mykatrain:settings",
        # Phase 180-C: enlarged from dp(700) -> dp(850) so the kifunarabe
        # tab (which now includes the saved-history list section) fits
        # without truncating the help text. The kifunarabe tab also wraps
        # its inner BoxLayout in a ScrollView as a safety net for future
        # additions.
        size=[dp(900), dp(850)],
        content=main_layout,
    ).__self__
    state.popup = popup

    # --- Save callback (Phase 145-D: 6-line orchestrator delegating to helpers;
    #                    Phase 177: kifunarabe.sgf_load 永続化) ---
    def save_settings(*_args: Any) -> None:
        """Save all settings sections (Phase 171: Leela セクション削除)。"""
        _save_general_settings(
            ctx,
            state.selected_skill_preset[0],
            state.selected_pv_filter[0],
            state.selected_player_rank[0],
        )
        _save_beginner_hints_settings(
            ctx,
            state.selected_beginner_hints[0],
            summary_mistake=state.selected_summary_mistake[0],
            summary_freedom=state.selected_summary_freedom[0],
            summary_difficulty=state.selected_summary_difficulty[0],
            katago_uncertain=state.selected_katago_uncertain[0],
            summary_ownership=state.selected_summary_ownership[0],
            summary_policy=state.selected_summary_policy[0],
            curator_hint=state.selected_curator_hint[0],
        )
        new_engine_value = state.selected_engine[0]
        _save_engine_settings(ctx, new_engine_value)
        _save_mykatrain_settings(
            ctx,
            widget_refs["user_input"].text,
            widget_refs["output_input"].text,
            widget_refs["input_input"].text,
            state.selected_format[0],
            state.selected_opp_info[0],
            # Phase 230-E: the export tab no longer exposes a rank input.
            # Pass empty string so the saver clears any legacy
            # ``default_user_rank`` value (migration already folded it
            # into ``general/player_rank`` on popup open).
            "",
            # Phase 248-B1: important-moves level from the analysis tab.
            important_moves_level=state.selected_important_moves_level[0],
        )
        # Phase 177: persist kifunarabe-specific SGF browse folder
        # Phase 177-E: persist the three display toggles.
        # Phase 177-H: persist the auto-toggle-markers preference.
        with contextlib.suppress(Exception):
            kif = dict(ctx.config("kifunarabe", {}) or {})
            kif["sgf_load"] = widget_refs["sgf_load_input"].text
            kif["show_digits"] = bool(widget_refs["show_digits_cb"].active)
            kif["show_actual_border"] = bool(widget_refs["show_actual_border_cb"].active)
            kif["uniform_color"] = bool(widget_refs["uniform_color_cb"].active)
            kif["auto_toggle_markers"] = bool(widget_refs["auto_toggle_cb"].active)
            ctx.set_config_section("kifunarabe", kif)
            ctx.save_config("kifunarabe")
        # Phase 177-F: if kifunarabe is active, the user just toggled
        # ``show_digits`` / ``show_actual_border`` / ``uniform_color`` in
        # this same popup. Redraw the board immediately so the new value
        # is reflected without requiring the user to restart the session.
        with contextlib.suppress(Exception):
            controller = getattr(ctx, "_kifunarabe_controller", None)
            if controller is not None and controller.is_active():
                from kivy.clock import Clock

                # Schedule a redraw on the main thread: the candidate-marker
                # cache lives on ``widget.canvas`` so all we need is an
                # ``ask_update()`` to flush fresh config values on the next
                # frame.
                def _redraw_board_gui(_dt: float) -> None:
                    board_gui = getattr(ctx, "board_gui", None)
                    if board_gui is not None:
                        with contextlib.suppress(Exception):
                            board_gui.canvas.ask_update()

                Clock.schedule_once(_redraw_board_gui, 0)
        ctx.controls.set_status(i18n._("Settings saved"), STATUS_INFO)
        popup.dismiss()

    # --- Browse callbacks (Phase 145-D: delegated to _open_browse_dialog) ---
    def browse_output(*_args: Any) -> None:
        _open_browse_dialog(
            ctx=ctx,
            title="Select folder - Navigate into target folder, then click 'Select This Folder'",
            initial_path=widget_refs["output_input"].text,
            target_text_input=widget_refs["output_input"],
            dirselect=True,
        )

    def browse_input(*_args: Any) -> None:
        _open_browse_dialog(
            ctx=ctx,
            title="Select folder - Navigate into target folder, then click 'Select This Folder'",
            initial_path=widget_refs["input_input"].text,
            target_text_input=widget_refs["input_input"],
            dirselect=True,
        )

    # Phase 177: kifunarabe folder browse
    def browse_kifunarabe(*_args: Any) -> None:
        _open_browse_dialog(
            ctx=ctx,
            title="Select folder - Navigate into target folder, then click 'Select This Folder'",
            initial_path=widget_refs["sgf_load_input"].text,
            target_text_input=widget_refs["sgf_load_input"],
            dirselect=True,
        )

    save_button.bind(on_release=save_settings)
    cancel_button.bind(on_release=lambda *_args: popup.dismiss())
    widget_refs["output_browse"].bind(on_release=browse_output)
    widget_refs["input_browse"].bind(on_release=browse_input)
    widget_refs["sgf_load_browse"].bind(on_release=browse_kifunarabe)

    export_button.bind(on_release=lambda *_args: _do_export_settings(ctx, popup))
    import_button.bind(on_release=lambda *_args: _do_import_settings(ctx, popup, reopen_popup))

    tab1_reset_btn.bind(on_release=lambda *_args: _reset_tab_settings(ctx, "analysis", popup, reopen_popup))
    tab2_reset_btn.bind(on_release=lambda *_args: _reset_tab_settings(ctx, "export", popup, reopen_popup))

    popup.open()


# =============================================================================
# Phase 145-D: Extracted helpers from do_mykatrain_settings_popup
# =============================================================================


def _build_search_bar(
    searchable_widgets: list[dict[str, Any]],
    register_searchable: Callable[[str, Any], None],
) -> tuple[BoxLayout, TextInput]:
    """Build the search bar (text input + clear button) and wire search callbacks.

    Args:
        searchable_widgets: Mutable list that the on_text callback will iterate
            over to filter visible widgets.
        register_searchable: Closure to register a widget as searchable.

    Returns:
        (search_layout, search_input) tuple. The layout is ready to be added to
        a parent; search_input is returned so the caller can clear its text.
    """

    def on_search_text_change(instance: Any, value: str) -> None:
        """検索テキスト変更時のフィルタ処理"""
        query = value.strip().lower()
        for item in searchable_widgets:
            label_text = item.get("label_text", "").lower()
            widget = item.get("widget")
            if widget is None:
                continue
            if query and query not in label_text:
                widget.opacity = 0.3
            else:
                widget.opacity = 1.0

    search_layout = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(40))
    search_input = TextInput(
        hint_text=i18n._("mykatrain:settings:search_placeholder"),
        multiline=False,
        size_hint_x=0.85,
        height=dp(40),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        foreground_color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    search_clear_btn = Button(
        text=i18n._("mykatrain:settings:search_clear"),
        size_hint_x=0.15,
        height=dp(40),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    search_layout.add_widget(search_input)
    search_layout.add_widget(search_clear_btn)

    def on_search_clear(*_args: Any) -> None:
        """検索をクリア"""
        search_input.text = ""

    search_input.bind(text=on_search_text_change)
    search_clear_btn.bind(on_release=on_search_clear)

    return search_layout, search_input


def _build_button_row() -> tuple[BoxLayout, Button, Button, Button, Button]:
    """Build the bottom button row (Export / Import / Save / Cancel).

    Returns:
        (buttons_layout, export_button, import_button, save_button, cancel_button)
    """
    buttons_layout = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48))
    export_button = Button(
        text=i18n._("mykatrain:settings:export"),
        size_hint_x=0.25,
        height=dp(48),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    import_button = Button(
        text=i18n._("mykatrain:settings:import"),
        size_hint_x=0.25,
        height=dp(48),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    save_button = Button(
        text=i18n._("Save"),
        size_hint_x=0.25,
        height=dp(48),
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    cancel_button = Button(
        text=i18n._("button:cancel"),
        size_hint_x=0.25,
        height=dp(48),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    buttons_layout.add_widget(export_button)
    buttons_layout.add_widget(import_button)
    buttons_layout.add_widget(save_button)
    buttons_layout.add_widget(cancel_button)
    return buttons_layout, export_button, import_button, save_button, cancel_button


def _open_browse_dialog(
    ctx: FeatureContext,
    title: str,
    initial_path: str,
    target_text_input: Any,
    dirselect: bool = True,
    file_filter: list[str] | None = None,
    select_string: str = "Select This Folder",
) -> None:
    """Open a file/directory browse dialog and update the target text input on selection.

    Phase 145-D: Unified the nearly-identical browse_output / browse_input
    callbacks into a single helper. Phase 171 で ``browse_leela_exe`` 経路は
    Leela 廃止に伴い削除されたため、現在は output / input の 2 用途。

    Args:
        ctx: FeatureContext (kept for API symmetry; not used directly).
        title: Popup title text.
        initial_path: Current value of the target text input (used to seed
            the dialog's initial directory if it exists).
        target_text_input: The TextInput whose text will be updated on selection.
        dirselect: True to select a directory, False to select a file.
        file_filter: Optional list of file filters (e.g. ["*.exe"]) for file mode.
        select_string: Label of the "select" button in the dialog.
    """
    from katrain.gui.popups import LoadSGFPopup

    browse_popup_content = LoadSGFPopup(ctx)
    browse_popup_content.filesel.dirselect = dirselect
    browse_popup_content.filesel.select_string = select_string
    if file_filter:
        browse_popup_content.filesel.filters = file_filter
    # Seed initial path: directory mode requires a directory; file mode requires
    # an existing file (in which case we open its parent directory).
    if initial_path:
        abs_path = os.path.abspath(initial_path)
        if dirselect and os.path.isdir(abs_path):
            browse_popup_content.filesel.path = abs_path
        elif not dirselect and os.path.isfile(abs_path):
            browse_popup_content.filesel.path = os.path.dirname(abs_path)

    browse_popup = Popup(
        title=title,
        title_font=Theme.DEFAULT_FONT,
        size_hint=(0.8, 0.8),
        content=browse_popup_content,
    ).__self__

    def on_select(*_args: Any) -> None:
        selected = browse_popup_content.filesel.file_text.text
        if selected and (dirselect and os.path.isdir(selected) or not dirselect and os.path.isfile(selected)):
            target_text_input.text = selected
        browse_popup.dismiss()

    browse_popup_content.filesel.bind(on_success=on_select)
    browse_popup.open()
