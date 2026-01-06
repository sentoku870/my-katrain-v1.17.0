"""isort:skip_file"""

# first, logging level lower
import os
import sys

os.environ["KCFG_KIVY_LOG_LEVEL"] = os.environ.get("KCFG_KIVY_LOG_LEVEL", "warning")

from kivy.utils import platform as kivy_platform

if kivy_platform == "win":
    from ctypes import windll, c_int64

    if hasattr(windll.user32, "SetProcessDpiAwarenessContext"):
        windll.user32.SetProcessDpiAwarenessContext(c_int64(-4))

import kivy

kivy.require("2.0.0")

# next, icon
from katrain.core.utils import find_package_resource, PATHS
from kivy.config import Config

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


import re
import signal
import json
import threading
import traceback
from queue import Queue
import urllib3
import webbrowser
import time
import random
import glob
from datetime import datetime
from typing import List, Optional
from kivy.clock import Clock


from kivy.base import ExceptionHandler, ExceptionManager
from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.lang import Builder
from kivy.resources import resource_add_path
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.uix.togglebutton import ToggleButton
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.resources import resource_find
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivy.clock import Clock
from kivy.metrics import dp, sp
from katrain.core.ai import generate_ai_move

from katrain.core.lang import DEFAULT_LANGUAGE, i18n
from katrain.core.constants import (
    OUTPUT_ERROR,
    OUTPUT_KATAGO_STDERR,
    OUTPUT_INFO,
    OUTPUT_DEBUG,
    OUTPUT_EXTRA_DEBUG,
    MODE_ANALYZE,
    HOMEPAGE,
    VERSION,
    STATUS_ERROR,
    STATUS_INFO,
    PLAYING_NORMAL,
    PLAYER_HUMAN,
    SGF_INTERNAL_COMMENTS_MARKER,
    MODE_PLAY,
    DATA_FOLDER,
    AI_DEFAULT,
)
from katrain.core import eval_metrics
from katrain.gui.popups import (
    ConfigTeacherPopup,
    ConfigTimerPopup,
    I18NPopup,
    SaveSGFPopup,
    ContributePopup,
    EngineRecoveryPopup,
)
from katrain.gui.sound import play_sound
from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import KataGoEngine
from katrain.core.contribute_engine import KataGoContributeEngine
from katrain.core.game import Game, IllegalMoveException, KaTrainSGF, BaseGame
from katrain.core.sgf_parser import Move, ParseError
from katrain.gui.features.karte_export import determine_user_color, do_export_karte
from katrain.gui.features.summary_stats import extract_analysis_from_sgf_node, extract_sgf_statistics
from katrain.gui.features.summary_aggregator import (
    scan_player_names,
    categorize_games_by_stats,
    collect_rank_info,
)
from katrain.gui.features.summary_formatter import build_summary_from_stats
from katrain.gui.features.summary_ui import (
    do_export_summary,
    do_export_summary_ui,
    process_summary_with_selected_players,
    scan_and_show_player_selection,
    show_player_selection_dialog,
    process_and_export_summary,
)
from katrain.gui.features.summary_io import (
    save_summaries_per_player,
    save_categorized_summaries_from_stats,
    save_summary_file,
)
from katrain.gui.features.quiz_popup import (
    do_quiz_popup,
    format_points_loss,
)
from katrain.gui.features.quiz_session import start_quiz_session
from katrain.gui.features.batch_core import (
    collect_batch_options,
    create_log_callback,
    create_progress_callback,
    create_summary_callback,
    run_batch_in_thread,
)
from katrain.gui.features.batch_ui import (
    create_browse_callback,
    create_on_start_callback,
    create_on_close_callback,
    create_get_player_filter_fn,
    build_batch_popup_widgets,
    create_batch_popup,
)
from katrain.gui.features.settings_popup import (
    load_export_settings,
    save_export_settings,
    save_batch_options,
    do_mykatrain_settings_popup,
)
from katrain.gui.popups import ConfigPopup, LoadSGFPopup, NewGamePopup, ConfigAIPopup
from katrain.gui.theme import Theme
from kivymd.app import MDApp

# used in kv
from katrain.gui.kivyutils import *
from katrain.gui.widgets import MoveTree, I18NFileBrowser, SelectionSlider, ScoreGraph  # noqa F401
from katrain.gui.badukpan import AnalysisControls, BadukPanControls, BadukPanWidget  # noqa F401
from katrain.gui.controlspanel import ControlsPanel  # noqa F401


class KaTrainGui(Screen, KaTrainBase):
    """Top level class responsible for tying everything together"""

    zen = NumericProperty(0)
    controls = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engine = None
        self.contributing = False

        self.new_game_popup = None
        self.fileselect_popup = None
        self.config_popup = None
        self.ai_settings_popup = None
        self.teacher_settings_popup = None
        self.timer_settings_popup = None
        self.contribute_popup = None

        self.pondering = False
        self.show_move_num = False

        self.animate_contributing = False
        self.message_queue = Queue()

        self.last_key_down = None
        self.last_focus_event = 0

    def _load_export_settings(self) -> dict:
        """Delegates to settings_popup.load_export_settings()."""
        return load_export_settings(self)

    def _save_export_settings(self, sgf_directory: str = None, selected_players: list = None):
        """Delegates to settings_popup.save_export_settings()."""
        save_export_settings(self, sgf_directory, selected_players)

    def _save_batch_options(self, options: dict):
        """Delegates to settings_popup.save_batch_options()."""
        save_batch_options(self, options)

    def set_config_section(self, section: str, value: dict) -> None:
        """設定セクションを書き込む。

        Args:
            section: セクション名（例: "export_settings", "mykatrain_settings", "general"）
            value: セクション全体の値（辞書）

        Note:
            保存は別途 save_config(section) を呼ぶ必要がある。
        """
        self._config[section] = value

    def log(self, message, level=OUTPUT_INFO):
        super().log(message, level)
        if level == OUTPUT_KATAGO_STDERR and "ERROR" not in self.controls.status.text:
            if self.contributing:
                self.controls.set_status(message, STATUS_INFO)
            elif "starting" in message.lower():
                self.controls.set_status("KataGo engine starting...", STATUS_INFO)
            elif message.startswith("Tuning"):
                self.controls.set_status(
                    "KataGo is tuning settings for first startup, please wait." + message, STATUS_INFO
                )
                return
            elif "ready" in message.lower():
                self.controls.set_status("KataGo engine ready.", STATUS_INFO)
        if (
            level == OUTPUT_ERROR
            or (level == OUTPUT_KATAGO_STDERR and "error" in message.lower() and "tuning" not in message.lower())
        ) and getattr(self, "controls", None):
            self.controls.set_status(f"ERROR: {message}", STATUS_ERROR)

    def handle_animations(self, *_args):
        if self.contributing and self.animate_contributing:
            self.engine.advance_showing_game()
        if (self.contributing and self.animate_contributing) or self.pondering:
            self.board_controls.engine_status_pondering += 5
        else:
            self.board_controls.engine_status_pondering = -1

    @property
    def play_analyze_mode(self):
        return self.play_mode.mode

    def toggle_continuous_analysis(self, quiet=False):
        if self.contributing:
            self.animate_contributing = not self.animate_contributing
        else:
            if self.pondering:
                self.controls.set_status("", STATUS_INFO)
            elif not quiet:  # See #549
                Clock.schedule_once(self.analysis_controls.hints.activate, 0)
            self.pondering = not self.pondering
            self.update_state()

    def toggle_move_num(self):
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
            node.clear_analysis()
        
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

    def start(self):
        if self.engine:
            return
        self.board_gui.trainer_config = self.config("trainer")
        self.engine = KataGoEngine(self, self.config("engine"))
        
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

        Clock.schedule_interval(self.handle_animations, 0.1)
        Window.request_keyboard(None, self, "").bind(on_key_down=self._on_keyboard_down, on_key_up=self._on_keyboard_up)

        def set_focus_event(*args):
            self.last_focus_event = time.time()

        MDApp.get_running_app().root_window.bind(focus=set_focus_event)

        # 前回終了時のモードを復元
        Clock.schedule_once(lambda dt: self.restore_last_mode(), 0.3)
        
        # Initialize focus button states on startup
        Clock.schedule_once(lambda dt: self.update_focus_button_states(), 0.5)

    def update_gui(self, cn, redraw_board=False):
        # Handle prisoners and next player display
        prisoners = self.game.prisoner_count
        top, bot = [w.__self__ for w in self.board_controls.circles]  # no weakref
        if self.next_player_info.player == "W":
            top, bot = bot, top
            self.controls.players["W"].active = True
            self.controls.players["B"].active = False
        else:
            self.controls.players["W"].active = False
            self.controls.players["B"].active = True
        self.board_controls.mid_circles_container.clear_widgets()
        self.board_controls.mid_circles_container.add_widget(bot)
        self.board_controls.mid_circles_container.add_widget(top)

        self.controls.players["W"].captures = prisoners["W"]
        self.controls.players["B"].captures = prisoners["B"]

        # update engine status dot
        if not self.engine or not self.engine.katago_process or self.engine.katago_process.poll() is not None:
            self.board_controls.engine_status_col = Theme.ENGINE_DOWN_COLOR
        elif self.engine.is_idle():
            self.board_controls.engine_status_col = Theme.ENGINE_READY_COLOR
        else:
            self.board_controls.engine_status_col = Theme.ENGINE_BUSY_COLOR
        self.board_controls.queries_remaining = self.engine.queries_remaining()

        # redraw board/stones
        if redraw_board:
            self.board_gui.draw_board()
        self.board_gui.redraw_board_contents_trigger()
        self.controls.update_evaluation()
        self.controls.update_timer(1)
        # update move tree
        self.controls.move_tree.current_node = self.game.current_node

    def update_state(self, redraw_board=False):  # redirect to message queue thread
        self("update_state", redraw_board=redraw_board)

    def _do_update_state(
        self, redraw_board=False
    ):  # is called after every message and on receiving analyses and config changes
        # AI and Trainer/auto-undo handlers
        if not self.game or not self.game.current_node:
            return
        cn = self.game.current_node
        if not self.contributing:
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
                    and cn.parent.analysis_complete
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
        Clock.schedule_once(lambda _dt: self.update_gui(cn, redraw_board=redraw_board), -1)  # trigger?

    def update_player(self, bw, **kwargs):
        super().update_player(bw, **kwargs)
        if self.game:
            sgf_name = self.game.root.get_property("P" + bw)
            self.players_info[bw].name = None if not sgf_name or SGF_INTERNAL_COMMENTS_MARKER in sgf_name else sgf_name
        if self.controls:
            self.controls.update_players()
            self.update_state()
        for player_setup_block in PlayerSetupBlock.INSTANCES:
            player_setup_block.update_player_info(bw, self.players_info[bw])

    def set_note(self, note):
        self.game.current_node.note = note

    # The message loop is here to make sure moves happen in the right order, and slow operations don't hang the GUI
    def _message_loop_thread(self):
        while True:
            game, msg, args, kwargs = self.message_queue.get()
            try:
                self.log(f"Message Loop Received {msg}: {args} for Game {game}", OUTPUT_EXTRA_DEBUG)
                if game != self.game.game_id:
                    self.log(
                        f"Message skipped as it is outdated (current game is {self.game.game_id}", OUTPUT_EXTRA_DEBUG
                    )
                    continue
                msg = msg.replace("-", "_")
                if self.contributing:
                    if msg not in [
                        "katago_contribute",
                        "redo",
                        "undo",
                        "update_state",
                        "save_game",
                        "find_mistake",
                    ]:
                        self.controls.set_status(
                            i18n._("gui-locked").format(action=msg), STATUS_INFO, check_level=False
                        )
                        continue
                fn = getattr(self, f"_do_{msg}")
                fn(*args, **kwargs)
                if msg != "update_state":
                    self._do_update_state()
            except Exception as exc:
                self.log(f"Exception in processing message {msg} {args}: {exc}", OUTPUT_ERROR)
                traceback.print_exc()

    def __call__(self, message, *args, **kwargs):
        if self.game:
            if message.endswith("popup"):  # gui code needs to run in main kivy thread.
                if self.contributing and "save" not in message and message != "contribute-popup":
                    self.controls.set_status(
                        i18n._("gui-locked").format(action=message), STATUS_INFO, check_level=False
                    )
                    return
                fn = getattr(self, f"_do_{message.replace('-', '_')}")
                Clock.schedule_once(lambda _dt: fn(*args, **kwargs), -1)
            else:  # game related actions
                self.message_queue.put([self.game.game_id, message, args, kwargs])

    def _do_new_game(self, move_tree=None, analyze_fast=False, sgf_filename=None):
        self.pondering = False
        mode = self.play_analyze_mode
        if not getattr(self, "_suppress_play_mode_switch", False) and (
            (move_tree is not None and mode == MODE_PLAY)
            or (move_tree is None and mode == MODE_ANALYZE)
        ):
            self.play_mode.switch_ui_mode()  # for new game, go to play, for loaded, analyze
        self.board_gui.animating_pv = None
        self.board_gui.reset_rotation()
        self.engine.on_new_game()  # clear queries
        self.game = Game(
            self,
            self.engine,
            move_tree=move_tree,
            analyze_fast=analyze_fast or not move_tree,
            sgf_filename=sgf_filename,
        )
        for bw, player_info in self.players_info.items():
            player_info.sgf_rank = self.game.root.get_property(bw + "R")
            player_info.calculated_rank = None
            if sgf_filename is not None:  # load game->no ai player
                player_info.player_type = PLAYER_HUMAN
                player_info.player_subtype = PLAYING_NORMAL
            self.update_player(bw, player_type=player_info.player_type, player_subtype=player_info.player_subtype)
        self.controls.graph.initialize_from_game(self.game.root)
        self.update_state(redraw_board=True)

    def _do_katago_contribute(self):
        if self.contributing and not self.engine.server_error and self.engine.katago_process is not None:
            return
        self.contributing = self.animate_contributing = True  # special mode
        if self.play_analyze_mode == MODE_PLAY:  # switch to analysis view
            self.play_mode.switch_ui_mode()
        self.pondering = False
        self.board_gui.animating_pv = None
        for bw, player_info in self.players_info.items():
            self.update_player(bw, player_type=PLAYER_AI, player_subtype=AI_DEFAULT)
        self.engine.shutdown(finish=False)
        self.engine = KataGoContributeEngine(self)
        self.game = BaseGame(self)

    def _do_insert_mode(self, mode="toggle"):
        self.game.set_insert_mode(mode)
        if self.play_analyze_mode != MODE_ANALYZE:
            self.play_mode.switch_ui_mode()

    def _do_ai_move(self, node=None):
        if node is None or self.game.current_node == node:
            mode = self.next_player_info.strategy
            settings = self.config(f"ai/{mode}")
            if settings is not None:
                generate_ai_move(self.game, mode, settings)
            else:
                self.log(f"AI Mode {mode} not found!", OUTPUT_ERROR)

    def _do_undo(self, n_times=1):
        if n_times == "smart":
            n_times = 1
            if self.play_analyze_mode == MODE_PLAY and self.last_player_info.ai and self.next_player_info.human:
                n_times = 2
        self.board_gui.animating_pv = None
        self.game.undo(n_times)

    def _do_reset_analysis(self):
        self.game.reset_current_analysis()

    def _do_resign(self):
        self.game.current_node.end_state = f"{self.game.current_node.player}+R"

    def _do_redo(self, n_times=1):
        self.board_gui.animating_pv = None
        self.game.redo(n_times)

    def _do_rotate(self):
        self.board_gui.rotate_gridpos()

    def _do_find_mistake(self, fn="redo"):
        self.board_gui.animating_pv = None
        getattr(self.game, fn)(9999, stop_on_mistake=self.config("trainer/eval_thresholds")[-4])

    # ------------------------------------------------------------------
    # 重要局面ナビゲーション
    # ------------------------------------------------------------------
    def _do_prev_important(self):
        if self.game:
            self.game.jump_to_prev_important_move()

    def _do_next_important(self):
        if self.game:
            self.game.jump_to_next_important_move()

    def _do_switch_branch(self, *args):
        self.board_gui.animating_pv = None
        self.controls.move_tree.switch_branch(*args)

    def _play_stone_sound(self, _dt=None):
        play_sound(random.choice(Theme.STONE_SOUNDS))

    def _do_play(self, coords):
        self.board_gui.animating_pv = None
        try:
            old_prisoner_count = self.game.prisoner_count["W"] + self.game.prisoner_count["B"]
            self.game.play(Move(coords, player=self.next_player_info.player))
            if old_prisoner_count < self.game.prisoner_count["W"] + self.game.prisoner_count["B"]:
                play_sound(Theme.CAPTURING_SOUND)
            elif not self.game.current_node.is_pass:
                self._play_stone_sound()

        except IllegalMoveException as e:
            self.controls.set_status(f"Illegal Move: {str(e)}", STATUS_ERROR)

    def _do_analyze_extra(self, mode, **kwargs):
        self.game.analyze_extra(mode, **kwargs)

    def _do_selfplay_setup(self, until_move, target_b_advantage=None):
        self.game.selfplay(int(until_move) if isinstance(until_move, float) else until_move, target_b_advantage)

    def _do_select_box(self):
        self.controls.set_status(i18n._("analysis:region:start"), STATUS_INFO)
        self.board_gui.selecting_region_of_interest = True

    def _do_new_game_popup(self):
        self.controls.timer.paused = True
        if not self.new_game_popup:
            self.new_game_popup = I18NPopup(
                title_key="New Game title", size=[dp(800), dp(900)], content=NewGamePopup(self)
            ).__self__
            self.new_game_popup.content.popup = self.new_game_popup
        self.new_game_popup.open()
        self.new_game_popup.content.update_from_current_game()

    def _do_timer_popup(self):
        self.controls.timer.paused = True
        if not self.timer_settings_popup:
            self.timer_settings_popup = I18NPopup(
                title_key="timer settings", size=[dp(600), dp(500)], content=ConfigTimerPopup(self)
            ).__self__
            self.timer_settings_popup.content.popup = self.timer_settings_popup
        self.timer_settings_popup.open()

    def _do_teacher_popup(self):
        self.controls.timer.paused = True
        if not self.teacher_settings_popup:
            self.teacher_settings_popup = I18NPopup(
                title_key="teacher settings", size=[dp(800), dp(825)], content=ConfigTeacherPopup(self)
            ).__self__
            self.teacher_settings_popup.content.popup = self.teacher_settings_popup
        self.teacher_settings_popup.open()

    def _do_config_popup(self):
        self.controls.timer.paused = True
        if not self.config_popup:
            self.config_popup = I18NPopup(
                title_key="general settings title", size=[dp(1200), dp(950)], content=ConfigPopup(self)
            ).__self__
            self.config_popup.content.popup = self.config_popup
            self.config_popup.title += ": " + self.config_file
        self.config_popup.open()

    def _do_contribute_popup(self):
        if not self.contribute_popup:
            self.contribute_popup = I18NPopup(
                title_key="contribute settings title", size=[dp(1100), dp(800)], content=ContributePopup(self)
            ).__self__
            self.contribute_popup.content.popup = self.contribute_popup
        self.contribute_popup.open()

    def _do_ai_popup(self):
        self.controls.timer.paused = True
        if not self.ai_settings_popup:
            self.ai_settings_popup = I18NPopup(
                title_key="ai settings", size=[dp(750), dp(750)], content=ConfigAIPopup(self)
            ).__self__
            self.ai_settings_popup.content.popup = self.ai_settings_popup
        self.ai_settings_popup.open()

    def _do_engine_recovery_popup(self, error_message, code):
        current_open = self.popup_open
        if current_open and isinstance(current_open.content, EngineRecoveryPopup):
            self.log(f"Not opening engine recovery popup with {error_message} as one is already open", OUTPUT_DEBUG)
            return
        popup = I18NPopup(
            title_key="engine recovery",
            size=[dp(600), dp(700)],
            content=EngineRecoveryPopup(self, error_message=error_message, code=code),
        ).__self__
        popup.content.popup = popup
        popup.open()

    def _do_tsumego_frame(self, ko, margin):
        from katrain.core.tsumego_frame import tsumego_frame_from_katrain_game

        if not self.game.stones:
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
            self.game.set_region_of_interest(flattened_region)
        node.analyze(self.game.engines[node.next_player])
        self.update_state(redraw_board=True)

    def play_mistake_sound(self, node):
        if self.config("timer/sound") and node.played_mistake_sound is None and Theme.MISTAKE_SOUNDS:
            node.played_mistake_sound = True
            play_sound(random.choice(Theme.MISTAKE_SOUNDS))

    def load_sgf_file(self, file, fast=False, rewind=True):
        if self.contributing:
            return
        try:
            file = os.path.abspath(file)
            move_tree = KaTrainSGF.parse_file(file)
        except (ParseError, FileNotFoundError) as e:
            self.log(i18n._("Failed to load SGF").format(error=e), OUTPUT_ERROR)
            return
        self._do_new_game(move_tree=move_tree, analyze_fast=fast, sgf_filename=file)
        if not rewind:
            self.game.redo(999)

    def _do_analyze_sgf_popup(self):
        if not self.fileselect_popup:
            popup_contents = LoadSGFPopup(self)
            # Set initial path with fallback if configured path doesn't exist
            sgf_load_path = os.path.abspath(os.path.expanduser(self.config("general/sgf_load", ".")))
            if os.path.isdir(sgf_load_path):
                popup_contents.filesel.path = sgf_load_path
            # else: leave default path (user home or current dir)
            self.fileselect_popup = I18NPopup(
                title_key="load sgf title", size=[dp(1200), dp(800)], content=popup_contents
            ).__self__

            def readfile(*_args):
                filename = popup_contents.filesel.filename
                self.fileselect_popup.dismiss()
                path, file = os.path.split(filename)
                if path != self.config("general/sgf_load"):
                    self.log(f"Updating sgf load path default to {path}", OUTPUT_DEBUG)
                    self._config["general"]["sgf_load"] = path
                popup_contents.update_config(False)
                self.save_config("general")
                self.load_sgf_file(filename, popup_contents.fast.active, popup_contents.rewind.active)

            popup_contents.filesel.on_success = readfile
            popup_contents.filesel.on_submit = readfile
        self.fileselect_popup.open()
        self.fileselect_popup.content.filesel.ids.list_view._trigger_update()

    def _do_open_recent_sgf(self):
        try:
            sgf_dir = os.path.abspath(os.path.expanduser(self.config("general/sgf_load", ".")))
        except Exception as e:
            self.log(f"Failed to determine sgf load directory: {e}", OUTPUT_DEBUG)
            return self("analyze-sgf-popup")

        if not sgf_dir or not os.path.isdir(sgf_dir):
            return self("analyze-sgf-popup")

        try:
            sgf_files = [
                os.path.join(sgf_dir, f)
                for f in os.listdir(sgf_dir)
                if f.lower().endswith(".sgf") and os.path.isfile(os.path.join(sgf_dir, f))
            ]
            sgf_files.sort(key=os.path.getmtime, reverse=True)
        except Exception as e:
            self.log(f"Failed to list SGF files in {sgf_dir}: {e}", OUTPUT_DEBUG)
            return self("analyze-sgf-popup")

        if not sgf_files:
            return self("analyze-sgf-popup")

        sgf_files = sgf_files[:20]
        fast = bool(self.config("general/load_fast_analysis", False))
        rewind = bool(self.config("general/load_sgf_rewind", True))
        if len(sgf_files) == 1:
            self.load_sgf_file(sgf_files[0], fast=fast, rewind=rewind)
            return

        # Build and open dropdown on the main thread to avoid Kivy thread errors.
        file_entries = [os.path.basename(path) for path in sgf_files]
        Clock.schedule_once(
            lambda *_dt, files=sgf_files, labels=file_entries, fast=fast, rewind=rewind: self._show_recent_sgf_dropdown(
                files, labels, fast, rewind
            )
        )

    def _show_recent_sgf_dropdown(self, sgf_files, labels, fast, rewind, *_args):
        dropdown = DropDown(auto_width=False)
        max_width = 0
        menu_items = []
        base_width = dp(240)
        item_height = dp(34)
        font_size = sp(13)

        def truncate(text, max_len=35):
            return text if len(text) <= max_len else text[: max_len - 3] + "..."

        def load_and_analyze(path, *_load_args):
            dropdown.dismiss()
            self.load_sgf_file(path, fast=fast, rewind=rewind)

        for idx, (path, filename) in enumerate(zip(sgf_files, labels)):
            label = f"[NEW] {filename}" if idx < 3 else filename
            label = truncate(label)
            menu_item = MenuItem(text=label, content_width=max(base_width, len(label) * dp(7)))
            menu_item.height = item_height
            menu_item.font_size = font_size
            menu_item.background_color = Theme.LIGHTER_BACKGROUND_COLOR
            label_widget = menu_item.ids.get("label")
            if label_widget:
                label_widget.color = Theme.TEXT_COLOR
                label_widget.shorten = True
                label_widget.shorten_from = "right"
            menu_item.bind(on_action=lambda _item, p=path: load_and_analyze(p))
            dropdown.add_widget(menu_item)
            menu_items.append(menu_item)
            max_width = max(max_width, menu_item.content_width)

        if max_width:
            dropdown.width = max(max_width, base_width)
            for item in menu_items:
                label_widget = item.ids.get("label")
                if label_widget:
                    label_widget.text_size = (dropdown.width - dp(70), None)

        sgf_button = getattr(self.board_controls, "sgf_button", None)
        try:
            if sgf_button:
                dropdown.open(sgf_button)
            else:
                raise AttributeError("SGF button not available")
        except Exception as e:
            self.log(f"Failed to open recent SGF dropdown: {e}", OUTPUT_DEBUG)
            self("analyze-sgf-popup")

    def _do_save_game(self, filename=None):
        filename = filename or self.game.sgf_filename
        if not filename:
            return self("save-game-as-popup")
        try:
            msg = self.game.write_sgf(filename)
            self.log(msg, OUTPUT_INFO)
            self.controls.set_status(msg, STATUS_INFO, check_level=False)
        except Exception as e:
            self.log(f"Failed to save SGF to {filename}: {e}", OUTPUT_ERROR)

    def _do_save_game_as_popup(self):
        popup_contents = SaveSGFPopup(suggested_filename=self.game.generate_filename())
        save_game_popup = I18NPopup(
            title_key="save sgf title", size=[dp(1200), dp(800)], content=popup_contents
        ).__self__

        def readfile(*_args):
            filename = popup_contents.filesel.filename
            if not filename.lower().endswith(".sgf"):
                filename += ".sgf"
            save_game_popup.dismiss()
            path, file = os.path.split(filename.strip())
            if not path:
                path = popup_contents.filesel.path  # whatever dir is shown
            if path != self.config("general/sgf_save"):
                self.log(f"Updating sgf save path default to {path}", OUTPUT_DEBUG)
                self._config["general"]["sgf_save"] = path
                self.save_config("general")
            self._do_save_game(os.path.join(path, file))

        popup_contents.filesel.on_success = readfile
        popup_contents.filesel.on_submit = readfile
        save_game_popup.open()

    def _do_export_karte(self, *args, **kwargs):
        """Export karte. Delegates to karte_export.do_export_karte()."""
        do_export_karte(self, self._do_mykatrain_settings_popup)

    def _determine_user_color(self, username: str) -> Optional[str]:
        """Determine user's color based on player names in SGF.

        Delegates to katrain.gui.features.karte_export.determine_user_color().
        """
        return determine_user_color(self.game, username)

    def _do_export_summary(self, *args, **kwargs):
        """Delegates to summary_ui.do_export_summary()."""
        do_export_summary(
            self,
            self._scan_and_show_player_selection,
            self._load_export_settings,
            self._save_export_settings,
        )

    def _do_export_summary_ui(self, *args, **kwargs):
        """Delegates to summary_ui.do_export_summary_ui()."""
        do_export_summary_ui(
            self,
            self._scan_and_show_player_selection,
            self._load_export_settings,
            self._save_export_settings,
        )

    def _extract_analysis_from_sgf_node(self, node) -> dict:
        """SGFノードのKTプロパティから解析データを抽出。

        Delegates to summary_stats.extract_analysis_from_sgf_node().
        """
        return extract_analysis_from_sgf_node(node)

    def _extract_sgf_statistics(self, path: str) -> dict:
        """SGFファイルから統計データを直接抽出（KTプロパティ解析）。

        Delegates to summary_stats.extract_sgf_statistics().
        """
        return extract_sgf_statistics(path, self, self.engine, self.log)

    def _scan_player_names(self, sgf_files: list) -> dict:
        """Delegates to summary_aggregator.scan_player_names()."""
        return scan_player_names(sgf_files, self.log)

    def _scan_and_show_player_selection(self, sgf_files: list):
        """Delegates to summary_ui.scan_and_show_player_selection()."""
        scan_and_show_player_selection(
            sgf_files,
            self,
            self._scan_player_names,
            self._process_summary_with_selected_players,
            self._show_player_selection_dialog,
        )

    def _process_summary_with_selected_players(self, sgf_files: list, selected_players: list):
        """Delegates to summary_ui.process_summary_with_selected_players()."""
        process_summary_with_selected_players(
            sgf_files,
            selected_players,
            self._process_and_export_summary,
        )

    def _show_player_selection_dialog(self, sorted_players: list, sgf_files: list):
        """Delegates to summary_ui.show_player_selection_dialog()."""
        show_player_selection_dialog(
            sorted_players,
            sgf_files,
            self._load_export_settings,
            self._save_export_settings,
            self._process_and_export_summary,
        )

    def _process_and_export_summary(self, sgf_paths: list, progress_popup, selected_players: list = None):
        """Delegates to summary_ui.process_and_export_summary()."""
        process_and_export_summary(
            sgf_paths,
            progress_popup,
            selected_players,
            self,
            self._extract_sgf_statistics,
            self._categorize_games_by_stats,
            self._save_summaries_per_player,
            self._save_categorized_summaries_from_stats,
        )

    def _categorize_games_by_stats(self, game_stats_list: list, focus_player: str) -> dict:
        """Delegates to summary_aggregator.categorize_games_by_stats()."""
        return categorize_games_by_stats(game_stats_list, focus_player)

    def _collect_rank_info(self, stats_list: list, focus_player: str) -> str:
        """Delegates to summary_aggregator.collect_rank_info()."""
        return collect_rank_info(stats_list, focus_player)

    def _build_summary_from_stats(self, stats_list: list, focus_player: str = None) -> str:
        """Delegates to summary_formatter.build_summary_from_stats()."""
        return build_summary_from_stats(stats_list, focus_player, self.config)

    def _save_summaries_per_player(self, game_stats_list: list, selected_players: list, progress_popup):
        """Delegates to summary_io.save_summaries_per_player()."""
        save_summaries_per_player(
            game_stats_list,
            selected_players,
            progress_popup,
            self,
            self._categorize_games_by_stats,
            self._build_summary_from_stats,
        )

    def _save_categorized_summaries_from_stats(self, categorized_games: dict, player_name: str, progress_popup):
        """Delegates to summary_io.save_categorized_summaries_from_stats()."""
        save_categorized_summaries_from_stats(
            categorized_games,
            player_name,
            progress_popup,
            self,
            self._build_summary_from_stats,
        )

    def _save_summary_file(self, summary_text: str, player_name: str, progress_popup):
        """Delegates to summary_io.save_summary_file()."""
        save_summary_file(summary_text, player_name, progress_popup, self)

    def _do_quiz_popup(self):
        """Delegates to quiz_popup.do_quiz_popup()."""
        do_quiz_popup(
            self,
            self._start_quiz_session,
            lambda: self.update_state(redraw_board=True),
        )

    def _do_mykatrain_settings_popup(self):
        """Delegates to settings_popup.do_mykatrain_settings_popup()."""
        do_mykatrain_settings_popup(self)

    def _do_batch_analyze_popup(self):
        """Show batch analyze folder dialog."""
        import threading
        from kivy.uix.textinput import TextInput
        from kivy.uix.checkbox import CheckBox
        from kivy.uix.scrollview import ScrollView

        from katrain.tools.batch_analyze_sgf import run_batch, BatchResult, parse_timeout_input, DEFAULT_TIMEOUT_SECONDS

        # Get default values from mykatrain_settings
        mykatrain_settings = self.config("mykatrain_settings") or {}
        # Load all batch options for persistence (PR: batch options persistence)
        batch_options = mykatrain_settings.get("batch_options", {})
        # Fallback to legacy key for input_dir
        default_input_dir = batch_options.get("input_dir") or mykatrain_settings.get("batch_export_input_directory", "")
        default_output_dir = batch_options.get("output_dir", "")

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
        input_input = TextInput(
            text=default_input_dir,
            multiline=False,
            size_hint_x=0.6,
            font_name=Theme.DEFAULT_FONT,
        )
        input_browse = Button(
            text=i18n._("Browse..."),
            size_hint_x=0.15,
            background_color=Theme.LIGHTER_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        input_row.add_widget(input_label)
        input_row.add_widget(input_input)
        input_row.add_widget(input_browse)
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
        output_input = TextInput(
            text=default_output_dir,
            hint_text=i18n._("mykatrain:batch:output_hint"),
            multiline=False,
            size_hint_x=0.6,
            font_name=Theme.DEFAULT_FONT,
        )
        output_browse = Button(
            text=i18n._("Browse..."),
            size_hint_x=0.15,
            background_color=Theme.LIGHTER_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        output_row.add_widget(output_label)
        output_row.add_widget(output_input)
        output_row.add_widget(output_browse)
        main_layout.add_widget(output_row)

        # batch_options already loaded at the top of this method

        # Options row 1: visits and timeout
        options_row1 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))

        # Get saved visits value
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
        visits_input = TextInput(
            text=str(saved_visits) if saved_visits else "",
            hint_text=i18n._("mykatrain:batch:visits_hint"),
            multiline=False,
            input_filter="int",
            size_hint_x=0.2,
            font_name=Theme.DEFAULT_FONT,
        )

        # Get saved timeout value (None means no timeout)
        saved_timeout = batch_options.get("timeout", DEFAULT_TIMEOUT_SECONDS)
        # Display "None" for no timeout, otherwise the numeric value
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
        timeout_input = TextInput(
            text=timeout_display,
            multiline=False,
            # No input_filter: allow "None" for no timeout, or numeric values
            size_hint_x=0.15,
            font_name=Theme.DEFAULT_FONT,
        )

        options_row1.add_widget(visits_label)
        options_row1.add_widget(visits_input)
        options_row1.add_widget(Label(size_hint_x=0.1))  # spacer
        options_row1.add_widget(timeout_label)
        options_row1.add_widget(timeout_input)
        options_row1.add_widget(Label(size_hint_x=0.2))  # spacer
        main_layout.add_widget(options_row1)

        # Options row 2: skip analyzed checkbox
        options_row2 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(10))

        # Load saved skip_analyzed (default True)
        skip_checkbox = CheckBox(
            active=batch_options.get("skip_analyzed", True),
            size_hint_x=None, width=dp(30)
        )
        skip_label = Label(
            text=i18n._("mykatrain:batch:skip_analyzed"),
            size_hint_x=0.4,
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        skip_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

        options_row2.add_widget(skip_checkbox)
        options_row2.add_widget(skip_label)
        options_row2.add_widget(Label(size_hint_x=0.5))  # spacer
        main_layout.add_widget(options_row2)

        # Options row 3: output options (save SGF, karte, summary)
        options_row3 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(5))

        save_sgf_checkbox = CheckBox(
            active=batch_options.get("save_analyzed_sgf", False),
            size_hint_x=None, width=dp(30)
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

        karte_checkbox = CheckBox(
            active=batch_options.get("generate_karte", True),
            size_hint_x=None, width=dp(30)
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

        summary_checkbox = CheckBox(
            active=batch_options.get("generate_summary", True),
            size_hint_x=None, width=dp(30)
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

        options_row3.add_widget(save_sgf_checkbox)
        options_row3.add_widget(save_sgf_label)
        options_row3.add_widget(karte_checkbox)
        options_row3.add_widget(karte_label)
        options_row3.add_widget(summary_checkbox)
        options_row3.add_widget(summary_label)
        main_layout.add_widget(options_row3)

        # Options row 4: Player filter (for Karte) and min games (for Summary)
        options_row4 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(5))

        # Player filter label
        player_filter_label = Label(
            text=i18n._("mykatrain:batch:player_filter"),
            size_hint_x=0.18,
            halign="right",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        player_filter_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

        # Load saved player filter state
        saved_filter = batch_options.get("karte_player_filter")  # None, "B", or "W"

        filter_both = ToggleButton(
            text=i18n._("mykatrain:batch:filter_both"),
            group="player_filter",
            state="down" if saved_filter is None else "normal",
            size_hint_x=0.12,
            font_name=Theme.DEFAULT_FONT,
        )
        filter_black = ToggleButton(
            text=i18n._("mykatrain:batch:filter_black"),
            group="player_filter",
            state="down" if saved_filter == "B" else "normal",
            size_hint_x=0.12,
            font_name=Theme.DEFAULT_FONT,
        )
        filter_white = ToggleButton(
            text=i18n._("mykatrain:batch:filter_white"),
            group="player_filter",
            state="down" if saved_filter == "W" else "normal",
            size_hint_x=0.12,
            font_name=Theme.DEFAULT_FONT,
        )

        # Min games label and input
        min_games_label = Label(
            text=i18n._("mykatrain:batch:min_games"),
            size_hint_x=0.18,
            halign="right",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        min_games_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))

        min_games_input = TextInput(
            text=str(batch_options.get("min_games_per_player", 3)),
            multiline=False,
            input_filter="int",
            size_hint_x=0.1,
            font_name=Theme.DEFAULT_FONT,
        )

        options_row4.add_widget(player_filter_label)
        options_row4.add_widget(filter_both)
        options_row4.add_widget(filter_black)
        options_row4.add_widget(filter_white)
        options_row4.add_widget(min_games_label)
        options_row4.add_widget(min_games_input)
        options_row4.add_widget(Label(size_hint_x=0.18))  # spacer
        main_layout.add_widget(options_row4)

        # Options row 5: Variable Visits and Sound on finish
        options_row5 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(5))

        # Variable Visits checkbox
        variable_visits_checkbox = CheckBox(
            active=batch_options.get("variable_visits", False),
            size_hint_x=None, width=dp(30)
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

        # Jitter % input
        jitter_label = Label(
            text=i18n._("mykatrain:batch:jitter_pct"),
            size_hint_x=0.1,
            halign="right",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        jitter_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        jitter_input = TextInput(
            text=str(batch_options.get("jitter_pct", 10)),
            multiline=False,
            input_filter="int",
            size_hint_x=0.08,
            font_name=Theme.DEFAULT_FONT,
        )

        # Deterministic checkbox
        deterministic_checkbox = CheckBox(
            active=batch_options.get("deterministic", True),
            size_hint_x=None, width=dp(30)
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

        # Sound on finish checkbox
        sound_checkbox = CheckBox(
            active=batch_options.get("sound_on_finish", False),
            size_hint_x=None, width=dp(30)
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

        options_row5.add_widget(variable_visits_checkbox)
        options_row5.add_widget(variable_visits_label)
        options_row5.add_widget(jitter_label)
        options_row5.add_widget(jitter_input)
        options_row5.add_widget(deterministic_checkbox)
        options_row5.add_widget(deterministic_label)
        options_row5.add_widget(sound_checkbox)
        options_row5.add_widget(sound_label)
        main_layout.add_widget(options_row5)

        # Helper function to get selected player filter
        def get_player_filter() -> Optional[str]:
            if filter_black.state == "down":
                return "B"
            elif filter_white.state == "down":
                return "W"
            return None  # Both = no filter

        # Progress row
        progress_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30), spacing=dp(10))
        progress_label = Label(
            text=i18n._("mykatrain:batch:ready"),
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        progress_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        progress_row.add_widget(progress_label)
        main_layout.add_widget(progress_row)

        # Log area (scrollable)
        log_scroll = ScrollView(size_hint=(1, 1))
        log_text = TextInput(
            text="",
            multiline=True,
            readonly=True,
            size_hint_y=None,
            font_name=Theme.DEFAULT_FONT,
            background_color=(0.1, 0.1, 0.1, 1),
            foreground_color=(0.9, 0.9, 0.9, 1),
        )
        log_text.bind(minimum_height=log_text.setter('height'))
        log_scroll.add_widget(log_text)
        main_layout.add_widget(log_scroll)

        # Buttons row
        buttons_layout = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48))
        start_button = Button(
            text=i18n._("mykatrain:batch:start"),
            size_hint_x=0.5,
            height=dp(48),
            background_color=Theme.BOX_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        close_button = Button(
            text=i18n._("Close"),
            size_hint_x=0.5,
            height=dp(48),
            background_color=Theme.LIGHTER_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        buttons_layout.add_widget(start_button)
        buttons_layout.add_widget(close_button)
        main_layout.add_widget(buttons_layout)

        popup = I18NPopup(
            title_key="mykatrain:batch:title",
            size=[dp(800), dp(600)],
            content=main_layout,
        ).__self__

        # State for cancellation
        cancel_flag = [False]
        is_running = [False]

        # Log callback (thread-safe via Clock)
        def log_cb(msg: str):
            def update_log(dt):
                log_text.text += msg + "\n"
                # Auto-scroll to bottom
                log_scroll.scroll_y = 0
            Clock.schedule_once(update_log, 0)

        # Progress callback (thread-safe via Clock)
        def progress_cb(current: int, total: int, filename: str):
            def update_progress(dt):
                progress_label.text = f"[{current}/{total}] {filename}"
            Clock.schedule_once(update_progress, 0)

        # Run batch in background thread
        def run_batch_thread():
            input_dir = input_input.text.strip()
            output_dir = output_input.text.strip() or None
            visits = int(visits_input.text) if visits_input.text.strip() else None
            # Parse timeout with support for "None" (no timeout), invalid values fall back to default
            timeout = parse_timeout_input(timeout_input.text, default=DEFAULT_TIMEOUT_SECONDS, log_cb=log_cb)
            skip_analyzed = skip_checkbox.active

            # New options
            save_analyzed_sgf = save_sgf_checkbox.active
            generate_karte = karte_checkbox.active
            generate_summary = summary_checkbox.active
            karte_player_filter = get_player_filter()
            min_games_per_player = int(min_games_input.text) if min_games_input.text.strip() else 3

            # Variable visits options
            variable_visits = variable_visits_checkbox.active
            jitter_pct = int(jitter_input.text) if jitter_input.text.strip() else 10
            deterministic = deterministic_checkbox.active
            sound_on_finish = sound_checkbox.active

            # Save all options for next time (persistence across sessions)
            # Persist timeout as-is (None means no timeout, numeric means timeout in seconds)
            self._save_batch_options({
                "input_dir": input_dir,
                "output_dir": output_dir or "",
                "visits": visits,
                "timeout": timeout,
                "skip_analyzed": skip_analyzed,
                "save_analyzed_sgf": save_analyzed_sgf,
                "generate_karte": generate_karte,
                "generate_summary": generate_summary,
                "karte_player_filter": karte_player_filter,
                "min_games_per_player": min_games_per_player,
                "variable_visits": variable_visits,
                "jitter_pct": jitter_pct,
                "deterministic": deterministic,
                "sound_on_finish": sound_on_finish,
            })

            # Get skill preset for karte/summary generation
            skill_preset = self.config("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET

            result = run_batch(
                katrain=self,
                engine=self.engine,
                input_dir=input_dir,
                output_dir=output_dir,
                visits=visits,
                timeout=timeout,
                skip_analyzed=skip_analyzed,
                progress_cb=progress_cb,
                log_cb=log_cb,
                cancel_flag=cancel_flag,
                # New options
                save_analyzed_sgf=save_analyzed_sgf,
                generate_karte=generate_karte,
                generate_summary=generate_summary,
                karte_player_filter=karte_player_filter,
                min_games_per_player=min_games_per_player,
                skill_preset=skill_preset,
                # Variable visits options
                variable_visits=variable_visits,
                jitter_pct=jitter_pct,
                deterministic=deterministic,
            )

            # Play completion sound if enabled
            if sound_on_finish and not result.cancelled:
                try:
                    from katrain.gui.sound import play_sound
                    play_sound("stone")  # Use existing stone sound as completion notification
                except Exception:
                    pass  # Silently ignore sound errors

            # Show summary on main thread
            def show_summary(dt):
                is_running[0] = False
                start_button.text = i18n._("mykatrain:batch:start")
                close_button.disabled = False

                if result.cancelled:
                    summary = i18n._("mykatrain:batch:cancelled")
                else:
                    # Extended summary with karte/summary counts and error reporting
                    karte_total = result.karte_written + result.karte_failed

                    # Summary status: "Yes" / "No (skipped)" / "ERROR: <message>"
                    if result.summary_written:
                        summary_status = "Yes"
                    elif result.summary_error:
                        summary_status = f"ERROR: {result.summary_error}"
                    else:
                        summary_status = "No (skipped)"

                    summary = i18n._("mykatrain:batch:complete_extended").format(
                        success=result.success_count,
                        failed=result.fail_count,
                        skipped=result.skip_count,
                        karte_ok=result.karte_written,
                        karte_total=karte_total,
                        karte_fail=result.karte_failed,
                        summary=summary_status,
                        sgf=result.analyzed_sgf_written,
                        output_dir=result.output_dir,
                    )
                progress_label.text = summary
                log_cb(summary)

            Clock.schedule_once(show_summary, 0)

        # Start button callback
        def on_start(*_args):
            if is_running[0]:
                # Cancel
                cancel_flag[0] = True
                start_button.text = i18n._("mykatrain:batch:cancelling")
                start_button.disabled = True
                return

            # Validate input
            input_dir = input_input.text.strip()
            if not input_dir or not os.path.isdir(input_dir):
                self.controls.set_status(i18n._("mykatrain:batch:error_input_dir"), STATUS_ERROR)
                return

            # Check engine
            if not self.engine:
                self.controls.set_status(i18n._("mykatrain:batch:error_no_engine"), STATUS_ERROR)
                return

            # Start
            is_running[0] = True
            cancel_flag[0] = False
            start_button.text = i18n._("mykatrain:batch:cancel")
            start_button.disabled = False
            close_button.disabled = True
            log_text.text = ""
            progress_label.text = i18n._("mykatrain:batch:starting")

            threading.Thread(target=run_batch_thread, daemon=True).start()

        # Close button callback
        def on_close(*_args):
            if is_running[0]:
                return  # Don't close while running
            popup.dismiss()

        # Browse callbacks
        def browse_input_dir(*_args):
            from katrain.gui.popups import LoadSGFPopup

            browse_popup_content = LoadSGFPopup(self)
            browse_popup_content.filesel.dirselect = True
            browse_popup_content.filesel.select_string = "Select This Folder"
            if input_input.text and os.path.isdir(input_input.text):
                browse_popup_content.filesel.path = os.path.abspath(input_input.text)

            browse_popup = Popup(
                title="Select input folder",
                size_hint=(0.8, 0.8),
                content=browse_popup_content,
            ).__self__

            def on_select(*_args):
                input_input.text = browse_popup_content.filesel.file_text.text
                browse_popup.dismiss()

            browse_popup_content.filesel.bind(on_success=on_select)
            browse_popup.open()

        def browse_output_dir(*_args):
            from katrain.gui.popups import LoadSGFPopup

            browse_popup_content = LoadSGFPopup(self)
            browse_popup_content.filesel.dirselect = True
            browse_popup_content.filesel.select_string = "Select This Folder"
            if output_input.text and os.path.isdir(output_input.text):
                browse_popup_content.filesel.path = os.path.abspath(output_input.text)

            browse_popup = Popup(
                title="Select output folder",
                size_hint=(0.8, 0.8),
                content=browse_popup_content,
            ).__self__

            def on_select(*_args):
                output_input.text = browse_popup_content.filesel.file_text.text
                browse_popup.dismiss()

            browse_popup_content.filesel.bind(on_success=on_select)
            browse_popup.open()

        start_button.bind(on_release=on_start)
        close_button.bind(on_release=on_close)
        input_browse.bind(on_release=browse_input_dir)
        output_browse.bind(on_release=browse_output_dir)

        popup.open()

    def _format_points_loss(self, loss: Optional[float]) -> str:
        """Delegates to quiz_popup.format_points_loss()."""
        return format_points_loss(loss)

    def _start_quiz_session(self, quiz_items: List[eval_metrics.QuizItem]) -> None:
        """Delegates to quiz_session.start_quiz_session()."""
        start_quiz_session(
            self,
            quiz_items,
            self._format_points_loss,
            lambda: self.update_state(redraw_board=True),
        )

    def load_sgf_from_clipboard(self):
        clipboard = Clipboard.paste()
        if not clipboard:
            self.controls.set_status("Ctrl-V pressed but clipboard is empty.", STATUS_INFO)
            return

        url_match = re.match(r"(?P<url>https?://[^\s]+)", clipboard)
        if url_match:
            self.log("Recognized url: " + url_match.group(), OUTPUT_INFO)
            http = urllib3.PoolManager()
            response = http.request("GET", url_match.group())
            clipboard = response.data.decode("utf-8")

        try:
            move_tree = KaTrainSGF.parse_sgf(clipboard)
        except Exception as exc:
            self.controls.set_status(
                i18n._("Failed to import from clipboard").format(error=exc, contents=clipboard[:50]), STATUS_INFO
            )
            return
        move_tree.nodes_in_tree[-1].analyze(
            self.engine, analyze_fast=False
        )  # speed up result for looking at end of game
        self._do_new_game(move_tree=move_tree, analyze_fast=True)
        self("redo", 9999)
        self.log("Imported game from clipboard.", OUTPUT_INFO)

    def on_touch_up(self, touch):
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
        return super().on_touch_up(touch)

    @property
    def shortcuts(self):
        return {
            k: v
            for ks, v in [
                (Theme.KEY_ANALYSIS_CONTROLS_SHOW_CHILDREN, self.analysis_controls.show_children),
                (Theme.KEY_ANALYSIS_CONTROLS_EVAL, self.analysis_controls.eval),
                (Theme.KEY_ANALYSIS_CONTROLS_HINTS, self.analysis_controls.hints),
                (Theme.KEY_ANALYSIS_CONTROLS_OWNERSHIP, self.analysis_controls.ownership),
                (Theme.KEY_ANALYSIS_CONTROLS_POLICY, self.analysis_controls.policy),
                (Theme.KEY_AI_MOVE, ("ai-move",)),
                (Theme.KEY_ANALYZE_EXTRA_EXTRA, ("analyze-extra", "extra")),
                (Theme.KEY_ANALYZE_EXTRA_EQUALIZE, ("analyze-extra", "equalize")),
                (Theme.KEY_ANALYZE_EXTRA_SWEEP, ("analyze-extra", "sweep")),
                (Theme.KEY_ANALYZE_EXTRA_ALTERNATIVE, ("analyze-extra", "alternative")),
                (Theme.KEY_SELECT_BOX, ("select-box",)),
                (Theme.KEY_RESET_ANALYSIS, ("reset-analysis",)),
                (Theme.KEY_INSERT_MODE, ("insert-mode",)),
                (Theme.KEY_PASS, ("play", None)),
                (Theme.KEY_SELFPLAY_TO_END, ("selfplay-setup", "end", None)),
                (Theme.KEY_NAV_PREV_BRANCH, ("undo", "branch")),
                (Theme.KEY_NAV_BRANCH_DOWN, ("switch-branch", 1)),
                (Theme.KEY_NAV_BRANCH_UP, ("switch-branch", -1)),
                (Theme.KEY_TIMER_POPUP, ("timer-popup",)),
                (Theme.KEY_TEACHER_POPUP, ("teacher-popup",)),
                (Theme.KEY_AI_POPUP, ("ai-popup",)),
                (Theme.KEY_CONFIG_POPUP, ("config-popup",)),
                (Theme.KEY_CONTRIBUTE_POPUP, ("contribute-popup",)),
                (Theme.KEY_STOP_ANALYSIS, ("analyze-extra", "stop")),
            ]
            for k in (ks if isinstance(ks, list) else [ks])
        }

    @property
    def popup_open(self) -> Popup:
        app = App.get_running_app()
        if app:
            first_child = app.root_window.children[0]
            return first_child if isinstance(first_child, Popup) else None

    def _on_keyboard_down(self, _keyboard, keycode, _text, modifiers):
        self.last_key_down = keycode
        ctrl_pressed = "ctrl" in modifiers or ("meta" in modifiers and kivy_platform == "macosx")
        shift_pressed = "shift" in modifiers
        if self.controls.note.focus:
            return  # when making notes, don't allow keyboard shortcuts
        popup = self.popup_open
        if popup:
            if keycode[1] in [
                Theme.KEY_DEEPERANALYSIS_POPUP,
                Theme.KEY_REPORT_POPUP,
                Theme.KEY_TIMER_POPUP,
                Theme.KEY_TEACHER_POPUP,
                Theme.KEY_AI_POPUP,
                Theme.KEY_CONFIG_POPUP,
                Theme.KEY_TSUMEGO_FRAME,
                Theme.KEY_CONTRIBUTE_POPUP,
            ]:  # switch between popups
                popup.dismiss()

                return
            elif keycode[1] in Theme.KEY_SUBMIT_POPUP:
                fn = getattr(popup.content, "on_submit", None)
                if fn:
                    fn()
                return
            else:
                return

        if self.contributing:
            if keycode[1] == Theme.KEY_STOP_CONTRIBUTING:
                self.engine.graceful_shutdown()
                return
            elif keycode[1] in Theme.KEY_PAUSE_CONTRIBUTE:
                self.engine.pause()
                return

        if keycode[1] == Theme.KEY_TOGGLE_CONTINUOUS_ANALYSIS:
            self.toggle_continuous_analysis(quiet=shift_pressed)
        elif keycode[1] == Theme.KEY_TOGGLE_MOVENUM:
            self.toggle_move_num()
        elif keycode[1] == Theme.KEY_TOGGLE_COORDINATES:
            self.board_gui.toggle_coordinates()
        elif keycode[1] in Theme.KEY_PAUSE_TIMER and not ctrl_pressed:
            self.controls.timer.paused = not self.controls.timer.paused
        elif keycode[1] in Theme.KEY_ZEN:
            self.zen = (self.zen + 1) % 3
        elif keycode[1] in Theme.KEY_NAV_PREV:
            self("undo", 1 + shift_pressed * 9 + ctrl_pressed * 9999)
        elif keycode[1] in Theme.KEY_NAV_NEXT:
            self("redo", 1 + shift_pressed * 9 + ctrl_pressed * 9999)
        elif keycode[1] == Theme.KEY_NAV_GAME_START:
            self("undo", 9999)
        elif keycode[1] == Theme.KEY_NAV_GAME_END:
            self("redo", 9999)
        elif keycode[1] == Theme.KEY_MOVE_TREE_MAKE_SELECTED_NODE_MAIN_BRANCH:
            self.controls.move_tree.make_selected_node_main_branch()
        elif keycode[1] == Theme.KEY_NAV_MISTAKE and not ctrl_pressed:
            self("find-mistake", "undo" if shift_pressed else "redo")
        elif keycode[1] == Theme.KEY_MOVE_TREE_DELETE_SELECTED_NODE and ctrl_pressed:
            self.controls.move_tree.delete_selected_node()
        elif keycode[1] == Theme.KEY_MOVE_TREE_TOGGLE_SELECTED_NODE_COLLAPSE and not ctrl_pressed:
            self.controls.move_tree.toggle_selected_node_collapse()
        elif keycode[1] == Theme.KEY_NEW_GAME and ctrl_pressed:
            self("new-game-popup")
        elif keycode[1] == Theme.KEY_LOAD_GAME and ctrl_pressed:
            self("analyze-sgf-popup")
        elif keycode[1] == Theme.KEY_SAVE_GAME and ctrl_pressed:
            self("save-game")
        elif keycode[1] == Theme.KEY_SAVE_GAME_AS and ctrl_pressed:
            self("save-game-as-popup")
        elif keycode[1] == Theme.KEY_COPY and ctrl_pressed:
            Clipboard.copy(self.game.root.sgf())
            self.controls.set_status(i18n._("Copied SGF to clipboard."), STATUS_INFO)
        elif keycode[1] == Theme.KEY_PASTE and ctrl_pressed:
            self.load_sgf_from_clipboard()
        elif keycode[1] == Theme.KEY_NAV_PREV_BRANCH and shift_pressed:
            self("undo", "main-branch")
        elif keycode[1] == Theme.KEY_DEEPERANALYSIS_POPUP:
            self.analysis_controls.dropdown.open_game_analysis_popup()
        elif keycode[1] == Theme.KEY_TSUMEGO_FRAME:
            self.analysis_controls.dropdown.open_tsumego_frame_popup()
        elif keycode[1] == Theme.KEY_REPORT_POPUP:
            self.analysis_controls.dropdown.open_report_popup()
        elif keycode[1] == "f10" and self.debug_level >= OUTPUT_EXTRA_DEBUG:
            import yappi

            yappi.set_clock_type("cpu")
            yappi.start()
            self.log("starting profiler", OUTPUT_ERROR)
        elif keycode[1] == "f11" and self.debug_level >= OUTPUT_EXTRA_DEBUG:
            import time
            import yappi

            stats = yappi.get_func_stats()
            filename = f"callgrind.{int(time.time())}.prof"
            stats.save(filename, type="callgrind")
            self.log(f"wrote profiling results to {filename}", OUTPUT_ERROR)
        elif not ctrl_pressed:
            shortcut = self.shortcuts.get(keycode[1])
            if shortcut is not None:
                if isinstance(shortcut, Widget):
                    shortcut.trigger_action(duration=0)
                else:
                    self(*shortcut)

    def _on_keyboard_up(self, _keyboard, keycode):
        if keycode[1] in ["alt", "tab"]:
            Clock.schedule_once(lambda *_args: self._single_key_action(keycode), 0.05)

    def _single_key_action(self, keycode):
        if (
            self.controls.note.focus
            or self.popup_open
            or keycode != self.last_key_down
            or time.time() - self.last_focus_event < 0.2  # this is here to prevent alt-tab from firing alt or tab
        ):
            return
        if keycode[1] == "alt":
            self.nav_drawer.set_state("toggle")
        elif keycode[1] == "tab":
            self.play_mode.switch_ui_mode()


class KaTrainApp(MDApp):
    gui = ObjectProperty(None)
    language = StringProperty(DEFAULT_LANGUAGE)

    def __init__(self):
        super().__init__()

    def is_valid_window_position(self, left, top, width, height):
        try:
            from screeninfo import get_monitors
            monitors = get_monitors()
            for monitor in monitors:
                if (left >= monitor.x and left + width <= monitor.x + monitor.width and
                    top >= monitor.y and top + height <= monitor.y + monitor.height):
                    return True
            return False
        except Exception as e:
            return True # yolo

    def build(self):
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

        theme_files = glob.glob(os.path.join(os.path.expanduser(DATA_FOLDER), "theme*.json"))
        for theme_file in sorted(theme_files):
            try:
                with open(theme_file) as f:
                    theme_overrides = json.load(f)
                for k, v in theme_overrides.items():
                    setattr(Theme, k, v)
                    print(f"[{theme_file}] Found theme override {k} = {v}")
            except Exception as e:  # noqa E722
                print(f"Failed to load theme file {theme_file}: {e}")

        Theme.DEFAULT_FONT = resource_find(Theme.DEFAULT_FONT)
        Builder.load_file(kv_file)

        Window.bind(on_request_close=self.on_request_close)
        Window.bind(on_dropfile=lambda win, file: self.gui.load_sgf_file(file.decode("utf8")))
        self.gui = KaTrainGui()
        Builder.load_file(popup_kv_file)

        win_left = win_top = win_size = None
        if self.gui.config("ui_state/restoresize", True):
            win_size = self.gui.config("ui_state/size", [])
            win_left = self.gui.config("ui_state/left", None)
            win_top = self.gui.config("ui_state/top", None)
        if not win_size:
            window_scale_fac = 1
            try:
                from screeninfo import get_monitors

                for m in get_monitors():
                    window_scale_fac = min(window_scale_fac, (m.height - 100) / 1000, (m.width - 100) / 1300)
            except Exception as e:
                window_scale_fac = 0.85
            win_size = [1300 * window_scale_fac, 1000 * window_scale_fac]
        self.gui.log(f"Setting window size to {win_size} and position to {[win_left, win_top]}", OUTPUT_DEBUG)
        Window.size = (win_size[0], win_size[1])
        if win_left is not None and win_top is not None and self.is_valid_window_position(win_left, win_top, win_size[0], win_size[1]):
            Window.left = win_left
            Window.top = win_top

        return self.gui

    def on_language(self, _instance, language):
        self.gui.log(f"Switching language to {language}", OUTPUT_INFO)
        i18n.switch_lang(language)
        self.gui._config["general"]["lang"] = language
        self.gui.save_config()
        if self.gui.game:
            self.gui.update_state()
            self.gui.controls.set_status("", STATUS_INFO)

    def webbrowser(self, site_key):
        websites = {
            "homepage": HOMEPAGE + "#manual",
            "support": HOMEPAGE + "#support",
            "contribute:signup": "http://katagotraining.org/accounts/signup/",
            "engine:help": HOMEPAGE + "/blob/master/ENGINE.md",
        }
        if site_key in websites:
            webbrowser.open(websites[site_key])

    def on_start(self):
        self.language = self.gui.config("general/lang")
        self.gui.start()

    def on_request_close(self, *_args, source=None):
        if source == "keyboard":
            return True  # do not close on esc
        if getattr(self, "gui", None):
            self.gui.play_mode.save_ui_state()
            self.gui._config["ui_state"]["size"] = list(Window._size)
            self.gui._config["ui_state"]["top"] = Window.top
            self.gui._config["ui_state"]["left"] = Window.left
            self.gui.save_config("ui_state")
            if self.gui.engine:
                self.gui.engine.shutdown(finish=None)

    def signal_handler(self, _signal, _frame):
        if self.gui.debug_level >= OUTPUT_DEBUG:
            print("TRACEBACKS")
            for threadId, stack in sys._current_frames().items():
                print(f"\n# ThreadID: {threadId}")
                for filename, lineno, name, line in traceback.extract_stack(stack):
                    print(f"\tFile: {filename}, line {lineno}, in {name}")
                    if line:
                        print(f"\t\t{line.strip()}")
        self.stop()


def run_app():
    class CrashHandler(ExceptionHandler):
        def handle_exception(self, inst):
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
            return ExceptionManager.PASS

    ExceptionManager.add_handler(CrashHandler())
    app = KaTrainApp()
    signal.signal(signal.SIGINT, app.signal_handler)
    app.run()


if __name__ == "__main__":
    run_app()
