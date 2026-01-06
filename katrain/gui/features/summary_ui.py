# katrain/gui/features/summary_ui.py
#
# サマリUI配線モジュール
#
# __main__.py から抽出したサマリエクスポートのUI配線関数を配置します。
# - do_export_summary: エントリポイント（Kivyスレッドスケジュール）
# - do_export_summary_ui: メインUI処理
# - process_summary_with_selected_players: 選択後の処理開始

import os
import threading
from typing import TYPE_CHECKING, Callable, List

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from katrain.core.lang import i18n
from katrain.gui.popups import LoadSGFPopup
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def do_export_summary(
    ctx: "FeatureContext",
    scan_and_show_callback: Callable[[List[str]], None],
    load_export_settings_fn: Callable[[], dict],
    save_export_settings_fn: Callable[..., None],
) -> None:
    """Schedule summary export on the main Kivy thread.

    Args:
        ctx: FeatureContext providing config, log
        scan_and_show_callback: Callback to scan players and show selection dialog
        load_export_settings_fn: Function to load export settings
        save_export_settings_fn: Function to save export settings
    """
    # export_summary is executed from _message_loop_thread (NOT the main Kivy thread).
    # Any Kivy UI creation must happen on the main thread.
    Clock.schedule_once(
        lambda dt: do_export_summary_ui(
            ctx, scan_and_show_callback, load_export_settings_fn, save_export_settings_fn
        ),
        0
    )


def do_export_summary_ui(
    ctx: "FeatureContext",
    scan_and_show_callback: Callable[[List[str]], None],
    load_export_settings_fn: Callable[[], dict],
    save_export_settings_fn: Callable[..., None],
) -> None:
    """ディレクトリ選択とまとめ生成（自動分類）

    Args:
        ctx: FeatureContext providing config, log
        scan_and_show_callback: Callback to scan players and show selection dialog
        load_export_settings_fn: Function to load export settings
        save_export_settings_fn: Function to save export settings
    """
    # mykatrain_settings を取得
    mykatrain_settings = ctx.config("mykatrain_settings") or {}
    default_input_dir = mykatrain_settings.get("batch_export_input_directory", "")

    # 入力ディレクトリが設定されている場合はフォルダ選択をスキップ
    if default_input_dir and os.path.isdir(default_input_dir):
        # SGFファイルを取得
        sgf_files = []
        for file in os.listdir(default_input_dir):
            if file.lower().endswith('.sgf'):
                sgf_files.append(os.path.join(default_input_dir, file))

        if len(sgf_files) < 2:
            Popup(
                title="Error",
                content=Label(
                    text=f"Found only {len(sgf_files)} SGF file(s) in batch directory.\nNeed at least 2 games for summary.",
                    halign="center",
                    valign="middle",
                    font_name=Theme.DEFAULT_FONT,
                ),
                size_hint=(0.5, 0.3),
            ).open()
            return

        # プレイヤー名をスキャンして処理（バックグラウンド）
        threading.Thread(
            target=scan_and_show_callback,
            args=(sgf_files,),
            daemon=True
        ).start()
        return

    # 入力ディレクトリ未設定の場合: ディレクトリ選択ダイアログ
    popup_contents = LoadSGFPopup(ctx)
    popup_contents.filesel.dirselect = True  # ディレクトリ選択モード

    # mykatrain_settings の batch_export_input_directory を優先、なければ前回のパス
    if default_input_dir and os.path.isdir(default_input_dir):
        popup_contents.filesel.path = default_input_dir
    else:
        # フォールバック: 前回のパス
        export_settings = load_export_settings_fn()
        last_directory = export_settings.get("last_sgf_directory")
        if last_directory and os.path.isdir(last_directory):
            popup_contents.filesel.path = last_directory

    load_popup = Popup(
        title=i18n._("Select directory containing SGF files"),
        size_hint=(0.8, 0.8),
        content=popup_contents
    ).__self__

    def process_directory(*_args):
        selected_path = popup_contents.filesel.path

        if not selected_path or not os.path.isdir(selected_path):
            load_popup.dismiss()
            Popup(
                title="Error",
                content=Label(
                    text="Please select a valid directory.",
                    halign="center",
                    valign="middle"
                ),
                size_hint=(0.5, 0.3),
            ).open()
            return

        # ディレクトリ内の全SGFファイルを取得
        sgf_files = []
        for file in os.listdir(selected_path):
            if file.lower().endswith('.sgf'):
                sgf_files.append(os.path.join(selected_path, file))

        if len(sgf_files) < 2:
            load_popup.dismiss()
            Popup(
                title="Error",
                content=Label(
                    text=f"Found only {len(sgf_files)} SGF file(s).\nNeed at least 2 games for summary.",
                    halign="center",
                    valign="middle"
                ),
                size_hint=(0.5, 0.3),
            ).open()
            return

        load_popup.dismiss()

        # 選択したディレクトリを保存
        save_export_settings_fn(sgf_directory=selected_path)

        # プレイヤー名をスキャン（バックグラウンド）
        threading.Thread(
            target=scan_and_show_callback,
            args=(sgf_files,),
            daemon=True
        ).start()

    popup_contents.filesel.on_success = process_directory
    load_popup.open()


def process_summary_with_selected_players(
    sgf_files: List[str],
    selected_players: List[str],
    process_and_export_fn: Callable[[List[str], "Popup", List[str]], None],
) -> None:
    """選択されたプレイヤーでサマリー処理を開始

    Args:
        sgf_files: SGFファイルパスのリスト
        selected_players: 選択されたプレイヤー名のリスト
        process_and_export_fn: 処理・エクスポート関数
    """
    # 進行状況ポップアップ
    progress_label = Label(
        text=f"Processing {len(sgf_files)} games...",
        halign="center",
        valign="middle"
    )
    progress_popup = Popup(
        title="Generating Summary",
        content=progress_label,
        size_hint=(0.5, 0.3),
        auto_dismiss=False
    )
    progress_popup.open()

    # バックグラウンドで処理
    threading.Thread(
        target=process_and_export_fn,
        args=(sgf_files, progress_popup, selected_players),
        daemon=True
    ).start()
