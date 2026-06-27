"""Data models and constants for batch statistics.

This module contains:
- EvidenceMove dataclass
- All i18n constants

No dependencies on other stats submodules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.core.analysis.models import MistakeCategory


# Generic player names to skip
SKIP_PLAYER_NAMES = frozenset({"Black", "White", "黒", "白", "", "?", "Unknown", "不明"})


# =============================================================================
# Evidence Support (Phase 66)
# =============================================================================


@dataclass(frozen=True)
class EvidenceMove:
    """Lightweight evidence holder - avoids synthesizing MoveEval.

    Contains only the fields needed for evidence display.
    Does NOT inherit from or synthesize MoveEval.

    Attributes:
        game_name: Name/path of the game file
        move_number: Move number in the game
        player: "B" or "W"
        gtp: GTP coordinate (e.g., "D4")
        points_lost: Loss in points
        mistake_category: MistakeCategory enum value
    """

    game_name: str
    move_number: int
    player: str
    gtp: str
    points_lost: float
    mistake_category: MistakeCategory
    analysis_errors: list[str] = field(default_factory=list)

