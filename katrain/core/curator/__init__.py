"""Curator package for suitability scoring (Phase 63).

This package evaluates how well professional game records match a user's
learning needs by scoring:
    - needs_match: How well the game's mistakes align with user's weak areas
    - stability: How stable the game is (suitable for learning vs chaotic)
    - total: Weighted combination with batch-relative percentile

Example usage:
    from katrain.core.curator import score_game_suitability, score_batch_suitability
    from katrain.core.curator import SuitabilityScore, SuitabilityConfig

    # Score a single game
    score = score_game_suitability(user_aggregate, game, game_stats)

    # Score multiple games with percentiles
    scores = score_batch_suitability(user_aggregate, [(game1, stats1), (game2, stats2)])
"""

from .models import (
    AXIS_TO_MEANING_TAGS,
    DEFAULT_CONFIG,
    SUPPORTED_AXES,
    UNCERTAIN_TAG,
    SuitabilityConfig,
    SuitabilityScore,
)
from .scoring import (
    compute_batch_percentiles,
    compute_needs_match,
    compute_stability,
    score_batch_suitability,
    score_game_suitability,
)

__all__ = [
    # Models
    "SuitabilityScore",
    "SuitabilityConfig",
    "DEFAULT_CONFIG",
    # Constants
    "AXIS_TO_MEANING_TAGS",
    "SUPPORTED_AXES",
    "UNCERTAIN_TAG",
    # Functions
    "score_game_suitability",
    "score_batch_suitability",
    "compute_needs_match",
    "compute_stability",
    "compute_batch_percentiles",
]
