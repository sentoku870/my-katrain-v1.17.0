# -*- coding: utf-8 -*-
"""Time Analysis Package - Public API.

This package provides SGF time tag parsing and pacing/tilt analysis.

Phase 58: Time Data Parser
    - TimeMetrics: Per-move time dataclass
    - GameTimeData: Aggregated game time data
    - parse_time_data(): Main parsing function

Phase 59: Pacing & Tilt Core
    - PacingConfig: Configuration for pacing analysis
    - PacingMetrics: Per-move pacing classification
    - TiltSeverity: Severity enum for tilt episodes
    - TiltEpisode: Detected tilt episode
    - PacingAnalysisResult: Complete analysis result
    - GamePacingStats: Computed game statistics
    - LossSource: Source of canonical loss values
    - analyze_pacing(): Main analysis function

Example usage:
    >>> from katrain.core.analysis.time import parse_time_data, analyze_pacing
    >>> time_data = parse_time_data(game.root)
    >>> result = analyze_pacing(time_data, snapshot.moves)
    >>> if result.has_time_data:
    ...     impulsive_count = sum(1 for m in result.pacing_metrics if m.is_impulsive)
"""

from .models import GameTimeData, TimeMetrics
from .parser import parse_time_data
from .pacing import (
    LossSource,
    PacingConfig,
    PacingMetrics,
    TiltSeverity,
    TiltEpisode,
    PacingAnalysisResult,
    GamePacingStats,
    analyze_pacing,
)

__all__ = [
    # Phase 58
    "TimeMetrics",
    "GameTimeData",
    "parse_time_data",
    # Phase 59
    "LossSource",
    "PacingConfig",
    "PacingMetrics",
    "TiltSeverity",
    "TiltEpisode",
    "PacingAnalysisResult",
    "GamePacingStats",
    "analyze_pacing",
]
