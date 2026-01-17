# katrain/gui/features/smart_kifu_training_set.py
#
# Smart Kifu Learning - Training Set Manager UI (Phase 13.2)
#
# Training Set の一覧表示・作成・SGFインポートを行うUIモジュール。

import os
import threading
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

from katrain.core.constants import STATUS_ERROR, STATUS_INFO
from katrain.core.lang import i18n
from katrain.core.smart_kifu import (
    Context,
    ImportResult,
    TrainingSetManifest,
    compute_training_set_summary,
    create_training_set,
    import_analyzed_sgf_folder,
    import_sgf_folder,
    list_training_sets,
    load_manifest,
)
from katrain.gui.popups import I18NPopup
from katrain.gui.theme import Theme


# =============================================================================
# Analyzed Ratio Formatting (Phase 28)
# =============================================================================

# Color constants for analysis ratio display
COLOR_RATIO_GREEN = [0.3, 0.8, 0.3, 1.0]
COLOR_RATIO_YELLOW = [0.9, 0.8, 0.2, 1.0]
COLOR_RATIO_RED = [0.9, 0.3, 0.3, 1.0]
COLOR_RATIO_GRAY = [0.5, 0.5, 0.5, 1.0]


def _format_analyzed_ratio(ratio: Optional[float]) -> tuple:
    """解析率を表示文字列と色に変換。

    Args:
        ratio: 解析率 (0.0-1.0) または None

    Returns:
        (表示文字列, RGBA色)

    Note:
        ratio is None → "--" (グレー)
        ratio == 0.0 → "0%" (赤)  # 0.0 は falsy だが正しく処理
    """
    if ratio is None:  # IMPORTANT: `if not ratio` ではダメ！
        return ("--", COLOR_RATIO_GRAY)

    pct = int(ratio * 100)
    if ratio >= 0.7:
        return (f"{pct}%", COLOR_RATIO_GREEN)
    elif ratio >= 0.4:
        return (f"{pct}%", COLOR_RATIO_YELLOW)
    else:
        return (f"{pct}%", COLOR_RATIO_RED)

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


# =============================================================================
# Type Aliases
# =============================================================================

TrainingSetWidgets = Dict[str, Any]


# =============================================================================
# Constants
# =============================================================================

CONTEXT_LABELS = {
    Context.HUMAN: "対人戦",
    Context.VS_KATAGO: "vs KataGo",
    Context.GENERATED: "AI生成",
}


# =============================================================================
# Browse Callback
# =============================================================================


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
    def browse_callback(*_args) -> None:
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

        def on_select(*_args):
            text_input_widget.text = browse_popup_content.filesel.file_text.text
            browse_popup.dismiss()

        browse_popup_content.filesel.bind(on_success=on_select)
        browse_popup.open()

    return browse_callback


# =============================================================================
# Training Set List Widget
# =============================================================================


def build_training_set_list_widget(
    sets: List[str],
    selected_set: List[Optional[str]],
    on_select_callback: Callable[[str], None],
) -> BoxLayout:
    """Training Set 一覧ウィジェットを構築

    Args:
        sets: Training Set ID のリスト
        selected_set: 選択中のセットID（リストで参照渡し）
        on_select_callback: 選択時のコールバック

    Returns:
        一覧を含む BoxLayout
    """
    container = BoxLayout(
        orientation="vertical",
        spacing=dp(4),
        size_hint_y=None,
    )
    container.bind(minimum_height=container.setter("height"))

    if not sets:
        # 空の場合
        empty_label = Label(
            text="Training Set がありません",
            size_hint_y=None,
            height=dp(40),
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        container.add_widget(empty_label)
        return container

    for set_id in sets:
        manifest = load_manifest(set_id)
        if manifest is None:
            continue

        # Phase 28: 解析サマリを計算
        summary = compute_training_set_summary(manifest)
        ratio_text, ratio_color = _format_analyzed_ratio(summary.average_analyzed_ratio)

        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(50),
            spacing=dp(8),
        )

        # セット名と情報（解析率を追加）
        info_text = f"{manifest.name}\n{summary.total_games} 局 | {ratio_text} 解析済"
        btn = ToggleButton(
            text=info_text,
            group="training_set_selection",
            state="down" if selected_set[0] == set_id else "normal",
            halign="left",
            valign="middle",
            font_name=Theme.DEFAULT_FONT,
            background_color=Theme.BOX_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        btn.bind(size=lambda b, _: setattr(b, "text_size", (b.width - dp(10), None)))

        def make_select_fn(sid: str):
            def select_fn(instance, state):
                if state == "down":
                    selected_set[0] = sid
                    on_select_callback(sid)
            return select_fn

        btn.bind(state=make_select_fn(set_id))
        row.add_widget(btn)
        container.add_widget(row)

    return container


# =============================================================================
# Create Training Set Dialog
# =============================================================================


def show_create_training_set_dialog(
    ctx: "FeatureContext",
    on_created_callback: Callable[[str], None],
) -> None:
    """新規 Training Set 作成ダイアログを表示

    Args:
        ctx: FeatureContext
        on_created_callback: 作成成功時のコールバック（set_id を渡す）
    """
    content = BoxLayout(
        orientation="vertical",
        spacing=dp(10),
        padding=dp(15),
    )

    # 名前入力
    name_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(40),
        spacing=dp(10),
    )
    name_label = Label(
        text="セット名:",
        size_hint_x=0.3,
        halign="right",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    name_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    name_input = TextInput(
        text="",
        hint_text="例: 2024年対局",
        multiline=False,
        size_hint_x=0.7,
        font_name=Theme.DEFAULT_FONT,
    )
    name_row.add_widget(name_label)
    name_row.add_widget(name_input)
    content.add_widget(name_row)

    # スペーサー
    content.add_widget(BoxLayout(size_hint_y=1))

    # ボタン行
    button_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(48),
        spacing=dp(10),
    )

    popup = I18NPopup(
        title_key="",
        size=[dp(400), dp(200)],
        content=content,
        auto_dismiss=True,
    )
    popup.title = "新規 Training Set 作成"

    def on_create(*_args):
        name = name_input.text.strip()
        if not name:
            ctx.controls.set_status("セット名を入力してください", STATUS_ERROR)
            return

        try:
            set_id = create_training_set(name)
            popup.dismiss()
            ctx.controls.set_status(f"Training Set '{name}' を作成しました", STATUS_INFO)
            on_created_callback(set_id)
        except Exception as e:
            ctx.controls.set_status(f"作成エラー: {e}", STATUS_ERROR)

    def on_cancel(*_args):
        popup.dismiss()

    create_btn = Button(
        text="作成",
        size_hint_x=0.5,
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    create_btn.bind(on_release=on_create)

    cancel_btn = Button(
        text="キャンセル",
        size_hint_x=0.5,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    cancel_btn.bind(on_release=on_cancel)

    button_row.add_widget(create_btn)
    button_row.add_widget(cancel_btn)
    content.add_widget(button_row)

    popup.open()


# =============================================================================
# Import SGF Dialog
# =============================================================================


def show_import_sgf_dialog(
    ctx: "FeatureContext",
    katrain_gui: Any,
    set_id: str,
    on_import_complete: Callable[[], None],
) -> None:
    """SGF インポートダイアログを表示

    Args:
        ctx: FeatureContext
        katrain_gui: KaTrainGui インスタンス
        set_id: インポート先の Training Set ID
        on_import_complete: インポート完了時のコールバック
    """
    manifest = load_manifest(set_id)
    if manifest is None:
        ctx.controls.set_status("Training Set が見つかりません", STATUS_ERROR)
        return

    content = BoxLayout(
        orientation="vertical",
        spacing=dp(10),
        padding=dp(15),
    )

    # セット名表示
    header_label = Label(
        text=f"インポート先: {manifest.name}",
        size_hint_y=None,
        height=dp(30),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    content.add_widget(header_label)

    # フォルダ選択行
    folder_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(40),
        spacing=dp(10),
    )
    folder_label = Label(
        text="SGFフォルダ:",
        size_hint_x=0.25,
        halign="right",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    folder_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    folder_input = TextInput(
        text="",
        hint_text="インポートするSGFフォルダを選択",
        multiline=False,
        size_hint_x=0.55,
        font_name=Theme.DEFAULT_FONT,
    )
    browse_btn = Button(
        text="参照...",
        size_hint_x=0.2,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    browse_btn.bind(on_release=create_browse_callback(folder_input, "SGFフォルダを選択", katrain_gui))
    folder_row.add_widget(folder_label)
    folder_row.add_widget(folder_input)
    folder_row.add_widget(browse_btn)
    content.add_widget(folder_row)

    # Context 選択行
    context_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(40),
        spacing=dp(10),
    )
    context_label = Label(
        text="コンテキスト:",
        size_hint_x=0.25,
        halign="right",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    context_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    selected_context: List[Context] = [Context.HUMAN]

    context_buttons_container = BoxLayout(
        orientation="horizontal",
        size_hint_x=0.75,
        spacing=dp(5),
    )
    for ctx_enum in [Context.HUMAN, Context.VS_KATAGO, Context.GENERATED]:
        btn = ToggleButton(
            text=CONTEXT_LABELS[ctx_enum],
            group="import_context",
            state="down" if ctx_enum == Context.HUMAN else "normal",
            font_name=Theme.DEFAULT_FONT,
            background_color=Theme.BOX_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )

        def make_context_select(c: Context):
            def select_fn(instance, state):
                if state == "down":
                    selected_context[0] = c
            return select_fn

        btn.bind(state=make_context_select(ctx_enum))
        context_buttons_container.add_widget(btn)

    context_row.add_widget(context_label)
    context_row.add_widget(context_buttons_container)
    content.add_widget(context_row)

    # 進捗表示用ラベル
    progress_label = Label(
        text="",
        size_hint_y=None,
        height=dp(30),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    content.add_widget(progress_label)

    # スペーサー
    content.add_widget(BoxLayout(size_hint_y=1))

    # ボタン行
    button_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(48),
        spacing=dp(10),
    )

    popup = I18NPopup(
        title_key="",
        size=[dp(500), dp(300)],
        content=content,
        auto_dismiss=False,
    )
    popup.title = "SGF インポート"

    is_importing: List[bool] = [False]

    def on_import(*_args):
        if is_importing[0]:
            return

        folder_path = folder_input.text.strip()
        if not folder_path:
            ctx.controls.set_status("フォルダを選択してください", STATUS_ERROR)
            return

        if not os.path.isdir(folder_path):
            ctx.controls.set_status("指定されたフォルダが存在しません", STATUS_ERROR)
            return

        is_importing[0] = True
        progress_label.text = "インポート中..."

        def import_thread():
            try:
                result = import_sgf_folder(
                    set_id=set_id,
                    folder_path=folder_path,
                    context=selected_context[0],
                    origin=folder_path,
                )

                def update_ui(dt):
                    is_importing[0] = False
                    show_import_result(ctx, result)
                    popup.dismiss()
                    on_import_complete()

                Clock.schedule_once(update_ui, 0)

            except Exception as e:
                def show_error(dt):
                    is_importing[0] = False
                    progress_label.text = f"エラー: {e}"
                    ctx.controls.set_status(f"インポートエラー: {e}", STATUS_ERROR)

                Clock.schedule_once(show_error, 0)

        threading.Thread(target=import_thread, daemon=True).start()

    def on_cancel(*_args):
        if is_importing[0]:
            return
        popup.dismiss()

    import_btn = Button(
        text="インポート",
        size_hint_x=0.5,
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    import_btn.bind(on_release=on_import)

    cancel_btn = Button(
        text="閉じる",
        size_hint_x=0.5,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    cancel_btn.bind(on_release=on_cancel)

    button_row.add_widget(import_btn)
    button_row.add_widget(cancel_btn)
    content.add_widget(button_row)

    popup.open()


def show_import_result(ctx: "FeatureContext", result: ImportResult) -> None:
    """インポート結果をポップアップで表示

    Args:
        ctx: FeatureContext
        result: インポート結果
    """
    content = BoxLayout(
        orientation="vertical",
        spacing=dp(10),
        padding=dp(15),
    )

    # サマリ
    summary_text = (
        f"成功: {result.success_count} 件\n"
        f"重複スキップ: {result.skipped_count} 件\n"
        f"失敗: {result.failed_count} 件"
    )
    summary_label = Label(
        text=summary_text,
        size_hint_y=None,
        height=dp(80),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        halign="left",
        valign="top",
    )
    summary_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, None)))
    content.add_widget(summary_label)

    # 失敗詳細（ある場合）
    if result.failed_files:
        failed_label = Label(
            text="失敗ファイル:",
            size_hint_y=None,
            height=dp(25),
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
            halign="left",
        )
        failed_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        content.add_widget(failed_label)

        failed_scroll = ScrollView(size_hint_y=None, height=dp(100))
        failed_content = BoxLayout(
            orientation="vertical",
            spacing=dp(2),
            size_hint_y=None,
        )
        failed_content.bind(minimum_height=failed_content.setter("height"))

        for filename, error_msg in result.failed_files[:10]:  # 最大10件表示
            item_label = Label(
                text=f"  • {filename}: {error_msg}",
                size_hint_y=None,
                height=dp(20),
                color=Theme.TEXT_COLOR,
                font_name=Theme.DEFAULT_FONT,
                halign="left",
                font_size=dp(12),
            )
            item_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
            failed_content.add_widget(item_label)

        if len(result.failed_files) > 10:
            more_label = Label(
                text=f"  ...他 {len(result.failed_files) - 10} 件",
                size_hint_y=None,
                height=dp(20),
                color=Theme.TEXT_COLOR,
                font_name=Theme.DEFAULT_FONT,
                halign="left",
                font_size=dp(12),
            )
            failed_content.add_widget(more_label)

        failed_scroll.add_widget(failed_content)
        content.add_widget(failed_scroll)

    # 閉じるボタン
    close_btn = Button(
        text="OK",
        size_hint_y=None,
        height=dp(48),
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )

    popup = I18NPopup(
        title_key="",
        size=[dp(400), dp(350) if result.failed_files else dp(200)],
        content=content,
        auto_dismiss=True,
    )
    popup.title = "インポート結果"

    close_btn.bind(on_release=lambda *_: popup.dismiss())
    content.add_widget(close_btn)

    popup.open()

    # ステータスバーにもサマリ表示
    if result.has_failures:
        ctx.controls.set_status(
            f"インポート完了: 成功{result.success_count}, スキップ{result.skipped_count}, 失敗{result.failed_count}",
            STATUS_ERROR
        )
    else:
        ctx.controls.set_status(
            f"インポート完了: 成功{result.success_count}, スキップ{result.skipped_count}",
            STATUS_INFO
        )


# =============================================================================
# Main Training Set Manager Popup
# =============================================================================


def show_training_set_manager(
    ctx: "FeatureContext",
    katrain_gui: Any,
) -> None:
    """Training Set Manager ポップアップを表示

    Args:
        ctx: FeatureContext
        katrain_gui: KaTrainGui インスタンス
    """
    # 状態管理
    selected_set: List[Optional[str]] = [None]
    set_list_container: List[Optional[BoxLayout]] = [None]

    # メインレイアウト
    main_layout = BoxLayout(
        orientation="vertical",
        spacing=dp(10),
        padding=dp(15),
    )

    # ヘッダー
    header_label = Label(
        text="Training Set 管理",
        size_hint_y=None,
        height=dp(30),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(18),
    )
    main_layout.add_widget(header_label)

    # 一覧スクロールビュー
    list_scroll = ScrollView(size_hint_y=1)
    main_layout.add_widget(list_scroll)

    def refresh_list():
        """Training Set 一覧を更新"""
        sets = list_training_sets()

        def on_select(set_id: str):
            selected_set[0] = set_id

        new_list = build_training_set_list_widget(sets, selected_set, on_select)
        list_scroll.clear_widgets()
        list_scroll.add_widget(new_list)
        set_list_container[0] = new_list

    refresh_list()

    # アクションボタン行
    action_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(48),
        spacing=dp(10),
    )

    def on_new_set(*_args):
        def on_created(set_id: str):
            selected_set[0] = set_id
            refresh_list()

        show_create_training_set_dialog(ctx, on_created)

    def on_import_sgf(*_args):
        if selected_set[0] is None:
            ctx.controls.set_status("インポート先の Training Set を選択してください", STATUS_ERROR)
            return

        show_import_sgf_dialog(
            ctx,
            katrain_gui,
            selected_set[0],
            on_import_complete=refresh_list,
        )

    new_set_btn = Button(
        text="新規作成",
        size_hint_x=0.33,
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    new_set_btn.bind(on_release=on_new_set)

    import_btn = Button(
        text="SGFインポート",
        size_hint_x=0.34,
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    import_btn.bind(on_release=on_import_sgf)

    close_btn = Button(
        text="閉じる",
        size_hint_x=0.33,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )

    action_row.add_widget(new_set_btn)
    action_row.add_widget(import_btn)
    action_row.add_widget(close_btn)
    main_layout.add_widget(action_row)

    # ポップアップ作成
    popup = I18NPopup(
        title_key="",
        size=[dp(500), dp(450)],
        content=main_layout,
        auto_dismiss=True,
    )
    popup.title = "Smart Kifu - Training Set"

    close_btn.bind(on_release=lambda *_: popup.dismiss())

    popup.open()


# =============================================================================
# Batch Import Bridge (Phase 28)
# =============================================================================


def show_import_batch_output_dialog(
    ctx: "FeatureContext",
    set_id: str,
    on_import_complete: Callable[[], None],
) -> None:
    """バッチ解析出力フォルダのインポートダイアログを表示

    Phase 28: バッチ解析の出力（analyzed/*.sgf）をTraining Setにインポート

    Args:
        ctx: FeatureContext
        set_id: インポート先のTraining Set ID
        on_import_complete: インポート完了時のコールバック
    """
    from pathlib import Path

    content = BoxLayout(
        orientation="vertical",
        spacing=dp(10),
        padding=dp(15),
    )

    # フォルダ選択行
    folder_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(40),
        spacing=dp(10),
    )
    folder_label = Label(
        text="フォルダ:",
        size_hint_x=0.2,
        halign="right",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    folder_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    folder_input = TextInput(
        text="",
        hint_text="解析済みSGFフォルダを選択",
        multiline=False,
        size_hint_x=0.6,
        font_name=Theme.DEFAULT_FONT,
    )
    browse_btn = Button(
        text="参照...",
        size_hint_x=0.2,
        font_name=Theme.DEFAULT_FONT,
    )
    browse_btn.bind(on_release=create_browse_callback(
        folder_input, "解析済みSGFフォルダを選択", ctx.katrain_gui
    ))
    folder_row.add_widget(folder_label)
    folder_row.add_widget(folder_input)
    folder_row.add_widget(browse_btn)
    content.add_widget(folder_row)

    # Context選択行
    context_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(40),
        spacing=dp(10),
    )
    context_label = Label(
        text="コンテキスト:",
        size_hint_x=0.2,
        halign="right",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    context_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))

    # Context選択ボタン群
    context_buttons = BoxLayout(
        orientation="horizontal",
        size_hint_x=0.8,
        spacing=dp(5),
    )
    selected_context = [Context.HUMAN]  # 参照渡し用

    for ctx_enum, label in CONTEXT_LABELS.items():
        btn = ToggleButton(
            text=label,
            group="batch_import_context",
            state="down" if ctx_enum == Context.HUMAN else "normal",
            font_name=Theme.DEFAULT_FONT,
        )

        def make_context_fn(c):
            def set_ctx(instance, state):
                if state == "down":
                    selected_context[0] = c
            return set_ctx

        btn.bind(state=make_context_fn(ctx_enum))
        context_buttons.add_widget(btn)

    context_row.add_widget(context_label)
    context_row.add_widget(context_buttons)
    content.add_widget(context_row)

    # 結果表示ラベル
    result_label = Label(
        text="",
        size_hint_y=None,
        height=dp(60),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        halign="center",
        valign="middle",
    )
    result_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    content.add_widget(result_label)

    # スペーサー
    content.add_widget(BoxLayout(size_hint_y=1))

    # ボタン行
    button_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(48),
        spacing=dp(10),
    )

    popup = I18NPopup(
        title_key="",
        size=[dp(500), dp(280)],
        content=content,
        auto_dismiss=True,
    )
    popup.title = "バッチ出力をインポート"

    def on_import(*_args):
        folder_path_str = folder_input.text.strip()
        if not folder_path_str:
            result_label.text = "フォルダを選択してください"
            result_label.color = Theme.TEXT_COLOR
            return

        folder_path = Path(folder_path_str)
        if not folder_path.is_dir():
            result_label.text = "有効なフォルダを選択してください"
            result_label.color = [0.9, 0.3, 0.3, 1.0]
            return

        result_label.text = "インポート中..."
        result_label.color = Theme.TEXT_COLOR

        def do_import():
            result = import_analyzed_sgf_folder(
                set_id=set_id,
                folder_path=folder_path,
                context=selected_context[0],
                origin=f"batch:{folder_path_str}",
            )
            return result

        def show_result(result: ImportResult):
            # IMPORTANT: ratio is not None で判定（0.0 を "--" にしない）
            if result.average_analyzed_ratio is not None:
                ratio_text = f"{int(result.average_analyzed_ratio * 100)}%"
            else:
                ratio_text = "--"

            result_label.text = (
                f"成功: {result.success_count}, "
                f"スキップ: {result.skipped_count}, "
                f"失敗: {result.failed_count}\n"
                f"平均解析率: {ratio_text}"
            )

            if result.has_failures:
                result_label.color = [0.9, 0.8, 0.2, 1.0]  # Yellow for partial
            elif result.success_count > 0:
                result_label.color = [0.3, 0.8, 0.3, 1.0]  # Green for success
            else:
                result_label.color = Theme.TEXT_COLOR

            on_import_complete()

        def import_thread():
            result = do_import()
            Clock.schedule_once(lambda dt: show_result(result), 0)

        threading.Thread(target=import_thread, daemon=True).start()

    import_btn = Button(
        text="インポート",
        size_hint_x=0.5,
        font_name=Theme.DEFAULT_FONT,
    )
    import_btn.bind(on_release=on_import)

    close_btn = Button(
        text="閉じる",
        size_hint_x=0.5,
        font_name=Theme.DEFAULT_FONT,
    )
    close_btn.bind(on_release=lambda *_: popup.dismiss())

    button_row.add_widget(import_btn)
    button_row.add_widget(close_btn)
    content.add_widget(button_row)

    popup.open()


# =============================================================================
# __all__
# =============================================================================

__all__ = [
    "show_training_set_manager",
    "show_create_training_set_dialog",
    "show_import_sgf_dialog",
    "show_import_result",
    "show_import_batch_output_dialog",
]
