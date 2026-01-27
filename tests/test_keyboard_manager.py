"""KeyboardManagerのユニットテスト。

Phase 73: KaTrainGuiからキーボード処理を抽出。
Kivyインポート不要 - 全て依存注入でモック/スタブ。
"""
from typing import Callable

import pytest

from katrain.gui.managers.keyboard_manager import KeyboardManager


# === 実状態を持つスタブ（MagicMockより堅牢） ===


class TimerStub:
    """timer.pausedの実際のトグル動作を検証"""

    def __init__(self):
        self.paused = False


class NoteStub:
    """note.focusの状態を持つスタブ"""

    def __init__(self):
        self.focus = False


class MoveTreeStub:
    """move_tree操作の呼び出しを記録"""

    def __init__(self):
        self.calls = []

    def make_selected_node_main_branch(self):
        self.calls.append("make_main_branch")

    def delete_selected_node(self):
        self.calls.append("delete_node")

    def toggle_selected_node_collapse(self):
        self.calls.append("toggle_collapse")


class ControlsStub:
    """controls.timer, controls.note等を持つスタブ"""

    def __init__(self):
        self.timer = TimerStub()
        self.note = NoteStub()
        self.move_tree = MoveTreeStub()
        self._status_calls = []

    def set_status(self, msg, level):
        self._status_calls.append((msg, level))


class PopupStub:
    """ポップアップのdismiss呼び出しを検証"""

    def __init__(self):
        self.dismissed = False
        self.content = type("Content", (), {"on_submit": lambda: None})()

    def dismiss(self):
        self.dismissed = True


class NavDrawerStub:
    """nav_drawerの状態変更を検証"""

    def __init__(self):
        self.state_calls = []

    def set_state(self, state):
        self.state_calls.append(state)


class ZenStateHolder:
    """zenの実際の状態遷移を検証"""

    def __init__(self):
        self.value = 0

    def get_set(self):
        return (self.value, self._set)

    def _set(self, v):
        self.value = v


class ScheduleOnceRecorder:
    """schedule_once呼び出しを記録し、コールバックを実行可能"""

    def __init__(self):
        self.calls = []  # [(callback, delay), ...]

    def __call__(self, callback: Callable[[float], None], delay: float):
        """Kivy Clock.schedule_once互換"""
        self.calls.append((callback, delay))

    def execute_pending(self, dt: float = 0.0):
        """保留中のコールバックを実行（テスト用）"""
        for callback, _ in self.calls:
            callback(dt)
        self.calls.clear()


class AnalysisControlsStub:
    """analysis_controlsの動作を記録"""

    def __init__(self, dispatched_actions):
        self._dispatched = dispatched_actions
        self.show_children = type("W", (), {"trigger_action": lambda duration=0: None})()
        self.eval = type("W", (), {"trigger_action": lambda duration=0: None})()
        self.hints = type("W", (), {"trigger_action": lambda duration=0: None})()
        self.ownership = type("W", (), {"trigger_action": lambda duration=0: None})()
        self.policy = type("W", (), {"trigger_action": lambda duration=0: None})()
        self.dropdown = DropdownStub(dispatched_actions)


class DropdownStub:
    """dropdown操作を記録"""

    def __init__(self, dispatched_actions):
        self._dispatched = dispatched_actions

    def open_game_analysis_popup(self):
        self._dispatched.append(("open_game_analysis_popup", ()))

    def open_report_popup(self):
        self._dispatched.append(("open_report_popup", ()))

    def open_tsumego_frame_popup(self):
        self._dispatched.append(("open_tsumego_frame_popup", ()))


class BoardGuiStub:
    """board_guiの動作を記録"""

    def __init__(self):
        self.toggle_coordinates_called = False

    def toggle_coordinates(self):
        self.toggle_coordinates_called = True


class PlayModeStub:
    """play_modeの動作を記録"""

    def __init__(self, dispatched_actions):
        self._dispatched = dispatched_actions

    def switch_ui_mode(self):
        self._dispatched.append(("switch_ui_mode", ()))


class RootStub:
    """game.rootの動作をスタブ"""

    def sgf(self):
        return "(;)"


class GameStub:
    """gameの動作をスタブ"""

    def __init__(self):
        self.root = RootStub()


@pytest.fixture
def stubs():
    """実状態を持つスタブ群"""
    dispatched_actions = []
    return {
        "controls": ControlsStub(),
        "popup": None,  # デフォルトはポップアップなし
        "nav_drawer": NavDrawerStub(),
        "zen": ZenStateHolder(),
        "dispatched_actions": dispatched_actions,
        "platform": "win",  # デフォルトはWindows
        "schedule_once": ScheduleOnceRecorder(),
        "copied_text": [],
        "analysis_controls": AnalysisControlsStub(dispatched_actions),
        "board_gui": BoardGuiStub(),
        "play_mode": PlayModeStub(dispatched_actions),
        "game": GameStub(),
    }


@pytest.fixture
def manager(stubs):
    """スタブを注入したKeyboardManager"""
    return KeyboardManager(
        # Kivy代替
        get_platform=lambda: stubs["platform"],
        schedule_once=stubs["schedule_once"],
        clipboard_copy=lambda text: stubs["copied_text"].append(text),
        # State accessors
        get_note_focus=lambda: stubs["controls"].note.focus,
        get_popup_open=lambda: stubs["popup"],
        get_game=lambda: stubs["game"],
        # Action dispatcher
        action_dispatcher=lambda action, *args: stubs["dispatched_actions"].append((action, args)),
        # Widget accessors
        get_analysis_controls=lambda: stubs["analysis_controls"],
        get_board_gui=lambda: stubs["board_gui"],
        get_controls=lambda: stubs["controls"],
        get_nav_drawer=lambda: stubs["nav_drawer"],
        get_play_mode=lambda: stubs["play_mode"],
        # State modifiers
        get_set_zen=stubs["zen"].get_set,
        toggle_continuous_analysis=lambda quiet: stubs["dispatched_actions"].append(
            ("toggle_analysis", (quiet,))
        ),
        toggle_move_num=lambda: stubs["dispatched_actions"].append(("toggle_movenum", ())),
        load_from_clipboard=lambda: stubs["dispatched_actions"].append(("load_clipboard", ())),
        # Utilities
        logger=lambda msg, level: None,
        status_setter=lambda msg, level: stubs["controls"].set_status(msg, level),
    )


class TestKeyboardManagerInit:
    """初期化テスト"""

    def test_initial_state(self, manager):
        """初期状態の検証"""
        assert manager.last_key_down is None
        assert manager.last_focus_event == 0.0


class TestNoteFocusBlocking:
    """ノートフォーカス中のブロック"""

    def test_note_focus_blocks_all_keys(self, manager, stubs):
        """ノートフォーカス中は全キー無効"""
        stubs["controls"].note.focus = True
        manager.on_keyboard_down(None, (123, "left"), None, [])
        assert stubs["dispatched_actions"] == []


class TestPopupBehavior:
    """ポップアップ中のキー動作を検証（Option B: dismiss only）"""

    def test_popup_switch_key_dismisses_only(self, manager, stubs):
        """ポップアップ中のF2はdismissのみ（新ポップアップは開かない）"""
        popup = PopupStub()
        stubs["popup"] = popup
        manager.on_keyboard_down(None, (113, "f2"), None, [])
        # ポップアップはdismissされる
        assert popup.dismissed is True
        # 新ポップアップは開かない（action_dispatcherは呼ばれない）
        assert stubs["dispatched_actions"] == []
        # schedule_onceも呼ばれない
        assert stubs["schedule_once"].calls == []

    def test_all_popup_switch_keys_dismiss(self, manager, stubs):
        """F2, F3, F5, F6, F7, F8, F10は全てdismissのみ"""
        switch_keys = ["f2", "f3", "f5", "f6", "f7", "f8", "f10"]
        for key in switch_keys:
            popup = PopupStub()
            stubs["popup"] = popup
            stubs["dispatched_actions"].clear()
            manager.on_keyboard_down(None, (0, key), None, [])
            assert popup.dismissed is True, f"Key {key} should dismiss popup"
            assert stubs["dispatched_actions"] == [], f"Key {key} should not dispatch"

    def test_popup_blocks_other_keys(self, manager, stubs):
        """ポップアップ中は許可キー以外ブロック"""
        popup = PopupStub()
        stubs["popup"] = popup
        # Left arrow - ブロックされるべき
        manager.on_keyboard_down(None, (123, "left"), None, [])
        assert popup.dismissed is False
        assert stubs["dispatched_actions"] == []

    def test_popup_enter_submits(self, manager, stubs):
        """ポップアップ中のEnterはon_submit()を呼ぶ"""
        submitted = {"called": False}
        popup = PopupStub()
        popup.content.on_submit = lambda: submitted.__setitem__("called", True)
        stubs["popup"] = popup
        manager.on_keyboard_down(None, (13, "enter"), None, [])
        assert submitted["called"] is True
        assert popup.dismissed is False  # dismissはしない

    def test_second_keypress_opens_popup(self, manager, stubs):
        """ポップアップ閉じた後の2回目押下で新ポップアップが開く"""
        # 1回目: ポップアップ中 → dismiss
        popup = PopupStub()
        stubs["popup"] = popup
        manager.on_keyboard_down(None, (113, "f2"), None, [])
        assert popup.dismissed is True
        assert stubs["dispatched_actions"] == []

        # 2回目: ポップアップなし → open
        stubs["popup"] = None
        stubs["dispatched_actions"].clear()
        manager.on_keyboard_down(None, (113, "f2"), None, [])
        # analysis_controls.dropdown.open_game_analysis_popup() が呼ばれる
        assert ("open_game_analysis_popup", ()) in stubs["dispatched_actions"]


class TestNavigation:
    """ナビゲーションキーテスト"""

    def test_left_basic(self, manager, stubs):
        """Left: 1手戻る"""
        manager.on_keyboard_down(None, (123, "left"), None, [])
        assert stubs["dispatched_actions"] == [("undo", (1,))]

    def test_left_with_shift(self, manager, stubs):
        """Shift+Left: 10手戻る"""
        manager.on_keyboard_down(None, (123, "left"), None, ["shift"])
        assert stubs["dispatched_actions"] == [("undo", (10,))]

    def test_left_with_ctrl(self, manager, stubs):
        """Ctrl+Left: 最初まで戻る"""
        manager.on_keyboard_down(None, (123, "left"), None, ["ctrl"])
        assert stubs["dispatched_actions"] == [("undo", (10000,))]

    def test_left_with_shift_and_ctrl(self, manager, stubs):
        """Shift+Ctrl+Left: 10009手戻る"""
        manager.on_keyboard_down(None, (123, "left"), None, ["shift", "ctrl"])
        assert stubs["dispatched_actions"] == [("undo", (10009,))]

    def test_right_basic(self, manager, stubs):
        """Right: 1手進む"""
        manager.on_keyboard_down(None, (124, "right"), None, [])
        assert stubs["dispatched_actions"] == [("redo", (1,))]

    def test_z_as_left(self, manager, stubs):
        """Zキーも左と同じ"""
        manager.on_keyboard_down(None, (122, "z"), None, [])
        assert stubs["dispatched_actions"] == [("undo", (1,))]

    def test_x_as_right(self, manager, stubs):
        """Xキーも右と同じ"""
        manager.on_keyboard_down(None, (120, "x"), None, [])
        assert stubs["dispatched_actions"] == [("redo", (1,))]

    def test_home(self, manager, stubs):
        """Home: 最初へ（修飾キー無視）"""
        manager.on_keyboard_down(None, (36, "home"), None, ["shift"])
        assert stubs["dispatched_actions"] == [("undo", (9999,))]

    def test_end(self, manager, stubs):
        """End: 最後へ（修飾キー無視）"""
        manager.on_keyboard_down(None, (35, "end"), None, ["ctrl"])
        assert stubs["dispatched_actions"] == [("redo", (9999,))]


class TestModifierRobustness:
    """修飾キーの異常入力に対する堅牢性"""

    def test_modifiers_none(self, manager, stubs):
        """modifiers=Noneでもクラッシュしない"""
        manager.on_keyboard_down(None, (123, "left"), None, None)
        assert stubs["dispatched_actions"] == [("undo", (1,))]

    def test_modifiers_empty_list(self, manager, stubs):
        """modifiers=[]は修飾キーなし"""
        manager.on_keyboard_down(None, (123, "left"), None, [])
        assert stubs["dispatched_actions"] == [("undo", (1,))]

    def test_modifiers_unknown_strings(self, manager, stubs):
        """未知の修飾キー文字列は無視"""
        manager.on_keyboard_down(None, (123, "left"), None, ["unknown", "foo"])
        assert stubs["dispatched_actions"] == [("undo", (1,))]

    def test_macos_meta_as_ctrl(self, manager, stubs):
        """macOSではmetaをctrlとして扱う"""
        stubs["platform"] = "macosx"
        manager.on_keyboard_down(None, (123, "left"), None, ["meta"])
        assert stubs["dispatched_actions"] == [("undo", (10000,))]

    def test_non_macos_meta_not_ctrl(self, manager, stubs):
        """非macOSではmetaはctrlではない"""
        stubs["platform"] = "win"
        manager.on_keyboard_down(None, (123, "left"), None, ["meta"])
        assert stubs["dispatched_actions"] == [("undo", (1,))]


class TestCtrlKeyOperations:
    """Ctrl+Key操作テスト"""

    def test_ctrl_n_new_game(self, manager, stubs):
        """Ctrl+N: 新規ゲームポップアップ"""
        manager.on_keyboard_down(None, (110, "n"), None, ["ctrl"])
        assert ("new-game-popup", ()) in stubs["dispatched_actions"]

    def test_ctrl_s_save(self, manager, stubs):
        """Ctrl+S: 保存"""
        manager.on_keyboard_down(None, (115, "s"), None, ["ctrl"])
        assert ("save-game", ()) in stubs["dispatched_actions"]

    def test_ctrl_c_copy(self, manager, stubs):
        """Ctrl+C: SGFコピー"""
        manager.on_keyboard_down(None, (99, "c"), None, ["ctrl"])
        assert len(stubs["copied_text"]) == 1
        assert stubs["copied_text"][0] == "(;)"

    def test_ctrl_v_paste(self, manager, stubs):
        """Ctrl+V: クリップボードから読込"""
        manager.on_keyboard_down(None, (118, "v"), None, ["ctrl"])
        assert ("load_clipboard", ()) in stubs["dispatched_actions"]


class TestRealStateMutation:
    """MagicMockではなく実際の状態変更を検証"""

    def test_timer_pause_toggles(self, manager, stubs):
        """Pauseキーでtimer.pausedが実際に反転"""
        assert stubs["controls"].timer.paused is False
        manager.on_keyboard_down(None, (19, "pause"), None, [])
        assert stubs["controls"].timer.paused is True
        manager.on_keyboard_down(None, (19, "pause"), None, [])
        assert stubs["controls"].timer.paused is False

    def test_zen_cycles_through_states(self, manager, stubs):
        """バッククォートキーでzenが0→1→2→0とサイクル"""
        assert stubs["zen"].value == 0
        manager.on_keyboard_down(None, (96, "`"), None, [])
        assert stubs["zen"].value == 1
        manager.on_keyboard_down(None, (96, "`"), None, [])
        assert stubs["zen"].value == 2
        manager.on_keyboard_down(None, (96, "`"), None, [])
        assert stubs["zen"].value == 0

    def test_toggle_coordinates(self, manager, stubs):
        """Kキーで座標表示トグル"""
        assert stubs["board_gui"].toggle_coordinates_called is False
        manager.on_keyboard_down(None, (107, "k"), None, [])
        assert stubs["board_gui"].toggle_coordinates_called is True

    def test_move_tree_make_main_branch(self, manager, stubs):
        """PageUpでメイン分岐に設定"""
        manager.on_keyboard_down(None, (33, "pageup"), None, [])
        assert "make_main_branch" in stubs["controls"].move_tree.calls

    def test_move_tree_delete_node(self, manager, stubs):
        """Ctrl+Deleteでノード削除"""
        manager.on_keyboard_down(None, (46, "delete"), None, ["ctrl"])
        assert "delete_node" in stubs["controls"].move_tree.calls

    def test_move_tree_toggle_collapse(self, manager, stubs):
        """Cキーで折り畳みトグル（Ctrlなし）"""
        manager.on_keyboard_down(None, (99, "c"), None, [])
        assert "toggle_collapse" in stubs["controls"].move_tree.calls


class TestRequiresNoCtrl:
    """!Ctrl必須のキー"""

    def test_pause_blocked_with_ctrl(self, manager, stubs):
        """Pauseはctrl押下時は無効"""
        assert stubs["controls"].timer.paused is False
        manager.on_keyboard_down(None, (19, "pause"), None, ["ctrl"])
        assert stubs["controls"].timer.paused is False  # 変更なし

    def test_collapse_blocked_with_ctrl(self, manager, stubs):
        """Cキーの折り畳みはctrl押下時は無効（Ctrl+Cはコピー）"""
        manager.on_keyboard_down(None, (99, "c"), None, ["ctrl"])
        # Ctrl+Cはコピーなので、toggle_collapseは呼ばれない
        assert "toggle_collapse" not in stubs["controls"].move_tree.calls

    def test_find_mistake_blocked_with_ctrl(self, manager, stubs):
        """Nキーのfind-mistakeはctrl押下時は無効（Ctrl+Nは新規ゲーム）"""
        manager.on_keyboard_down(None, (110, "n"), None, ["ctrl"])
        # Ctrl+Nは新規ゲームポップアップ
        assert ("new-game-popup", ()) in stubs["dispatched_actions"]
        # find-mistakeは呼ばれない
        assert ("find-mistake", ("redo",)) not in stubs["dispatched_actions"]


class TestFindMistake:
    """find-mistakeのテスト"""

    def test_n_key_finds_next_mistake(self, manager, stubs):
        """Nキーで次のミスへ"""
        manager.on_keyboard_down(None, (110, "n"), None, [])
        assert ("find-mistake", ("redo",)) in stubs["dispatched_actions"]

    def test_shift_n_finds_prev_mistake(self, manager, stubs):
        """Shift+Nで前のミスへ"""
        manager.on_keyboard_down(None, (110, "n"), None, ["shift"])
        assert ("find-mistake", ("undo",)) in stubs["dispatched_actions"]


class TestPopupKeys:
    """ポップアップ開くキーのテスト"""

    def test_f2_opens_analysis_popup(self, manager, stubs):
        """F2で詳細解析ポップアップ"""
        manager.on_keyboard_down(None, (113, "f2"), None, [])
        assert ("open_game_analysis_popup", ()) in stubs["dispatched_actions"]

    def test_f3_opens_report_popup(self, manager, stubs):
        """F3でレポートポップアップ"""
        manager.on_keyboard_down(None, (114, "f3"), None, [])
        assert ("open_report_popup", ()) in stubs["dispatched_actions"]

    def test_f10_opens_tsumego_popup(self, manager, stubs):
        """F10で詰碁フレームポップアップ"""
        manager.on_keyboard_down(None, (121, "f10"), None, [])
        assert ("open_tsumego_frame_popup", ()) in stubs["dispatched_actions"]


class TestDispatchTableOrdering:
    """テーブルリファクタ時の動作変更を防止"""

    def test_f10_tsumego_not_profiler(self, manager, stubs):
        """F10は常にtsumego-frame（デッドコードのyappiではない）"""
        manager.on_keyboard_down(None, (121, "f10"), None, [])
        assert ("open_tsumego_frame_popup", ()) in stubs["dispatched_actions"]


class TestSingleKeyActions:
    """Alt/Tab単独押下のテスト"""

    def test_alt_schedules_action(self, manager, stubs):
        """Alt押下後に離すとschedule_onceが呼ばれる"""
        manager.on_keyboard_down(None, (18, "alt"), None, [])
        manager.on_keyboard_up(None, (18, "alt"))
        assert len(stubs["schedule_once"].calls) == 1
        assert stubs["schedule_once"].calls[0][1] == 0.05  # delay

    def test_tab_schedules_action(self, manager, stubs):
        """Tab押下後に離すとschedule_onceが呼ばれる"""
        manager.on_keyboard_down(None, (9, "tab"), None, [])
        manager.on_keyboard_up(None, (9, "tab"))
        assert len(stubs["schedule_once"].calls) == 1
        assert stubs["schedule_once"].calls[0][1] == 0.05

    def test_alt_toggles_nav_drawer(self, manager, stubs):
        """Alt単独押下でnav_drawer toggled"""
        keycode = (18, "alt")
        manager.on_keyboard_down(None, keycode, None, [])
        manager.on_keyboard_up(None, keycode)
        # コールバックを実行
        stubs["schedule_once"].execute_pending()
        assert "toggle" in stubs["nav_drawer"].state_calls

    def test_tab_switches_ui_mode(self, manager, stubs):
        """Tab単独押下でUIモード切替"""
        keycode = (9, "tab")
        manager.on_keyboard_down(None, keycode, None, [])
        manager.on_keyboard_up(None, keycode)
        # コールバックを実行
        stubs["schedule_once"].execute_pending()
        assert ("switch_ui_mode", ()) in stubs["dispatched_actions"]

    def test_alt_blocked_by_note_focus(self, manager, stubs):
        """ノートフォーカス中はAlt無効"""
        stubs["controls"].note.focus = True
        keycode = (18, "alt")
        manager.on_keyboard_down(None, keycode, None, [])
        manager.on_keyboard_up(None, keycode)
        stubs["schedule_once"].execute_pending()
        assert stubs["nav_drawer"].state_calls == []

    def test_alt_blocked_by_popup(self, manager, stubs):
        """ポップアップ中はAlt無効"""
        stubs["popup"] = PopupStub()
        keycode = (18, "alt")
        manager.on_keyboard_down(None, keycode, None, [])
        manager.on_keyboard_up(None, keycode)
        stubs["schedule_once"].execute_pending()
        assert stubs["nav_drawer"].state_calls == []

    def test_alt_blocked_by_different_last_key(self, manager, stubs):
        """違うキーを押した後のAlt離しは無効"""
        manager.on_keyboard_down(None, (65, "a"), None, [])  # Aを押す
        manager.on_keyboard_up(None, (18, "alt"))  # Altを離す
        stubs["schedule_once"].execute_pending()
        assert stubs["nav_drawer"].state_calls == []


class TestShortcutsProperty:
    """shortcutsプロパティのテスト"""

    def test_shortcuts_returns_dict(self, manager):
        """shortcutsは辞書を返す"""
        shortcuts = manager.shortcuts
        assert isinstance(shortcuts, dict)

    def test_shortcuts_contains_expected_keys(self, manager):
        """shortcutsには期待されるキーが含まれる"""
        shortcuts = manager.shortcuts
        # Theme定数のキーがいくつか含まれているはず
        assert "q" in shortcuts  # KEY_ANALYSIS_CONTROLS_SHOW_CHILDREN
        assert "escape" in shortcuts  # KEY_STOP_ANALYSIS

    def test_shortcuts_empty_when_no_analysis_controls(self, stubs):
        """analysis_controlsがNoneの場合は空辞書"""
        manager = KeyboardManager(
            get_platform=lambda: stubs["platform"],
            schedule_once=stubs["schedule_once"],
            clipboard_copy=lambda text: stubs["copied_text"].append(text),
            get_note_focus=lambda: stubs["controls"].note.focus,
            get_popup_open=lambda: stubs["popup"],
            get_game=lambda: stubs["game"],
            action_dispatcher=lambda action, *args: stubs["dispatched_actions"].append(
                (action, args)
            ),
            get_analysis_controls=lambda: None,  # None
            get_board_gui=lambda: stubs["board_gui"],
            get_controls=lambda: stubs["controls"],
            get_nav_drawer=lambda: stubs["nav_drawer"],
            get_play_mode=lambda: stubs["play_mode"],
            get_set_zen=stubs["zen"].get_set,
            toggle_continuous_analysis=lambda quiet: None,
            toggle_move_num=lambda: None,
            load_from_clipboard=lambda: None,
            logger=lambda msg, level: None,
            status_setter=lambda msg, level: None,
        )
        assert manager.shortcuts == {}


class TestToggleContinuousAnalysis:
    """継続解析トグルのテスト"""

    def test_spacebar_toggles_analysis(self, manager, stubs):
        """Spacebarで継続解析トグル"""
        manager.on_keyboard_down(None, (32, "spacebar"), None, [])
        assert ("toggle_analysis", (False,)) in stubs["dispatched_actions"]

    def test_shift_spacebar_toggles_quietly(self, manager, stubs):
        """Shift+Spacebarで静かにトグル"""
        manager.on_keyboard_down(None, (32, "spacebar"), None, ["shift"])
        assert ("toggle_analysis", (True,)) in stubs["dispatched_actions"]


class TestToggleMoveNum:
    """手数表示トグルのテスト"""

    def test_m_toggles_move_num(self, manager, stubs):
        """Mキーで手数表示トグル"""
        manager.on_keyboard_down(None, (109, "m"), None, [])
        assert ("toggle_movenum", ()) in stubs["dispatched_actions"]
