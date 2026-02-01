"""ポップアップ管理マネージャー（Phase 75）

設定系ポップアップのキャッシュと開閉制御を担当。
依存注入パターンでKivy非依存テストを実現。

不変条件:
- open_*メソッドはKivy UIスレッドから呼び出すこと
- engine.pyからの呼び出しはKaTrainGui.__call__経由で自動UIスレッド化

使用例:
    from katrain.gui.managers.popup_manager import PopupManager

    manager = PopupManager(
        create_new_game_popup=self._create_new_game_popup,
        create_timer_popup=self._create_timer_popup,
        create_teacher_popup=self._create_teacher_popup,
        create_ai_popup=self._create_ai_popup,
        create_engine_recovery_popup=self._create_engine_recovery_popup,
        get_popup_open=lambda: self.popup_open,
        is_engine_recovery_popup=lambda p: isinstance(getattr(p, "content", None), EngineRecoveryPopup),
        pause_timer=self._safe_pause_timer,
        on_new_game_opened=lambda p: p.content.update_from_current_game(),
        logger=self.log,
        log_level_debug=OUTPUT_DEBUG,
    )

    # 使用
    manager.open_new_game_popup()
    manager.open_engine_recovery_popup("error message", "E001")
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional


class PopupManager:
    """設定系ポップアップの管理（キャッシュ・開閉制御）

    キャッシュポリシー:
    - new_game, timer, teacher, ai: キャッシュ再利用（初回のみファクトリ呼び出し）
    - engine_recovery: 毎回新規作成（キャッシュなし）

    タイマー一時停止ポリシー:
    - new_game, timer, teacher, ai: pause_timer()を呼ぶ
    - engine_recovery: pause_timer()を呼ばない（エラー条件によるトリガーのため）
    """

    def __init__(
        self,
        # Popup factories (Kivy依存を注入)
        create_new_game_popup: Callable[[], Any],
        create_timer_popup: Callable[[], Any],
        create_teacher_popup: Callable[[], Any],
        create_ai_popup: Callable[[], Any],
        create_engine_recovery_popup: Callable[[str, str], Any],
        # State accessors
        get_popup_open: Callable[[], Optional[Any]],
        is_engine_recovery_popup: Callable[[Any], bool],
        # Timer control (null-safe)
        pause_timer: Callable[[], None],
        # Post-open hooks
        on_new_game_opened: Callable[[Any], None],  # update_from_current_game呼び出し用
        # Logging
        logger: Callable[[str, int], None],
        log_level_debug: int,
    ):
        """PopupManagerを初期化する。

        Args:
            create_new_game_popup: NewGamePopupのファクトリ
            create_timer_popup: TimerPopupのファクトリ
            create_teacher_popup: TeacherPopupのファクトリ
            create_ai_popup: AIPopupのファクトリ
            create_engine_recovery_popup: EngineRecoveryPopupのファクトリ (error_message, code) -> Popup
            get_popup_open: 現在開いているポップアップを取得
            is_engine_recovery_popup: ポップアップがEngineRecoveryPopupかを判定
            pause_timer: タイマーを一時停止（null-safe実装を期待）
            on_new_game_opened: NewGamePopup open後のフック
            logger: ロギング関数 (message, level)
            log_level_debug: OUTPUT_DEBUG相当のログレベル
        """
        self._popups: Dict[str, Optional[Any]] = {
            "new_game": None,
            "timer": None,
            "teacher": None,
            "ai": None,
        }
        self._create_new_game_popup = create_new_game_popup
        self._create_timer_popup = create_timer_popup
        self._create_teacher_popup = create_teacher_popup
        self._create_ai_popup = create_ai_popup
        self._create_engine_recovery_popup = create_engine_recovery_popup
        self._get_popup_open = get_popup_open
        self._is_engine_recovery_popup = is_engine_recovery_popup
        self._pause_timer = pause_timer
        self._on_new_game_opened = on_new_game_opened
        self._log = logger
        self._log_level_debug = log_level_debug

    def open_new_game_popup(self) -> None:
        """新規対局ポップアップを開く（キャッシュ再利用）"""
        self._pause_timer()
        if self._popups["new_game"] is None:
            self._popups["new_game"] = self._create_new_game_popup()
        popup = self._popups["new_game"]
        if popup:  # Type narrowing for mypy
            popup.open()
            self._on_new_game_opened(popup)

    def open_timer_popup(self) -> None:
        """タイマー設定ポップアップを開く（キャッシュ再利用）"""
        self._pause_timer()
        if self._popups["timer"] is None:
            self._popups["timer"] = self._create_timer_popup()
        popup = self._popups["timer"]
        if popup:  # Type narrowing for mypy
            popup.open()

    def open_teacher_popup(self) -> None:
        """教師設定ポップアップを開く（キャッシュ再利用）"""
        self._pause_timer()
        if self._popups["teacher"] is None:
            self._popups["teacher"] = self._create_teacher_popup()
        popup = self._popups["teacher"]
        if popup:  # Type narrowing for mypy
            popup.open()

    def open_ai_popup(self) -> None:
        """AI設定ポップアップを開く（キャッシュ再利用）"""
        self._pause_timer()
        if self._popups["ai"] is None:
            self._popups["ai"] = self._create_ai_popup()
        popup = self._popups["ai"]
        if popup:  # Type narrowing for mypy
            popup.open()

    def open_engine_recovery_popup(self, error_message: str, code: str) -> None:
        """エンジン復旧ポップアップを開く（重複防止付き、タイマー一時停止なし）

        重複防止条件:
        - 現在開いているポップアップがEngineRecoveryPopupの場合、新規作成しない

        注意: 他のopen_*メソッドと異なり、pause_timer()を呼ばない（意図的）
        - エラー条件によるトリガーであり、設定変更ではない
        - 対局中のタイマー状態を保持する

        Args:
            error_message: エラーメッセージ
            code: エラーコード
        """
        current = self._get_popup_open()
        if current and self._is_engine_recovery_popup(current):
            # ログ可読性のため、メッセージを短縮（改行除去、200文字制限）
            truncated = error_message.replace("\n", " ")[:200]
            self._log(
                f"Not opening engine recovery popup (code={code}, msg={truncated}...) as one is already open",
                self._log_level_debug,
            )
            return
        popup = self._create_engine_recovery_popup(error_message, code)
        popup.open()
