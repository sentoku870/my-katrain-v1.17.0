"""Phase 91: Beginner Hint System

Safety net for beginners to avoid self-sabotage moves.

Public API:
    - compute_beginner_hint(game, node) -> Optional[BeginnerHint]
    - get_beginner_hint_cached(game, node) -> Optional[BeginnerHint]
    - HintCategory: Enum of hint types
    - BeginnerHint: Hint data class
"""

from katrain.core.beginner.hints import (
    compute_beginner_hint,
    get_beginner_hint_cached,
)
from katrain.core.beginner.models import BeginnerHint, HintCategory

__all__ = [
    "compute_beginner_hint",
    "get_beginner_hint_cached",
    "BeginnerHint",
    "HintCategory",
]
