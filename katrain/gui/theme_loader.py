"""Theme loading utilities (side-effect free for testability).

This module provides theme override loading without Kivy initialization,
making it testable without GUI dependencies.
"""

import json
import logging
from typing import Any, Type

_logger = logging.getLogger(__name__)


def load_theme_overrides(theme_file: str, theme_class: Type[Any]) -> None:
    """Load theme overrides from JSON file.

    Args:
        theme_file: Path to theme JSON file.
        theme_class: Theme class to apply overrides to.

    Only known attributes (hasattr check) are applied.
    Unknown keys and load errors are logged as warnings.
    """
    try:
        with open(theme_file, encoding="utf-8") as f:
            overrides = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        _logger.warning(f"Failed to load theme file {theme_file}: {e}")
        return

    for k, v in overrides.items():
        if hasattr(theme_class, k):
            setattr(theme_class, k, v)
            _logger.debug(f"Theme override: {k}")
        else:
            _logger.warning(f"Unknown theme key '{k}' in {theme_file}, ignoring")
