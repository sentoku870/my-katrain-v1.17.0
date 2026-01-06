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
from kivy.uix.textinput import TextInput

from katrain.core import eval_metrics
from katrain.core.constants import STATUS_INFO
from katrain.core.lang import i18n
from katrain.gui.popups import I18NPopup
from katrain.gui.theme import Theme

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

    # ScrollView でコンテンツをスクロール可能に
    scroll_view = ScrollView(size_hint=(1, 1))
    popup_content = BoxLayout(
        orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None
    )
    popup_content.bind(minimum_height=popup_content.setter("height"))

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
    popup_content.add_widget(skill_label)

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
    popup_content.add_widget(skill_layout)

    # Default User Name
    user_row = BoxLayout(
        orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10)
    )
    user_label = Label(
        text=i18n._("mykatrain:settings:default_user_name"),
        size_hint_x=0.35,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    user_label.bind(
        size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height))
    )
    user_input = TextInput(
        text=current_settings.get("default_user_name", ""),
        multiline=False,
        size_hint_x=0.65,
        font_name=Theme.DEFAULT_FONT,
    )
    user_row.add_widget(user_label)
    user_row.add_widget(user_input)
    popup_content.add_widget(user_row)

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
    popup_content.add_widget(output_row)

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
    popup_content.add_widget(input_row)

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
    popup_content.add_widget(format_label)

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

    popup_content.add_widget(format_layout)

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
    popup_content.add_widget(opp_info_label)

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
    popup_content.add_widget(opp_info_layout)

    # Buttons
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
    popup_content.add_widget(buttons_layout)

    scroll_view.add_widget(popup_content)

    popup = I18NPopup(
        title_key="mykatrain:settings",
        size=[dp(900), dp(700)],
        content=scroll_view,
    ).__self__

    # Save callback
    def save_settings(*_args):
        # Save skill preset to general config
        general = ctx.config("general") or {}
        general["skill_preset"] = selected_skill_preset[0]
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

    save_button.bind(on_release=save_settings)
    cancel_button.bind(on_release=lambda *_args: popup.dismiss())
    output_browse.bind(on_release=browse_output)
    input_browse.bind(on_release=browse_input)

    popup.open()
