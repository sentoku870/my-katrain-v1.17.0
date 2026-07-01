# katrain/gui/features/settings_popup.py
#
# 設定ポップアップ機能モジュール
#
# __main__.py から抽出した設定関連の関数を配置します。
# - do_mykatrain_settings_popup: myKatrain設定ポップアップの表示
# - _reset_tab_settings: タブ別設定リセット (Phase 27)

from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.textinput import TextInput

from katrain.common.settings_export import (
    EXCLUDED_SECTIONS,
    TAB_RESET_KEYS,
    atomic_save_config,
    create_backup_path,
    export_settings,
    get_default_value,
    parse_exported_settings,
)
from katrain.common.typed_config import LeelaConfig
from katrain.core import eval_metrics
from katrain.core.constants import (
    STATUS_ERROR,
    STATUS_INFO,
)
from katrain.core.lang import i18n
from katrain.core.leela.logic import clamp_k
from katrain.gui.popups import I18NPopup
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button, Label, Popup
from katrain.gui.widgets.helpers import create_text_input_row

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def _reset_tab_settings(
    ctx: FeatureContext,
    tab_id: str,
    popup: Popup,
    on_reset_complete: Callable[[], None],
) -> None:
    """タブの設定をデフォルトに戻す (Phase 27)

    Args:
        ctx: FeatureContext providing config, save_config, controls
        tab_id: タブID ("analysis", "export", "leela")
        popup: 親ポップアップ（リセット後に閉じてリロード用）
        on_reset_complete: リセット完了後に呼ばれるコールバック
    """
    from katrain.gui.popups import I18NPopup

    keys = TAB_RESET_KEYS.get(tab_id, [])
    if not keys:
        return

    # リセット対象のキー名を表示用に整形
    target_names = [key for _, key in keys]
    tab_display_name = i18n._(f"mykatrain:settings:tab_{tab_id}")

    # 確認ダイアログ
    confirm_layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
    message_label = Label(
        text=i18n._("mykatrain:settings:reset_confirm_message").format(
            tab=tab_display_name, targets=", ".join(target_names)
        ),
        halign="center",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    message_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width * 0.9, None)))
    confirm_layout.add_widget(message_label)

    buttons_layout = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(40))
    confirm_btn = Button(
        text=i18n._("OK"),
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    cancel_btn = Button(
        text=i18n._("Cancel"),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    buttons_layout.add_widget(confirm_btn)
    buttons_layout.add_widget(cancel_btn)
    confirm_layout.add_widget(buttons_layout)

    confirm_popup = I18NPopup(
        title_key="mykatrain:settings:reset_confirm_title",
        size=[dp(450), dp(200)],
        content=confirm_layout,
    ).__self__

    def do_reset(*_args: Any) -> None:
        """実際のリセット処理"""
        affected_sections: set[str] = set()

        for section, key in keys:
            default_val = get_default_value(section, key)
            if default_val is not None:
                # config section を取得または作成
                section_config = ctx.config(section) or {}
                section_config[key] = default_val
                ctx.set_config_section(section, section_config)
                affected_sections.add(section)

        # 影響セクションのみ保存
        for section in affected_sections:
            ctx.save_config(section)

        ctx.controls.set_status(
            i18n._("mykatrain:settings:reset_success").format(tab=tab_display_name),
            STATUS_INFO,
        )
        confirm_popup.dismiss()

        # 設定ポップアップをリロード
        popup.dismiss()
        on_reset_complete()

    confirm_btn.bind(on_release=do_reset)
    cancel_btn.bind(on_release=lambda *_args: confirm_popup.dismiss())
    confirm_popup.open()


def _do_export_settings(
    ctx: FeatureContext,
    popup: Popup,
) -> None:
    """設定をJSONファイルにエクスポート (Phase 27)

    Opens a file save dialog and exports current settings to a JSON file.
    Uses the export_settings function from settings_export module.

    Args:
        ctx: FeatureContext providing config, controls
        popup: 親ポップアップ（エクスポート後も開いたまま）
    """
    from tkinter import Tk, filedialog

    # Create hidden Tk root for file dialog
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        file_path = filedialog.asksaveasfilename(
            title=i18n._("mykatrain:settings:export"),
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="katrain_settings.json",
        )
    finally:
        root.destroy()

    if not file_path:
        return  # User cancelled

    try:
        # Get current config and app version
        config_dict = dict(ctx._config)  # type: ignore[attr-defined]
        app_version = ctx.config("general", {}).get("version", "unknown")

        # Export to JSON string
        json_str = export_settings(config_dict, app_version)

        # Write to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_str)

        ctx.controls.set_status(
            i18n._("mykatrain:settings:export_success").format(path=file_path),
            STATUS_INFO,
        )
    except OSError as e:
        # File write failure: permission denied, disk full, invalid path
        logging.warning(f"Settings export failed to {file_path}: {e}", exc_info=True)
        ctx.controls.set_status(f"Export failed: {e}", STATUS_ERROR)
    except Exception as e:
        # Boundary fallback: unexpected error during settings export
        logging.error(f"Unexpected error exporting settings to {file_path}: {e}", exc_info=True)
        ctx.controls.set_status(f"Export failed: {e}", STATUS_ERROR)


def _do_import_settings(
    ctx: FeatureContext,
    popup: Popup,
    on_import_complete: Callable[[], None],
) -> None:
    """設定をJSONファイルからインポート (Phase 27)

    Opens a file selection dialog and imports settings from a JSON file.
    Creates a backup before modifying config and uses atomic save.

    Args:
        ctx: FeatureContext providing config, config_file, controls, _config_store
        popup: 親ポップアップ（インポート後に閉じてリロード用）
        on_import_complete: インポート完了後に呼ばれるコールバック
    """
    from tkinter import Tk, filedialog

    # Create hidden Tk root for file dialog
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        file_path = filedialog.askopenfilename(
            title=i18n._("mykatrain:settings:import_title"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
    finally:
        root.destroy()

    if not file_path:
        return  # User cancelled

    try:
        # Read JSON file
        with open(file_path, encoding="utf-8") as f:
            json_str = f.read()

        # Parse and validate
        imported = parse_exported_settings(json_str)

    except ValueError as e:
        # JSON parse or validation error
        logging.warning(f"Settings import validation failed: {e}")
        ctx.controls.set_status(f"Import failed: {e}", STATUS_ERROR)
        return
    except (OSError, UnicodeDecodeError) as e:
        # File read failure: file not found, permission denied, encoding error
        logging.warning(f"Settings import read failed from {file_path}: {e}", exc_info=True)
        ctx.controls.set_status(f"Import failed: {e}", STATUS_ERROR)
        return
    except Exception as e:
        # Boundary fallback: unexpected error during settings import
        logging.error(f"Unexpected error importing settings from {file_path}: {e}", exc_info=True)
        ctx.controls.set_status(f"Import failed: {e}", STATUS_ERROR)
        return

    # Create backup
    backup_path = create_backup_path(ctx.config_file)
    try:
        shutil.copy2(ctx.config_file, backup_path)
    except OSError as e:
        # Backup failure: permission denied, disk full
        logging.warning(f"Settings import backup failed: {e}", exc_info=True)
        ctx.controls.set_status(f"Backup failed: {e}", STATUS_ERROR)
        return

    # Save original config for rollback
    # Note: Accessing private _config is intentional (Phase 111 scope-out)
    original_config = {
        k: dict(v) if isinstance(v, dict) else v
        for k, v in ctx._config.items()  # type: ignore[attr-defined]
    }

    try:
        # Update config in memory
        for section, values in imported.sections.items():
            if section in EXCLUDED_SECTIONS:
                continue
            if section not in ctx._config:  # type: ignore[attr-defined]
                ctx._config[section] = {}  # type: ignore[attr-defined]
            ctx._config[section].update(values)  # type: ignore[attr-defined]

        # Atomic save
        atomic_save_config(ctx._config, ctx.config_file)  # type: ignore[attr-defined]

        # Reload store (reload-then-sync pattern)
        ctx._config_store._load()  # type: ignore[attr-defined]
        ctx._config = dict(ctx._config_store)  # type: ignore[attr-defined]

    except (OSError, json.JSONDecodeError) as e:
        # Atomic save or reload failure
        logging.error(f"Settings import save failed: {e}", exc_info=True)
        # Rollback on failure
        ctx._config = original_config  # type: ignore[attr-defined]
        rollback_failed = False
        try:
            shutil.copy2(backup_path, ctx.config_file)
            ctx._config_store._load()  # type: ignore[attr-defined]
            ctx._config = dict(ctx._config_store)  # type: ignore[attr-defined]
        except Exception as rollback_err:
            # Boundary fallback: rollback itself failed.
            # At this point the config may be in an inconsistent state.
            # We log but cannot recover - user must restart or manually fix.
            logging.error(
                f"CRITICAL: Settings rollback failed after import error. "
                f"Config may be inconsistent. Error: {rollback_err}",
                exc_info=True,
            )
            rollback_failed = True
        if rollback_failed:
            ctx.controls.set_status(
                f"Import failed, restore may be incomplete. Restart recommended. Error: {e}",
                STATUS_ERROR,
            )
        else:
            ctx.controls.set_status(f"Import failed, restored: {e}", STATUS_ERROR)
        return
    except Exception as e:
        # Boundary fallback: unexpected error during save
        logging.error(f"Unexpected error during settings save: {e}", exc_info=True)
        # Rollback on failure
        ctx._config = original_config  # type: ignore[attr-defined]
        rollback_failed = False
        try:
            shutil.copy2(backup_path, ctx.config_file)
            ctx._config_store._load()  # type: ignore[attr-defined]
            ctx._config = dict(ctx._config_store)  # type: ignore[attr-defined]
        except Exception as rollback_err:
            logging.error(
                f"CRITICAL: Settings rollback failed after import error. "
                f"Config may be inconsistent. Error: {rollback_err}",
                exc_info=True,
            )
            rollback_failed = True
        if rollback_failed:
            ctx.controls.set_status(
                f"Import failed, restore may be incomplete. Restart recommended. Error: {e}",
                STATUS_ERROR,
            )
        else:
            ctx.controls.set_status(f"Import failed, restored: {e}", STATUS_ERROR)
        return

    ctx.controls.set_status(
        i18n._("mykatrain:settings:import_success").format(backup=backup_path),
        STATUS_INFO,
    )

    # Reload settings popup
    popup.dismiss()
    on_import_complete()


# =============================================================================
# Phase 145-D+: Shared state container for tab builders
# =============================================================================

from katrain.gui.features.settings_popup_helpers import _add_searchable_label
from katrain.gui.features.settings_popup_state import _SettingsPopupContext
from katrain.gui.features.settings_popup_tabs import _build_leela_tab

# Re-export for backward compatibility (Phase 145-D+)
__all__ = ["do_mykatrain_settings_popup", "_SettingsPopupContext"]


# =============================================================================
# Phase 145-D+: Tab builders (extracted from do_mykatrain_settings_popup)
# =============================================================================


def _build_analysis_tab(state: _SettingsPopupContext) -> tuple[BoxLayout, Button]:
    """Build the Analysis tab content (Tab 1).

    Phase 145-D+: Extracted from ``do_mykatrain_settings_popup``.

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
    from katrain.core.analysis import EngineType  # Phase 34

    inner = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None)
    inner.bind(minimum_height=inner.setter("height"))

    # --- Analysis Engine Selection (Phase 34) ---
    _add_searchable_label(inner, "mykatrain:settings:analysis_engine", state)

    engine_options = [
        (EngineType.KATAGO.value, i18n._("mykatrain:settings:engine_katago")),
        (EngineType.LEELA.value, i18n._("mykatrain:settings:engine_leela")),
    ]

    # Phase 87.5: Check if Leela is configured for gating
    leela_enabled_for_gating = state.leela_config.enabled or bool(state.leela_config.exe_path or "")

    engine_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(3))
    for engine_value, engine_label_text in engine_options:
        is_leela_option = engine_value == EngineType.LEELA.value
        should_disable = is_leela_option and not leela_enabled_for_gating
        is_active = engine_value == state.current_engine
        # If Leela not configured and currently selected, force to KataGo
        if is_leela_option and not leela_enabled_for_gating and is_active:
            is_active = False
            state.selected_engine[0] = EngineType.KATAGO.value

        checkbox = CheckBox(
            group="analysis_engine_setting",
            active=is_active,
            size_hint_x=None,
            width=dp(30),
            disabled=should_disable,
        )
        checkbox.bind(
            active=lambda chk, active, val=engine_value: state.selected_engine.__setitem__(0, val)
            if active
            else None
        )
        label = Label(
            text=engine_label_text,
            size_hint_x=0.4,  # Flexible width for i18n (Issue 16)
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        engine_layout.add_widget(checkbox)
        engine_layout.add_widget(label)
    inner.add_widget(engine_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:analysis_engine", engine_layout)

    # --- Disable KataGo Checkbox (Phase 3 Extension) ---
    _add_searchable_label(inner, "mykatrain:settings:disable_katago", state)

    disable_katago_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8))
    disable_katago_checkbox = CheckBox(
        active=state.selected_disable_katago[0],
        size_hint_x=None,
        width=dp(30),
    )
    disable_katago_checkbox.bind(
        active=lambda chk, active: state.selected_disable_katago.__setitem__(0, active)
    )
    disable_katago_layout.add_widget(disable_katago_checkbox)
    disable_katago_layout.add_widget(Label())  # Spacer
    inner.add_widget(disable_katago_layout)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:disable_katago", disable_katago_layout)

    # --- Skill Preset (Radio buttons) ---
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
            active=lambda chk, active, val=skill_value: state.selected_skill_preset.__setitem__(0, val)
            if active
            else None
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

    # --- PV Filter Level (Radio buttons) ---
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
            active=lambda chk, active, val=pv_value: state.selected_pv_filter.__setitem__(0, val)
            if active
            else None
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

    # --- Beginner Hints toggle (Phase 91) ---
    _add_searchable_label(inner, "mykatrain:settings:beginner_hints", state)

    beginner_hints_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8))
    beginner_hints_checkbox = CheckBox(
        active=state.selected_beginner_hints[0],
        size_hint_x=None,
        width=dp(30),
    )
    beginner_hints_checkbox.bind(
        active=lambda chk, active: state.selected_beginner_hints.__setitem__(0, active)
    )
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

    # --- Reset button ---
    reset_btn = Button(
        text=i18n._("mykatrain:settings:reset"),
        size_hint_y=None,
        height=dp(36),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    inner.add_widget(reset_btn)

    return inner, reset_btn


def _build_export_tab(state: _SettingsPopupContext) -> tuple[BoxLayout, Button, dict[str, Any]]:
    """Build the Export tab content (Tab 2).

    Phase 145-D+: Extracted from ``do_mykatrain_settings_popup``.

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

    # --- Default User Name ---
    user_row, user_input, _ = create_text_input_row(
        label_text=i18n._("mykatrain:settings:default_user_name"),
        initial_value=state.current_settings.get("default_user_name", ""),
    )
    inner.add_widget(user_row)
    if state.register_searchable is not None:
        state.register_searchable("mykatrain:settings:default_user_name", user_row)

    # --- Karte Output Directory ---
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

    # --- Batch Export Input Directory ---
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

    # --- Karte Format (Radio buttons - 2x2 grid) ---
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
            active=lambda chk, active, val=format_value: state.selected_format.__setitem__(0, val)
            if active
            else None
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

    # --- Opponent Info Mode (Radio buttons - 2x2 grid) - Phase 4 ---
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
            active=lambda chk, active, val=opp_value: state.selected_opp_info.__setitem__(0, val)
            if active
            else None
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
        "user_input": user_input,
        "output_input": output_input,
        "input_input": input_input,
        "output_browse": output_browse,
        "input_browse": input_browse,
    }
    return inner, reset_btn, widget_refs


def do_mykatrain_settings_popup(
    ctx: FeatureContext,
    initial_tab: str | None = None,  # Phase 87.5: "analysis", "export", "leela"
) -> None:
    """myKatrain設定ポップアップを表示

    Phase 145-D+: Refactored from a 809-line closure into a thin orchestrator
    that delegates tab content generation to ``_build_analysis_tab``,
    ``_build_export_tab`` and ``_build_leela_tab``. Shared mutable state is
    passed via ``_SettingsPopupContext``.

    Args:
        ctx: FeatureContext providing config, save_config, controls
        initial_tab: Optional tab to select on open ("analysis", "export", "leela")
    """
    from katrain.core.analysis import EngineType, get_analysis_engine

    current_settings = ctx.config("mykatrain_settings") or {}
    engine_config = ctx.config("engine") or {}
    current_engine = get_analysis_engine(engine_config)
    leela_config = ctx.get_leela_config()

    # Phase 145-D+: Initialize shared state container
    state = _SettingsPopupContext(
        ctx=ctx,
        current_settings=current_settings,
        engine_config=engine_config,
        current_engine=current_engine,
        leela_config=leela_config,
        selected_engine=[current_engine],
        selected_disable_katago=[ctx.config("engine/disabled", False)],
        selected_skill_preset=[ctx.config("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET],
        selected_pv_filter=[ctx.config("general/pv_filter_level") or eval_metrics.DEFAULT_PV_FILTER_LEVEL],
        selected_beginner_hints=[ctx.config("beginner_hints/enabled", False)],
        selected_format=[current_settings.get("karte_format", "both")],
        selected_opp_info=[current_settings.get("opponent_info_mode", "auto")],
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

    # --- Build 3 tabs ---
    tab1_inner, tab1_reset_btn = _build_analysis_tab(state)
    tab2_inner, tab2_reset_btn, export_widgets = _build_export_tab(state)
    tab3_inner, tab3_reset_btn, leela_widgets = _build_leela_tab(state)
    widget_refs = {**export_widgets, **leela_widgets}

    tab1 = TabbedPanelItem(text=i18n._("mykatrain:settings:tab_analysis"))
    tab1_scroll = ScrollView(do_scroll_x=False)
    tab1_scroll.add_widget(tab1_inner)
    tab1.add_widget(tab1_scroll)

    tab2 = TabbedPanelItem(text=i18n._("mykatrain:settings:tab_export"))
    tab2_scroll = ScrollView(do_scroll_x=False)
    tab2_scroll.add_widget(tab2_inner)
    tab2.add_widget(tab2_scroll)

    tab3 = TabbedPanelItem(text=i18n._("mykatrain:settings:tab_leela"))
    tab3_scroll = ScrollView(do_scroll_x=False)
    tab3_scroll.add_widget(tab3_inner)
    tab3.add_widget(tab3_scroll)

    tabbed_panel = TabbedPanel(
        do_default_tab=False,
        tab_width=dp(120),
        tab_height=dp(40),
        size_hint_y=0.9,
    )
    tabbed_panel.add_widget(tab1)
    tabbed_panel.add_widget(tab2)
    tabbed_panel.add_widget(tab3)

    # Phase 87.5 + Phase 89: Tab lookup dictionary
    tab_by_id = {
        "analysis": tab1,
        "export": tab2,
        "leela": tab3,
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
        size=[dp(900), dp(700)],
        content=main_layout,
    ).__self__
    state.popup = popup

    # --- Save callback (Phase 145-D: 6-line orchestrator delegating to helpers) ---
    def save_settings(*_args: Any) -> None:
        """Save all settings sections."""
        _save_general_settings(ctx, state.selected_skill_preset[0], state.selected_pv_filter[0])
        _save_beginner_hints_settings(ctx, state.selected_beginner_hints[0])
        new_engine_value = state.selected_engine[0]
        leela_enabled = new_engine_value == EngineType.LEELA.value
        _save_engine_settings(ctx, new_engine_value)
        _save_mykatrain_settings(
            ctx,
            widget_refs["user_input"].text,
            widget_refs["output_input"].text,
            widget_refs["input_input"].text,
            state.selected_format[0],
            state.selected_opp_info[0],
            state.selected_disable_katago[0],
        )
        _save_leela_settings(
            ctx,
            leela_enabled=leela_enabled,
            leela_path=widget_refs["leela_path_input"].text.strip(),
            leela_k_value=widget_refs["leela_k_slider"].value,
            leela_top_show=widget_refs["leela_top_moves_spinner"].selected[1],
            leela_top_show_2=widget_refs["leela_top_moves_spinner_2"].selected[1],
            leela_visits_text=widget_refs["leela_visits_input"].text,
            leela_fast_visits_text=widget_refs["leela_fast_visits_input"].text.strip(),
            leela_cand_value=widget_refs["leela_cand_spinner"].selected[1],
        )
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

    def browse_leela_exe(*_args: Any) -> None:
        _open_browse_dialog(
            ctx=ctx,
            title="Select Leela Zero executable",
            initial_path=widget_refs["leela_path_input"].text,
            target_text_input=widget_refs["leela_path_input"],
            dirselect=False,
            file_filter=["*.exe"],
            select_string="Select",
        )

    save_button.bind(on_release=save_settings)
    cancel_button.bind(on_release=lambda *_args: popup.dismiss())
    widget_refs["output_browse"].bind(on_release=browse_output)
    widget_refs["input_browse"].bind(on_release=browse_input)
    widget_refs["leela_path_browse"].bind(on_release=browse_leela_exe)

    export_button.bind(on_release=lambda *_args: _do_export_settings(ctx, popup))
    import_button.bind(on_release=lambda *_args: _do_import_settings(ctx, popup, reopen_popup))

    tab1_reset_btn.bind(on_release=lambda *_args: _reset_tab_settings(ctx, "analysis", popup, reopen_popup))
    tab2_reset_btn.bind(on_release=lambda *_args: _reset_tab_settings(ctx, "export", popup, reopen_popup))
    tab3_reset_btn.bind(on_release=lambda *_args: _reset_tab_settings(ctx, "leela", popup, reopen_popup))

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
        text=i18n._("Cancel"),
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

    Phase 145-D: Unified the 3 nearly-identical browse_output / browse_input /
    browse_leela_exe callbacks into a single helper. The original behavior is
    preserved exactly.

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


# =============================================================================
# Phase 145-D: Per-section save helpers (extracted from save_settings closure)
# =============================================================================


def _save_general_settings(ctx: FeatureContext, skill_preset: str, pv_filter_level: str) -> None:
    """Save general config (skill_preset, pv_filter_level)."""
    general = ctx.config("general") or {}
    general["skill_preset"] = skill_preset
    general["pv_filter_level"] = pv_filter_level
    ctx.set_config_section("general", general)
    ctx.save_config("general")


def _save_beginner_hints_settings(ctx: FeatureContext, enabled: bool) -> None:
    """Save beginner_hints enabled state (Phase 91)."""
    beginner_hints_config = ctx.config("beginner_hints") or {}
    beginner_hints_config["enabled"] = enabled
    ctx.set_config_section("beginner_hints", beginner_hints_config)
    ctx.save_config("beginner_hints")


def _save_engine_settings(ctx: FeatureContext, new_engine_value: str) -> None:
    """Save analysis engine selection with error handling (Phase 34, Phase 102)."""
    try:
        ctx.update_engine_config(analysis_engine=new_engine_value)
    except OSError as e:
        # File write failure during engine config save
        logging.error(f"Failed to save engine config (file error): {e}", exc_info=True)
        ctx.controls.set_status(
            i18n._("mykatrain:settings:engine_save_error"),
            STATUS_ERROR,
        )
    except Exception as e:
        # Boundary fallback: unexpected error (config structure issue, etc.)
        logging.error(f"Failed to save engine config (unexpected): {e}", exc_info=True)
        ctx.controls.set_status(
            i18n._("mykatrain:settings:engine_save_error"),
            STATUS_ERROR,
        )


def _save_mykatrain_settings(
    ctx: FeatureContext,
    default_user_name: str,
    karte_output_directory: str,
    batch_export_input_directory: str,
    karte_format: str,
    opponent_info_mode: str,
    disabled_katago: bool,
) -> None:
    """Save mykatrain_settings section + engine disabled flag (Phase 27)."""
    mykatrain_settings = {
        "default_user_name": default_user_name,
        "karte_output_directory": karte_output_directory,
        "batch_export_input_directory": batch_export_input_directory,
        "karte_format": karte_format,
        "opponent_info_mode": opponent_info_mode,
    }
    ctx.set_config_section("mykatrain_settings", mykatrain_settings)
    ctx.save_config("mykatrain_settings")
    # Save engine config (Phase 3 Extension)
    ctx.update_engine_config(disabled=disabled_katago)


def _save_leela_settings(
    ctx: FeatureContext,
    *,
    leela_enabled: bool,
    leela_path: str,
    leela_k_value: float,
    leela_top_show: str,
    leela_top_show_2: str,
    leela_visits_text: str,
    leela_fast_visits_text: str,
    leela_cand_value: Any,
) -> None:
    """Save Leela Zero settings via typed config API (Phase 102, Phase 30, Phase 123)."""
    from katrain.core.analysis.models import LEELA_FAST_VISITS_MIN

    # Get defaults from single source (no hardcoding)
    _leela_defaults = LeelaConfig.from_dict({})

    # max_visits: parse with validation
    try:
        computed_max_visits = max(100, min(100000, int(leela_visits_text)))
    except ValueError:
        computed_max_visits = _leela_defaults.max_visits

    # fast_visits: parse with validation
    try:
        fast_visits_raw = int(leela_fast_visits_text)
        # UI Validation:
        # - 下限: LEELA_FAST_VISITS_MIN (50) または max_visits のうち小さい方
        # - 上限: max_visits
        # エッジケース: max_visits < 50 の場合、fast_visits も max_visits に制限
        lower_bound = min(LEELA_FAST_VISITS_MIN, computed_max_visits)
        computed_fast_visits = max(lower_bound, min(computed_max_visits, fast_visits_raw))
    except ValueError:
        computed_fast_visits = _leela_defaults.fast_visits

    # play_visits: fixed default (Phase 123: removed from UI)
    computed_play_visits = _leela_defaults.play_visits

    # Convert "auto" to -1 (unlimited)
    max_cand_int = -1 if str(leela_cand_value).lower() == "auto" else int(leela_cand_value)

    # Update via typed config API (handles MERGE and persistence)
    ctx.update_leela_config(
        enabled=leela_enabled,
        exe_path=leela_path,
        loss_scale_k=clamp_k(leela_k_value),
        max_visits=computed_max_visits,
        top_moves_show=leela_top_show,
        top_moves_show_secondary=leela_top_show_2,
        fast_visits=computed_fast_visits,
        play_visits=computed_play_visits,
        max_candidates=max_cand_int,
    )
