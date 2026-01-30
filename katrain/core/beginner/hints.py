"""Phase 91: Beginner Hint Computation

Main entry points for computing beginner hints.
"""

from typing import Any, Optional

from katrain.core.beginner.detector import (
    detect_cut_risk,
    detect_ignore_atari,
    detect_missed_capture,
    detect_self_atari,
)
from katrain.core.beginner.models import BeginnerHint, DetectorInput
from katrain.core.board_analysis import extract_groups_from_game

# Sentinel value for cache (distinguishes None from "not computed")
_NOT_COMPUTED = object()


def compute_beginner_hint(game: Any, node: Any) -> Optional[BeginnerHint]:
    """Compute a beginner hint for a specific node

    Node state transitions:
    1. Save original_node
    2. Move to node -> get groups_after, was_capture
    3. Move to node.parent -> get groups_before
    4. Move back to node <- Required for CUT_RISK
    5. Run detectors
    6. Restore original_node

    Args:
        game: Game instance
        node: GameNode to evaluate

    Returns:
        BeginnerHint if a warning applies, None otherwise
    """
    if node.move is None or node.parent is None:
        return None

    move = node.move
    if move.is_pass:
        return None

    original_node = game.current_node

    try:
        # Step 1: Move to node (after state)
        if game.current_node != node:
            game.set_current_node(node)

        # Step 2: Get after-state information
        # Note: last_capture is always initialized as [] (game.py:152)
        # but we use defensive `or []` for safety
        captured = game.last_capture or []
        was_capture = bool(captured)
        captured_count = len(captured)
        groups_after = extract_groups_from_game(game)

        # Step 3: Move to parent (before state)
        game.set_current_node(node.parent)
        groups_before = extract_groups_from_game(game)

        # Step 4: Move back to node (after state) <- Required for CUT_RISK
        game.set_current_node(node)

        # Step 5: Create DetectorInput
        inp = DetectorInput(
            node=node,
            parent=node.parent,
            move_coords=move.coords,
            player=move.player,  # "B" or "W"
            groups_after=groups_after,
            groups_before=groups_before,
            was_capture=was_capture,
            captured_count=captured_count,
        )

        # Step 6: Run detectors in priority order
        # Note: At this point game.current_node == node

        hint = detect_self_atari(inp)
        if hint:
            return hint

        hint = detect_ignore_atari(inp)
        if hint:
            return hint

        hint = detect_missed_capture(inp)
        if hint:
            return hint

        hint = detect_cut_risk(inp, game)  # Needs game for find_connect_points
        return hint

    finally:
        # Step 7: Restore original state
        if game.current_node != original_node:
            game.set_current_node(original_node)


def get_beginner_hint_cached(game: Any, node: Any) -> Optional[BeginnerHint]:
    """Get beginner hint with node-level caching

    Caches the result on the node to avoid recomputation.
    Uses a sentinel value to distinguish None (no hint) from
    "not yet computed".

    Args:
        game: Game instance
        node: GameNode to evaluate

    Returns:
        BeginnerHint if a warning applies, None otherwise
    """
    cache_attr = "_beginner_hint_cache"

    cached = getattr(node, cache_attr, _NOT_COMPUTED)
    if cached is not _NOT_COMPUTED:
        return cached  # None is a valid cached value

    hint = compute_beginner_hint(game, node)
    setattr(node, cache_attr, hint)
    return hint
