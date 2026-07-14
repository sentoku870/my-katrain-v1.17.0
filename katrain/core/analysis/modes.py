"""Analysis mode enum and parser (Phase 204: extracted from core/constants.py).

Controls the behavior of ``game.analyze_extra()``. Note that "toggle" is NOT
a valid AnalysisMode - it is an action token used only by set_insert_mode().
"""

from __future__ import annotations

import logging

from katrain.core.compatibility import StrEnum

_logger = logging.getLogger(__name__)


class AnalysisMode(StrEnum):
    """Analysis mode for analyze_extra()."""

    STOP = "stop"
    PONDER = "ponder"
    EXTRA = "extra"
    GAME = "game"
    SWEEP = "sweep"
    EQUALIZE = "equalize"
    ALTERNATIVE = "alternative"
    LOCAL = "local"

    def __str__(self) -> str:
        return self.value


def parse_analysis_mode(
    value: str | AnalysisMode,
    fallback: AnalysisMode = AnalysisMode.STOP,
) -> AnalysisMode:
    """Normalize a string or Enum to AnalysisMode.

    Args:
        value: Mode value ("stop", " PONDER ", AnalysisMode.STOP, etc.)
        fallback: Fallback value when parsing fails

    Returns:
        AnalysisMode (returns fallback and logs WARNING for unknown values)

    Usage:
        - game.py: Entry point of analyze_extra()
        - __main__.py: Entry point of _do_analyze_extra()
    """
    if isinstance(value, AnalysisMode):
        return value
    try:
        normalized = value.strip().lower()
        return AnalysisMode(normalized)
    except (ValueError, AttributeError):
        _logger.warning(f"Unknown analysis mode: {value!r}, falling back to {fallback}")
        return fallback


__all__ = ["AnalysisMode", "parse_analysis_mode"]