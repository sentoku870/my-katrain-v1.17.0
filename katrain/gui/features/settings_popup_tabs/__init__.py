"""Settings popup tab builders (Phase 145-D+).

This package is structured for per-tab file separation. Each tab is its
own submodule loaded lazily to defer Kivy initialization:

- ``leela_tab``: Leela Zero engine tab (Tab 3)

Callers should use the lazy ``__getattr__`` re-export (see below) so
that importing the package itself does NOT eagerly load Kivy. This is
required by Phase 146 (kivy headless smoke tests).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["_build_leela_tab"]


def __getattr__(name: str) -> Any:
    if name == "_build_leela_tab":
        from katrain.gui.features.settings_popup_tabs.leela_tab import _build_leela_tab

        return _build_leela_tab
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    from katrain.gui.features.settings_popup_tabs.leela_tab import _build_leela_tab as _build_leela_tab
