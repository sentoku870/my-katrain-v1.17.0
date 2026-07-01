"""Phase classification and game phase functions.

Phase 144-C: Extracted from logic.py (1494 lines → 6 focused modules).

Contains:
- get_phase_thresholds: Get phase boundaries for a given board size
- classify_game_phase: Classify a move number into opening/middle/yose
"""
from __future__ import annotations

# =============================================================================
# Phase thresholds
# =============================================================================


def get_phase_thresholds(board_size: int = 19) -> tuple[int, int]:
    """
    Get phase classification thresholds for a given board size.

    Args:
        board_size: Board size (9, 13, 19, etc.)

    Returns:
        Tuple of (opening_end, middle_end) move numbers.
    """
    thresholds = {
        9: (15, 50),
        13: (30, 100),
        19: (50, 200),
    }
    return thresholds.get(board_size, (50, 200))


def classify_game_phase(move_number: int, board_size: int = 19) -> str:
    """
    手数と盤サイズから対局のフェーズを判定する

    Args:
        move_number: 手数
        board_size: 盤サイズ（9, 13, 19 など）

    Returns:
        "opening" / "middle" / "yose"

    Note:
        Boundaries are inclusive for the first phase:
        - opening: move_number <= opening_end (e.g., <= 50 for 19x19)
        - middle: opening_end < move_number <= middle_end
        - yose: move_number > middle_end
    """
    thresholds = {
        9: (15, 50),
        13: (30, 100),
        19: (50, 200),
    }
    opening_end, middle_end = thresholds.get(board_size, (50, 200))

    if move_number <= opening_end:  # Changed from < to <=
        return "opening"
    elif move_number <= middle_end:  # Changed from < to <= for consistency
        return "middle"
    else:
        return "yose"
