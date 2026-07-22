"""Kivy mixin classes.

Phase 140 P2-2: Extracted from katrain/gui/kivyutils.py.
Phase 287-F: Added ``TooltipMixin`` for long-press tooltips.
"""

from __future__ import annotations

from typing import Any

from kivy.clock import Clock
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior, ToggleButtonBehavior
from kivy.uix.widget import Widget


class BackgroundMixin(Widget):  # -- mixins
    background_color = ListProperty([0, 0, 0, 0])
    background_radius = NumericProperty(0)
    outline_color = ListProperty([0.5, 0.5, 0.5, 0])
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

    def on_press(self) -> None:
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


class TooltipMixin(Widget):
    """Show a floating tooltip after a 500 ms long-press.

    Phase 287-F (UI/UX fixes, Wave C commit 7): the nav buttons along
    the bottom of the main window used to be icon-only. Users had to
    hover for tooltips or memorise icons. KivyMD 1.2.0 removed the
    built-in HoverBehavior, so we implement a long-press trigger:
    press the button, hold 500 ms, the tooltip appears below the
    cursor. Release before 500 ms → normal click behaviour.

    Properties:
        tooltip_text: the message shown in the popup. Empty string
            disables the tooltip entirely (no timer is scheduled).
        tooltip_delay: seconds before the tooltip appears. Default 0.5.
    """

    tooltip_text = StringProperty("")
    tooltip_delay = NumericProperty(0.5)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tooltip_event: Any = None
        self._tooltip_popup: Any = None

    def on_touch_down(self, touch: Any) -> Any:
        # Only schedule a tooltip when the touch lands inside this widget.
        if self.collide_point(*touch.pos) and self.tooltip_text:
            self._cancel_tooltip()
            self._tooltip_event = Clock.schedule_once(self._show_tooltip, self.tooltip_delay)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch: Any) -> Any:
        # Any release cancels the pending tooltip and dismisses the
        # already-visible one. This keeps the existing click behaviour
        # untouched: a quick tap fires the action; a long press shows
        # the tooltip, releasing dismisses it.
        self._cancel_tooltip()
        self._dismiss_tooltip()
        return super().on_touch_up(touch)

    def _cancel_tooltip(self) -> None:
        if self._tooltip_event is not None:
            self._tooltip_event.cancel()
            self._tooltip_event = None

    def _show_tooltip(self, *_args: Any) -> None:
        # Lazy import to avoid loading kivymd tooltip at module-import time.
        try:
            from kivymd.uix.tooltip import MDTooltip
        except ImportError:
            return
        if not self.tooltip_text or not self.get_root_window():
            return
        # Re-use a single popup so we don't leak widgets on repeated long-presses.
        if self._tooltip_popup is None or not self._tooltip_popup.parent:
            self._tooltip_popup = MDTooltip(
                text=self.tooltip_text,
                pos_hint={"center_x": 0.5, "center_y": 0.5},
            )
        else:
            self._tooltip_popup.text = self.tooltip_text
        # Anchor the tooltip below the widget centre.
        self._tooltip_popup.pos = (
            self.center_x - self._tooltip_popup.width / 2,
            self.y - self._tooltip_popup.height - 4,
        )
        if self._tooltip_popup.parent is None:
            self._tooltip_popup.open()

    def _dismiss_tooltip(self) -> None:
        if self._tooltip_popup is not None:
            with __import__("contextlib").suppress(Exception):
                self._tooltip_popup.dismiss()
