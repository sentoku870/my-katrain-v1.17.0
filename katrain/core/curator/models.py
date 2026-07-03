"""Data models for Curator Scoring (Phase 63).

This module defines the data structures for suitability scoring,
which evaluates how well a professional game record matches a user's learning needs.

Phase 137+: Curator simplified to stability-only scoring. Radar axes (needs_match)
and meaning-tag-based scoring have been removed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class SuitabilityConfig:
    """Configuration for suitability scoring.

    Attributes:
        max_volatility: Maximum volatility for stability=0.0 (default: 15.0)
        stability_insufficient_data: Stability value when < 2 valid scores (default: 0.0)
    """

    max_volatility: float = 15.0
    stability_insufficient_data: float = 0.0


# Default configuration instance
DEFAULT_CONFIG: SuitabilityConfig = SuitabilityConfig()


@dataclass(frozen=True)
class SuitabilityScore:
    """Suitability score for a game.

    All fields are immutable. debug_info uses MappingProxyType over a copied dict.

    Attributes:
        stability: 0.0-1.0, game stability (higher = more stable = better for learning)
        total: 0.0-1.0, equal to stability (stability-only scoring)
        percentile: 0-100, batch-relative ranking (ECDF-style, None if not yet computed)
        debug_info: Optional immutable dict for transparency/debugging
    """

    stability: float
    total: float
    percentile: int | None = None
    debug_info: Mapping[str, Any] | None = None
