"""Stats package for batch analysis.

Public API is eagerly exported; formatting module uses lazy loading.
"""

from typing import TYPE_CHECKING

# =============================================================================
# Eager Exports (lightweight, frequently used, or required by tests)
# =============================================================================

# Models - small dataclass and constants
from .models import (
    EvidenceMove,
    SKIP_PLAYER_NAMES,
    TIER_LABELS,
    AXIS_LABELS,
    AXIS_PRACTICE_HINTS,
    AXIS_PRACTICE_HINTS_LOCALIZED,
    MTAG_PRACTICE_HINTS,
    RTAG_PRACTICE_HINTS,
    PRACTICE_INTRO_TEXTS,
    NOTES_HEADERS,
    HINT_LINE_FORMATS,
    PERCENTAGE_NOTES,
    COLOR_BIAS_NOTES,
    PHASE_PRIORITY_TEXTS,
    PHASE_LABELS_LOCALIZED,
    SECTION_HEADERS,
)

# Extraction - medium weight, frequently used
from .extraction import (
    extract_game_stats,
    extract_players_from_stats,
)

# Aggregation - includes i18n getters and helper functions
from .aggregation import (
    build_batch_summary,
    _select_evidence_moves,
    _format_evidence_with_links,
    detect_color_bias,
    get_dominant_tags,
    build_tag_based_hints,
    _get_tier_label,
    _get_axis_label,
    _build_skill_profile_section,
    _build_radar_json_section,
    # i18n getters
    get_phase_priority_text,
    get_phase_label_localized,
    get_section_header,
    get_practice_intro_text,
    get_notes_header,
    get_axis_practice_hint,
    get_mtag_practice_hint,
    get_rtag_practice_hint,
    format_hint_line,
    get_percentage_note,
    get_color_bias_note,
)

# =============================================================================
# Lazy Exports (heavy formatting module - ~680 lines)
# =============================================================================

_LAZY_IMPORTS = {
    "build_player_summary": ("formatting", "build_player_summary"),
}

# Backward compatibility aliases
_BACKWARD_COMPAT_ALIASES = {
    "_extract_game_stats": "extract_game_stats",
    "_build_batch_summary": "build_batch_summary",
    "_extract_players_from_stats": "extract_players_from_stats",
    "_build_player_summary": "build_player_summary",
}

_lazy_cache: dict = {}


def __getattr__(name: str):
    """Lazy load formatting module symbols and handle aliases."""
    if name in _BACKWARD_COMPAT_ALIASES:
        target = _BACKWARD_COMPAT_ALIASES[name]
        if target in globals():
            return globals()[target]
        return __getattr__(target)

    if name in _LAZY_IMPORTS:
        if name not in _lazy_cache:
            module_name, symbol_name = _LAZY_IMPORTS[name]
            if module_name == "formatting":
                from . import formatting
                _lazy_cache[name] = getattr(formatting, symbol_name)
            else:
                raise ImportError(f"Unknown module: {module_name}")
        return _lazy_cache[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """Return list of public attributes for introspection."""
    # Return only __all__ symbols for clean dir() output
    return list(__all__)


# =============================================================================
# __all__ definition
# =============================================================================

__all__ = [
    # Public API
    "extract_game_stats",
    "build_batch_summary",
    "extract_players_from_stats",
    "build_player_summary",
    "EvidenceMove",
    # Constants (tests)
    "SKIP_PLAYER_NAMES",
    "TIER_LABELS",
    "AXIS_LABELS",
    "AXIS_PRACTICE_HINTS",
    "AXIS_PRACTICE_HINTS_LOCALIZED",
    "MTAG_PRACTICE_HINTS",
    "RTAG_PRACTICE_HINTS",
    "PRACTICE_INTRO_TEXTS",
    "NOTES_HEADERS",
    "HINT_LINE_FORMATS",
    "PERCENTAGE_NOTES",
    "COLOR_BIAS_NOTES",
    "PHASE_PRIORITY_TEXTS",
    "PHASE_LABELS_LOCALIZED",
    "SECTION_HEADERS",
    # Private functions (tests)
    "_select_evidence_moves",
    "_format_evidence_with_links",
    "_build_skill_profile_section",
    "_build_radar_json_section",
    "_get_tier_label",
    "_get_axis_label",
    # Backward compat aliases
    "_extract_game_stats",
    "_build_batch_summary",
    "_extract_players_from_stats",
    "_build_player_summary",
    # i18n getters
    "get_phase_priority_text",
    "get_phase_label_localized",
    "get_section_header",
    "get_practice_intro_text",
    "get_notes_header",
    "get_axis_practice_hint",
    "get_mtag_practice_hint",
    "get_rtag_practice_hint",
    "format_hint_line",
    "get_percentage_note",
    "get_color_bias_note",
    # Helper functions
    "detect_color_bias",
    "get_dominant_tags",
    "build_tag_based_hints",
]

# =============================================================================
# TYPE_CHECKING imports for IDE support
# =============================================================================

if TYPE_CHECKING:
    from .formatting import build_player_summary as build_player_summary
