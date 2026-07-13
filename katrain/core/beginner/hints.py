"""Phase 91-92 + Phase 179: Beginner Hint Computation

Main entry points for computing beginner hints.

Phase 91: 4 priority detectors (SELF_ATARI, IGNORE_ATARI, MISSED_CAPTURE, CUT_RISK)
Phase 92: MeaningTag fallback, reliability filter, gating functions
Phase 179: Summary hint layer (Mistake / Freedom / Difficulty / KataGo)
          driven by SummaryHintContext, separate from the structural chain.
"""

from __future__ import annotations

from typing import Any

from katrain.core.beginner.detector import (
    detect_cut_risk,
    detect_ignore_atari,
    detect_missed_capture,
    detect_self_atari,
)
from katrain.core.beginner.detector_curator import detect_curator_weak_axis
from katrain.core.beginner.detector_difficulty import detect_difficulty_summary
from katrain.core.beginner.detector_freedom import count_freedom_candidates, detect_freedom_summary
from katrain.core.beginner.detector_katago import detect_katago_uncertain
from katrain.core.beginner.detector_mistake import detect_mistake_summary
from katrain.core.beginner.detector_ownership import detect_ownership_dominant
from katrain.core.beginner.detector_policy import detect_policy_confident, detect_policy_conflict
from katrain.core.beginner.models import BeginnerHint, DetectorInput, HintCategory, SummaryHintContext
from katrain.core.board_analysis import extract_groups_from_game

# Sentinel value for cache (distinguishes None from "not computed")
_NOT_COMPUTED = object()

# Phase 92: Reliability filter constant for structural hints.
MIN_RELIABLE_VISITS = 200

# Phase 179: Relaxed threshold for summary hints. Summary hints are
# informational and tolerate lower visits; MISTAKE_GOOD still requires
# >= 300 (enforced inside detector_mistake.py).
MIN_SUMMARY_VISITS = 100

# Phase 92: Detector categories (always reliable, use board state).
# Backward-compat alias for tests / external callers.
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


def should_show_summary_hint(
    enabled: bool,
    mode: str,
    summary_key: str,
    summary_flags: dict[str, bool] | None,
) -> bool:
    """Phase 179: gate a summary hint category group.

    Args:
        enabled: beginner_hints/enabled (master switch).
        mode: Current play_analyze_mode.
        summary_key: One of "summary_mistake", "summary_freedom",
            "summary_difficulty", "katago_uncertain".
        summary_flags: Dict of summary_key -> bool. Missing keys default
            to True (preserve existing behavior for users who upgrade).

    Returns:
        True if the summary hint category group should be displayed.
    """
    if not should_show_beginner_hints(enabled, mode):
        return False
    if not summary_flags:
        return True
    return bool(summary_flags.get(summary_key, True))


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
        if hint and require_reliable and hint.category not in _DETECTOR_CATEGORIES and not _is_reliable(node):
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


# =============================================================================
# Phase 179: Summary Hint Computation
# =============================================================================


def _compute_summary_context(
    node: Any,
    *,
    threshold_blunder: float = 8.0,
    threshold_mistake: float = 2.0,
    threshold_score_stdev: float = 1.5,
) -> SummaryHintContext:
    """Build a SummaryHintContext from a GameNode.

    Pulls points_lost / good_move_count / overall_difficulty / score_stdev
    from public API surfaces. Defensive against missing analysis (all
    fields default to None / 0).

    Phase 179.1: scoreStdev / visits extracted via the public helpers
    ``katrain.core.analysis.get_score_stdev`` and
    ``katrain.core.analysis.get_root_visits`` instead of raw
    ``analysis.get(...)`` dict traversal.

    Args:
        node: GameNode after the move to evaluate.
        threshold_blunder: MISTAKE_BLUNDER threshold (default 8.0).
        threshold_mistake: MISTAKE_MISTAKE threshold (default 2.0).
        threshold_score_stdev: KATAGO_UNCERTAIN threshold (default 1.5).

    Returns:
        SummaryHintContext populated from the node (fields may be None).
    """
    from katrain.core.analysis import difficulty_metrics_from_node, get_root_visits, get_score_stdev

    parent = getattr(node, "parent", None)

    points_lost = getattr(node, "points_lost", None)

    # Phase 179.2: shared with ``gui.controlspanel.update_evaluation``.
    candidate_moves = getattr(parent, "candidate_moves", None) if parent is not None else None
    good_count, near_count = count_freedom_candidates(candidate_moves)

    overall_difficulty: float | None = None
    is_reliable = False
    try:
        metrics = difficulty_metrics_from_node(node)
        if not getattr(metrics, "is_unknown", True):
            overall_difficulty = float(metrics.overall_difficulty)
            is_reliable = bool(metrics.is_reliable)
    except Exception:
        overall_difficulty = None
        is_reliable = False

    # Phase 179.1: use the public helpers so that changes to the analysis
    # payload schema (e.g. the legacy ``rootInfo`` vs current ``root``
    # key convention) flow through a single source of truth instead of
    # being duplicated here.
    analysis = getattr(node, "analysis", None)
    visits_val = get_root_visits(analysis)
    try:
        visits_int = int(visits_val) if visits_val is not None else 0
    except (TypeError, ValueError):
        visits_int = 0

    score_stdev_raw = get_score_stdev(node)
    score_stdev: float | None = float(score_stdev_raw) if score_stdev_raw is not None else None

    move_number = 0
    if node.move is not None:
        move_number = int(getattr(node.move, "move_number", 0) or 0)
    if move_number == 0:
        depth = getattr(node, "depth", 0) or 0
        move_number = int(depth)

    is_endgame = _is_endgame_position(node)

    # Phase 182: ownership / policy extraction. Both fields require
    # explicit opt-in on the engine side (``_enable_ownership``) or are
    # only available when KataGo includes them in the analysis payload.
    # We read the public ``node.ownership`` / ``node.policy`` properties
    # which already guard against missing / malformed data (game_node.py
    # :309 and :313).
    predicted_territory = _extract_predicted_territory(node)
    best_policy = _extract_best_policy(node)

    return SummaryHintContext(
        points_lost=float(points_lost) if points_lost is not None else None,
        good_move_count=good_count,
        near_move_count=near_count,
        overall_difficulty=overall_difficulty,
        is_reliable=is_reliable,
        score_stdev=score_stdev,
        root_visits=visits_int,
        move_number=move_number,
        is_endgame=is_endgame,
        score_loss_threshold_blunder=float(threshold_blunder),
        score_loss_threshold_mistake=float(threshold_mistake),
        score_stdev_threshold=float(threshold_score_stdev),
        predicted_territory=predicted_territory,
        best_policy=best_policy,
    )


def _extract_predicted_territory(node: Any) -> float | None:
    """Phase 182: derive a single-sided territory signal from
    ``node.ownership``.

    The ownership grid is a flat list with one value per cell:
    +1 = that cell is fully owned by Black (per KataGo's JSON convention),
    -1 = fully White, 0 = neutral. Summing all cells and dividing by the
    cell count gives ``predicted_territory`` in ``[-1.0, +1.0]`` where
    +1 means Black owns 100% of the board, -1 means White owns 100%.
    Beginners benefit from this single signed scalar far more than from
    a 361-cell grid.

    Args:
        node: GameNode.

    Returns:
        Normalised territory in [-1.0, +1.0], or None when ownership is
        unavailable (config disabled, analysis missing, or malformed).
    """
    ownership = getattr(node, "ownership", None)
    if not ownership:
        return None
    # Skip Nones / non-numeric cells (KataGo occasionally emits None for
    # points where the network is fully undecided).
    values: list[float] = []
    for v in ownership:
        if v is None:
            continue
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return sum(values) / len(values)


def _extract_best_policy(node: Any) -> float | None:
    """Phase 182: extract the maximum probability from ``node.policy``.

    The policy distribution is a flat list of probabilities (one per
    cell, summing to ~1). The maximum value indicates how confident
    KataGo's policy network is about its top choice. Range 0..1.

    Args:
        node: GameNode.

    Returns:
        Maximum policy probability in [0.0, 1.0], or None when policy is
        unavailable (analysis missing, or empty / malformed list).
    """
    policy = getattr(node, "policy", None)
    if not policy:
        return None
    best = 0.0
    for v in policy:
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f > best:
            best = f
    return best if best > 0.0 else None


def _is_endgame_position(node: Any) -> bool:
    """Phase 179.2: endgame heuristic for MISTAKE_GOOD gating.

    Returns True when the node is in (or very close to) the endgame. Two
    signals are combined:

    1. **Dynamic (primary)**: KataGo's ``scoreStdev`` is at or below
       ``ENDGAME_SCORE_STDEV_THRESHOLD`` (8.0). This is the same
       threshold used by ``analysis.logic_phase_dynamic`` (Phase 156-A
       / 158-G) for the dynamic phase classifier — when KataGo has
       effectively read the position out, the game is likely in the
       endgame.
    2. **Static (fallback)**: ``move_number >= 200`` for legacy /
       short-game compatibility. Used only when ``scoreStdev`` is
       unavailable (no analysis yet, batch mode without stdev).

    The previous static-only check (Phase 179.1, ``move_number >= 200``)
    fired for middle-game persistence fights on 19x19 boards because
    long sequences of small skirmishes can stay below 200 moves; in
    those positions MISTAKE_GOOD ("良い手") praise would mislead
    beginners.

    Args:
        node: GameNode.

    Returns:
        True if the position is plausibly in the endgame.
    """
    # Primary signal: KataGo's scoreStdev <= 8.0 implies endgame-eligible.
    from katrain.core.analysis import get_score_stdev
    from katrain.core.analysis.logic_phase_dynamic import ENDGAME_SCORE_STDEV_THRESHOLD

    stdev_val = get_score_stdev(node)
    if stdev_val is not None:
        return float(stdev_val) <= float(ENDGAME_SCORE_STDEV_THRESHOLD)

    # Fallback: static move-number heuristic. Used when scoreStdev is
    # unavailable (analysis missing, batch re-run, very recent init).
    move_number = 0
    if getattr(node, "move", None) is not None:
        move_number = int(getattr(node.move, "move_number", 0) or 0)
    if move_number == 0:
        depth = getattr(node, "depth", 0) or 0
        move_number = int(depth)
    return move_number >= 200


def compute_summary_hint(
    node: Any,
    *,
    summary_flags: dict[str, bool] | None = None,
    require_reliable: bool = True,
    threshold_blunder: float = 8.0,
    threshold_mistake: float = 2.0,
    threshold_score_stdev: float = 1.5,
    user_weak_tags: dict[str, int] | None = None,
    curator_min_occurrences: int = 3,
) -> BeginnerHint | None:
    """Phase 179 + 182 + 186: Compute a summary hint from existing metrics.

    Runs Mistake / Freedom / Difficulty / KataGo / Ownership / Policy /
    Curator detectors in priority order. Each detector group is
    independently gated by ``summary_flags``. Returns the
    highest-priority BeginnerHint or None.

    Args:
        node: GameNode to evaluate.
        summary_flags: Dict of group_key -> bool. Each group:
            - "summary_mistake"
            - "summary_freedom"
            - "summary_difficulty"
            - "katago_uncertain"
            - "summary_ownership"
            - "summary_policy"
            - "curator_hint"
            Missing keys default to True.
        require_reliable: If True, skip summary hint when visits < MIN_SUMMARY_VISITS.
        threshold_blunder: MISTAKE_BLUNDER threshold.
        threshold_mistake: MISTAKE_MISTAKE threshold.
        threshold_score_stdev: KATAGO_UNCERTAIN threshold.
        user_weak_tags: Phase 186: ``{meaning_tag_id: occurrence_count}``
            loaded from the Curator profile. When provided, the
            CURATOR_WEAK_AXIS detector can fire on nodes whose
            ``meaning_tag_id`` matches a frequent user weakness. None
            disables the curator layer entirely.
        curator_min_occurrences: Phase 186: minimum tag count for a
            user-weakness to count as a real pattern. Default 3 (matches
            the pattern-miner's statistical significance threshold).

    Returns:
        Highest-priority BeginnerHint, or None.
    """
    ctx = _compute_summary_context(
        node,
        threshold_blunder=threshold_blunder,
        threshold_mistake=threshold_mistake,
        threshold_score_stdev=threshold_score_stdev,
    )

    visits = int(ctx.root_visits)
    if require_reliable and visits < MIN_SUMMARY_VISITS:
        return None

    flags = summary_flags or {}

    def _flag(key: str) -> bool:
        return bool(flags.get(key, True))

    # Priority order: Mistake (concrete loss) > Freedom (board shape) >
    # Difficulty (KataGo metric) > KataGo uncertainty (most contextual) >
    # Ownership / Policy (board-state observations) >
    # Curator (whole-game aggregation).
    if _flag("summary_mistake"):
        hint = detect_mistake_summary(ctx)
        if hint:
            return hint

    if _flag("summary_freedom"):
        hint = detect_freedom_summary(ctx)
        if hint:
            return hint

    if _flag("summary_difficulty"):
        hint = detect_difficulty_summary(ctx)
        if hint:
            return hint

    if _flag("katago_uncertain"):
        hint = detect_katago_uncertain(ctx)
        if hint:
            return hint

    if _flag("summary_ownership"):
        hint = detect_ownership_dominant(ctx)
        if hint:
            return hint

    if _flag("summary_policy"):
        # POLICY_CONFIDENT (severity 0) takes priority over POLICY_CONFLICT
        # (severity 1) by ordering — the former is "KataGo has a clear
        # choice" which is the more actionable teaching signal.
        hint = detect_policy_confident(ctx)
        if hint:
            return hint
        hint = detect_policy_conflict(ctx)
        if hint:
            return hint

    if _flag("curator_hint"):
        # Phase 186: lowest priority. Curator hints are aggregated
        # context — useful for the user's overall improvement story but
        # not actionable per-move. They never outrank a Mistake /
        # structural hint.
        hint = detect_curator_weak_axis(
            node,
            user_weak_tags,
            min_occurrences=curator_min_occurrences,
        )
        if hint:
            return hint

    return None


def get_summary_hint_cached(
    node: Any,
    *,
    summary_flags: dict[str, bool] | None = None,
    require_reliable: bool = True,
    user_weak_tags: dict[str, int] | None = None,
    curator_min_occurrences: int = 3,
) -> BeginnerHint | None:
    """Phase 179 + 186: Cached wrapper around ``compute_summary_hint``.

    Caches on the node under ``_summary_hint_cache`` keyed by the
    ``summary_flags`` mapping, ``require_reliable``, and
    ``user_weak_tags`` (so toggling any of them invalidates the cache).
    The cache is separate from the structural Beginner Hint cache so
    the two layers can be invalidated independently.

    Phase 179.1: ``require_reliable`` added to cache key.
    Phase 186: ``user_weak_tags`` added to cache key so re-running with
    a different curator profile always produces a fresh result.

    Args:
        node: GameNode to evaluate.
        summary_flags: See ``compute_summary_hint``.
        require_reliable: See ``compute_summary_hint``.
        user_weak_tags: Phase 186 — see ``compute_summary_hint``.
        curator_min_occurrences: Phase 186 — see ``compute_summary_hint``.

    Returns:
        BeginnerHint or None.
    """
    cache_attr = "_summary_hint_cache"
    flags_key = None if not summary_flags else tuple(sorted((k, bool(v)) for k, v in summary_flags.items()))
    curator_key = None if not user_weak_tags else tuple(sorted((k, int(v)) for k, v in user_weak_tags.items()))
    cache_key = (flags_key, bool(require_reliable), curator_key, int(curator_min_occurrences))
    cached = getattr(node, cache_attr, _NOT_COMPUTED)
    if cached is not _NOT_COMPUTED and isinstance(cached, tuple) and len(cached) == 2:
        cached_cache_key, cached_hint = cached
        if cached_cache_key == cache_key:
            from typing import cast

            return cast(BeginnerHint | None, cached_hint)

    hint = compute_summary_hint(
        node,
        summary_flags=summary_flags,
        require_reliable=require_reliable,
        user_weak_tags=user_weak_tags,
        curator_min_occurrences=curator_min_occurrences,
    )
    setattr(node, cache_attr, (cache_key, hint))
    return hint
