"""Kivy panel, menu, drawer, layout, and analysis widgets (Phase 144-A split).

Extracted from katrain/gui/kivyutils/widgets.py:
- MenuItem: Ripple-behavior menu item with on_action / on_close events.
- CollapsablePanelHeader: Header bar for CollapsablePanel.
- CollapsablePanelTab: Tab button for CollapsablePanel options.
- CollapsablePanel: Expandable panel with optional tabbed content.
- MyNavigationDrawer: MDNavigationDrawer that closes on outside click.
- AnalysisToggle: Tri-state toggle for analysis options.
- BGBoxLayout: BoxLayout with BackgroundMixin (foundational for Timer etc.).
- ScrollableLabel: ScrollView with label-like text and ref_press event.
"""
from __future__ import annotations

from typing import Any

from kivy.clock import Clock
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, OptionProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivymd.uix.behaviors import RectangularRippleBehavior
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.navigationdrawer import MDNavigationDrawer

from katrain.core.lang import i18n
from katrain.gui.kivyutils.buttons import AutoSizedRectangleToggleButton, TransparentIconButton
from katrain.gui.kivyutils.mixins import BackgroundMixin, LeftButtonBehavior
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Label


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


class MyNavigationDrawer(MDNavigationDrawer):
    def on_touch_down(self, touch: Any) -> Any:
        return super().on_touch_down(touch)

    def on_touch_up(self, touch: Any) -> Any:  # in PR - closes NavDrawer on any outside click
        if self.status == "opened" and self.close_on_click and not self.collide_point(touch.ox, touch.oy):
            self.set_state("close", animation=True)
            return True
        return super().on_touch_up(touch)


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


class BGBoxLayout(BoxLayout, BackgroundMixin):
    pass


class ScrollableLabel(ScrollView, BackgroundMixin):
    __events__ = ["on_ref_press"]
    outline_color = ListProperty([0, 0, 0, 0])  # mixin not working for some reason
    text = StringProperty("")
    line_height = NumericProperty(1)
    markup = BooleanProperty(False)

    def on_ref_press(self, ref: str) -> None:
        pass
