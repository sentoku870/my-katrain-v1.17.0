"""Phase 91: Beginner Hint Detectors

Detection functions for beginner safety hints.
Each detector returns a BeginnerHint or None.
"""

from __future__ import annotations

from typing import Any

from katrain.core.beginner.models import BeginnerHint, DetectorInput, HintCategory


def find_matching_group(
    target_stones: set[tuple[int, int]],
    groups: list[Any],
    color: str,
) -> Any | None:
    """Match a group across board states using stone coordinate overlap

    Args:
        target_stones: Set of stone coordinates from the original group
        groups: List of Group objects to search in
        color: Color to match ("B" or "W")

    Returns:
        The best matching Group, or None if no match found

    Matching strategy:
        - Only groups of the same color are considered
        - Overlap >= 50% (based on min of both sizes) to match
        - Returns the group with maximum overlap

    MVP limitations:
        - Merge: Matches if 50%+ of original stones are in new group
        - Split: Matches the split fragment with most overlap
        - Complete disappearance: Returns None (detector skips)
    """
    target_set = set(target_stones)
    best_match = None
    best_overlap = 0

    for g in groups:
        if g.color != color:
            continue
        stones_set = set(g.stones)
        overlap = len(target_set & stones_set)
        min_size = min(len(target_set), len(stones_set))
        if min_size > 0 and overlap >= min_size * 0.5:
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = g

    return best_match


def detect_self_atari(inp: DetectorInput) -> BeginnerHint | None:
    """Detect self-atari: playing into atari on your own group

    Excluded cases:
        - Single stone (intentional sacrifice is common)
        - Favorable recapture (captured >= group_size)

    Args:
        inp: DetectorInput with move and group information

    Returns:
        BeginnerHint with SELF_ATARI category, or None
    """
    if inp.move_coords is None:
        return None

    # Find the group containing the played stone
    my_group = None
    for g in inp.groups_after:
        if g.color == inp.player and inp.move_coords in g.stones:
            my_group = g
            break

    if my_group is None or not my_group.is_in_atari:
        return None

    # Exclude: single stone (common sacrifice)
    if len(my_group.stones) == 1:
        return None

    # Exclude: favorable recapture
    # If captured >= group_size, the trade is at least even
    if inp.was_capture and inp.captured_count >= len(my_group.stones):
        return None

    return BeginnerHint(
        category=HintCategory.SELF_ATARI,
        coords=inp.move_coords,
        severity=3,
        context={"group_size": len(my_group.stones)},
    )


def detect_ignore_atari(inp: DetectorInput) -> BeginnerHint | None:
    """Detect ignoring atari: leaving a friendly group in atari

    MVP scope: Only detects "still in atari" case.
    Captured/disappeared groups are skipped.

    Excluded cases:
        - Small groups (size < 3)

    Args:
        inp: DetectorInput with move and group information

    Returns:
        BeginnerHint with IGNORE_ATARI category, or None
    """
    if inp.parent is None:
        return None

    # Find friendly groups that were in atari before the move (size >= 3)
    atari_groups_before = [
        g
        for g in inp.groups_before
        if g.color == inp.player and g.is_in_atari and len(g.stones) >= 3
    ]

    if not atari_groups_before:
        return None

    for old_group in atari_groups_before:
        old_stones = set(old_group.stones)
        matched = find_matching_group(old_stones, inp.groups_after, inp.player)

        if matched is None:
            # Disappeared/merge failed -> skip
            continue

        if matched.is_in_atari:
            # Still in atari after move - this is the warning
            liberty = next(iter(matched.liberties), None)
            return BeginnerHint(
                category=HintCategory.IGNORE_ATARI,
                coords=liberty,
                severity=3,
                context={"group_size": len(matched.stones)},
            )

    return None


def detect_missed_capture(inp: DetectorInput) -> BeginnerHint | None:
    """Detect missed capture: opponent group in atari was not captured

    Excluded cases:
        - Small groups (size < 2)
        - Already captured same or more stones elsewhere

    Args:
        inp: DetectorInput with move and group information

    Returns:
        BeginnerHint with MISSED_CAPTURE category, or None
    """
    if inp.parent is None:
        return None

    opponent = "W" if inp.player == "B" else "B"

    # Find opponent groups that were in atari (size >= 2)
    capturable = [
        g
        for g in inp.groups_before
        if g.color == opponent and g.is_in_atari and len(g.stones) >= 2
    ]

    if not capturable:
        return None

    # Sort by size (largest first) to prioritize bigger captures
    capturable.sort(key=lambda g: len(g.stones), reverse=True)
    target = capturable[0]

    liberty = next(iter(target.liberties), None)
    if liberty is None:
        return None

    # If moved to a different spot than the capture point
    if liberty != inp.move_coords:
        # Exclude: captured same or more elsewhere
        if inp.was_capture and inp.captured_count >= len(target.stones):
            return None

        return BeginnerHint(
            category=HintCategory.MISSED_CAPTURE,
            coords=liberty,
            severity=2,
            context={"capturable_size": len(target.stones)},
        )

    return None


def detect_cut_risk(inp: DetectorInput, game: Any) -> BeginnerHint | None:
    """Detect cut risk: groups that could be connected but aren't

    Precondition: game.current_node == inp.node (after state)
    find_connect_points() uses game.board, so correct node state is required.

    Uses runtime guard (not assert) since asserts can be disabled with -O.

    Args:
        inp: DetectorInput with move and group information
        game: Game instance (needed for find_connect_points)

    Returns:
        BeginnerHint with CUT_RISK category, or None
    """
    from katrain.core.board_analysis import (
        DANGER_ATARI,
        DANGER_LOW_LIBERTY,
        find_connect_points,
    )

    # Runtime guard: ensure correct node state
    # Note: using explicit guard instead of assert (-O compatibility)
    if game.current_node != inp.node:
        game.set_current_node(inp.node)

    # Build danger scores for groups
    danger_scores: dict[int, float] = {
        g.group_id: float(
            DANGER_ATARI
            if g.is_in_atari
            else (DANGER_LOW_LIBERTY if g.is_low_liberty else 0)
        )
        for g in inp.groups_after
    }

    connect_points = find_connect_points(game, inp.groups_after, danger_scores)

    IMPROVEMENT_THRESHOLD = 15.0
    MIN_TOTAL_SIZE = 6

    # connect_points: List[Tuple[Tuple[int, int], List[int], float]]
    # Format: (coord, group_ids, improvement) - verified at board_analysis.py:225-226
    for coord, group_ids, improvement in connect_points:
        if improvement < IMPROVEMENT_THRESHOLD:
            continue

        # Calculate total size of player's groups that would be connected
        total_size = sum(
            len(g.stones)
            for g in inp.groups_after
            if g.group_id in group_ids and g.color == inp.player
        )

        if total_size < MIN_TOTAL_SIZE:
            continue

        # Don't warn if they played at the connection point
        if coord != inp.move_coords:
            return BeginnerHint(
                category=HintCategory.CUT_RISK,
                coords=coord,
                severity=2,
                context={"improvement": improvement, "total_size": total_size},
            )

    return None
