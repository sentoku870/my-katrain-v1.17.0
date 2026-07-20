"""Phase 277: KivyMD 1.2.0 missing .kv files runtime loader.

KivyMD 1.2.0 was released without its companion ``.kv`` files in the
sdist/wheel (the upstream tarball ships only ``.py`` files). Every
``kivymd.uix.<widget>`` module does ``open(os.path.join(uix_path,
"<widget>", "<widget>.kv"))`` at module-import time, which fails with
``FileNotFoundError`` on the first import.

To make ``import kivymd.uix.button`` (etc.) work without forking
KivyMD, we:

1. Pre-create stub ``.kv`` files in a private tempdir that mirrors
   KivyMD's ``uix/<widget>/<widget>.kv`` layout.
2. Override ``kivymd.uix_path`` to point at the tempdir *before* any
   ``kivymd.uix.*`` submodule is imported.

The stub bodies are minimal but enough to let the affected widget
classes register with ``kivy.lang.Builder`` and instantiate. The custom
``<MyNavigationDrawer>`` / ``<MDCard>`` / ``<MDLabel>`` / ``<MDButton>`` /
``<MDTextField>`` rules in our own ``katrain/gui/kv/*.kv`` files take
over once the application loads its own KV strings.

Import order contract:

- This module MUST be imported **after** ``import kivy`` and
  ``import kivymd`` (so the package object exists), but **before** any
  ``from kivymd.uix import ...`` line.

- ``katrain/__main__.py`` imports this module at line ~31 (right after
  ``kivy.require("2.0.0")``, before ``from kivymd.app import MDApp``).

Why a runtime shim rather than a vendored fork?

- KivyMD 1.2.0 is the most recent Material-Design-3 release on PyPI.
  Upstream's tarball bug has been open since 2024-01; we do not want
  to pin to ``master.zip`` (which may carry unrelated API churn).
- The PyInstaller build already has a similar shim in
  ``spec/hook-kivymd.py``. This module is the dev/CI counterpart.

Lifecycle:

- The tempdir is created once per process and reused across tests.
  ``_ensure_kv_stubs()`` is idempotent.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile

__all__ = ["ensure_kivymd_kv_stubs", "uix_path_override"]


_stub_root: str | None = None

# ---------------------------------------------------------------------------
# Stub .kv bodies
# ---------------------------------------------------------------------------
#
# The strings below are intentionally minimal: only the rules and
# properties that the runtime strictly needs. Anything richer would be
# dead weight because the application overrides these widget rules in
# its own ``katrain/gui/kv/*.kv`` files.
#
# Keep this table in sync with the affected KivyMD widget classes. The
# KivyMD source files (``kivymd/uix/<widget>/<widget>.py``) are the
# source of truth; ``grep -l uix_path kivymd/uix`` enumerates them.
_STUB_KV: dict[str, str] = {
    "backdrop/backdrop.kv": "<MDBackdrop>:\n",
    "banner/banner.kv": "<MDBanner>:\n",
    "bottomnavigation/bottomnavigation.kv": "<MDBottomNavigation>:\n",
    "bottomsheet/bottomsheet.kv": "<MDBottomSheet>:\n",
    "button/button.kv": ("<MDButton>:\n    disabled_color: self.theme_cls.disabled_hint_text_color\n"),
    "card/card.kv": ("<MDCard>:\n    elevation: 0\n    md_bg_color: self.theme_cls.bg_light\n"),
    "chip/chip.kv": "<MDChip>:\n",
    "datatables/datatables.kv": "<MDDataTable>:\n",
    "dialog/dialog.kv": "<MDDialog>:\n",
    "dropdownitem/dropdownitem.kv": "<MDDropDownItem>:\n",
    "expansionpanel/expansionpanel.kv": "<MDExpansionPanel>:\n",
    "filemanager/filemanager.kv": "<MDFileManager>:\n",
    "imagelist/imagelist.kv": "<MDSmartTile>:\n",
    "label/label.kv": (
        "<MDLabel>:\n    disabled_color: self.theme_cls.disabled_hint_text_color\n    text_size: self.size\n"
    ),
    "list/list.kv": "<MDList>:\n",
    "menu/menu.kv": "<MDDropdownMenu>:\n",
    "navigationdrawer/navigationdrawer.kv": ("<MDNavigationDrawer>:\n    close_on_click: True\n"),
    "navigationrail/navigationrail.kv": "<MDNavigationRail>:\n",
    "pickers/colorpicker/colorpicker.kv": "<MDColorPicker>:\n",
    "pickers/datepicker/datepicker.kv": "<MDDatePicker>:\n",
    "pickers/timepicker/timepicker.kv": "<MDTimePicker>:\n",
    "progressbar/progressbar.kv": "<MDProgressBar>:\n",
    "refreshlayout/refreshlayout.kv": "<MDRefreshLayout>:\n",
    "segmentedbutton/segmentedbutton.kv": "<MDSegmentedButton>:\n",
    "segmentedcontrol/segmentedcontrol.kv": "<MDSegmentedControl>:\n",
    "selection/selection.kv": "<MDSelection>:\n",
    "selectioncontrol/selectioncontrol.kv": ("<MDCheckbox>:\n    ripple_effect: True\n"),
    "slider/slider.kv": "<MDSlider>:\n",
    "sliverappbar/sliverappbar.kv": "<MDSliverAppBar>:\n",
    "snackbar/snackbar.kv": "<MDSnackbar>:\n",
    "spinner/spinner.kv": "<MDSpinner>:\n",
    "tab/tab.kv": "<MDTabs>:\n",
    "textfield/textfield.kv": ("<MDTextField>:\n    disabled_color: self.theme_cls.disabled_hint_text_color\n"),
    "toolbar/toolbar.kv": "<MDTopAppBar>:\n",
    "tooltip/tooltip.kv": "<MDTooltip>:\n",
    "transition/transition.kv": "<MDScreenTransition>:\n",
}


def _ensure_kv_stubs() -> str:
    """Create stub ``.kv`` files in a tempdir and return its path.

    The function is idempotent: subsequent calls return the same path
    without re-creating files.
    """
    global _stub_root
    if _stub_root is not None and os.path.isdir(_stub_root):
        return _stub_root

    _stub_root = tempfile.mkdtemp(prefix="kivymd_1_2_kv_stubs_")
    for relpath, body in _STUB_KV.items():
        full = os.path.join(_stub_root, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(body)

    def _cleanup() -> None:
        global _stub_root
        if _stub_root is not None:
            shutil.rmtree(_stub_root, ignore_errors=True)
            _stub_root = None

    atexit.register(_cleanup)
    return _stub_root


def ensure_kivymd_kv_stubs() -> str:
    """Patch ``kivymd.uix_path`` to point at the stub tempdir.

    Returns the new ``uix_path`` value. Idempotent.

    Raises:
        ImportError: if ``kivymd`` cannot be imported (very early call).
    """
    import kivymd  # noqa: WPS433 — lazy import is intentional

    stub_root = _ensure_kv_stubs()
    if kivymd.uix_path != stub_root:
        kivymd.uix_path = stub_root
    return stub_root


# Convenience for the rare call site that wants the resolved path
# without forcing the import (e.g. unit tests that mock kivymd).
uix_path_override: str | None = None
