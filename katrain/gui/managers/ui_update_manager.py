"""UI更新制御マネージャー（Phase 133）

StateNotifierからのイベント（ゲーム変更、解析完了、設定更新等）を購読し、
メインスレッドで安全かつ効率的にupdate_guiを呼び出す。
複数イベントが発生した際の合体（Coalescing）ロジックを含む。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, Protocol

from katrain.core.state import EventType


class StateNotifierProtocol(Protocol):
    """UIUpdateManagerが使用するStateNotifierのインターフェース"""

    def subscribe(self, event_type: EventType, callback: Callable[[Any], None]) -> None: ...


class UIUpdateContext(Protocol):
    """UIUpdateManagerが動作するために必要な外部インターフェース"""

    state_notifier: StateNotifierProtocol

    def update_gui(self, cn: Any, redraw_board: bool = False) -> None: ...
    def log(self, message: str, level: int) -> None: ...
    def get_game(self) -> Any: ...


class UIUpdateManager:
    """UI更新の購読と最適化。

    責務:
    - StateNotifierへのイベント登録
    - スレッドセーフなUI更新フラグの管理
    - Clockを使用したメインスレッドでの一括更新（Coalescing）
    """

    def __init__(self, ctx: UIUpdateContext, clock: Any) -> None:
        """UIUpdateManagerを初期化。

        Args:
            ctx: KaTrainGuiなどのコンテキスト
            clock: kivy.clock.Clock オブジェクト（依存注入）
        """
        self._ctx = ctx
        self._clock = clock
        self._ui_update_lock = threading.Lock()
        self._pending_ui_update: Any = None
        self._pending_redraw_board = False
        self._state_subscriptions_setup = False

    def setup_state_subscriptions(self) -> None:
        """StateNotifier購読を設定（重複登録防止付き）"""
        if self._state_subscriptions_setup:
            return
        self._state_subscriptions_setup = True

        notifier = self._ctx.state_notifier
        notifier.subscribe(EventType.GAME_CHANGED, self._on_game_changed)
        notifier.subscribe(EventType.ANALYSIS_COMPLETE, self._on_analysis_complete)
        notifier.subscribe(EventType.CONFIG_UPDATED, self._on_config_updated)

    def schedule_ui_update(self, redraw_board: bool = False) -> None:
        """UI更新をスケジュール。

        同一フレーム内の複数イベントを1回のupdate_gui()呼び出しに集約。
        """
        with self._ui_update_lock:
            self._pending_redraw_board = self._pending_redraw_board or redraw_board
            if self._pending_ui_update is not None:
                return
            self._pending_ui_update = self._clock.schedule_once(self._do_ui_update, 0)

    def _do_ui_update(self, dt: Any) -> None:
        """UI更新コールバック（メインスレッドで実行）"""
        with self._ui_update_lock:
            self._pending_ui_update = None
            redraw = self._pending_redraw_board
            self._pending_redraw_board = False

        game = self._ctx.get_game()
        if not game or not hasattr(game, "current_node") or game.current_node is None:
            return

        try:
            self._ctx.update_gui(game.current_node, redraw_board=redraw)
        except Exception as e:
            # 循環参照やログレベル定数のため、一旦単純な文字列表記
            self._ctx.log(f"update_gui failed: {e}", 10) # 10 = OUTPUT_DEBUG

    def _on_game_changed(self, event: Any) -> None:
        self.schedule_ui_update(redraw_board=True)

    def _on_analysis_complete(self, event: Any) -> None:
        self.schedule_ui_update(redraw_board=False)

    def _on_config_updated(self, event: Any) -> None:
        self.schedule_ui_update(redraw_board=False)
