"""Meaning Tags Integration Helpers.

This module provides helper functions for integrating meaning tags with
other parts of the system (stats, karte, summary).

Part of Phase 47: Meaning Tags Integration.
Updated in Phase 52: Use common locale_utils for consistency.

Public API:
    - normalize_lang(): Normalize language code ("jp" → "ja") for registry lookups
    - get_meaning_tag_label_safe(): Safe label lookup with None handling
    - format_meaning_tag_with_definition(): Display helper with truncation
"""

from katrain.common.locale_utils import to_iso_lang_code

from .models import MeaningTagId
from .registry import MEANING_TAG_REGISTRY, get_tag_label

# =============================================================================
# Language Normalization (for meaning tags registry - needs ISO codes)
# =============================================================================

# Backward compatibility alias:
# This module requires ISO codes ("en", "ja") for registry lookups.
# The common to_iso_lang_code function provides exactly this:
#   - "jp" -> "ja"
#   - "ja" -> "ja"
#   - "en" -> "en"
#   - region variants like "ja_JP" -> "ja"
normalize_lang = to_iso_lang_code


# =============================================================================
# Safe Label Lookup
# =============================================================================


def get_meaning_tag_label_safe(
    tag_id_str: str | None,
    lang: str = "ja",
) -> str | None:
    """Get meaning tag label with safe None handling.

    Unlike get_tag_label() which raises KeyError for invalid IDs,
    this function returns None for None input or unknown tag IDs.

    Args:
        tag_id_str: Tag ID string (e.g., "overplay") or None
        lang: Language code ("en", "ja", or "jp")

    Returns:
        Localized label string, or None if tag_id_str is None/invalid

    Examples:
        >>> get_meaning_tag_label_safe("life_death_error", "ja")
        '死活ミス'
        >>> get_meaning_tag_label_safe("life_death_error", "en")
        'Life/Death Error'
        >>> get_meaning_tag_label_safe(None, "ja")
        None
        >>> get_meaning_tag_label_safe("invalid_tag", "ja")
        None
    """
    if tag_id_str is None:
        return None

    # Normalize language
    normalized_lang = normalize_lang(lang)

    # Try to convert string to MeaningTagId
    try:
        tag_id = MeaningTagId(tag_id_str)
    except ValueError:
        # Unknown tag ID string
        return None

    return get_tag_label(tag_id, normalized_lang)


# =============================================================================
# Display Formatting
# =============================================================================

# Maximum length for truncated descriptions
MAX_DESCRIPTION_LENGTH = 30


def format_meaning_tag_with_definition(
    tag_id: MeaningTagId,
    lang: str = "ja",
) -> str:
    """Format meaning tag with label and truncated description.

    Creates a display string like "死活ミス: 石の生死に関わる重大なミスです..."

    Args:
        tag_id: MeaningTagId enum value
        lang: Language code ("en", "ja", or "jp")

    Returns:
        Formatted string: "{label}: {truncated_description}"

    Examples:
        >>> format_meaning_tag_with_definition(MeaningTagId.LIFE_DEATH_ERROR, "ja")
        '死活ミス: 石の生死に関わる重大なミスです。ow...'
        >>> format_meaning_tag_with_definition(MeaningTagId.UNCERTAIN, "en")
        'Uncertain: Could not be clearly class...'
    """
    # Normalize language
    normalized_lang = normalize_lang(lang)

    # Get definition from registry
    definition = MEANING_TAG_REGISTRY[tag_id]

    # Get localized label and description
    if normalized_lang == "en":
        label = definition.en_label
        description = definition.en_description
    else:
        label = definition.ja_label
        description = definition.ja_description

    # Truncate description if too long
    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = description[:MAX_DESCRIPTION_LENGTH] + "..."

    return f"{label}: {description}"


def format_meaning_tag_with_definition_safe(
    tag_id_str: str | None,
    lang: str = "ja",
) -> str | None:
    """Safe version of format_meaning_tag_with_definition.

    Args:
        tag_id_str: Tag ID string or None
        lang: Language code

    Returns:
        Formatted string, or None if tag_id_str is None/invalid
    """
    if tag_id_str is None:
        return None

    try:
        tag_id = MeaningTagId(tag_id_str)
    except ValueError:
        return None

    return format_meaning_tag_with_definition(tag_id, lang)
