"""Scoring logic for Curator (Phase 63).

This module implements suitability scoring for game records,
evaluating how well they match a user's learning needs.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from katrain.core.game_node import GameNode

from .models import (
    DEFAULT_CONFIG,
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


def _extract_user_weak_tags(
    user_aggregate: Any,
    min_occurrences: int,
) -> set[str]:
    """Extract the set of meaning tags the user is weak at.

    Phase A-1: lightweight replacement for the deprecated radar-axis
    approach. We accept the ``user_aggregate`` object produced by batch
    processing and look for a meaningful-tag count map on it. The
    supported shapes are:

    - ``user_aggregate.weak_tags`` : set[str] / dict[str, int] (preferred)
    - ``user_aggregate.meaning_tags`` : set[str] / dict[str, int] (alias)
    - ``user_aggregate.meaning_tags_by_player`` : {"B": {...}, "W": {...}}

    Anything else returns an empty set so that ``needs_match`` falls back
    to the configured insufficient-data value rather than silently
    applying a meaningless default.

    Args:
        user_aggregate: User aggregated profile or None.
        min_occurrences: When the candidate is a count dict, tags must
            appear at least this many times to count as a real weakness.

    Returns:
        Set of normalised tag names.
    """
    if user_aggregate is None:
        return set()

    weak_set: set[str] | None = None
    counts: dict[str, int] | None = None
    for attr in ("weak_tags", "meaning_tags"):
        candidate = getattr(user_aggregate, attr, None)
        if isinstance(candidate, set):
            weak_set = {str(t) for t in candidate if t != UNCERTAIN_TAG}
            break
        if isinstance(candidate, dict):
            counts = candidate
            break
    if weak_set is None and counts is None:
        per_player = getattr(user_aggregate, "meaning_tags_by_player", None)
        if isinstance(per_player, dict):
            counts = {}
            for player_tags in per_player.values():
                if not isinstance(player_tags, dict):
                    continue
                for key, count in player_tags.items():
                    if not isinstance(count, (int, float)):
                        continue
                    tag = _normalize_meaning_tag_key(key)
                    if tag == UNCERTAIN_TAG:
                        continue
                    counts[tag] = counts.get(tag, 0) + int(count)

    if weak_set is not None:
        return {t for t in weak_set if t != UNCERTAIN_TAG}
    if counts:
        return {tag for tag, count in counts.items() if count >= min_occurrences and tag != UNCERTAIN_TAG}
    return set()


def _compute_jaccard_score(
    user_weak_tags: set[str],
    game_tags_combined: dict[str, int],
    config: SuitabilityConfig,
) -> float:
    """Compute the Jaccard-style needs_match score.

    Returns ``config.jaccard_insufficient_data`` when there is no overlap
    to compare against (no user weak tags known, or the game has no
    tags). Otherwise returns |A ∩ B| / |A ∪ B| ∈ [0, 1].

    Args:
        user_weak_tags: Set of tags the user struggles with.
        game_tags_combined: Combined game tags {tag: count}, may be empty.
        config: Suitability config (only ``min_tag_occurrences`` and
            ``jaccard_insufficient_data`` are consulted).

    Returns:
        Jaccard score in [0, 1] or the configured insufficient-data value.
    """
    if not user_weak_tags or not game_tags_combined:
        return config.jaccard_insufficient_data
    game_tags = {
        tag for tag, count in game_tags_combined.items() if count >= config.min_tag_occurrences and tag != UNCERTAIN_TAG
    }
    if not game_tags:
        return config.jaccard_insufficient_data
    intersection = user_weak_tags & game_tags
    union = user_weak_tags | game_tags
    if not union:
        return config.jaccard_insufficient_data
    return len(intersection) / len(union)


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
                if score_lead is not None and isinstance(score_lead, (int, float)) and math.isfinite(score_lead):
                    values.append(float(score_lead))
        # Follow mainline only (cast to GameNode since game.root is GameNode)
        node = cast(GameNode, node.children[0]) if node.children else None
    return values


def _compute_volatility(values: list[float]) -> float | None:
    """Compute volatility as population standard deviation.

    Standalone helper: kept local to avoid a dependency on the private
    helper inside ``katrain/core/analysis/`` that would otherwise have
    to be promoted to the public API just for this single call site.

    Args:
        values: List of scoreLead values (already validated)

    Returns:
        Population standard deviation, or None if len(values) < 2

    Note:
        Uses /n (population), not /n-1 (sample). This matches the
        volatility convention used elsewhere in the analysis layer.
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
    game: Game,
    game_stats: dict[str, Any],
    config: SuitabilityConfig = DEFAULT_CONFIG,
    user_aggregate: Any = None,
) -> SuitabilityScore:
    """Score a single game's suitability.

    Args:
        game: Game object (required for stability calculation)
        game_stats: Stats dict with meaning_tags_by_player
        config: Scoring configuration
        user_aggregate: User aggregated profile (optional). When supplied,
            ``needs_match`` is computed via Jaccard similarity between the
            user's weak meaning tags and the game's tags. Without it,
            ``needs_match`` falls back to ``config.jaccard_insufficient_data``.

    Returns:
        SuitabilityScore with percentile=None (set later by batch)

    Note:
        debug_info is wrapped via _wrap_debug_info() which copies the dict
        before wrapping in MappingProxyType, ensuring true immutability.
    """
    # Get meaning tags from stats
    meaning_tags_by_player = game_stats.get("meaning_tags_by_player", {})
    meaning_tags_combined = _combine_meaning_tags(meaning_tags_by_player)

    # Phase A-1: Jaccard-based needs_match replaces the deprecated Radar
    # axes. We compute it from the user's weak tags and the game's
    # combined tag counts.
    user_weak_tags = _extract_user_weak_tags(user_aggregate, config.min_tag_occurrences)
    needs_match = _compute_jaccard_score(user_weak_tags, meaning_tags_combined, config)
    stability = compute_stability(game, config)
    total = _compute_total(needs_match, stability, config)

    # Build debug info
    debug_dict: dict[str, Any] = {
        "meaning_tags_combined": meaning_tags_combined,
        "user_weak_tags": sorted(user_weak_tags),
    }

    return SuitabilityScore(
        needs_match=needs_match,
        stability=stability,
        total=total,
        percentile=None,  # Set later by batch
        debug_info=_wrap_debug_info(debug_dict),
    )


def score_batch_suitability(
    games_and_stats: list[tuple[Game, dict[str, Any]]],
    config: SuitabilityConfig = DEFAULT_CONFIG,
    user_aggregate: Any = None,
) -> list[SuitabilityScore]:
    """Score multiple games and compute batch-relative percentiles.

    Args:
        games_and_stats: List of (Game, game_stats) tuples
        config: Scoring configuration
        user_aggregate: Optional user profile forwarded to each
            ``score_game_suitability`` call.

    Returns:
        List of SuitabilityScore with percentiles computed (ECDF-style)
    """
    # Score each game
    scores = [score_game_suitability(game, stats, config, user_aggregate) for game, stats in games_and_stats]

    # Compute percentiles
    return compute_batch_percentiles(scores)
