"""Kivy custom widgets package.

Phase 140 P2-2: Extracted from katrain/gui/kivyutils.py (743 lines) into a
focused package of 4 submodules:

- _base.py: common imports, module-level state (_fallback_texture,
  _missing_resources), free functions (cached_text_texture, draw_text,
  draw_circle, cached_texture, clear_texture_caches, _make_hashable,
  _create_text_texture, _get_fallback_texture)
- mixins.py: 3 mixin classes (BackgroundMixin, LeftButtonBehavior,
  ToggleButtonMixin)
- buttons.py: 9 button classes (SizedButton, AutoSizedButton,
  SizedRectangleButton, AutoSizedRectangleButton, SizedToggleButton,
  SizedRectangleToggleButton, AutoSizedRectangleToggleButton,
  TransparentIconButton, PauseButton)
- _labels.py / _spinners.py / _player.py / _timer.py / _panels.py /
  _clickables.py: 23 widget classes split by concern (Phase 144-A).

This __init__.py re-exports all public names for backward compatibility
with existing `from katrain.gui.kivyutils import X` imports.
"""
from __future__ import annotations

from katrain.gui.kivyutils._base import (
    _create_text_texture,
    _fallback_texture,
    _get_fallback_texture,
    _make_hashable,
    _missing_resources,
    cached_text_texture,
    cached_texture,
    clear_texture_caches,
    draw_circle,
    draw_text,
)
from katrain.gui.kivyutils._clickables import (
    CircleWithText,
    ClickableCircle,
    ClickableLabel,
)
from katrain.gui.kivyutils._labels import (
    StatsBox,
    StatsLabel,
    TableCellLabel,
    TableHeaderLabel,
    TableStatLabel,
)
from katrain.gui.kivyutils._panels import (
    AnalysisToggle,
    BGBoxLayout,
    CollapsablePanel,
    CollapsablePanelHeader,
    CollapsablePanelTab,
    MenuItem,
    MyNavigationDrawer,
    ScrollableLabel,
)
from katrain.gui.kivyutils._player import (
    PlayerInfo,
    PlayerSetup,
    PlayerSetupBlock,
)
from katrain.gui.kivyutils._spinners import (
    I18NSpinner,
    KeyValueSpinner,
)
from katrain.gui.kivyutils._timer import (
    Timer,
    TimerOrMoveTree,
)
from katrain.gui.kivyutils.buttons import (
    AutoSizedButton,
    AutoSizedRectangleButton,
    AutoSizedRectangleToggleButton,
    PauseButton,
    SizedButton,
    SizedRectangleButton,
    SizedRectangleToggleButton,
    SizedToggleButton,
    TransparentIconButton,
)
from katrain.gui.kivyutils.mixins import (
    BackgroundMixin,
    LeftButtonBehavior,
    ToggleButtonMixin,
)

__all__ = [
    # Base
    "_create_text_texture",
    "_fallback_texture",
    "_get_fallback_texture",
    "_make_hashable",
    "_missing_resources",
    "cached_text_texture",
    "cached_texture",
    "clear_texture_caches",
    "draw_circle",
    "draw_text",
    # Mixins
    "BackgroundMixin",
    "LeftButtonBehavior",
    "ToggleButtonMixin",
    # Buttons
    "AutoSizedButton",
    "AutoSizedRectangleButton",
    "AutoSizedRectangleToggleButton",
    "PauseButton",
    "SizedButton",
    "SizedRectangleButton",
    "SizedRectangleToggleButton",
    "SizedToggleButton",
    "TransparentIconButton",
    # Widgets - Labels
    "TableCellLabel",
    "TableStatLabel",
    "TableHeaderLabel",
    "StatsLabel",
    "StatsBox",
    # Widgets - Spinners
    "KeyValueSpinner",
    "I18NSpinner",
    # Widgets - Player
    "PlayerSetup",
    "PlayerSetupBlock",
    "PlayerInfo",
    # Widgets - Timer
    "TimerOrMoveTree",
    "Timer",
    # Widgets - Panels / Layouts
    "MenuItem",
    "CollapsablePanelHeader",
    "CollapsablePanelTab",
    "CollapsablePanel",
    "MyNavigationDrawer",
    "AnalysisToggle",
    "BGBoxLayout",
    "ScrollableLabel",
    # Widgets - Clickables
    "CircleWithText",
    "ClickableLabel",
    "ClickableCircle",
]
