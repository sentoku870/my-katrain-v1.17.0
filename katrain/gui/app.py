# mypy: ignore-errors
#
# Phase 158+: This module contains Windows-specific code paths
# (ctypes.windll) that mypy cannot resolve on Linux CI but are guarded
# by platform checks. The original ``katrain/__main__.py`` carried the
# same pragma; we preserve it here so the move does not introduce
# regressions.
"""Phase PR3: Top-level GUI classes.

Moved from ``katrain/__main__.py`` to keep the entry point small.
``KaTrainGui`` is the Screen-based facade that ties every manager
and controller together; ``KaTrainApp`` is the MDApp subclass.

Backward compatibility:
    ``katrain/__main__.py`` re-exports these symbols so existing
    ``from katrain.__main__ import KaTrainGui`` references (mostly
    inside ``TYPE_CHECKING`` blocks in error_handler and the
    commands modules) continue to work unchanged.
"""

from __future__ import annotations

# Standard library symbols used by the class definitions below.
import contextlib
import glob
import logging
import os
import random
import sys
import time
import traceback
import webbrowser
from collections.abc import Callable
from queue import Queue
from typing import TYPE_CHECKING, Any

# Kivy / KivyMD symbols used by the class definitions below. These were
# previously imported in ``katrain/__main__.py``; we replicate the
# subset actually referenced in this module so the classes are
# self-contained.
from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.resources import resource_add_path, resource_find
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.utils import platform as kivy_platform
from kivymd.app import MDApp

# Phase PR3: previously imported transitively via __main__ → common.
from katrain.common.resource_utils import find_package_resource, get_package_path

if TYPE_CHECKING:
    from katrain.core.game import Game

# Phase PR3: ICON moved here from __main__.py so both __main__ and
# gui.app.build() can refer to it without a circular import.
ICON = find_package_resource("katrain/img/icon.icns" if kivy_platform == "macosx" else "katrain/img/icon.ico")

from katrain.core.analysis_result import (
    EngineTestResult as TestAnalysisResult,
)
from katrain.core.base_katrain import KaTrainBase
from katrain.core.constants.metadata import DATA_FOLDER, HOMEPAGE, SGF_INTERNAL_COMMENTS_MARKER, VERSION
from katrain.core.constants.modes import MODE_ANALYZE
from katrain.core.constants.output import OUTPUT_DEBUG, OUTPUT_INFO, STATUS_INFO
from katrain.core.engine import KataGoEngine
from katrain.core.lang import DEFAULT_LANGUAGE, i18n
from katrain.gui.badukpan import AnalysisControls, BadukPanControls, BadukPanWidget  # noqa F401
from katrain.gui.controllers.analysis_controller import AnalysisController
from katrain.gui.controllers.batch_analysis_controller import BatchAnalysisController
from katrain.gui.controlspanel import ControlsPanel  # noqa F401
from katrain.gui.error_handler import ErrorHandler

# Batch analysis related imports removed; handled by BatchAnalysisController
from katrain.gui.features.commands import dispatch, game_commands

# used in kv
# used in kv
from katrain.gui.kivyutils import (
    PlayerSetupBlock,
)  # noqa: F401
from katrain.gui.managers.auto_setup_controller import AutoSetupController
from katrain.gui.managers.config_manager import ConfigManager
from katrain.gui.managers.dialog_factory import DialogFactory
from katrain.gui.managers.engine_bootstrap import EngineBootstrap
from katrain.gui.managers.game_state_manager import GameStateManager
from katrain.gui.managers.game_state_update_manager import GameStateUpdateManager
from katrain.gui.managers.gui_refresh_manager import GUIRefreshManager
from katrain.gui.managers.keyboard_manager import KeyboardManager
from katrain.gui.managers.kifunarabe_controller import KifunarabeController
from katrain.gui.managers.message_loop_manager import MessageLoopManager
from katrain.gui.managers.popup_manager import PopupManager
from katrain.gui.managers.scroll_handler import ScrollHandler
from katrain.gui.managers.summary_manager import SummaryManager
from katrain.gui.managers.ui_update_manager import UIUpdateManager

# deleted imports
from katrain.gui.sgf_manager import SGFManager
from katrain.gui.sound import play_sound
from katrain.gui.theme import Theme
from katrain.gui.widgets import I18NFileBrowser, MoveTree, ScoreGraph, SelectionSlider  # noqa F401

# Phase 287-H (revert): NavIconButtonWithCaption was abandoned in favour
# of bare NavIconButton (icon + tooltip only). The Python class is gone.


class KaTrainGui(Screen, KaTrainBase):
    """Top level class responsible for tying everything together"""

    zen = NumericProperty(0)
    controls = ObjectProperty(None)
    #: Kifunarabe (棋譜並べ) mode flag. Toggled by the menu / abort button.
    kifunarabe_mode = BooleanProperty(False)

    def on_kifunarabe_mode(self, _instance: Any, value: bool) -> None:
        """Bridge Kivy property changes to KifunarabeController.

        Previously this happened implicitly through the lambda injected as
        ``set_mode`` on the controller, but several KV bindings
        (``opacity: 1 if (app.gui and app.gui.kifunarabe_mode) else 0``) re-
        evaluate here, and we want a single, debuggable notification path
        so any failure is visible.
        """
        controller = getattr(self, "_kifunarabe_controller", None)
        if controller is not None:
            try:
                controller.on_mode_change(value)
            except Exception as e:  # noqa: BLE001
                self.log(f"kifunarabe: on_mode_change({value}) raised: {e}", 0)

    def _init_simple_state(self) -> None:
        """Initialize simple instance attributes with no manager dependencies.

        These attributes can be set before any managers are constructed.
        """
        self.pondering = False
        self.show_move_num = False
        self.message_queue: Queue[Any] = Queue()
        # Phase 22: Clock.schedule_interval イベントを追跡（cleanup用）
        self._clock_events: list[Any] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.error_handler = ErrorHandler(self)
        self.engine: Any = None
        # Phase 270: ``curator_profile`` was removed.  The Curator
        # weak-axis hint has been deprecated; ``get_beginner_hint_cached``
        # no longer consults a profile loader.

        # Phase 272-C: split the once-228-line __init__ into 3 manager
        # groups + a small AppContext aggregator. The ``self.ctx``
        # assignment stays in this method body (Phase 249-hotfix regression
        # test in test_config_imports.py requires it).
        self._init_managers_core()
        self._init_managers_state()
        self._init_managers_loops()

        # Phase 198: aggregate every manager into a single AppContext so that
        # downstream code can reach them through ``self.ctx.<name>`` without
        # walking the GUI. The legacy ``self._<name>`` accessors remain for
        # backwards compatibility — see gui/app_context.py.
        #
        # Phase 249-hotfix: this block was previously left as dead code inside
        # ``_build_kifunarabe_weakness_exporter`` (after a ``return``), which
        # made ``self.ctx`` undefined on the instance and caused the startup
        # ``AttributeError: 'KaTrainGui' object has no attribute 'ctx'`` when
        # ``on_language`` → ``set_config_section`` fired.
        try:
            from katrain.gui.app_context import AppContext
        except ImportError:
            AppContext = None  # type: ignore[assignment,misc]
        if AppContext is not None:
            self.ctx: Any = AppContext(
                error_handler=self.error_handler,
                sgf_manager=self._sgf_manager,
                config_manager=self._config_manager,
                summary_manager=self._summary_manager,
                keyboard_manager=self._keyboard_manager,
                dialog_factory=self.dialog_factory,
                popup_manager=self._popup_manager,
                game_state_manager=self._game_state_manager,
                ui_update_manager=self._ui_update_manager,
                auto_setup_controller=self._auto_setup_controller,
                analysis_controller=self._analysis_controller,
                batch_analysis_controller=self._batch_analysis_controller,
                gui_refresh_manager=self._gui_refresh_manager,
                game_state_update_manager=self._game_state_update_manager,
                message_loop_manager=self._message_loop_manager,
                scroll_handler=self._scroll_handler,
                kifunarabe_controller=self._kifunarabe_controller,
                engine_bootstrap=self._engine_bootstrap,
                engine=self.engine,
                pondering=self.pondering,
                show_move_num=self.show_move_num,
                message_queue=self.message_queue,
                cancel_flag=None,
            )
        else:
            self.ctx = None

        if self.ctx is not None:
            self.ctx.ui_update_manager.setup_state_subscriptions()

    def _init_managers_core(self) -> None:
        """Phase 272-C: core managers (SGF, Config, Summary, Keyboard, Dialog, Popup, GameState).

        Lines 170-258 of the original monolithic ``__init__``. All other
        manager groups and the AppContext aggregator call into these via
        ``self`` (the GUI), so this must run first.
        """
        # SGF file management (refactored in PR #122)
        self._sgf_manager = SGFManager(
            config_getter=self.config,
            config_setter=lambda section, values: self.set_config_section(section, values),
            save_config=self.save_config,
            logger=self.log,
            status_setter=lambda msg, level: (
                self.controls.set_status(msg, level, check_level=False) if self.controls else None
            ),
            new_game_callback=lambda tree, fast, filename: game_commands.do_new_game(
                self, move_tree=tree, analyze_fast=fast, sgf_filename=filename
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
            toggle_continuous_analysis=lambda *a, **kw: self.ctx.analysis_controller.toggle_continuous_analysis(
                *a, clock=Clock, **kw
            ),
            toggle_move_num=lambda: self.ctx.analysis_controller.toggle_move_num(),
            load_from_clipboard=lambda: self.ctx.sgf_manager.load_sgf_from_clipboard(),
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
            pause_timer=lambda: (
                setattr(timer, "paused", True)
                if (timer := getattr(getattr(self, "controls", None), "timer", None))
                else None
            ),
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

    def _init_managers_state(self) -> None:
        """Phase 272-C: state managers and controllers (UIUpdate, AutoSetup, Analysis, Batch, GUIRefresh, GameStateUpdate).

        Lines 260-309 of the original monolithic ``__init__``. Depends on
        ``_init_managers_core`` (uses ``self._ui_update_manager``) and on
        ``_init_simple_state`` (for ``self.pondering`` / ``self.message_queue``).
        """
        self._init_simple_state()

        # New Managers & Controllers (Phase 133)
        # Phase 173: UI update coalescing lives in UIUpdateManager; the
        # legacy static-method helpers on this class (and the related
        # __init__ flags) have been removed.
        self._ui_update_manager = UIUpdateManager(self, clock=Clock)
        self._auto_setup_controller = AutoSetupController(self)
        self._analysis_controller = AnalysisController(self)
        self._batch_analysis_controller = BatchAnalysisController(self)

        # Phase 158+: New managers for the remaining inline logic
        self._gui_refresh_manager = GUIRefreshManager(
            get_game=lambda: self.game,
            get_board_gui=lambda: getattr(self, "board_gui", None),
            get_board_controls=lambda: getattr(self, "board_controls", None),
            get_controls=lambda: getattr(self, "controls", None),
            get_gui=lambda: self,
            set_status=lambda msg, level: (
                self.controls.set_status(msg, level) if getattr(self, "controls", None) else None
            ),
        )
        self._game_state_update_manager = GameStateUpdateManager(
            get_game=lambda: self.game,
            get_engine=lambda: self.engine,
            get_play_analyze_mode=lambda: self.play_analyze_mode,
            get_pondering=lambda: self.pondering,
            set_pondering=lambda v: setattr(self, "pondering", v),
            get_last_player_info=lambda: self.last_player_info,
            get_next_player_info=lambda: self.next_player_info,
            get_popups_open=lambda: self.popup_open,
            get_nav_drawer_open=lambda: bool(self.nav_drawer.state == "open"),
            get_eval_thresholds=lambda: self.config("trainer/eval_thresholds"),
            # Phase 171 で削除: get_leela_manager, get_config (leela/enabled 用),
            # get_analysis_controls (Leela hint 起動用)
            play_sound=self.play_mistake_sound,
            ai_move=lambda cn: game_commands.do_ai_move(self, cn),
            stone_sound=self._play_stone_sound,
            schedule_gui_update=lambda cn, rb: Clock.schedule_once(
                lambda _dt: self.ctx.gui_refresh_manager.update_gui(cn, redraw_board=rb), -1
            ),
            clock=Clock,
        )

    def _init_managers_loops(self) -> None:
        """Phase 272-C: loop, scroll, and Kifunarabe managers (MessageLoop, Scroll, Kifunarabe, EngineBootstrap).

        Lines 310-347 of the original monolithic ``__init__``. The
        ``_engine_bootstrap`` attribute is created as ``None`` here and
        populated later by ``start()``.
        """
        self._message_loop_manager = MessageLoopManager(
            get_message_queue=lambda: self.message_queue,
            get_game_id=lambda: self.game.game_id if self.game else None,
            get_gui=lambda: self,
            log=self.log,
            error_handler_handle=lambda exc, notify, msg: self.error_handler.handle(
                exc, notify_user=notify, fallback_message=msg
            ),
        )
        self._scroll_handler = ScrollHandler(
            get_board_gui=lambda: getattr(self, "board_gui", None),
            get_board_controls=lambda: getattr(self, "board_controls", None),
            get_controls=lambda: getattr(self, "controls", None),
            action_dispatcher=self.__call__,
        )

        self._kifunarabe_controller = KifunarabeController(
            get_ctx=lambda: self,
            get_config=self.config,
            get_game=lambda: self.game,
            get_controls=lambda: getattr(self, "controls", None),
            get_mode=lambda: self.kifunarabe_mode,
            set_mode=lambda v: setattr(self, "kifunarabe_mode", v),
            logger=self.log,
            # Phase 249-β: persistent history store. The directory is
            # configurable via ``kifunarabe/history_dir``; falling back
            # to ``~/.katrain/kifunarabe_history``.
            history_store=self._build_kifunarabe_history_store(),
            # Phase 249-γ: opt-in WRONG_GUESS exporter. The directory
            # is configurable via ``kifunarabe/auto_export_dir``.
            weakness_exporter=self._build_kifunarabe_weakness_exporter(),
        )

        self._engine_bootstrap: EngineBootstrap | None = None  # populated in start()

    def _build_kifunarabe_history_store(self) -> Any:
        """Phase 249-β: build the persistent kifunarabe history store.

        Resolution order for the directory:
        1. ``kifunarabe/history_dir`` config (if set and not empty)
        2. ``~/.katrain/kifunarabe_history`` (default)

        Failures to import the store (e.g. on a stripped-down
        install) are swallowed and return ``None`` so the rest of the
        app still works.
        """
        try:
            from katrain.core.study.kifunarabe_history import KifunarabeHistoryStore
        except ImportError:
            return None
        configured = self.config("kifunarabe/history_dir", None)
        directory: str | None = configured if configured else None
        return KifunarabeHistoryStore(directory=directory)

    def _build_kifunarabe_weakness_exporter(self) -> Any:
        """Phase 249-γ: build the opt-in weakness exporter.

        Resolution order for the directory:
        1. ``kifunarabe/auto_export_dir`` config (if set and not empty)
        2. ``~/.katrain/kifunarabe_weaknesses`` (default)

        The exporter is always constructed (so a user can flip
        ``kifunarabe/auto_export_weaknesses`` on mid-session); the
        export only fires when the session's config flag is True.
        """
        try:
            from katrain.core.study.kifunarabe_weakness_export import (
                KifunarabeWeaknessExporter,
            )
        except ImportError:
            return None
        configured = self.config("kifunarabe/auto_export_dir", None)
        directory: str | None = configured if configured else None
        return KifunarabeWeaknessExporter(directory=directory)

    # ========== Phase 173 P0-①-A: Remove dead UIUpdate duplicate ==========
    # Six static-method helpers (_setup_state_subscriptions, _schedule_ui_update,
    # _do_ui_update, _on_game_changed, _on_analysis_complete, _on_config_updated)
    # and a thin instance delegate were duplicates of UIUpdateManager. The
    # actual implementation moved to UIUpdateManager in Phase 133 (which only
    # _schedule_ui_update above was referring to) — the static stubs were kept
    # around for tests. Both layers are unused now that UIUpdateManager.setup_
    # state_subscriptions() is the single source of truth.

    def get_game(self) -> Game:
        """現在のゲームオブジェクトを返す（Phase 133: UIUpdateManager用）。"""
        return self.game

    # ========== PopupManager support methods (Phase 75) ==========
    # ========== PopupManager support methods (Factories moved to DialogFactory) ==========

    def set_config_section(self, section: str, value: dict[str, Any]) -> None:
        """設定セクションを書き込む（Phase 74: ConfigManagerに委譲）。

        Args:
            section: セクション名（例: "export_settings", "mykatrain_settings", "general"）
            value: セクション全体の値（辞書）

        Note:
            保存は別途 save_config(section) を呼ぶ必要がある。

        Defensive: ``self.ctx`` is normally set at the end of ``__init__``,
        but early ``on_start`` paths (e.g. ``on_language``) can fire before
        configuration is fully wired on a malformed install.  In that
        extreme edge case we no-op silently — the user will hit a clear
        error on the first real GUI action rather than an opaque
        ``AttributeError`` from the language switcher.
        """
        ctx = getattr(self, "ctx", None)
        if ctx is None:  # defensive: see docstring
            return
        ctx.config_manager.set_section(section, value)

    def log(self, message: str, level: int = OUTPUT_INFO) -> None:
        """Log via base class, then surface errors to status bar via GUIRefreshManager (Phase 158+).

        Note:
            ``super().__init__()`` invokes ``_load_config`` which calls ``self.log()`` before
            ``_gui_refresh_manager`` is initialized. Guard with ``getattr`` to keep early logs alive.
        """
        super().log(message, level)
        gui_refresh_manager = getattr(self, "_gui_refresh_manager", None)
        if gui_refresh_manager is not None:
            gui_refresh_manager.update_status_for_error(message, level)

    @property
    def play_analyze_mode(self) -> str:
        return self.play_mode.mode  # type: ignore[no-any-return]

    def start(self) -> None:
        if self.engine:
            return
        self.board_gui.trainer_config = self.config("trainer")
        # Phase 173 P0-①-D: engine construction moved to EngineBootstrap so
        # this method stays a thin orchestrator.

        def _schedule_on_main_thread(fn: Callable[[], None]) -> None:
            from kivy.clock import Clock

            Clock.schedule_once(lambda _dt: fn(), 0)

        self._engine_bootstrap = EngineBootstrap(
            ctx=self,
            config_getter=self.config,
            status_callback=self._gui_refresh_manager.on_engine_status,
            error_handler=self.error_handler,
            main_thread_scheduler=_schedule_on_main_thread,
        )
        self.engine = self._engine_bootstrap.create()
        EngineBootstrap.reset_initial_focus(self.engine)

        self.ctx.message_loop_manager.start()
        sgf_args = [
            f
            for f in sys.argv[1:]
            if os.path.isfile(f) and any(f.lower().endswith(ext) for ext in ["sgf", "ngf", "gib"])
        ]
        if sgf_args:
            self.ctx.sgf_manager.load_sgf_file(sgf_args[0], fast=True, rewind=True)
        else:
            # game_commands.do_new_game 内の自動 Play/Analyze 切り替えを一時的に無効化
            self._suppress_play_mode_switch = True
            try:
                game_commands.do_new_game(self)
            finally:
                self._suppress_play_mode_switch = False

        # Phase 22: Clockイベントを追跡（cleanup用）
        animation_event = Clock.schedule_interval(lambda dt: self.ctx.analysis_controller.handle_animations(), 0.2)
        self._clock_events.append(animation_event)

        Window.request_keyboard(None, self, "").bind(
            on_key_down=self.ctx.keyboard_manager.on_keyboard_down,
            on_key_up=self.ctx.keyboard_manager.on_keyboard_up,
        )

        def set_focus_event(*args: Any) -> None:
            self.ctx.keyboard_manager.last_focus_event = time.time()

        MDApp.get_running_app().root_window.bind(focus=set_focus_event)

        # 前回終了時のモードを復元
        Clock.schedule_once(lambda dt: self.ctx.analysis_controller.restore_last_mode(), 0.3)

        # Initialize focus button states on startup
        Clock.schedule_once(lambda dt: self.ctx.analysis_controller.update_focus_button_states(), 0.5)

        # Phase 270: the curator_profile loader was removed.  The
        # Curator weak-axis hint is deprecated.

    # =========================================================================
    # Phase 89: Auto Setup Mode Methods
    # =========================================================================

    def restart_engine_with_fallback(self, fallback_type: str) -> tuple[bool, TestAnalysisResult]:
        """Delegates to AutoSetupController (Phase 133)."""
        return self.ctx.auto_setup_controller.restart_engine_with_fallback(
            fallback_type,
            lambda cfg: KataGoEngine(self, cfg, status_callback=self._gui_refresh_manager.on_engine_status),
        )

    def restart_engine(self) -> bool:
        """Delegates to AutoSetupController (Phase 133)."""
        return self.ctx.auto_setup_controller.restart_engine(
            lambda cfg: KataGoEngine(self, cfg, status_callback=self._gui_refresh_manager.on_engine_status)
        )

    def save_auto_setup_result(self, success: bool) -> None:
        """Delegates to AutoSetupController (Phase 133)."""
        self.ctx.auto_setup_controller.save_auto_setup_result(success)

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

        # BadukPanWidget の Window.bind / ClockEvent / Texture cache を解放
        # (P2-A: H1+H2+H4)
        board_gui = getattr(self, "board_gui", None)
        if board_gui is not None and hasattr(board_gui, "cleanup"):
            with contextlib.suppress(Exception):
                board_gui.cleanup()

        self.log("KaTrainGui cleanup completed", OUTPUT_DEBUG)

    def update_state(self, redraw_board: bool = False) -> None:  # redirect to message queue thread
        self("update_state", redraw_board=redraw_board)

    def _do_update_state(
        self, redraw_board: bool = False
    ) -> None:  # is called after every message and on receiving analyses and config changes
        """Delegates to GameStateUpdateManager (Phase 158+)."""
        self.ctx.game_state_update_manager.do_update_state(redraw_board=redraw_board)

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

    def __call__(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Central dispatcher for menu actions triggered from .kv or shortcuts.

        Phase 172: Routes messages via ``commands.dispatch`` (the explicit
        ``DISPATCH_TABLE`` lookup). Popup actions are scheduled on the main
        Kivy thread; other actions are forwarded to the message-queue
        consumer which also looks up the same table.
        """
        if self.game:
            if message.endswith("popup"):  # gui code needs to run in main kivy thread.
                Clock.schedule_once(lambda _dt: dispatch(self, message, *args, **kwargs), -1)
            else:  # game related actions
                self.message_queue.put([self.game.game_id, message, args, kwargs])

    # ------------------------------------------------------------------
    # Phase 172: Removed all 34 ``_do_*`` wrapper methods. The action
    # dispatcher (``__call__``) and the message-loop consumer now route
    # directly through ``commands.dispatch`` (DISPATCH_TABLE).
    #
    # Internal callers (`start()`, ``SGFManager.new_game_callback``,
    # ``GameStateUpdateManager.ai_move``) now call ``game_commands.do_*``
    # directly. KV bindings that used to invoke ``_do_*`` have been
    # rewritten to use the ``katrain(...)`` message form so the same
    # dispatch path is used uniformly.
    # ------------------------------------------------------------------

    def _play_stone_sound(self, _dt: Any = None) -> None:
        play_sound(random.choice(Theme.STONE_SOUNDS))

    # =========================================================================
    # Phase 130: Active Review Mode removed (stub is_fog_active kept for KV)
    # =========================================================================

    def is_fog_active(self) -> bool:
        """Active Review removed (Phase 130). Always returns False.

        This stub is retained because KV / drawing code references it from
        multiple sites. Production callers should treat the return value as
        a constant False.
        """
        return False

    def play_mistake_sound(self, node: Any) -> None:
        if self.config("timer/sound") and node.played_mistake_sound is None:
            node.played_mistake_sound = True
            if Theme.MISTAKE_SOUNDS:
                play_sound(random.choice(Theme.MISTAKE_SOUNDS))
            else:
                # P3 (M16): Theme ships with an empty MISTAKE_SOUNDS list, so
                # the previous guard short-circuited silently. Now we still
                # mark the node as played but flash a one-line status so the
                # user knows the mistake chime is intentionally muted.
                self.controls.set_status(i18n._("Mistake played (sound disabled)"), STATUS_INFO)

    # === SGF File Management (refactored in PR #122) ===
    def load_sgf_from_clipboard(self) -> None:
        """Load SGF from clipboard. Delegates to SGFManager."""
        self.ctx.sgf_manager.load_sgf_from_clipboard()

    def on_touch_up(self, touch: Any) -> bool:
        """Delegates scroll handling to ScrollHandler, defers to Kivy otherwise (Phase 158+)."""
        handled = self.ctx.scroll_handler.handle_touch_up(touch)
        if handled:
            return True
        return super().on_touch_up(touch)  # type: ignore[no-any-return]

    @property
    def shortcuts(self) -> dict[str, Any]:
        """Delegate to KeyboardManager for backward compatibility."""
        return self.ctx.keyboard_manager.shortcuts

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

        # Phase 277.1: KivyMD 1.2.0 defaults ``theme_style`` to "Light",
        # which makes ``theme_cls.text_color`` resolve to 87% black and
        # ``on_primary_container_color`` resolve to a dark blue. On
        # myKatrain's dark navy background that renders every KivyMD
        # widget's text (tab labels, MDTextField path inputs, MDLabel
        # hints, MDCheckbox captions, ...) as barely-visible dark
        # text. The upstream fork used a Dark theme; replicate it.
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"

        # Phase 287-G: register the MDI ("Icons") font with Kivy's
        # LabelBase. kivymd.font_definitions performs the registration as
        # an import side-effect, so any MDI Label built before this
        # import would fail with ``OSError: Label: File
        # 'materialdesignicons-webfont.ttf' not found``. Import early,
        # before KV load and before any ``MdiIconOrImage`` construction.
        import kivymd.font_definitions  # noqa: F401, WPS433

        # Phase 133: KV files are now loaded from katrain/gui/kv/ directory

        package_path = get_package_path()
        resource_add_path(package_path + "/fonts")
        resource_add_path(package_path + "/sounds")
        resource_add_path(package_path + "/img")
        resource_add_path(os.path.abspath(os.path.expanduser(DATA_FOLDER)))  # prefer resources in .katrain

        from katrain.gui.theme_loader import load_theme_overrides

        theme_files = glob.glob(os.path.join(os.path.expanduser(DATA_FOLDER), "theme*.json"))
        for theme_file in sorted(theme_files):
            load_theme_overrides(theme_file, Theme)

        # Phase 281 (tofu-fix): if ``resource_find`` returns None the
        # bundled ``NotoSansJP-Regular.otf`` was not located in any of
        # the registered resource paths. Without this guard the theme
        # would silently fall back to Kivy's built-in Roboto font, which
        # has no Japanese glyphs and renders every Japanese string as
        # tofu boxes (the bug that prompted this Phase). Surface the
        # missing resource loudly so PyInstaller / development-environment
        # misconfigurations become obvious instead of producing silent
        # UI degradation.
        resolved_font = resource_find(Theme.DEFAULT_FONT)
        if resolved_font is None:
            logging.getLogger(__name__).warning(
                "Font resource %r not found; Japanese text may render as tofu boxes. "
                "Check that katrain/fonts/ is reachable (PyInstaller datas, "
                "editable install layout, etc.).",
                Theme.DEFAULT_FONT,
            )
        else:
            Theme.DEFAULT_FONT = resolved_font
        # Phase 287-G: resolve the bold-face font (falls back to the regular
        # font via the canonical name in katrain.common.theme_constants when
        # no dedicated bold OTF is bundled).
        resolved_bold = resource_find(Theme.DEFAULT_FONT_BOLD)
        if resolved_bold is not None:
            Theme.DEFAULT_FONT_BOLD = resolved_bold
        else:
            logging.getLogger(__name__).info(
                "Bold font %r not found; falling back to regular %r.",
                Theme.DEFAULT_FONT_BOLD,
                Theme.DEFAULT_FONT,
            )
        # Load Split KV files (Phase 133)
        kv_dir = find_package_resource("katrain/gui/kv")
        kv_files = glob.glob(os.path.join(kv_dir, "*.kv"))
        # Load widget definitions first to ensure base classes are available
        for file in sorted(kv_files, key=lambda x: ("widget" not in x.lower(), x)):
            Builder.load_file(file)

        Window.bind(on_request_close=self.on_request_close)
        Window.bind(on_dropfile=lambda win, file: self.gui.ctx.sgf_manager.load_sgf_file(file.decode("utf8")))
        self.gui = KaTrainGui()

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
            # Some window providers (e.g. pygame) don't implement
            # `_get_window_pos`/`_set_window_pos`, so setting Window.left/top
            # raises TypeError. Guard with try/except to stay portable.
            try:
                Window.left = int(win_left)
                Window.top = int(win_top)
            except TypeError:
                self.gui.log(
                    "Window provider does not support setting position; skipping left/top assignment",
                    OUTPUT_DEBUG,
                )

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
            window_top = Window.top
            window_left = Window.left
            if window_top is not None:
                ui_state["top"] = window_top
            if window_left is not None:
                ui_state["left"] = window_left
            self.gui.set_config_section("ui_state", ui_state)
            self.gui.save_config("ui_state")
            # P3 (M8): engine.shutdown() and config persistence can raise.
            # Wrap them in try/finally so cleanup() still runs and releases
            # the Window/ClockEvent bindings accumulated during the session.
            try:
                if self.gui.engine:
                    self.gui.engine.shutdown(finish=None)
            except Exception:
                pass
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
