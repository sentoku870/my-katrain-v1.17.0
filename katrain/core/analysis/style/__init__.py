# -*- coding: utf-8 -*-
"""Style Archetype System - Public API.

This package provides style archetype analysis based on RadarMetrics and
MeaningTag data. It classifies users into positive playing style identities.

Part of Phase 56: Style Archetype Core.

Public API:
    - StyleArchetypeId: Enum of all 6 archetype identifiers
    - StyleArchetype: Immutable archetype definition
    - StyleResult: Analysis result with confidence
    - STYLE_ARCHETYPES: Registry of all archetype definitions
    - determine_style(): Main analysis function

Example usage:
    >>> from katrain.core.analysis.style import (
    ...     determine_style,
    ...     StyleArchetypeId,
    ... )
    >>> result = determine_style(radar_metrics, tag_counts)
    >>> result.archetype.id
    <StyleArchetypeId.KIAI_FIGHTER: 'kiai_fighter'>
"""

from .analyzer import (
    CONFIDENCE_NORMALIZATION,
    DEVIATION_HIGH_THRESHOLD,
    DEVIATION_LOW_THRESHOLD,
    SCORE_TOLERANCE,
    TAG_SIGNIFICANT_COUNT,
    compute_confidence,
    determine_style,
    scores_are_tied,
)
from .models import (
    STYLE_ARCHETYPES,
    StyleArchetype,
    StyleArchetypeId,
    StyleResult,
)

__all__ = [
    # Models
    "StyleArchetypeId",
    "StyleArchetype",
    "StyleResult",
    "STYLE_ARCHETYPES",
    # Analyzer
    "determine_style",
    "compute_confidence",
    "scores_are_tied",
    # Constants
    "DEVIATION_HIGH_THRESHOLD",
    "DEVIATION_LOW_THRESHOLD",
    "TAG_SIGNIFICANT_COUNT",
    "SCORE_TOLERANCE",
    "CONFIDENCE_NORMALIZATION",
]
