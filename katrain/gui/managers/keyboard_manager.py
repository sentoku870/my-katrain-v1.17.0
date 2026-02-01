"""Keyboard input management.

Phase 73: KaTrainGuiからキーボード処理を抽出。
依存注入パターンでKivy非依存テストを実現。

重要: このモジュールはインポート時にKivy UIクラスを読み込まない。
Kivy依存（platform, Clock, Clipboard）は全てコンストラクタで注入。
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from katrain.core.constants import STATUS_INFO
from katrain.core.lang import i18n
from katrain.gui.theme import Theme


class KeyboardManager:
    """Keyboard input handler for KaTrainGui.

    依存注入パターンにより、Kivy非依存でテスト可能。
    """

    def __init__(
        self,
        # Kivy代替（依存注入）
        get_platform: Callable[[], str],
        schedule_once: Callable[[Callable[[float], None], float], None],
        clipboard_copy: Callable[[str], None],
        # State accessors
        get_note_focus: Callable[[], bool],
        get_popup_open: Callable[[], Optional[Any]],
        get_game: Callable[[], Optional[Any]],
        # Action dispatcher
        action_dispatcher: Callable[..., None],
        # Widget accessors
        get_analysis_controls: Callable[[], Optional[Any]],
        get_board_gui: Callable[[], Optional[Any]],
        get_controls: Callable[[], Optional[Any]],
        get_nav_drawer: Callable[[], Optional[Any]],
        get_play_mode: Callable[[], Optional[Any]],
        # State modifiers
        get_set_zen: Callable[[], Tuple[int, Callable[[int], None]]],
        toggle_continuous_analysis: Callable[[bool], None],
        toggle_move_num: Callable[[], None],
        load_from_clipboard: Callable[[], None],
        # Utilities
        logger: Callable[[str, int], None],
        status_setter: Callable[[str, int], None],
        # Debug level for profiler (optional)
        get_debug_level: Optional[Callable[[], int]] = None,
    ):
        """初期化。全依存をコンストラクタで受け取る。"""
        # Kivy代替
        self._get_platform = get_platform
        self._schedule_once = schedule_once
        self._clipboard_copy = clipboard_copy
        # State accessors
        self._get_note_focus = get_note_focus
        self._get_popup_open = get_popup_open
        self._get_game = get_game
        # Action dispatcher
        self._action_dispatcher = action_dispatcher
        # Widget accessors
        self._get_analysis_controls = get_analysis_controls
        self._get_board_gui = get_board_gui
        self._get_controls = get_controls
        self._get_nav_drawer = get_nav_drawer
        self._get_play_mode = get_play_mode
        # State modifiers
        self._get_set_zen = get_set_zen
        self._toggle_continuous_analysis = toggle_continuous_analysis
        self._toggle_move_num = toggle_move_num
        self._load_from_clipboard = load_from_clipboard
        # Utilities
        self._log = logger
        self._set_status = status_setter
        self._get_debug_level = get_debug_level
        # Internal state
        self.last_key_down: Optional[Tuple[int, str]] = None
        self.last_focus_event: float = 0.0

    def _parse_modifiers(self, modifiers: Optional[List[str]]) -> Tuple[bool, bool]:
        """修飾キーを安全にパース。None/不正値に対応。

        Args:
            modifiers: 修飾キーリスト（None可、不正文字列含む可能性あり）
        Returns:
            (ctrl_pressed, shift_pressed) タプル
        """
        if modifiers is None:
            modifiers = []
        mod_set = set(modifiers)
        ctrl = "ctrl" in mod_set or (
            "meta" in mod_set and self._get_platform() == "macosx"
        )
        shift = "shift" in mod_set
        return ctrl, shift

    @property
    def shortcuts(self) -> Dict[str, Any]:
        """ショートカットキー辞書を返す。

        Returns:
            キー文字列 → アクション（Widget or Tuple）のマッピング
        """
        analysis_controls = self._get_analysis_controls()
        if analysis_controls is None:
            return {}

        return {
            k: v
            for ks, v in [
                (Theme.KEY_ANALYSIS_CONTROLS_SHOW_CHILDREN, analysis_controls.show_children),
                (Theme.KEY_ANALYSIS_CONTROLS_EVAL, analysis_controls.eval),
                (Theme.KEY_ANALYSIS_CONTROLS_HINTS, analysis_controls.hints),
                (Theme.KEY_ANALYSIS_CONTROLS_OWNERSHIP, analysis_controls.ownership),
                (Theme.KEY_ANALYSIS_CONTROLS_POLICY, analysis_controls.policy),
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
                (Theme.KEY_STOP_ANALYSIS, ("analyze-extra", "stop")),
            ]
            for k in (ks if isinstance(ks, list) else [ks])
        }

    def on_keyboard_down(self, _keyboard: Any, keycode: Tuple[int, str], _text: str, modifiers: Optional[List[str]]) -> None:
        """キー押下イベントハンドラ。

        Args:
            _keyboard: Keyboard instance (unused)
            keycode: Tuple[int, str] - (scancode, key_name)
            _text: str - text representation (unused)
            modifiers: List[str] | None - ["ctrl", "shift", "alt", "meta", etc.]

        Returns:
            None

        Note on return values:
            Kivyはキーボードイベントで戻り値を使用する場合がある（dispatch結果）が、
            KaTrainの現行コードは戻り値に依存していない。
            既存動作を維持するためNoneを返す。将来的な変更は別Phaseで検討。
        """
        self.last_key_down = keycode
        ctrl_pressed, shift_pressed = self._parse_modifiers(modifiers)

        # ノート入力中はキーボードショートカット無効
        if self._get_note_focus():
            return

        # ポップアップ処理
        popup = self._get_popup_open()
        if popup:
            if keycode[1] in [
                Theme.KEY_DEEPERANALYSIS_POPUP,
                Theme.KEY_REPORT_POPUP,
                Theme.KEY_TIMER_POPUP,
                Theme.KEY_TEACHER_POPUP,
                Theme.KEY_AI_POPUP,
                Theme.KEY_CONFIG_POPUP,
                Theme.KEY_TSUMEGO_FRAME,
            ]:
                # ポップアップを閉じるのみ（新ポップアップは開かない）
                popup.dismiss()
                return
            elif keycode[1] in Theme.KEY_SUBMIT_POPUP:
                fn = getattr(popup.content, "on_submit", None)
                if fn:
                    fn()
                return
            else:
                return

        # 通常キー処理
        if keycode[1] == Theme.KEY_TOGGLE_CONTINUOUS_ANALYSIS:
            self._toggle_continuous_analysis(shift_pressed)  # positional arg to match Callable signature
        elif keycode[1] == Theme.KEY_TOGGLE_MOVENUM:
            self._toggle_move_num()
        elif keycode[1] == Theme.KEY_TOGGLE_COORDINATES:
            board_gui = self._get_board_gui()
            if board_gui:
                board_gui.toggle_coordinates()
        elif keycode[1] in Theme.KEY_PAUSE_TIMER and not ctrl_pressed:
            controls = self._get_controls()
            if controls:
                controls.timer.paused = not controls.timer.paused
        elif keycode[1] in Theme.KEY_ZEN:
            zen_value, zen_setter = self._get_set_zen()
            zen_setter((zen_value + 1) % 3)
        elif keycode[1] in Theme.KEY_NAV_PREV:
            self._action_dispatcher("undo", 1 + shift_pressed * 9 + ctrl_pressed * 9999)
        elif keycode[1] in Theme.KEY_NAV_NEXT:
            self._action_dispatcher("redo", 1 + shift_pressed * 9 + ctrl_pressed * 9999)
        elif keycode[1] == Theme.KEY_NAV_GAME_START:
            self._action_dispatcher("undo", 9999)
        elif keycode[1] == Theme.KEY_NAV_GAME_END:
            self._action_dispatcher("redo", 9999)
        elif keycode[1] == Theme.KEY_MOVE_TREE_MAKE_SELECTED_NODE_MAIN_BRANCH:
            controls = self._get_controls()
            if controls:
                controls.move_tree.make_selected_node_main_branch()
        elif keycode[1] == Theme.KEY_NAV_MISTAKE and not ctrl_pressed:
            self._action_dispatcher("find-mistake", "undo" if shift_pressed else "redo")
        elif keycode[1] == Theme.KEY_MOVE_TREE_DELETE_SELECTED_NODE and ctrl_pressed:
            controls = self._get_controls()
            if controls:
                controls.move_tree.delete_selected_node()
        elif keycode[1] == Theme.KEY_MOVE_TREE_TOGGLE_SELECTED_NODE_COLLAPSE and not ctrl_pressed:
            controls = self._get_controls()
            if controls:
                controls.move_tree.toggle_selected_node_collapse()
        elif keycode[1] == Theme.KEY_NEW_GAME and ctrl_pressed:
            self._action_dispatcher("new-game-popup")
        elif keycode[1] == Theme.KEY_LOAD_GAME and ctrl_pressed:
            self._action_dispatcher("analyze-sgf-popup")
        elif keycode[1] == Theme.KEY_SAVE_GAME and ctrl_pressed:
            self._action_dispatcher("save-game")
        elif keycode[1] == Theme.KEY_SAVE_GAME_AS and ctrl_pressed:
            self._action_dispatcher("save-game-as-popup")
        elif keycode[1] == Theme.KEY_COPY and ctrl_pressed:
            game = self._get_game()
            if game:
                self._clipboard_copy(game.root.sgf())
                self._set_status(i18n._("Copied SGF to clipboard."), int(STATUS_INFO))
        elif keycode[1] == Theme.KEY_PASTE and ctrl_pressed:
            self._load_from_clipboard()
        elif keycode[1] == Theme.KEY_NAV_PREV_BRANCH and shift_pressed:
            self._action_dispatcher("undo", "main-branch")
        elif keycode[1] == Theme.KEY_DEEPERANALYSIS_POPUP:
            analysis_controls = self._get_analysis_controls()
            if analysis_controls:
                analysis_controls.dropdown.open_game_analysis_popup()
        elif keycode[1] == Theme.KEY_TSUMEGO_FRAME:
            analysis_controls = self._get_analysis_controls()
            if analysis_controls:
                analysis_controls.dropdown.open_tsumego_frame_popup()
        elif keycode[1] == Theme.KEY_REPORT_POPUP:
            analysis_controls = self._get_analysis_controls()
            if analysis_controls:
                analysis_controls.dropdown.open_report_popup()
        elif keycode[1] == "f10" and self._get_debug_level and self._get_debug_level() >= 4:
            # OUTPUT_EXTRA_DEBUG = 4
            # Dead code: KEY_TSUMEGO_FRAME = "f10" matches first
            import yappi
            yappi.set_clock_type("cpu")
            yappi.start()
            self._log("starting profiler", 1)  # OUTPUT_ERROR = 1
        elif keycode[1] == "f11" and self._get_debug_level and self._get_debug_level() >= 4:
            import time as time_module
            import yappi
            stats = yappi.get_func_stats()
            filename = f"callgrind.{int(time_module.time())}.prof"
            stats.save(filename, type="callgrind")
            self._log(f"wrote profiling results to {filename}", 1)
        elif not ctrl_pressed:
            shortcut = self.shortcuts.get(keycode[1])
            if shortcut is not None:
                # Check if it's a Widget (has trigger_action method)
                if hasattr(shortcut, "trigger_action"):
                    shortcut.trigger_action(duration=0)
                else:
                    self._action_dispatcher(*shortcut)

    def on_keyboard_up(self, _keyboard: Any, keycode: Tuple[int, str]) -> None:
        """キー解放イベントハンドラ。

        Args:
            _keyboard: Keyboard instance (unused)
            keycode: Tuple[int, str] - (scancode, key_name)

        Returns:
            None (既存動作維持)
        """
        if keycode[1] in ["alt", "tab"]:
            self._schedule_once(lambda dt: self._single_key_action(keycode), 0.05)

    def _single_key_action(self, keycode: Tuple[int, str]) -> None:
        """Alt/Tab単独押下時の処理。

        schedule_onceから遅延呼び出しされる。
        """
        if (
            self._get_note_focus()
            or self._get_popup_open()
            or keycode != self.last_key_down
            or time.time() - self.last_focus_event < 0.2  # alt-tab防止
        ):
            return
        if keycode[1] == "alt":
            nav_drawer = self._get_nav_drawer()
            if nav_drawer:
                nav_drawer.set_state("toggle")
        elif keycode[1] == "tab":
            play_mode = self._get_play_mode()
            if play_mode:
                play_mode.switch_ui_mode()
