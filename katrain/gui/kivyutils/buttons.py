"""Kivy button classes (resizable, sized, toggle, icon).

Phase 140 P2-2: Extracted from katrain/gui/kivyutils.py.

Hierarchy:
- SizedButton (base for resizable buttons)
  - AutoSizedButton
  - SizedRectangleButton
    - AutoSizedRectangleButton
- SizedToggleButton (ToggleButtonMixin + SizedButton)
- SizedRectangleToggleButton (ToggleButtonMixin + SizedRectangleButton)
- AutoSizedRectangleToggleButton (ToggleButtonMixin + AutoSizedRectangleButton)
- TransparentIconButton
- PauseButton
"""
from __future__ import annotations

from typing import Any

from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, OptionProperty, StringProperty
from kivy.uix.widget import Widget
from kivymd.uix.behaviors import CircularRippleBehavior, RectangularRippleBehavior
from kivymd.uix.button import BaseFlatButton, BasePressedButton

from katrain.gui.kivyutils.mixins import BackgroundMixin, LeftButtonBehavior, ToggleButtonMixin
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button


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
