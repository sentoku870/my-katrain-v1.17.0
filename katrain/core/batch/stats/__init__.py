"""Stats package for batch analysis.

Public API is eagerly exported; formatting module uses lazy loading.
"""

from typing import TYPE_CHECKING, Any

# Aggregation - includes i18n getters and helper functions
from .aggregation import (
    build_batch_summary,
    detect_color_bias,
    format_hint_line,
    get_color_bias_note,
    get_dominant_tags,
    get_mtag_practice_hint,
    get_notes_header,
    get_percentage_note,
    get_phase_label_localized,
    # i18n getters
    get_phase_priority_text,
    get_practice_intro_text,
    get_rtag_practice_hint,
    get_section_header,
)

# Extraction - medium weight, frequently used
from .extraction import (
    extract_game_stats,
    extract_players_from_stats,
)

# =============================================================================
# Eager Exports (lightweight, frequently used, or required by tests)
# =============================================================================
# Models - small dataclass and constants
from .models import (
     EvidenceMove,
    SKIP_PLAYER_NAMES,
)

# Pattern Mining - recurring mistake detection (Phase 84)
from .pattern_miner import (
    AREA_THRESHOLDS,
    LOSS_THRESHOLD,
    MAX_GAME_REFS_PER_CLUSTER,
    OPENING_THRESHOLDS,
    GameRef,
    MistakeSignature,
    PatternCluster,
    create_signature,
    determine_phase,
    get_area_from_gtp,
    get_area_threshold,
    get_opening_threshold,
    get_severity,
    mine_patterns,
    normalize_primary_tag,
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

_lazy_cache: dict[str, Any] = {}


def __getattr__(name: str) -> Any:
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


def __dir__() -> list[str]:
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
    # Pattern Mining (Phase 84)
    "MistakeSignature",
    "GameRef",
    "PatternCluster",
    "create_signature",
    "mine_patterns",
    "get_severity",
    "normalize_primary_tag",
    "determine_phase",
    "get_area_from_gtp",
    "get_opening_threshold",
    "get_area_threshold",
    "LOSS_THRESHOLD",
    "OPENING_THRESHOLDS",
    "AREA_THRESHOLDS",
    "MAX_GAME_REFS_PER_CLUSTER",
    # Constants (tests)
    "SKIP_PLAYER_NAMES",
    # i18n getters
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
