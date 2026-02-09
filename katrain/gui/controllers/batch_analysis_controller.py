"""バッチ解析制御コントローラー（Phase 133）

バッチ解析用ポップアップの生成、ウィジェットの構築、設定の収集、
およびバックグラウンド実行スレッドの制御を担当。
"""

from __future__ import annotations

import threading
from typing import Any, Protocol


class BatchAnalysisContext(Protocol):
    """BatchAnalysisControllerが動作するために必要な外部インターフェース"""

    def config(self, section: str, default: Any = None) -> Any: ...
    def save_config(self, section: str) -> None: ...
    def log(self, message: str, level: int) -> None: ...
    def update_engine_config(self, **kwargs: Any) -> None: ...
    def set_config_section(self, section: str, value: Any) -> None: ...


class BatchAnalysisController:
    """バッチ解析UIとプロセスの制御。

    責務:
    - バッチ解析ポップアップのオープン
    - ウィジェット構築とイベントのバインド
    - バッチ解析スレッドの起動と進捗監視
    """

    def __init__(self, ctx: BatchAnalysisContext) -> None:
        self._ctx = ctx

    def open_batch_analyze_popup(self) -> None:
        """バッチ解析フォルダー選択／実行ポップアップを表示する。"""
        # 遅延インポートによる依存関係の回避
        from katrain.gui.features.batch_core import (
            collect_batch_options,
            create_log_callback,
            create_progress_callback,
            create_summary_callback,
            run_batch_in_thread,
        )
        from katrain.gui.features.batch_ui import (
            build_batch_popup_widgets,
            create_batch_popup,
            create_browse_callback,
            create_get_player_filter_fn,
            create_on_close_callback,
            create_on_start_callback,
        )
        from katrain.gui.features.settings_popup import do_mykatrain_settings_popup
        from kivy.clock import Clock

        # 1. 保存されたオプションのロード
        mykatrain_settings = self._ctx.config("mykatrain_settings") or {}
        batch_options = mykatrain_settings.get("batch_options", {})
        default_input_dir = batch_options.get("input_dir") or mykatrain_settings.get("batch_export_input_directory", "")
        default_output_dir = batch_options.get("output_dir", "")

        # 2. ウィジェット構築
        main_layout, widgets = build_batch_popup_widgets(batch_options, default_input_dir, default_output_dir)

        # 3. ポップアップ生成
        popup = create_batch_popup(main_layout)

        # 4. 実行状態管理
        is_running = [False]
        cancel_flag = [False]

        # 5. コールバック作成
        filter_buttons = {
            "filter_black": widgets["filter_black"],
            "filter_white": widgets["filter_white"],
            "filter_both": widgets["filter_both"],
        }
        get_player_filter = create_get_player_filter_fn(filter_buttons)

        log_cb = create_log_callback(widgets["log_text"], widgets["log_scroll"])
        progress_cb = create_progress_callback(widgets["progress_label"])
        
        def save_batch_options(options: dict[str, Any]) -> None:
            self._ctx.set_config_section("batch_options", options)
            self._ctx.save_config("batch_options")

        summary_cb = create_summary_callback(
            is_running,
            widgets["start_button"],
            widgets["close_button"],
            widgets["progress_label"],
            log_cb,
        )

        def run_batch_thread() -> None:
            options = collect_batch_options(widgets, get_player_filter)
            run_batch_in_thread(self._ctx, options, cancel_flag, progress_cb, log_cb, summary_cb, save_batch_options) # type: ignore[arg-type]

        def start_batch_thread() -> None:
            threading.Thread(target=run_batch_thread, daemon=True).start()

        # 6. イベントバインド
        on_start = create_on_start_callback(
            self._ctx, widgets, is_running, cancel_flag, get_player_filter, start_batch_thread # type: ignore[arg-type]
        )
        on_close = create_on_close_callback(popup, is_running)
        browse_input = create_browse_callback(widgets["input_input"], "Select input folder", self._ctx) # type: ignore[arg-type]
        browse_output = create_browse_callback(widgets["output_input"], "Select output folder", self._ctx) # type: ignore[arg-type]

        widgets["start_button"].bind(on_release=on_start)
        widgets["close_button"].bind(on_release=on_close)
        widgets["input_browse"].bind(on_release=browse_input)
        widgets["output_browse"].bind(on_release=browse_output)


        # 7. 表示
        popup.open()
