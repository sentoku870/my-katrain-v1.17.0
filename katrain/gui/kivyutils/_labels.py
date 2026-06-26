"""Kivy label and stats-display widgets (Phase 144-A split).

Extracted from katrain/gui/kivyutils/widgets.py:
- TableCellLabel: Base label for table cells with optional outlines.
- TableStatLabel: Numeric value label with a side bar indicator.
- TableHeaderLabel: Table header label with bottom outline.
- StatsLabel: Text label box for statistics.
- StatsBox: Box layout for winrate/score display.
"""
from __future__ import annotations

from typing import Any

from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivymd.uix.boxlayout import MDBoxLayout

from katrain.core.lang import i18n
from katrain.gui.kivyutils.mixins import BackgroundMixin
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Label


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


class StatsLabel(MDBoxLayout):
    text = StringProperty("")
    label = StringProperty("")
    color = ListProperty([1, 1, 1, 1])
    hidden = BooleanProperty(False)
    font_name = StringProperty(Theme.DEFAULT_FONT)


class StatsBox(MDBoxLayout, BackgroundMixin):
    winrate = StringProperty("...")
    score = StringProperty("...")
    points_lost = NumericProperty(None, allownone=True)
    player = StringProperty("")
