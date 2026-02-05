from __future__ import annotations

import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from kivy.clock import Clock
from kivy.core.image import Image
from kivy.core.text import Label as CoreLabel
from kivy.core.text.markup import MarkupLabel as CoreMarkupLabel
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.graphics.texture import Texture
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    OptionProperty,
    StringProperty,
)
from kivy.resources import resource_find

_logger = logging.getLogger(__name__)
from kivy.uix.behaviors import ButtonBehavior, ToggleButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.behaviors import CircularRippleBehavior, RectangularRippleBehavior
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import BaseFlatButton, BasePressedButton
from kivymd.uix.navigationdrawer import MDNavigationDrawer
from kivymd.uix.textfield import MDTextField

from katrain.core.constants import (
    AI_STRATEGIES_RECOMMENDED_ORDER,
    GAME_TYPES,
    MODE_PLAY,
    PLAYER_AI,
    PLAYER_HUMAN,
    PLAYING_NORMAL,
    PLAYING_TEACHING,
)
from katrain.core.lang import i18n
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button, Label


class BackgroundMixin(Widget):  # -- mixins
    background_color = ListProperty([0, 0, 0, 0])
    background_radius = NumericProperty(0)
    outline_color = ListProperty([0, 0, 0, 0])
    outline_width = NumericProperty(1)


class BackgroundLabel(BackgroundMixin, Label):
    pass


class TableCellLabel(Label):
    background_color = ListProperty([0, 0, 0, 0])
    line_width = NumericProperty(0)
    outlines = ListProperty([])
    outline_color = Theme.LINE_COLOR
    outline_width = NumericProperty(1.1)

    def __init__(self, **kwargs: Any) -> None:
        kwargs["font_name"] = kwargs.get("font_name", i18n.font_name)
        super().__init__(**kwargs)


class TableStatLabel(TableCellLabel):
    side = StringProperty("right")
    value = NumericProperty(0)
    scale = NumericProperty(100)
    bar_color = ListProperty([0, 0, 0, 1])

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if "outlines" not in kwargs:
            self.outlines = ["left"] if self.side == "right" else ["right"]


class TableHeaderLabel(TableCellLabel):
    outlines = ["bottom"]


class LeftButtonBehavior(ButtonBehavior):  # stops buttons etc activating on right click
    def __init__(self, **kwargs: Any) -> None:
        self.register_event_type("on_left_release")
        self.register_event_type("on_left_press")
        super().__init__(**kwargs)

    def on_touch_down(self, touch: Any) -> Any:
        return super().on_touch_down(touch)

    def on_release(self) -> Any:
        if not self.last_touch or "button" not in self.last_touch.profile or self.last_touch.button == "left":
            self.dispatch("on_left_release")
        return super().on_release()

    def on_press(self) -> Any:
        if not self.last_touch or "button" not in self.last_touch.profile or self.last_touch.button == "left":
            self.dispatch("on_left_press")
        return super().on_press()

    def on_left_release(self) -> None:
        pass

    def on_left_press(self) -> None:
        pass


# -- resizeable buttons / avoid baserectangular for sizing
class SizedButton(LeftButtonBehavior, RectangularRippleBehavior, BasePressedButton, BaseFlatButton, BackgroundMixin):
    text = StringProperty("")
    text_color = ListProperty(Theme.BUTTON_TEXT_COLOR)
    text_size = ListProperty([100, 100])
    halign = OptionProperty("center", options=["left", "center", "right", "justify", "auto"])
    label = ObjectProperty(None)
    padding_x = NumericProperty(6)
    padding_y = NumericProperty(0)
    _font_size = NumericProperty(None)
    font_name = StringProperty(Theme.DEFAULT_FONT)


class AutoSizedButton(SizedButton):
    pass


class SizedRectangleButton(SizedButton):
    pass


class AutoSizedRectangleButton(AutoSizedButton):
    pass


class ToggleButtonMixin(ToggleButtonBehavior):
    inactive_outline_color = ListProperty([0.5, 0.5, 0.5, 0])
    active_outline_color = ListProperty([1, 1, 1, 0])
    inactive_background_color = ListProperty([0.5, 0.5, 0.5, 1])
    active_background_color = ListProperty([1, 1, 1, 1])

    @property
    def active(self) -> bool:
        return bool(self.state == "down")


class SizedToggleButton(ToggleButtonMixin, SizedButton):
    pass


class SizedRectangleToggleButton(ToggleButtonMixin, SizedRectangleButton):
    pass


class AutoSizedRectangleToggleButton(ToggleButtonMixin, AutoSizedRectangleButton):
    pass


class TransparentIconButton(CircularRippleBehavior, Button):
    color = ListProperty([1, 1, 1, 1])
    icon_size = ListProperty([25, 25])
    icon = StringProperty("")
    disabled = BooleanProperty(False)


class PauseButton(CircularRippleBehavior, LeftButtonBehavior, Widget):
    active = BooleanProperty(True)
    active_line_color = ListProperty([0.5, 0.5, 0.8, 1])
    inactive_line_color = ListProperty([1, 1, 1, 1])
    active_fill_color = ListProperty([0.5, 0.5, 0.5, 1])
    inactive_fill_color = ListProperty([1, 1, 1, 0])
    line_width = NumericProperty(5)
    fill_color = ListProperty([0.5, 0.5, 0.5, 1])
    line_color = ListProperty([0.5, 0.5, 0.5, 1])
    min_size = NumericProperty(100)


# -- basic styles
class LightLabel(Label):
    pass


class StatsLabel(MDBoxLayout):
    text = StringProperty("")
    label = StringProperty("")
    color = ListProperty([1, 1, 1, 1])
    hidden = BooleanProperty(False)
    font_name = StringProperty(Theme.DEFAULT_FONT)


class MyNavigationDrawer(MDNavigationDrawer):
    def on_touch_down(self, touch: Any) -> Any:
        return super().on_touch_down(touch)

    def on_touch_up(self, touch: Any) -> Any:  # in PR - closes NavDrawer on any outside click
        if self.status == "opened" and self.close_on_click and not self.collide_point(touch.ox, touch.oy):
            self.set_state("close", animation=True)
            return True
        return super().on_touch_up(touch)


class CircleWithText(Widget):
    text = StringProperty("0")
    player = OptionProperty("B", options=["B", "W"])
    min_size = NumericProperty(50)


class BGBoxLayout(BoxLayout, BackgroundMixin):
    pass


# --  gui elements


class IMETextField(MDTextField):
    _imo_composition = StringProperty("")
    _imo_cursor = ListProperty(None, allownone=True)

    def _bind_keyboard(self) -> None:
        super()._bind_keyboard()
        Window.bind(on_textedit=self.window_on_textedit)

    def _unbind_keyboard(self) -> None:
        super()._unbind_keyboard()
        Window.unbind(on_textedit=self.window_on_textedit)

    def do_backspace(self, from_undo: bool = False, mode: str = "bkspc") -> Any:
        if self._imo_composition == "":  # IMO handles sub-character backspaces
            return super().do_backspace(from_undo, mode)

    def window_on_textedit(self, window: Any, imo_input: str) -> None:
        text_lines = self._lines
        if self._imo_composition:
            pcc, pcr = self._imo_cursor
            text = text_lines[pcr]
            if text[pcc - len(self._imo_composition) : pcc] == self._imo_composition:  # should always be true
                remove_old_imo_text = text[: pcc - len(self._imo_composition)] + text[pcc:]
                ci = self.cursor_index()
                self._refresh_text_from_property("insert", *self._get_line_from_cursor(pcr, remove_old_imo_text))
                self.cursor = self.get_cursor_from_index(ci - len(self._imo_composition))

        if imo_input:
            if self._selection:
                self.delete_selection()
            cc, cr = self.cursor
            text = text_lines[cr]
            new_text = text[:cc] + imo_input + text[cc:]
            self._refresh_text_from_property("insert", *self._get_line_from_cursor(cr, new_text))
            self.cursor = self.get_cursor_from_index(self.cursor_index() + len(imo_input))
        self._imo_composition = imo_input
        self._imo_cursor = self.cursor


class KeyValueSpinner(Spinner):
    __events__ = ["on_select"]
    sync_height_frac = NumericProperty(1.0)
    value_refs = ListProperty()
    selected_index = NumericProperty(0)
    font_name = StringProperty(Theme.DEFAULT_FONT)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.build_values()
        self.bind(size=self.update_dropdown_props, pos=self.update_dropdown_props, value_refs=self.build_values)

    @property
    def input_value(self) -> Any:
        try:
            return self.value_refs[self.selected_index]
        except KeyError:
            return ""

    @property
    def selected(self) -> tuple[int, Any, Any]:
        try:
            selected = self.selected_index
            return selected, self.value_refs[selected], self.values[selected]
        except (ValueError, IndexError):
            return 0, "", ""

    def on_text(self, _widget: Any, text: str) -> None:
        try:
            new_index = self.values.index(text)
            if new_index != self.selected_index:
                self.selected_index = new_index
                self.dispatch("on_select")
        except (ValueError, IndexError):
            pass

    def on_select(self, *args: Any) -> None:
        pass

    def select_key(self, key: Any) -> None:
        try:
            ix = self.value_refs.index(key)
            self.text = self.values[ix]
        except (ValueError, IndexError):
            pass

    def build_values(self, *_args: Any) -> None:
        if self.value_refs and self.values:
            self.text = self.values[self.selected_index]
            self.font_name = i18n.font_name
            self.update_dropdown_props()

    def update_dropdown_props(self, *largs: Any) -> None:
        if not self.sync_height_frac:
            return
        dp = self._dropdown
        if not dp:
            return
        container = dp.container
        if not container:
            return
        h = self.height
        fsz = self.font_size
        for item in container.children[:]:
            item.height = h * self.sync_height_frac
            item.font_size = fsz
            item.font_name = self.font_name


class I18NSpinner(KeyValueSpinner):
    __events__ = ["on_select"]
    sync_height_frac = NumericProperty(1.0)
    value_refs = ListProperty()
    selected_index = NumericProperty(0)
    font_name = StringProperty(Theme.DEFAULT_FONT)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        MDApp.get_running_app().bind(language=self.build_values)

    def build_values(self, *_args: Any) -> None:
        self.values = [i18n._(ref) for ref in self.value_refs]
        super().build_values()


class PlayerSetup(MDBoxLayout):
    player = OptionProperty("B", options=["B", "W"])
    mode = StringProperty("")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.player_subtype_ai.value_refs = AI_STRATEGIES_RECOMMENDED_ORDER
        self.player_subtype_human.value_refs = GAME_TYPES
        self.setup_options()

    def setup_options(self, *_args: Any) -> None:
        if self.player_type.selected[1] == self.mode:
            return
        self.mode = self.player_type.selected[1]
        self.update_global_player_info()

    @property
    def player_type_dump(self) -> dict[str, Any]:
        if self.mode == PLAYER_AI:
            return {"player_type": self.player_type.selected[1], "player_subtype": self.player_subtype_ai.selected[1]}
        else:
            return {
                "player_type": self.player_type.selected[1],
                "player_subtype": self.player_subtype_human.selected[1],
            }

    def update_widget(self, player_type: str, player_subtype: str) -> None:
        self.player_type.select_key(player_type)  # should trigger setup options
        if self.mode == PLAYER_AI:
            self.player_subtype_ai.select_key(player_subtype)  # should trigger setup options
        else:
            self.player_subtype_human.select_key(player_subtype)  # should trigger setup options

    def update_global_player_info(self) -> None:
        if self.parent and self.parent.update_global:
            katrain = MDApp.get_running_app().gui
            if katrain.game and katrain.game.current_node:
                katrain.update_player(self.player, **self.player_type_dump)


class PlayerSetupBlock(MDBoxLayout):
    players = ObjectProperty(None)
    black = ObjectProperty(None)
    white = ObjectProperty(None)
    update_global = BooleanProperty(False)
    INSTANCES: list[Any] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.black = PlayerSetup(player="B")
        self.white = PlayerSetup(player="W")
        self.players = {"B": self.black, "W": self.white}
        self.add_widget(self.black)
        self.add_widget(self.white)
        PlayerSetupBlock.INSTANCES.append(self)

    def swap_players(self) -> None:
        player_dump = {bw: p.player_type_dump for bw, p in self.players.items()}
        for bw in "BW":
            self.update_player_params(bw, player_dump["B" if bw == "W" else "W"])

    def update_player_params(self, bw: str, params: dict[str, Any]) -> None:
        self.players[bw].update_widget(**params)

    def update_player_info(self, bw: str, player_info: Any) -> None:  # update sub widget based on gui state change
        Clock.schedule_once(
            lambda _dt: self.players[bw].update_widget(
                player_type=player_info.player_type, player_subtype=player_info.player_subtype
            ),
            -1,
        )


class PlayerInfo(MDBoxLayout, BackgroundMixin):
    captures = ObjectProperty(0)
    player = OptionProperty("B", options=["B", "W"])
    player_type = StringProperty("Player")
    komi = NumericProperty(0)
    player_subtype = StringProperty("")
    name = StringProperty("", allownone=True)
    rank = StringProperty("", allownone=True)
    active = BooleanProperty(True)
    alignment = StringProperty("right")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.bind(player_type=self.set_label, player_subtype=self.set_label, name=self.set_label, rank=self.set_label)

    def set_label(self, *args: Any) -> None:
        if not self.subtype_label:  # building
            return
        show_player_name = self.name and self.player_type == PLAYER_HUMAN and self.player_subtype == PLAYING_NORMAL
        text = self.name if show_player_name else i18n._(self.player_subtype)
        if (
            self.rank
            and self.player_subtype != PLAYING_TEACHING
            and (show_player_name or self.player_type == PLAYER_AI)
        ):
            text += f" ({self.rank})"
        self.subtype_label.text = text


class TimerOrMoveTree(MDBoxLayout):
    mode = StringProperty(MODE_PLAY)


class Timer(BGBoxLayout):
    state = ListProperty([30, 5, 1])
    timeout = BooleanProperty(False)


class AnalysisToggle(MDBoxLayout):
    text = StringProperty("")
    default_active = BooleanProperty(False)
    font_name = StringProperty(Theme.DEFAULT_FONT)
    disabled = BooleanProperty(False)
    tri_state = BooleanProperty(False)

    def trigger_action(self, *args: Any, **kwargs: Any) -> Any:
        return self.checkbox._do_press()

    def activate(self, *_args: Any) -> None:
        self.checkbox.active = True

    @property
    def active(self) -> bool:
        return bool(self.checkbox.active)


class MenuItem(RectangularRippleBehavior, LeftButtonBehavior, MDBoxLayout, BackgroundMixin):
    __events__ = ["on_action", "on_close"]
    icon = StringProperty("")
    text = StringProperty("")
    shortcut = StringProperty("")
    font_name = StringProperty(Theme.DEFAULT_FONT)
    content_width = NumericProperty(100)

    def on_left_release(self) -> None:
        self.anim_complete()  # kill ripple
        self.dispatch("on_close")
        self.dispatch("on_action")

    def on_action(self) -> None:
        pass

    def on_close(self) -> None:
        pass


class CollapsablePanelHeader(MDBoxLayout):
    pass


class CollapsablePanelTab(AutoSizedRectangleToggleButton):
    pass


class CollapsablePanel(MDBoxLayout):
    __events__ = ["on_option_state"]

    options = ListProperty([])
    options_height = NumericProperty(25)
    content_height = NumericProperty(100)
    size_hint_y_open = NumericProperty(None)  # total height inc tabs, overrides content_height
    options_spacing = NumericProperty(6)
    option_labels = ListProperty([])
    option_active = ListProperty([])
    option_colors = ListProperty([])

    contents = ListProperty([])

    closed_label = StringProperty("Closed Panel")

    state = OptionProperty("open", options=["open", "close"])
    close_icon = "Previous-5.png"
    open_icon = "Next-5.png"

    def __init__(self, **kwargs: Any) -> None:
        self.open_close_button: Any = None
        self.header: Any = None
        self.option_buttons: list[Any] = []
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.bind(
            options=self.build_options,
            option_colors=self.build_options,
            options_height=self.build_options,
            option_active=self.build_options,
            options_spacing=self.build_options,
        )
        self.bind(state=self._on_state, content_height=self._on_size, options_height=self._on_size)
        MDApp.get_running_app().bind(language=lambda *_: Clock.schedule_once(self.build_options, 0))
        self.build_options()

    def _on_state(self, *_args: Any) -> None:
        self.build()
        self.trigger_select(ix=None)

    def _on_size(self, *_args: Any) -> None:
        height, size_hint_y = 1, None
        if self.state == "open" and self.contents:
            if self.size_hint_y_open is not None:
                size_hint_y = self.size_hint_y_open
            else:
                height = self.content_height + self.options_height
        else:
            height = self.header.height
        self.height, self.size_hint_y = height, size_hint_y

    @property
    def option_state(self) -> dict[str, bool]:
        return {option: active for option, active in zip(self.options, self.option_active, strict=False)}

    def set_option_state(self, state_dict: dict[str, bool]) -> None:
        for ix, (option, button) in enumerate(zip(self.options, self.option_buttons, strict=False)):
            if option in state_dict:
                self.option_active[ix] = state_dict[option]
                button.state = "down" if state_dict[option] else "normal"
        self.trigger_select(ix=None)

    def build_options(self, *args: Any) -> None:
        self.header = CollapsablePanelHeader(
            height=self.options_height, size_hint_y=None, spacing=self.options_spacing, padding=[1, 0, 0, 0]
        )
        self.option_buttons = []
        option_labels = self.option_labels or [i18n._(f"tab:{opt}") for opt in self.options]
        for ix, (lbl, opt_col, active) in enumerate(
            zip(option_labels, self.option_colors, self.option_active, strict=False)
        ):
            button = CollapsablePanelTab(
                text=lbl,
                font_name=i18n.font_name,
                active_outline_color=opt_col,
                height=self.options_height,
                state="down" if active else "normal",
            )
            self.option_buttons.append(button)
            button.bind(state=lambda *_args, _ix=ix: self.trigger_select(_ix))
        self.open_close_button = TransparentIconButton(  # <<  / >> collapse button
            icon=self.open_close_icon(),
            icon_size=[0.5 * self.options_height, 0.5 * self.options_height],
            width=0.75 * self.options_height,
            size_hint_x=None,
            on_press=lambda *_args: self.set_state("toggle"),
        )
        self.bind(state=lambda *_args: self.open_close_button.setter("icon")(None, self.open_close_icon()))
        self.build()

    def build(self, *args: Any) -> None:
        self.header.clear_widgets()
        if self.state == "open":
            for button in self.option_buttons:
                self.header.add_widget(button)
            self.header.add_widget(Label())  # spacer
        else:
            self.header.add_widget(
                Label(
                    text=i18n._(self.closed_label), font_name=i18n.font_name, halign="right", height=self.options_height
                )
            )
        self.header.add_widget(self.open_close_button)

        super().clear_widgets()
        super().add_widget(self.header)
        if self.state == "open" and self.contents:
            for w in self.contents:
                super().add_widget(w)
        self._on_size()

    def open_close_icon(self) -> str:
        return self.open_icon if self.state == "open" else self.close_icon

    def add_widget(self, widget: Any, index: int = 0, **_kwargs: Any) -> None:
        self.contents.append(widget)
        self.build()

    def set_state(self, state: str = "toggle") -> None:
        if state == "toggle":
            state = "close" if self.state == "open" else "open"
        self.state = state
        self.build()
        if self.state == "open":
            self.trigger_select(ix=None)

    def trigger_select(self, ix: int | None) -> bool:
        if ix is not None and self.option_buttons:
            self.option_active[ix] = self.option_buttons[ix].state == "down"
        if self.state == "open":
            self.dispatch(
                "on_option_state",
                {opt: btn.active for opt, btn in zip(self.options, self.option_buttons, strict=False)},
            )
        return False

    def on_option_state(self, options: dict[str, bool]) -> None:
        pass


class StatsBox(MDBoxLayout, BackgroundMixin):
    winrate = StringProperty("...")
    score = StringProperty("...")
    points_lost = NumericProperty(None, allownone=True)
    player = StringProperty("")


class ClickableLabel(LeftButtonBehavior, Label):
    pass


class ClickableCircle(LeftButtonBehavior, CircleWithText):
    pass


class ScrollableLabel(ScrollView, BackgroundMixin):
    __events__ = ["on_ref_press"]
    outline_color = ListProperty([0, 0, 0, 0])  # mixin not working for some reason
    text = StringProperty("")
    line_height = NumericProperty(1)
    markup = BooleanProperty(False)

    def on_ref_press(self, ref: str) -> None:
        pass


def _make_hashable(value: Any) -> Any:
    """kwargs値をhashableに変換（list/dict/set/tuple対応）

    v4: エッジケース対策
    - tuple: そのまま返す（既にhashable）
    - set: sorted tupleに変換
    - numpy配列/カスタムオブジェクト: repr()でフォールバック（サイズ制限付き）
    """
    if isinstance(value, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in value.items()))
    elif isinstance(value, list):
        return tuple(_make_hashable(v) for v in value)
    elif isinstance(value, set):
        # v4: setをsorted tupleに変換（要素がcomparableな場合のみ）
        try:
            return tuple(sorted(_make_hashable(v) for v in value))
        except TypeError:
            return tuple(_make_hashable(v) for v in value)
    elif isinstance(value, tuple):
        # v4: tupleはそのまま（既にhashable、ネストは再帰処理）
        return tuple(_make_hashable(v) for v in value)
    # v4: その他のオブジェクト（numpy配列等）はrepr()でフォールバック
    try:
        hash(value)
        return value
    except TypeError:
        # unhashableな場合はrepr()で文字列化（サイズ制限）
        repr_str = repr(value)
        if len(repr_str) > 200:
            repr_str = repr_str[:200] + "..."
        return f"__unhashable__:{type(value).__name__}:{repr_str}"


@lru_cache(maxsize=500)
def _create_text_texture(text: str, resolved_font_name: str, markup: bool, kwargs_tuple: tuple[Any, ...]) -> Any:
    """LRU制限付きテクスチャ生成（内部用）

    Args:
        resolved_font_name: 解決済みのフォント名（Noneは許可しない）
    """
    kwargs = dict(kwargs_tuple)
    label_cls = CoreMarkupLabel if markup else CoreLabel
    label = label_cls(text=text, bold=True, font_name=resolved_font_name, **kwargs)
    label.refresh()
    return label.texture


def cached_text_texture(text: str, font_name: str | None, markup: bool, **kwargs: Any) -> Any:
    """互換性維持のラッパー（API変更なし）

    Note: Kivyの描画はメインスレッドのみなのでスレッドセーフは不要
    """
    # v3: font_nameをキャッシュ前に解決（言語変更時のキャッシュ問題を回避）
    # v5: i18n.font_nameがNoneの場合のフォールバック追加
    resolved_font_name = font_name if font_name else (i18n.font_name or "Roboto")
    # kwargsをhashableなtupleに変換（list/dict値も対応）
    kwargs_tuple = tuple(sorted((k, _make_hashable(v)) for k, v in kwargs.items()))
    return _create_text_texture(text, resolved_font_name, markup, kwargs_tuple)


def draw_text(
    pos: Sequence[float], text: str, font_name: str | None = None, markup: bool = False, **kwargs: Any
) -> None:
    texture = cached_text_texture(text, font_name, markup, **kwargs)
    Rectangle(texture=texture, pos=(pos[0] - texture.size[0] / 2, pos[1] - texture.size[1] / 2), size=texture.size)


def draw_circle(pos: Sequence[float], r: float, col: Sequence[float]) -> None:
    Color(*col)
    Ellipse(pos=(pos[0] - r, pos[1] - r), size=(2 * r, 2 * r))


# v5: フォールバックテクスチャをシングルトン化（毎回作成を避ける）
_fallback_texture = None


def _get_fallback_texture() -> Any:
    """1x1透明フォールバックテクスチャを取得（シングルトン）"""
    global _fallback_texture
    if _fallback_texture is None:
        _fallback_texture = Texture.create(size=(1, 1))
        _fallback_texture.blit_buffer(b"\x00\x00\x00\x00", colorfmt="rgba")
    return _fallback_texture


# v5: ログは関数外で管理（lru_cache内でログを呼ばない）
_missing_resources: set[str] = set()


@lru_cache(maxsize=100)
def cached_texture(path: str) -> Any:
    """画像テクスチャのLRUキャッシュ

    Args:
        path: リソースパス

    Returns:
        テクスチャ（成功時）またはフォールバックテクスチャ（失敗時）

    Note: v4変更 - FileNotFoundErrorを内部で処理しフォールバック返却
          呼び出し元（badukpan.py 8箇所）はすべてTexture前提のため、
          例外を投げずに1x1透明テクスチャをフォールバックとして返す
    Note: v5変更 - フォールバックをシングルトン化、ログスパム防止
    """
    resolved = resource_find(path)
    if resolved is None:
        # v5: 同じパスは一度だけログ出力（スパム防止）
        if path not in _missing_resources:
            _missing_resources.add(path)
            _logger.error(f"Resource not found: {path!r} - returning fallback texture")
        return _get_fallback_texture()
    return Image(resolved).texture


def clear_texture_caches() -> None:
    """テクスチャキャッシュをクリア（言語変更時に呼び出す）

    Note: i18n.set_language()等から呼び出すことで、
          古いフォントのテクスチャがメモリに残り続けることを防ぐ
    """
    _create_text_texture.cache_clear()
    _logger.debug("Text texture cache cleared")
