"""Backward-compatible shim. Real implementation in karte/ package.

Imports directly from low-level modules to avoid __init__.py side effects.
All symbols listed here are confirmed to be used by existing code (grep verified).

For new code, prefer importing from katrain.core.reports.karte directly.

Phase 171: ``MixedEngineSnapshotError`` / ``KARTE_ERROR_CODE_MIXED_ENGINE`` /
``KARTE_ERROR_CODE_NON_KATAGO`` / ``format_loss_with_engine_suffix`` /
``is_single_engine_snapshot`` を削除（KataGo 専用化に伴う後方互換の終了）。
"""

# Exceptions and constants from models (no side effects)
# Callable APIs from their respective modules

import warnings

warnings.warn(
    "katrain.core.reports.karte_report is a deprecated compatibility shim (Phase 195-C); import from katrain.core.reports.karte.builder or katrain.core.reports.karte.models instead. This module is scheduled for removal in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from katrain.core.reports.karte.builder import build_karte_report

# Helper functions from helpers (pure functions, no side effects)
from katrain.core.reports.karte.helpers import has_loss_data
from katrain.core.reports.karte.json_export import build_karte_json
from katrain.core.reports.karte.llm_prompt import build_critical_3_prompt
from katrain.core.reports.karte.models import (
    CRITICAL_3_PROMPT_TEMPLATE,
    KARTE_ERROR_CODE_GENERATION_FAILED,
    STYLE_CONFIDENCE_THRESHOLD,
    KarteGenerationError,
)

__all__ = [
    # Public APIs
    "build_karte_report",
    "build_karte_json",
    "build_critical_3_prompt",
    # Exceptions
    "KarteGenerationError",
    # Constants
    "KARTE_ERROR_CODE_GENERATION_FAILED",
    "CRITICAL_3_PROMPT_TEMPLATE",
    "STYLE_CONFIDENCE_THRESHOLD",
    # Helper functions
    "has_loss_data",
]
