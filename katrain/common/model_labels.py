"""Model strength classification for KataGo models.

Returns i18n keys only - no user-facing strings in this module.
"""

import ntpath
import posixpath
import re
from typing import Literal

StrengthCategory = Literal["light", "standard", "strong", "unknown"]

_STRENGTH_PATTERNS: list[tuple[str, StrengthCategory]] = [
    (r"b10c128", "light"),
    (r"b18c384", "standard"),
    (r"b28|b40", "strong"),
]


def _cross_platform_basename(path: str) -> str:
    """Extract basename from path, handling both Windows and Unix separators.

    os.path.basename("C:\\models\\file.bin") returns the full string on Linux
    because Linux doesn't recognize backslash as separator.

    This function handles:
    - Windows paths on any OS (backslash)
    - Unix paths on any OS (forward slash)
    - Mixed paths (uses rightmost separator)
    """
    if not path:
        return ""
    # If path contains backslash, use ntpath (Windows rules)
    if "\\" in path:
        return ntpath.basename(path)
    # Otherwise use posixpath (works for forward slash on all platforms)
    return posixpath.basename(path)


def classify_model_strength(model_path: str) -> StrengthCategory:
    """Classify model by strength based on filename pattern."""
    if not model_path:
        return "unknown"
    basename = _cross_platform_basename(model_path)
    for pattern, category in _STRENGTH_PATTERNS:
        if re.search(pattern, basename, re.IGNORECASE):
            return category
    return "unknown"


def get_model_i18n_key(model_path: str) -> str:
    """Get i18n key for model label."""
    category = classify_model_strength(model_path)
    return f"model:{category}"


def get_model_basename(model_path: str) -> str:
    """Get basename for display when model is unknown.

    Returns empty string if path is empty (caller should handle).
    """
    return _cross_platform_basename(model_path)
