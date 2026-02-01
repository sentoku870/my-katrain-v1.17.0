# -*- coding: utf-8 -*-
"""Language and locale utilities (Kivy-independent).

Canonical internal language codes: "en", "jp"
These match the locale directories in katrain/i18n/locales/.

Part of Phase 52: Stabilization (tofu fix + jp/ja consistency).
"""
from typing import Literal

# Canonical internal language codes (match locale directories)
InternalLangCode = Literal["en", "jp"]

# ISO 639-1 codes (for external APIs like meaning tags registry)
IsoLangCode = Literal["en", "ja"]

# Mapping to internal canonical codes
_TO_INTERNAL: dict[str, InternalLangCode] = {"ja": "jp", "jp": "jp", "en": "en"}

# Mapping from internal to ISO codes
_TO_ISO: dict[str, IsoLangCode] = {"jp": "ja", "en": "en"}


def normalize_lang_code(lang: str | None) -> InternalLangCode:
    """Normalize language code to internal canonical form.

    Internal canonical codes match locale directories: "en", "jp".
    Accepts ISO "ja" as alias for "jp".
    Unknown codes fall back to "en".

    Handles real-world inputs:
    - None/empty -> "en"
    - Strips whitespace, lowercases
    - Reduces region variants: "ja_JP" -> "ja", "ja-JP" -> "ja"

    Args:
        lang: Language code (e.g., "en", "jp", "ja", "ja_JP", None)

    Returns:
        Internal canonical code: "en" or "jp"

    Examples:
        >>> normalize_lang_code("ja")
        'jp'
        >>> normalize_lang_code("ja_JP")
        'jp'
        >>> normalize_lang_code("ja-JP")
        'jp'
        >>> normalize_lang_code("jp")
        'jp'
        >>> normalize_lang_code("JP")
        'jp'
        >>> normalize_lang_code(" jp ")
        'jp'
        >>> normalize_lang_code("en")
        'en'
        >>> normalize_lang_code("en_US")
        'en'
        >>> normalize_lang_code(None)
        'en'
        >>> normalize_lang_code("")
        'en'
        >>> normalize_lang_code("fr")
        'en'
    """
    if not lang:
        return "en"

    # Normalize: strip whitespace, lowercase
    normalized = lang.strip().lower()
    if not normalized:
        return "en"

    # Reduce region variants: take base before "_" or "-"
    # e.g., "ja_JP" -> "ja", "ja-JP" -> "ja", "en_US" -> "en"
    for sep in ("_", "-"):
        if sep in normalized:
            normalized = normalized.split(sep)[0]
            break

    return _TO_INTERNAL.get(normalized, "en")


def to_iso_lang_code(lang: str | None) -> IsoLangCode:
    """Convert to ISO 639-1 language code.

    Use ONLY at boundaries where ISO codes are required
    (e.g., meaning tags registry, lexicon lookups).

    Args:
        lang: Language code (internal or external)

    Returns:
        ISO 639-1 code: "en" or "ja"

    Examples:
        >>> to_iso_lang_code("jp")
        'ja'
        >>> to_iso_lang_code("ja")
        'ja'
        >>> to_iso_lang_code("ja_JP")
        'ja'
        >>> to_iso_lang_code("en")
        'en'
        >>> to_iso_lang_code("en_US")
        'en'
        >>> to_iso_lang_code(None)
        'en'
    """
    internal = normalize_lang_code(lang)
    return _TO_ISO.get(internal, "en")
