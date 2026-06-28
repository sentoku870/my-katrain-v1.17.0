"""User input parsing helpers (timeout, integer)."""

from __future__ import annotations

from collections.abc import Callable

# Default timeout in seconds when no timeout is specified
DEFAULT_TIMEOUT_SECONDS: float = 600.0


def parse_timeout_input(
    text: str,
    default: float = DEFAULT_TIMEOUT_SECONDS,
    log_cb: Callable[[str], None] | None = None,
) -> float | None:
    """Parse timeout input text from UI into a float or None.

    Args:
        text: Raw text from the timeout input field
        default: Default value when input is empty (default: 600.0)
        log_cb: Optional callback for logging warnings

    Returns:
        - None if text is "none" (case-insensitive, stripped)
        - default if text is empty
        - Parsed float value if valid number
        - default if parsing fails (with warning logged)

    Examples:
        >>> parse_timeout_input("")
        600.0
        >>> parse_timeout_input("None")
        None
        >>> parse_timeout_input("  NONE  ")
        None
        >>> parse_timeout_input("300")
        300.0
        >>> parse_timeout_input("abc")  # Returns default with warning
        600.0
    """
    stripped = text.strip()

    # Empty string -> default
    if not stripped:
        return default

    # "None" (case-insensitive) -> no timeout
    if stripped.lower() == "none":
        return None

    # Try to parse as float
    try:
        return float(stripped)
    except ValueError:
        if log_cb:
            log_cb(f"[WARNING] Invalid timeout value '{text}', using default {default}s")
        return default


def safe_int(text: str, default: int | None = None) -> int | None:
    """Parse integer safely, returning default on invalid input.

    Note: Does not log warnings to avoid noise from frequent UI validation.

    Args:
        text: Text to parse
        default: Value to return if parsing fails

    Returns:
        Parsed integer or default value
    """
    text = text.strip() if text else ""
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


# Alias for backward compatibility with private name
_safe_int = safe_int
