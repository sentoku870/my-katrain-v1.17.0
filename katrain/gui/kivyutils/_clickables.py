"""Kivy clickable widgets (Phase 144-A split).

Extracted from katrain/gui/kivyutils/widgets.py:
- CircleWithText: Circular widget displaying a single character (e.g. move letter).
- ClickableLabel: Label with LeftButtonBehavior (clickable).
- ClickableCircle: CircleWithText with LeftButtonBehavior (clickable).
"""
from __future__ import annotations

from kivy.properties import NumericProperty, OptionProperty, StringProperty
from kivy.uix.widget import Widget

from katrain.gui.kivyutils.mixins import LeftButtonBehavior
from katrain.gui.widgets.factory import Label


class CircleWithText(Widget):
    text = StringProperty("0")
    player = OptionProperty("B", options=["B", "W"])
    min_size = NumericProperty(50)


class ClickableLabel(LeftButtonBehavior, Label):
    pass


class ClickableCircle(LeftButtonBehavior, CircleWithText):
    pass
