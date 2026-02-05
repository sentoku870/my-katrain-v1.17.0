"""isort:skip_file"""
# mypy: ignore-errors
# Note: Contains Windows-specific code paths (ctypes.windll).
# On Linux CI, mypy cannot resolve Windows API calls, but these are guarded by platform checks.

from __future__ import annotations

# first, logging level lower
import os
import sys

os.environ["KCFG_KIVY_LOG_LEVEL"] = os.environ.get("KCFG_KIVY_LOG_LEVEL", "warning")

from kivy.utils import platform as kivy_platform

if kivy_platform == "win":
    from ctypes import c_int64, windll

    if hasattr(windll.user32, "SetProcessDpiAwarenessContext"):
        windll.user32.SetProcessDpiAwarenessContext(c_int64(-4))

import kivy

kivy.require("2.0.0")

# next, icon
from kivy.config import Config

from katrain.core.utils import PATHS, find_package_resource

if kivy_platform == "macosx":
    ICON = find_package_resource("katrain/img/icon.icns")
else:
    ICON = find_package_resource("katrain/img/icon.ico")
Config.set("kivy", "window_icon", ICON)
Config.set("input", "mouse", "mouse,multitouch_on_demand")

# next, certificates on package builds https://github.com/sanderland/katrain/issues/414
if getattr(sys, "frozen", False):
    import ssl

    if ssl.get_default_verify_paths().cafile is None and hasattr(sys, "_MEIPASS"):
        os.environ["SSL_CERT_FILE"] = os.path.join(sys._MEIPASS, "certifi", "cacert.pem")


import glob
import random
import signal
import threading
import time
import traceback
import webbrowser
from queue import Queue
from typing import Any

from kivy.app import App
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.resources import resource_add_path, resource_find
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivymd.app import MDApp

from katrain.core import eval_metrics
from katrain.core.ai import LeelaNotAvailableError, generate_ai_move
from katrain.core.auto_setup import find_cpu_katago  # Phase 89
from katrain.core.base_katrain import KaTrainBase
from katrain.core.constants import (
    DATA_FOLDER,
    HOMEPAGE,
    MODE_ANALYZE,
    MODE_PLAY,
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    OUTPUT_EXTRA_DEBUG,
    OUTPUT_INFO,
    OUTPUT_KATAGO_STDERR,
    SGF_INTERNAL_COMMENTS_MARKER,
    STATUS_ERROR,
    STATUS_INFO,
    VERSION,
)
from katrain.core.engine import KataGoEngine
from katrain.core.errors import EngineError
from katrain.core.game import IllegalMoveException
from katrain.core.lang import DEFAULT_LANGUAGE, i18n
from katrain.core.leela.engine import LeelaEngine
from katrain.core.sgf_parser import Move
from katrain.core.state import EventType  # Phase 107
from katrain.core.test_analysis import (  # Phase 89
    ErrorCategory,
    TestAnalysisResult,
    classify_engine_error,
)
from katrain.gui.badukpan import AnalysisControls, BadukPanControls, BadukPanWidget  # noqa F401
from katrain.gui.controlspanel import ControlsPanel  # noqa F401
from katrain.gui.error_handler import ErrorHandler
from katrain.gui.features.batch_core import (
    collect_batch_options,
    create_log_callback,
    create_progress_callback,
    create_summary_callback,
    is_leela_configured,
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
from katrain.gui.features.commands import (
    analyze_commands,
    export_commands,
    game_commands,
    popup_commands,
)
from katrain.gui.features.karte_export import determine_user_color
from katrain.gui.features.package_export_ui import do_export_package
from katrain.gui.features.report_navigator import open_latest_report, open_output_folder
from katrain.gui.features.resign_hint_popup import schedule_resign_hint_popup
from katrain.gui.features.settings_popup import (
    do_mykatrain_settings_popup,
)
from katrain.gui.features.smart_kifu_practice import (
    show_practice_report_popup,
)
from katrain.gui.features.smart_kifu_profile import (
    show_player_profile_popup,
)
from katrain.gui.features.smart_kifu_training_set import (
    show_training_set_manager,
)

# used in kv
# used in kv
from katrain.gui.kivyutils import (
    PlayerSetupBlock,
)  # noqa: F401
from katrain.gui.leela_manager import LeelaManager
from katrain.gui.managers.active_review_controller import ActiveReviewController
from katrain.gui.managers.config_manager import ConfigManager
from katrain.gui.managers.dialog_factory import DialogFactory
from katrain.gui.managers.game_state_manager import GameStateManager
from katrain.gui.managers.keyboard_manager import KeyboardManager
from katrain.gui.managers.popup_manager import PopupManager
from katrain.gui.managers.quiz_manager import QuizManager
from katrain.gui.managers.summary_manager import SummaryManager

# deleted imports
from katrain.gui.sgf_manager import SGFManager
from katrain.gui.sound import play_sound
from katrain.gui.theme import Theme
from katrain.gui.widgets import I18NFileBrowser, MoveTree, ScoreGraph, SelectionSlider  # noqa F401


class KaTrainGui(Screen, KaTrainBase):
    """Top level class responsible for tying everything together"""

    zen = NumericProperty(0)
    controls = ObjectProperty(None)
    active_review_mode = BooleanProperty(False)  # Phase 93: Active Review Mode

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.error_handler = ErrorHandler(self)
        self.engine: Any = None
        self.engine_unhealthy = False  # Phase 89: For TIMEOUT recovery

        # Leela engine management (Phase 15, refactored in PR #121)
        self._leela_manager = LeelaManager(
            config_getter=self.config,
            logger=self.log,
            update_state_callback=lambda: self.update_state() if self.game else None,
            schedule_resign_popup=lambda result: schedule_resign_hint_popup(self, result),
        )

        # SGF file management (refactored in PR #122)
        self._sgf_manager = SGFManager(
            config_getter=self.config,
            config_setter=lambda section, values: self.set_config_section(section, values),
            save_config=self.save_config,
            logger=self.log,
            status_setter=lambda msg, level: (
                self.controls.set_status(msg, level, check_level=False) if self.controls else None
            ),
            new_game_callback=lambda tree, fast, filename: self._do_new_game(
                move_tree=tree, analyze_fast=fast, sgf_filename=filename
            ),
            redo_callback=lambda moves: self("redo", moves),
            get_game=lambda: self.game,  # type: ignore[return-value]
            get_engine=lambda: self.engine,
            get_board_controls=lambda: getattr(self, "board_controls", None),
            action_dispatcher=lambda action: self(action),
        )

        # Config management (Phase 74)
        self._config_manager = ConfigManager(
            config_dict=self._config,
            save_config=super().save_config,
            logger=self.log,
            log_level_info=OUTPUT_INFO,
        )

        # Summary export management (Phase 96)
        self._summary_manager = SummaryManager(
            get_ctx=lambda: self,
            get_engine=lambda: self.engine,
            get_config=self.config,
            config_manager=self._config_manager,
            logger=self.log,
        )

        # Keyboard input management (Phase 73)
        self._keyboard_manager = KeyboardManager(
            # Kivy dependencies (injected)
            get_platform=lambda: kivy_platform,
            schedule_once=Clock.schedule_once,
            clipboard_copy=Clipboard.copy,
            # State accessors
            get_note_focus=lambda: self.controls.note.focus if self.controls else False,
            get_popup_open=lambda: self.popup_open,
            get_game=lambda: self.game,
            # Action dispatcher
            action_dispatcher=lambda action, *args: self(action, *args),
            # Widget accessors
            get_analysis_controls=lambda: self.analysis_controls,
            get_board_gui=lambda: self.board_gui,
            get_controls=lambda: self.controls,
            get_nav_drawer=lambda: self.nav_drawer,
            get_play_mode=lambda: self.play_mode,
            # State modifiers
            get_set_zen=lambda: (self.zen, lambda v: setattr(self, "zen", v)),
            toggle_continuous_analysis=self.toggle_continuous_analysis,
            toggle_move_num=self.toggle_move_num,
            load_from_clipboard=self._sgf_manager.load_sgf_from_clipboard,
            # Utilities
            logger=self.log,
            status_setter=lambda msg, level: self.controls.set_status(msg, level) if self.controls else None,
            get_debug_level=lambda: self.debug_level,
        )

        # Phase 120: DialogFactory & PopupManager
        self.dialog_factory = DialogFactory(self)
        self._popup_manager = PopupManager(
            create_new_game_popup=self.dialog_factory.create_new_game_popup,
            create_timer_popup=self.dialog_factory.create_timer_popup,
            create_teacher_popup=self.dialog_factory.create_teacher_popup,
            create_ai_popup=self.dialog_factory.create_ai_popup,
            create_engine_recovery_popup=self.dialog_factory.create_engine_recovery_popup,
            get_popup_open=lambda: self.popup_open,
            is_engine_recovery_popup=self.dialog_factory.is_engine_recovery_popup,
            pause_timer=self._safe_pause_timer,
            on_new_game_opened=lambda p: p.content.update_from_current_game(),
            logger=self.log,
            log_level_debug=OUTPUT_DEBUG,
        )

        self.config_popup = None  # popup_commands.do_config_popup()で独自管理

        # Phase 76: GameStateManager
        self._game_state_manager = GameStateManager(
            get_game=lambda: self.game,  # type: ignore[arg-type, return-value]
            get_play_analyze_mode=lambda: self.play_analyze_mode,
            mode_analyze=MODE_ANALYZE,
            switch_ui_mode=lambda: self.play_mode.switch_ui_mode() if self.play_mode else None,
            clear_animating_pv=lambda: setattr(self.board_gui, "animating_pv", None) if self.board_gui else None,
        )

        self.pondering = False
        self.show_move_num = False

        self.message_queue: Queue[Any] = Queue()

        # Phase 97: Active Review Controller
        self._active_review_controller = ActiveReviewController(
            get_ctx=lambda: self,
            get_config=self.config,
            get_game=lambda: self.game,
            get_controls=lambda: self.controls,
            get_mode=lambda: self.active_review_mode,
            set_mode=lambda v: setattr(self, "active_review_mode", v),
            logger=self.log,
        )
        self.bind(active_review_mode=self._on_active_review_mode_change)

        # Phase 98: Quiz Manager
        self._quiz_manager = QuizManager(
            get_ctx=lambda: self,
            get_active_review_controller=lambda: self._active_review_controller,
            update_state_fn=lambda: self.update_state(redraw_board=True),
            logger=self.log,
        )

        # Phase 22: Clock.schedule_interval イベントを追跡（cleanup用）
        self._clock_events: list[Any] = []

        # Phase 107: StateNotifier購読（スレッドセーフ）
        self._ui_update_lock = threading.Lock()  # フラグ保護用ロック
        self._pending_ui_update = None  # Clock event for coalescing
        self._pending_redraw_board = False  # Accumulated redraw flag
        self._state_subscriptions_setup = False
        self._setup_state_subscriptions()

    def _load_export_settings(self) -> dict[str, Any]:
        """Delegates to ConfigManager.load_export_settings() (Phase 74)."""
        return self._config_manager.load_export_settings()

    def _save_export_settings(
        self, sgf_directory: str | None = None, selected_players: list[Any] | None = None
    ) -> None:
        """Delegates to ConfigManager.save_export_settings() (Phase 74)."""
        self._config_manager.save_export_settings(sgf_directory, selected_players)

    def _save_batch_options(self, options: dict[str, Any]) -> None:
        """Delegates to ConfigManager.save_batch_options() (Phase 74)."""
        self._config_manager.save_batch_options(options)

    # ========== Phase 107: StateNotifier購読ハンドラ ==========

    def _setup_state_subscriptions(self) -> None:
        """StateNotifier購読を設定（重複登録防止付き）"""
        if self._state_subscriptions_setup:
            return
        self._state_subscriptions_setup = True

        self.state_notifier.subscribe(EventType.GAME_CHANGED, self._on_game_changed)
        self.state_notifier.subscribe(EventType.ANALYSIS_COMPLETE, self._on_analysis_complete)
        self.state_notifier.subscribe(EventType.CONFIG_UPDATED, self._on_config_updated)

    def _schedule_ui_update(self, redraw_board: bool = False) -> None:
        """UI更新をスケジュール（coalescing付き、スレッドセーフ）

        同一フレーム内の複数イベントを1回のupdate_gui()呼び出しに集約。
        redraw_board=Trueが1回でもあれば、最終的にredraw_board=Trueで呼び出す。

        Note: ANALYSIS_COMPLETEはバックグラウンドスレッドから呼ばれるため、
        _ui_update_lockでフラグアクセスを保護する。
        """
        with self._ui_update_lock:
            # redraw_boardフラグを蓄積（ORで結合）
            self._pending_redraw_board = self._pending_redraw_board or redraw_board

            # 既にスケジュール済みなら何もしない
            if self._pending_ui_update is not None:
                return

            # ロック内でスケジュール（Clock.schedule_onceはスレッドセーフ）
            self._pending_ui_update = Clock.schedule_once(self._do_ui_update, 0)

    def _do_ui_update(self, dt: Any) -> None:
        """UI更新コールバック（メインスレッドで実行）"""
        # フラグ読み取りとリセットをロック内で
        with self._ui_update_lock:
            self._pending_ui_update = None
            redraw = self._pending_redraw_board
            self._pending_redraw_board = False

        # 安全チェック（getattr使用でAttributeError防止）
        game = getattr(self, "game", None)
        if game is None:
            return
        current_node = getattr(game, "current_node", None)
        if current_node is None:
            return

        try:
            self.update_gui(current_node, redraw_board=redraw)
        except Exception as e:
            # コールバック例外をログ（UIスタック防止）
            self.log(f"update_gui failed: {e}", OUTPUT_DEBUG)

    def _on_game_changed(self, event: Any) -> None:
        """GAME_CHANGED → UI更新（redraw_board=True）"""
        self._schedule_ui_update(redraw_board=True)

    def _on_analysis_complete(self, event: Any) -> None:
        """ANALYSIS_COMPLETE → UI更新"""
        self._schedule_ui_update(redraw_board=False)

    def _on_config_updated(self, event: Any) -> None:
        """CONFIG_UPDATED → UI更新"""
        self._schedule_ui_update(redraw_board=False)

    # ========== PopupManager support methods (Phase 75) ==========

    def _safe_pause_timer(self) -> None:
        """タイマーを安全に一時停止（controls/timer未初期化時はスキップ）"""
        timer = getattr(getattr(self, "controls", None), "timer", None)
        if timer:
            timer.paused = True

    # ========== PopupManager support methods (Factories moved to DialogFactory) ==========

    def set_config_section(self, section: str, value: dict[str, Any]) -> None:
        """設定セクションを書き込む（Phase 74: ConfigManagerに委譲）。

        Args:
            section: セクション名（例: "export_settings", "mykatrain_settings", "general"）
            value: セクション全体の値（辞書）

        Note:
            保存は別途 save_config(section) を呼ぶ必要がある。
        """
        self._config_manager.set_section(section, value)

    def _on_engine_status(self, event_type: str, message: str) -> None:
        """Handle engine status updates (Phase 120: Decoupled logging)."""
        if not getattr(self, "controls", None):
            return

        if event_type == "starting":
            self.controls.set_status("KataGo engine starting...", STATUS_INFO)
        elif event_type == "tuning":
            self.controls.set_status(
                "KataGo is tuning settings for first startup, please wait." + message, STATUS_INFO
            )
        elif event_type == "ready":
            self.controls.set_status("KataGo engine ready.", STATUS_INFO)

    def log(self, message: str, level: int = OUTPUT_INFO) -> None:
        super().log(message, level)
        # Phase 120: Removed fragile log parsing.
        # Engine status updates are now handled by _on_engine_status via KataGoEngine callback.
        if (
            level == OUTPUT_ERROR
            or (level == OUTPUT_KATAGO_STDERR and "error" in message.lower() and "tuning" not in message.lower())
        ) and getattr(self, "controls", None):
            self.controls.set_status(f"ERROR: {message}", STATUS_ERROR)

    def handle_animations(self, *_args: Any) -> None:
        if self.pondering:
            self.board_controls.engine_status_pondering += 5
        else:
            self.board_controls.engine_status_pondering = -1

    @property
    def play_analyze_mode(self) -> str:
        return self.play_mode.mode  # type: ignore[no-any-return]

    def toggle_continuous_analysis(self, quiet: bool = False) -> None:
        if self.pondering:
            self.controls.set_status("", STATUS_INFO)
        elif not quiet:  # See #549
            Clock.schedule_once(self.analysis_controls.hints.activate, 0)
        self.pondering = not self.pondering
        self.update_state()

    def toggle_move_num(self) -> None:
        self.show_move_num = not self.show_move_num
        self.update_state()

    def set_analysis_focus_toggle(self, focus: str) -> None:
        """黒／白優先トグル: 同じボタンを2回押すとフォーカス解除に戻す."""
        engine = self.engine
        if not engine or not hasattr(engine, "config"):
            return

        current = engine.config.get("analysis_focus", None)
        # 同じ色をもう一度押したら解除、それ以外ならその色に固定
        new_focus = None if current == focus else focus

        engine.config["analysis_focus"] = new_focus
        self.log(f"analysis_focus set to: {new_focus}", OUTPUT_DEBUG)

        try:
            self.update_focus_button_states()
            # 現在のノード以降のすべての解析をリセットして再実行
            self._re_analyze_from_current_node()
        except Exception as e:
            self.log(f"set_analysis_focus_toggle() failed: {e}", OUTPUT_DEBUG)

    def _re_analyze_from_current_node(self) -> None:
        """現在のノード以降のすべての解析をリセットして再実行する."""
        if not self.game or not self.game.root:
            return

        # 全ノードをリセット（過去のノードを含む）
        for node in self.game.root.nodes_in_tree:
            if hasattr(node, "clear_analysis"):
                node.clear_analysis()  # type: ignore[attr-defined]

        # 再解析を要求（even_if_present=True により強制的に再解析）
        self.game.analyze_all_nodes(analyze_fast=False, even_if_present=True)
        self.log("Re-analysis started with new analysis_focus setting", OUTPUT_DEBUG)

    def restore_last_mode(self) -> None:
        """前回終了時のモードを復元する。"""
        try:
            last_mode = self.config("ui_state/last_mode", MODE_PLAY)
            if last_mode == MODE_ANALYZE and self.play_mode.mode == MODE_PLAY:
                # Analyzeモードを復元
                self.play_mode.analyze.trigger_action(duration=0)
            elif last_mode == MODE_PLAY and self.play_mode.mode == MODE_ANALYZE:
                # Playモードを復元
                self.play_mode.play.trigger_action(duration=0)
        except Exception as e:
            self.log(f"restore_last_mode() failed: {e}", OUTPUT_DEBUG)

    def update_focus_button_states(self) -> None:
        """黒優先・白優先ボタンのラベルを analysis_focus に合わせて更新する."""
        engine = self.engine
        if not engine or not hasattr(engine, "config"):
            return

        focus = engine.config.get("analysis_focus", None)

        board_controls = getattr(self, "board_controls", None)
        if not board_controls:
            return

        ids_map = getattr(board_controls, "ids", {}) or {}
        black_btn = ids_map.get("black_focus_btn")
        white_btn = ids_map.get("white_focus_btn")

        # ★付き表記で現在の優先側を示す
        if black_btn is not None:
            black_btn.text = "★黒優先" if focus == "black" else "黒優先"
        if white_btn is not None:
            white_btn.text = "★白優先" if focus == "white" else "白優先"

    def start(self) -> None:
        if self.engine:
            return
        self.board_gui.trainer_config = self.config("trainer")
        self.board_gui.trainer_config = self.config("trainer")
        self.engine = KataGoEngine(self, self.config("engine"), status_callback=self._on_engine_status)

        # Set up engine error handler with rich context
        def _handle_engine_error(message: str, code: Any = None, allow_popup: bool = True) -> None:
            """Handle engine errors with rich context.

            Args:
                message: Error message string
                code: Optional error code
                allow_popup: Whether to show recovery popup (used by engine.py)
            """
            context = {
                "original_error": repr(message),
                "error_code": code,
            }

            self.error_handler.handle(
                EngineError(
                    str(message),
                    user_message="Engine error occurred",
                    context=context,
                ),
                notify_user=allow_popup,
            )

        self.engine.on_error = _handle_engine_error

        # 起動時は常に「フォーカスなし」に戻す（本家と同じ初期状態）
        try:
            if hasattr(self.engine, "config") and isinstance(self.engine.config, dict):
                self.engine.config["analysis_focus"] = None
        except Exception:
            pass

        threading.Thread(target=self._message_loop_thread, daemon=True).start()
        sgf_args = [
            f
            for f in sys.argv[1:]
            if os.path.isfile(f) and any(f.lower().endswith(ext) for ext in ["sgf", "ngf", "gib"])
        ]
        if sgf_args:
            self.load_sgf_file(sgf_args[0], fast=True, rewind=True)
        else:
            # _do_new_game 内の自動 Play/Analyze 切り替えを一時的に無効化
            self._suppress_play_mode_switch = True
            try:
                self._do_new_game()
            finally:
                self._suppress_play_mode_switch = False

        # Phase 22: Clockイベントを追跡（cleanup用）
        animation_event = Clock.schedule_interval(self.handle_animations, 0.1)
        self._clock_events.append(animation_event)

        Window.request_keyboard(None, self, "").bind(
            on_key_down=self._keyboard_manager.on_keyboard_down,
            on_key_up=self._keyboard_manager.on_keyboard_up,
        )

        def set_focus_event(*args: Any) -> None:
            self._keyboard_manager.last_focus_event = time.time()

        MDApp.get_running_app().root_window.bind(focus=set_focus_event)

        # 前回終了時のモードを復元
        Clock.schedule_once(lambda dt: self.restore_last_mode(), 0.3)

        # Initialize focus button states on startup
        Clock.schedule_once(lambda dt: self.update_focus_button_states(), 0.5)

    def update_gui(self, cn: Any, redraw_board: bool = False) -> None:
        # Handle prisoners and next player display
        if not self.game:
            return

        # Phase 120: Delegated UI updates to BadukPanControls
        if self.board_controls:
            self.board_controls.update_controls(self)


        # redraw board/stones
        if redraw_board:
            self.board_gui.draw_board()
        self.board_gui.redraw_board_contents_trigger()
        self.controls.update_evaluation()
        self.controls.update_timer(1)
        # update move tree
        if self.game:
            self.controls.move_tree.current_node = self.game.current_node

    # === Leela Engine Management (Phase 15, refactored in PR #121) ===
    # Delegation to LeelaManager for backward compatibility

    @property
    def leela_engine(self) -> LeelaEngine | None:
        """Access to leela_engine for backward compatibility."""
        return self._leela_manager.leela_engine

    def start_leela_engine(self) -> bool:
        """Start Leela engine (no-op if already running)."""
        return self._leela_manager.start_engine(self)

    def shutdown_leela_engine(self) -> None:
        """Shutdown Leela engine."""
        self._leela_manager.shutdown_engine()

    # =========================================================================
    # Phase 89: Auto Setup Mode Methods
    # =========================================================================

    def restart_engine_with_fallback(self, fallback_type: str) -> tuple[bool, TestAnalysisResult]:
        """Restart engine with CPU fallback and verify.

        Processing flow:
        1. Find CPU binary
        2. Restart engine with CPU binary
        3. Run minimal analysis to verify
        4. Only persist if verification succeeds

        Persistence policy:
        - Only on verification success: persist engine.katago
        - On verification failure: do NOT persist (keep original settings)

        Args:
            fallback_type: Type of fallback ("cpu" for now).

        Returns:
            (success, result) tuple:
            - success: True if verification passed
            - result: TestAnalysisResult with details
        """
        if fallback_type != "cpu":
            return False, TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.UNKNOWN,
                error_message=f"Unknown fallback type: {fallback_type}",
            )

        # Find CPU binary
        cpu_katago = find_cpu_katago()
        if cpu_katago is None:
            return False, TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.ENGINE_START_FAILED,
                error_message="CPU KataGo binary not found",
            )

        # Shutdown current engine
        if self.engine:
            self.engine.shutdown(finish=False)
            self.engine = None

        # Create new engine with CPU binary
        try:
            engine_config = dict(self.config("engine"))
            engine_config["katago"] = cpu_katago
            self.engine = KataGoEngine(self, engine_config)
        except Exception as e:
            return False, TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.ENGINE_START_FAILED,
                error_message=f"Failed to start CPU engine: {e}",
            )

        # Verify with minimal analysis
        result = self._verify_engine_works()
        if result.success:
            # Persist only on success
            self._save_engine_katago_path(cpu_katago)
            self.engine_unhealthy = False

        return result.success, result

    def restart_engine(self) -> bool:
        """Restart engine with same settings (for TIMEOUT recovery).

        Returns:
            True if engine restarted successfully.
        """
        if self.engine:
            self.engine.shutdown(finish=False)
            self.engine = None

        try:
            engine_config = self.config("engine")
            self.engine = KataGoEngine(self, engine_config)
            self.engine_unhealthy = False
            return self.engine.check_alive()  # type: ignore[no-any-return]
        except Exception:
            return False

    def save_auto_setup_result(self, success: bool) -> None:
        """Persist test analysis result to config.

        Updates auto_setup section:
        - first_run_completed = True
        - last_test_result = "success" | "failed"

        Args:
            success: True if test analysis succeeded.
        """
        auto_setup = dict(self._config.get("auto_setup", {}))
        auto_setup["first_run_completed"] = True
        auto_setup["last_test_result"] = "success" if success else "failed"
        self._config["auto_setup"] = auto_setup
        self.save_config("auto_setup")

    def _verify_engine_works(self, timeout_seconds: float = 10.0) -> TestAnalysisResult:
        """Verify engine works with minimal analysis.

        Args:
            timeout_seconds: Timeout for analysis response.

        Returns:
            TestAnalysisResult with success/failure details.
        """
        if not self.engine:
            return TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.ENGINE_START_FAILED,
                error_message="Engine is None",
            )

        if not self.engine.check_alive():
            # Collect error from stderr if available
            error_text = ""
            if hasattr(self.engine, "stderr_queue"):
                while not self.engine.stderr_queue.empty():
                    try:
                        error_text += self.engine.stderr_queue.get_nowait() + "\n"
                    except Exception:
                        break

            error_category = classify_engine_error(error_text) if error_text else ErrorCategory.ENGINE_START_FAILED
            return TestAnalysisResult(
                success=False,
                error_category=error_category,
                error_message=error_text[:200] if error_text else "Engine not alive",
            )

        # Create minimal query
        query = self.engine.create_minimal_analysis_query()
        result_event = threading.Event()
        analysis_result: dict[str, Any] = {}

        def on_result(analysis: dict[str, Any]) -> None:
            analysis_result.update(analysis)
            result_event.set()

        try:
            self.engine.request_analysis(
                analysis_node=None,
                callback=on_result,
                override_queries=[query],
            )
        except Exception as e:
            return TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.ENGINE_START_FAILED,
                error_message=f"Failed to request analysis: {e}",
            )

        # Wait for result
        is_timeout = not result_event.wait(timeout=timeout_seconds)
        if is_timeout:
            return TestAnalysisResult(
                success=False,
                error_category=ErrorCategory.TIMEOUT,
                error_message=f"Analysis did not respond within {timeout_seconds}s",
            )

        # Check for errors in result
        if "error" in analysis_result:
            error_text = str(analysis_result.get("error", ""))
            return TestAnalysisResult(
                success=False,
                error_category=classify_engine_error(error_text),
                error_message=error_text[:200],
            )

        return TestAnalysisResult(
            success=True,
            error_category=None,
            error_message=None,
        )

    def _save_engine_katago_path(self, katago_path: str) -> None:
        """Save engine.katago path to config.

        Args:
            katago_path: Path to KataGo binary.
        """
        self.update_engine_config(katago=katago_path)

    def cleanup(self) -> None:
        """アプリ終了時のクリーンアップ（Phase 22）

        on_request_close から呼び出される。
        - Clockイベントをキャンセル
        - 子コンポーネントのcleanupを呼び出し
        """
        # Clockイベントのキャンセル
        for event in self._clock_events:
            event.cancel()
        self._clock_events.clear()

        # 子コンポーネントのcleanup
        if hasattr(self, "controls") and self.controls and hasattr(self.controls, "cleanup"):
            self.controls.cleanup()

        self.log("KaTrainGui cleanup completed", OUTPUT_DEBUG)

    def request_leela_analysis(self) -> None:
        """Request Leela analysis for current node (with debounce and duplicate prevention)."""
        if not self.game:
            return
        self._leela_manager.request_analysis(self.game.current_node, self)

    def update_state(self, redraw_board: bool = False) -> None:  # redirect to message queue thread
        self("update_state", redraw_board=redraw_board)

    def _do_update_state(
        self, redraw_board: bool = False
    ) -> None:  # is called after every message and on receiving analyses and config changes
        # AI and Trainer/auto-undo handlers
        if not self.game or not self.game.current_node:
            return
        cn = self.game.current_node
        last_player, next_player = self.players_info[cn.player], self.players_info[cn.next_player]
        if self.play_analyze_mode == MODE_PLAY and self.nav_drawer.state != "open" and self.popup_open is None:
            points_lost = cn.points_lost
            if (
                last_player.human
                and cn.analysis_complete
                and points_lost is not None
                and points_lost > self.config("trainer/eval_thresholds")[-4]
            ):
                self.play_mistake_sound(cn)
            teaching_undo = cn.player and last_player.being_taught and cn.parent
            if (
                teaching_undo
                and cn.analysis_complete
                and cn.parent is not None
                and hasattr(cn.parent, "analysis_complete")
                and cn.parent.analysis_complete  # type: ignore[attr-defined]
                and not cn.children
                and not self.game.end_result
            ):
                self.game.analyze_undo(cn)  # not via message loop
            if (
                cn.analysis_complete
                and next_player.ai
                and not cn.children
                and not self.game.end_result
                and not (teaching_undo and cn.auto_undo is None)
            ):  # cn mismatch stops this if undo fired. avoid message loop here or fires repeatedly.
                self._do_ai_move(cn)
                Clock.schedule_once(self._play_stone_sound, 0.25)
        if self.engine:
            if self.pondering:
                self.game.analyze_extra("ponder")
            else:
                self.engine.stop_pondering()
        # Leela engine lifecycle management (Phase 15)
        if not self.config("leela/enabled"):
            # Shutdown if disabled
            if self.leela_engine:
                self.shutdown_leela_engine()
        elif self.analysis_controls.hints.active:
            # Request analysis if enabled and hints are on
            self.request_leela_analysis()
        Clock.schedule_once(lambda _dt: self.update_gui(cn, redraw_board=redraw_board), -1)  # trigger?

    def update_player(self, bw: str, **kwargs: Any) -> None:
        super().update_player(bw, **kwargs)
        if self.game:
            sgf_name = self.game.root.get_property("P" + bw)
            sgf_name_str = sgf_name if isinstance(sgf_name, str) else None
            self.players_info[bw].name = (
                None if not sgf_name_str or SGF_INTERNAL_COMMENTS_MARKER in sgf_name_str else sgf_name_str
            )  # type: ignore[assignment]
        if self.controls:
            self.controls.update_players()
            self.update_state()
        for player_setup_block in PlayerSetupBlock.INSTANCES:
            player_setup_block.update_player_info(bw, self.players_info[bw])

    def set_note(self, note: str) -> None:
        # Guard: kv on_text may fire before _game_state_manager is initialized
        if hasattr(self, "_game_state_manager"):
            self._game_state_manager.set_note(note)
        elif self.game and self.game.current_node:
            # Fallback: direct assignment during early UI construction
            self.game.current_node.note = note

    # The message loop is here to make sure moves happen in the right order, and slow operations don't hang the GUI
    def _message_loop_thread(self) -> None:
        while True:
            msg_name = "<unknown>"  # Safe fallback for error message
            game, msg, args, kwargs = self.message_queue.get()
            try:
                msg_name = msg  # Capture for error handling
                self.log(f"Message Loop Received {msg}: {args} for Game {game}", OUTPUT_EXTRA_DEBUG)
                if not self.game or game != self.game.game_id:
                    self.log(
                        f"Message skipped as it is outdated (current game is {self.game.game_id if self.game else None}",
                        OUTPUT_EXTRA_DEBUG,
                    )
                    continue
                msg = msg.replace("-", "_")
                fn = getattr(self, f"_do_{msg}")
                fn(*args, **kwargs)
                if msg != "update_state":
                    self._do_update_state()
            except Exception as exc:
                self.error_handler.handle(
                    exc,
                    notify_user=True,
                    fallback_message=f"Action '{msg_name}' failed",
                )

    def __call__(self, message: str, *args: Any, **kwargs: Any) -> None:
        if self.game:
            if message.endswith("popup"):  # gui code needs to run in main kivy thread.
                fn = getattr(self, f"_do_{message.replace('-', '_')}")
                Clock.schedule_once(lambda _dt: fn(*args, **kwargs), -1)
            else:  # game related actions
                self.message_queue.put([self.game.game_id, message, args, kwargs])

    def _do_new_game(self, move_tree: Any = None, analyze_fast: bool = False, sgf_filename: str | None = None) -> None:
        game_commands.do_new_game(self, move_tree, analyze_fast, sgf_filename)

    def _do_insert_mode(self, mode: str = "toggle") -> None:
        self._game_state_manager.do_insert_mode(mode)

    def _do_ai_move(self, node: Any = None) -> None:
        if not self.game or (node is None or self.game.current_node == node):
            mode = self.next_player_info.strategy
            settings = self.config(f"ai/{mode}")
            if settings is not None:
                try:
                    if self.game:
                        generate_ai_move(self.game, mode, settings)
                except LeelaNotAvailableError as e:
                    self.log(str(e), OUTPUT_ERROR)
                    self.controls.set_status(str(e), STATUS_ERROR)
            else:
                self.log(f"AI Mode {mode} not found!", OUTPUT_ERROR)

    def _do_undo(self, n_times: int | str = 1) -> None:
        # "smart" mode handling stays here (requires player_info access)
        times: int = 1
        if n_times == "smart":
            times = 1
            if self.play_analyze_mode == MODE_PLAY and self.last_player_info.ai and self.next_player_info.human:
                times = 2
        elif isinstance(n_times, int):
            times = n_times
        self._game_state_manager.do_undo(times)

    def _do_reset_analysis(self) -> None:
        self._game_state_manager.do_reset_analysis()

    def _do_resign(self) -> None:
        self._game_state_manager.do_resign()

    def _do_redo(self, n_times: int = 1) -> None:
        self._game_state_manager.do_redo(n_times)

    def _do_rotate(self) -> None:
        self.board_gui.rotate_gridpos()

    def _do_find_mistake(self, fn: str = "redo") -> None:
        self.board_gui.animating_pv = None
        getattr(self.game, fn)(9999, stop_on_mistake=self.config("trainer/eval_thresholds")[-4])

    # ------------------------------------------------------------------
    # 重要局面ナビゲーション
    # ------------------------------------------------------------------
    def _do_prev_important(self) -> None:
        self._game_state_manager.do_prev_important()

    def _do_next_important(self) -> None:
        self._game_state_manager.do_next_important()

    def _do_switch_branch(self, *args: Any) -> None:
        self.board_gui.animating_pv = None
        self.controls.move_tree.switch_branch(*args)

    def _play_stone_sound(self, _dt: Any = None) -> None:
        play_sound(random.choice(Theme.STONE_SOUNDS))

    def _do_play(self, coords: Any) -> None:
        self.board_gui.animating_pv = None
        if not self.game:
            return
        try:
            old_prisoner_count = self.game.prisoner_count["W"] + self.game.prisoner_count["B"]
            self.game.play(Move(coords, player=self.next_player_info.player))
            if old_prisoner_count < self.game.prisoner_count["W"] + self.game.prisoner_count["B"]:
                play_sound(Theme.CAPTURING_SOUND)
            elif self.game and not self.game.current_node.is_pass:
                self._play_stone_sound()

        except IllegalMoveException as e:
            self.controls.set_status(f"Illegal Move: {str(e)}", STATUS_ERROR)

    # =========================================================================
    # Phase 97: Active Review Mode (delegated to ActiveReviewController)
    # =========================================================================

    def is_fog_active(self) -> bool:
        """Delegates to ActiveReviewController (Phase 97)."""
        return self._active_review_controller.is_fog_active()

    def _disable_active_review_if_needed(self) -> None:
        """Delegates to ActiveReviewController (Phase 97)."""
        self._active_review_controller.disable_if_needed()

    def toggle_active_review(self) -> None:
        """Delegates to ActiveReviewController (Phase 97)."""
        self._active_review_controller.toggle()

    def _on_active_review_mode_change(self, instance: Any, value: Any) -> None:
        """Delegates to ActiveReviewController (Phase 97)."""
        self._active_review_controller.on_mode_change(value)

    def _do_active_review_guess(self, coords: Any) -> None:
        """Delegates to ActiveReviewController (Phase 97)."""
        self._active_review_controller.handle_guess(coords)

    def _do_analyze_extra(self, mode: str, **kwargs: Any) -> None:
        analyze_commands.do_analyze_extra(self, mode, **kwargs)

    def _do_selfplay_setup(self, until_move: int | float, target_b_advantage: float | None = None) -> None:
        if not self.game:
            return
        self.game.selfplay(int(until_move) if isinstance(until_move, float) else until_move, target_b_advantage)

    def _do_select_box(self) -> None:
        self.controls.set_status(i18n._("analysis:region:start"), STATUS_INFO)
        self.board_gui.selecting_region_of_interest = True

    def _do_new_game_popup(self) -> None:
        self._popup_manager.open_new_game_popup()

    def _do_timer_popup(self) -> None:
        self._popup_manager.open_timer_popup()

    def _do_teacher_popup(self) -> None:
        self._popup_manager.open_teacher_popup()

    def _do_config_popup(self) -> None:
        popup_commands.do_config_popup(self)

    def _do_ai_popup(self) -> None:
        self._popup_manager.open_ai_popup()

    def _do_engine_recovery_popup(self, error_message: str, code: Any) -> None:
        self._popup_manager.open_engine_recovery_popup(error_message, code)

    def _do_tsumego_frame(self, ko: bool, margin: int) -> None:
        from katrain.core.tsumego_frame import tsumego_frame_from_katrain_game

        if not self.game or not self.game.stones:
            return

        black_to_play_p = self.next_player_info.player == "B"
        node, analysis_region = tsumego_frame_from_katrain_game(
            self.game, self.game.komi, black_to_play_p, ko_p=ko, margin=margin
        )
        self.game.set_current_node(node)
        if self.play_mode.mode == MODE_PLAY:
            self.play_mode.switch_ui_mode()  # go to analysis mode
        if analysis_region:
            flattened_region = [
                analysis_region[0][1],
                analysis_region[0][0],
                analysis_region[1][1],
                analysis_region[1][0],
            ]
            self.game.set_region_of_interest(tuple(flattened_region))  # type: ignore[arg-type]
        if self.game:
            node.analyze(self.game.engines[node.next_player])
        self.update_state(redraw_board=True)

    def play_mistake_sound(self, node: Any) -> None:
        if self.config("timer/sound") and node.played_mistake_sound is None and Theme.MISTAKE_SOUNDS:
            node.played_mistake_sound = True
            play_sound(random.choice(Theme.MISTAKE_SOUNDS))

    # === SGF File Management (refactored in PR #122) ===
    # Delegation to SGFManager for backward compatibility

    def load_sgf_file(self, file: str, fast: bool = False, rewind: bool = True) -> None:
        """Load SGF file. Delegates to SGFManager."""
        self._sgf_manager.load_sgf_file(file, fast=fast, rewind=rewind)

    def _do_analyze_sgf_popup(self) -> None:
        """Open SGF analysis popup. Delegates to SGFManager."""
        self._sgf_manager.do_analyze_sgf_popup(self)

    def _do_open_recent_sgf(self) -> None:
        """Open recent SGF dropdown. Delegates to SGFManager."""
        self._sgf_manager.open_recent_sgf()

    def _do_save_game(self, filename: str | None = None) -> None:
        """Save game. Delegates to export_commands."""
        export_commands.do_save_game(self, filename)

    def _do_save_game_as_popup(self) -> None:
        """Open save-as popup. Delegates to SGFManager."""
        self._sgf_manager.do_save_game_as_popup(self)

    def _do_export_karte(self, *args: Any, **kwargs: Any) -> None:
        """Export karte. Delegates to export_commands."""
        export_commands.do_export_karte(self, self._do_mykatrain_settings_popup)

    def _do_export_package(self, anonymize: bool = False, *args: Any, **kwargs: Any) -> None:
        """Export LLM package. Delegates to package_export_ui.do_export_package()."""
        do_export_package(self, anonymize=anonymize)

    def _do_open_latest_report(self, *args: Any, **kwargs: Any) -> None:
        """Open the most recent report file."""
        open_latest_report(self)

    def _do_open_output_folder(self, *args: Any, **kwargs: Any) -> None:
        """Open the output folder in the system file manager."""
        open_output_folder(self)

    def _determine_user_color(self, username: str) -> str | None:
        """Determine user's color based on player names in SGF.

        Delegates to katrain.gui.features.karte_export.determine_user_color().
        """
        if not self.game:
            return None
        return determine_user_color(self.game, username)

    def _do_export_summary(self, *args: Any, **kwargs: Any) -> None:
        """Delegates to SummaryManager.do_export_summary() (Phase 96)."""
        self._summary_manager.do_export_summary(*args, **kwargs)

    def _do_export_summary_ui(self, *args: Any, **kwargs: Any) -> None:
        """Delegates to SummaryManager.do_export_summary_ui() (Phase 96)."""
        self._summary_manager.do_export_summary_ui(*args, **kwargs)

    def _extract_analysis_from_sgf_node(self, node: Any) -> dict[str, Any]:
        """Delegates to SummaryManager (Phase 96)."""
        result = self._summary_manager.extract_analysis_from_sgf_node(node)
        return result if result is not None else {}

    def _extract_sgf_statistics(self, path: str) -> dict[str, Any] | None:
        """Delegates to SummaryManager (Phase 96)."""
        return self._summary_manager.extract_sgf_statistics(path)

    def _scan_player_names(self, sgf_files: list[Any]) -> dict[str, Any]:
        """Delegates to SummaryManager (Phase 96)."""
        return self._summary_manager.scan_player_names(sgf_files)

    def _scan_and_show_player_selection(self, sgf_files: list[Any]) -> None:
        """Delegates to SummaryManager (Phase 96)."""
        self._summary_manager.scan_and_show_player_selection(sgf_files)

    def _process_summary_with_selected_players(self, sgf_files: list[Any], selected_players: list[Any]) -> None:
        """Delegates to SummaryManager (Phase 96)."""
        self._summary_manager.process_summary_with_selected_players(sgf_files, selected_players)

    def _show_player_selection_dialog(self, sorted_players: list[Any], sgf_files: list[Any]) -> None:
        """Delegates to SummaryManager (Phase 96)."""
        self._summary_manager.show_player_selection_dialog(sorted_players, sgf_files)

    def _process_and_export_summary(
        self, sgf_paths: list[Any], progress_popup: Any, selected_players: list[Any] | None = None
    ) -> None:
        """Delegates to SummaryManager (Phase 96)."""
        self._summary_manager.process_and_export_summary(sgf_paths, progress_popup, selected_players)

    def _categorize_games_by_stats(self, game_stats_list: list[Any], focus_player: str) -> dict[str, Any]:
        """Delegates to SummaryManager (Phase 96)."""
        return self._summary_manager.categorize_games_by_stats(game_stats_list, focus_player)

    def _collect_rank_info(self, stats_list: list[Any], focus_player: str) -> str:
        """Delegates to SummaryManager (Phase 96)."""
        result = self._summary_manager.collect_rank_info(stats_list, focus_player)
        return result if result is not None else ""

    def _build_summary_from_stats(self, stats_list: list[Any], focus_player: str | None = None) -> str:
        """Delegates to SummaryManager (Phase 96)."""
        return self._summary_manager.build_summary_from_stats(stats_list, focus_player)

    def _save_summaries_per_player(
        self, game_stats_list: list[Any], selected_players: list[Any], progress_popup: Any
    ) -> None:
        """Delegates to SummaryManager (Phase 96)."""
        self._summary_manager.save_summaries_per_player(game_stats_list, selected_players, progress_popup)

    def _save_categorized_summaries_from_stats(
        self, categorized_games: dict[str, Any], player_name: str, progress_popup: Any
    ) -> None:
        """Delegates to SummaryManager (Phase 96)."""
        self._summary_manager.save_categorized_summaries_from_stats(categorized_games, player_name, progress_popup)

    def _save_summary_file(self, summary_text: str, player_name: str, progress_popup: Any) -> None:
        """Delegates to SummaryManager (Phase 96)."""
        self._summary_manager.save_summary_file(summary_text, player_name, progress_popup)

    def _do_quiz_popup(self) -> None:
        """Delegates to QuizManager (Phase 98)."""
        self._quiz_manager.do_quiz_popup()

    def _do_mykatrain_settings_popup(self) -> None:
        """Delegates to settings_popup.do_mykatrain_settings_popup()."""
        do_mykatrain_settings_popup(self)

    def _do_training_set_popup(self) -> None:
        """Show Training Set Manager popup. Delegates to smart_kifu_training_set."""
        show_training_set_manager(self, self)

    def _do_player_profile_popup(self) -> None:
        """Show Player Profile popup. Delegates to smart_kifu_profile."""
        show_player_profile_popup(self, self)

    def _do_practice_report_popup(self) -> None:
        """Show Practice Report popup. Delegates to smart_kifu_practice."""
        show_practice_report_popup(self, self)

    def _do_batch_analyze_popup(self) -> None:
        """Show batch analyze folder dialog. Delegates to batch_ui/batch_core functions."""
        import threading

        # 1. Load saved options
        mykatrain_settings = self.config("mykatrain_settings") or {}
        batch_options = mykatrain_settings.get("batch_options", {})
        default_input_dir = batch_options.get("input_dir") or mykatrain_settings.get("batch_export_input_directory", "")
        default_output_dir = batch_options.get("output_dir", "")

        # 2. Build widgets
        # Phase 87.5: Check if Leela is configured for gating
        leela_enabled = is_leela_configured(self)
        main_layout, widgets = build_batch_popup_widgets(
            batch_options, default_input_dir, default_output_dir, leela_enabled
        )

        # 3. Create popup
        popup = create_batch_popup(main_layout)

        # 4. Setup state
        is_running = [False]
        cancel_flag = [False]

        # 5. Create callbacks
        filter_buttons = {
            "filter_black": widgets["filter_black"],
            "filter_white": widgets["filter_white"],
            "filter_both": widgets["filter_both"],
        }
        get_player_filter = create_get_player_filter_fn(filter_buttons)

        log_cb = create_log_callback(widgets["log_text"], widgets["log_scroll"])
        progress_cb = create_progress_callback(widgets["progress_label"])
        summary_cb = create_summary_callback(
            is_running,
            widgets["start_button"],
            widgets["close_button"],
            widgets["progress_label"],
            log_cb,
        )

        def run_batch_thread() -> None:
            """バッチスレッド実行（threading.Thread から呼ばれる）"""
            options = collect_batch_options(widgets, get_player_filter)
            run_batch_in_thread(self, options, cancel_flag, progress_cb, log_cb, summary_cb, self._save_batch_options)

        def start_batch_thread() -> None:
            """バッチスレッドを起動"""
            threading.Thread(target=run_batch_thread, daemon=True).start()

        # 6. Bind callbacks
        on_start = create_on_start_callback(
            self, widgets, is_running, cancel_flag, get_player_filter, start_batch_thread
        )
        on_close = create_on_close_callback(popup, is_running)
        browse_input = create_browse_callback(widgets["input_input"], "Select input folder", self)
        browse_output = create_browse_callback(widgets["output_input"], "Select output folder", self)

        widgets["start_button"].bind(on_release=on_start)
        widgets["close_button"].bind(on_release=on_close)
        widgets["input_browse"].bind(on_release=browse_input)
        widgets["output_browse"].bind(on_release=browse_output)

        # Phase 87.5: Setup Leela button callback
        def open_leela_settings(*_args: Any) -> None:
            popup.dismiss()
            from kivy.clock import Clock

            Clock.schedule_once(lambda dt: do_mykatrain_settings_popup(self, initial_tab="leela"), 0.15)

        widgets["leela_settings_btn"].bind(on_press=open_leela_settings)

        # 7. Open popup
        popup.open()

    def _format_points_loss(self, loss: float | None) -> str:
        """Delegates to QuizManager (Phase 98)."""
        return self._quiz_manager.format_points_loss(loss)

    def _start_quiz_session(self, quiz_items: list[eval_metrics.QuizItem]) -> None:
        """Delegates to QuizManager (Phase 98)."""
        self._quiz_manager.start_quiz_session(quiz_items)

    def _do_diagnostics_popup(self) -> None:
        """Show diagnostics popup for bug report generation."""
        from katrain.gui.features.diagnostics_popup import show_diagnostics_popup

        show_diagnostics_popup(self)

    def _do_engine_compare_popup(self) -> None:
        """Show engine comparison popup for KataGo/Leela analysis."""
        from katrain.gui.features.engine_compare_popup import show_engine_compare_popup

        show_engine_compare_popup(self)

    def _do_skill_radar_popup(self) -> None:
        """Show skill radar popup for 5-axis skill profile."""
        from katrain.gui.features.skill_radar_popup import show_skill_radar_popup

        show_skill_radar_popup(self)

    def load_sgf_from_clipboard(self) -> None:
        """Load SGF from clipboard. Delegates to SGFManager."""
        self._sgf_manager.load_sgf_from_clipboard()

    def on_touch_up(self, touch: Any) -> bool:
        if touch.is_mouse_scrolling:
            touching_board = self.board_gui.collide_point(*touch.pos) or self.board_controls.collide_point(*touch.pos)
            touching_control_nonscroll = self.controls.collide_point(
                *touch.pos
            ) and not self.controls.notes_panel.collide_point(*touch.pos)
            if self.board_gui.animating_pv is not None and touching_board:
                if touch.button == "scrollup":
                    self.board_gui.adjust_animate_pv_index(1)
                elif touch.button == "scrolldown":
                    self.board_gui.adjust_animate_pv_index(-1)
            elif touching_board or touching_control_nonscroll:  # scroll through moves
                if touch.button == "scrollup":
                    self("redo")
                elif touch.button == "scrolldown":
                    self("undo")
        return super().on_touch_up(touch)  # type: ignore[no-any-return]

    @property
    def shortcuts(self) -> dict[str, Any]:
        """Delegate to KeyboardManager for backward compatibility."""
        return self._keyboard_manager.shortcuts

    @property
    def popup_open(self) -> Popup | None:
        app = App.get_running_app()
        if app:
            first_child = app.root_window.children[0]
            return first_child if isinstance(first_child, Popup) else None
        return None


class KaTrainApp(MDApp):
    gui = ObjectProperty(None)
    language = StringProperty(DEFAULT_LANGUAGE)

    def __init__(self) -> None:
        super().__init__()

    def is_valid_window_position(self, left: int, top: int, width: int, height: int) -> bool:
        try:
            from screeninfo import get_monitors

            monitors = get_monitors()
            for monitor in monitors:
                if (
                    left >= monitor.x
                    and left + width <= monitor.x + monitor.width
                    and top >= monitor.y
                    and top + height <= monitor.y + monitor.height
                ):
                    return True
            return False
        except Exception:
            return True  # yolo

    def build(self) -> KaTrainGui:
        self.icon = ICON  # how you're supposed to set an icon

        self.title = f"KaTrain v{VERSION}"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Gray"
        self.theme_cls.primary_hue = "200"

        kv_file = find_package_resource("katrain/gui.kv")
        popup_kv_file = find_package_resource("katrain/popups.kv")
        resource_add_path(PATHS["PACKAGE"] + "/fonts")
        resource_add_path(PATHS["PACKAGE"] + "/sounds")
        resource_add_path(PATHS["PACKAGE"] + "/img")
        resource_add_path(os.path.abspath(os.path.expanduser(DATA_FOLDER)))  # prefer resources in .katrain

        from katrain.gui.theme_loader import load_theme_overrides

        theme_files = glob.glob(os.path.join(os.path.expanduser(DATA_FOLDER), "theme*.json"))
        for theme_file in sorted(theme_files):
            load_theme_overrides(theme_file, Theme)

        Theme.DEFAULT_FONT = resource_find(Theme.DEFAULT_FONT)
        Builder.load_file(kv_file)

        Window.bind(on_request_close=self.on_request_close)
        Window.bind(on_dropfile=lambda win, file: self.gui.load_sgf_file(file.decode("utf8")))
        self.gui = KaTrainGui()
        Builder.load_file(popup_kv_file)

        win_left: int | None = None
        win_top: int | None = None
        win_size: list[Any] | None = None
        if self.gui.config("ui_state/restoresize", True):
            win_size = self.gui.config("ui_state/size", [])
            win_left = self.gui.config("ui_state/left", None)
            win_top = self.gui.config("ui_state/top", None)
        if not win_size:
            window_scale_fac: float = 1.0
            try:
                from screeninfo import get_monitors

                for m in get_monitors():
                    window_scale_fac = min(window_scale_fac, (m.height - 100) / 1000, (m.width - 100) / 1300)
            except Exception:
                window_scale_fac = 0.85
            win_size = [1300 * window_scale_fac, 1000 * window_scale_fac]
        self.gui.log(f"Setting window size to {win_size} and position to {[win_left, win_top]}", OUTPUT_DEBUG)
        Window.size = (win_size[0], win_size[1])
        if (
            win_left is not None
            and win_top is not None
            and self.is_valid_window_position(int(win_left), int(win_top), int(win_size[0]), int(win_size[1]))
        ):
            Window.left = int(win_left)
            Window.top = int(win_top)

        return self.gui  # type: ignore[return-value, no-any-return]

    def on_language(self, _instance: Any, language: str) -> None:
        self.gui.log(f"Switching language to {language}", OUTPUT_INFO)
        i18n.switch_lang(language)
        general = dict(self.gui.config("general") or {})
        general["lang"] = language
        self.gui.set_config_section("general", general)
        self.gui.save_config()
        if self.gui.game:
            self.gui.update_state()
            self.gui.controls.set_status("", STATUS_INFO)

    def webbrowser(self, site_key: str) -> None:
        websites = {
            "homepage": HOMEPAGE + "#manual",
            "support": HOMEPAGE + "#support",
            "engine:help": HOMEPAGE + "/blob/master/ENGINE.md",
        }
        if site_key in websites:
            webbrowser.open(websites[site_key])

    def on_start(self) -> None:
        self.language = self.gui.config("general/lang")
        self.gui.start()

    def on_request_close(self, *_args: Any, source: str | None = None) -> bool | None:
        if source == "keyboard":
            return True  # do not close on esc
        if getattr(self, "gui", None):
            self.gui.play_mode.save_ui_state()
            ui_state = dict(self.gui.config("ui_state") or {})
            ui_state["size"] = list(Window._size)
            ui_state["top"] = Window.top
            ui_state["left"] = Window.left
            self.gui.set_config_section("ui_state", ui_state)
            self.gui.save_config("ui_state")
            if self.gui.engine:
                self.gui.engine.shutdown(finish=None)
            # Shutdown Leela engine (Phase 15)
            self.gui.shutdown_leela_engine()
            # Phase 22: Clockイベントのクリーンアップ
            self.gui.cleanup()
        return None

    def signal_handler(self, _signal: int, _frame: Any) -> None:
        if self.gui.debug_level >= OUTPUT_DEBUG:
            print("TRACEBACKS")
            for threadId, stack in sys._current_frames().items():
                print(f"\n# ThreadID: {threadId}")
                for filename, lineno, name, line in traceback.extract_stack(stack):
                    print(f"\tFile: {filename}, line {lineno}, in {name}")
                    if line:
                        print(f"\t\t{line.strip()}")
        self.stop()


def run_app() -> None:
    class CrashHandler(ExceptionHandler):
        def handle_exception(self, inst: Exception) -> int:
            ex_type, ex, tb = sys.exc_info()
            trace = "".join(traceback.format_tb(tb))
            app = MDApp.get_running_app()

            if app and app.gui:
                app.gui.log(
                    f"Exception {inst.__class__.__name__}: {', '.join(repr(a) for a in inst.args)}\n{trace}",
                    OUTPUT_ERROR,
                )
            else:
                print(f"Exception {inst.__class__}: {inst.args}\n{trace}")
            return ExceptionManager.PASS  # type: ignore[no-any-return]

    ExceptionManager.add_handler(CrashHandler())
    app = KaTrainApp()
    signal.signal(signal.SIGINT, app.signal_handler)
    app.run()


if __name__ == "__main__":
    run_app()
