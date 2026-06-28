"""Reports utilities (Phase 154-A).

Currently exposes:
- :mod:`katrain.core.reports.utils.result_parser`: SGF ``RE`` parsing.
"""

from katrain.core.reports.utils.result_parser import (
    GameOutcome,
    PlayerOutcome,
    outcome_for_player,
    parse_result,
)

__all__ = [
    "GameOutcome",
    "PlayerOutcome",
    "outcome_for_player",
    "parse_result",
]