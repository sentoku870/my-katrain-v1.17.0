# -*- coding: utf-8 -*-
"""Meaning Tags System - Public API.

This package provides semantic classification of Go mistakes based on
KataGo analysis data. It converts numerical metrics (loss, policy, etc.)
into human-understandable categories like "Life/Death Error" or "Direction Error".

Part of Phase 46: Meaning Tags System Core.

Public API (PR-1 - Models & Registry):
    - MeaningTagId: Enum of all 12 tag identifiers
    - MeaningTag: Immutable classification result
    - MeaningTagDefinition: Static tag metadata
    - MEANING_TAG_REGISTRY: Dict of all tag definitions
    - get_tag_definition(): Get definition by ID
    - get_tag_label(): Get localized label
    - get_tag_description(): Get localized description

Future additions (PR-2 - Classifier Core):
    - ClassificationContext: Additional context for classification
    - classify_meaning_tag(): Main classification function
    - resolve_lexicon_anchor(): Lexicon anchor resolution

Example usage:
    >>> from katrain.core.analysis.meaning_tags import (
    ...     MeaningTagId,
    ...     MeaningTag,
    ...     get_tag_label,
    ... )
    >>> tag = MeaningTag(id=MeaningTagId.LIFE_DEATH_ERROR)
    >>> get_tag_label(tag.id, "en")
    'Life/Death Error'
"""

from .models import MeaningTag, MeaningTagId
from .registry import (
    MEANING_TAG_REGISTRY,
    MeaningTagDefinition,
    get_tag_definition,
    get_tag_description,
    get_tag_label,
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
]
