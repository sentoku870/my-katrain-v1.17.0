"""Risk Context Data Models.

This module defines the core data structures for the Risk Context system:
- RiskJudgmentType: Enum for game situation judgment
- RiskBehavior: Enum for move behavior classification
- RiskContext: Per-move risk analysis context
- RiskAnalysisConfig: Configuration with thresholds
- PlayerRiskStats: Per-player risk statistics
- RiskAnalysisResult: Complete analysis result

Part of Phase 61: Risk Context Core.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RiskJudgmentType(StrEnum):
    """Game situation judgment from the side-to-move perspective.

    Inherits from str for direct JSON serialization (no .value needed).
    """

    WINNING = "winning"  # Ahead (safe play recommended)
    LOSING = "losing"  # Behind (fighting moves recommended)
    CLOSE = "close"  # Close game (flexible strategy)


class RiskBehavior(StrEnum):
    """Move behavior classification based on complexity change.

    Inherits from str for direct JSON serialization (no .value needed).
    """

    SOLID = "solid"  # Stability-oriented (stdev decrease)
    COMPLICATING = "complicating"  # Complexity-oriented (stdev increase)
    NEUTRAL = "neutral"  # Neutral behavior


@dataclass(frozen=True)
class RiskContext:
    """Per-move risk context.

    Semantics:
        - Context for move N = situation before N + behavior from playing N
        - winrate_before, score_lead_before are converted to side-to-move perspective

    Data Quality Note:
        - has_stdev_data=True: delta_stdev is KataGo's scoreStdev difference
          (position uncertainty)
        - has_stdev_data=False: volatility_metric is past scoreLead variance
          (proxy metric)
        - Fallback values are different from true scoreStdev. Phase 62 Karte
          display should add "(estimated)" label.

    Attributes:
        move_number: Move number (1-indexed)
        player: "B" or "W"
        judgment_type: Game situation judgment
        winrate_before: Winrate from side-to-move perspective (0.0-1.0)
        score_lead_before: Score lead from side-to-move perspective (positive=ahead)
        risk_behavior: Behavior classification for this move
        delta_stdev: post_stdev - pre_stdev (KataGo scoreStdev), or None
        volatility_metric: Past N moves scoreLead std dev (proxy), or None
        is_strategy_mismatch: Whether behavior contradicts optimal strategy
        mismatch_reason: Reason for mismatch, or None
        has_stdev_data: True if scoreStdev used, False if volatility fallback
    """

    move_number: int
    player: str  # "B" or "W"

    # Situation (side-to-move perspective, before playing)
    judgment_type: RiskJudgmentType
    winrate_before: float  # Side-to-move perspective (0.0-1.0)
    score_lead_before: float  # Side-to-move perspective (positive=ahead)

    # Behavior (result of playing this move)
    risk_behavior: RiskBehavior
    delta_stdev: float | None  # post_stdev - pre_stdev (KataGo scoreStdev)
    volatility_metric: float | None  # Past N moves scoreLead std dev (proxy)

    # Strategy alignment
    is_strategy_mismatch: bool
    mismatch_reason: str | None

    # Data quality
    has_stdev_data: bool  # True=scoreStdev used, False=volatility fallback

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict.

        Returns:
            Dictionary with all fields, enums as string values.
        """
        return {
            "move_number": self.move_number,
            "player": self.player,
            "judgment_type": self.judgment_type.value,
            "winrate_before": round(self.winrate_before, 3),
            "score_lead_before": round(self.score_lead_before, 2),
            "risk_behavior": self.risk_behavior.value,
            "delta_stdev": round(self.delta_stdev, 3) if self.delta_stdev is not None else None,
            "volatility_metric": (round(self.volatility_metric, 3) if self.volatility_metric is not None else None),
            "is_strategy_mismatch": self.is_strategy_mismatch,
            "mismatch_reason": self.mismatch_reason,
            "has_stdev_data": self.has_stdev_data,
        }


@dataclass(frozen=True)
class RiskAnalysisConfig:
    """Configuration for risk analysis (thresholds).

    Threshold Semantics:
        - Judgment uses inclusive thresholds (>= and <=)
        - Both winrate AND score conditions must be met for WINNING/LOSING
        - If either condition fails, result is CLOSE

    Attributes:
        winning_winrate_threshold: WR >= this for winning (default: 0.85)
        losing_winrate_threshold: WR <= this for losing (default: 0.15)
        winning_score_threshold: Score >= this for winning (default: 10.0)
        losing_score_threshold: Score <= this for losing (default: -10.0)
        complicating_stdev_delta: delta >= this means complicating (default: 1.0)
        solid_stdev_delta: delta <= this means solid (default: -0.5)
        volatility_window: Number of past moves for volatility (default: 5)
        volatility_complicating_threshold: volatility >= this (default: 5.0)
        volatility_solid_threshold: volatility <= this (default: 2.0)
    """

    winning_winrate_threshold: float = 0.85
    losing_winrate_threshold: float = 0.15
    winning_score_threshold: float = 10.0
    losing_score_threshold: float = -10.0
    complicating_stdev_delta: float = 1.0
    solid_stdev_delta: float = -0.5
    volatility_window: int = 5
    volatility_complicating_threshold: float = 5.0
    volatility_solid_threshold: float = 2.0


@dataclass(frozen=True)
class PlayerRiskStats:
    """Per-player risk statistics.

    Note:
        All counts use "included RiskContexts" as denominator.
        Skipped nodes (no analysis, root node, etc.) are NOT included.

    Attributes:
        total_contexts: Total RiskContext count for this player
        winning_count: Count where judgment_type == WINNING
        losing_count: Count where judgment_type == LOSING
        close_count: Count where judgment_type == CLOSE
        mismatch_count: Count where is_strategy_mismatch == True
        contexts_with_stdev: Count where has_stdev_data == True
        contexts_with_fallback: Count where has_stdev_data == False
    """

    total_contexts: int
    winning_count: int
    losing_count: int
    close_count: int
    mismatch_count: int
    contexts_with_stdev: int
    contexts_with_fallback: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "total_contexts": self.total_contexts,
            "winning_count": self.winning_count,
            "losing_count": self.losing_count,
            "close_count": self.close_count,
            "mismatch_count": self.mismatch_count,
            "contexts_with_stdev": self.contexts_with_stdev,
            "contexts_with_fallback": self.contexts_with_fallback,
        }


@dataclass(frozen=True)
class RiskAnalysisResult:
    """Complete risk analysis result.

    Result-Level Flags (for UI/logging quality indicators):
        has_stdev_data: True if ANY context used scoreStdev
        fallback_used: True if ANY context used volatility fallback

    Usage:
        - UI per-move display: Use context.has_stdev_data for "(estimated)" label
        - Global summary: Use result.fallback_used for "includes estimates" note
        - These are UI/log quality indicators and don't affect analysis logic

    Attributes:
        contexts: Tuple of all RiskContext objects (immutable)
        has_stdev_data: True if any context used scoreStdev
        fallback_used: True if any context used volatility fallback
        strategy_mismatch_count: Total count of strategy mismatches
        winning_contexts: Total count of WINNING judgments
        losing_contexts: Total count of LOSING judgments
        black_stats: Statistics for Black player
        white_stats: Statistics for White player
    """

    contexts: tuple[RiskContext, ...]
    has_stdev_data: bool
    fallback_used: bool
    strategy_mismatch_count: int
    winning_contexts: int
    losing_contexts: int
    black_stats: PlayerRiskStats
    white_stats: PlayerRiskStats

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "contexts": [c.to_dict() for c in self.contexts],
            "has_stdev_data": self.has_stdev_data,
            "fallback_used": self.fallback_used,
            "strategy_mismatch_count": self.strategy_mismatch_count,
            "winning_contexts": self.winning_contexts,
            "losing_contexts": self.losing_contexts,
            "black_stats": self.black_stats.to_dict(),
            "white_stats": self.white_stats.to_dict(),
        }
