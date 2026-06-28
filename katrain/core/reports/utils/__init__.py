"""Reports utilities (Phase 154-A).

Currently exposes:
- :mod:`katrain.core.reports.utils.result_parser`: SGF ``RE`` parsing.
- :mod:`katrain.core.reports.utils.game_classifier`: even / handicapped split.
"""

from katrain.core.reports.utils.game_classifier import (
    EVEN_KOMI_FLOOR,
    GameType,
    classify_game,
    classify_games,
)
from katrain.core.reports.utils.result_parser import (
    GameOutcome,
    PlayerOutcome,
    outcome_for_player,
    parse_result,
)

__all__ = [
    "EVEN_KOMI_FLOOR",
    "GameOutcome",
    "GameType",
    "PlayerOutcome",
    "classify_game",
    "classify_games",
    "outcome_for_player",
    "parse_result",
]
