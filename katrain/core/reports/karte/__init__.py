"""Karte report generation package.

Public API:
- build_karte_json_string(): Generate JSON-serializable karte data as a string
- build_karte_json(): Generate karte data as a Python dict
- build_critical_3_prompt(): Generate LLM prompt for critical 3 moves
- KarteGenerationError: Exception for generation failures

Implementation uses lazy imports for callable APIs to avoid circular dependencies.
Exceptions and constants are imported directly (no side effects).

Phase 171: ``MixedEngineSnapshotError`` / ``KARTE_ERROR_CODE_MIXED_ENGINE`` は
KataGo 専用化により削除。
Phase 231: ``build_karte_report`` → ``build_karte_json_string`` リネーム。
            関数は Phase 149 から常に JSON 文字列を返していたが、関数名と
            docstring が「markdown」と齟齬していたため改名した。
"""

from typing import Any

# Exceptions and constants: direct import (no side effects, always needed)
from katrain.core.reports.karte.models import (
    KARTE_ERROR_CODE_GENERATION_FAILED,
    STYLE_CONFIDENCE_THRESHOLD,
    KarteGenerationError,
)


# Callable APIs: lazy import to avoid circular dependencies
def build_karte_json_string(*args: Any, **kwargs: Any) -> str:
    """Generate a JSON-serialized karte report. See builder.build_karte_json_string for details.

    Phase 231: renamed from ``build_karte_report``. Returns a JSON string
    (built via :func:`build_karte_json` + :func:`json.dumps`). On error
    with ``raise_on_error=False`` it returns a markdown error card
    instead (via :func:`_build_error_karte`).
    """
    from katrain.core.reports.karte.builder import build_karte_json_string as _impl

    return _impl(*args, **kwargs)


def build_karte_json(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Generate JSON karte data. See json_export.build_karte_json for details.

    Phase 149 C-3: Returns dict[str, Any] (KarteReport v3.0 structure).
    Previously typed as KarteReport TypedDict, but the wrapper returns the
    underlying dict for JSON serialization compatibility.
    """
    from katrain.core.reports.karte.json_export import build_karte_json as _impl

    return _impl(*args, **kwargs)


def build_critical_3_prompt(*args: Any, **kwargs: Any) -> str:
    """Generate LLM prompt for critical 3 moves. See llm_prompt.build_critical_3_prompt for details."""
    from katrain.core.reports.karte.llm_prompt import build_critical_3_prompt as _impl

    return _impl(*args, **kwargs)


__all__ = [
    "build_karte_json_string",
    "build_karte_json",
    "build_critical_3_prompt",
    "KarteGenerationError",
    "KARTE_ERROR_CODE_GENERATION_FAILED",
    "STYLE_CONFIDENCE_THRESHOLD",
]
