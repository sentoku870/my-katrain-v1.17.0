"""Settings popup tab builders (Phase 175).

This package is structured for per-tab file separation. Each tab is its
own submodule loaded lazily to defer Kivy initialization:

- ``analysis_tab``: Analysis settings tab (Tab 1)
- ``export_tab``: Export settings tab (Tab 2)
- ``kifunarabe_tab``: Kifunarabe (棋譜並べ) folder settings (Tab 3, Phase 177)
- ``diagnostics_tab``: Diagnostics tab (Tab 4, Phase 230-D)

Callers should use the lazy ``__getattr__`` re-export (see below) so
that importing the package itself does NOT eagerly load Kivy. This is
required by Phase 174 P1-B (import-resolution regression tests) and
keeps ``tests/test_import_resolution.py`` green.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "_build_analysis_tab",
    "_build_export_tab",
    "_build_kifunarabe_tab",
    "_build_diagnostics_tab",
]


def __getattr__(name: str) -> Any:
    if name == "_build_analysis_tab":
        from katrain.gui.features.settings_popup_tabs.analysis_tab import _build_analysis_tab

        return _build_analysis_tab
    if name == "_build_export_tab":
        from katrain.gui.features.settings_popup_tabs.export_tab import _build_export_tab

        return _build_export_tab
    if name == "_build_kifunarabe_tab":
        from katrain.gui.features.settings_popup_tabs.kifunarabe_tab import _build_kifunarabe_tab

        return _build_kifunarabe_tab
    if name == "_build_diagnostics_tab":
        from katrain.gui.features.settings_popup_tabs.diagnostics_tab import _build_diagnostics_tab

        return _build_diagnostics_tab
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    from katrain.gui.features.settings_popup_tabs.analysis_tab import _build_analysis_tab as _build_analysis_tab
    from katrain.gui.features.settings_popup_tabs.diagnostics_tab import (
        _build_diagnostics_tab as _build_diagnostics_tab,
    )
    from katrain.gui.features.settings_popup_tabs.export_tab import _build_export_tab as _build_export_tab
    from katrain.gui.features.settings_popup_tabs.kifunarabe_tab import (
        _build_kifunarabe_tab as _build_kifunarabe_tab,
    )
