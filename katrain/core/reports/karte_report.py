"""Backward-compatible shim. Real implementation in karte/ package.

Imports directly from low-level modules to avoid __init__.py side effects.
All symbols listed here are confirmed to be used by existing code (grep verified).

For new code, prefer importing from katrain.core.reports.karte directly.
"""

# Exceptions and constants from models (no side effects)
from katrain.core.reports.karte.models import (
    CRITICAL_3_PROMPT_TEMPLATE,
    KARTE_ERROR_CODE_GENERATION_FAILED,
    KARTE_ERROR_CODE_MIXED_ENGINE,
    STYLE_CONFIDENCE_THRESHOLD,
    KarteGenerationError,
    MixedEngineSnapshotError,
)

# Helper functions from helpers (pure functions, no side effects)
from katrain.core.reports.karte.helpers import (
    format_loss_with_engine_suffix,
    has_loss_data,
    is_single_engine_snapshot,
)

# Callable APIs from their respective modules
from katrain.core.reports.karte.builder import build_karte_report
from katrain.core.reports.karte.json_export import build_karte_json
from katrain.core.reports.karte.llm_prompt import build_critical_3_prompt

__all__ = [
    # Public APIs
    "build_karte_report",
    "build_karte_json",
    "build_critical_3_prompt",
    # Exceptions
    "KarteGenerationError",
    "MixedEngineSnapshotError",
    # Constants
    "KARTE_ERROR_CODE_MIXED_ENGINE",
    "KARTE_ERROR_CODE_GENERATION_FAILED",
    "CRITICAL_3_PROMPT_TEMPLATE",
    "STYLE_CONFIDENCE_THRESHOLD",
    # Helper functions
    "format_loss_with_engine_suffix",
    "has_loss_data",
    "is_single_engine_snapshot",
]
