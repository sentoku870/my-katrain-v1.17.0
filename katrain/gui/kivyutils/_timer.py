"""Kivy timer and move-tree widgets (Phase 144-A split).

Extracted from katrain/gui/kivyutils/widgets.py:
- TimerOrMoveTree: Layout that switches between timer and move tree view.
- Timer: BGBoxLayout-based timer display with state and timeout.
"""
from __future__ import annotations

from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivymd.uix.boxlayout import MDBoxLayout

from katrain.core.constants import MODE_PLAY
from katrain.gui.kivyutils._panels import BGBoxLayout


class TimerOrMoveTree(MDBoxLayout):
    mode = StringProperty(MODE_PLAY)


class Timer(BGBoxLayout):
    state = ListProperty([30, 5, 1])
    timeout = BooleanProperty(False)
