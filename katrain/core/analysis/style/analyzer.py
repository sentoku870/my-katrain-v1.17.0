# -*- coding: utf-8 -*-
"""Style Archetype Analyzer.

This module provides the core logic for determining a user's playing style
archetype based on RadarMetrics and MeaningTag counts.

Part of Phase 56: Style Archetype Core.
"""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.analysis.skill_radar import RadarAxis, RadarMetrics

from .models import (
    STYLE_ARCHETYPES,
    StyleArchetype,
    StyleArchetypeId,
    StyleResult,
)


# =============================================================================
# Constants
# =============================================================================

# RadarMetrics scores are 1.0-5.0 (4-point range)
DEVIATION_HIGH_THRESHOLD = 0.5  # axis deviation >= 0.5 -> "high"
DEVIATION_LOW_THRESHOLD = -0.5  # axis deviation <= -0.5 -> "low"
TAG_SIGNIFICANT_COUNT = 2  # tag count >= 2 -> considered significant

# Tolerance for float comparison (tie detection)
SCORE_TOLERANCE = 1e-9  # abs_tol for math.isclose

# Confidence normalization: gap of 0.3 = 100% confidence
CONFIDENCE_NORMALIZATION = 0.3

# Precomputed enum order maps (avoid repeated list().index() calls)
RADAR_AXIS_ORDER = {axis: i for i, axis in enumerate(RadarAxis)}
ARCHETYPE_ORDER = {aid: i for i, aid in enumerate(StyleArchetypeId)}


# =============================================================================
# Helper Functions
# =============================================================================


def scores_are_tied(a: float, b: float) -> bool:
    """Check if two scores are effectively equal (within tolerance).

    Args:
        a: First score
        b: Second score

    Returns:
        True if scores are within SCORE_TOLERANCE of each other
    """
    return math.isclose(a, b, abs_tol=SCORE_TOLERANCE)


def compute_confidence(best_score: float, second_best_score: float) -> float:
    """Compute confidence from gap between best and second-best archetype score.

    Precondition: Called ONLY after balance check passes.
    Fallback cases (balanced radar) are handled by caller with confidence=0.5.

    Formula:
        gap = max(best_score - second_best_score, 0.0)  # Defensive clamp
        confidence = min(gap / 0.3, 1.0)  # 0.3 gap = 100% confidence

    Args:
        best_score: Score of the best matching archetype
        second_best_score: Score of the second-best matching archetype

    Returns:
        0.0 on tie (scores_are_tied), up to 1.0 for large margin
    """
    if scores_are_tied(best_score, second_best_score):
        return 0.0
    gap = max(best_score - second_best_score, 0.0)
    return min(gap / CONFIDENCE_NORMALIZATION, 1.0)


# =============================================================================
# Main Analysis Function
# =============================================================================


def determine_style(
    radar: RadarMetrics,
    tag_counts: Mapping[MeaningTagId, int],
) -> StyleResult:
    """Determine the user's playing style archetype.

    Args:
        radar: RadarMetrics with valid scores for all 5 axes (1.0-5.0)
        tag_counts: Mapping of MeaningTagId -> count (can be empty)

    Returns:
        StyleResult with determined archetype and confidence

    Algorithm:
        1. Compute axis deviations from 5-axis mean
        2. Find dominant axis (highest deviation, None if tied)
        3. BALANCE-FIRST: If no axis exceeds threshold, return BALANCE_MASTER
        4. Score each archetype (except BALANCE_MASTER)
        5. Select best archetype (deterministic on ties via enum order)
        6. Compute confidence from score gap
    """
    # Step 1: Compute axis deviations
    scores = {
        RadarAxis.OPENING: radar.opening,
        RadarAxis.FIGHTING: radar.fighting,
        RadarAxis.ENDGAME: radar.endgame,
        RadarAxis.STABILITY: radar.stability,
        RadarAxis.AWARENESS: radar.awareness,
    }
    mean_score = sum(scores.values()) / 5.0
    deviations = {axis: score - mean_score for axis, score in scores.items()}

    # Step 2: Find dominant axis (using precomputed order map for determinism)
    sorted_axes = sorted(
        deviations.items(),
        key=lambda x: (-x[1], RADAR_AXIS_ORDER[x[0]]),
    )
    top_axis, top_deviation = sorted_axes[0]

    # Tie check: if second axis has same deviation (within tolerance), dominant_axis is None
    if len(sorted_axes) > 1 and math.isclose(
        sorted_axes[1][1], top_deviation, abs_tol=SCORE_TOLERANCE
    ):
        dominant_axis = None
    elif top_deviation >= DEVIATION_HIGH_THRESHOLD:
        dominant_axis = top_axis
    else:
        dominant_axis = None

    # Step 3: BALANCE-FIRST RULE - if no axis exceeds threshold, return BALANCE_MASTER
    max_abs_deviation = max(abs(d) for d in deviations.values())
    if max_abs_deviation < DEVIATION_HIGH_THRESHOLD:
        return StyleResult(
            archetype=STYLE_ARCHETYPES[StyleArchetypeId.BALANCE_MASTER],
            confidence=0.5,
            axis_deviations=MappingProxyType(deviations),
            dominant_axis=None,
        )

    # Step 4: Score each archetype (except BALANCE_MASTER)
    archetype_scores: list[tuple[StyleArchetype, float]] = []

    for archetype_id in StyleArchetypeId:
        if archetype_id == StyleArchetypeId.BALANCE_MASTER:
            continue
        archetype = STYLE_ARCHETYPES[archetype_id]

        # High axis score (0.5 weight)
        if archetype.high_axes:
            high_match = sum(
                1
                for ax in archetype.high_axes
                if deviations[ax] >= DEVIATION_HIGH_THRESHOLD
            )
            high_axis_score = (high_match / len(archetype.high_axes)) * 0.5
        else:
            high_axis_score = 0.0

        # Low axis score (0.2 weight)
        if archetype.low_axes:
            low_match = sum(
                1
                for ax in archetype.low_axes
                if deviations[ax] <= DEVIATION_LOW_THRESHOLD
            )
            low_axis_score = (low_match / len(archetype.low_axes)) * 0.2
        else:
            low_axis_score = 0.0

        # Tag score (0.3 weight)
        if archetype.reinforcing_tags:
            sig_tags = sum(
                1
                for tag in archetype.reinforcing_tags
                if tag_counts.get(tag, 0) >= TAG_SIGNIFICANT_COUNT
            )
            tag_score = (sig_tags / len(archetype.reinforcing_tags)) * 0.3
        else:
            tag_score = 0.0

        total_score = high_axis_score + low_axis_score + tag_score
        archetype_scores.append((archetype, total_score))

    # Step 5: Sort by score descending, then enum order for determinism
    archetype_scores.sort(key=lambda x: (-x[1], ARCHETYPE_ORDER[x[0].id]))

    best_archetype, best_score = archetype_scores[0]
    second_best_score = archetype_scores[1][1] if len(archetype_scores) > 1 else 0.0

    # Step 6: Compute confidence (balance case already handled in Step 3)
    confidence = compute_confidence(best_score, second_best_score)

    # Step 7: Return result (confidence is raw float; rounding in to_dict only)
    return StyleResult(
        archetype=best_archetype,
        confidence=confidence,
        axis_deviations=MappingProxyType(deviations),
        dominant_axis=dominant_axis,
    )
