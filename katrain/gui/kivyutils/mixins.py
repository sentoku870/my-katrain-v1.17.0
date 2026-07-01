"""Kivy mixin classes.

Phase 140 P2-2: Extracted from katrain/gui/kivyutils.py.
"""
from __future__ import annotations

from typing import Any

from kivy.properties import ListProperty, NumericProperty
from kivy.uix.behaviors import ButtonBehavior, ToggleButtonBehavior
from kivy.uix.widget import Widget


class BackgroundMixin(Widget):  # -- mixins
    background_color = ListProperty([0, 0, 0, 0])
    background_radius = NumericProperty(0)
    outline_color = ListProperty([0, 0, 0, 0])
    outline_width = NumericProperty(1)


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


class ToggleButtonMixin(ToggleButtonBehavior):
    inactive_outline_color = ListProperty([0.5, 0.5, 0.5, 0])
    active_outline_color = ListProperty([1, 1, 1, 0])
    inactive_background_color = ListProperty([0.5, 0.5, 0.5, 1])
    active_background_color = ListProperty([1, 1, 1, 1])

    @property
    def active(self) -> bool:
        return bool(self.state == "down")
