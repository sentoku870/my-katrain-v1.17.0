"""Phase 91: Beginner Hint Models

Data models for beginner hint detection system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class HintCategory(Enum):
    """Categories of beginner hints (detection priority order)

    Priority detectors (Phase 91): SELF_ATARI, IGNORE_ATARI, MISSED_CAPTURE, CUT_RISK
    MeaningTag fallbacks (Phase 92): LOW_LIBERTIES, SELF_CAPTURE_LIKE, BAD_SHAPE,
                                     HEAVY_GROUP, MISSED_DEFENSE, URGENT_VS_BIG
    """

    # Priority detectors (Phase 91)
    SELF_ATARI = "self_atari"
    IGNORE_ATARI = "ignore_atari"
    MISSED_CAPTURE = "missed_capture"
    CUT_RISK = "cut_risk"

    # MeaningTag fallbacks (Phase 92)
    LOW_LIBERTIES = "low_liberties"
    SELF_CAPTURE_LIKE = "self_capture_like"
    BAD_SHAPE = "bad_shape"
    HEAVY_GROUP = "heavy_group"
    MISSED_DEFENSE = "missed_defense"
    URGENT_VS_BIG = "urgent_vs_big"

    @classmethod
    def from_meaning_tag_id(cls, tag_id: Optional[str]) -> Optional["HintCategory"]:
        """Map MeaningTagId string to HintCategory.

        Returns None for unknown/unsupported IDs (no crash).

        Args:
            tag_id: MeaningTagId value (e.g., "capture_race_loss")

        Returns:
            Corresponding HintCategory or None if unknown
        """
        if tag_id is None:
            return None

        _MAPPING = {
            "capture_race_loss": cls.LOW_LIBERTIES,
            "life_death_error": cls.SELF_CAPTURE_LIKE,
            "shape_mistake": cls.BAD_SHAPE,
            "overplay": cls.HEAVY_GROUP,
            "connection_miss": cls.MISSED_DEFENSE,
            "endgame_slip": cls.URGENT_VS_BIG,
        }
        return _MAPPING.get(tag_id)  # Returns None for unknown


@dataclass(frozen=True)
class BeginnerHint:
    """A single beginner hint for a move

    Attributes:
        category: The type of hint (determines priority)
        coords: Board coordinates to highlight (x, y) or None
        severity: Severity level (higher = more important)
        context: Additional context for display/debugging
    """

    category: HintCategory
    coords: Optional[Tuple[int, int]]
    severity: int
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectorInput:
    """Input data for hint detectors

    Contains all information needed by detection functions,
    gathered from game state at a specific node.

    Attributes:
        node: The GameNode being evaluated (after the move)
        parent: The parent node (before the move)
        move_coords: Coordinates of the move, or None for pass
        player: Player who made the move ("B" or "W")
        groups_after: Group list after the move
        groups_before: Group list before the move
        was_capture: Whether the move captured any stones
        captured_count: Number of stones captured
    """

    node: Any  # GameNode
    parent: Optional[Any]  # Optional[GameNode]
    move_coords: Optional[Tuple[int, int]]
    player: str  # "B" or "W"
    groups_after: List[Any]  # List[Group]
    groups_before: List[Any]  # List[Group]
    was_capture: bool
    captured_count: int
