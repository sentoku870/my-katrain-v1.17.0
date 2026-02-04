"""Scoring logic for Curator (Phase 63).

This module implements suitability scoring for game records,
evaluating how well they match a user's learning needs.
"""

from __future__ import annotations

import math
from types import MappingProxyType
from enum import Enum
from typing import TYPE_CHECKING, Any, Mapping, cast

from katrain.core.analysis.skill_radar import AggregatedRadarResult
from katrain.core.game_node import GameNode

from .models import (
    AXIS_TO_MEANING_TAGS,
    DEFAULT_CONFIG,
    SUPPORTED_AXES,
    UNCERTAIN_TAG,
    SuitabilityConfig,
    SuitabilityScore,
)

if TYPE_CHECKING:
    from katrain.core.analysis.meaning_tags.models import MeaningTagId
    from katrain.core.game import Game


# =============================================================================
# Helper Functions
# =============================================================================


def _normalize_meaning_tag_key(key: str | MeaningTagId) -> str:
    """Normalize MeaningTagId or string to string key.

    Args:
        key: Either a string like "overplay" or MeaningTagId.OVERPLAY

    Returns:
        String value (e.g., "overplay")

    Note:
        Uses .value for Enum/MeaningTagId, not str(enum).
        str(MeaningTagId.OVERPLAY) = "MeaningTagId.OVERPLAY" (wrong)
        MeaningTagId.OVERPLAY.value = "overplay" (correct)
    """
    if isinstance(key, Enum):
        return str(key.value)
    return str(key)


def _combine_meaning_tags(
    meaning_tags_by_player: dict[str, dict[str, int]],
) -> dict[str, int]:
    """Combine meaning tags from both players (B + W).

    Args:
        meaning_tags_by_player: {"B": {"tag": count}, "W": {"tag": count}}

    Returns:
        Combined dict {"tag": total_count}, excluding UNCERTAIN

    Note:
        Uses UNCERTAIN_TAG = MeaningTagId.UNCERTAIN.value for filtering.
    """
    combined: dict[str, int] = {}
    for player_tags in meaning_tags_by_player.values():
        for key, count in player_tags.items():
            normalized = _normalize_meaning_tag_key(key)
            if normalized == UNCERTAIN_TAG:
                continue  # Skip UNCERTAIN
            combined[normalized] = combined.get(normalized, 0) + count
    return combined


def _round_half_up(value: float) -> int:
    """Round non-negative value to nearest integer using half-up rounding.

    Args:
        value: Non-negative float to round

    Returns:
        Rounded integer

    Precondition:
        value >= 0. Behavior for negative values is undefined.

    Note:
        Python's round() uses banker's rounding (round half to even),
        which can give surprising results (12.5 -> 12).
        This function always rounds .5 up (12.5 -> 13).
    """
    return int(math.floor(value + 0.5))


def _wrap_debug_info(
    debug_dict: dict[str, Any] | None,
) -> Mapping[str, Any] | None:
    """Wrap debug dict in MappingProxyType for immutability.

    Args:
        debug_dict: Mutable dict or None

    Returns:
        Immutable MappingProxyType wrapper over a COPY of the dict, or None

    Note:
        Creates a shallow copy before wrapping to prevent mutation via
        the original dict reference. This ensures true immutability.
    """
    if debug_dict is None:
        return None
    return MappingProxyType(dict(debug_dict))  # Copy then wrap


# =============================================================================
# Needs Match Calculation
# =============================================================================


def compute_needs_match(
    user_aggregate: AggregatedRadarResult | None,
    meaning_tags_combined: dict[str, int],
    config: SuitabilityConfig = DEFAULT_CONFIG,
) -> float:
    """Compute needs_match score.

    Args:
        user_aggregate: From UserRadarAggregate.get_aggregate()
        meaning_tags_combined: Combined tags from both players (already normalized)
        config: Scoring configuration

    Returns:
        0.0 if: no user data, no weak axes, or total_occurrences < min_tag_occurrences
        Otherwise: matching_occurrences / total_occurrences (0.0-1.0)

    Denominator semantics:
        - total_occurrences = sum of all tag counts (e.g., {"a":2, "b":3} = 5)
        - matching_occurrences = sum of counts for tags related to weak axes
        - This uses OCCURRENCE COUNT, not distinct tag count
        - min_tag_occurrences threshold also uses occurrence count

    Supported axes:
        Only iterates over SUPPORTED_AXES (the 5 axes defined in AXIS_TO_MEANING_TAGS).
        This prevents breakage if RadarAxis enum gains new members in the future.
    """
    if user_aggregate is None:
        return 0.0

    # Get weak axes - only iterate SUPPORTED_AXES
    weak_axes = [axis for axis in SUPPORTED_AXES if user_aggregate.is_weak_axis(axis)]
    if not weak_axes:
        return 0.0

    # Collect related tags for weak axes
    related_tags: set[str] = set()
    for axis in weak_axes:
        related_tags.update(AXIS_TO_MEANING_TAGS[axis])  # KeyError impossible

    # Calculate occurrences
    total_occurrences = sum(meaning_tags_combined.values())
    if total_occurrences < config.min_tag_occurrences:
        return 0.0

    matching_occurrences = sum(
        count for tag, count in meaning_tags_combined.items() if tag in related_tags
    )

    return matching_occurrences / total_occurrences


# =============================================================================
# Stability Calculation
# =============================================================================


def _collect_score_leads(game: Game) -> list[float]:
    """Collect scoreLead values from mainline nodes only.

    Traversal rules:
        - Start from game.root
        - Follow mainline only (node.children[0] if exists)
        - Skip nodes where:
          - node.analysis is None/falsy
          - node.analysis has no "root_info" key
          - root_info has no "scoreLead" key
          - scoreLead is None or not a number
          - scoreLead is NaN or infinity

    What counts as valid scoreLead:
        - node.analysis["root_info"]["scoreLead"] exists
        - Value is a finite float (not NaN, not inf)

    Returns:
        List of valid scoreLead values in move order.
        May be empty if no analyzed nodes or all nodes lack scoreLead.

    Note:
        Variations/branches are NOT included.
        This ensures consistent behavior for stability calculation.
        Missing root_info is silently skipped (common for unanalyzed nodes).
    """
    values: list[float] = []
    node: GameNode | None = game.root
    while node is not None:
        # Skip if no analysis data
        if node.analysis:
            # Safely get root_info (may be missing)
            root_info = node.analysis.get("root_info")
            if root_info is not None:
                score_lead = root_info.get("scoreLead")
                if score_lead is not None and isinstance(score_lead, (int, float)):
                    if math.isfinite(score_lead):
                        values.append(float(score_lead))
        # Follow mainline only (cast to GameNode since game.root is GameNode)
        node = cast(GameNode, node.children[0]) if node.children else None
    return values


def _compute_volatility(values: list[float]) -> float | None:
    """Compute volatility as population standard deviation.

    Mirrors Phase 61 logic (katrain/core/analysis/risk/analyzer.py:178-195).
    Copied here to avoid importing private function.

    Args:
        values: List of scoreLead values (already validated)

    Returns:
        Population standard deviation, or None if len(values) < 2

    Note:
        Uses /n (population), not /n-1 (sample).
        This matches Phase 61 thresholds.
    """
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def compute_stability(
    game: Game,
    config: SuitabilityConfig = DEFAULT_CONFIG,
) -> float:
    """Compute stability score from game's scoreLead volatility.

    Algorithm:
        1. Collect scoreLead from mainline nodes
        2. Compute population stdev (volatility)
        3. stability = 1.0 - clamp(volatility / max_volatility, 0, 1)

    Returns:
        config.stability_insufficient_data (default 0.0) if < 2 valid scores
        0.0-1.0 based on stability (higher = more stable)

    Note:
        Does NOT use volatility_window. Uses all mainline scoreLead values.
        This is simpler than Phase 61's rolling-window approach.

        Default 0.0 for insufficient data ensures unanalyzed games are not
        artificially boosted. This can be changed via config if needed.
    """
    values = _collect_score_leads(game)
    volatility = _compute_volatility(values)

    if volatility is None:
        return config.stability_insufficient_data  # Default 0.0

    if config.max_volatility <= 0:
        return config.stability_insufficient_data

    normalized = volatility / config.max_volatility
    clamped = max(0.0, min(1.0, normalized))
    return 1.0 - clamped


# =============================================================================
# Total Calculation
# =============================================================================


def _compute_total(
    needs_match: float,
    stability: float,
    config: SuitabilityConfig,
) -> float:
    """Compute weighted total with normalized weights.

    Weights are normalized: w_n + w_s = 1.0
    total = needs_match * (w_n / sum) + stability * (w_s / sum)

    If weight_sum <= 0, returns 0.0.
    """
    weight_sum = config.needs_match_weight + config.stability_weight
    if weight_sum <= 0:
        return 0.0
    w_n = config.needs_match_weight / weight_sum
    w_s = config.stability_weight / weight_sum
    return needs_match * w_n + stability * w_s


# =============================================================================
# Percentile Calculation (ECDF-style)
# =============================================================================


def compute_batch_percentiles(
    scores: list[SuitabilityScore],
) -> list[SuitabilityScore]:
    """Assign percentile ranks based on total score using ECDF-style calculation.

    Specification (ECDF-style):
        - For each score, percentile = round_half_up((count(total <= x) / n) * 100)
        - This means: "what percentage of games have total <= this game's total"
        - Top-tied items always get percentile = 100
        - Single item: percentile = 100
        - Empty list: return empty list
        - Rounding: half-up (12.5 -> 13)

    Why ECDF-style:
        Ensures that the best games (highest total) always get percentile = 100,
        even when tied. This makes ">=X%" threshold filtering work correctly.

    Returns:
        New list of SuitabilityScore objects with percentile set.
    """
    if not scores:
        return []

    n = len(scores)
    totals = [s.total for s in scores]

    # For each score, count how many scores have total <= this total
    result: list[SuitabilityScore] = []
    for score in scores:
        count_le = sum(1 for t in totals if t <= score.total)
        percentile = _round_half_up((count_le / n) * 100)
        result.append(
            SuitabilityScore(
                needs_match=score.needs_match,
                stability=score.stability,
                total=score.total,
                percentile=percentile,
                debug_info=score.debug_info,
            )
        )

    return result


# =============================================================================
# Public API
# =============================================================================


def score_game_suitability(
    user_aggregate: AggregatedRadarResult | None,
    game: Game,
    game_stats: dict[str, Any],
    config: SuitabilityConfig = DEFAULT_CONFIG,
) -> SuitabilityScore:
    """Score a single game's suitability.

    Args:
        user_aggregate: User's aggregated radar (can be None)
        game: Game object (required for stability calculation)
        game_stats: Stats dict with meaning_tags_by_player
        config: Scoring configuration

    Returns:
        SuitabilityScore with percentile=None (set later by batch)

    Note:
        debug_info is wrapped via _wrap_debug_info() which copies the dict
        before wrapping in MappingProxyType, ensuring true immutability.
    """
    # Get meaning tags from stats
    meaning_tags_by_player = game_stats.get("meaning_tags_by_player", {})
    meaning_tags_combined = _combine_meaning_tags(meaning_tags_by_player)

    # Calculate components
    needs_match = compute_needs_match(user_aggregate, meaning_tags_combined, config)
    stability = compute_stability(game, config)
    total = _compute_total(needs_match, stability, config)

    # Build debug info
    debug_dict: dict[str, Any] = {
        "meaning_tags_combined": meaning_tags_combined,
        "weak_axes": (
            [
                axis.value
                for axis in SUPPORTED_AXES
                if user_aggregate is not None and user_aggregate.is_weak_axis(axis)
            ]
            if user_aggregate is not None
            else []
        ),
    }

    return SuitabilityScore(
        needs_match=needs_match,
        stability=stability,
        total=total,
        percentile=None,  # Set later by batch
        debug_info=_wrap_debug_info(debug_dict),
    )


def score_batch_suitability(
    user_aggregate: AggregatedRadarResult | None,
    games_and_stats: list[tuple[Game, dict[str, Any]]],
    config: SuitabilityConfig = DEFAULT_CONFIG,
) -> list[SuitabilityScore]:
    """Score multiple games and compute batch-relative percentiles.

    Args:
        user_aggregate: User's aggregated radar (can be None)
        games_and_stats: List of (Game, game_stats) tuples
        config: Scoring configuration

    Returns:
        List of SuitabilityScore with percentiles computed (ECDF-style)
    """
    # Score each game
    scores = [
        score_game_suitability(user_aggregate, game, stats, config)
        for game, stats in games_and_stats
    ]

    # Compute percentiles
    return compute_batch_percentiles(scores)
