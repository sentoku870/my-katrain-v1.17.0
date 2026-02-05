"""Meaning Tags Data Models.

This module defines the core data structures for the Meaning Tags system:
- MeaningTagId: Enum of all meaning tag identifiers
- MeaningTag: Immutable dataclass for classification results

Part of Phase 46: Meaning Tags System Core.
"""

from dataclasses import dataclass
from enum import StrEnum


class MeaningTagId(StrEnum):
    """Meaning tag identifiers.

    Inherits from str for direct JSON serialization (no .value needed).

    All 12 tags represent semantic categories of Go mistakes:
    - Tactical: CAPTURE_RACE_LOSS, LIFE_DEATH_ERROR, CONNECTION_MISS, READING_FAILURE
    - Shape: SHAPE_MISTAKE, SLOW_MOVE
    - Strategic: DIRECTION_ERROR, OVERPLAY, MISSED_TESUJI, TERRITORIAL_LOSS
    - Endgame: ENDGAME_SLIP
    - Fallback: UNCERTAIN
    """

    MISSED_TESUJI = "missed_tesuji"
    OVERPLAY = "overplay"
    SLOW_MOVE = "slow_move"
    DIRECTION_ERROR = "direction_error"
    SHAPE_MISTAKE = "shape_mistake"
    READING_FAILURE = "reading_failure"
    ENDGAME_SLIP = "endgame_slip"
    CONNECTION_MISS = "connection_miss"
    CAPTURE_RACE_LOSS = "capture_race_loss"
    LIFE_DEATH_ERROR = "life_death_error"
    TERRITORIAL_LOSS = "territorial_loss"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class MeaningTag:
    """Classification result for a single move.

    This is an immutable dataclass representing the semantic classification
    of a mistake. It contains:
    - id: The tag identifier (required)
    - lexicon_anchor_id: Optional reference to a Lexicon entry
    - confidence: Reserved for future ML-based classification (always 1.0 now)
    - debug_reason: Explains why this tag was assigned (for debugging/testing)

    Examples:
        >>> tag = MeaningTag(id=MeaningTagId.LIFE_DEATH_ERROR)
        >>> tag.id
        <MeaningTagId.LIFE_DEATH_ERROR: 'life_death_error'>

        >>> tag = MeaningTag(
        ...     id=MeaningTagId.UNCERTAIN,
        ...     debug_reason="pass_move"
        ... )
        >>> tag.debug_reason
        'pass_move'

    Note:
        This dataclass is frozen (immutable) to ensure thread-safety
        and hashability for use in sets/dicts.
    """

    id: MeaningTagId
    lexicon_anchor_id: str | None = None
    confidence: float = 1.0
    debug_reason: str | None = None

    def __post_init__(self) -> None:
        """Validate field values after initialization."""
        if not isinstance(self.id, MeaningTagId):
            raise TypeError(f"id must be MeaningTagId, got {type(self.id).__name__}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
