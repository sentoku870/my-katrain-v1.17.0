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

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from katrain.core.compatibility import StrEnum
from types import MappingProxyType
from typing import Any, cast

_logger = logging.getLogger("katrain.core.analysis.skill_radar")

from katrain.core.analysis.models import MistakeCategory, PositionDifficulty

# =============================================================================
# Enums
# =============================================================================


class RadarAxis(StrEnum):
    """5-axis radar dimensions for skill evaluation."""

    OPENING = "opening"  # 序盤力
    FIGHTING = "fighting"  # 戦闘力
    ENDGAME = "endgame"  # 終盤力
    STABILITY = "stability"  # 安定性
    AWARENESS = "awareness"  # 感性（AI一致率）


class SkillTier(StrEnum):
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
TIER_TO_INT: dict[SkillTier, int] = {
    SkillTier.TIER_1: 1,
    SkillTier.TIER_2: 2,
    SkillTier.TIER_3: 3,
    SkillTier.TIER_4: 4,
    SkillTier.TIER_5: 5,
}
INT_TO_TIER: dict[int, SkillTier] = {v: k for k, v in TIER_TO_INT.items()}


# =============================================================================
# Threshold Constants
# =============================================================================

# APL (Average Point Loss) -> Tier thresholds
# Half-open intervals: [lower, upper), apl < threshold
APL_TIER_THRESHOLDS: list[tuple[float, SkillTier, float]] = [
    (0.4, SkillTier.TIER_5, 5.0),
    (0.8, SkillTier.TIER_4, 4.0),
    (1.2, SkillTier.TIER_3, 3.0),
    (2.0, SkillTier.TIER_2, 2.0),
    (float("inf"), SkillTier.TIER_1, 1.0),
]

# Blunder Rate -> Tier thresholds
# Half-open intervals: [lower, upper), rate < threshold
BLUNDER_RATE_TIER_THRESHOLDS: list[tuple[float, SkillTier, float]] = [
    (0.01, SkillTier.TIER_5, 5.0),
    (0.03, SkillTier.TIER_4, 4.0),
    (0.05, SkillTier.TIER_3, 3.0),
    (0.10, SkillTier.TIER_2, 2.0),
    (float("inf"), SkillTier.TIER_1, 1.0),
]

# Match Rate -> Tier thresholds
# Higher is better, half-open intervals: [lower, upper), rate < threshold
MATCH_RATE_TIER_THRESHOLDS: list[tuple[float, SkillTier, float]] = [
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
# Phase 49: Aggregation Constants
# =============================================================================

# Minimum valid axes required to compute overall tier
MIN_VALID_AXES_FOR_OVERALL = 3

# Minimum moves per player for meaningful radar (statistical significance)
MIN_MOVES_FOR_RADAR = 10

# Required keys for radar_from_dict() validation (strict)
REQUIRED_RADAR_DICT_KEYS = frozenset({"scores", "tiers", "overall_tier"})

# Optional keys (use defaults if missing, for backward compatibility)
OPTIONAL_RADAR_DICT_KEYS = frozenset({"valid_move_counts"})


# =============================================================================
# Rounding Helper (Phase 49)
# =============================================================================


def round_score(v: float | None) -> float | None:
    """Round score to 1 decimal place for display.

    This is the SINGLE SOURCE OF TRUTH for score display rounding.
    Used by BOTH to_dict() and summary table formatting for consistency.

    Args:
        v: Score value (1.0-5.0) or None

    Returns:
        Rounded score (1 decimal) or None if input is None

    Note:
        Uses Decimal for deterministic rounding (avoids banker's rounding edge cases).
        ROUND_HALF_UP: 2.25 -> 2.3, 2.35 -> 2.4 (always rounds .5 up)
    """
    if v is None:
        return None
    return float(Decimal(str(v)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


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

    def to_dict(self) -> dict[str, Any]:
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
            "valid_move_counts": {axis.value: count for axis, count in self.valid_move_counts.items()},
        }


# =============================================================================
# AggregatedRadarResult Dataclass (Phase 49)
# =============================================================================


@dataclass(frozen=True)
class AggregatedRadarResult:
    """Aggregated radar metrics across multiple games.

    Unlike RadarMetrics, scores can be None (insufficient data for axis).

    Attributes:
        opening: Aggregated score for Opening axis (1.0-5.0 or None)
        fighting: Aggregated score for Fighting axis
        endgame: Aggregated score for Endgame axis
        stability: Aggregated score for Stability axis
        awareness: Aggregated score for Awareness axis
        opening_tier: Tier for Opening axis (TIER_UNKNOWN if score is None)
        fighting_tier: Tier for Fighting axis
        endgame_tier: Tier for Endgame axis
        stability_tier: Tier for Stability axis
        awareness_tier: Tier for Awareness axis
        overall_tier: Overall tier (median of valid axes, TIER_UNKNOWN if <3 valid)
        valid_move_counts: Total valid moves per axis across all aggregated games
        games_aggregated: Number of games included in aggregation

    Note:
        - Use RAW scores for all logic (thresholds, tier derivation)
        - Round only in to_dict() for display via round_score()
    """

    # Raw scores: 1.0-5.0 or None if no valid data
    opening: float | None
    fighting: float | None
    endgame: float | None
    stability: float | None
    awareness: float | None

    # Per-axis tier (TIER_UNKNOWN if score is None)
    opening_tier: SkillTier
    fighting_tier: SkillTier
    endgame_tier: SkillTier
    stability_tier: SkillTier
    awareness_tier: SkillTier

    # Overall tier (median of valid axes, TIER_UNKNOWN if <3 valid)
    overall_tier: SkillTier

    # Total valid moves across all aggregated games
    valid_move_counts: Mapping[RadarAxis, int]

    # Aggregation metadata
    games_aggregated: int

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict with null for None values.

        Output schema is canonical and stable for golden tests.
        Scores are rounded via shared helper for consistency.

        Returns:
            Dictionary with axes (sorted alphabetically), games_aggregated,
            overall_tier, and valid_move_counts.
        """
        return {
            "axes": {
                "awareness": {
                    "score": round_score(self.awareness),
                    "tier": self.awareness_tier.value,
                },
                "endgame": {
                    "score": round_score(self.endgame),
                    "tier": self.endgame_tier.value,
                },
                "fighting": {
                    "score": round_score(self.fighting),
                    "tier": self.fighting_tier.value,
                },
                "opening": {
                    "score": round_score(self.opening),
                    "tier": self.opening_tier.value,
                },
                "stability": {
                    "score": round_score(self.stability),
                    "tier": self.stability_tier.value,
                },
            },
            "games_aggregated": self.games_aggregated,
            "overall_tier": self.overall_tier.value,
            "valid_move_counts": {
                axis.value: count for axis, count in sorted(self.valid_move_counts.items(), key=lambda x: x[0].value)
            },
        }

    def is_weak_axis(self, axis: RadarAxis) -> bool:
        """Check if axis is weak (score < 2.5).

        Args:
            axis: The radar axis to check

        Returns:
            True if score is not None AND score < 2.5 (uses RAW score, not rounded)

        Note:
            Uses raw score for logic. A score of 2.45 would be flagged as weak
            even though it rounds to 2.5 for display.
        """
        score = getattr(self, axis.value)
        return score is not None and score < 2.5


# =============================================================================
# Tier Conversion Functions
# =============================================================================


def apl_to_tier_and_score(apl: float) -> tuple[SkillTier, float]:
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


def blunder_rate_to_tier_and_score(rate: float) -> tuple[SkillTier, float]:
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


def match_rate_to_tier_and_score(rate: float) -> tuple[SkillTier, float]:
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


def is_garbage_time(winrate_before: float | None) -> bool:
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
    return winrate_before >= GARBAGE_TIME_WINRATE_HIGH or winrate_before <= GARBAGE_TIME_WINRATE_LOW


# =============================================================================
# Overall Tier Calculation
# =============================================================================


def compute_overall_tier(tiers: list[SkillTier]) -> SkillTier:
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
# Phase 49: Aggregation Functions
# =============================================================================


def radar_from_dict(d: dict[str, Any] | None) -> RadarMetrics | None:
    """Reconstruct RadarMetrics from to_dict() output.

    Args:
        d: Dictionary from RadarMetrics.to_dict(), or None

    Returns:
        RadarMetrics if valid, None otherwise

    Validation rules:
        - Returns None if d is None or empty
        - Returns None if any REQUIRED key is missing (logs at debug)
        - Uses defaults for OPTIONAL keys (backward compat)
        - Ignores unknown keys (forward compat)

    Example:
        >>> radar = compute_radar_from_moves(moves)
        >>> d = radar.to_dict()
        >>> reconstructed = radar_from_dict(d)
        # Roundtrip: tiers match exactly, scores match within floating point tolerance
    """
    if not d:
        return None

    # Check required top-level keys
    missing = REQUIRED_RADAR_DICT_KEYS - d.keys()
    if missing:
        _logger.debug("radar_from_dict: missing required keys %s", missing)
        return None

    try:
        scores = d["scores"]
        tiers = d["tiers"]
        overall_tier_str = d["overall_tier"]

        # Optional with default (backward compat)
        valid_move_counts_raw = d.get("valid_move_counts", {})

        # Parse scores
        opening_score = float(scores["opening"])
        fighting_score = float(scores["fighting"])
        endgame_score = float(scores["endgame"])
        stability_score = float(scores["stability"])
        awareness_score = float(scores["awareness"])

        # Parse tiers
        opening_tier = SkillTier(tiers["opening"])
        fighting_tier = SkillTier(tiers["fighting"])
        endgame_tier = SkillTier(tiers["endgame"])
        stability_tier = SkillTier(tiers["stability"])
        awareness_tier = SkillTier(tiers["awareness"])

        # Parse overall tier
        overall_tier = SkillTier(overall_tier_str)

        # Parse valid_move_counts (optional, default to 0 for missing axes)
        valid_move_counts: dict[RadarAxis, int] = {}
        for axis in RadarAxis:
            count = valid_move_counts_raw.get(axis.value, 0)
            valid_move_counts[axis] = int(count)

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
            valid_move_counts=MappingProxyType(valid_move_counts),
        )
    except (KeyError, TypeError, ValueError) as e:
        _logger.debug("radar_from_dict: parse error: %s", e)
        return None


def aggregate_radar(
    radar_list: list[RadarMetrics],
) -> AggregatedRadarResult | None:
    """Aggregate multiple RadarMetrics into one AggregatedRadarResult.

    Args:
        radar_list: List of RadarMetrics (from individual games)

    Returns:
        AggregatedRadarResult, or None if radar_list is empty

    Algorithm:
        1. For each axis independently:
           - Collect scores where that axis tier != TIER_UNKNOWN
           - Compute simple average; if no valid scores, result is None
        2. Derive tier from aggregated score (or TIER_UNKNOWN if None)
        3. Overall tier = median of valid axis tiers (need ≥3 valid axes)
           - Uses compute_overall_tier() to match Phase 48 behavior
        4. Sum valid_move_counts across all input RadarMetrics (filtered)

    Note:
        - Recency weighting deferred to future phase; this uses uniform (simple average)
        - valid_move_counts are filtered to match aggregation: only include counts
          from games where that axis tier != UNKNOWN
    """
    if not radar_list:
        return None

    # Helper to get tier for an axis from a RadarMetrics
    def get_axis_tier(rm: RadarMetrics, axis: RadarAxis) -> SkillTier:
        return cast(SkillTier, getattr(rm, f"{axis.value}_tier"))

    # Helper to get score for an axis from a RadarMetrics
    def get_axis_score(rm: RadarMetrics, axis: RadarAxis) -> float:
        return cast(float, getattr(rm, axis.value))

    # Helper to derive tier from aggregated score using APL thresholds
    # (since all axes use 1.0-5.0 score range mapped from tier)
    def score_to_tier(score: float | None) -> SkillTier:
        if score is None:
            return SkillTier.TIER_UNKNOWN
        # Reverse mapping: score 1.0-5.0 -> tier
        if score >= 4.5:
            return SkillTier.TIER_5
        elif score >= 3.5:
            return SkillTier.TIER_4
        elif score >= 2.5:
            return SkillTier.TIER_3
        elif score >= 1.5:
            return SkillTier.TIER_2
        else:
            return SkillTier.TIER_1

    # Compute per-axis aggregated scores and counts
    aggregated_scores: dict[RadarAxis, float | None] = {}
    aggregated_tiers: dict[RadarAxis, SkillTier] = {}
    aggregated_counts: dict[RadarAxis, int] = {}

    for axis in RadarAxis:
        # Collect scores from games where this axis is valid (tier != UNKNOWN)
        valid_scores = [
            get_axis_score(rm, axis) for rm in radar_list if get_axis_tier(rm, axis) != SkillTier.TIER_UNKNOWN
        ]

        # Collect counts from games where this axis is valid (filtered)
        valid_counts = [
            rm.valid_move_counts.get(axis, 0) for rm in radar_list if get_axis_tier(rm, axis) != SkillTier.TIER_UNKNOWN
        ]

        if valid_scores:
            # Simple average (uniform weighting)
            aggregated_scores[axis] = sum(valid_scores) / len(valid_scores)
            aggregated_counts[axis] = sum(valid_counts)
        else:
            aggregated_scores[axis] = None
            aggregated_counts[axis] = 0

        aggregated_tiers[axis] = score_to_tier(aggregated_scores[axis])

    # Compute overall tier using existing function (reuse Phase 48 logic)
    axis_tiers_list = [aggregated_tiers[axis] for axis in RadarAxis]
    overall_tier = compute_overall_tier(axis_tiers_list)

    # Check minimum valid axes for overall tier
    valid_axis_count = sum(1 for t in axis_tiers_list if t != SkillTier.TIER_UNKNOWN)
    if valid_axis_count < MIN_VALID_AXES_FOR_OVERALL:
        overall_tier = SkillTier.TIER_UNKNOWN

    return AggregatedRadarResult(
        opening=aggregated_scores[RadarAxis.OPENING],
        fighting=aggregated_scores[RadarAxis.FIGHTING],
        endgame=aggregated_scores[RadarAxis.ENDGAME],
        stability=aggregated_scores[RadarAxis.STABILITY],
        awareness=aggregated_scores[RadarAxis.AWARENESS],
        opening_tier=aggregated_tiers[RadarAxis.OPENING],
        fighting_tier=aggregated_tiers[RadarAxis.FIGHTING],
        endgame_tier=aggregated_tiers[RadarAxis.ENDGAME],
        stability_tier=aggregated_tiers[RadarAxis.STABILITY],
        awareness_tier=aggregated_tiers[RadarAxis.AWARENESS],
        overall_tier=overall_tier,
        valid_move_counts=MappingProxyType(aggregated_counts),
        games_aggregated=len(radar_list),
    )


# =============================================================================
# Axis Computation Functions
# =============================================================================


def compute_opening_axis(moves: list[Any]) -> tuple[SkillTier, float, int]:
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


def compute_fighting_axis(moves: list[Any]) -> tuple[SkillTier, float, int]:
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


def compute_endgame_axis(moves: list[Any]) -> tuple[SkillTier, float, int]:
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
        if m.move_number >= ENDGAME_START_MOVE and not is_garbage_time(m.winrate_before) and m.points_lost is not None
    ]
    if not filtered:
        return NEUTRAL_TIER, NEUTRAL_DISPLAY_SCORE, 0

    apl = sum(max(0.0, m.points_lost) for m in filtered) / len(filtered)
    tier, score = apl_to_tier_and_score(apl)
    return tier, score, len(filtered)


def compute_stability_axis(moves: list[Any]) -> tuple[SkillTier, float, int]:
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

    blunders = len([m for m in moves if m.mistake_category == MistakeCategory.BLUNDER])
    rate = blunders / len(moves)
    tier, score = blunder_rate_to_tier_and_score(rate)
    return tier, score, len(moves)


def compute_awareness_axis(moves: list[Any]) -> tuple[SkillTier, float, int]:
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
        if m.position_difficulty != PositionDifficulty.ONLY_MOVE and not is_garbage_time(m.winrate_before)
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
    moves: list[Any],
    player: str | None = None,
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

    overall_tier = compute_overall_tier([opening_tier, fighting_tier, endgame_tier, stability_tier, awareness_tier])

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
