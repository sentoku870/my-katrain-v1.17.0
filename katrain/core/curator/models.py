"""Data models for Curator Scoring (Phase 63).

This module defines the data structures for suitability scoring,
which evaluates how well a professional game record matches a user's learning needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, FrozenSet, Mapping

from katrain.core.analysis.meaning_tags.models import MeaningTagId
from katrain.core.analysis.skill_radar import RadarAxis


# =============================================================================
# Constants
# =============================================================================

# Use MeaningTagId.UNCERTAIN.value to avoid string drift
UNCERTAIN_TAG: str = MeaningTagId.UNCERTAIN.value

# Radar axis to MeaningTag mapping based on Go domain knowledge
# Phase 63 supports exactly these 5 axes
AXIS_TO_MEANING_TAGS: Mapping[RadarAxis, FrozenSet[str]] = MappingProxyType(
    {
        RadarAxis.FIGHTING: frozenset(
            {
                "capture_race_loss",
                "life_death_error",
                "reading_failure",
                "missed_tesuji",
            }
        ),
        RadarAxis.OPENING: frozenset({"direction_error"}),
        RadarAxis.ENDGAME: frozenset({"endgame_slip", "territorial_loss"}),
        RadarAxis.STABILITY: frozenset(
            {"overplay", "connection_miss", "shape_mistake"}
        ),
        RadarAxis.AWARENESS: frozenset({"slow_move"}),
    }
)

# Phase 63 supports exactly these 5 axes
# This prevents breakage if RadarAxis enum gains new members in the future
SUPPORTED_AXES: FrozenSet[RadarAxis] = frozenset(AXIS_TO_MEANING_TAGS.keys())


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class SuitabilityConfig:
    """Configuration for suitability scoring.

    Attributes:
        needs_match_weight: Weight for needs_match in total calculation (default: 0.6)
        stability_weight: Weight for stability in total calculation (default: 0.4)
        min_tag_occurrences: Minimum total tag occurrences for needs_match (default: 3)
        max_volatility: Maximum volatility for stability=0.0 (default: 15.0)
        stability_insufficient_data: Stability value when < 2 valid scores (default: 0.0)

    Note:
        Weights are normalized at computation time.
        If needs_match_weight + stability_weight != 1.0, they are normalized.
    """

    needs_match_weight: float = 0.6
    stability_weight: float = 0.4
    min_tag_occurrences: int = 3
    max_volatility: float = 15.0
    stability_insufficient_data: float = 0.0


# Default configuration instance
DEFAULT_CONFIG: SuitabilityConfig = SuitabilityConfig()


@dataclass(frozen=True)
class SuitabilityScore:
    """Suitability score for a game relative to user's learning needs.

    All fields are immutable. debug_info uses MappingProxyType over a copied dict.

    Attributes:
        needs_match: 0.0-1.0, how well game's MeaningTags align with user's weak axes
        stability: 0.0-1.0, game stability (higher = more stable = better for learning)
        total: 0.0-1.0, weighted combination of needs_match and stability
        percentile: 0-100, batch-relative ranking (ECDF-style, None if not yet computed)
        debug_info: Optional immutable dict for transparency/debugging
    """

    needs_match: float
    stability: float
    total: float
    percentile: int | None = None
    debug_info: Mapping[str, Any] | None = None
