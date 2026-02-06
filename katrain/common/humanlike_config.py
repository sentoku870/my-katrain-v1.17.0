"""Human-like config normalization logic."""

from __future__ import annotations


def normalize_humanlike_config(
    toggle_on: bool, current_path: str, last_path: str
) -> tuple[str, str, bool]:
    """Normalize human-like configuration state.
    
    Args:
        toggle_on: Whether the human-like toggle is requested ON.
        current_path: The currently selected human-like model path (or empty).
        last_path: The previously used human-like model path.

    Returns:
        tuple: (
            model: The effective model path to use (empty if OFF),
            last: The path to save as 'last used',
            effective_on: Whether the feature is effectively ON.
        )
    """
    if not toggle_on:
        # Off state: clear model, save current to last if present
        new_last = current_path if current_path else last_path
        return "", new_last, False

    if current_path:
        # On state with valid path: use it
        return current_path, current_path, True

    # On state but no path: force off, preserve last
    return "", last_path, False
