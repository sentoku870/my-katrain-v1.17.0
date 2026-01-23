"""5-Axis Skill Radar and Tier Assessment Module.

This module implements a 5-axis skill evaluation model (Radar) with Tier classification
based on the Idea #2 specification (5軸レーダーチャートとTier判定).

The 5 axes are:
- Opening (序盤力): Performance in moves 1-50
- Fighting (戦闘力): Performance in complex positions (PositionDifficulty.HARD)
- Endgame (終盤力): Performance in moves 150+
- Stability (安定性): Blunder avoidance rate
- Awareness (感性): AI match rate (mistake_category == GOOD)

Phase 48 constraints:
- 19x19 board size only
- No GUI, no aggregation, no snapshot changes
- Pure computation module
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Tuple

from katrain.core.analysis.models import MistakeCategory, PositionDifficulty


# =============================================================================
# Enums
# =============================================================================


class RadarAxis(str, Enum):
    """5-axis radar dimensions for skill evaluation."""

    OPENING = "opening"  # 序盤力
    FIGHTING = "fighting"  # 戦闘力
    ENDGAME = "endgame"  # 終盤力
    STABILITY = "stability"  # 安定性
    AWARENESS = "awareness"  # 感性（AI一致率）


class SkillTier(str, Enum):
    """Skill tier classification (Tier 1-5 + Unknown)."""

    TIER_1 = "tier_1"  # Novice (初学) - 15級以下
    TIER_2 = "tier_2"  # Apprentice (習得) - 6-14級
    TIER_3 = "tier_3"  # Proficient (熟練) - 1-5級
    TIER_4 = "tier_4"  # Advanced (上級) - 初段〜四段
    TIER_5 = "tier_5"  # Elite (精鋭) - 五段〜
    TIER_UNKNOWN = "unknown"


# =============================================================================
# Tier Mapping Constants
# =============================================================================

# Tier numeric representation for median calculation
TIER_TO_INT: Dict[SkillTier, int] = {
    SkillTier.TIER_1: 1,
    SkillTier.TIER_2: 2,
    SkillTier.TIER_3: 3,
    SkillTier.TIER_4: 4,
    SkillTier.TIER_5: 5,
}
INT_TO_TIER: Dict[int, SkillTier] = {v: k for k, v in TIER_TO_INT.items()}


# =============================================================================
# Threshold Constants
# =============================================================================

# APL (Average Point Loss) -> Tier thresholds
# Half-open intervals: [lower, upper), apl < threshold
APL_TIER_THRESHOLDS: List[Tuple[float, SkillTier, float]] = [
    (0.4, SkillTier.TIER_5, 5.0),
    (0.8, SkillTier.TIER_4, 4.0),
    (1.2, SkillTier.TIER_3, 3.0),
    (2.0, SkillTier.TIER_2, 2.0),
    (float("inf"), SkillTier.TIER_1, 1.0),
]

# Blunder Rate -> Tier thresholds
# Half-open intervals: [lower, upper), rate < threshold
BLUNDER_RATE_TIER_THRESHOLDS: List[Tuple[float, SkillTier, float]] = [
    (0.01, SkillTier.TIER_5, 5.0),
    (0.03, SkillTier.TIER_4, 4.0),
    (0.05, SkillTier.TIER_3, 3.0),
    (0.10, SkillTier.TIER_2, 2.0),
    (float("inf"), SkillTier.TIER_1, 1.0),
]

# Match Rate -> Tier thresholds
# Higher is better, half-open intervals: [lower, upper), rate < threshold
MATCH_RATE_TIER_THRESHOLDS: List[Tuple[float, SkillTier, float]] = [
    (0.25, SkillTier.TIER_1, 1.0),  # rate < 0.25
    (0.35, SkillTier.TIER_2, 2.0),  # 0.25 <= rate < 0.35
    (0.45, SkillTier.TIER_3, 3.0),  # 0.35 <= rate < 0.45
    (0.55, SkillTier.TIER_4, 4.0),  # 0.45 <= rate < 0.55
    (float("inf"), SkillTier.TIER_5, 5.0),  # rate >= 0.55
]


# =============================================================================
# Filtering Constants
# =============================================================================

# Garbage time detection (BLACK perspective winrate)
GARBAGE_TIME_WINRATE_HIGH = 0.99
GARBAGE_TIME_WINRATE_LOW = 0.01

# Phase boundaries (19x19 only, Phase 48 constraint)
# move_number is 1-based (1, 2, 3, ...)
OPENING_END_MOVE = 50  # move_number 1-50 = Opening
ENDGAME_START_MOVE = 150  # move_number >= 150 = Endgame

# Neutral values for axes with 0 valid moves
NEUTRAL_DISPLAY_SCORE = 3.0
NEUTRAL_TIER = SkillTier.TIER_UNKNOWN


# =============================================================================
# RadarMetrics Dataclass
# =============================================================================


@dataclass(frozen=True)
class RadarMetrics:
    """Immutable 5-axis radar metrics with tier classification.

    Attributes:
        opening: Display score for Opening axis (1.0-5.0, higher=better)
        fighting: Display score for Fighting axis
        endgame: Display score for Endgame axis
        stability: Display score for Stability axis
        awareness: Display score for Awareness axis
        opening_tier: Tier classification for Opening axis
        fighting_tier: Tier classification for Fighting axis
        endgame_tier: Tier classification for Endgame axis
        stability_tier: Tier classification for Stability axis
        awareness_tier: Tier classification for Awareness axis
        overall_tier: Overall tier (median of 5 axes)
        valid_move_counts: Number of valid moves used for each axis calculation
    """

    # Display scores (1.0-5.0, higher=better)
    opening: float
    fighting: float
    endgame: float
    stability: float
    awareness: float

    # Per-axis tier classifications
    opening_tier: SkillTier
    fighting_tier: SkillTier
    endgame_tier: SkillTier
    stability_tier: SkillTier
    awareness_tier: SkillTier

    # Overall tier (median of 5 axes)
    overall_tier: SkillTier

    # Valid move counts per axis (immutable via MappingProxyType)
    valid_move_counts: Mapping[RadarAxis, int]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary.

        Returns:
            Dictionary with scores, tiers, overall_tier, and valid_move_counts.

        Contract:
            - All Enum values are converted to .value (strings)
            - valid_move_counts keys use RadarAxis.value
        """
        return {
            "scores": {
                "opening": self.opening,
                "fighting": self.fighting,
                "endgame": self.endgame,
                "stability": self.stability,
                "awareness": self.awareness,
            },
            "tiers": {
                "opening": self.opening_tier.value,
                "fighting": self.fighting_tier.value,
                "endgame": self.endgame_tier.value,
                "stability": self.stability_tier.value,
                "awareness": self.awareness_tier.value,
            },
            "overall_tier": self.overall_tier.value,
            "valid_move_counts": {
                axis.value: count for axis, count in self.valid_move_counts.items()
            },
        }


# =============================================================================
# Tier Conversion Functions
# =============================================================================


def apl_to_tier_and_score(apl: float) -> Tuple[SkillTier, float]:
    """Convert APL (Average Point Loss) to tier and display score.

    Args:
        apl: Average point loss in points per move

    Returns:
        Tuple of (SkillTier, display_score)

    Boundary rule: apl < threshold (half-open interval [lower, upper))
    Example: apl=0.4 -> not < 0.4, but < 0.8 -> TIER_4
    """
    for threshold, tier, score in APL_TIER_THRESHOLDS:
        if apl < threshold:
            return tier, score
    return SkillTier.TIER_1, 1.0  # fallback (shouldn't reach)


def blunder_rate_to_tier_and_score(rate: float) -> Tuple[SkillTier, float]:
    """Convert Blunder Rate to tier and display score.

    Args:
        rate: Blunder rate as fraction (0.0-1.0)

    Returns:
        Tuple of (SkillTier, display_score)

    Boundary rule: rate < threshold (half-open interval [lower, upper))
    """
    for threshold, tier, score in BLUNDER_RATE_TIER_THRESHOLDS:
        if rate < threshold:
            return tier, score
    return SkillTier.TIER_1, 1.0  # fallback


def match_rate_to_tier_and_score(rate: float) -> Tuple[SkillTier, float]:
    """Convert Match Rate to tier and display score.

    Args:
        rate: Match rate as fraction (0.0-1.0)

    Returns:
        Tuple of (SkillTier, display_score)

    Boundary rule: rate < threshold (half-open interval [lower, upper))
    Example: rate=0.25 -> not < 0.25, but < 0.35 -> TIER_2
    """
    for threshold, tier, score in MATCH_RATE_TIER_THRESHOLDS:
        if rate < threshold:
            return tier, score
    return SkillTier.TIER_5, 5.0  # fallback


# =============================================================================
# Garbage Time Detection
# =============================================================================


def is_garbage_time(winrate_before: Optional[float]) -> bool:
    """Detect if position is in "garbage time" (game essentially decided).

    Args:
        winrate_before: BLACK perspective winrate (0.0-1.0)

    Returns:
        True if position is garbage time (should be excluded from evaluation)
        False if position is normal (should be included)

    Detection rules:
        - winrate_before >= 0.99: Black has essentially won
        - winrate_before <= 0.01: White has essentially won
        - Both cases indicate "game decided" state

    Note:
        - winrate_before is None: Return False (cannot determine, include)
        - No player parameter needed (absolute BLACK perspective)
    """
    if winrate_before is None:
        return False
    return (
        winrate_before >= GARBAGE_TIME_WINRATE_HIGH
        or winrate_before <= GARBAGE_TIME_WINRATE_LOW
    )


# =============================================================================
# Overall Tier Calculation
# =============================================================================


def compute_overall_tier(tiers: List[SkillTier]) -> SkillTier:
    """Compute overall tier from 5 axis tiers using median.

    Args:
        tiers: List of 5 axis tiers

    Returns:
        Overall tier (median-based)

    Algorithm:
        1. Exclude TIER_UNKNOWN values
        2. Convert to integers (TIER_1=1, ..., TIER_5=5)
        3. Calculate median:
           - Odd count: Middle element
           - Even count: Average of two middle elements, rounded up (math.ceil)
        4. If all UNKNOWN, return TIER_UNKNOWN

    Rounding rule:
        - For X.5 averages, round up (ceil)
        - Example: [1,2] -> avg=1.5 -> ceil=2 -> TIER_2
        - Example: [4,5] -> avg=4.5 -> ceil=5 -> TIER_5
    """
    known = [t for t in tiers if t != SkillTier.TIER_UNKNOWN]
    if not known:
        return SkillTier.TIER_UNKNOWN

    values = sorted([TIER_TO_INT[t] for t in known])
    n = len(values)

    if n % 2 == 1:
        # Odd: Use middle element directly
        median_int = values[n // 2]
    else:
        # Even: Average of two middle elements, rounded up
        mid_low = values[n // 2 - 1]
        mid_high = values[n // 2]
        avg = (mid_low + mid_high) / 2
        median_int = math.ceil(avg)

    return INT_TO_TIER[median_int]


# =============================================================================
# Axis Computation Functions
# =============================================================================


def compute_opening_axis(moves: List[Any]) -> Tuple[SkillTier, float, int]:
    """Compute Opening axis (序盤力).

    Target: move_number <= OPENING_END_MOVE (50)
    Exclude:
        - Garbage time (is_garbage_time(winrate_before)=True)
        - ONLY_MOVE (position_difficulty == ONLY_MOVE)
        - points_lost is None
    Calculation: APL -> Tier/Score

    Args:
        moves: List of MoveEval-like objects

    Returns:
        Tuple of (tier, score, valid_count)
    """
    filtered = [
        m
        for m in moves
        if m.move_number <= OPENING_END_MOVE
        and not is_garbage_time(m.winrate_before)
        and m.position_difficulty != PositionDifficulty.ONLY_MOVE
        and m.points_lost is not None
    ]
    if not filtered:
        return NEUTRAL_TIER, NEUTRAL_DISPLAY_SCORE, 0

    apl = sum(max(0.0, m.points_lost) for m in filtered) / len(filtered)
    tier, score = apl_to_tier_and_score(apl)
    return tier, score, len(filtered)


def compute_fighting_axis(moves: List[Any]) -> Tuple[SkillTier, float, int]:
    """Compute Fighting axis (戦闘力).

    Target: position_difficulty == HARD
    Exclude:
        - Garbage time
        - points_lost is None
        - position_difficulty is None (cannot determine)
    Calculation: APL -> Tier/Score

    Note:
        - position_difficulty=None moves are excluded (conservative)
        - Only HARD positions are included (not EASY/NORMAL/ONLY_MOVE/UNKNOWN)

    Args:
        moves: List of MoveEval-like objects

    Returns:
        Tuple of (tier, score, valid_count)
    """
    filtered = [
        m
        for m in moves
        if m.position_difficulty == PositionDifficulty.HARD
        and not is_garbage_time(m.winrate_before)
        and m.points_lost is not None
    ]
    if not filtered:
        return NEUTRAL_TIER, NEUTRAL_DISPLAY_SCORE, 0

    apl = sum(max(0.0, m.points_lost) for m in filtered) / len(filtered)
    tier, score = apl_to_tier_and_score(apl)
    return tier, score, len(filtered)


def compute_endgame_axis(moves: List[Any]) -> Tuple[SkillTier, float, int]:
    """Compute Endgame axis (終盤力).

    Target: move_number >= ENDGAME_START_MOVE (150)
    Exclude:
        - Garbage time
        - points_lost is None
    Calculation: APL -> Tier/Score

    Note: ONLY_MOVE is NOT excluded because:
        - In endgame (yose), accurately playing "obvious" moves is important
        - ONLY_MOVE can still incur loss (timing, move order)
        - Unlike Awareness axis, this measures overall yose precision

    Args:
        moves: List of MoveEval-like objects

    Returns:
        Tuple of (tier, score, valid_count)
    """
    filtered = [
        m
        for m in moves
        if m.move_number >= ENDGAME_START_MOVE
        and not is_garbage_time(m.winrate_before)
        and m.points_lost is not None
    ]
    if not filtered:
        return NEUTRAL_TIER, NEUTRAL_DISPLAY_SCORE, 0

    apl = sum(max(0.0, m.points_lost) for m in filtered) / len(filtered)
    tier, score = apl_to_tier_and_score(apl)
    return tier, score, len(filtered)


def compute_stability_axis(moves: List[Any]) -> Tuple[SkillTier, float, int]:
    """Compute Stability axis (安定性).

    Target: All moves
    Exclude: None (garbage time is INCLUDED)
    Calculation: Blunder Rate = count(BLUNDER) / total_moves -> Tier/Score

    Note: Garbage time is included because:
        - Stability measures "not making blunders" as mental steadiness
        - Blunders in winning/losing positions are still "real blunders"
        - Slow moves in winning positions have small loss, won't be BLUNDER

    Note: mistake_category is non-Optional (default=GOOD), no None check needed

    Args:
        moves: List of MoveEval-like objects

    Returns:
        Tuple of (tier, score, valid_count)
    """
    if not moves:
        return NEUTRAL_TIER, NEUTRAL_DISPLAY_SCORE, 0

    blunders = len(
        [m for m in moves if m.mistake_category == MistakeCategory.BLUNDER]
    )
    rate = blunders / len(moves)
    tier, score = blunder_rate_to_tier_and_score(rate)
    return tier, score, len(moves)


def compute_awareness_axis(moves: List[Any]) -> Tuple[SkillTier, float, int]:
    """Compute Awareness axis (感性 / AI match rate).

    Target: All moves
    Exclude:
        - ONLY_MOVE (trivial matches don't indicate "awareness")
        - Garbage time (matches in decided games are not meaningful)
    Calculation: Match Rate = count(GOOD) / total_valid -> Tier/Score

    Definition: mistake_category == GOOD is used as proxy for "Top-1 match"

    Note: Garbage time exclusion rationale:
        - Moves in decided positions don't measure "intuition alignment"
        - Same as Opening/Fighting/Endgame, focus on competitive positions
        - Only Stability differs (measures mental steadiness including pressure)

    Args:
        moves: List of MoveEval-like objects

    Returns:
        Tuple of (tier, score, valid_count)
    """
    valid = [
        m
        for m in moves
        if m.position_difficulty != PositionDifficulty.ONLY_MOVE
        and not is_garbage_time(m.winrate_before)
    ]
    if not valid:
        return NEUTRAL_TIER, NEUTRAL_DISPLAY_SCORE, 0

    matches = len([m for m in valid if m.mistake_category == MistakeCategory.GOOD])
    rate = matches / len(valid)
    tier, score = match_rate_to_tier_and_score(rate)
    return tier, score, len(valid)


# =============================================================================
# Main Entry Point
# =============================================================================


def compute_radar_from_moves(
    moves: List[Any],
    player: Optional[str] = None,
) -> RadarMetrics:
    """Compute 5-axis radar metrics from MoveEval list.

    Args:
        moves: List of MoveEval-like objects (e.g., EvalSnapshot.moves)
        player: Filter by player color
            - "B": Black moves only (recommended for individual skill)
            - "W": White moves only (recommended for individual skill)
            - None: Include both (game quality, not individual skill)

    Returns:
        RadarMetrics (frozen dataclass)

    Note:
        - Assumes board_size=19 (Phase 48 constraint)
        - Axes with 0 valid moves return NEUTRAL_TIER/NEUTRAL_DISPLAY_SCORE
    """
    if player is not None:
        moves = [m for m in moves if m.player == player]

    opening_tier, opening_score, opening_count = compute_opening_axis(moves)
    fighting_tier, fighting_score, fighting_count = compute_fighting_axis(moves)
    endgame_tier, endgame_score, endgame_count = compute_endgame_axis(moves)
    stability_tier, stability_score, stability_count = compute_stability_axis(moves)
    awareness_tier, awareness_score, awareness_count = compute_awareness_axis(moves)

    overall_tier = compute_overall_tier(
        [opening_tier, fighting_tier, endgame_tier, stability_tier, awareness_tier]
    )

    return RadarMetrics(
        opening=opening_score,
        fighting=fighting_score,
        endgame=endgame_score,
        stability=stability_score,
        awareness=awareness_score,
        opening_tier=opening_tier,
        fighting_tier=fighting_tier,
        endgame_tier=endgame_tier,
        stability_tier=stability_tier,
        awareness_tier=awareness_tier,
        overall_tier=overall_tier,
        # MappingProxyType for immutability
        valid_move_counts=MappingProxyType(
            {
                RadarAxis.OPENING: opening_count,
                RadarAxis.FIGHTING: fighting_count,
                RadarAxis.ENDGAME: endgame_count,
                RadarAxis.STABILITY: stability_count,
                RadarAxis.AWARENESS: awareness_count,
            }
        ),
    )
