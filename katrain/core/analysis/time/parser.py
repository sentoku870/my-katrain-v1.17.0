"""Time Data Parser.

This module provides functionality to parse BL/WL time tags from SGF files
and compute per-move time consumption.

Part of Phase 58: Time Data Parser.
"""

import logging

from katrain.core.sgf_parser import SGFNode

from .models import GameTimeData, TimeMetrics

_logger = logging.getLogger(__name__)

# Floating point tolerance for delta calculation (KGS decimal values)
# Tiny negative deltas within this range are treated as 0.0
_EPS = 0.001


def _extract_time_left(node: SGFNode, player: str) -> float | None:
    """Extract time left from node's BL or WL property.

    Args:
        node: SGFNode to extract time from
        player: 'B' (reads BL) or 'W' (reads WL)

    Returns:
        Time left in seconds as float, or None if:
        - Property doesn't exist or is empty
        - Property value is empty/whitespace
        - Property value cannot be parsed as a number
        - Property value is negative

    Implementation notes:
        - Handles IndexError from empty property lists (malformed SGF)
        - Black moves read BL, White moves read WL (never reversed)
        - Handles both int ("45") and float ("123.456") formats
        - Strips whitespace before parsing
    """
    prop = "BL" if player == "B" else "WL"

    # Guard against IndexError from empty property lists
    try:
        value = node.get_property(prop)  # Returns str or None (default)
    except (IndexError, KeyError):
        _logger.warning("Malformed %s property (empty list), treating as None", prop)
        return None

    if value is None:
        return None

    # value is str at this point (from get_property implementation)
    value_str = str(value).strip()  # Defensive: ensure str, strip whitespace
    if not value_str:
        return None

    try:
        result = float(value_str)
        if result < 0:
            _logger.warning("Negative time value %s='%s', treating as None", prop, value)
            return None
        return result
    except (ValueError, TypeError):
        _logger.warning("Invalid %s value '%s', treating as None", prop, value)
        return None


def parse_time_data(root: SGFNode) -> GameTimeData:
    """Parse time data from SGF game tree (mainline only).

    Traverses the mainline (first child of each node) and extracts
    BL/WL time tags for each move. Starts from root's children
    (root node typically contains game properties, not moves).

    Args:
        root: Root SGFNode of the game

    Returns:
        GameTimeData (never None).
        - If no valid BL/WL tags found: has_time_data=False, metrics=()
        - If time data exists: has_time_data=True, metrics contains ALL
          mainline moves (preserving move_number alignment)

    Example:
        >>> from katrain.core.game import KaTrainSGF
        >>> root = KaTrainSGF.parse_sgf("(;GM[1]SZ[19];B[aa]BL[100];W[bb]WL[95])")
        >>> td = parse_time_data(root)
        >>> td.has_time_data
        True
    """
    temp_metrics: list[TimeMetrics] = []
    prev_time: dict[str, float | None] = {"B": None, "W": None}

    move_number = 0
    node = root

    # Traverse mainline only (first child), starting from root's children
    while node.children:
        node = node.children[0]

        # Check if this node has a move
        move = node.move
        if not move or move.player not in ("B", "W"):
            continue  # Skip non-move nodes (comments, setup, etc.)

        # Only increment move_number for actual moves
        move_number += 1
        player = move.player

        time_left = _extract_time_left(node, player)

        # Compute time_spent (only if both current and previous are valid)
        time_spent: float | None = None
        prev = prev_time[player]  # Safe: prev_time always has "B" and "W" keys
        if time_left is not None and prev is not None:
            delta = prev - time_left
            if delta >= -_EPS:
                # Treat tiny negative deltas as 0 (floating point tolerance)
                time_spent = max(0.0, delta)
            else:
                # Byoyomi reset or increment - treat as unknown
                _logger.warning(
                    "Move %d (%s): time increased (%.3f -> %.3f), treating time_spent as unknown",
                    move_number,
                    player,
                    prev,
                    time_left,
                )
                # time_spent remains None

        temp_metrics.append(
            TimeMetrics(
                move_number=move_number,
                player=player,
                time_left_sec=time_left,
                time_spent_sec=time_spent,
            )
        )

        # CRITICAL: Always update prev_time, even when time_left is None.
        # This prevents computing delta across a gap where a tag was missing.
        # Example: B1=100, B3=None, B5=80 -> B5 time_spent must be None, not 20.
        prev_time[player] = time_left

    # Determine if any valid time data exists
    has_time = any(m.time_left_sec is not None for m in temp_metrics)

    if not has_time:
        # No time data found anywhere - return empty metrics
        return GameTimeData(
            metrics=(),
            has_time_data=False,
            black_moves_with_time=0,
            white_moves_with_time=0,
        )

    # Time data exists - return ALL moves to preserve move_number alignment
    # (moves with missing tags have time_left_sec=None)
    black_count = sum(1 for m in temp_metrics if m.player == "B" and m.time_left_sec is not None)
    white_count = sum(1 for m in temp_metrics if m.player == "W" and m.time_left_sec is not None)

    return GameTimeData(
        metrics=tuple(temp_metrics),
        has_time_data=True,
        black_moves_with_time=black_count,
        white_moves_with_time=white_count,
    )
