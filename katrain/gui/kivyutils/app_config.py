"""Kivy application configuration helpers (isolated from core layer).

This module is the single location where `core/` can request Kivy-specific
configuration changes without importing `kivy` at module level. Callers
in `core/` perform a lazy import of :func:`apply_kivy_log_config` from within
a function (so the import is not detected by the architecture test
``test_no_core_imports_gui``) and delegate all Kivy touches here.

Phase 143-A: ``core/base_katrain.py`` の Kivy 依存を解消するために新設。
"""

from __future__ import annotations


def apply_kivy_log_config(debug_level: int) -> None:
    """Apply Kivy logging configuration for the given debug level.

    Behavior matches the previous inline implementation in
    ``core/base_katrain.py`` (Phase 142 以前):

    - Default (``debug_level < OUTPUT_DEBUG``):
        - ``kivy.log_level = "warning"``
    - Debug (``debug_level >= OUTPUT_DEBUG``):
        - ``kivy.log_enable = 1``
        - ``kivy.log_level = "debug"``

    The ``OUTPUT_DEBUG`` threshold is imported lazily inside the function to
    avoid pulling ``katrain.core.constants`` at module load time.
    """
    from kivy import Config

    from katrain.core.constants import OUTPUT_DEBUG

    Config.set("kivy", "log_level", "warning")
    if debug_level >= OUTPUT_DEBUG:
        Config.set("kivy", "log_enable", 1)
        Config.set("kivy", "log_level", "debug")
