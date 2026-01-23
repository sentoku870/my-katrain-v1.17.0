# -*- coding: utf-8 -*-
"""Meaning Tags System - Public API.

This package provides semantic classification of Go mistakes based on
KataGo analysis data. It converts numerical metrics (loss, policy, etc.)
into human-understandable categories like "Life/Death Error" or "Direction Error".

Part of Phase 46: Meaning Tags System Core.
Extended in Phase 47: Meaning Tags Integration.

Public API (PR-1 - Models & Registry):
    - MeaningTagId: Enum of all 12 tag identifiers
    - MeaningTag: Immutable classification result
    - MeaningTagDefinition: Static tag metadata
    - MEANING_TAG_REGISTRY: Dict of all tag definitions
    - get_tag_definition(): Get definition by ID
    - get_tag_label(): Get localized label
    - get_tag_description(): Get localized description

Public API (PR-2 - Classifier Core):
    - ClassificationContext: Additional context for classification
    - classify_meaning_tag(): Main classification function
    - resolve_lexicon_anchor(): Lexicon anchor resolution
    - Helper functions: get_loss_value, classify_gtp_move, is_classifiable_move,
                       compute_move_distance, is_endgame

Public API (Phase 47 - Integration Helpers):
    - normalize_lang(): Normalize language code ("jp" → "ja")
    - get_meaning_tag_label_safe(): Safe label lookup with None handling
    - format_meaning_tag_with_definition(): Display helper with truncation
    - format_meaning_tag_with_definition_safe(): Safe version of above

Example usage:
    >>> from katrain.core.analysis.meaning_tags import (
    ...     MeaningTagId,
    ...     MeaningTag,
    ...     classify_meaning_tag,
    ...     ClassificationContext,
    ...     get_tag_label,
    ... )
    >>> # Simple classification (MoveEval only)
    >>> tag = classify_meaning_tag(move_eval)
    >>> get_tag_label(tag.id, "en")
    'Life/Death Error'

    >>> # With additional context
    >>> context = ClassificationContext(move_distance=12, actual_move_policy=0.001)
    >>> tag = classify_meaning_tag(move_eval, context=context)
"""

from .classifier import (
    THRESHOLD_DISTANCE_CLOSE,
    THRESHOLD_DISTANCE_FAR,
    THRESHOLD_ENDGAME_RATIO,
    THRESHOLD_LOSS_CATASTROPHIC,
    THRESHOLD_LOSS_CUT_RISK,
    THRESHOLD_LOSS_HUGE,
    THRESHOLD_LOSS_LARGE,
    THRESHOLD_LOSS_MEDIUM,
    THRESHOLD_LOSS_SIGNIFICANT,
    THRESHOLD_LOSS_SMALL,
    THRESHOLD_MOVE_EARLY_GAME,
    THRESHOLD_MOVE_ENDGAME_ABSOLUTE,
    THRESHOLD_OWNERSHIP_FLUX_LIFE_DEATH,
    THRESHOLD_POLICY_ACTUAL_LOW,
    THRESHOLD_POLICY_BEST_HIGH,
    THRESHOLD_POLICY_LOW,
    THRESHOLD_POLICY_TRAP,
    THRESHOLD_POLICY_VERY_LOW,
    THRESHOLD_SCORE_STDEV_HIGH,
    ClassificationContext,
    classify_gtp_move,
    classify_meaning_tag,
    compute_move_distance,
    get_loss_value,
    is_classifiable_move,
    is_endgame,
    resolve_lexicon_anchor,
)
from .models import MeaningTag, MeaningTagId
from .registry import (
    MEANING_TAG_REGISTRY,
    MeaningTagDefinition,
    get_tag_definition,
    get_tag_description,
    get_tag_label,
)
from .integration import (
    MAX_DESCRIPTION_LENGTH,
    format_meaning_tag_with_definition,
    format_meaning_tag_with_definition_safe,
    get_meaning_tag_label_safe,
    normalize_lang,
)

__all__ = [
    # Models (PR-1)
    "MeaningTagId",
    "MeaningTag",
    # Registry (PR-1)
    "MeaningTagDefinition",
    "MEANING_TAG_REGISTRY",
    "get_tag_definition",
    "get_tag_label",
    "get_tag_description",
    # Classifier (PR-2)
    "ClassificationContext",
    "classify_meaning_tag",
    "resolve_lexicon_anchor",
    # Helper functions (PR-2)
    "get_loss_value",
    "classify_gtp_move",
    "is_classifiable_move",
    "compute_move_distance",
    "is_endgame",
    # Threshold constants (PR-2)
    "THRESHOLD_LOSS_SIGNIFICANT",
    "THRESHOLD_LOSS_SMALL",
    "THRESHOLD_LOSS_MEDIUM",
    "THRESHOLD_LOSS_CUT_RISK",
    "THRESHOLD_LOSS_LARGE",
    "THRESHOLD_LOSS_HUGE",
    "THRESHOLD_LOSS_CATASTROPHIC",
    "THRESHOLD_OWNERSHIP_FLUX_LIFE_DEATH",
    "THRESHOLD_POLICY_VERY_LOW",
    "THRESHOLD_POLICY_LOW",
    "THRESHOLD_POLICY_ACTUAL_LOW",
    "THRESHOLD_POLICY_TRAP",
    "THRESHOLD_POLICY_BEST_HIGH",
    "THRESHOLD_SCORE_STDEV_HIGH",
    "THRESHOLD_DISTANCE_CLOSE",
    "THRESHOLD_DISTANCE_FAR",
    "THRESHOLD_MOVE_EARLY_GAME",
    "THRESHOLD_MOVE_ENDGAME_ABSOLUTE",
    "THRESHOLD_ENDGAME_RATIO",
    # Integration helpers (Phase 47)
    "normalize_lang",
    "get_meaning_tag_label_safe",
    "format_meaning_tag_with_definition",
    "format_meaning_tag_with_definition_safe",
    "MAX_DESCRIPTION_LENGTH",
]
