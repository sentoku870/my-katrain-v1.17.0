"""Phase 91-92: Beginner Hint Computation

Main entry points for computing beginner hints.

Phase 91: 4 priority detectors (SELF_ATARI, IGNORE_ATARI, MISSED_CAPTURE, CUT_RISK)
Phase 92: MeaningTag fallback, reliability filter, gating functions
"""

from __future__ import annotations

from typing import Any

from katrain.core.beginner.detector import (
    detect_cut_risk,
    detect_ignore_atari,
    detect_missed_capture,
    detect_self_atari,
)
from katrain.core.beginner.models import BeginnerHint, DetectorInput, HintCategory
from katrain.core.board_analysis import extract_groups_from_game

# Sentinel value for cache (distinguishes None from "not computed")
_NOT_COMPUTED = object()

# Phase 92: Reliability filter constant
MIN_RELIABLE_VISITS = 200

# Phase 92: Detector categories (always reliable, use board state)
_DETECTOR_CATEGORIES = frozenset(
    {
        HintCategory.SELF_ATARI,
        HintCategory.IGNORE_ATARI,
        HintCategory.MISSED_CAPTURE,
        HintCategory.CUT_RISK,
    }
)


# =============================================================================
# Phase 92: Reliability Filter Functions
# =============================================================================


def _get_visits_from_node(node: Any) -> int | None:
    """Get visits from node analysis using public helper.

    Args:
        node: GameNode to check

    Returns:
        Number of visits, or None if analysis unavailable
    """
    from katrain.core.analysis import get_root_visits

    analysis = getattr(node, "analysis", None)
    return get_root_visits(analysis)


def _is_reliable(node: Any) -> bool:
    """Check if node analysis is reliable enough for hints.

    Args:
        node: GameNode to check

    Returns:
        True if visits >= MIN_RELIABLE_VISITS, False otherwise
    """
    visits = _get_visits_from_node(node)
    if visits is None:
        return False
    return visits >= MIN_RELIABLE_VISITS


# =============================================================================
# Phase 92c: Gating Pure Functions (Kivy-independent)
# =============================================================================


def _normalize_board_size(board_size: int | tuple[int, int]) -> tuple[int, int]:
    """Normalize board_size to (width, height) tuple.

    Args:
        board_size: Either int (square board) or (width, height) tuple.

    Returns:
        Tuple of (width, height).
    """
    if isinstance(board_size, int):
        return (board_size, board_size)
    return board_size


def should_show_beginner_hints(enabled: bool, mode: str) -> bool:
    """Check if beginner hints should be shown (pure function).

    Args:
        enabled: beginner_hints/enabled config value
        mode: Current play_analyze_mode

    Returns:
        True if hints should be displayed.
    """
    from katrain.core.constants import MODE_PLAY

    if not enabled:
        return False
    return mode != MODE_PLAY


def should_draw_board_highlight(
    enabled: bool,
    mode: str,
    board_highlight: bool,
) -> bool:
    """Check if board highlight should be drawn (pure function).

    Args:
        enabled: beginner_hints/enabled config value
        mode: Current play_analyze_mode
        board_highlight: beginner_hints/board_highlight config value

    Returns:
        True if highlight should be drawn.
    """
    if not should_show_beginner_hints(enabled, mode):
        return False
    return board_highlight


def is_coords_valid(
    coords: tuple[int, int] | None,
    board_size: int | tuple[int, int],
) -> bool:
    """Check if coords are valid for the given board size (pure function).

    Args:
        coords: (x, y) coordinates or None
        board_size: Board size (int or tuple)

    Returns:
        True if coords are within bounds.
    """
    if coords is None:
        return False
    x, y = coords
    board_size_x, board_size_y = _normalize_board_size(board_size)
    return 0 <= x < board_size_x and 0 <= y < board_size_y


def _get_meaning_tag_hint(node: Any, move_coords: tuple[int, int] | None) -> BeginnerHint | None:
    """Get beginner hint from node's MeaningTag (Phase 92).

    Checks if the node has a meaning_tag_id attribute (typically set by
    batch analysis) and maps it to a beginner hint category.

    MeaningTag-based hints have lower severity (1) than detector hints (2-3).

    Args:
        node: GameNode to check
        move_coords: Coordinates of the move for highlighting

    Returns:
        BeginnerHint if a valid MeaningTag mapping exists, None otherwise
    """
    # Check for meaning_tag_id on the node (may be set by batch analysis)
    tag_id = getattr(node, "meaning_tag_id", None)
    if tag_id is None:
        return None

    # Map to HintCategory (returns None for unknown/unsupported tags)
    category = HintCategory.from_meaning_tag_id(tag_id)
    if category is None:
        return None

    return BeginnerHint(
        category=category,
        coords=move_coords,
        severity=1,  # Lower priority than detectors
        context={"source": "meaning_tag", "tag_id": tag_id},
    )


def compute_beginner_hint(
    game: Any,
    node: Any,
    *,
    require_reliable: bool = True,
) -> BeginnerHint | None:
    """Compute a beginner hint for a specific node (Phase 91-92)

    Node state transitions:
    1. Save original_node
    2. Move to node -> get groups_after, was_capture
    3. Move to node.parent -> get groups_before
    4. Move back to node <- Required for CUT_RISK
    5. Run detectors
    6. MeaningTag fallback (Phase 92)
    7. Apply reliability filter (Phase 92)
    8. Restore original_node

    Args:
        game: Game instance
        node: GameNode to evaluate
        require_reliable: If True, filter non-detector hints when visits < threshold

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
        if hint:
            return hint

        # Phase 92: MeaningTag fallback (lower priority than detectors)
        hint = _get_meaning_tag_hint(node, move.coords)

        # Phase 92: Apply reliability filter for non-detector hints
        if hint and require_reliable:
            # Detector hints use board state (always reliable)
            # MeaningTag hints need analysis reliability check
            if hint.category not in _DETECTOR_CATEGORIES and not _is_reliable(node):
                return None

        return hint

    finally:
        # Step 7: Restore original state
        if game.current_node != original_node:
            game.set_current_node(original_node)


def get_beginner_hint_cached(
    game: Any,
    node: Any,
    *,
    require_reliable: bool = True,
) -> BeginnerHint | None:
    """Get beginner hint with node-level caching (Phase 91-92)

    Caches the result on the node to avoid recomputation.
    Uses a sentinel value to distinguish None (no hint) from
    "not yet computed".

    Phase 92: Cache key includes require_reliable setting to prevent
    stale results when the setting changes.

    Args:
        game: Game instance
        node: GameNode to evaluate
        require_reliable: If True, filter non-detector hints when visits < threshold

    Returns:
        BeginnerHint if a warning applies, None otherwise
    """
    cache_attr = "_beginner_hint_cache"

    # Phase 92: Cache stores (require_reliable, hint) tuple
    cached = getattr(node, cache_attr, _NOT_COMPUTED)
    if cached is not _NOT_COMPUTED and isinstance(cached, tuple) and len(cached) == 2:
        cached_require_reliable, cached_hint = cached
        if cached_require_reliable == require_reliable:
            # cached_hint is BeginnerHint | None (trust the cache we set)
            if cached_hint is None:
                return None
            # Cast to expected return type (we control what goes in the cache)
            from typing import cast

            return cast(BeginnerHint | None, cached_hint)
        # Setting changed, recompute

    hint = compute_beginner_hint(game, node, require_reliable=require_reliable)
    setattr(node, cache_attr, (require_reliable, hint))
    return hint
