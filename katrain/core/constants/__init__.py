"""Constants package.

Phase PR1: Split from the monolithic ``katrain/core/constants.py`` into
4 cohesive sub-modules so changes have a narrower blast radius:

    katrain.core.constants.output       OUTPUT_*, STATUS_*, KATAGO_EXCEPTION
    katrain.core.constants.modes        MODE_*, PLAYER_*, PLAYING_*, GAME_TYPES
    katrain.core.constants.priorities   PRIORITY_*, ADDITIONAL_MOVE_ORDER
    katrain.core.constants.metadata     PROGRAM_NAME, VERSION, paths, timings

Backward compatibility:
    This package re-exports every symbol from the original
    ``katrain.core.constants`` module, so existing
    ``from katrain.core.constants import X`` imports keep working
    unchanged.

New code should prefer the granular sub-modules to make dependencies
explicit (e.g. ``from katrain.core.constants.output import OUTPUT_DEBUG``).
"""

from __future__ import annotations

from katrain.core.constants.metadata import (
    ANALYSIS_FORMAT_VERSION,
    CONFIG_MIN_VERSION,
    DATA_FOLDER,
    DEFAULT_CRITICAL_3_MAX_MOVES,
    HOMEPAGE,
    PONDERING_REPORT_DT,
    PROGRAM_NAME,
    REPORT_DT,
    SGF_INTERNAL_COMMENTS_MARKER,
    SGF_SEPARATOR_MARKER,
    TOP_MOVE_DELTA_SCORE,
    TOP_MOVE_DELTA_WINRATE,
    TOP_MOVE_NOTHING,
    TOP_MOVE_OPTIONS,
    TOP_MOVE_OWNERSHIP,
    TOP_MOVE_POLICY,
    TOP_MOVE_SCORE,
    TOP_MOVE_SCORE_STDEV,
    TOP_MOVE_VISITS,
    TOP_MOVE_WINRATE,
    VERSION,
)
from katrain.core.constants.modes import (
    GAME_TYPES,
    MODE_ANALYZE,
    MODE_PLAY,
    PLAYER_AI,
    PLAYER_HUMAN,
    PLAYER_TYPES,
    PLAYING_NORMAL,
    PLAYING_TEACHING,
)
from katrain.core.constants.output import (
    KATAGO_EXCEPTION,
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    OUTPUT_EXTRA_DEBUG,
    OUTPUT_INFO,
    OUTPUT_KATAGO_STDERR,
    STATUS_ANALYSIS,
    STATUS_ERROR,
    STATUS_INFO,
    STATUS_TEACHING,
)
from katrain.core.constants.priorities import (
    ADDITIONAL_MOVE_ORDER,
    PRIORITY_ALTERNATIVES,
    PRIORITY_DEFAULT,
    PRIORITY_EQUALIZE,
    PRIORITY_EXTRA_AI_QUERY,
    PRIORITY_EXTRA_ANALYSIS,
    PRIORITY_GAME_ANALYSIS,
    PRIORITY_SWEEP,
)

__all__ = [
    # metadata
    "ANALYSIS_FORMAT_VERSION",
    "CONFIG_MIN_VERSION",
    "DATA_FOLDER",
    "DEFAULT_CRITICAL_3_MAX_MOVES",
    "HOMEPAGE",
    "PONDERING_REPORT_DT",
    "PROGRAM_NAME",
    "REPORT_DT",
    "SGF_INTERNAL_COMMENTS_MARKER",
    "SGF_SEPARATOR_MARKER",
    "TOP_MOVE_DELTA_SCORE",
    "TOP_MOVE_DELTA_WINRATE",
    "TOP_MOVE_NOTHING",
    "TOP_MOVE_OPTIONS",
    "TOP_MOVE_OWNERSHIP",
    "TOP_MOVE_POLICY",
    "TOP_MOVE_SCORE",
    "TOP_MOVE_SCORE_STDEV",
    "TOP_MOVE_VISITS",
    "TOP_MOVE_WINRATE",
    "VERSION",
    # modes
    "GAME_TYPES",
    "MODE_ANALYZE",
    "MODE_PLAY",
    "PLAYER_AI",
    "PLAYER_HUMAN",
    "PLAYER_TYPES",
    "PLAYING_NORMAL",
    "PLAYING_TEACHING",
    # output
    "KATAGO_EXCEPTION",
    "OUTPUT_DEBUG",
    "OUTPUT_ERROR",
    "OUTPUT_EXTRA_DEBUG",
    "OUTPUT_INFO",
    "OUTPUT_KATAGO_STDERR",
    "STATUS_ANALYSIS",
    "STATUS_ERROR",
    "STATUS_INFO",
    "STATUS_TEACHING",
    # priorities
    "ADDITIONAL_MOVE_ORDER",
    "PRIORITY_ALTERNATIVES",
    "PRIORITY_DEFAULT",
    "PRIORITY_EQUALIZE",
    "PRIORITY_EXTRA_AI_QUERY",
    "PRIORITY_EXTRA_ANALYSIS",
    "PRIORITY_GAME_ANALYSIS",
    "PRIORITY_SWEEP",
]
