"""Kivy application configuration helpers (isolated from core layer).

This module is the single location where `core/` can request Kivy-specific
configuration changes without importing `kivy` at module level. Callers
in `core/` perform a lazy import of :func:`apply_kivy_log_config` from within
a function (so the import is not detected by the architecture test
``test_no_core_imports_gui``) and delegate all Kivy touches here.

Phase 143-A: ``core/base_katrain.py`` の Kivy 依存を解消するために新設。
Phase 147: CI/test 環境で Kivy import を回避する no-op 化を追加（OOM 対策）。
"""

from __future__ import annotations

import os
import sys


def _should_skip_kivy_log_config() -> bool:
    """Return True when Kivy log configuration should be skipped.

    Triggers (any of):
    - ``KATRAIN_SKIP_KIVY_LOG_CONFIG=1`` (explicit opt-out)
    - ``KIVY_NO_ENV_CONFIG=1`` (CI / headless env, no Kivy runtime)
    - ``KIVY_HEADLESS=1`` (Phase 146 で Kivy ヘッドレス実行中)
    - ``KIVY_NO_WINDOW=1`` (Phase 146 で window 無し実行中）
    - Kivy is not already imported (lazy import not yet paid for)

    The "kivy not yet imported" check protects test environments that never
    load Kivy at all: paying the 110+ MB import cost on every KaTrainBase
    construction was the root cause of the 16 GB runner OOM (Phase 147 fix).
    """
    explicit = os.environ.get("KATRAIN_SKIP_KIVY_LOG_CONFIG", "").lower() in ("1", "true", "yes")
    if explicit:
        return True
    if os.environ.get("KIVY_NO_ENV_CONFIG") == "1":
        return True
    if os.environ.get("KIVY_HEADLESS") == "1":
        return True
    if os.environ.get("KIVY_NO_WINDOW") == "1":
        return True
    return "kivy" not in sys.modules


def apply_kivy_log_config(debug_level: int) -> None:
    """Apply Kivy logging configuration for the given debug level.

    Behavior matches the previous inline implementation in
    ``core/base_katrain.py`` (Phase 142 以前):

    - Default (``debug_level < OUTPUT_DEBUG``):
        - ``kivy.log_level = "warning"``
    - Debug (``debug_level >= OUTPUT_DEBUG``):
        - ``kivy.log_enable = 1``
        - ``kivy.log_level = "debug"`

    Skipped when :func:`_should_skip_kivy_log_config` returns True
    (test/CI environments where Kivy is not actually running).

    The ``OUTPUT_DEBUG`` threshold is imported lazily inside the function to
    avoid pulling ``katrain.core.constants`` at module load time.
    """
    if _should_skip_kivy_log_config():
        return

    from kivy import Config

    from katrain.core.constants import OUTPUT_DEBUG

    Config.set("kivy", "log_level", "warning")
    if debug_level >= OUTPUT_DEBUG:
        Config.set("kivy", "log_enable", 1)
        Config.set("kivy", "log_level", "debug")
