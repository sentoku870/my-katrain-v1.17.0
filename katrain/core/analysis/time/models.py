# -*- coding: utf-8 -*-
"""Time Data Models.

This module defines the core data structures for SGF time parsing:
- TimeMetrics: Per-move time information
- GameTimeData: Aggregated game time data

Part of Phase 58: Time Data Parser.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeMetrics:
    """Per-move time metrics extracted from SGF time tags.

    This is an immutable dataclass representing time information for a single move.

    Attributes:
        move_number: 1-indexed move number (mainline moves only, not node index).
                    Increments only for actual B/W moves.
        player: 'B' or 'W' (the player who made this move)
        time_left_sec: Time remaining AFTER this move (from BL/WL tag).
                      None if tag is missing, invalid, or negative.
        time_spent_sec: Time consumed for this move (prev_left - current_left).
                       None if:
                       - This is the player's first move (no previous baseline)
                       - Current or previous time tag is missing/invalid
                       - Delta is negative (byoyomi reset, exceeds EPS tolerance)

    Note:
        - BL/WL represents time-left AFTER the move is played (SGF standard)
        - This dataclass is frozen (immutable) for thread-safety
    """

    move_number: int
    player: str  # 'B' or 'W'
    time_left_sec: float | None
    time_spent_sec: float | None


@dataclass(frozen=True)
class GameTimeData:
    """Aggregated time data for an entire game.

    Always returned by parse_time_data() (never None). Check has_time_data
    to determine if meaningful time data exists.

    Attributes:
        metrics: Tuple of TimeMetrics for all mainline moves.
                - Empty tuple if no valid BL/WL tags found (has_time_data=False)
                - Contains ALL mainline moves if data exists (has_time_data=True),
                  preserving move_number alignment. Moves with missing tags
                  have time_left_sec=None.
        has_time_data: True if any valid BL/WL tags were found in the game.
        black_moves_with_time: Count of black moves with valid time_left_sec.
        white_moves_with_time: Count of white moves with valid time_left_sec.

    Note:
        - metrics is a tuple (immutable) for thread-safety
        - When has_time_data=False, metrics is guaranteed to be empty tuple
        - When has_time_data=True, metrics preserves move_number alignment
    """

    metrics: tuple[TimeMetrics, ...]
    has_time_data: bool
    black_moves_with_time: int
    white_moves_with_time: int
