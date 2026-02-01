# -*- coding: utf-8 -*-
"""Risk Management section for Karte reports.

Phase 62: Risk Integration

Terminology mapping:
    - When WINNING: SOLID = "Solid" (good), COMPLICATING = "Risk Taker" (bad)
    - When LOSING: COMPLICATING = "Fighter" (good), SOLID = "Resigned" (bad)

Thresholding (3-tier, separate functions):
    - Winning: SOLID% 61-100 = Solid, 40-60 = Mixed, 0-39 = Risk Taker
    - Losing: COMPLICATING% 61-100 = Fighter, 40-60 = Mixed, 0-39 = Resigned
"""

from dataclasses import dataclass
from typing import Optional

from katrain.core.lang import i18n

# Canonical import from top-level analysis package
from katrain.core.analysis import (
    RiskAnalysisResult,
    RiskBehavior,
    RiskJudgmentType,
)


@dataclass(frozen=True)
class RiskDisplayData:
    """Display data for risk section."""

    player: str  # "B" or "W"
    winning_solid_pct: Optional[float]  # SOLID % when WINNING (0-100)
    losing_complicating_pct: Optional[float]  # COMPLICATING % when LOSING (0-100)
    mismatch_count: int
    has_winning_data: bool
    has_losing_data: bool


def _classify_winning_behavior(solid_pct: float) -> str:
    """Classify behavior when WINNING based on SOLID percentage.

    Args:
        solid_pct: Percentage of SOLID moves when WINNING (0-100)

    Returns:
        i18n key: "risk:solid", "risk:mixed", or "risk:risk_taker"
    """
    if solid_pct >= 61:
        return "risk:solid"
    elif solid_pct >= 40:
        return "risk:mixed"
    else:
        return "risk:risk_taker"


def _classify_losing_behavior(complicating_pct: float) -> str:
    """Classify behavior when LOSING based on COMPLICATING percentage.

    Args:
        complicating_pct: Percentage of COMPLICATING moves when LOSING (0-100)

    Returns:
        i18n key: "risk:fighter", "risk:mixed", or "risk:resigned"
    """
    if complicating_pct >= 61:
        return "risk:fighter"
    elif complicating_pct >= 40:
        return "risk:mixed"
    else:
        return "risk:resigned"


def format_risk_stats(
    data: RiskDisplayData,
    fallback_used: bool,
) -> list[str]:
    """Format risk statistics as markdown lines.

    Args:
        data: Display data for a player
        fallback_used: True if volatility fallback was used

    Returns:
        List of markdown-formatted lines
    """
    lines = []
    suffix = f" {i18n._('risk:estimated_suffix')}" if fallback_used else ""

    # Winning behavior (SOLID % → Solid/Mixed/RiskTaker)
    if data.has_winning_data and data.winning_solid_pct is not None:
        label = i18n._("risk:when_winning")
        pct = data.winning_solid_pct
        behavior_key = _classify_winning_behavior(pct)
        behavior = i18n._(behavior_key)
        lines.append(f"- {label}: {behavior} ({pct:.0f}%){suffix}")

    # Losing behavior (COMPLICATING % → Fighter/Mixed/Resigned)
    if data.has_losing_data and data.losing_complicating_pct is not None:
        label = i18n._("risk:when_losing")
        pct = data.losing_complicating_pct
        behavior_key = _classify_losing_behavior(pct)
        behavior = i18n._(behavior_key)
        lines.append(f"- {label}: {behavior} ({pct:.0f}%){suffix}")

    # Mismatch count
    if data.mismatch_count > 0:
        label = i18n._("risk:strategy_mismatch")
        lines.append(f"- {label}: {data.mismatch_count}")

    return lines


def extract_risk_display_data(
    result: RiskAnalysisResult,
    player: str,
) -> RiskDisplayData:
    """Extract display data for a player from RiskAnalysisResult.

    Computes BOTH numerator and denominator from filtered contexts to ensure
    consistency. Does not rely on stats for counts (avoids mismatch risk).

    Args:
        result: Complete risk analysis result
        player: "B" or "W"

    Returns:
        RiskDisplayData for the specified player
    """
    # Filter contexts for this player
    player_contexts = [ctx for ctx in result.contexts if ctx.player == player]

    # Count WINNING contexts (denominator) and SOLID within WINNING (numerator)
    winning_contexts = [
        ctx for ctx in player_contexts
        if ctx.judgment_type == RiskJudgmentType.WINNING
    ]
    winning_total = len(winning_contexts)
    winning_solid = sum(
        1 for ctx in winning_contexts
        if ctx.risk_behavior == RiskBehavior.SOLID
    )

    # Count LOSING contexts (denominator) and COMPLICATING within LOSING (numerator)
    losing_contexts = [
        ctx for ctx in player_contexts
        if ctx.judgment_type == RiskJudgmentType.LOSING
    ]
    losing_total = len(losing_contexts)
    losing_complicating = sum(
        1 for ctx in losing_contexts
        if ctx.risk_behavior == RiskBehavior.COMPLICATING
    )

    # Calculate percentages (None if no data)
    winning_pct = (
        winning_solid / winning_total * 100
        if winning_total > 0 else None
    )
    losing_pct = (
        losing_complicating / losing_total * 100
        if losing_total > 0 else None
    )

    # Mismatch count from stats (this is a summary, not behavior-specific)
    stats = result.black_stats if player == "B" else result.white_stats

    return RiskDisplayData(
        player=player,
        winning_solid_pct=winning_pct,
        losing_complicating_pct=losing_pct,
        mismatch_count=stats.mismatch_count,
        has_winning_data=winning_total > 0,
        has_losing_data=losing_total > 0,
    )


def get_section_title() -> str:
    """Get localized section title."""
    return i18n._("risk:section_title")
