"""Widgets package - uses lazy imports to avoid triggering Kivy initialization."""

from __future__ import annotations

from typing import Any

__all__ = ["ScoreGraph", "MoveTree", "I18NFileBrowser", "SelectionSlider"]

# Lazy loading to avoid Kivy initialization when importing non-Kivy modules
# like radar_geometry.py


def __getattr__(name: str) -> Any:
    """Lazy load Kivy-dependent widgets on first access."""
    if name == "ScoreGraph":
        from katrain.gui.widgets.graph import ScoreGraph

        return ScoreGraph
    if name == "MoveTree":
        from katrain.gui.widgets.movetree import MoveTree

        return MoveTree
    if name == "I18NFileBrowser":
        from katrain.gui.widgets.filebrowser import I18NFileBrowser

        return I18NFileBrowser
    if name == "SelectionSlider":
        from katrain.gui.widgets.selection_slider import SelectionSlider

        return SelectionSlider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
