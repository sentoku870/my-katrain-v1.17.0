# katrain/gui/features/settings_popup.py
#
# 設定ポップアップ機能モジュール
#
# __main__.py から抽出した設定関連の関数を配置します。
# - load_export_settings: エクスポート設定の読み込み
# - save_export_settings: エクスポート設定の保存
# - save_batch_options: バッチオプションの保存
# - do_mykatrain_settings_popup: myKatrain設定ポップアップの表示

import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

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

from katrain.core import eval_metrics
from katrain.core.constants import (
    LEELA_K_DEFAULT,
    LEELA_K_MAX,
    LEELA_K_MIN,
    LEELA_TOP_MOVE_OPTIONS,
    LEELA_TOP_MOVE_OPTIONS_SECONDARY,
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


def load_export_settings(ctx: "FeatureContext") -> Dict[str, Any]:
    """エクスポート設定を読み込む

    Args:
        ctx: FeatureContext providing config

    Returns:
        エクスポート設定辞書
    """
    return ctx.config("export_settings") or {}


def save_export_settings(
    ctx: "FeatureContext",
    sgf_directory: Optional[str] = None,
    selected_players: Optional[List[str]] = None,
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


def save_batch_options(ctx: "FeatureContext", options: Dict[str, Any]) -> None:
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


def do_mykatrain_settings_popup(ctx: "FeatureContext") -> None:
    """myKatrain設定ポップアップを表示

    Args:
        ctx: FeatureContext providing config, save_config, controls
    """
    current_settings = ctx.config("mykatrain_settings") or {}

    # Main layout: TabbedPanel + Buttons
    main_layout = BoxLayout(orientation="vertical", spacing=dp(8))

    # TabbedPanel with 3 tabs
    tabbed_panel = TabbedPanel(
        do_default_tab=False,
        tab_width=dp(120),
        tab_height=dp(40),
        size_hint_y=0.9,
    )

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

    # Default User Name
    user_row, user_input, _ = create_text_input_row(
        label_text=i18n._("mykatrain:settings:default_user_name"),
        initial_value=current_settings.get("default_user_name", ""),
    )
    tab2_inner.add_widget(user_row)

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

    # === Leela Zero Settings Section ===
    # Note: Section label is no longer needed as it's now a separate tab

    # Leela Enabled Checkbox
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

    # Buttons (outside TabbedPanel)
    buttons_layout = BoxLayout(
        orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48)
    )
    save_button = Button(
        text=i18n._("Save"),
        size_hint_x=0.5,
        height=dp(48),
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    cancel_button = Button(
        text=i18n._("Cancel"),
        size_hint_x=0.5,
        height=dp(48),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
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

    # Set default tab to tab1 (Analysis)
    tabbed_panel.default_tab = tab1

    # Assemble main layout
    main_layout.add_widget(tabbed_panel)
    main_layout.add_widget(buttons_layout)

    popup = I18NPopup(
        title_key="mykatrain:settings",
        size=[dp(900), dp(700)],
        content=main_layout,
    ).__self__

    # Save callback
    def save_settings(*_args):
        # Save skill preset and pv_filter_level to general config
        general = ctx.config("general") or {}
        general["skill_preset"] = selected_skill_preset[0]
        general["pv_filter_level"] = selected_pv_filter[0]
        ctx.set_config_section("general", general)
        ctx.save_config("general")
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
        # Save Leela settings (MERGE with existing to preserve resign_hint settings)
        existing_leela = ctx.config("leela") or {}
        new_leela_config = {
            **existing_leela,  # 既存設定を保持（resign_hint_*等）
            "enabled": leela_enabled_checkbox.active,
            "exe_path": leela_path_input.text.strip(),
            "loss_scale_k": clamp_k(leela_k_slider.value),
            "max_visits": 1000,  # default, overwritten below
            "top_moves_show": leela_top_moves_spinner.selected[1],
            "top_moves_show_secondary": leela_top_moves_spinner_2.selected[1],
        }
        try:
            new_leela_config["max_visits"] = max(100, min(100000, int(leela_visits_input.text)))
        except ValueError:
            pass  # use default
        ctx.set_config_section("leela", new_leela_config)
        ctx.save_config("leela")
        ctx.controls.set_status(i18n._("Settings saved"), STATUS_INFO)
        popup.dismiss()

    # Directory browse callbacks
    def browse_output(*_args):
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

        def on_select(*_args):
            output_input.text = browse_popup_content.filesel.file_text.text
            browse_popup.dismiss()

        browse_popup_content.filesel.bind(on_success=on_select)
        browse_popup.open()

    def browse_input(*_args):
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

        def on_select(*_args):
            input_input.text = browse_popup_content.filesel.file_text.text
            browse_popup.dismiss()

        browse_popup_content.filesel.bind(on_success=on_select)
        browse_popup.open()

    def browse_leela_exe(*_args):
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

        def on_select(*_args):
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

    popup.open()
