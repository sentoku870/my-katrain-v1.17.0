"""Phase 91-92 / 179-186: dispatch layer (detector chains + summary context).

Phase 196 extraction: contains everything that *computes* a hint rather
than gates it. The two main entry points are

* :func:`compute_beginner_hint` — the 4-detector structural chain
* :func:`compute_summary_hint` — the 7-detector priority chain (Phase
  179 + 182 + 186)

plus the ``SummaryHintContext`` builder and the small MeaningTag helper.

Implementation note: every detector call below goes through
``katrain.core.beginner.hints`` (the package, *not* a particular
detector module) so test code that does
``patch("katrain.core.beginner.hints.detect_mistake_summary", ...)``
keeps taking effect. Bypassing the legacy namespace here would force
the tests to know about the new private module layout.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from typing import Any

from katrain.core.beginner import hints as _hints_pkg
from katrain.core.beginner.hints._extract import (
    _extract_best_policy,
    _extract_predicted_territory,
    _is_endgame_position,
)
from katrain.core.beginner.models import BeginnerHint, DetectorInput, HintCategory, SummaryHintContext

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


def _get_visits_from_node(node: Any) -> int | None:
    """Get visits from node analysis using public helper."""
    from katrain.core.analysis import get_root_visits

    analysis = getattr(node, "analysis", None)
    return get_root_visits(analysis)


def _is_reliable(node: Any) -> bool:
    """Check if node analysis is reliable enough for hints."""
    from katrain.core.beginner.hints._gate import MIN_RELIABLE_VISITS

    visits = _get_visits_from_node(node)
    if visits is None:
        return False
    return visits >= MIN_RELIABLE_VISITS


def _get_meaning_tag_hint(node: Any, move_coords: tuple[int, int] | None) -> BeginnerHint | None:
    """Get beginner hint from node's MeaningTag (Phase 92)."""
    tag_id = getattr(node, "meaning_tag_id", None)
    if tag_id is None:
        return None

    category = HintCategory.from_meaning_tag_id(tag_id)
    if category is None:
        return None

    return BeginnerHint(
        category=category,
        coords=move_coords,
        severity=1,
        context={"source": "meaning_tag", "tag_id": tag_id},
    )


def compute_beginner_hint(
    game: Any,
    node: Any,
    *,
    require_reliable: bool = True,
) -> BeginnerHint | None:
    """Compute a beginner hint for a specific node (Phase 91-92)."""
    if node.move is None or node.parent is None:
        return None

    move = node.move
    if move.is_pass:
        return None

    original_node = game.current_node

    try:
        if game.current_node != node:
            game.set_current_node(node)

        captured = game.last_capture or []
        was_capture = bool(captured)
        captured_count = len(captured)
        groups_after = _hints_pkg.extract_groups_from_game(game)

        game.set_current_node(node.parent)
        groups_before = _hints_pkg.extract_groups_from_game(game)

        game.set_current_node(node)

        inp = DetectorInput(
            node=node,
            parent=node.parent,
            move_coords=move.coords,
            player=move.player,
            groups_after=groups_after,
            groups_before=groups_before,
            was_capture=was_capture,
            captured_count=captured_count,
        )

        hint = _hints_pkg.detect_self_atari(inp)
        if hint:
            return hint

        hint = _hints_pkg.detect_ignore_atari(inp)
        if hint:
            return hint

        hint = _hints_pkg.detect_missed_capture(inp)
        if hint:
            return hint

        hint = _hints_pkg.detect_cut_risk(inp, game)
        if hint:
            return hint

        hint = _get_meaning_tag_hint(node, move.coords)

        if hint and require_reliable and hint.category not in _DETECTOR_CATEGORIES and not _is_reliable(node):
            return None

        return hint

    finally:
        if game.current_node != original_node:
            game.set_current_node(original_node)


def _compute_summary_context(
    node: Any,
    *,
    threshold_blunder: float = 8.0,
    threshold_mistake: float = 2.0,
    threshold_score_stdev: float = 1.5,
) -> SummaryHintContext:
    """Build a SummaryHintContext from a GameNode."""
    from katrain.core.analysis import difficulty_metrics_from_node, get_root_visits, get_score_stdev

    parent = getattr(node, "parent", None)

    points_lost = getattr(node, "points_lost", None)

    candidate_moves = getattr(parent, "candidate_moves", None) if parent is not None else None
    good_count, near_count = _hints_pkg.count_freedom_candidates(candidate_moves)

    overall_difficulty: float | None = None
    is_reliable = False
    try:
        metrics = difficulty_metrics_from_node(node)
        if not getattr(metrics, "is_unknown", True):
            overall_difficulty = float(metrics.overall_difficulty)
            is_reliable = bool(metrics.is_reliable)
    except Exception:
        logger.debug("difficulty_metrics_from_node fallback during summary context build", exc_info=True)
        overall_difficulty = None
        is_reliable = False

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
    """Phase 179 + 182 + 186: Compute a summary hint from existing metrics."""
    from katrain.core.beginner.hints._cache import MIN_SUMMARY_VISITS

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

    if _flag("summary_mistake"):
        hint = _hints_pkg.detect_mistake_summary(ctx)
        if hint:
            return hint

    if _flag("summary_freedom"):
        hint = _hints_pkg.detect_freedom_summary(ctx)
        if hint:
            return hint

    if _flag("summary_difficulty"):
        hint = _hints_pkg.detect_difficulty_summary(ctx)
        if hint:
            return hint

    if _flag("katago_uncertain"):
        hint = _hints_pkg.detect_katago_uncertain(ctx)
        if hint:
            return hint

    if _flag("summary_ownership"):
        hint = _hints_pkg.detect_ownership_dominant(ctx)
        if hint:
            return hint

    if _flag("summary_policy"):
        hint = _hints_pkg.detect_policy_confident(ctx)
        if hint:
            return hint
        hint = _hints_pkg.detect_policy_conflict(ctx)
        if hint:
            return hint

    if _flag("curator_hint"):
        hint = _hints_pkg.detect_curator_weak_axis(
            node,
            user_weak_tags,
            min_occurrences=curator_min_occurrences,
        )
        if hint:
            return hint

    return None
