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


TOP_MOVE_OPTIONS = [
    TOP_MOVE_SCORE,
    TOP_MOVE_DELTA_SCORE,
    TOP_MOVE_WINRATE,
    TOP_MOVE_DELTA_WINRATE,
    TOP_MOVE_VISITS,
    TOP_MOVE_NOTHING,
]

REPORT_DT = 1
PONDERING_REPORT_DT = 0.25

SGF_INTERNAL_COMMENTS_MARKER = "\u3164\u200b"
SGF_SEPARATOR_MARKER = "\u3164\u3164"


# Kifunarabe (棋譜並べ) display option constants were moved to
# katrain.core.study.kifunarabe_constants in Phase 202.


# --- Analysis Modes ---
import logging

from katrain.core.compatibility import StrEnum

_logger = logging.getLogger(__name__)


class AnalysisMode(StrEnum):
    """Analysis mode for analyze_extra().

    Note: "toggle" is NOT included here - it is an action token
    used only by set_insert_mode(), not by analyze_extra().
    """

    STOP = "stop"
    PONDER = "ponder"
    EXTRA = "extra"
    GAME = "game"
    SWEEP = "sweep"
    EQUALIZE = "equalize"
    ALTERNATIVE = "alternative"
    LOCAL = "local"

    def __str__(self) -> str:
        return self.value


def parse_analysis_mode(
    value: str | AnalysisMode,
    fallback: AnalysisMode = AnalysisMode.STOP,
) -> AnalysisMode:
    """Normalize a string or Enum to AnalysisMode.

    Args:
        value: Mode value ("stop", " PONDER ", AnalysisMode.STOP, etc.)
        fallback: Fallback value when parsing fails

    Returns:
        AnalysisMode (returns fallback and logs WARNING for unknown values)

    Usage:
        - game.py: Entry point of analyze_extra()
        - __main__.py: Entry point of _do_analyze_extra()
    """
    if isinstance(value, AnalysisMode):
        return value
    try:
        # Normalize: strip whitespace, lowercase
        normalized = value.strip().lower()
        return AnalysisMode(normalized)
    except (ValueError, AttributeError):
        _logger.warning(f"Unknown analysis mode: {value!r}, falling back to {fallback}")
        return fallback
