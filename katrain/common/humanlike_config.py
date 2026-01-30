"""Human-like config normalization logic.

Pure functions with no Kivy dependencies for CI-safe testing.
"""


def normalize_humanlike_config(
    toggle_on: bool,
    current_path: str,
    last_path: str,
) -> tuple[str, str, bool]:
    """Normalize humanlike config for saving.

    Args:
        toggle_on: Whether human-like toggle is ON
        current_path: Current humanlike_model value
        last_path: Previous humanlike_model_last value

    Returns:
        (humanlike_model, humanlike_model_last, effective_toggle_on) tuple

    Rules (Option A: Force OFF when path empty):
        - toggle ON + path valid: (path, path, True)
        - toggle ON + path empty: ("", last_path, False) <- force OFF
        - toggle OFF + path valid: ("", path, False) <- save path to last
        - toggle OFF + path empty: ("", last_path, False)
    """
    if toggle_on:
        if current_path:
            return (current_path, current_path, True)
        else:
            # ON but empty path -> force OFF
            return ("", last_path, False)
    else:
        # OFF: clear model, preserve last
        new_last = current_path if current_path else last_path
        return ("", new_last, False)
