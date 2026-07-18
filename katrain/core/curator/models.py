"""Data models for Curator Scoring (Phase 63).

This module defines the data structures for suitability scoring,
which evaluates how well a professional game record matches a user's learning needs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from katrain.core.analysis.meaning_tags.models import MeaningTagId

# =============================================================================
# Constants
# =============================================================================

# Use MeaningTagId.UNCERTAIN.value to avoid string drift
UNCERTAIN_TAG: str = MeaningTagId.UNCERTAIN.value

# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class SuitabilityConfig:
    """Configuration for suitability scoring.

    Attributes:
        needs_match_weight: Weight for needs_match in total calculation.
            Default 0.5 (Phase A-1 equal weighting).
        stability_weight: Weight for stability in total calculation.
            Default 0.5 (Phase A-1 equal weighting).
        min_tag_occurrences: Minimum total tag occurrences for needs_match (default: 3)
        max_volatility: Maximum volatility for stability=0.0 (default: 15.0)
        stability_insufficient_data: Stability value when < 2 valid scores (default: 0.0)
        jaccard_insufficient_data: needs_match value when no overlap can be
            computed (default: 0.0).

    Note:
        Weights are normalized at computation time.
        If needs_match_weight + stability_weight != 1.0, they are normalized.
    """

    needs_match_weight: float = 0.5
    stability_weight: float = 0.5
    min_tag_occurrences: int = 3
    max_volatility: float = 15.0
    stability_insufficient_data: float = 0.0
    jaccard_insufficient_data: float = 0.0


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


@dataclass(frozen=True)
class UserAggregate:
    """Phase 268+ user-aggregated profile built from batch game stats.

    Aggregated by :func:`katrain.core.curator.batch.build_user_aggregate_from_stats`
    from a list of ``game_stats`` dicts (each produced by
    ``katrain.core.batch.stats.extract_game_stats``).

    The shape matches the duck-typed access pattern in
    :func:`katrain.core.curator.scoring._extract_user_weak_tags` —
    the scorer looks for ``weak_tags`` / ``meaning_tags`` /
    ``meaning_tags_by_player`` attributes, so this dataclass exposes
    the same surface.

    Attributes:
        weak_tags: ``{meaning_tag_id: occurrence_count}`` summed across
            all games. UNCERTAIN tags are excluded.
        meaning_tags_by_player: ``{player_color: {tag: count}}`` raw
            per-game aggregates (not collapsed across players).
        total_games: Number of games that contributed to this profile.
        source_games: Optional list of game identifiers (e.g. file
            paths) that contributed. Useful for status messages.
    """

    weak_tags: dict[str, int]
    meaning_tags_by_player: dict[str, dict[str, int]]
    total_games: int = 0
    source_games: tuple[str, ...] = ()

    def is_meaningful(self) -> bool:
        """Return True if the profile carries at least one tag.

        A profile with no weak tags at all (e.g. every game was a
        perfect play) is not useful for the curator weak-axis hint.
        """
        return bool(self.weak_tags)
