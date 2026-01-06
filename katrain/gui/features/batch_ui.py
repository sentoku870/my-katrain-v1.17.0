# katrain/gui/features/batch_ui.py
#
# バッチ解析UIモジュール
#
# __main__.py から抽出したバッチ解析UIの配線・コールバックを配置します。
# - create_browse_callback: フォルダ選択ブラウズコールバック作成
# - create_on_start_callback: 開始ボタンコールバック作成
# - create_on_close_callback: 閉じるボタンコールバック作成

import os
import threading
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from kivy.uix.popup import Popup

from katrain.core.constants import STATUS_ERROR
from katrain.core.lang import i18n

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


def create_on_start_callback(
    ctx: "FeatureContext",
    widgets: Dict[str, Any],
    is_running: List[bool],
    cancel_flag: List[bool],
    get_player_filter_fn: Callable[[], Optional[str]],
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
    def on_start(*_args) -> None:
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
    is_running: List[bool],
) -> Callable[..., None]:
    """閉じるボタンコールバックを作成

    Args:
        popup: ポップアップウィジェット
        is_running: 実行中フラグ（リストで参照渡し）

    Returns:
        閉じるボタンコールバック関数
    """
    def on_close(*_args) -> None:
        if is_running[0]:
            return  # Don't close while running
        popup.dismiss()

    return on_close


def create_get_player_filter_fn(
    filter_buttons: Dict[str, Any],
) -> Callable[[], Optional[str]]:
    """プレイヤーフィルター取得関数を作成

    Args:
        filter_buttons: フィルターボタン辞書（filter_black, filter_white, filter_both）

    Returns:
        プレイヤーフィルター取得関数
    """
    def get_player_filter() -> Optional[str]:
        if filter_buttons["filter_black"].state == "down":
            return "B"
        elif filter_buttons["filter_white"].state == "down":
            return "W"
        return None  # Both = no filter

    return get_player_filter
