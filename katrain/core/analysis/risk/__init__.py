"""Risk Context System - Public API.

This package provides risk-taking behavior analysis based on game situation.
It evaluates whether a player's moves align with appropriate strategy
(safe play when winning, fighting moves when losing).

Part of Phase 61: Risk Context Core.

Public API:
    Models:
        - RiskJudgmentType: Enum for game situation (WINNING, LOSING, CLOSE)
        - RiskBehavior: Enum for move behavior (SOLID, COMPLICATING, NEUTRAL)
        - RiskContext: Per-move risk analysis context
        - RiskAnalysisConfig: Configuration with thresholds
        - PlayerRiskStats: Per-player risk statistics
        - RiskAnalysisResult: Complete analysis result

    Functions:
        - analyze_risk(): Main entry point for risk analysis
        - to_player_perspective(): Convert Black-perspective to side-to-move
        - determine_judgment(): Classify game situation
        - determine_behavior_from_stdev(): Classify behavior from stdev
        - determine_behavior_from_volatility(): Classify behavior from volatility
        - check_strategy_mismatch(): Detect strategy alignment issues

Example usage:
    >>> from katrain.core.analysis.risk import analyze_risk, RiskJudgmentType
    >>> result = analyze_risk(game)
    >>> result.strategy_mismatch_count
    2
    >>> result.contexts[0].judgment_type
    <RiskJudgmentType.WINNING: 'winning'>
"""

from .analyzer import (
    analyze_risk,
    check_strategy_mismatch,
    determine_behavior_from_stdev,
    determine_behavior_from_volatility,
    determine_judgment,
    to_player_perspective,
)
from .models import (
    PlayerRiskStats,
    RiskAnalysisConfig,
    RiskAnalysisResult,
    RiskBehavior,
    RiskContext,
    RiskJudgmentType,
)

__all__ = [
    # Models
    "RiskJudgmentType",
    "RiskBehavior",
    "RiskContext",
    "RiskAnalysisConfig",
    "PlayerRiskStats",
    "RiskAnalysisResult",
    # Functions
    "analyze_risk",
    "to_player_perspective",
    "determine_judgment",
    "determine_behavior_from_stdev",
    "determine_behavior_from_volatility",
    "check_strategy_mismatch",
]
