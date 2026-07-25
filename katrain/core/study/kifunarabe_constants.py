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

# Phase 290: candidate pool mode for the choice-set builder.
#: ``"top_kata"`` keeps the legacy behaviour (KataGo best-to-decreasing).
#: ``"near_actual"`` picks candidates within ``near_threshold_points`` of
#: the actual move's ``pointsLost``, so the puzzle presents alternative
#: hands of comparable evaluation rather than the obvious-best moves.
KIFUNARABE_CANDIDATE_POOL_KEY = "kifunarabe/candidate_pool"
KIFUNARABE_CANDIDATE_POOL_TOP_KATA = "top_kata"
KIFUNARABE_CANDIDATE_POOL_NEAR_ACTUAL = "near_actual"
KIFUNARABE_CANDIDATE_POOL_DEFAULT = KIFUNARABE_CANDIDATE_POOL_NEAR_ACTUAL
#: Allowed values for :data:`KIFUNARABE_CANDIDATE_POOL_KEY`. Treated as a
#: tuple (rather than ``Literal``) so the kivy-free core layer can iterate.
VALID_CANDIDATE_POOLS: tuple[str, ...] = (
    KIFUNARABE_CANDIDATE_POOL_TOP_KATA,
    KIFUNARABE_CANDIDATE_POOL_NEAR_ACTUAL,
)

# Phase 290: tolerance (in points) for the ``near_actual`` pool mode.
#: Default 2.0 points: roughly the "small mistake" boundary in myKatrain's
#: own Phase-3 mistake table. Users who want a harder puzzle can lower
#: this toward 0.5; users who want KataGo-best bias can raise it toward 8.0.
KIFUNARABE_NEAR_THRESHOLD_KEY = "kifunarabe/near_threshold"
KIFUNARABE_NEAR_THRESHOLD_DEFAULT = 2.0
KIFUNARABE_NEAR_THRESHOLD_MIN = 0.0
KIFUNARABE_NEAR_THRESHOLD_MAX = 20.0

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
    "KIFUNARABE_CANDIDATE_POOL_KEY",
    "KIFUNARABE_CANDIDATE_POOL_TOP_KATA",
    "KIFUNARABE_CANDIDATE_POOL_NEAR_ACTUAL",
    "KIFUNARABE_CANDIDATE_POOL_DEFAULT",
    "VALID_CANDIDATE_POOLS",
    "KIFUNARABE_NEAR_THRESHOLD_KEY",
    "KIFUNARABE_NEAR_THRESHOLD_DEFAULT",
    "KIFUNARABE_NEAR_THRESHOLD_MIN",
    "KIFUNARABE_NEAR_THRESHOLD_MAX",
]
