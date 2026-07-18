"""Kifunarabe (棋譜並べ) display option constants (Phase 177).

Extracted from katrain/core/constants.py to reduce the central constants
module's coupling. All three show_* defaults are "minimal" so the choice
set looks like a clean multiple-choice puzzle.
"""

KIFUNARABE_SHOW_DIGITS_KEY = "kifunarabe/show_digits"
KIFUNARABE_SHOW_ACTUAL_BORDER_KEY = "kifunarabe/show_actual_border"
KIFUNARABE_UNIFORM_COLOR_KEY = "kifunarabe/uniform_color"
KIFUNARABE_SHOW_DIGITS_DEFAULT = False
KIFUNARABE_SHOW_ACTUAL_BORDER_DEFAULT = False
KIFUNARABE_UNIFORM_COLOR_DEFAULT = True

# Phase 177-H: auto-toggle markers to mask "next moves"/"dots" overlays
# while a kifunarabe session is active.
KIFUNARABE_AUTO_TOGGLE_MARKERS_KEY = "kifunarabe/auto_toggle_markers"
KIFUNARABE_AUTO_TOGGLE_MARKERS_DEFAULT = True

# Phase 249-γ: opt-in auto-export of WRONG_GUESS results to a JSON
# file (Karte 弱点連携の入口). Default OFF.
KIFUNARABE_AUTO_EXPORT_WEAKNESSES_KEY = "kifunarabe/auto_export_weaknesses"
KIFUNARABE_AUTO_EXPORT_WEAKNESSES_DEFAULT = False

# Phase 249-γ: directory used when the user has not configured one.
KIFUNARABE_AUTO_EXPORT_DIR_KEY = "kifunarabe/auto_export_dir"
#: ``~/.katrain/kifunarabe_weaknesses`` — created on demand.
KIFUNARABE_AUTO_EXPORT_DIR_DEFAULT = ""

__all__ = [
    "KIFUNARABE_SHOW_DIGITS_KEY",
    "KIFUNARABE_SHOW_ACTUAL_BORDER_KEY",
    "KIFUNARABE_UNIFORM_COLOR_KEY",
    "KIFUNARABE_SHOW_DIGITS_DEFAULT",
    "KIFUNARABE_SHOW_ACTUAL_BORDER_DEFAULT",
    "KIFUNARABE_UNIFORM_COLOR_DEFAULT",
    "KIFUNARABE_AUTO_TOGGLE_MARKERS_KEY",
    "KIFUNARABE_AUTO_TOGGLE_MARKERS_DEFAULT",
    "KIFUNARABE_AUTO_EXPORT_WEAKNESSES_KEY",
    "KIFUNARABE_AUTO_EXPORT_WEAKNESSES_DEFAULT",
    "KIFUNARABE_AUTO_EXPORT_DIR_KEY",
    "KIFUNARABE_AUTO_EXPORT_DIR_DEFAULT",
]
