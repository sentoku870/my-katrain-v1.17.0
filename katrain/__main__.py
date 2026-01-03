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
        """前回のエクスポート設定を読み込む"""
        return self.config("export_settings") or {}

    def _save_export_settings(self, sgf_directory: str = None, selected_players: list = None):
        """エクスポート設定を保存する"""
        current_settings = self._load_export_settings()

        if sgf_directory is not None:
            current_settings["last_sgf_directory"] = sgf_directory
        if selected_players is not None:
            current_settings["last_selected_players"] = selected_players

        # config システムに保存
        self._config["export_settings"] = current_settings
        self.save_config("export_settings")

    def _save_batch_options(self, options: dict):
        """Save batch analyze options for persistence across sessions."""
        mykatrain_settings = self.config("mykatrain_settings") or {}
        batch_options = mykatrain_settings.get("batch_options", {})
        batch_options.update(options)
        mykatrain_settings["batch_options"] = batch_options
        self._config["mykatrain_settings"] = mykatrain_settings
        self.save_config("mykatrain_settings")

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
            popup_contents.filesel.path = os.path.abspath(os.path.expanduser(self.config("general/sgf_load", ".")))
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
        # export_karte is executed from _message_loop_thread (NOT the main Kivy thread).
        # Any Kivy UI creation must happen on the main thread.
        Clock.schedule_once(lambda dt: self._do_export_karte_ui(*args, **kwargs), 0)

    def _do_export_karte_ui(self, *args, **kwargs):
        """Export karte using myKatrain settings (Phase 3)"""
        if not self.game:
            return

        # Load settings
        settings = self.config("mykatrain_settings") or {}
        output_dir = settings.get("karte_output_directory", "")
        karte_format = settings.get("karte_format", "both")
        default_user = settings.get("default_user_name", "")

        # Validate output directory
        if not output_dir or not os.path.isdir(output_dir):
            Popup(
                title=i18n._("Error"),
                content=Label(
                    text=i18n._("mykatrain:error:output_dir_not_configured"),
                    halign="center",
                    valign="middle",
                    font_name=Theme.DEFAULT_FONT,
                ),
                size_hint=(0.5, 0.3),
            ).open()
            # Open settings dialog
            self._do_mykatrain_settings_popup()
            return

        # Generate filename base
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        root_name = self.game.root.get_property("GN", None)
        base_name = (
            os.path.splitext(os.path.basename(self.game.sgf_filename or ""))[0]
            or (root_name if root_name not in [None, ""] else None)
            or self.game.game_id
        )
        base_name = base_name[:50]  # Truncate to avoid overly long filenames
        # Sanitize filename: replace problematic characters
        base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)

        # Check if analysis data exists
        snapshot = self.game.build_eval_snapshot()
        if not snapshot.moves:
            Popup(
                title=i18n._("Error"),
                content=Label(
                    text=i18n._("mykatrain:error:no_analysis_data"),
                    halign="center",
                    valign="middle",
                    font_name=Theme.DEFAULT_FONT,
                ),
                size_hint=(0.5, 0.3),
            ).open()
            return

        # Determine player filter(s) and filename(s)
        exports = []  # [(player_filter, filename), ...]

        if karte_format == "both":
            # Both players in one file (player_filter=None)
            exports = [(None, f"karte_{base_name}_{timestamp}.md")]
        elif karte_format == "black_only":
            exports = [("B", f"karte_{base_name}_black_{timestamp}.md")]
        elif karte_format == "white_only":
            exports = [("W", f"karte_{base_name}_white_{timestamp}.md")]
        elif karte_format == "default_user_only":
            # Determine user's color
            player_color = self._determine_user_color(default_user)
            if player_color:
                color_label = "black" if player_color == "B" else "white"
                exports = [(player_color, f"karte_{base_name}_{color_label}_{timestamp}.md")]
            else:
                # Fallback to both in one file
                Popup(
                    title="Warning",
                    content=Label(
                        text=i18n._(
                            f"Could not determine color for '{default_user}'.\nExporting both players."
                        ),
                        halign="center",
                        valign="middle",
                        font_name=Theme.DEFAULT_FONT,
                    ),
                    size_hint=(0.5, 0.3),
                ).open()
                exports = [(None, f"karte_{base_name}_{timestamp}.md")]

        # Generate and save karte(s)
        saved_files = []
        for player_filter, filename in exports:
            full_path = os.path.join(output_dir, filename)
            try:
                text = self.game.build_karte_report(player_filter=player_filter)
                os.makedirs(output_dir, exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(text)
                saved_files.append(full_path)
            except Exception as exc:
                self.log(f"Failed to save karte: {exc}", OUTPUT_ERROR)
                Popup(
                    title="Error",
                    content=Label(text=f"Failed to save karte:\n{exc}", halign="center", valign="middle"),
                    size_hint=(0.5, 0.3),
                ).open()
                return

        # Show confirmation
        files_text = "\n".join(saved_files)
        self.controls.set_status(f"Karte(s) exported", STATUS_INFO, check_level=False)
        Popup(
            title="Karte exported",
            content=Label(text=f"Saved to:\n{files_text}", halign="center", valign="middle"),
            size_hint=(0.6, 0.4),
        ).open()

    def _determine_user_color(self, username: str) -> Optional[str]:
        """Determine user's color based on player names in SGF (Phase 3)

        Args:
            username: Username to match against player names

        Returns:
            "B" for black, "W" for white, None if no match or ambiguous
        """
        if not username or not self.game:
            return None

        # Use existing normalization logic from game.py
        def normalize_name(name: Optional[str]) -> str:
            if not name:
                return ""
            return re.sub(r"[^0-9a-z]+", "", str(name).casefold())

        pb = self.game.root.get_property("PB", None)
        pw = self.game.root.get_property("PW", None)

        user_norm = normalize_name(username)
        pb_norm = normalize_name(pb)
        pw_norm = normalize_name(pw)

        match_black = pb_norm and user_norm in pb_norm
        match_white = pw_norm and user_norm in pw_norm

        if match_black and not match_white:
            return "B"
        elif match_white and not match_black:
            return "W"
        else:
            # Ambiguous or no match
            return None

    def _do_export_summary(self, *args, **kwargs):
        # export_summary is executed from _message_loop_thread (NOT the main Kivy thread).
        # Any Kivy UI creation must happen on the main thread.
        Clock.schedule_once(lambda dt: self._do_export_summary_ui(*args, **kwargs), 0)

    def _do_export_summary_ui(self, *args, **kwargs):
        """ディレクトリ選択とまとめ生成（自動分類）"""
        # mykatrain_settings を取得
        mykatrain_settings = self.config("mykatrain_settings") or {}
        karte_format = mykatrain_settings.get("karte_format", "both")
        default_user = mykatrain_settings.get("default_user_name", "")
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
            # default_user_only の場合はプレイヤー選択もスキップ
            import threading
            threading.Thread(
                target=self._scan_and_show_player_selection,
                args=(sgf_files,),
                daemon=True
            ).start()
            return

        # 入力ディレクトリ未設定の場合: ディレクトリ選択ダイアログ
        popup_contents = LoadSGFPopup(self)
        popup_contents.filesel.dirselect = True  # ディレクトリ選択モード

        # mykatrain_settings の batch_export_input_directory を優先、なければ前回のパス
        if default_input_dir and os.path.isdir(default_input_dir):
            popup_contents.filesel.path = default_input_dir
        else:
            # フォールバック: 前回のパス
            export_settings = self._load_export_settings()
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
            self._save_export_settings(sgf_directory=selected_path)

            # プレイヤー名をスキャン（バックグラウンド）
            import threading
            threading.Thread(
                target=self._scan_and_show_player_selection,
                args=(sgf_files,),
                daemon=True
            ).start()

        popup_contents.filesel.on_success = process_directory
        load_popup.open()

    def _extract_analysis_from_sgf_node(self, node) -> dict:
        """SGFノードのKTプロパティから解析データを抽出"""
        import base64
        import gzip
        import json

        # CRITICAL: GameNode.add_list_property() は KT プロパティを
        # node.properties ではなく node.analysis_from_sgf に保存する
        kt_data = getattr(node, 'analysis_from_sgf', None)

        if not kt_data:
            return None

        try:
            # KTプロパティは複数の圧縮データのリスト
            if not isinstance(kt_data, list):
                return None

            if len(kt_data) < 3:
                return None

            # KaTrain SGF format: [ownership_data, policy_data, main_data]
            # Only main_data is JSON, ownership and policy are binary floats
            main_data = gzip.decompress(base64.standard_b64decode(kt_data[2]))
            analysis = json.loads(main_data)

            # analysis already contains {"root": {...}, "moves": {...}}
            return analysis

        except Exception as e:
            return None

    def _extract_sgf_statistics(self, path: str) -> dict:
        """SGFファイルから統計データを直接抽出（KTプロパティ解析）"""
        try:
            move_tree = KaTrainSGF.parse_file(path)
            nodes = list(move_tree.nodes_in_tree)

            # メタデータ
            player_black = move_tree.get_property("PB", "Black")
            player_white = move_tree.get_property("PW", "White")
            handicap = int(move_tree.get_property("HA", "0"))
            date = move_tree.get_property("DT", None)
            board_size_prop = move_tree.get_property("SZ", "19")
            try:
                board_size = (int(board_size_prop), int(board_size_prop))
            except:
                board_size = (19, 19)

            # 段級位情報を抽出（Phase 10-C）
            rank_black = move_tree.get_property("BR", None)
            rank_white = move_tree.get_property("WR", None)

            # 統計用カウンター
            stats = {
                "game_name": os.path.basename(path),
                "player_black": player_black,
                "player_white": player_white,
                "rank_black": rank_black,  # Phase 10-C
                "rank_white": rank_white,  # Phase 10-C
                "handicap": handicap,
                "date": date,
                "board_size": board_size,
                "total_moves": 0,
                "total_points_lost": 0.0,
                # Phase 4: プレイヤー別の統計
                "moves_by_player": {"B": 0, "W": 0},
                "loss_by_player": {"B": 0.0, "W": 0.0},
                "mistake_counts": {cat: 0 for cat in eval_metrics.MistakeCategory},
                "mistake_total_loss": {cat: 0.0 for cat in eval_metrics.MistakeCategory},
                "freedom_counts": {diff: 0 for diff in eval_metrics.PositionDifficulty},
                "phase_moves": {"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
                "phase_loss": {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0},
                "phase_mistake_counts": {},  # {(phase, category): count}
                "phase_mistake_loss": {},  # {(phase, category): loss}
                "worst_moves": [],  # (move_number, player, gtp, points_lost, category)
            }

            prev_score = None
            moves_with_kt = 0
            moves_with_analysis = 0
            move_count = 0
            for i, node in enumerate(nodes):
                # 手があるノードのみ処理
                move_prop = node.get_property("B") or node.get_property("W")
                if not move_prop:
                    continue

                move_count += 1
                player = "B" if node.get_property("B") else "W"
                gtp = move_prop

                # KTプロパティから解析データを取得
                analysis = self._extract_analysis_from_sgf_node(node)
                if analysis:
                    moves_with_kt += 1
                if not analysis or "root" not in analysis or not analysis["root"]:
                    continue
                moves_with_analysis += 1

                score = analysis["root"].get("scoreLead")
                if score is None:
                    prev_score = None
                    continue

                # points_lost を計算（親ノードとのスコア差）
                points_lost = None
                if prev_score is not None:
                    player_sign = 1 if player == "B" else -1
                    points_lost = player_sign * (prev_score - score)

                prev_score = score

                # 解析データがある手は全てカウント
                if points_lost is not None:
                    stats["total_moves"] += 1
                    # Phase 4: プレイヤー別にカウント
                    stats["moves_by_player"][player] += 1

                    # 損失は正の値のみ加算
                    if points_lost > 0:
                        stats["total_points_lost"] += points_lost
                        # Phase 4: プレイヤー別に損失を記録
                        stats["loss_by_player"][player] += points_lost

                    # ミス分類（負の損失は"良い手"としてカウント）
                    # canonical loss: 常に >= 0
                    canonical_loss = max(0.0, points_lost)
                    category = eval_metrics.classify_mistake(canonical_loss, None)
                    stats["mistake_counts"][category] += 1
                    stats["mistake_total_loss"][category] += canonical_loss

                    # Freedom（未実装の場合はUNKNOWN）
                    freedom = eval_metrics.PositionDifficulty.UNKNOWN
                    stats["freedom_counts"][freedom] += 1

                    # Phase（簡易版：手数ベース）
                    move_number = i
                    phase = eval_metrics.classify_game_phase(move_number)

                    stats["phase_moves"][phase] += 1
                    if canonical_loss > 0:
                        stats["phase_loss"][phase] += canonical_loss

                    # Phase × Mistake クロス集計（Phase 6.5で追加）
                    key = (phase, category)
                    stats["phase_mistake_counts"][key] = stats["phase_mistake_counts"].get(key, 0) + 1
                    if canonical_loss > 0:
                        stats["phase_mistake_loss"][key] = stats["phase_mistake_loss"].get(key, 0.0) + canonical_loss

                    # Importance を簡易計算（points_lost をベースに）
                    # 本来は delta_score, delta_winrate, swing_bonus を考慮するが、
                    # SGF直接パースではそれらが取れないため、points_lost をそのまま使用
                    importance = max(0, points_lost)

                    # Worst moves記録（損失がある手のみ）
                    if points_lost > 0.5:  # 閾値: 0.5目以上の損失
                        stats["worst_moves"].append((move_number, player, gtp, points_lost, importance, category))

            # Worst movesをソート（損失の大きい順）
            stats["worst_moves"].sort(key=lambda x: x[3], reverse=True)
            stats["worst_moves"] = stats["worst_moves"][:10]  # Top 10

            # Extract reason_tags counts from important moves (Phase 10-B)
            reason_tags_counts = {}
            try:
                # Create a temporary Game object to compute reason_tags
                from katrain.core.game import Game
                temp_game = Game(self, self.engine, move_tree=move_tree)

                # Load analysis data from SGF into Game nodes
                sgf_nodes = list(move_tree.nodes_in_tree)
                game_nodes = list(temp_game.root.nodes_in_tree)

                for sgf_node, game_node in zip(sgf_nodes, game_nodes):
                    # Extract analysis from SGF node
                    analysis = self._extract_analysis_from_sgf_node(sgf_node)
                    if analysis:
                        # Directly set analysis dict (already in correct format)
                        game_node.analysis = analysis

                # Get skill preset for tag threshold calculation (Option 0-B: Problem 3 fix)
                skill_preset = self.config("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET

                # Get important moves with reason_tags
                important_moves = temp_game.get_important_move_evals(level=skill_preset, compute_reason_tags=True)

                # Count reason_tags
                for move_eval in important_moves:
                    for tag in move_eval.reason_tags:
                        reason_tags_counts[tag] = reason_tags_counts.get(tag, 0) + 1

            except Exception as e:
                # If reason_tags computation fails, log but continue
                self.log(f"Failed to compute reason_tags for {path}: {e}", OUTPUT_ERROR)
                import traceback
                self.log(traceback.format_exc(), OUTPUT_ERROR)
                reason_tags_counts = {}

            # Add to stats dict
            stats["reason_tags_counts"] = reason_tags_counts  # {tag: count}

            return stats

        except Exception as e:
            self.log(f"Failed to extract statistics from {path}: {e}", OUTPUT_ERROR)
            import traceback
            self.log(traceback.format_exc(), OUTPUT_ERROR)
            return None

    def _scan_player_names(self, sgf_files: list) -> dict:
        """SGFファイルから全プレイヤー名をスキャン（出現回数付き）"""
        player_counts = {}  # {player_name: count}

        for path in sgf_files:
            try:
                move_tree = KaTrainSGF.parse_file(path)
                player_black = move_tree.get_property("PB", "").strip()
                player_white = move_tree.get_property("PW", "").strip()

                # 空でないプレイヤー名をカウント
                if player_black:
                    player_counts[player_black] = player_counts.get(player_black, 0) + 1
                if player_white:
                    player_counts[player_white] = player_counts.get(player_white, 0) + 1

            except Exception as e:
                self.log(f"Failed to scan {path}: {e}", OUTPUT_ERROR)

        return player_counts

    def _scan_and_show_player_selection(self, sgf_files: list):
        """プレイヤー名をスキャンして選択ダイアログを表示"""
        # mykatrain_settings を取得
        mykatrain_settings = self.config("mykatrain_settings") or {}
        karte_format = mykatrain_settings.get("karte_format", "both")
        default_user = mykatrain_settings.get("default_user_name", "")

        player_counts = self._scan_player_names(sgf_files)

        if not player_counts:
            Clock.schedule_once(
                lambda dt: Popup(
                    title="Error",
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
                    lambda dt: self._process_summary_with_selected_players(sgf_files, [default_user]),
                    0
                )
                return
            else:
                # デフォルトユーザーが見つからない場合は警告して選択ダイアログへ
                Clock.schedule_once(
                    lambda dt: Popup(
                        title="Warning",
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
            lambda dt: self._show_player_selection_dialog(sorted_players, sgf_files),
            0
        )

    def _process_summary_with_selected_players(self, sgf_files: list, selected_players: list):
        """選択されたプレイヤーでサマリー処理を開始"""
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
        import threading
        threading.Thread(
            target=self._process_and_export_summary,
            args=(sgf_files, progress_popup, selected_players),
            daemon=True
        ).start()

    def _show_player_selection_dialog(self, sorted_players: list, sgf_files: list):
        """プレイヤー選択ダイアログを表示"""
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.checkbox import CheckBox
        from kivy.uix.button import Button
        from kivy.uix.scrollview import ScrollView

        # 前回の選択を読み込む
        export_settings = self._load_export_settings()
        last_selected_players = export_settings.get("last_selected_players", [])

        # チェックボックスリスト
        checkbox_dict = {}  # {player_name: CheckBox}

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

        def on_ok(*args):
            selected_players = [name for name, cb in checkbox_dict.items() if cb.active]

            if not selected_players:
                # 警告
                Popup(
                    title="Warning",
                    content=Label(
                        text="Please select at least one player.",
                        halign="center",
                        valign="middle"
                    ),
                    size_hint=(0.4, 0.2),
                ).open()
                return

            selection_popup.dismiss()

            # 選択したプレイヤーを保存
            self._save_export_settings(selected_players=selected_players)

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
            import threading
            threading.Thread(
                target=self._process_and_export_summary,
                args=(sgf_files, progress_popup, selected_players),
                daemon=True
            ).start()

        ok_button = Button(text="OK")
        ok_button.bind(on_release=on_ok)
        button_layout.add_widget(ok_button)

        content_layout.add_widget(button_layout)

        selection_popup = Popup(
            title="Select Players",
            content=content_layout,
            size_hint=(0.6, 0.7),
        )
        selection_popup.open()

    def _process_and_export_summary(self, sgf_paths: list, progress_popup, selected_players: list = None):
        """バックグラウンドでの複数局処理（プレイヤーフィルタリング対応）"""
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
                stats = self._extract_sgf_statistics(path)
                if not stats:
                    self.log(f"Skipping {path}: Failed to extract statistics", OUTPUT_INFO)
                    continue

                # 解析データがほとんどない場合はスキップ
                if stats["total_moves"] < 10:
                    self.log(f"Skipping {path}: Too few analyzed moves ({stats['total_moves']})", OUTPUT_INFO)
                    continue

                # プレイヤーフィルタリング（selected_playersが指定されている場合）
                if selected_players:
                    player_black = stats["player_black"]
                    player_white = stats["player_white"]
                    if player_black not in selected_players and player_white not in selected_players:
                        # どちらのプレイヤーも選択されていない場合はスキップ
                        self.log(f"Skipping {path}: Players not in selection", OUTPUT_INFO)
                        continue

                game_stats_list.append(stats)

            except Exception as e:
                self.log(f"Failed to process {path}: {e}", OUTPUT_ERROR)

        if not game_stats_list:
            # 処理できた対局がない
            Clock.schedule_once(lambda dt: progress_popup.dismiss(), 0)
            Clock.schedule_once(
                lambda dt: Popup(
                    title="Error",
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
                lambda dt: self._save_summaries_per_player(game_stats_list, selected_players, progress_popup),
                0
            )
        else:
            # 1プレイヤーまたは未選択の場合は従来通り
            focus_player = selected_players[0] if selected_players and len(selected_players) == 1 else None
            categorized_games = self._categorize_games_by_stats(game_stats_list, focus_player)

            # 各カテゴリごとにまとめレポート生成
            Clock.schedule_once(
                lambda dt: self._save_categorized_summaries_from_stats(categorized_games, focus_player, progress_popup),
                0
            )

    def _categorize_games_by_stats(self, game_stats_list: list, focus_player: str) -> dict:
        """統計データから対局を分類（互先/置碁）"""
        categories = {
            "even": [],          # 互先
            "handi_weak": [],    # 置碁（下手・黒）
            "handi_strong": [],  # 置碁（上手・白）
        }

        for stats in game_stats_list:
            handicap = stats["handicap"]

            # focus_playerが設定されている場合のみフィルタリング
            if focus_player:
                is_black = (stats["player_black"] == focus_player)
                is_white = (stats["player_white"] == focus_player)

                # focus_playerが対局者でない場合はスキップ
                if not is_black and not is_white:
                    continue

                # 分類
                if handicap == 0:
                    # 互先（黒白統合）
                    categories["even"].append(stats)
                elif handicap >= 2:
                    # 置碁
                    if is_black:
                        categories["handi_weak"].append(stats)  # 下手（黒）
                    else:
                        categories["handi_strong"].append(stats)  # 上手（白）
            else:
                # focus_playerが未設定の場合は全ゲームを分類
                if handicap == 0:
                    categories["even"].append(stats)
                elif handicap >= 2:
                    # ハンデ戦は黒が下手、白が上手
                    # 両方のプレイヤーのゲームを適切なカテゴリに入れる
                    # （後でfocus_playerなしでレポート生成するため）
                    categories["handi_weak"].append(stats)
                    # 注: focus_playerなしの場合、上手/下手を分けるのは困難なため、
                    # 下手（黒）のみを集計する

        return categories

    def _collect_rank_info(self, stats_list: list, focus_player: str) -> str:
        """focus_player の段級位情報を収集（Phase 10-C）

        Args:
            stats_list: 統計dictのリスト
            focus_player: 対象プレイヤー名

        Returns:
            str: 段級位文字列（例: "5段", "8級"）、見つからない場合は None
        """
        if not focus_player:
            return None

        # 全ゲームから focus_player の段級位を探す
        ranks = []
        for stats in stats_list:
            if stats["player_black"] == focus_player and stats.get("rank_black"):
                ranks.append(stats["rank_black"])
            elif stats["player_white"] == focus_player and stats.get("rank_white"):
                ranks.append(stats["rank_white"])

        # 最も頻出する段級位を返す（複数ある場合は最初のもの）
        if ranks:
            from collections import Counter
            most_common = Counter(ranks).most_common(1)[0][0]
            return most_common

        return None

    def _build_summary_from_stats(self, stats_list: list, focus_player: str = None) -> str:
        """統計dictリストからsummaryテキストを生成"""
        if not stats_list:
            return "# Multi-Game Summary\n\nNo games provided."

        # 集計
        total_games = len(stats_list)
        total_moves = sum(s["total_moves"] for s in stats_list)
        total_loss = sum(s["total_points_lost"] for s in stats_list)
        avg_loss = total_loss / total_moves if total_moves > 0 else 0.0

        # ミス分類の集計
        mistake_totals = {cat: 0 for cat in eval_metrics.MistakeCategory}
        mistake_loss_totals = {cat: 0.0 for cat in eval_metrics.MistakeCategory}
        for stats in stats_list:
            for cat, count in stats["mistake_counts"].items():
                mistake_totals[cat] += count
            for cat, loss in stats.get("mistake_total_loss", {}).items():
                mistake_loss_totals[cat] += loss

        # Freedom の集計
        freedom_totals = {diff: 0 for diff in eval_metrics.PositionDifficulty}
        for stats in stats_list:
            for diff, count in stats["freedom_counts"].items():
                freedom_totals[diff] += count

        # Phase の集計
        phase_moves_total = {"opening": 0, "middle": 0, "yose": 0, "unknown": 0}
        phase_loss_total = {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0}
        for stats in stats_list:
            for phase in phase_moves_total:
                phase_moves_total[phase] += stats["phase_moves"][phase]
                phase_loss_total[phase] += stats["phase_loss"][phase]

        # Phase × Mistake クロス集計（Phase 6.5で追加）
        phase_mistake_counts_total = {}
        phase_mistake_loss_total = {}
        for stats in stats_list:
            for key, count in stats.get("phase_mistake_counts", {}).items():
                phase_mistake_counts_total[key] = phase_mistake_counts_total.get(key, 0) + count
            for key, loss in stats.get("phase_mistake_loss", {}).items():
                phase_mistake_loss_total[key] = phase_mistake_loss_total.get(key, 0.0) + loss

        # Aggregate reason_tags counts (Phase 10-B)
        reason_tags_totals = {}
        for stats in stats_list:
            for tag, count in stats.get("reason_tags_counts", {}).items():
                reason_tags_totals[tag] = reason_tags_totals.get(tag, 0) + count

        # Worst moves の集計
        all_worst_moves = []
        for stats in stats_list:
            game_name = stats["game_name"]
            for move_num, player, gtp, loss, importance, cat in stats["worst_moves"]:
                all_worst_moves.append((game_name, move_num, player, gtp, loss, importance, cat))
        all_worst_moves.sort(key=lambda x: x[5], reverse=True)  # importance でソート
        all_worst_moves = all_worst_moves[:10]

        # 日付範囲
        dates = [s["date"] for s in stats_list if s["date"]]
        date_range = f"{min(dates)} to {max(dates)}" if dates else "Unknown"

        # 段級位情報を収集（Phase 10-C）
        rank_info = self._collect_rank_info(stats_list, focus_player)

        # Markdown生成
        lines = ["# Multi-Game Summary\n"]
        lines.append("## Meta")
        lines.append(f"- Games analyzed: {total_games}")
        if focus_player:
            lines.append(f"- Focus player: {focus_player}")
            if rank_info:
                lines.append(f"- Rank: {rank_info}")
        lines.append(f"- Date range: {date_range}")
        # Removed: Generated timestamp (not needed for LLM)
        lines.append("")

        # Phase 4: 相手情報セクション（動的詳細度調整）
        if focus_player:
            opponent_info_mode = (self.config("mykatrain_settings") or {}).get("opponent_info_mode", "auto")
            # 自動モードの場合、対局数で詳細度を決定
            if opponent_info_mode == "auto":
                show_individual = total_games <= 5
            elif opponent_info_mode == "always_detailed":
                show_individual = True
            else:  # always_aggregate
                show_individual = False

            if show_individual and total_games >= 1:
                # 個別対局テーブル（5局以下）
                lines.append("## Individual Game Overview")
                lines.append("")
                lines.append("| Game | Opponent | Result | My Loss | Opp Loss | Ratio |")
                lines.append("|------|----------|--------|---------|----------|-------|")
                for s in stats_list:
                    game_short = s["game_name"][:20] + "..." if len(s["game_name"]) > 23 else s["game_name"]
                    # focus_player が黒か白かを判定
                    if s["player_black"] == focus_player:
                        my_color = "B"
                        opp_name = s["player_white"]
                        my_loss = s.get("loss_by_player", {}).get("B", 0.0)
                        opp_loss = s.get("loss_by_player", {}).get("W", 0.0)
                    else:
                        my_color = "W"
                        opp_name = s["player_black"]
                        my_loss = s.get("loss_by_player", {}).get("W", 0.0)
                        opp_loss = s.get("loss_by_player", {}).get("B", 0.0)
                    # 結果判定（損失が少ない方が勝ち傾向）
                    ratio = my_loss / opp_loss if opp_loss > 0 else 0.0
                    result = "Win?" if ratio < 0.8 else ("Loss?" if ratio > 1.2 else "Close")
                    lines.append(f"| {game_short} | {opp_name[:15]} | {result} | {my_loss:.1f} | {opp_loss:.1f} | {ratio:.2f} |")
                lines.append("")
            elif total_games > 1:
                # 集計情報のみ（6局以上）
                lines.append("## Opponent Statistics (Aggregate)")
                # 対戦相手をカウント
                opponents = set()
                total_opp_loss = 0.0
                total_my_loss = 0.0
                for s in stats_list:
                    if s["player_black"] == focus_player:
                        opponents.add(s["player_white"])
                        total_my_loss += s.get("loss_by_player", {}).get("B", 0.0)
                        total_opp_loss += s.get("loss_by_player", {}).get("W", 0.0)
                    else:
                        opponents.add(s["player_black"])
                        total_my_loss += s.get("loss_by_player", {}).get("W", 0.0)
                        total_opp_loss += s.get("loss_by_player", {}).get("B", 0.0)
                avg_opp_loss = total_opp_loss / total_games if total_games > 0 else 0.0
                avg_my_loss = total_my_loss / total_games if total_games > 0 else 0.0
                loss_ratio = avg_my_loss / avg_opp_loss if avg_opp_loss > 0 else 0.0
                lines.append(f"- Opponents faced: {len(opponents)}")
                lines.append(f"- Average opponent loss per game: {avg_opp_loss:.1f}")
                lines.append(f"- Average my loss per game: {avg_my_loss:.1f}")
                lines.append(f"- Loss ratio (me/opponent): {loss_ratio:.2f}")
                lines.append("")

        lines.append("## Overall Statistics" + (f" ({focus_player})" if focus_player else ""))
        lines.append(f"- Total games: {total_games}")
        lines.append(f"- Total moves analyzed: {total_moves}")
        lines.append(f"- Total points lost: {total_loss:.1f}")
        lines.append(f"- Average points lost per move: {avg_loss:.2f}\n")

        lines.append("## Mistake Distribution" + (f" ({focus_player})" if focus_player else ""))
        lines.append("| Category | Count | Percentage | Avg Loss |")
        lines.append("|----------|-------|------------|----------|")
        cat_names = {"GOOD": "Good", "INACCURACY": "Inaccuracy", "MISTAKE": "Mistake", "BLUNDER": "Blunder"}
        for cat in eval_metrics.MistakeCategory:
            count = mistake_totals[cat]
            pct = (count / total_moves * 100) if total_moves > 0 else 0
            # Avg Loss = そのカテゴリの損失合計 ÷ そのカテゴリの手数
            cat_loss = mistake_loss_totals.get(cat, 0.0)
            avg = cat_loss / count if count > 0 else 0.0
            lines.append(f"| {cat_names.get(cat.name, cat.name)} | {count} | {pct:.1f}% | {avg:.2f} |")
        lines.append("")

        # Freedom Distribution: Only include if non-UNKNOWN values exist
        # (Phase 8: LLM optimization - skip if 100% UNKNOWN)
        has_real_freedom_data = any(
            count > 0 for diff, count in freedom_totals.items()
            if diff != eval_metrics.PositionDifficulty.UNKNOWN
        )

        if has_real_freedom_data:
            lines.append("## Freedom Distribution" + (f" ({focus_player})" if focus_player else ""))
            lines.append("| Difficulty | Count | Percentage |")
            lines.append("|------------|-------|------------|")
            diff_names = {"EASY": "Easy (wide)", "NORMAL": "Normal", "HARD": "Hard (narrow)", "ONLY_MOVE": "Only move"}
            for diff in eval_metrics.PositionDifficulty:
                if diff == eval_metrics.PositionDifficulty.UNKNOWN:
                    continue  # Skip UNKNOWN rows
                count = freedom_totals[diff]
                pct = (count / total_moves * 100) if total_moves > 0 else 0
                lines.append(f"| {diff_names.get(diff.name, diff.name)} | {count} | {pct:.1f}% |")
            lines.append("")
        # If no real data, section is omitted entirely (saves ~150 tokens)

        # Phase Breakdown: REMOVED (Phase 8: LLM optimization)
        # Rationale: This section is fully superseded by "Phase × Mistake Breakdown" below,
        # which contains all the same information (moves, loss per phase) plus mistake
        # category breakdowns. Keeping both is 100% redundant for LLM consumption.
        # The cross-tabulation provides strictly more information value.

        # Phase × Mistake クロス集計テーブル（Phase 6.5で追加）
        phase_names = {"opening": "Opening", "middle": "Middle game", "yose": "Endgame", "unknown": "Unknown"}
        lines.append("## Phase × Mistake Breakdown" + (f" ({focus_player})" if focus_player else ""))
        lines.append("| Phase | Good | Inaccuracy | Mistake | Blunder | Total Loss |")
        lines.append("|-------|------|------------|---------|---------|------------|")
        for phase in ["opening", "middle", "yose"]:
            row = [phase_names[phase]]
            total_phase_loss = 0.0
            for cat in eval_metrics.MistakeCategory:
                key = (phase, cat)
                count = phase_mistake_counts_total.get(key, 0)
                loss = phase_mistake_loss_total.get(key, 0.0)
                if count > 0 and cat != eval_metrics.MistakeCategory.GOOD:
                    total_phase_loss += loss
                    row.append(f"{count} ({loss:.1f})")
                else:
                    row.append(f"{count}")
            row.append(f"{total_phase_loss:.1f}")
            lines.append(f"| {' | '.join(row)} |")
        lines.append("")

        # Reason Tags Distribution (Phase 10-B)
        if reason_tags_totals:  # Only show if tags exist
            focus_suffix = f" ({focus_player})" if focus_player else ""
            lines.append(f"## ミス理由タグ分布{focus_suffix}")
            lines.append("")

            # Sort by count descending
            sorted_tags = sorted(
                reason_tags_totals.items(),
                key=lambda x: x[1],
                reverse=True
            )

            for tag, count in sorted_tags:
                label = eval_metrics.REASON_TAG_LABELS.get(tag, tag)
                lines.append(f"- {label}: {count} 回")

            lines.append("")

            # Phase 13: 棋力推定
            # 重要局面総数を計算（reason_tagsを持つ手の数）
            total_important = sum(
                sum(stats.get("reason_tags_counts", {}).values())
                for stats in stats_list
            )
            if total_important >= 5:
                estimation = eval_metrics.estimate_skill_level_from_tags(
                    reason_tags_totals,
                    total_important
                )

                level_labels = {
                    "beginner": "初級〜中級（G0-G1相当）",
                    "standard": "有段者（G2-G3相当）",
                    "advanced": "高段者（G4相当）",
                    "unknown": "不明"
                }

                lines.append(f"## 推定棋力{focus_suffix}")
                lines.append("")
                lines.append(f"- **レベル**: {level_labels.get(estimation.estimated_level, estimation.estimated_level)}")
                lines.append(f"- **確度**: {estimation.confidence:.0%}")
                lines.append(f"- **理由**: {estimation.reason}")

                # プリセット推奨（Phase 14）
                preset_recommendations = {
                    "beginner": "beginner（緩め：5目以上を大悪手判定）",
                    "standard": "standard（標準：2目以上を悪手判定）",
                    "advanced": "advanced（厳しめ：1目以上を悪手判定）"
                }
                if estimation.estimated_level in preset_recommendations:
                    lines.append(f"- **推奨プリセット**: {preset_recommendations[estimation.estimated_level]}")

                lines.append("")

        lines.append("## Top Worst Moves" + (f" ({focus_player})" if focus_player else ""))

        if all_worst_moves:
            # 急場見逃しパターンを検出（全worst_movesから、Top10だけでなく）
            # all_worst_movesを[(game, move_num, player, gtp, loss, importance, cat), ...]から
            # Game._detect_urgent_miss_sequencesが期待する[(game_name, move_like_obj), ...]形式に変換

            # 仮のmoveオブジェクトを作成（必要な属性のみ）
            class TempMove:
                def __init__(self, move_num, player, gtp, loss, importance):
                    self.move_number = move_num
                    self.player = player
                    self.gtp = gtp
                    self.points_lost = loss
                    self.score_loss = loss
                    self.importance = importance

            moves_for_detection = [(game_name, TempMove(move_num, player, gtp, loss, importance))
                                   for game_name, move_num, player, gtp, loss, importance, cat in all_worst_moves]

            # 急場見逃しパターンを検出
            from katrain.core.game import Game

            # 棋力設定から閾値を取得
            skill_preset = self.config("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET
            urgent_config = eval_metrics.get_urgent_miss_config(skill_preset)

            sequences, filtered_moves = Game._detect_urgent_miss_sequences(
                moves_for_detection,
                threshold_loss=urgent_config.threshold_loss,
                min_consecutive=urgent_config.min_consecutive
            )

            # 急場見逃しパターンがあれば表示
            if sequences:
                lines.append("")
                lines.append("**注意**: 以下の区間は双方が急場を見逃した可能性があります（損失20目超が3手以上連続）")
                lines.append("| Game | 手数範囲 | 連続 | 総損失 | 平均損失/手 |")
                lines.append("|------|---------|------|--------|------------|")

                for seq in sequences:
                    short_game = seq['game'][:20] + "..." if len(seq['game']) > 23 else seq['game']
                    avg_loss = seq['total_loss'] / seq['count']
                    lines.append(
                        f"| {short_game} | #{seq['start']}-{seq['end']} | "
                        f"{seq['count']}手 | {seq['total_loss']:.1f}目 | {avg_loss:.1f}目 |"
                    )
                lines.append("")

            # 通常のワースト手を表示
            if filtered_moves:
                # filtered_movesをソートしてTop 10を取得
                filtered_moves.sort(key=lambda x: x[1].points_lost or x[1].score_loss or 0, reverse=True)
                display_moves = filtered_moves[:10]

                if sequences:
                    lines.append("通常のワースト手（損失20目以下 or 単発）:")
                lines.append("| Game | # | P | Coord | Loss | Importance | Category |")
                lines.append("|------|---|---|-------|------|------------|----------|")

                for game_name, temp_move in display_moves:
                    # 座標変換（SGF座標→GTP座標）
                    coord = temp_move.gtp or '-'
                    # move.gtp が2文字の小文字アルファベット（SGF座標）の場合、変換
                    if coord and len(coord) == 2 and coord.isalpha() and coord.islower():
                        coord = Game._convert_sgf_to_gtp_coord(coord, 19)

                    # 元のall_worst_movesからcategoryを取得
                    cat_name = "UNKNOWN"
                    for gn, mn, pl, gt, ls, imp, ct in all_worst_moves:
                        if gn == game_name and mn == temp_move.move_number:
                            cat_name = ct.name
                            break

                    lines.append(f"| {game_name[:20]} | {temp_move.move_number} | {temp_move.player} | {coord} | {temp_move.points_lost:.1f} | {temp_move.importance:.1f} | {cat_name} |")
            elif sequences:
                lines.append("通常のワースト手: なし（すべて急場見逃しパターン）")
            else:
                # sequencesもfiltered_movesもない場合は元のall_worst_movesを表示
                lines.append("| Game | # | P | Coord | Loss | Importance | Category |")
                lines.append("|------|---|---|-------|------|------------|----------|")
                for game_name, move_num, player, gtp, loss, importance, cat in all_worst_moves:
                    # 座標変換
                    coord = gtp or '-'
                    if coord and len(coord) == 2 and coord.isalpha() and coord.islower():
                        coord = Game._convert_sgf_to_gtp_coord(coord, 19)
                    lines.append(f"| {game_name[:20]} | {move_num} | {player} | {coord} | {loss:.1f} | {importance:.1f} | {cat.name} |")
        else:
            lines.append("- No significant mistakes found.")
        lines.append("")

        # 弱点仮説セクション（Phase 7で追加）
        lines.append("## Weakness Hypothesis" + (f" ({focus_player})" if focus_player else ""))
        lines.append("\nBased on cross-tabulation analysis:\n")

        hypotheses = []
        cat_names_ja = {
            eval_metrics.MistakeCategory.BLUNDER: "大悪手",
            eval_metrics.MistakeCategory.MISTAKE: "悪手",
            eval_metrics.MistakeCategory.INACCURACY: "軽微なミス",
        }

        # クロス集計から上位3つの弱点を抽出
        if phase_mistake_loss_total:
            # 損失が大きい順にソート（GOOD は除外）
            sorted_combos = sorted(
                [(k, v) for k, v in phase_mistake_loss_total.items() if k[1] in cat_names_ja and v > 0],
                key=lambda x: x[1],
                reverse=True
            )

            for i, (key, loss) in enumerate(sorted_combos[:3]):
                phase, category = key
                count = phase_mistake_counts_total.get(key, 0)
                hypotheses.append(
                    f"{i+1}. **{phase_names.get(phase, phase)}の{cat_names_ja[category]}** "
                    f"({count}回、損失{loss:.1f}目)"
                )

        if hypotheses:
            lines.extend(hypotheses)
            lines.append("")
            lines.append("**分析**:")
            # 最悪の組み合わせについて簡単な分析を追加
            if sorted_combos:
                worst_phase, worst_cat = sorted_combos[0][0]
                worst_loss = sorted_combos[0][1]
                worst_count = phase_mistake_counts_total.get((worst_phase, worst_cat), 0)

                # 損失の割合を計算
                phase_total_loss = phase_loss_total.get(worst_phase, 0)
                if phase_total_loss > 0:
                    pct = (worst_loss / phase_total_loss) * 100
                    lines.append(
                        f"- {phase_names.get(worst_phase, worst_phase)}の損失の{pct:.1f}%が"
                        f"{cat_names_ja[worst_cat]}によるもの"
                    )

                # 頻度の分析
                phase_total_moves = phase_moves_total.get(worst_phase, 0)
                if phase_total_moves > 0:
                    freq_pct = (worst_count / phase_total_moves) * 100
                    lines.append(
                        f"- {phase_names.get(worst_phase, worst_phase)}の{freq_pct:.1f}%の手が"
                        f"{cat_names_ja[worst_cat]}と判定されている"
                    )
        else:
            lines.append("- 明確な弱点パターンは検出されませんでした。")

        # 急場見逃しパターンがあれば追加
        if all_worst_moves:
            # sequencesは既に計算済み（Top Worst Movesセクションで）
            from katrain.core.game import Game
            class TempMove:
                def __init__(self, move_num, player, gtp, loss, importance):
                    self.move_number = move_num
                    self.player = player
                    self.gtp = gtp
                    self.points_lost = loss
                    self.score_loss = loss
                    self.importance = importance

            moves_for_detection = [(game_name, TempMove(move_num, player, gtp, loss, importance))
                                   for game_name, move_num, player, gtp, loss, importance, cat in all_worst_moves]

            # 棋力設定から閾値を取得（Top Worst Movesと同じ設定を使用）
            skill_preset = self.config("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET
            urgent_config = eval_metrics.get_urgent_miss_config(skill_preset)

            sequences, _ = Game._detect_urgent_miss_sequences(
                moves_for_detection,
                threshold_loss=urgent_config.threshold_loss,
                min_consecutive=urgent_config.min_consecutive
            )

            if sequences:
                lines.append("")
                lines.append("**急場見逃しパターン**:")
                for seq in sequences:
                    short_game = seq['game'][:20] + "..." if len(seq['game']) > 23 else seq['game']
                    avg_loss = seq['total_loss'] / seq['count']
                    lines.append(
                        f"- {short_game} #{seq['start']}-{seq['end']}: "
                        f"{seq['count']}手連続、総損失{seq['total_loss']:.1f}目（平均{avg_loss:.1f}目/手）"
                    )

                lines.append("")
                lines.append("**推奨アプローチ**:")
                lines.append("- 詰碁（死活）訓練で読みの精度向上")
                lines.append("- 対局中、戦いの前に「自分の石は安全か？」「相手の弱点はどこか？」を確認")
                lines.append("- 急場見逃し区間のSGFを重点的に復習")

        lines.append("")

        lines.append("## Practice Priorities" + (f" ({focus_player})" if focus_player else ""))
        lines.append("\nBased on the data above, consider focusing on:\n")

        # Practice Priorities は弱点仮説の上位1-2個を簡潔に提示
        priorities = []
        if hypotheses:
            # 上位2つを抽出
            for hyp in hypotheses[:2]:
                priorities.append(f"- {hyp}")

        # フォールバック: 上記で見つからなければ、最も損失が大きいphaseを提案
        if not priorities and total_moves > 0:
            worst_phase = max(phase_loss_total.items(), key=lambda x: x[1])
            if worst_phase[1] > 0:
                priorities.append(f"- Improve {phase_names[worst_phase[0]]} play ({worst_phase[1]:.1f} points lost)")

        if priorities:
            lines.extend(priorities)
        else:
            lines.append("- No specific priorities identified. Keep up the good work!")

        return "\n".join(lines)

    def _save_summaries_per_player(self, game_stats_list: list, selected_players: list, progress_popup):
        """各プレイヤーごとに別ファイルでサマリーを保存"""
        progress_popup.dismiss()

        saved_files = []
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")

        # mykatrain_settings の karte_output_directory を優先、なければ従来のパス
        mykatrain_settings = self.config("mykatrain_settings") or {}
        output_dir = mykatrain_settings.get("karte_output_directory", "")
        if not output_dir or not os.path.isdir(output_dir):
            output_dir = os.path.join(os.path.expanduser(self.config("general/sgf_save") or "."), "reports")
        os.makedirs(output_dir, exist_ok=True)

        for player_name in selected_players:
            try:
                # このプレイヤーが参加しているゲームのみフィルタ
                player_games = [
                    stats for stats in game_stats_list
                    if stats["player_black"] == player_name or stats["player_white"] == player_name
                ]

                if len(player_games) < 2:
                    self.log(f"Skipping {player_name}: Not enough games ({len(player_games)})", OUTPUT_INFO)
                    continue

                # ゲームを分類（互先/置碁）
                categorized_games = self._categorize_games_by_stats(player_games, player_name)

                # 各カテゴリごとにファイル出力
                category_labels = {
                    "even": "互先",
                    "handi_weak": "置碁下手",
                    "handi_strong": "置碁上手",
                }

                for category, games in categorized_games.items():
                    if len(games) < 2:
                        continue

                    summary_text = self._build_summary_from_stats(games, player_name)

                    # ファイル名にプレイヤー名を含める
                    label = category_labels[category]
                    # プレイヤー名のサニタイズ
                    safe_player_name = re.sub(r'[<>:"/\\|?*]', '_', player_name)[:30]
                    filename = f"summary_{safe_player_name}_{label}_{timestamp}.md"
                    full_path = os.path.join(output_dir, filename)

                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(summary_text)

                    saved_files.append(full_path)
                    self.log(f"Summary saved: {full_path}", OUTPUT_INFO)

            except Exception as exc:
                self.log(f"Failed to save summary for {player_name}: {exc}", OUTPUT_ERROR)

        # 結果ポップアップ
        if saved_files:
            files_text = "\n".join([os.path.basename(f) for f in saved_files])
            Popup(
                title=i18n._("Summaries exported"),
                content=Label(
                    text=f"Saved {len(saved_files)} summary file(s):\n\n{files_text}",
                    halign="center",
                    valign="middle",
                    font_name=Theme.DEFAULT_FONT,
                ),
                size_hint=(0.6, 0.5),
            ).open()
            self.controls.set_status(f"{len(saved_files)} summaries exported", STATUS_INFO, check_level=False)
        else:
            Popup(
                title=i18n._("No summaries generated"),
                content=Label(
                    text="No players had enough games (need 2+ per category).",
                    halign="center",
                    valign="middle",
                    font_name=Theme.DEFAULT_FONT,
                ),
                size_hint=(0.5, 0.3),
            ).open()

    def _save_categorized_summaries_from_stats(self, categorized_games: dict, player_name: str, progress_popup):
        """カテゴリごとにsummary.mdを保存"""
        progress_popup.dismiss()

        category_labels = {
            "even": "互先",
            "handi_weak": "置碁下手",
            "handi_strong": "置碁上手",
        }

        saved_files = []
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")

        # mykatrain_settings の karte_output_directory を優先、なければ従来のパス
        mykatrain_settings = self.config("mykatrain_settings") or {}
        output_dir = mykatrain_settings.get("karte_output_directory", "")
        if not output_dir or not os.path.isdir(output_dir):
            # フォールバック: general/sgf_save/reports/
            output_dir = os.path.join(os.path.expanduser(self.config("general/sgf_save") or "."), "reports")
        os.makedirs(output_dir, exist_ok=True)

        for category, games in categorized_games.items():
            if len(games) < 2:
                # 2局未満はスキップ
                continue

            try:
                # 統計dictから直接まとめレポート生成
                summary_text = self._build_summary_from_stats(games, player_name)

                # ファイル名
                label = category_labels[category]
                filename = f"summary_{label}_{timestamp}.md"
                full_path = os.path.join(output_dir, filename)

                # 保存
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(summary_text)

                saved_files.append(full_path)
                self.log(f"Summary saved: {full_path}", OUTPUT_INFO)

            except Exception as exc:
                self.log(f"Failed to save summary for {category}: {exc}", OUTPUT_ERROR)

        # 結果ポップアップ
        if saved_files:
            files_text = "\n".join([os.path.basename(f) for f in saved_files])
            Popup(
                title="Summaries exported",
                content=Label(
                    text=f"Saved {len(saved_files)} summary file(s):\n\n{files_text}",
                    halign="center",
                    valign="middle"
                ),
                size_hint=(0.6, 0.5),
            ).open()
            self.controls.set_status(f"{len(saved_files)} summaries exported", STATUS_INFO, check_level=False)
        else:
            Popup(
                title="No summaries generated",
                content=Label(
                    text="No categories had enough games (need 2+).\nCheck that focus_player matches SGF player names.",
                    halign="center",
                    valign="middle"
                ),
                size_hint=(0.5, 0.3),
            ).open()

    def _save_summary_file(self, summary_text: str, player_name: str, progress_popup):
        """まとめファイルを保存"""
        progress_popup.dismiss()

        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        filename = f"summary_{player_name or 'all'}_{timestamp}.md"

        # reports/ ディレクトリに保存
        default_path = os.path.join(os.path.expanduser(self.config("general/sgf_save") or "."), "reports")
        os.makedirs(default_path, exist_ok=True)
        full_path = os.path.join(default_path, filename)

        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(summary_text)

            # クリップボードにコピー
            try:
                Clipboard.copy(summary_text)
            except Exception as exc:
                self.log(f"Clipboard copy failed: {exc}", OUTPUT_DEBUG)

            self.controls.set_status(f"Summary exported to {full_path}", STATUS_INFO, check_level=False)
            Popup(
                title="Summary exported",
                content=Label(text=f"Saved to:\n{full_path}", halign="center", valign="middle"),
                size_hint=(0.5, 0.3),
            ).open()
        except Exception as exc:
            self.log(f"Failed to export Summary to {full_path}: {exc}", OUTPUT_ERROR)
            Popup(
                title="Error",
                content=Label(text=f"Failed to save:\n{exc}", halign="center", valign="middle"),
                size_hint=(0.5, 0.3),
            ).open()

    def _do_quiz_popup(self):
        if not self.game:
            return

        # Use QuizConfig so we can add presets later.
        cfg = getattr(eval_metrics, "QUIZ_CONFIG_DEFAULT", None)
        if cfg is None:
            # Fallback for safety.
            loss_threshold = eval_metrics.DEFAULT_QUIZ_LOSS_THRESHOLD
            limit = eval_metrics.DEFAULT_QUIZ_ITEM_LIMIT
        else:
            loss_threshold = cfg.loss_threshold
            limit = cfg.limit

        quiz_items = self.game.get_quiz_items(
            loss_threshold=loss_threshold, limit=limit
        )

        popup_content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))

        if quiz_items:
            header_text = i18n._(
                "Review the worst moves on the main line.\n"
                "Showing up to {limit} moves with loss > {loss:.1f} points.\n"
                "Click a row to jump to the position before the move."
            ).format(limit=limit, loss=loss_threshold)
        else:
            header_text = i18n._(
                "No moves with loss greater than {loss:.1f} points were found on the main line."
            ).format(loss=loss_threshold)

        header_label = Label(
            text=header_text,
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(70),
            color=Theme.TEXT_COLOR,
        )
        header_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, None)))
        popup_content.add_widget(header_label)

        scroll = ScrollView(size_hint=(1, 1))
        items_layout = BoxLayout(
            orientation="vertical",
            spacing=dp(6),
            size_hint_y=None,
        )
        items_layout.bind(minimum_height=items_layout.setter("height"))

        def jump_to_move(move_number: int) -> None:
            node = self.game.get_main_branch_node_before_move(move_number)
            if node is None:
                self.controls.set_status(
                    f"Could not navigate to move {move_number}.", STATUS_INFO
                )
                return
            self.game.set_current_node(node)
            self.update_state(redraw_board=True)

        for item in quiz_items:
            color_label = "Black" if item.player == "B" else "White" if item.player == "W" else "?"
            btn = Button(
                text=f"Move {item.move_number} ({color_label}), loss: {item.loss:.1f} points",
                size_hint_y=None,
                height=dp(44),
                background_color=Theme.BOX_BACKGROUND_COLOR,
                color=Theme.TEXT_COLOR,
            )
            btn.bind(on_release=lambda _btn, mv=item.move_number: jump_to_move(mv))
            items_layout.add_widget(btn)

        scroll.add_widget(items_layout)
        popup_content.add_widget(scroll)

        buttons_layout = BoxLayout(
            orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48)
        )
        start_button = Button(
            text=i18n._("Start quiz"),
            size_hint=(0.5, None),
            height=dp(48),
            disabled=not quiz_items,
            background_color=Theme.LIGHTER_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        close_button = Button(
            text=i18n._("Close"),
            size_hint=(0.5, None),
            height=dp(48),
            background_color=Theme.LIGHTER_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        buttons_layout.add_widget(start_button)
        buttons_layout.add_widget(close_button)
        popup_content.add_widget(buttons_layout)

        popup = I18NPopup(
            title_key="Generate quiz (beta)",
            size=[dp(520), dp(620)],
            content=popup_content,
        ).__self__
        # 右下の分析パネルを残すため、右上に寄せて高さを抑える
        popup.size_hint = (0.38, 0.55)
        popup.pos_hint = {"right": 0.99, "top": 0.99}
        close_button.bind(on_release=lambda *_args: popup.dismiss())

        def start_quiz(*_args):
            popup.dismiss()
            self._start_quiz_session(quiz_items)

        start_button.bind(on_release=start_quiz)
        popup.open()

    def _do_mykatrain_settings_popup(self):
        """Show myKatrain settings dialog (Phase 3)"""
        from kivy.uix.textinput import TextInput
        from kivy.uix.checkbox import CheckBox
        from katrain.core import eval_metrics

        current_settings = self.config("mykatrain_settings") or {}

        from kivy.uix.scrollview import ScrollView

        # ScrollView でコンテンツをスクロール可能に
        scroll_view = ScrollView(size_hint=(1, 1))
        popup_content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12), size_hint_y=None)
        popup_content.bind(minimum_height=popup_content.setter('height'))

        # Skill Preset (Radio buttons)
        skill_label = Label(
            text=i18n._("mykatrain:settings:skill_preset"),
            size_hint_y=None,
            height=dp(25),
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        skill_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        popup_content.add_widget(skill_label)

        current_skill_preset = self.config("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET
        selected_skill_preset = [current_skill_preset]

        skill_options = [
            ("beginner", i18n._("mykatrain:settings:skill_beginner")),
            ("standard", i18n._("mykatrain:settings:skill_standard")),
            ("advanced", i18n._("mykatrain:settings:skill_advanced")),
        ]

        skill_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(5))
        for skill_value, skill_label_text in skill_options:
            checkbox = CheckBox(
                group="skill_preset_setting",
                active=(skill_value == current_skill_preset),
                size_hint_x=None,
                width=dp(30),
            )
            checkbox.bind(
                active=lambda chk, active, val=skill_value: selected_skill_preset.__setitem__(0, val) if active else None
            )
            label = Label(
                text=skill_label_text,
                size_hint_x=None,
                width=dp(100),
                halign="left",
                valign="middle",
                color=Theme.TEXT_COLOR,
                font_name=Theme.DEFAULT_FONT,
            )
            label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
            skill_layout.add_widget(checkbox)
            skill_layout.add_widget(label)
        popup_content.add_widget(skill_layout)

        # Default User Name
        user_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
        user_label = Label(
            text=i18n._("mykatrain:settings:default_user_name"),
            size_hint_x=0.35,
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        user_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        user_input = TextInput(
            text=current_settings.get("default_user_name", ""),
            multiline=False,
            size_hint_x=0.65,
            font_name=Theme.DEFAULT_FONT,
        )
        user_row.add_widget(user_label)
        user_row.add_widget(user_input)
        popup_content.add_widget(user_row)

        # Karte Output Directory
        output_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
        output_label = Label(
            text=i18n._("mykatrain:settings:karte_output_directory"),
            size_hint_x=0.35,
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        output_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        output_input = TextInput(
            text=current_settings.get("karte_output_directory", ""),
            multiline=False,
            size_hint_x=0.5,
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
        popup_content.add_widget(output_row)

        # Batch Export Input Directory
        input_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))
        input_label = Label(
            text=i18n._("mykatrain:settings:batch_export_input_directory"),
            size_hint_x=0.35,
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        input_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        input_input = TextInput(
            text=current_settings.get("batch_export_input_directory", ""),
            multiline=False,
            size_hint_x=0.5,
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
        popup_content.add_widget(input_row)

        # Karte Format (Radio buttons - 2x2 grid)
        format_label = Label(
            text=i18n._("mykatrain:settings:karte_format"),
            size_hint_y=None,
            height=dp(25),
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        format_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        popup_content.add_widget(format_label)

        from kivy.uix.gridlayout import GridLayout

        format_layout = GridLayout(cols=2, spacing=dp(5), size_hint_y=None, height=dp(80))
        format_options = [
            ("both", i18n._("mykatrain:settings:format_both")),
            ("black_only", i18n._("mykatrain:settings:format_black_only")),
            ("white_only", i18n._("mykatrain:settings:format_white_only")),
            ("default_user_only", i18n._("mykatrain:settings:format_default_user_only")),
        ]

        current_format = current_settings.get("karte_format", "both")
        selected_format = [current_format]

        for format_value, format_label_text in format_options:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36))
            checkbox = CheckBox(
                group="karte_format",
                active=(format_value == current_format),
                size_hint_x=None,
                width=dp(30),
            )
            checkbox.bind(
                active=lambda chk, active, val=format_value: selected_format.__setitem__(0, val) if active else None
            )
            label = Label(
                text=format_label_text,
                halign="left",
                valign="middle",
                color=Theme.TEXT_COLOR,
                font_name=Theme.DEFAULT_FONT,
            )
            label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
            row.add_widget(checkbox)
            row.add_widget(label)
            format_layout.add_widget(row)

        popup_content.add_widget(format_layout)

        # Opponent Info Mode (Radio buttons - 2x2 grid) - Phase 4
        opp_info_label = Label(
            text=i18n._("mykatrain:settings:opponent_info_mode"),
            size_hint_y=None,
            height=dp(25),
            halign="left",
            valign="middle",
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
        )
        opp_info_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        popup_content.add_widget(opp_info_label)

        opp_info_layout = GridLayout(cols=2, spacing=dp(5), size_hint_y=None, height=dp(80))
        opp_info_options = [
            ("auto", i18n._("mykatrain:settings:opponent_info_auto")),
            ("always_detailed", i18n._("mykatrain:settings:opponent_info_detailed")),
            ("always_aggregate", i18n._("mykatrain:settings:opponent_info_aggregate")),
        ]

        current_opp_info = current_settings.get("opponent_info_mode", "auto")
        selected_opp_info = [current_opp_info]

        for opp_value, opp_label_text in opp_info_options:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36))
            checkbox = CheckBox(
                group="opponent_info_mode",
                active=(opp_value == current_opp_info),
                size_hint_x=None,
                width=dp(30),
            )
            checkbox.bind(
                active=lambda chk, active, val=opp_value: selected_opp_info.__setitem__(0, val) if active else None
            )
            label = Label(
                text=opp_label_text,
                halign="left",
                valign="middle",
                color=Theme.TEXT_COLOR,
                font_name=Theme.DEFAULT_FONT,
            )
            label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
            row.add_widget(checkbox)
            row.add_widget(label)
            opp_info_layout.add_widget(row)
        popup_content.add_widget(opp_info_layout)

        # Buttons
        buttons_layout = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48))
        save_button = Button(
            text=i18n._("Save"),
            size_hint_x=0.5,
            height=dp(48),
            background_color=Theme.BOX_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        cancel_button = Button(
            text=i18n._("Cancel"),
            size_hint_x=0.5,
            height=dp(48),
            background_color=Theme.LIGHTER_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        buttons_layout.add_widget(save_button)
        buttons_layout.add_widget(cancel_button)
        popup_content.add_widget(buttons_layout)

        scroll_view.add_widget(popup_content)

        popup = I18NPopup(
            title_key="mykatrain:settings",
            size=[dp(900), dp(700)],
            content=scroll_view,
        ).__self__

        # Save callback
        def save_settings(*_args):
            # Save skill preset to general config
            self._config["general"]["skill_preset"] = selected_skill_preset[0]
            self.save_config("general")
            # Save mykatrain settings
            self._config["mykatrain_settings"] = {
                "default_user_name": user_input.text,
                "karte_output_directory": output_input.text,
                "batch_export_input_directory": input_input.text,
                "karte_format": selected_format[0],
                "opponent_info_mode": selected_opp_info[0],  # Phase 4
            }
            self.save_config("mykatrain_settings")
            self.controls.set_status(i18n._("Settings saved"), STATUS_INFO)
            popup.dismiss()

        # Directory browse callbacks
        def browse_output(*_args):
            from katrain.gui.popups import LoadSGFPopup

            browse_popup_content = LoadSGFPopup(self)
            browse_popup_content.filesel.dirselect = True
            # Change button text to clarify it selects current folder
            browse_popup_content.filesel.select_string = "Select This Folder"
            if output_input.text and os.path.isdir(output_input.text):
                browse_popup_content.filesel.path = os.path.abspath(output_input.text)

            browse_popup = Popup(
                title="Select folder - Navigate into target folder, then click 'Select This Folder'",
                size_hint=(0.8, 0.8),
                content=browse_popup_content,
            ).__self__

            def on_select(*_args):
                # Use file_text.text which is updated by button_clicked
                output_input.text = browse_popup_content.filesel.file_text.text
                browse_popup.dismiss()

            browse_popup_content.filesel.bind(on_success=on_select)
            browse_popup.open()

        def browse_input(*_args):
            from katrain.gui.popups import LoadSGFPopup

            browse_popup_content = LoadSGFPopup(self)
            browse_popup_content.filesel.dirselect = True
            # Change button text to clarify it selects current folder
            browse_popup_content.filesel.select_string = "Select This Folder"
            if input_input.text and os.path.isdir(input_input.text):
                browse_popup_content.filesel.path = os.path.abspath(input_input.text)

            browse_popup = Popup(
                title="Select folder - Navigate into target folder, then click 'Select This Folder'",
                size_hint=(0.8, 0.8),
                content=browse_popup_content,
            ).__self__

            def on_select(*_args):
                # Use file_text.text which is updated by button_clicked
                input_input.text = browse_popup_content.filesel.file_text.text
                browse_popup.dismiss()

            browse_popup_content.filesel.bind(on_success=on_select)
            browse_popup.open()

        save_button.bind(on_release=save_settings)
        cancel_button.bind(on_release=lambda *_args: popup.dismiss())
        output_browse.bind(on_release=browse_output)
        input_browse.bind(on_release=browse_input)

        popup.open()

    def _do_batch_analyze_popup(self):
        """Show batch analyze folder dialog."""
        import threading
        from kivy.uix.textinput import TextInput
        from kivy.uix.checkbox import CheckBox
        from kivy.uix.scrollview import ScrollView

        from katrain.tools.batch_analyze_sgf import run_batch, BatchResult

        # Get default values from mykatrain_settings
        mykatrain_settings = self.config("mykatrain_settings") or {}
        default_input_dir = mykatrain_settings.get("batch_export_input_directory", "")

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
            text="",
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

        # Options row 1: visits and timeout
        options_row1 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))

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
            text="",
            hint_text=i18n._("mykatrain:batch:visits_hint"),
            multiline=False,
            input_filter="int",
            size_hint_x=0.2,
            font_name=Theme.DEFAULT_FONT,
        )

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
            text="600",
            multiline=False,
            input_filter="int",
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

        skip_checkbox = CheckBox(active=True, size_hint_x=None, width=dp(30))
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

        # Load saved batch options
        batch_options = mykatrain_settings.get("batch_options", {})

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
            timeout = float(timeout_input.text) if timeout_input.text.strip() else 600.0
            skip_analyzed = skip_checkbox.active

            # New options
            save_analyzed_sgf = save_sgf_checkbox.active
            generate_karte = karte_checkbox.active
            generate_summary = summary_checkbox.active

            # Save options for next time
            self._save_batch_options({
                "save_analyzed_sgf": save_analyzed_sgf,
                "generate_karte": generate_karte,
                "generate_summary": generate_summary,
            })

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
            )

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
        if loss is None:
            return i18n._("Points lost unknown")
        return i18n._("{loss:.1f} points lost").format(loss=loss)

    def _start_quiz_session(self, quiz_items: List[eval_metrics.QuizItem]) -> None:
        if not self.game:
            return
        if not quiz_items:
            self.controls.set_status(i18n._("No quiz items to show."), STATUS_INFO)
            return

        questions = self.game.build_quiz_questions(quiz_items)

        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))

        question_label = Label(
            text="",
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(60),
            color=Theme.TEXT_COLOR,
        )
        question_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, None)))
        content.add_widget(question_label)

        choices_layout = BoxLayout(
            orientation="vertical",
            spacing=dp(6),
            size_hint_y=None,
        )
        choices_layout.bind(minimum_height=choices_layout.setter("height"))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(choices_layout)
        content.add_widget(scroll)

        result_label = Label(
            text="",
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(70),
            color=Theme.TEXT_COLOR,
        )
        result_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, None)))
        content.add_widget(result_label)

        nav_layout = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(48))
        prev_button = Button(
            text=i18n._("Prev"),
            background_color=Theme.LIGHTER_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        next_button = Button(
            text=i18n._("Next"),
            background_color=Theme.LIGHTER_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        close_button = Button(
            text=i18n._("Close"),
            background_color=Theme.LIGHTER_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        nav_layout.add_widget(prev_button)
        nav_layout.add_widget(next_button)
        nav_layout.add_widget(close_button)
        content.add_widget(nav_layout)

        popup = I18NPopup(
            title_key="Quiz mode (beta)",
            size=[dp(540), dp(640)],
            content=content,
        ).__self__
        # 右下の分析パネルを残すため、右上に寄せて高さを抑える
        popup.size_hint = (0.38, 0.55)
        popup.pos_hint = {"right": 0.99, "top": 0.99}

        answers: dict[int, str] = {}
        current_index = 0
        total_questions = len(questions)

        def on_select(choice: eval_metrics.QuizChoice) -> None:
            nonlocal answers, current_index
            question = questions[current_index]

            # Backward-compatible: older QuizQuestion may not have played_loss/played_move
            item = getattr(question, "item", None)
            best_move = getattr(question, "best_move", None)
            played_loss_q = getattr(question, "played_loss", None)
            played_loss_item = getattr(item, "loss", None)
            played_loss = played_loss_q if played_loss_q is not None else played_loss_item

            played_move_q = getattr(question, "played_move", None)
            played_move_item = getattr(item, "played_move", None)
            played_move = played_move_q if played_move_q is not None else played_move_item

            def display_move(move_id: Optional[str]) -> str:
                if move_id is None:
                    return i18n._("Unknown move")
                return move_id or i18n._("Pass")
            loss_text = self._format_points_loss(choice.points_lost)
            played_loss_text = self._format_points_loss(played_loss)
            is_best = best_move is not None and choice.move == best_move

            lines = [
                i18n._("Correct!") if is_best else i18n._("Incorrect"),
                i18n._("Best move: {move}").format(
                    move=display_move(best_move)
                ),
                i18n._("Selected move loss: {loss_text}").format(
                    loss_text=loss_text
                ),
                i18n._("Played move {move} loss: {loss_text}").format(
                    move=display_move(played_move),
                    loss_text=played_loss_text,
                ),
            ]

            if choice.points_lost is not None and played_loss is not None:
                delta = choice.points_lost - played_loss
                lines.append(
                    i18n._("Delta vs played: {delta:+.1f} points").format(delta=delta)
                )

            text = "\n".join(lines)
            answers[current_index] = text
            result_label.text = text

        def show_question() -> None:
            nonlocal current_index
            if not questions:
                self.controls.set_status(i18n._("No analysis data for this position."), STATUS_INFO)
                popup.dismiss()
                return

            question = questions[current_index]
            color_label = "B" if question.item.player == "B" else "W" if question.item.player == "W" else "?"
            question_label.text = i18n._("Question {idx}/{total}: Move {move} ({player})").format(
                idx=current_index + 1,
                total=total_questions,
                move=question.item.move_number,
                player=color_label,
            )

            choices_layout.clear_widgets()
            result_label.text = answers.get(current_index, "")

            node_before = question.node_before_move
            if node_before is not None:
                self.game.set_current_node(node_before)
                self.update_state(redraw_board=True)

            if not question.has_analysis:
                no_data_label = Label(
                    text=i18n._("No analysis data for this position."),
                    halign="center",
                    valign="middle",
                    size_hint_y=None,
                    height=dp(80),
                    color=Theme.TEXT_COLOR,
                )
                no_data_label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, None)))
                choices_layout.add_widget(no_data_label)
            else:
                for choice in question.choices:
                    btn = Button(
                        text=choice.move or i18n._("Pass"),
                        size_hint_y=None,
                        height=dp(44),
                        background_color=Theme.BOX_BACKGROUND_COLOR,
                        color=Theme.TEXT_COLOR,
                    )
                    btn.bind(on_release=lambda _btn, c=choice: on_select(c))
                    choices_layout.add_widget(btn)

            prev_button.disabled = current_index <= 0
            next_button.disabled = current_index >= total_questions - 1

        def go_next(delta: int) -> None:
            nonlocal current_index
            new_index = current_index + delta
            new_index = max(0, min(total_questions - 1, new_index))
            if new_index != current_index:
                current_index = new_index
                show_question()

        prev_button.bind(on_release=lambda *_args: go_next(-1))
        next_button.bind(on_release=lambda *_args: go_next(1))
        close_button.bind(on_release=lambda *_args: popup.dismiss())

        show_question()
        popup.open()

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
