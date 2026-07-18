PROGRAM_NAME = "KaTrain"
VERSION = "1.17.1"
HOMEPAGE = "https://github.com/sanderland/katrain"
CONFIG_MIN_VERSION = "1.17.0"  # keep config files from this version
ANALYSIS_FORMAT_VERSION = "1.0"
DATA_FOLDER = "~/.katrain"


OUTPUT_ERROR = -1
OUTPUT_KATAGO_STDERR = -0.5
OUTPUT_INFO = 0
OUTPUT_DEBUG = 1
OUTPUT_EXTRA_DEBUG = 2

KATAGO_EXCEPTION = "KATAGO-INTERNAL-ERROR"

STATUS_ANALYSIS = 1.0  # same priority for analysis/info
STATUS_INFO = 1.1
STATUS_TEACHING = 2.0
STATUS_ERROR = 1000.0

ADDITIONAL_MOVE_ORDER = 999

PRIORITY_GAME_ANALYSIS = -100
PRIORITY_SWEEP = -10  # sweep is live, but slow, so deprioritize
PRIORITY_ALTERNATIVES = 100  # extra analysis, live interaction
PRIORITY_EQUALIZE = 100
PRIORITY_EXTRA_ANALYSIS = 100
PRIORITY_DEFAULT = 1000  # new move, high pri
PRIORITY_EXTRA_AI_QUERY = 10_000

PLAYER_HUMAN, PLAYER_AI = "player:human", "player:ai"
PLAYER_TYPES = [PLAYER_HUMAN, PLAYER_AI]

PLAYING_NORMAL, PLAYING_TEACHING = "game:normal", "game:teach"
GAME_TYPES = [PLAYING_NORMAL, PLAYING_TEACHING]

MODE_PLAY, MODE_ANALYZE = "play", "analyze"

# AI strategy constants moved to katrain.core.ai.constants (Phase 203).


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

REPORT_DT = 1
PONDERING_REPORT_DT = 0.25

# Phase 248-γ-D1: default count for the important-moves popup.
# Mirrors the Phase 50 critical_3 baseline. The user-configurable
# ``mykatrain_settings.critical_3_max_moves`` (Phase 248-B2) overrides
# this when set.
DEFAULT_CRITICAL_3_MAX_MOVES = 3

SGF_INTERNAL_COMMENTS_MARKER = "\u3164\u200b"
SGF_SEPARATOR_MARKER = "\u3164\u3164"


# Kifunarabe (棋譜並べ) display option constants were moved to
# katrain.core.study.kifunarabe_constants in Phase 202.


# --- Analysis Modes ---

# AnalysisMode and parse_analysis_mode moved to katrain.core.analysis.modes (Phase 204).
