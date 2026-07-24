"""Metadata, paths, and timing constants.

Phase PR1: Extracted from ``katrain.core.constants`` to limit blast
radius. All symbols are re-exported from the package root for
backward compatibility.

Categories:
    App metadata   PROGRAM_NAME, VERSION, HOMEPAGE, format versions
    File paths     DATA_FOLDER, SGF markers
    Timing         REPORT_DT, PONDERING_REPORT_DT, DEFAULT_CRITICAL_3_MAX_MOVES
    Top-move keys  TOP_MOVE_* display keys (used by gui_utils.top_move_keys)
"""

# --- App metadata ---
PROGRAM_NAME = "KaTrain"
VERSION = "1.17.1"
HOMEPAGE = "https://github.com/sanderland/katrain"
CONFIG_MIN_VERSION = "1.17.0"
ANALYSIS_FORMAT_VERSION = "1.0"

# --- File paths / markers ---
DATA_FOLDER = "~/.katrain"
SGF_INTERNAL_COMMENTS_MARKER = "\u3164\u200b"
SGF_SEPARATOR_MARKER = "\u3164\u3164"

# --- Timing / sizing ---
REPORT_DT = 1
PONDERING_REPORT_DT = 0.25
DEFAULT_CRITICAL_3_MAX_MOVES = 3

# --- Top-move display keys ---
# These keys index into the per-move display dict produced by
# ``katrain.core.gui_utils.top_move_keys``. They are *display* keys,
# not engine output keys.
TOP_MOVE_DELTA_SCORE = "top_move_delta_score"
TOP_MOVE_SCORE = "top_move_score"
TOP_MOVE_DELTA_WINRATE = "top_move_delta_winrate"
TOP_MOVE_WINRATE = "top_move_winrate"
TOP_MOVE_VISITS = "top_move_visits"
TOP_MOVE_NOTHING = "top_move_nothing"
# Phase 259 (I-11): three new optional columns.
# - SCORE_STDEV: KataGo's per-move scoreStdev (how uncertain the engine
#   is about the score if this move is played). High values = chaotic
#   position, low values = quiet continuation.
# - POLICY: KataGo's per-move prior (the policy network's confidence
#   that this is the right move). Useful for spotting "KataGo's first
#   instinct" vs "KataGo's calculated alternative".
# - OWNERSHIP: the position-level predicted territory skew (same for
#   all moves on this node). A quick "is Black winning or White?" check
#   without leaving the candidate-marker overlay.
TOP_MOVE_SCORE_STDEV = "top_move_score_stdev"
TOP_MOVE_POLICY = "top_move_policy"
TOP_MOVE_OWNERSHIP = "top_move_ownership"

TOP_MOVE_OPTIONS = [
    TOP_MOVE_SCORE,
    TOP_MOVE_DELTA_SCORE,
    TOP_MOVE_WINRATE,
    TOP_MOVE_DELTA_WINRATE,
    TOP_MOVE_VISITS,
    TOP_MOVE_SCORE_STDEV,
    TOP_MOVE_POLICY,
    TOP_MOVE_OWNERSHIP,
    TOP_MOVE_NOTHING,
]
