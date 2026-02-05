# katrain/gui/features/summary_ui.py
#
# サマリUI配線モジュール
#
# __main__.py から抽出したサマリエクスポートのUI配線関数を配置します。
# - do_export_summary: エントリポイント（Kivyスレッドスケジュール）
# - do_export_summary_ui: メインUI処理
# - process_summary_with_selected_players: 選択後の処理開始

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Any, Callable

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
    scan_and_show_callback: Callable[[list[str]], None],
    load_export_settings_fn: Callable[[], dict[str, Any]],
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
    scan_and_show_callback: Callable[[list[str]], None],
    load_export_settings_fn: Callable[[], dict[str, Any]],
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
                title=i18n._("Error"),
                title_font=Theme.DEFAULT_FONT,
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
        title_font=Theme.DEFAULT_FONT,
        size_hint=(0.8, 0.8),
        content=popup_contents
    ).__self__

    def process_directory(*_args: Any) -> None:
        selected_path = popup_contents.filesel.path

        if not selected_path or not os.path.isdir(selected_path):
            load_popup.dismiss()
            Popup(
                title=i18n._("Error"),
                title_font=Theme.DEFAULT_FONT,
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
                title=i18n._("Error"),
                title_font=Theme.DEFAULT_FONT,
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
    sgf_files: list[str],
    selected_players: list[str],
    process_and_export_fn: Callable[[list[str], "Popup", list[str]], None],
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
        title=i18n._("Generating Summary"),
        title_font=Theme.DEFAULT_FONT,
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


def scan_and_show_player_selection(
    sgf_files: list[str],
    ctx: "FeatureContext",
    scan_player_names_fn: Callable[[list[str]], dict[str, int]],
    process_summary_fn: Callable[[list[str], list[str]], None],
    show_player_selection_fn: Callable[[list[tuple[str, int]], list[str]], None],
) -> None:
    """プレイヤー名をスキャンして選択ダイアログを表示

    Args:
        sgf_files: SGFファイルパスのリスト
        ctx: FeatureContext providing config
        scan_player_names_fn: プレイヤー名スキャン関数
        process_summary_fn: サマリ処理開始関数
        show_player_selection_fn: プレイヤー選択ダイアログ表示関数
    """
    # mykatrain_settings を取得
    mykatrain_settings = ctx.config("mykatrain_settings") or {}
    karte_format = mykatrain_settings.get("karte_format", "both")
    default_user = mykatrain_settings.get("default_user_name", "")

    player_counts = scan_player_names_fn(sgf_files)

    if not player_counts:
        Clock.schedule_once(
            lambda dt: Popup(
                title=i18n._("Error"),
                title_font=Theme.DEFAULT_FONT,
                content=Label(
                    text="No player names found in SGF files.",
                    halign="center",
                    valign="middle"
                ),
                size_hint=(0.5, 0.3),
            ).open(),
            0
        )
        return

    # karte_format に基づいてプレイヤー選択を自動化
    if karte_format == "default_user_only" and default_user:
        # デフォルトユーザーがSGF内に存在するか確認
        if default_user in player_counts:
            # プレイヤー選択をスキップ、デフォルトユーザーを自動選択
            Clock.schedule_once(
                lambda dt: process_summary_fn(sgf_files, [default_user]),
                0
            )
            return
        else:
            # デフォルトユーザーが見つからない場合は警告して選択ダイアログへ
            Clock.schedule_once(
                lambda dt: Popup(
                    title=i18n._("Warning"),
                    title_font=Theme.DEFAULT_FONT,
                    content=Label(
                        text=f"Default user '{default_user}' not found in SGF files.\nPlease select players manually.",
                        halign="center",
                        valign="middle",
                        font_name=Theme.DEFAULT_FONT,
                    ),
                    size_hint=(0.5, 0.3),
                ).open(),
                0
            )

    # 出現回数でソート（多い順）
    sorted_players = sorted(player_counts.items(), key=lambda x: x[1], reverse=True)

    # 選択ダイアログを表示（UIスレッドで）
    Clock.schedule_once(
        lambda dt: show_player_selection_fn(sorted_players, sgf_files),
        0
    )


def show_player_selection_dialog(
    sorted_players: list[tuple[str, int]],
    sgf_files: list[str],
    load_export_settings_fn: Callable[[], dict[str, Any]],
    save_export_settings_fn: Callable[..., None],
    process_and_export_fn: Callable[[list[str], "Popup", list[str]], None],
) -> None:
    """プレイヤー選択ダイアログを表示

    Args:
        sorted_players: ソート済み(プレイヤー名, 出現数)タプルのリスト
        sgf_files: SGFファイルパスのリスト
        load_export_settings_fn: エクスポート設定読み込み関数
        save_export_settings_fn: エクスポート設定保存関数
        process_and_export_fn: 処理・エクスポート関数
    """
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.checkbox import CheckBox
    from kivy.uix.button import Button
    from kivy.uix.scrollview import ScrollView

    # 前回の選択を読み込む
    export_settings = load_export_settings_fn()
    last_selected_players = export_settings.get("last_selected_players", [])

    # チェックボックスリスト
    checkbox_dict: dict[str, Any] = {}  # {player_name: CheckBox}

    content_layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))

    # 説明ラベル
    instruction_label = Label(
        text="Select players to include in summary:",
        size_hint_y=None,
        height=dp(30),
        halign="left",
        valign="middle",
        font_name=Theme.DEFAULT_FONT,
    )
    instruction_label.bind(size=instruction_label.setter('text_size'))
    content_layout.add_widget(instruction_label)

    # スクロール可能なチェックボックスリスト
    scroll_layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(5))
    scroll_layout.bind(minimum_height=scroll_layout.setter('height'))

    for player_name, count in sorted_players:
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30))

        checkbox = CheckBox(size_hint_x=None, width=dp(40))
        # 前回の選択がある場合はそれを使用、なければ最も多いプレイヤーを選択
        if last_selected_players:
            checkbox.active = player_name in last_selected_players
        else:
            checkbox.active = player_name == sorted_players[0][0]

        checkbox_dict[player_name] = checkbox

        label = Label(
            text=f"{player_name} ({count} games)",
            size_hint_x=1.0,
            halign="left",
            valign="middle",
            font_name=Theme.DEFAULT_FONT,
        )
        label.bind(size=label.setter('text_size'))

        row.add_widget(checkbox)
        row.add_widget(label)
        scroll_layout.add_widget(row)

    scroll_view = ScrollView(size_hint=(1, 1))
    scroll_view.add_widget(scroll_layout)
    content_layout.add_widget(scroll_view)

    # OKボタン
    button_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))

    # selection_popup を先に定義（on_ok 内で参照するため）
    selection_popup = None

    def on_ok(*args: Any) -> None:
        nonlocal selection_popup
        selected_players = [name for name, cb in checkbox_dict.items() if cb.active]

        if not selected_players:
            # 警告
            Popup(
                title=i18n._("Warning"),
                title_font=Theme.DEFAULT_FONT,
                content=Label(
                    text="Please select at least one player.",
                    halign="center",
                    valign="middle"
                ),
                size_hint=(0.4, 0.2),
            ).open()
            return

        if selection_popup:
            selection_popup.dismiss()

        # 選択したプレイヤーを保存
        save_export_settings_fn(selected_players=selected_players)

        # 進行状況ポップアップ
        progress_label = Label(
            text=f"Processing {len(sgf_files)} games...",
            halign="center",
            valign="middle"
        )
        progress_popup = Popup(
            title=i18n._("Generating Summary"),
            title_font=Theme.DEFAULT_FONT,
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

    ok_button = Button(text="OK")
    ok_button.bind(on_release=on_ok)
    button_layout.add_widget(ok_button)

    content_layout.add_widget(button_layout)

    selection_popup = Popup(
        title=i18n._("Select Players"),
        title_font=Theme.DEFAULT_FONT,
        content=content_layout,
        size_hint=(0.6, 0.7),
    )
    selection_popup.open()


def process_and_export_summary(
    sgf_paths: list[str],
    progress_popup: "Popup",
    selected_players: list[str],
    ctx: "FeatureContext",
    extract_sgf_statistics_fn: Callable[[str], dict[str, Any]],
    categorize_games_fn: Callable[[list[dict[str, Any]], str | None], dict[str, Any]],
    save_summaries_per_player_fn: Callable[[list[dict[str, Any]], list[str], "Popup"], None],
    save_categorized_summaries_fn: Callable[[dict[str, Any], str | None, "Popup"], None],
) -> None:
    """バックグラウンドでの複数局処理（プレイヤーフィルタリング対応）

    Args:
        sgf_paths: SGFファイルパスのリスト
        progress_popup: 進行状況ポップアップ
        selected_players: 選択されたプレイヤー名のリスト
        ctx: FeatureContext providing log
        extract_sgf_statistics_fn: SGF統計抽出関数
        categorize_games_fn: ゲーム分類関数
        save_summaries_per_player_fn: プレイヤーごとサマリ保存関数
        save_categorized_summaries_fn: 分類別サマリ保存関数
    """
    import os
    from katrain.core.constants import OUTPUT_ERROR, OUTPUT_INFO
    from katrain.core.errors import SGFError

    game_stats_list = []

    for i, path in enumerate(sgf_paths):
        try:
            # 進行状況更新（UI）
            Clock.schedule_once(
                lambda dt, i=i, path=path: setattr(
                    progress_popup.content,
                    "text",
                    f"Processing {i+1}/{len(sgf_paths)}...\n{os.path.basename(path)}"
                ),
                0
            )

            # SGFから統計を直接抽出
            stats = extract_sgf_statistics_fn(path)
            if not stats:
                ctx.log(f"Skipping {path}: Failed to extract statistics", OUTPUT_INFO)
                continue

            # 解析データがほとんどない場合はスキップ
            if stats["total_moves"] < 10:
                ctx.log(f"Skipping {path}: Too few analyzed moves ({stats['total_moves']})", OUTPUT_INFO)
                continue

            # プレイヤーフィルタリング（selected_playersが指定されている場合）
            if selected_players:
                player_black = stats["player_black"]
                player_white = stats["player_white"]
                if player_black not in selected_players and player_white not in selected_players:
                    # どちらのプレイヤーも選択されていない場合はスキップ
                    ctx.log(f"Skipping {path}: Players not in selection", OUTPUT_INFO)
                    continue

            game_stats_list.append(stats)

        except (SGFError, OSError, KeyError) as e:
            # Expected: SGF parse error, file I/O error, or missing stats data
            ctx.log(f"Failed to process {path}: {e}", OUTPUT_ERROR)
        except Exception as e:
            # Unexpected: Internal bug - traceback required
            import traceback
            ctx.log(f"Unexpected error processing {path}: {e}\n{traceback.format_exc()}", OUTPUT_ERROR)

    if not game_stats_list:
        # 処理できた対局がない
        Clock.schedule_once(lambda dt: progress_popup.dismiss(), 0)
        Clock.schedule_once(
            lambda dt: Popup(
                title=i18n._("Error"),
                title_font=Theme.DEFAULT_FONT,
                content=Label(
                    text="No games could be processed.\nCheck that games have analysis data.",
                    halign="center",
                    valign="middle"
                ),
                size_hint=(0.5, 0.3),
            ).open(),
            0
        )
        return

    # 複数プレイヤーが選択された場合は、各プレイヤーごとに別ファイルを出力
    if selected_players and len(selected_players) > 1:
        # 各プレイヤーごとに処理
        Clock.schedule_once(
            lambda dt: save_summaries_per_player_fn(game_stats_list, selected_players, progress_popup),
            0
        )
    else:
        # 1プレイヤーまたは未選択の場合は従来通り
        focus_player = selected_players[0] if selected_players and len(selected_players) == 1 else None
        categorized_games = categorize_games_fn(game_stats_list, focus_player)

        # 各カテゴリごとにまとめレポート生成
        Clock.schedule_once(
            lambda dt: save_categorized_summaries_fn(categorized_games, focus_player, progress_popup),
            0
        )
