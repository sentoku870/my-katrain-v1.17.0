"""Common base classes and input widgets for katrain GUI popups.

Phase 140 P2-1: Extracted from katrain/gui/popups.py to enable focused
maintenance and faster incremental imports.
"""
from __future__ import annotations

import os
from typing import Any

from kivy.clock import Clock
from kivy.properties import BooleanProperty, ListProperty, ObjectProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.textfield import MDTextField

from katrain.common.resource_utils import find_package_resource
from katrain.gui.kivyutils import I18NSpinner
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Label, Popup


def _get_app_gui() -> Any:
    """アプリのguiインスタンスを安全に取得

    Returns:
        gui instance or None

    Note: KivyMD (MDApp) と Kivy (App) の両方に対応
          将来的な移行を容易にするためヘルパー関数化
    """
    try:
        from kivymd.app import MDApp

        app = MDApp.get_running_app()
    except ImportError:
        from kivy.app import App

        app = App.get_running_app()

    if app is None:
        return None
    return getattr(app, "gui", None)


class I18NPopup(Popup):
    title_key = StringProperty("")
    font_name = StringProperty(Theme.DEFAULT_FONT)
    title_font = StringProperty(Theme.DEFAULT_FONT)
    # クラス変数: 前回のupdate_stateイベント（連続dismiss対策）
    _pending_update_event: Any = None

    def __init__(self, size: list[int] | None = None, **kwargs: Any) -> None:
        if size:  # do not exceed window size
            # v3: sizeをミューテートせず新しいリストを作成
            # Kivyは内部でlistに変換するため、listで渡すのがベストプラクティス
            gui = _get_app_gui()
            if gui:
                size = [min(gui.width, size[0]), min(gui.height, size[1])]
            else:
                # appがNoneの場合は元のsizeをlistに変換（tuple対応）
                size = list(size) if not isinstance(size, list) else size
        super().__init__(size=size, **kwargs)
        self.bind(on_dismiss=self._schedule_update_state)

    def _schedule_update_state(self, popup_instance: Any) -> None:
        """on_dismiss時にupdate_stateをスケジュール（重複防止付き）

        Args:
            popup_instance: Kivyのbindコールバックから渡されるPopupインスタンス

        Note:
            - v5改善: 引数を明示的に受け取る（*argsより安全）
            - Phase 22: 遅延を1秒→0.1秒に短縮、前回イベントをキャンセル
        """
        # 前回のイベントをキャンセル（連続dismiss対策）
        if I18NPopup._pending_update_event is not None:
            I18NPopup._pending_update_event.cancel()
        # 0.1秒後に実行（Kivyのレイアウト計算に十分な余裕）
        I18NPopup._pending_update_event = Clock.schedule_once(self._do_update_state, 0.1)

    def _do_update_state(self, dt: float) -> None:
        """実際のupdate_state呼び出し（nullチェック付き）

        Args:
            dt: Clock.schedule_onceから渡される経過時間（秒）

        Note: アプリ終了中やgui未初期化時は何もしない
        """
        gui = _get_app_gui()
        if gui:
            gui.update_state()


class LabelledTextInput(MDTextField):
    input_property = StringProperty("")
    multiline = BooleanProperty(False)

    @property
    def input_value(self) -> Any:
        return self.text

    @property
    def raw_input_value(self) -> Any:
        return self.text


class LabelledPathInput(LabelledTextInput):
    check_path = BooleanProperty(True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        Clock.schedule_once(self.check_error, 0)

    def check_error(self, _dt: float | None = None) -> None:
        file = find_package_resource(self.input_value, silent_errors=True)
        self.error = self.check_path and not (file and os.path.exists(file))

    def on_text(self, widget: Any, text: str) -> Any:
        self.check_error()
        return super().on_text(widget, text)

    @property
    def input_value(self) -> Any:
        return self.text.strip().replace("\n", " ").replace("\r", " ")


class LabelledCheckBox(MDCheckbox):
    input_property = StringProperty("")

    def __init__(self, text: str | None = None, **kwargs: Any) -> None:
        if text is not None:
            kwargs["active"] = text.lower() == "true"
        super().__init__(**kwargs)

    @property
    def input_value(self) -> bool:
        return bool(self.active)

    def raw_input_value(self) -> Any:
        return self.active


class LabelledSpinner(I18NSpinner):
    input_property = StringProperty("")

    @property
    def input_value(self) -> Any:
        return self.selected[1]  # ref value

    def raw_input_value(self) -> Any:
        return self.text


class LabelledFloatInput(LabelledTextInput):
    input_filter = ObjectProperty("float")

    @property
    def input_value(self) -> float:
        return float(self.text or "0.0")


class LabelledIntInput(LabelledTextInput):
    input_filter = ObjectProperty("int")

    @property
    def input_value(self) -> int:
        return int(self.text or "0")


class LabelledSelectionSlider(BoxLayout):
    input_property = StringProperty("")
    values = ListProperty([(0, "")])  # (value:numeric,label:string) pairs
    key_option = BooleanProperty(False)

    def set_value(self, v: Any) -> None:
        self.slider.set_value(v)
        self.textbox.text = str(v)

    @property
    def input_value(self) -> float:
        if self.textbox.text:
            return float(self.textbox.text)
        return float(self.slider.values[self.slider.index][0])

    @property
    def raw_input_value(self) -> Any:
        return self.textbox.text


class InputParseError(Exception):
    pass


class DescriptionLabel(Label):
    font_name = StringProperty(Theme.DEFAULT_FONT)


def wrap_anchor(widget: Any) -> AnchorLayout:
    anchor = AnchorLayout()
    anchor.add_widget(widget)
    return anchor
