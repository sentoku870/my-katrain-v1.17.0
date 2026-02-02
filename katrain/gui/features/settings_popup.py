# katrain/gui/features/settings_popup.py
#
# 設定ポップアップ機能モジュール
#
# __main__.py から抽出した設定関連の関数を配置します。
# - load_export_settings: エクスポート設定の読み込み
# - save_export_settings: エクスポート設定の保存
# - save_batch_options: バッチオプションの保存
# - do_mykatrain_settings_popup: myKatrain設定ポップアップの表示
# - _reset_tab_settings: タブ別設定リセット (Phase 27)

from __future__ import annotations

import json
import logging
import os
import shutil
from typing import TYPE_CHECKING, Any, Callable

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
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
from katrain.core import eval_metrics
from katrain.core.auto_setup import should_show_auto_tab_first  # Phase 89
from katrain.core.constants import (
    LEELA_K_DEFAULT,
    LEELA_K_MAX,
    LEELA_K_MIN,
    LEELA_TOP_MOVE_OPTIONS,
    LEELA_TOP_MOVE_OPTIONS_SECONDARY,
    STATUS_ERROR,
    STATUS_INFO,
)
from katrain.core.leela.logic import clamp_k
from katrain.core.lang import i18n
from katrain.gui.kivyutils import I18NSpinner
from katrain.gui.popups import I18NPopup
from katrain.gui.theme import Theme
from katrain.gui.widgets.helpers import create_text_input_row

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def _reset_tab_settings(
    ctx: "FeatureContext",
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
    message_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width * 0.9, None))
    )
    confirm_layout.add_widget(message_label)

    buttons_layout = BoxLayout(
        orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(40)
    )
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
    ctx: "FeatureContext",
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
    ctx: "FeatureContext",
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
        with open(file_path, "r", encoding="utf-8") as f:
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
        k: dict(v) if isinstance(v, dict) else v for k, v in ctx._config.items()  # type: ignore[attr-defined]
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


def load_export_settings(ctx: "FeatureContext") -> dict[str, Any]:
    """エクスポート設定を読み込む

    Args:
        ctx: FeatureContext providing config

    Returns:
        エクスポート設定辞書
    """
    return ctx.config("export_settings") or {}


def save_export_settings(
    ctx: "FeatureContext",
    sgf_directory: str | None = None,
    selected_players: list[str] | None = None,
) -> None:
    """エクスポート設定を保存する

    Args:
        ctx: FeatureContext providing config, save_config
        sgf_directory: SGFディレクトリパス（オプション）
        selected_players: 選択されたプレイヤーリスト（オプション）
    """
    current_settings = load_export_settings(ctx)

    if sgf_directory is not None:
        current_settings["last_sgf_directory"] = sgf_directory
    if selected_players is not None:
        current_settings["last_selected_players"] = selected_players

    # config システムに保存
    ctx.set_config_section("export_settings", current_settings)
    ctx.save_config("export_settings")


def save_batch_options(ctx: "FeatureContext", options: dict[str, Any]) -> None:
    """バッチオプションを保存する

    Args:
        ctx: FeatureContext providing config, save_config
        options: 保存するオプション辞書
    """
    mykatrain_settings = ctx.config("mykatrain_settings") or {}
    batch_options = mykatrain_settings.get("batch_options", {})
    batch_options.update(options)
    mykatrain_settings["batch_options"] = batch_options
    ctx.set_config_section("mykatrain_settings", mykatrain_settings)
    ctx.save_config("mykatrain_settings")


def do_mykatrain_settings_popup(
    ctx: "FeatureContext",
    initial_tab: str | None = None,  # Phase 87.5: "analysis", "export", "leela"
) -> None:
    """myKatrain設定ポップアップを表示

    Args:
        ctx: FeatureContext providing config, save_config, controls
        initial_tab: Optional tab to select on open ("analysis", "export", "leela")
    """
    current_settings = ctx.config("mykatrain_settings") or {}

    # Main layout: Search + TabbedPanel + Buttons
    main_layout = BoxLayout(orientation="vertical", spacing=dp(8))

    # Search bar
    search_layout = BoxLayout(
        orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(40)
    )
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

    # Searchable widgets list (populated after widget creation)
    searchable_widgets: list[dict[str, Any]] = []

    def register_searchable(label_text: str, *widgets: Any) -> None:
        """検索対象としてウィジェットを登録"""
        for widget in widgets:
            searchable_widgets.append({"label_text": label_text, "widget": widget})

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

    def on_search_clear(*_args: Any) -> None:
        """検索をクリア"""
        search_input.text = ""

    search_input.bind(text=on_search_text_change)
    search_clear_btn.bind(on_release=on_search_clear)

    # TabbedPanel with 3 tabs
    tabbed_panel = TabbedPanel(
        do_default_tab=False,
        tab_width=dp(120),
        tab_height=dp(40),
        size_hint_y=0.9,
    )

    # popup 変数を先に宣言（リセット用のコールバックで使用）
    popup = None

    def reopen_popup() -> None:
        """ポップアップをリロードして再表示"""
        from kivy.clock import Clock

        Clock.schedule_once(lambda dt: do_mykatrain_settings_popup(ctx), 0.1)

    # === Tab 1: 解析設定 (Analysis) ===
    tab1 = TabbedPanelItem(text=i18n._("mykatrain:settings:tab_analysis"))
    tab1_scroll = ScrollView(do_scroll_x=False)
    tab1_inner = BoxLayout(
        orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None
    )
    tab1_inner.bind(minimum_height=tab1_inner.setter("height"))

    # === Tab 2: 出力設定 (Export) ===
    tab2 = TabbedPanelItem(text=i18n._("mykatrain:settings:tab_export"))
    tab2_scroll = ScrollView(do_scroll_x=False)
    tab2_inner = BoxLayout(
        orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None
    )
    tab2_inner.bind(minimum_height=tab2_inner.setter("height"))

    # === Tab 3: Leela Zero ===
    tab3 = TabbedPanelItem(text=i18n._("mykatrain:settings:tab_leela"))
    tab3_scroll = ScrollView(do_scroll_x=False)
    tab3_inner = BoxLayout(
        orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None
    )
    tab3_inner.bind(minimum_height=tab3_inner.setter("height"))

    # === Analysis Engine Selection (Phase 34) ===
    from katrain.core.analysis import EngineType, get_analysis_engine

    engine_label = Label(
        text=i18n._("mykatrain:settings:analysis_engine"),
        size_hint_y=None,
        height=dp(25),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    engine_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    tab1_inner.add_widget(engine_label)

    # Get current value via Phase 33 function (with fallback)
    engine_config = ctx.config("engine") or {}
    current_engine = get_analysis_engine(engine_config)
    selected_engine = [current_engine]

    # Radio button options (use EngineType constants for name consistency)
    engine_options = [
        (EngineType.KATAGO.value, i18n._("mykatrain:settings:engine_katago")),
        (EngineType.LEELA.value, i18n._("mykatrain:settings:engine_leela")),
    ]

    # Phase 87.5: Check if Leela is configured for gating
    from katrain.gui.features.batch_core import is_leela_configured
    leela_enabled_for_gating = is_leela_configured(ctx)

    engine_layout = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(3)
    )
    for engine_value, engine_label_text in engine_options:
        # Phase 87.5: Disable Leela checkbox if not configured
        is_leela_option = (engine_value == EngineType.LEELA.value)
        should_disable = is_leela_option and not leela_enabled_for_gating

        # If Leela not configured and currently selected, force to KataGo
        is_active = (engine_value == current_engine)
        if is_leela_option and not leela_enabled_for_gating and is_active:
            is_active = False
            # Force KataGo to be selected
            if engine_value == EngineType.KATAGO.value:
                pass  # Will be handled by the katago iteration
            else:
                selected_engine[0] = EngineType.KATAGO.value

        checkbox = CheckBox(
            group="analysis_engine_setting",
            active=is_active,
            size_hint_x=None,
            width=dp(30),
            disabled=should_disable,  # Phase 87.5
        )
        checkbox.bind(
            active=lambda chk, active, val=engine_value: (
                selected_engine.__setitem__(0, val) if active else None
            )
        )
        label = Label(
            text=engine_label_text,
            size_hint_x=0.4,  # Flexible width for i18n (Issue 16)
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        label.bind(
            size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
        )
        engine_layout.add_widget(checkbox)
        engine_layout.add_widget(label)

    tab1_inner.add_widget(engine_layout)
    register_searchable(
        i18n._("mykatrain:settings:analysis_engine"), engine_label, engine_layout
    )

    # Skill Preset (Radio buttons)
    skill_label = Label(
        text=i18n._("mykatrain:settings:skill_preset"),
        size_hint_y=None,
        height=dp(25),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    skill_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    tab1_inner.add_widget(skill_label)
    # Register for search (will register skill_layout after creation)

    current_skill_preset = (
        ctx.config("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET
    )
    selected_skill_preset = [current_skill_preset]

    skill_options = [
        ("auto", i18n._("mykatrain:settings:skill_auto")),
        ("relaxed", i18n._("mykatrain:settings:skill_relaxed")),
        ("beginner", i18n._("mykatrain:settings:skill_beginner")),
        ("standard", i18n._("mykatrain:settings:skill_standard")),
        ("advanced", i18n._("mykatrain:settings:skill_advanced")),
        ("pro", i18n._("mykatrain:settings:skill_pro")),
    ]

    skill_layout = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(3)
    )
    for skill_value, skill_label_text in skill_options:
        checkbox = CheckBox(
            group="skill_preset_setting",
            active=(skill_value == current_skill_preset),
            size_hint_x=None,
            width=dp(30),
        )
        checkbox.bind(
            active=lambda chk, active, val=skill_value: (
                selected_skill_preset.__setitem__(0, val) if active else None
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
        label.bind(
            size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
        )
        skill_layout.add_widget(checkbox)
        skill_layout.add_widget(label)
    tab1_inner.add_widget(skill_layout)
    register_searchable(i18n._("mykatrain:settings:skill_preset"), skill_label, skill_layout)

    # PV Filter Level (Radio buttons)
    pv_filter_label = Label(
        text=i18n._("mykatrain:settings:pv_filter_level"),
        size_hint_y=None,
        height=dp(25),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    pv_filter_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    tab1_inner.add_widget(pv_filter_label)

    current_pv_filter = (
        ctx.config("general/pv_filter_level") or eval_metrics.DEFAULT_PV_FILTER_LEVEL
    )
    selected_pv_filter = [current_pv_filter]

    pv_filter_options = [
        ("auto", i18n._("mykatrain:settings:pv_filter_auto")),
        ("off", i18n._("mykatrain:settings:pv_filter_off")),
        ("weak", i18n._("mykatrain:settings:pv_filter_weak")),
        ("medium", i18n._("mykatrain:settings:pv_filter_medium")),
        ("strong", i18n._("mykatrain:settings:pv_filter_strong")),
    ]

    pv_filter_layout = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(3)
    )
    for pv_value, pv_label_text in pv_filter_options:
        checkbox = CheckBox(
            group="pv_filter_setting",
            active=(pv_value == current_pv_filter),
            size_hint_x=None,
            width=dp(30),
        )
        checkbox.bind(
            active=lambda chk, active, val=pv_value: (
                selected_pv_filter.__setitem__(0, val) if active else None
            )
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
        label.bind(
            size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
        )
        pv_filter_layout.add_widget(checkbox)
        pv_filter_layout.add_widget(label)
    tab1_inner.add_widget(pv_filter_layout)
    register_searchable(i18n._("mykatrain:settings:pv_filter_level"), pv_filter_label, pv_filter_layout)

    # Phase 91: Beginner Hints toggle
    beginner_hints_label = Label(
        text=i18n._("mykatrain:settings:beginner_hints"),
        size_hint_y=None,
        height=dp(25),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    beginner_hints_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    tab1_inner.add_widget(beginner_hints_label)

    current_beginner_hints = ctx.config("beginner_hints/enabled", False)
    selected_beginner_hints = [current_beginner_hints]

    beginner_hints_layout = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(8)
    )
    beginner_hints_checkbox = CheckBox(
        active=current_beginner_hints,
        size_hint_x=None,
        width=dp(30),
    )
    beginner_hints_checkbox.bind(
        active=lambda chk, active: selected_beginner_hints.__setitem__(0, active)
    )
    beginner_hints_desc = Label(
        text=i18n._("mykatrain:settings:beginner_hints_desc"),
        size_hint_x=0.9,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    beginner_hints_desc.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    beginner_hints_layout.add_widget(beginner_hints_checkbox)
    beginner_hints_layout.add_widget(beginner_hints_desc)
    tab1_inner.add_widget(beginner_hints_layout)
    register_searchable(
        i18n._("mykatrain:settings:beginner_hints"), beginner_hints_label, beginner_hints_layout
    )

    # Reset button for Analysis tab (Phase 27)
    tab1_reset_btn = Button(
        text=i18n._("mykatrain:settings:reset"),
        size_hint_y=None,
        height=dp(36),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    tab1_inner.add_widget(tab1_reset_btn)

    # Default User Name
    user_row, user_input, _ = create_text_input_row(
        label_text=i18n._("mykatrain:settings:default_user_name"),
        initial_value=current_settings.get("default_user_name", ""),
    )
    tab2_inner.add_widget(user_row)
    register_searchable(i18n._("mykatrain:settings:default_user_name"), user_row)

    # Karte Output Directory
    output_row = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10)
    )
    output_label = Label(
        text=i18n._("mykatrain:settings:karte_output_directory"),
        size_hint_x=0.35,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    output_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    output_input = TextInput(
        text=current_settings.get("karte_output_directory", ""),
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
    tab2_inner.add_widget(output_row)
    register_searchable(i18n._("mykatrain:settings:karte_output_directory"), output_row)

    # Batch Export Input Directory
    input_row = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10)
    )
    input_label = Label(
        text=i18n._("mykatrain:settings:batch_export_input_directory"),
        size_hint_x=0.35,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    input_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    input_input = TextInput(
        text=current_settings.get("batch_export_input_directory", ""),
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
    tab2_inner.add_widget(input_row)
    register_searchable(i18n._("mykatrain:settings:batch_export_input"), input_row)

    # Karte Format (Radio buttons - 2x2 grid)
    format_label = Label(
        text=i18n._("mykatrain:settings:karte_format"),
        size_hint_y=None,
        height=dp(25),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    format_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    tab2_inner.add_widget(format_label)

    format_layout = GridLayout(cols=2, spacing=dp(5), size_hint_y=None, height=dp(80))
    format_options = [
        ("both", i18n._("mykatrain:settings:format_both")),
        ("black_only", i18n._("mykatrain:settings:format_black_only")),
        ("white_only", i18n._("mykatrain:settings:format_white_only")),
        ("default_user_only", i18n._("mykatrain:settings:format_default_user_only")),
    ]

    current_format = current_settings.get("karte_format", "both")
    selected_format = [current_format]

    for format_value, format_label_text in format_options:
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36))
        checkbox = CheckBox(
            group="karte_format",
            active=(format_value == current_format),
            size_hint_x=None,
            width=dp(30),
        )
        checkbox.bind(
            active=lambda chk, active, val=format_value: (
                selected_format.__setitem__(0, val) if active else None
            )
        )
        label = Label(
            text=format_label_text,
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        label.bind(
            size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
        )
        row.add_widget(checkbox)
        row.add_widget(label)
        format_layout.add_widget(row)

    tab2_inner.add_widget(format_layout)
    register_searchable(i18n._("mykatrain:settings:karte_format"), format_label, format_layout)

    # Opponent Info Mode (Radio buttons - 2x2 grid) - Phase 4
    opp_info_label = Label(
        text=i18n._("mykatrain:settings:opponent_info_mode"),
        size_hint_y=None,
        height=dp(25),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    opp_info_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    tab2_inner.add_widget(opp_info_label)

    opp_info_layout = GridLayout(cols=2, spacing=dp(5), size_hint_y=None, height=dp(80))
    opp_info_options = [
        ("auto", i18n._("mykatrain:settings:opponent_info_auto")),
        ("always_detailed", i18n._("mykatrain:settings:opponent_info_detailed")),
        ("always_aggregate", i18n._("mykatrain:settings:opponent_info_aggregate")),
    ]

    current_opp_info = current_settings.get("opponent_info_mode", "auto")
    selected_opp_info = [current_opp_info]

    for opp_value, opp_label_text in opp_info_options:
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36))
        checkbox = CheckBox(
            group="opponent_info_mode",
            active=(opp_value == current_opp_info),
            size_hint_x=None,
            width=dp(30),
        )
        checkbox.bind(
            active=lambda chk, active, val=opp_value: (
                selected_opp_info.__setitem__(0, val) if active else None
            )
        )
        label = Label(
            text=opp_label_text,
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        label.bind(
            size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
        )
        row.add_widget(checkbox)
        row.add_widget(label)
        opp_info_layout.add_widget(row)
    tab2_inner.add_widget(opp_info_layout)
    register_searchable(i18n._("mykatrain:settings:opponent_info_mode"), opp_info_label, opp_info_layout)

    # Reset button for Export tab (Phase 27)
    tab2_reset_btn = Button(
        text=i18n._("mykatrain:settings:reset"),
        size_hint_y=None,
        height=dp(36),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    tab2_inner.add_widget(tab2_reset_btn)

    # === Leela Zero Settings Section ===
    # Note: Section label is no longer needed as it's now a separate tab

    # Leela Enabled Checkbox
    # Note: leela_config is used as dict throughout this section, keep as dict
    leela_config = ctx.config("leela") or {}
    leela_enabled_row = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(5)
    )
    leela_enabled_checkbox = CheckBox(
        active=leela_config.get("enabled", False),
        size_hint_x=None,
        width=dp(36),
    )
    leela_enabled_label = Label(
        text=i18n._("mykatrain:settings:leela_enabled"),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_enabled_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    leela_enabled_row.add_widget(leela_enabled_checkbox)
    leela_enabled_row.add_widget(leela_enabled_label)
    tab3_inner.add_widget(leela_enabled_row)
    register_searchable(i18n._("mykatrain:settings:leela_enabled"), leela_enabled_row)

    # Leela Executable Path
    leela_path_row = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10)
    )
    leela_path_label = Label(
        text=i18n._("mykatrain:settings:leela_exe_path"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_path_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    leela_path_input = TextInput(
        text=leela_config.get("exe_path", ""),
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
    tab3_inner.add_widget(leela_path_row)
    register_searchable(i18n._("mykatrain:settings:leela_exe_path"), leela_path_row)

    # Leela K Value Slider
    leela_k_row = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10)
    )
    leela_k_label = Label(
        text=i18n._("mykatrain:settings:leela_k_value"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_k_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    leela_k_slider = Slider(
        min=LEELA_K_MIN,
        max=LEELA_K_MAX,
        value=leela_config.get("loss_scale_k", LEELA_K_DEFAULT),
        step=0.1,
        size_hint_x=0.50,
    )
    leela_k_value_label = Label(
        text=f"{leela_k_slider.value:.1f}",
        size_hint_x=0.20,
        halign="center",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_k_slider.bind(
        value=lambda inst, val: setattr(leela_k_value_label, "text", f"{val:.1f}")
    )
    leela_k_row.add_widget(leela_k_label)
    leela_k_row.add_widget(leela_k_slider)
    leela_k_row.add_widget(leela_k_value_label)
    tab3_inner.add_widget(leela_k_row)
    register_searchable(i18n._("mykatrain:settings:leela_k_value"), leela_k_row)

    # Leela Max Visits
    leela_visits_row = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10)
    )
    leela_visits_label = Label(
        text=i18n._("mykatrain:settings:leela_max_visits"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_visits_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    leela_visits_input = TextInput(
        text=str(leela_config.get("max_visits", 1000)),
        multiline=False,
        input_filter="int",
        size_hint_x=0.70,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_visits_row.add_widget(leela_visits_label)
    leela_visits_row.add_widget(leela_visits_input)
    tab3_inner.add_widget(leela_visits_row)
    register_searchable(i18n._("mykatrain:settings:leela_max_visits"), leela_visits_row)

    # Leela Fast Visits (Phase 30)
    leela_fast_visits_row = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10)
    )
    leela_fast_visits_label = Label(
        text=i18n._("mykatrain:settings:leela_fast_visits"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_fast_visits_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    leela_fast_visits_input = TextInput(
        text=str(leela_config.get("fast_visits", 200)),
        multiline=False,
        input_filter="int",
        size_hint_x=0.70,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_fast_visits_row.add_widget(leela_fast_visits_label)
    leela_fast_visits_row.add_widget(leela_fast_visits_input)
    tab3_inner.add_widget(leela_fast_visits_row)
    register_searchable(
        i18n._("mykatrain:settings:leela_fast_visits"), leela_fast_visits_row
    )

    # Leela Play Visits (Phase 40)
    leela_play_visits_row = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10)
    )
    leela_play_visits_label = Label(
        text=i18n._("mykatrain:settings:leela_play_visits"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_play_visits_label.bind(
        size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    leela_play_visits_input = TextInput(
        text=str(leela_config.get("play_visits", 500)),
        multiline=False,
        input_filter="int",
        size_hint_x=0.70,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_play_visits_row.add_widget(leela_play_visits_label)
    leela_play_visits_row.add_widget(leela_play_visits_input)
    tab3_inner.add_widget(leela_play_visits_row)
    register_searchable(
        i18n._("mykatrain:settings:leela_play_visits"), leela_play_visits_row
    )

    # Leela Top Moves Display
    leela_top_moves_row = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10)
    )
    leela_top_moves_label = Label(
        text=i18n._("mykatrain:settings:leela_top_moves_show"),
        size_hint_x=0.30,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    leela_top_moves_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )

    leela_top_moves_spinner = I18NSpinner(size_hint_x=0.35)
    leela_top_moves_spinner.value_refs = LEELA_TOP_MOVE_OPTIONS
    leela_top_moves_spinner.build_values()
    leela_top_moves_spinner.select_key(
        leela_config.get("top_moves_show", "leela_top_move_loss")
    )

    leela_top_moves_spinner_2 = I18NSpinner(size_hint_x=0.35)
    leela_top_moves_spinner_2.value_refs = LEELA_TOP_MOVE_OPTIONS_SECONDARY
    leela_top_moves_spinner_2.build_values()
    leela_top_moves_spinner_2.select_key(
        leela_config.get("top_moves_show_secondary", "leela_top_move_winrate")
    )

    leela_top_moves_row.add_widget(leela_top_moves_label)
    leela_top_moves_row.add_widget(leela_top_moves_spinner)
    leela_top_moves_row.add_widget(leela_top_moves_spinner_2)
    tab3_inner.add_widget(leela_top_moves_row)
    register_searchable(i18n._("mykatrain:settings:leela_top_moves_show"), leela_top_moves_row)

    # Reset button for Leela tab (Phase 27)
    tab3_reset_btn = Button(
        text=i18n._("mykatrain:settings:reset"),
        size_hint_y=None,
        height=dp(36),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    tab3_inner.add_widget(tab3_reset_btn)

    # === Tab 4: Auto Setup (Phase 89) ===
    tab4 = TabbedPanelItem(text=i18n._("mykatrain:settings:tab_auto"))
    tab4_inner = BoxLayout(
        orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None
    )
    tab4_inner.bind(minimum_height=tab4_inner.setter("height"))

    # Auto Setup content will be rendered by show_auto_mode_content()
    # We need access to katrain instance for engine operations
    # The ctx provides access via ctx._katrain (internal, but necessary)
    from katrain.gui.features.auto_mode_popup import show_auto_mode_content

    # Get katrain instance from ctx (FeatureContext is actually KaTrainGui)
    katrain_instance = ctx  # ctx IS the KaTrainGui instance

    # Build Auto Mode content
    show_auto_mode_content(ctx, tab4_inner, katrain_instance)

    # Wrap in ScrollView like other tabs
    tab4_scroll = ScrollView(do_scroll_x=False)
    tab4_scroll.add_widget(tab4_inner)
    tab4.add_widget(tab4_scroll)

    # Buttons (outside TabbedPanel)
    buttons_layout = BoxLayout(
        orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48)
    )
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

    # Assemble tabs
    tab1_scroll.add_widget(tab1_inner)
    tab1.add_widget(tab1_scroll)
    tabbed_panel.add_widget(tab1)

    tab2_scroll.add_widget(tab2_inner)
    tab2.add_widget(tab2_scroll)
    tabbed_panel.add_widget(tab2)

    tab3_scroll.add_widget(tab3_inner)
    tab3.add_widget(tab3_scroll)
    tabbed_panel.add_widget(tab3)

    # Phase 89: Add Auto Setup tab
    tabbed_panel.add_widget(tab4)

    # Phase 87.5 + Phase 89: Tab lookup dictionary
    tab_by_id = {
        "analysis": tab1,
        "export": tab2,
        "leela": tab3,
        "auto": tab4,  # Phase 89
    }

    # Phase 89: Determine if Auto tab should be shown first
    # Conditions: mode == "auto" AND first_run_completed == False
    auto_setup_config = ctx.config("auto_setup") or {}
    show_auto_first = should_show_auto_tab_first(auto_setup_config)

    # Phase 87.5 + Phase 89: Switch to initial_tab if specified, or auto if conditions met
    if initial_tab and initial_tab in tab_by_id:
        from kivy.clock import Clock
        target_tab = tab_by_id[initial_tab]
        Clock.schedule_once(lambda dt: tabbed_panel.switch_to(target_tab), 0.1)
    elif show_auto_first:
        # Phase 89: Auto tab first for new users
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: tabbed_panel.switch_to(tab4), 0.1)

    # Set default tab to tab1 (Analysis) or tab4 (Auto) based on conditions
    tabbed_panel.default_tab = tab4 if show_auto_first else tab1

    # Apply Japanese-capable font to tab headers (fix tofu rendering)
    # TabbedPanelHeader may not have font_name directly accessible;
    # schedule after construction to ensure widgets are ready.
    from kivy.clock import Clock

    def _set_tab_fonts(dt: float) -> None:
        for tab in tabbed_panel.tab_list:
            # Try public font_name first (TabbedPanelHeader)
            if hasattr(tab, "font_name"):
                tab.font_name = Theme.DEFAULT_FONT
            # Guarded fallback for internal _label if present
            if hasattr(tab, "_label") and tab._label:
                tab._label.font_name = Theme.DEFAULT_FONT

    Clock.schedule_once(_set_tab_fonts, 0)

    # Assemble main layout
    main_layout.add_widget(search_layout)
    main_layout.add_widget(tabbed_panel)
    main_layout.add_widget(buttons_layout)

    popup = I18NPopup(
        title_key="mykatrain:settings",
        size=[dp(900), dp(700)],
        content=main_layout,
    ).__self__

    # Save callback
    def save_settings(*_args: Any) -> None:
        # Save skill preset and pv_filter_level to general config
        general = ctx.config("general") or {}
        general["skill_preset"] = selected_skill_preset[0]
        general["pv_filter_level"] = selected_pv_filter[0]
        ctx.set_config_section("general", general)
        ctx.save_config("general")

        # Phase 91: Save beginner_hints enabled state
        beginner_hints_config = ctx.config("beginner_hints") or {}
        beginner_hints_config["enabled"] = selected_beginner_hints[0]
        ctx.set_config_section("beginner_hints", beginner_hints_config)
        ctx.save_config("beginner_hints")

        # [Phase 34] Capture UI state early for consistency (with defensive fallback)
        leela_will_be_enabled = getattr(leela_enabled_checkbox, "active", None)
        if leela_will_be_enabled is None:
            # Fallback to config if checkbox not available (future-proofing)
            leela_will_be_enabled = (ctx.config("leela") or {}).get("enabled", False)

        # [Phase 34] Save analysis engine to engine config (MERGE pattern)
        from katrain.core.analysis import needs_leela_warning
        import logging

        new_engine_value = selected_engine[0]

        # Consistency check: warn if Leela selected but not enabled
        if needs_leela_warning(new_engine_value, leela_will_be_enabled):
            ctx.controls.set_status(
                i18n._("mykatrain:settings:engine_leela_not_enabled_warning"),
                STATUS_INFO,  # Note: STATUS_WARNING does not exist in constants.py
            )

        # MERGE: preserve other engine keys (katago, model, etc.)
        # Phase 102: Use typed config API
        try:
            ctx.update_engine_config(analysis_engine=new_engine_value)
        except OSError as e:
            # File write failure during engine config save
            logging.error(f"Failed to save engine config (file error): {e}", exc_info=True)
            ctx.controls.set_status(
                i18n._("mykatrain:settings:engine_save_error"),
                STATUS_ERROR,
            )
            # Continue with other saves (partial save is better than nothing)
        except Exception as e:
            # Boundary fallback: unexpected error (config structure issue, etc.)
            logging.error(f"Failed to save engine config (unexpected): {e}", exc_info=True)
            ctx.controls.set_status(
                i18n._("mykatrain:settings:engine_save_error"),
                STATUS_ERROR,
            )
            # Continue with other saves (partial save is better than nothing)

        # Save mykatrain settings
        mykatrain_settings = {
            "default_user_name": user_input.text,
            "karte_output_directory": output_input.text,
            "batch_export_input_directory": input_input.text,
            "karte_format": selected_format[0],
            "opponent_info_mode": selected_opp_info[0],
        }
        ctx.set_config_section("mykatrain_settings", mykatrain_settings)
        ctx.save_config("mykatrain_settings")
        # Save Leela settings (Phase 102: Use typed config API)
        # TypedConfigWriter automatically preserves unknown keys (resign_hint_* etc.)
        from katrain.common.typed_config import LeelaConfig
        from katrain.core.analysis.models import LEELA_FAST_VISITS_MIN

        # Get defaults from single source (no hardcoding)
        _leela_defaults = LeelaConfig.from_dict({})

        # Calculate values with validation
        leela_enabled = leela_will_be_enabled
        leela_exe_path = leela_path_input.text.strip()
        leela_loss_scale = clamp_k(leela_k_slider.value)
        leela_top_show = leela_top_moves_spinner.selected[1]
        leela_top_show_2 = leela_top_moves_spinner_2.selected[1]

        # max_visits: parse with validation
        try:
            computed_max_visits = max(100, min(100000, int(leela_visits_input.text)))
        except ValueError:
            computed_max_visits = _leela_defaults.max_visits

        # fast_visits: parse with validation (Phase 30)
        try:
            fast_visits_raw = int(leela_fast_visits_input.text.strip())
            # UI Validation:
            # - 下限: LEELA_FAST_VISITS_MIN (50) または max_visits のうち小さい方
            # - 上限: max_visits
            # エッジケース: max_visits < 50 の場合、fast_visits も max_visits に制限
            lower_bound = min(LEELA_FAST_VISITS_MIN, computed_max_visits)
            computed_fast_visits = max(lower_bound, min(computed_max_visits, fast_visits_raw))
        except ValueError:
            computed_fast_visits = _leela_defaults.fast_visits

        # play_visits: parse with validation (Phase 40)
        try:
            play_visits_raw = int(leela_play_visits_input.text.strip())
            computed_play_visits = max(50, min(computed_max_visits, play_visits_raw))
        except ValueError:
            computed_play_visits = _leela_defaults.play_visits

        # Update via typed config API (handles MERGE and persistence)
        ctx.update_leela_config(
            enabled=leela_enabled,
            exe_path=leela_exe_path,
            loss_scale_k=leela_loss_scale,
            max_visits=computed_max_visits,
            top_moves_show=leela_top_show,
            top_moves_show_secondary=leela_top_show_2,
            fast_visits=computed_fast_visits,
            play_visits=computed_play_visits,
        )
        ctx.controls.set_status(i18n._("Settings saved"), STATUS_INFO)
        popup.dismiss()

    # Directory browse callbacks
    def browse_output(*_args: Any) -> None:
        from katrain.gui.popups import LoadSGFPopup

        browse_popup_content = LoadSGFPopup(ctx)
        browse_popup_content.filesel.dirselect = True
        browse_popup_content.filesel.select_string = "Select This Folder"
        if output_input.text and os.path.isdir(output_input.text):
            browse_popup_content.filesel.path = os.path.abspath(output_input.text)

        browse_popup = Popup(
            title="Select folder - Navigate into target folder, then click 'Select This Folder'",
            size_hint=(0.8, 0.8),
            content=browse_popup_content,
        ).__self__

        def on_select(*_args: Any) -> None:
            output_input.text = browse_popup_content.filesel.file_text.text
            browse_popup.dismiss()

        browse_popup_content.filesel.bind(on_success=on_select)
        browse_popup.open()

    def browse_input(*_args: Any) -> None:
        from katrain.gui.popups import LoadSGFPopup

        browse_popup_content = LoadSGFPopup(ctx)
        browse_popup_content.filesel.dirselect = True
        browse_popup_content.filesel.select_string = "Select This Folder"
        if input_input.text and os.path.isdir(input_input.text):
            browse_popup_content.filesel.path = os.path.abspath(input_input.text)

        browse_popup = Popup(
            title="Select folder - Navigate into target folder, then click 'Select This Folder'",
            size_hint=(0.8, 0.8),
            content=browse_popup_content,
        ).__self__

        def on_select(*_args: Any) -> None:
            input_input.text = browse_popup_content.filesel.file_text.text
            browse_popup.dismiss()

        browse_popup_content.filesel.bind(on_success=on_select)
        browse_popup.open()

    def browse_leela_exe(*_args: Any) -> None:
        from katrain.gui.popups import LoadSGFPopup

        browse_popup_content = LoadSGFPopup(ctx)
        browse_popup_content.filesel.dirselect = False  # File selection
        browse_popup_content.filesel.filters = ["*.exe"]  # Windows exe
        browse_popup_content.filesel.select_string = "Select"
        if leela_path_input.text and os.path.isfile(leela_path_input.text):
            browse_popup_content.filesel.path = os.path.dirname(
                os.path.abspath(leela_path_input.text)
            )

        browse_popup = Popup(
            title="Select Leela Zero executable",
            size_hint=(0.8, 0.8),
            content=browse_popup_content,
        ).__self__

        def on_select(*_args: Any) -> None:
            selected = browse_popup_content.filesel.file_text.text
            if selected and os.path.isfile(selected):
                leela_path_input.text = selected
            browse_popup.dismiss()

        browse_popup_content.filesel.bind(on_success=on_select)
        browse_popup.open()

    save_button.bind(on_release=save_settings)
    cancel_button.bind(on_release=lambda *_args: popup.dismiss())
    output_browse.bind(on_release=browse_output)
    input_browse.bind(on_release=browse_input)
    leela_path_browse.bind(on_release=browse_leela_exe)

    # Export/Import button bindings (Phase 27)
    export_button.bind(
        on_release=lambda *_args: _do_export_settings(ctx, popup)
    )
    import_button.bind(
        on_release=lambda *_args: _do_import_settings(ctx, popup, reopen_popup)
    )

    # Reset button bindings (Phase 27)
    tab1_reset_btn.bind(
        on_release=lambda *_args: _reset_tab_settings(ctx, "analysis", popup, reopen_popup)
    )
    tab2_reset_btn.bind(
        on_release=lambda *_args: _reset_tab_settings(ctx, "export", popup, reopen_popup)
    )
    tab3_reset_btn.bind(
        on_release=lambda *_args: _reset_tab_settings(ctx, "leela", popup, reopen_popup)
    )

    popup.open()
