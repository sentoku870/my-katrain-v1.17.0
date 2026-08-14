"""Kivy mixin classes.

Phase 140 P2-2: Extracted from katrain/gui/kivyutils.py.
Phase 287-F: Added ``TooltipMixin`` for long-press tooltips.
Phase 296: ``TooltipMixin`` rebuilt on vanilla Kivy ``Label`` + ``Window``
because KivyMD 1.2.0's ``MDTooltip`` is a *behavior mixin* (combined with
a button widget), not a standalone popup. Calling
``MDTooltip(text=..., pos_hint=...)`` raises TypeError; the class has
no ``text`` or ``pos_hint`` property and no ``open`` / ``dismiss``.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from kivy.clock import Clock
from kivy.core.window import Window
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


class TooltipMixin(Widget):
    """Show a floating tooltip after a 500 ms long-press.

    Phase 287-F (UI/UX fixes, Wave C commit 7): the nav buttons along
    the bottom of the main window used to be icon-only. Users had to
    hover for tooltips or memorise icons. KivyMD 1.2.0 removed the
    built-in HoverBehavior, so we implement a long-press trigger:
    press the button, hold 500 ms, the tooltip appears below the
    widget. Release before 500 ms → normal click behaviour.

    Phase 296: KivyMD 1.2.0's ``MDTooltip`` is a behavior mixin (combined
    with a widget class via multiple inheritance), not a standalone popup.
    We therefore build a vanilla Kivy ``Label`` + canvas-drawn background
    and attach it directly to the ``Window`` instead.

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
        if not self.tooltip_text or not self.get_root_window():
            return
        # Re-use a single popup so we don't leak widgets on repeated long-presses.
        if self._tooltip_popup is None or not self._tooltip_popup.parent:
            self._build_tooltip_popup()
        popup = self._tooltip_popup
        popup.text = self.tooltip_text
        # Force the texture to refresh so texture_size reflects the
        # latest text and we can size the popup synchronously below.
        popup.texture_update()
        pad_x, pad_y = 16, 8
        popup.size = (popup.texture_size[0] + pad_x, popup.texture_size[1] + pad_y)
        # Anchor the tooltip below the widget centre.
        popup.pos = (
            self.center_x - popup.width / 2,
            self.y - popup.height - 4,
        )
        if popup.parent is None:
            Window.add_widget(popup)

    def _build_tooltip_popup(self) -> None:
        """Create a vanilla Kivy Label-based tooltip popup.

        We avoid ``kivymd.uix.tooltip.MDTooltip`` because in 1.2.0 it is
        a behavior mixin, not a popup widget: it has no ``text`` /
        ``pos_hint`` properties and no ``open`` / ``dismiss`` methods.
        A plain ``Label`` with a canvas-drawn opaque background is
        portable across KivyMD versions and keeps the long-press API
        identical.
        """
        from kivy.graphics import Color, Rectangle
        from kivy.uix.label import Label

        popup = Label(
            text=self.tooltip_text,
            color=(1, 1, 1, 1),
            font_size="12sp",
            size_hint=(None, None),
        )
        with popup.canvas.before:
            Color(0, 0, 0, 0.85)
            popup._tooltip_bg = Rectangle(pos=popup.pos, size=popup.size)
        popup.bind(
            pos=lambda inst, val: setattr(inst._tooltip_bg, "pos", val),
            size=lambda inst, val: setattr(inst._tooltip_bg, "size", val),
        )
        self._tooltip_popup = popup

    def _dismiss_tooltip(self) -> None:
        if self._tooltip_popup is not None:
            with suppress(Exception):
                Window.remove_widget(self._tooltip_popup)
