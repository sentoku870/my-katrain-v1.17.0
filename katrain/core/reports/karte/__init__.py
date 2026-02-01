"""Karte report generation package.

Public API:
- build_karte_report(): Generate markdown karte report
- build_karte_json(): Generate JSON karte data
- build_critical_3_prompt(): Generate LLM prompt for critical 3 moves
- KarteGenerationError: Exception for generation failures
- MixedEngineSnapshotError: Exception for mixed-engine snapshots

Implementation uses lazy imports for callable APIs to avoid circular dependencies.
Exceptions and constants are imported directly (no side effects).
"""

from typing import Any

# Exceptions and constants: direct import (no side effects, always needed)
from katrain.core.reports.karte.models import (
    KARTE_ERROR_CODE_GENERATION_FAILED,
    KARTE_ERROR_CODE_MIXED_ENGINE,
    STYLE_CONFIDENCE_THRESHOLD,
    KarteGenerationError,
    MixedEngineSnapshotError,
)


# Callable APIs: lazy import to avoid circular dependencies
def build_karte_report(*args: Any, **kwargs: Any) -> str:
    """Generate markdown karte report. See builder.build_karte_report for details."""
    from katrain.core.reports.karte.builder import build_karte_report as _impl

    return _impl(*args, **kwargs)


def build_karte_json(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Generate JSON karte data. See json_export.build_karte_json for details."""
    from katrain.core.reports.karte.json_export import build_karte_json as _impl

    return _impl(*args, **kwargs)


def build_critical_3_prompt(*args: Any, **kwargs: Any) -> str:
    """Generate LLM prompt for critical 3 moves. See llm_prompt.build_critical_3_prompt for details."""
    from katrain.core.reports.karte.llm_prompt import build_critical_3_prompt as _impl

    return _impl(*args, **kwargs)


__all__ = [
    "build_karte_report",
    "build_karte_json",
    "build_critical_3_prompt",
    "KarteGenerationError",
    "MixedEngineSnapshotError",
    "KARTE_ERROR_CODE_MIXED_ENGINE",
    "KARTE_ERROR_CODE_GENERATION_FAILED",
    "STYLE_CONFIDENCE_THRESHOLD",
]
