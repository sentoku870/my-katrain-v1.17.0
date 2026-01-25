"""Curator package for suitability scoring and batch output (Phase 63-64).

This package evaluates how well professional game records match a user's
learning needs by scoring:
    - needs_match: How well the game's mistakes align with user's weak areas
    - stability: How stable the game is (suitable for learning vs chaotic)
    - total: Weighted combination with batch-relative percentile

And generates batch outputs (Phase 64):
    - curator_ranking.json: Game rankings with suitability scores
    - replay_guide.json: Highlight moments for replay guidance

Example usage:
    from katrain.core.curator import score_game_suitability, score_batch_suitability
    from katrain.core.curator import SuitabilityScore, SuitabilityConfig
    from katrain.core.curator import generate_curator_outputs, CuratorBatchResult

    # Score a single game
    score = score_game_suitability(user_aggregate, game, game_stats)

    # Score multiple games with percentiles
    scores = score_batch_suitability(user_aggregate, [(game1, stats1), (game2, stats2)])

    # Generate batch outputs
    result = generate_curator_outputs(games_and_stats, curator_dir, batch_timestamp)
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
from .batch import (
    CuratorBatchResult,
    generate_curator_outputs,
)
from .guide_extractor import (
    HighlightMoment,
    ReplayGuide,
    extract_replay_guide,
)

__all__ = [
    # Models (Phase 63)
    "SuitabilityScore",
    "SuitabilityConfig",
    "DEFAULT_CONFIG",
    # Constants (Phase 63)
    "AXIS_TO_MEANING_TAGS",
    "SUPPORTED_AXES",
    "UNCERTAIN_TAG",
    # Scoring Functions (Phase 63)
    "score_game_suitability",
    "score_batch_suitability",
    "compute_needs_match",
    "compute_stability",
    "compute_batch_percentiles",
    # Batch Output (Phase 64)
    "CuratorBatchResult",
    "generate_curator_outputs",
    # Replay Guide (Phase 64)
    "HighlightMoment",
    "ReplayGuide",
    "extract_replay_guide",
]
