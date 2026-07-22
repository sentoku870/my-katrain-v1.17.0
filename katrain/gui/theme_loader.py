"""Theme loading utilities (side-effect free for testability).

This module provides theme override loading without Kivy initialization,
making it testable without GUI dependencies.

Phase 287-G additions:

* ``COLOR_*`` semantic tokens are validated against a small whitelist of
  shape / length rules (RGBA list, 0..1 range) so a typo in the user's
  ``~/.katrain/theme*.json`` cannot crash the UI.
* ``ICON_*`` entries from the JSON are mapped to the canonical Material
  Design Icons name. The same map is exposed for icon button resolution
  so menu.kv / board.kv can stay declarative.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from katrain.gui.theme import Theme

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
# Icon mapping (Phase 287-G: 既存 PNG → Material Design Icons)           #
# ---------------------------------------------------------------------- #
#
# The legacy icon names below are looked up by both ``TransparentIconButton``
# and ``MaterialIconButton``. New KV / Python code should use the MDI name
# directly; this table is only consulted when the legacy PNG file is still
# referenced (back-compat for ``~/.katrain/*.json`` overrides).
LEGACY_ICON_TO_MDI: dict[str, str] = {
    "hamburger.png": "menu",
    "New-Game.png": "file-plus-outline",
    "Insert-Move.png": "format-list-numbered",
    "Save-Game.png": "content-save",
    "Save-Game-As.png": "content-save-edit",
    "Load-Game.png": "folder-open",
    "Time-Settings.png": "clock-outline",
    "Teaching-Settings.png": "school-outline",
    "AI-Settings.png": "robot-outline",
    "General-Settings.png": "cog-outline",
    "Extra.png": "plus-circle-outline",
    "Equalize.png": "scale-balance",
    "Sweep.png": "magnify-scan",
    "Alternative.png": "source-branch",
    "local.png": "selection-drag",
    "reset.png": "refresh",
    "Finish.png": "skip-forward",
    "Deeper all.png": "chart-line",
    "analysis.png": "chart-box-outline",
    "play.png": "play",
    "ai.png": "robot-happy-outline",
    "Previous.png": "chevron-left",
    "Previous-5.png": "rewind-10",
    "Previous-End.png": "page-first",
    "Previous-Mistake.png": "arrow-left-circle",
    "Next.png": "chevron-right",
    "Next-5.png": "fast-forward-10",
    "Next-End.png": "page-last",
    "Next-Mistake.png": "arrow-right-circle",
    "Rotate.png": "rotate-right",
    "delete.png": "delete",
    "Branch.png": "source-branch",
    "Collapse.png": "unfold-less-horizontal",
    "Prune.png": "source-branch-remove",
}

# ---------------------------------------------------------------------- #
# Reverse map: MDI name -> legacy PNG file (Phase 287-G rendering fix)   #
# ---------------------------------------------------------------------- #
#
# Kivy Label-based MDI rendering proved unreliable inside MaterialIconButton
# (texture generated but rendering pipeline failed to display it). The
# pragmatic workaround is to keep using the existing PNG asset library
# (already licensed via Flaticon per LICENSE) and look up a PNG file by
# its semantic MDI name. ``MaterialIconButton`` resolves the icon through
# this map and renders via the proven ``Image`` widget path. The icon
# *naming* stays MDI-conventional so future migration to true MDI font
# rendering is purely a rendering-layer change.
#
# PNG paths here live in ``katrain/img/`` (registered with Kivy's resource
# path in ``__main__.py:780``), so the Kivy ``Image`` widget can resolve
# them by basename without an explicit directory prefix.
MDI_TO_PNG_FALLBACK: dict[str, str] = {
    # top-level / nav
    "menu": "hamburger.png",
    "chevron-left": "Previous.png",
    "chevron-right": "Next.png",
    "rewind-10": "Previous-5.png",
    "fast-forward-10": "Next-5.png",
    "page-first": "Previous-End.png",
    "page-last": "Next-End.png",
    "rotate-right": "Rotate.png",
    "arrow-left-circle": "Previous-Mistake.png",
    "arrow-right-circle": "Next-Mistake.png",
    "delete": "delete.png",
    "source-branch": "Branch.png",
    "unfold-less-horizontal": "Collapse.png",
    "source-branch-remove": "Prune.png",
    # menu items
    "file-plus-outline": "New-Game.png",
    "format-list-numbered": "Insert-Move.png",
    "content-save": "Save-Game.png",
    "content-save-edit": "Save-Game-As.png",
    "folder-open": "Load-Game.png",
    "clock-outline": "Time-Settings.png",
    "school-outline": "Teaching-Settings.png",
    "robot-outline": "AI-Settings.png",
    "cog-outline": "General-Settings.png",
    "plus-circle-outline": "Extra.png",
    "plus-box-outline": "Extra.png",
    "scale-balance": "Equalize.png",
    "magnify-scan": "Sweep.png",
    "selection-drag": "local.png",
    "refresh": "reset.png",
    "skip-forward": "Finish.png",
    "chart-line": "Deeper all.png",
    "chart-box-outline": "analysis.png",
    "puzzle-outline": "New-Game.png",
    "play": "play.png",
    "robot-happy-outline": "ai.png",
    "file-export-outline": "Save-Game.png",
    "chat-processing-outline": "Teaching-Settings.png",
}


# ---------------------------------------------------------------------- #
# Theme override loader                                                  #
# ---------------------------------------------------------------------- #
_COLOR_KEYS: frozenset[str] = frozenset(
    key for key in vars(Theme) if key.startswith("COLOR_") or key in {"BACKGROUND_COLOR", "BOX_BACKGROUND_COLOR"}
)


def _validate_color_value(value: Any) -> bool:
    """Return True iff ``value`` looks like an RGBA list with 0..1 range."""
    if not isinstance(value, list) or len(value) != 4:
        return False
    try:
        return all(isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0 for v in value)
    except TypeError:
        return False


def load_theme_overrides(theme_file: str, theme_class: type[Any]) -> None:
    """Load theme overrides from JSON file.

    Args:
        theme_file: Path to theme JSON file.
        theme_class: Theme class to apply overrides to.

    Only known attributes (hasattr check) are applied.
    Unknown keys and load errors are logged as warnings.

    Phase 287-G: ``COLOR_*`` keys are additionally validated for shape and
    range so a malformed entry cannot crash the GUI at startup.
    """
    try:
        with open(theme_file, encoding="utf-8") as f:
            overrides = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        _logger.warning(f"Failed to load theme file {theme_file}: {e}")
        return

    for k, v in overrides.items():
        if not hasattr(theme_class, k):
            _logger.warning(f"Unknown theme key '{k}' in {theme_file}, ignoring")
            continue
        if k in _COLOR_KEYS and not _validate_color_value(v):
            _logger.warning(
                f"Theme key '{k}' in {theme_file} has invalid color value {v!r}; expected list of 4 floats in [0, 1]."
            )
            continue
        setattr(theme_class, k, v)
        _logger.debug(f"Theme override: {k}")
