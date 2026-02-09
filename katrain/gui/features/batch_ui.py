# katrain/gui/features/batch_ui.py
#
# バッチ解析UIモジュール
#
# __main__.py から抽出したバッチ解析UIの配線・コールバックを配置します。
# - create_browse_callback: フォルダ選択ブラウズコールバック作成
# - create_on_start_callback: 開始ボタンコールバック作成
# - create_on_close_callback: 閉じるボタンコールバック作成
# - build_batch_popup_widgets: バッチポップアップのウィジェット構築

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

from katrain.core.batch import DEFAULT_TIMEOUT_SECONDS
from katrain.core.constants import STATUS_ERROR
from katrain.core.lang import i18n
from katrain.gui.features.types import BatchOptions, BatchWidgets
from katrain.gui.popups import I18NPopup
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def create_browse_callback(
    text_input_widget: Any,
    title: str,
    katrain_gui: Any,
) -> Callable[..., None]:
    """フォルダ選択ブラウズコールバックを作成

    Args:
        text_input_widget: パス入力用TextInputウィジェット
        title: ポップアップタイトル
        katrain_gui: KaTrainGuiインスタンス（LoadSGFPopup用）

    Returns:
        ブラウズコールバック関数
    """

    def browse_callback(*_args: Any) -> None:
        from katrain.gui.popups import LoadSGFPopup

        browse_popup_content = LoadSGFPopup(katrain_gui)
        browse_popup_content.filesel.dirselect = True
        browse_popup_content.filesel.select_string = "Select This Folder"

        current_path = text_input_widget.text.strip()
        if current_path and os.path.isdir(current_path):
            browse_popup_content.filesel.path = os.path.abspath(current_path)

        browse_popup = Popup(
            title=title,
            size_hint=(0.8, 0.8),
            content=browse_popup_content,
        ).__self__

        def on_select(*_args: Any) -> None:
            text_input_widget.text = browse_popup_content.filesel.file_text.text
            browse_popup.dismiss()

        browse_popup_content.filesel.bind(on_success=on_select)
        browse_popup.open()

    return browse_callback


def create_on_start_callback(
    ctx: FeatureContext,
    widgets: BatchWidgets,
    is_running: list[bool],
    cancel_flag: list[bool],
    get_player_filter_fn: Callable[[], str | None],
    run_batch_thread_fn: Callable[[], None],
) -> Callable[..., None]:
    """開始ボタンコールバックを作成

    Args:
        ctx: FeatureContext providing controls, engine
        widgets: ウィジェット辞書
        is_running: 実行中フラグ（リストで参照渡し）
        cancel_flag: キャンセルフラグ（リストで参照渡し）
        get_player_filter_fn: プレイヤーフィルター取得関数
        run_batch_thread_fn: バッチスレッド実行関数

    Returns:
        開始ボタンコールバック関数
    """

    def on_start(*_args: Any) -> None:
        if is_running[0]:
            # Cancel
            cancel_flag[0] = True
            widgets["start_button"].text = i18n._("mykatrain:batch:cancelling")
            widgets["start_button"].disabled = True
            return

        # Validate input
        input_dir = widgets["input_input"].text.strip()
        if not input_dir or not os.path.isdir(input_dir):
            ctx.controls.set_status(i18n._("mykatrain:batch:error_input_dir"), STATUS_ERROR)
            return

        # Check engine
        engine = getattr(ctx, "engine", None)
        if not engine:
            ctx.controls.set_status(i18n._("mykatrain:batch:error_no_engine"), STATUS_ERROR)
            return

        # Check engine is alive (Phase 95B)
        if not engine.check_alive():
            ctx.controls.set_status(i18n._("mykatrain:batch:error_engine_dead"), STATUS_ERROR)
            return

        # Start
        is_running[0] = True
        cancel_flag[0] = False
        widgets["start_button"].text = i18n._("mykatrain:batch:cancel")
        widgets["start_button"].disabled = False
        widgets["close_button"].disabled = True
        widgets["log_text"].text = ""
        widgets["progress_label"].text = i18n._("mykatrain:batch:starting")

        threading.Thread(target=run_batch_thread_fn, daemon=True).start()

    return on_start


def create_on_close_callback(
    popup: Any,
    is_running: list[bool],
) -> Callable[..., None]:
    """閉じるボタンコールバックを作成

    Args:
        popup: ポップアップウィジェット
        is_running: 実行中フラグ（リストで参照渡し）

    Returns:
        閉じるボタンコールバック関数
    """

    def on_close(*_args: Any) -> None:
        if is_running[0]:
            return  # Don't close while running
        popup.dismiss()

    return on_close


def create_get_player_filter_fn(
    filter_buttons: BatchWidgets,
) -> Callable[[], str | None]:
    """プレイヤーフィルター取得関数を作成

    Args:
        filter_buttons: フィルターボタン辞書（filter_black, filter_white, filter_both）

    Returns:
        プレイヤーフィルター取得関数
    """

    def get_player_filter() -> str | None:
        if filter_buttons["filter_black"].state == "down":
            return "B"
        elif filter_buttons["filter_white"].state == "down":
            return "W"
        return None  # Both = no filter

    return get_player_filter


def build_batch_popup_widgets(
    batch_options: BatchOptions,
    default_input_dir: str,
    default_output_dir: str,
) -> tuple[BoxLayout, BatchWidgets]:
    """バッチポップアップのウィジェットを構築

    Args:
        batch_options: バッチオプション辞書（永続化された設定）
        default_input_dir: デフォルト入力ディレクトリ
        default_output_dir: デフォルト出力ディレクトリ
        leela_enabled: Leela解析が有効かどうか

    Returns:
        (main_layout, widgets_dict) タプル
        widgets_dict には以下のキーが含まれる:
        - input_input, output_input: ディレクトリ入力
        - input_browse, output_browse: ブラウズボタン
        - visits_input, timeout_input: オプション入力
        - skip_checkbox, save_sgf_checkbox, karte_checkbox, summary_checkbox: チェックボックス
        - filter_both, filter_black, filter_white: フィルターボタン
        - min_games_input, jitter_input: 数値入力
        - variable_visits_checkbox, deterministic_checkbox, sound_checkbox: チェックボックス
        - progress_label, log_text, log_scroll: 進行状況表示
        - start_button, close_button: ボタン
    """
    widgets: BatchWidgets = {}

    # Main layout
    main_layout = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))

    # Input directory row
    input_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    input_label = Label(
        text=i18n._("mykatrain:batch:input_dir"),
        size_hint_x=0.25,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    input_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    widgets["input_input"] = TextInput(
        text=default_input_dir,
        multiline=False,
        size_hint_x=0.6,
        font_name=Theme.DEFAULT_FONT,
    )
    widgets["input_browse"] = Button(
        text=i18n._("Browse..."),
        size_hint_x=0.15,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    input_row.add_widget(input_label)
    input_row.add_widget(widgets["input_input"])
    input_row.add_widget(widgets["input_browse"])
    main_layout.add_widget(input_row)

    # Output directory row
    output_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
    output_label = Label(
        text=i18n._("mykatrain:batch:output_dir"),
        size_hint_x=0.25,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    output_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    widgets["output_input"] = TextInput(
        text=default_output_dir,
        hint_text=i18n._("mykatrain:batch:output_hint"),
        multiline=False,
        size_hint_x=0.6,
        font_name=Theme.DEFAULT_FONT,
    )
    widgets["output_browse"] = Button(
        text=i18n._("Browse..."),
        size_hint_x=0.15,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    output_row.add_widget(output_label)
    output_row.add_widget(widgets["output_input"])
    output_row.add_widget(widgets["output_browse"])
    main_layout.add_widget(output_row)

    # Options row 1: visits and timeout
    options_row1 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))

    saved_visits = batch_options.get("visits")
    visits_label = Label(
        text=i18n._("mykatrain:batch:visits"),
        size_hint_x=0.15,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    visits_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    widgets["visits_input"] = TextInput(
        text=str(saved_visits) if saved_visits else "",
        hint_text=i18n._("mykatrain:batch:visits_hint"),
        multiline=False,
        input_filter="int",
        size_hint_x=0.2,
        font_name=Theme.DEFAULT_FONT,
    )

    saved_timeout = batch_options.get("timeout", DEFAULT_TIMEOUT_SECONDS)
    timeout_display = "None" if saved_timeout is None else str(int(saved_timeout))
    timeout_label = Label(
        text=i18n._("mykatrain:batch:timeout"),
        size_hint_x=0.2,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    timeout_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    widgets["timeout_input"] = TextInput(
        text=timeout_display,
        multiline=False,
        size_hint_x=0.15,
        font_name=Theme.DEFAULT_FONT,
    )

    options_row1.add_widget(visits_label)
    options_row1.add_widget(widgets["visits_input"])
    options_row1.add_widget(Label(size_hint_x=0.1))  # spacer
    options_row1.add_widget(timeout_label)
    options_row1.add_widget(widgets["timeout_input"])
    options_row1.add_widget(Label(size_hint_x=0.2))  # spacer
    main_layout.add_widget(options_row1)

    # Options row 2: skip analyzed checkbox
    options_row2 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(10))

    widgets["skip_checkbox"] = CheckBox(active=batch_options.get("skip_analyzed", True), size_hint_x=None, width=dp(30))
    skip_label = Label(
        text=i18n._("mykatrain:batch:skip_analyzed"),
        size_hint_x=0.4,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    skip_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    options_row2.add_widget(widgets["skip_checkbox"])
    options_row2.add_widget(skip_label)
    options_row2.add_widget(Label(size_hint_x=0.5))  # spacer
    main_layout.add_widget(options_row2)

    # Phase 44: Skip analyzed hint row
    skip_hint_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(18), spacing=dp(10))
    skip_hint_row.add_widget(Label(size_hint_x=None, width=dp(30)))  # spacer to align with checkbox
    skip_hint_label = Label(
        text=i18n._("mykatrain:batch:skip_analyzed_hint"),
        size_hint_x=0.9,
        halign="left",
        valign="middle",
        color=[0.5, 0.5, 0.5, 1],  # gray text
        font_size=sp(10),
        font_name=Theme.DEFAULT_FONT,
    )
    skip_hint_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    skip_hint_row.add_widget(skip_hint_label)
    main_layout.add_widget(skip_hint_row)

    # Options row 3: output options (save SGF, karte, summary, curator)
    options_row3 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(5))

    widgets["save_sgf_checkbox"] = CheckBox(
        active=batch_options.get("save_analyzed_sgf", False), size_hint_x=None, width=dp(30)
    )
    save_sgf_label = Label(
        text=i18n._("mykatrain:batch:save_analyzed_sgf"),
        size_hint_x=0.25,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    save_sgf_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    widgets["karte_checkbox"] = CheckBox(
        active=batch_options.get("generate_karte", True), size_hint_x=None, width=dp(30)
    )
    karte_label = Label(
        text=i18n._("mykatrain:batch:generate_karte"),
        size_hint_x=0.25,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    karte_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    widgets["summary_checkbox"] = CheckBox(
        active=batch_options.get("generate_summary", True), size_hint_x=None, width=dp(30)
    )
    summary_label = Label(
        text=i18n._("mykatrain:batch:generate_summary"),
        size_hint_x=0.25,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    summary_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    widgets["curator_checkbox"] = CheckBox(
        active=batch_options.get("generate_curator", False), size_hint_x=None, width=dp(30)
    )
    curator_label = Label(
        text=i18n._("mykatrain:batch:generate_curator"),
        size_hint_x=0.25,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    curator_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    options_row3.add_widget(widgets["save_sgf_checkbox"])
    options_row3.add_widget(save_sgf_label)
    options_row3.add_widget(widgets["karte_checkbox"])
    options_row3.add_widget(karte_label)
    options_row3.add_widget(widgets["summary_checkbox"])
    options_row3.add_widget(summary_label)
    options_row3.add_widget(widgets["curator_checkbox"])
    options_row3.add_widget(curator_label)
    main_layout.add_widget(options_row3)


    # Options row 4: Player filter and min games
    options_row4 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(5))

    player_filter_label = Label(
        text=i18n._("mykatrain:batch:player_filter"),
        size_hint_x=0.18,
        halign="right",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    player_filter_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    saved_filter = batch_options.get("karte_player_filter")

    widgets["filter_both"] = ToggleButton(
        text=i18n._("mykatrain:batch:filter_both"),
        group="player_filter",
        state="down" if saved_filter is None else "normal",
        size_hint_x=0.12,
        font_name=Theme.DEFAULT_FONT,
    )
    widgets["filter_black"] = ToggleButton(
        text=i18n._("mykatrain:batch:filter_black"),
        group="player_filter",
        state="down" if saved_filter == "B" else "normal",
        size_hint_x=0.12,
        font_name=Theme.DEFAULT_FONT,
    )
    widgets["filter_white"] = ToggleButton(
        text=i18n._("mykatrain:batch:filter_white"),
        group="player_filter",
        state="down" if saved_filter == "W" else "normal",
        size_hint_x=0.12,
        font_name=Theme.DEFAULT_FONT,
    )

    min_games_label = Label(
        text=i18n._("mykatrain:batch:min_games"),
        size_hint_x=0.18,
        halign="right",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    min_games_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    widgets["min_games_input"] = TextInput(
        text=str(batch_options.get("min_games_per_player", 3)),
        multiline=False,
        input_filter="int",
        size_hint_x=0.1,
        font_name=Theme.DEFAULT_FONT,
    )

    options_row4.add_widget(player_filter_label)
    options_row4.add_widget(widgets["filter_both"])
    options_row4.add_widget(widgets["filter_black"])
    options_row4.add_widget(widgets["filter_white"])
    options_row4.add_widget(min_games_label)
    options_row4.add_widget(widgets["min_games_input"])
    options_row4.add_widget(Label(size_hint_x=0.18))  # spacer
    main_layout.add_widget(options_row4)

    # Options row 5: Variable Visits and Sound on finish
    options_row5 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(5))

    widgets["variable_visits_checkbox"] = CheckBox(
        active=batch_options.get("variable_visits", False), size_hint_x=None, width=dp(30)
    )
    variable_visits_label = Label(
        text=i18n._("mykatrain:batch:variable_visits"),
        size_hint_x=0.18,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    variable_visits_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    jitter_label = Label(
        text=i18n._("mykatrain:batch:jitter_pct"),
        size_hint_x=0.1,
        halign="right",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    jitter_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    widgets["jitter_input"] = TextInput(
        text=str(batch_options.get("jitter_pct", 10)),
        multiline=False,
        input_filter="int",
        size_hint_x=0.08,
        font_name=Theme.DEFAULT_FONT,
    )

    widgets["deterministic_checkbox"] = CheckBox(
        active=batch_options.get("deterministic", True), size_hint_x=None, width=dp(30)
    )
    deterministic_label = Label(
        text=i18n._("mykatrain:batch:deterministic"),
        size_hint_x=0.15,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    deterministic_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    widgets["sound_checkbox"] = CheckBox(
        active=batch_options.get("sound_on_finish", False), size_hint_x=None, width=dp(30)
    )
    sound_label = Label(
        text=i18n._("mykatrain:batch:sound_on_finish"),
        size_hint_x=0.18,
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    sound_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    options_row5.add_widget(widgets["variable_visits_checkbox"])
    options_row5.add_widget(variable_visits_label)
    options_row5.add_widget(jitter_label)
    options_row5.add_widget(widgets["jitter_input"])
    options_row5.add_widget(widgets["deterministic_checkbox"])
    options_row5.add_widget(deterministic_label)
    options_row5.add_widget(widgets["sound_checkbox"])
    options_row5.add_widget(sound_label)
    main_layout.add_widget(options_row5)

    # Phase 87.5: Variable visits linkage - enable/disable Jitter% and Deterministic
    def update_variable_visits_controls(*_args: Any) -> None:
        checkbox = widgets["variable_visits_checkbox"]
        is_variable = getattr(checkbox, "active", False)
        widgets["jitter_input"].disabled = not is_variable
        widgets["deterministic_checkbox"].disabled = not is_variable

    widgets["variable_visits_checkbox"].bind(active=update_variable_visits_controls)
    update_variable_visits_controls()  # Set initial state

    # Progress row
    progress_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30), spacing=dp(10))
    widgets["progress_label"] = Label(
        text=i18n._("mykatrain:batch:ready"),
        halign="left",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    widgets["progress_label"].bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    progress_row.add_widget(widgets["progress_label"])
    main_layout.add_widget(progress_row)

    # Log area (scrollable)
    widgets["log_scroll"] = ScrollView(size_hint=(1, 1))
    widgets["log_text"] = TextInput(
        text="",
        multiline=True,
        readonly=True,
        size_hint_y=None,
        font_name=Theme.DEFAULT_FONT,
        background_color=(0.1, 0.1, 0.1, 1),
        foreground_color=(0.9, 0.9, 0.9, 1),
    )
    widgets["log_text"].bind(minimum_height=widgets["log_text"].setter("height"))
    widgets["log_scroll"].add_widget(widgets["log_text"])
    main_layout.add_widget(widgets["log_scroll"])

    # Buttons row
    buttons_layout = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48))
    widgets["start_button"] = Button(
        text=i18n._("mykatrain:batch:start"),
        size_hint_x=0.5,
        height=dp(48),
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    widgets["close_button"] = Button(
        text=i18n._("Close"),
        size_hint_x=0.5,
        height=dp(48),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
    )
    buttons_layout.add_widget(widgets["start_button"])
    buttons_layout.add_widget(widgets["close_button"])
    main_layout.add_widget(buttons_layout)

    return main_layout, widgets


def create_batch_popup(
    main_layout: BoxLayout,
) -> Any:
    """バッチポップアップを作成

    Args:
        main_layout: メインレイアウト

    Returns:
        ポップアップウィジェット
    """
    popup = I18NPopup(
        title_key="mykatrain:batch:title",
        size=[dp(800), dp(600)],
        content=main_layout,
    ).__self__

    return popup
