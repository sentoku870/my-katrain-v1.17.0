"""Kivy button classes (resizable, sized, toggle, icon).

Phase 140 P2-2: Extracted from katrain/gui/kivyutils.py.
Phase 277: Reworked for KivyMD 1.2.0 (BaseFlatButton / BasePressedButton were
removed in 1.0.0; the entire button hierarchy is now rooted on
``kivymd.uix.button.BaseButton`` which already provides ripple + a
self-managed background). We keep the same external API and KV rules but
drop the now-defunct KivyMD base classes from the MRO.

Hierarchy:
- SizedButton (base for resizable buttons; KivyMD 1.2.0 ``BaseButton``
  + BackgroundMixin for the rounded-rectangle outline + LeftButtonBehavior
  for click dispatch)
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

from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    OptionProperty,
    StringProperty,
)
from kivy.uix.widget import Widget
from kivymd.uix.behaviors import CircularRippleBehavior
from kivymd.uix.button import BaseButton

from katrain.gui.kivyutils.mixins import BackgroundMixin, LeftButtonBehavior, ToggleButtonMixin
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Button


# -- resizeable buttons / avoid baserectangular for sizing
# Phase 277: KivyMD 1.2.0 removed BaseFlatButton / BasePressedButton and
# collapsed the hierarchy into a single BaseButton. BaseButton already
# extends RectangularRippleBehavior, ThemableBehavior, ButtonBehavior,
# and AnchorLayout, so we no longer need to mix RectangularRippleBehavior
# in explicitly -- only LeftButtonBehavior (for our left-click dispatch
# contract) and BackgroundMixin (for the project's custom rounded-rect
# outline drawn in widgets.kv).
class SizedButton(LeftButtonBehavior, BaseButton, BackgroundMixin):
    text = StringProperty("")
    text_color = ListProperty(Theme.BUTTON_TEXT_COLOR)
    text_size = ListProperty([100, 100])
    halign = OptionProperty("center", options=["left", "center", "right", "justify", "auto"])
    label = ObjectProperty(None)
    padding_x = NumericProperty(6)
    padding_y = NumericProperty(0)
    _font_size = NumericProperty(None)
    font_name = StringProperty(Theme.DEFAULT_FONT)
    # Phase 277: KivyMD 1.2.0 BaseButton defaults theme_text_color to None
    # which is then resolved by each subclass. We rely on text_color being
    # applied explicitly so the button is always rendered in our chosen
    # colour regardless of the subclass defaults.
    theme_text_color = OptionProperty(
        "Custom", options=["Primary", "Secondary", "Hint", "Error", "Custom", "ContrastParentBackground"]
    )


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
