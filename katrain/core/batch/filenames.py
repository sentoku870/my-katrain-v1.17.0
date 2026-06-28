"""Filename sanitization, normalization, and uniqueness helpers."""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata

# Windows reserved filenames
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """Sanitize player name for use in filename.

    Handles:
        - Invalid characters (<>:"/\\|?*)
        - Whitespace normalization
        - Windows reserved names (CON, PRN, NUL, etc.)
        - Empty result fallback
        - Length truncation

    Args:
        name: Original player name
        max_length: Maximum filename length (default 50)

    Returns:
        Safe filename string
    """
    if not name:
        return "unknown"

    # Remove/replace invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', "_", name)
    # Normalize whitespace (including full-width spaces)
    safe = re.sub(r"\s+", "_", safe)
    # Remove leading/trailing dots and underscores
    safe = safe.strip("._")

    # Check for Windows reserved names (case-insensitive)
    if safe.upper() in _WINDOWS_RESERVED:
        safe = f"_{safe}_"

    # Truncate to max length
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip("_")

    # Strip trailing dots and spaces again after truncation (Windows requirement)
    safe = safe.rstrip(". ")

    # Final fallback if empty
    if not safe:
        return "unknown"

    return safe


# Alias for backward compatibility with private name
_sanitize_filename = sanitize_filename


def get_unique_filename(base_path: str, extension: str = ".md") -> str:
    """Generate unique filename by adding suffix if collision exists.

    Args:
        base_path: Full path without extension
        extension: File extension including dot

    Returns:
        Unique file path
    """
    path = base_path + extension
    if not os.path.exists(path):
        return path

    counter = 1
    while True:
        path = f"{base_path}_{counter}{extension}"
        if not os.path.exists(path):
            return path
        counter += 1
        if counter > 100:  # Safety limit
            hash_suffix = hashlib.md5(base_path.encode()).hexdigest()[:6]
            return f"{base_path}_{hash_suffix}{extension}"


# Alias for backward compatibility with private name
_get_unique_filename = get_unique_filename


def normalize_player_name(name: str) -> str:
    """Normalize player name for grouping.

    Uses NFKC normalization and collapses whitespace.
    This is the single source of truth for name normalization.

    Args:
        name: Original player name

    Returns:
        Normalized player name
    """
    name = name.strip()
    name = unicodedata.normalize("NFKC", name)
    # Collapse multiple spaces
    name = " ".join(name.split())
    return name


# Alias for backward compatibility with private name
_normalize_player_name = normalize_player_name
