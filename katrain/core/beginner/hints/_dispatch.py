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
    """Check if node analysis is reliable enough for hints.

    Phase 252: the threshold scales with board size (19x19 = 200,
    13x13 = 150, 9x9 = 100). Falls back to ``MIN_RELIABLE_VISITS = 200``
    for unknown sizes / missing ``game`` attribute so legacy tests
    and pre-Phase-252 callers keep their behaviour.
    """
    from katrain.core.beginner.hints._gate import min_reliable_visits_for_board_size

    visits = _get_visits_from_node(node)
    if visits is None:
        return False
    # Extract board_size from node → game → root (best effort, never
    # raise — the dispatcher should silently fall back to the 19x19
    # default for any node that lacks a full game tree).
    board_size = None
    try:
        parent = getattr(node, "parent", None)
        game = getattr(parent, "game", None) if parent is not None else None
        if game is not None:
            board_size = getattr(game, "board_size", None)
    except Exception:
        board_size = None
    threshold = min_reliable_visits_for_board_size(board_size)
    return visits >= threshold


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


def _category_enabled(category: "HintCategory", category_filter: dict[str, bool] | None) -> bool:
    """Phase 251: per-category enable check.

    Returns True when the category's ``config_key`` is enabled. A missing
    key in ``category_filter`` is treated as enabled (preserves the
    pre-Phase-251 default of "all hints visible when master switch is on").

    Args:
        category: The hint category to test.
        category_filter: Dict of ``config_key -> bool`` as built by the
            settings UI / config loader. May be None (legacy callers
            that have not migrated yet) — treated as "all enabled".
    """
    if not category_filter:
        return True
    key = category.config_key
    if key is None:
        return True
    return bool(category_filter.get(key, True))


def compute_beginner_hint(
    game: Any,
    node: Any,
    *,
    require_reliable: bool = True,
    aggregate: bool = False,
    category_filter: dict[str, bool] | None = None,
) -> BeginnerHint | None:
    """Compute a beginner hint for a specific node (Phase 91-92).

    Args:
        game: Game instance
        node: Target node
        require_reliable: If True, meaning_tag / curator hints require
            ``root_visits >= MIN_RELIABLE_VISITS`` to fire.
        aggregate: Phase 248-C4 — when True, run *all* detectors and
            return the one with the highest ``severity`` (ties broken
            by the original priority chain: structural > meaning_tag).
            When False (default), preserve the Phase 91 short-circuit
            behaviour (first non-None wins).
        category_filter: Phase 251 — per-category enable map. Keys are
            ``HintCategory.config_key`` values (e.g. ``"self_atari"``,
            ``"low_liberties"``, ``"summary_mistake"``). Missing keys
            are treated as enabled. ``None`` means "all enabled"
            (preserves pre-Phase-251 behaviour for callers that have
            not migrated).

    Note:
        The default ``aggregate=False`` keeps backward compatibility
        for all existing callers. ``aggregate=True`` is a stricter
        variant that surfaces every applicable hint. Use it from the
        controlspanel status line when the user explicitly asks
        "what's wrong with this move?" — see ``gui/controlspanel.py``.
    """
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

        # Phase 248-C4: collect every applicable hint, then return the
        # highest-severity one (ties → first in the original chain).
        if aggregate:
            return _aggregate_hints(game, node, inp, move.coords, require_reliable, category_filter)

        hint = _hints_pkg.detect_self_atari(inp)
        if hint and _category_enabled(hint.category, category_filter):
            return hint

        hint = _hints_pkg.detect_ignore_atari(inp)
        if hint and _category_enabled(hint.category, category_filter):
            return hint

        hint = _hints_pkg.detect_missed_capture(inp)
        if hint and _category_enabled(hint.category, category_filter):
            return hint

        hint = _hints_pkg.detect_cut_risk(inp, game)
        if hint and _category_enabled(hint.category, category_filter):
            return hint

        hint = _get_meaning_tag_hint(node, move.coords)

        if hint and require_reliable and hint.category not in _DETECTOR_CATEGORIES and not _is_reliable(node):
            return None
        if hint and not _category_enabled(hint.category, category_filter):
            return None

        return hint

    finally:
        if game.current_node != original_node:
            game.set_current_node(original_node)


def _aggregate_hints(
    game: Any,
    node: Any,
    inp: Any,
    move_coords: tuple[int, int] | None,
    require_reliable: bool,
    category_filter: dict[str, bool] | None = None,
) -> BeginnerHint | None:
    """Phase 248-C4: run every detector, return the highest-severity hint.

    Returns the hint with the largest ``severity`` field. Ties are
    broken by the original priority chain order (structural detectors
    first, then meaning_tag). ``None`` if nothing fires.

    Args:
        game: Game instance (forwarded to ``detect_cut_risk``).
        node: Target node (used by ``_get_meaning_tag_hint``).
        inp: DetectorInput shared across all four structural detectors.
        move_coords: Coords of the played move, forwarded to the
            meaning-tag fallback so its hint has a non-None ``coords``.
        require_reliable: If True, meaning_tag fallback requires
            ``root_visits >= MIN_RELIABLE_VISITS`` (mirrors the legacy
            path's gate in :func:`compute_beginner_hint`).
        category_filter: Phase 251 — per-category enable map. Categories
            whose ``config_key`` resolves to ``False`` are filtered out
            before the highest-severity pick. ``None`` means no filter.

    Returns:
        The highest-severity hint, or ``None``.
    """
    candidates: list[BeginnerHint] = []

    for detector in (
        _hints_pkg.detect_self_atari,
        _hints_pkg.detect_ignore_atari,
        _hints_pkg.detect_missed_capture,
    ):
        hint = detector(inp)
        if hint is not None and _category_enabled(hint.category, category_filter):
            candidates.append(hint)

    # detect_cut_risk needs the game argument.
    hint = _hints_pkg.detect_cut_risk(inp, game)
    if hint is not None and _category_enabled(hint.category, category_filter):
        candidates.append(hint)

    # meaning_tag fallback. Same require_reliable gate as the legacy path.
    mt_hint = _get_meaning_tag_hint(node, move_coords)
    if mt_hint is not None:
        if require_reliable and mt_hint.category not in _DETECTOR_CATEGORIES and not _is_reliable(node):
            mt_hint = None
        if mt_hint is not None and _category_enabled(mt_hint.category, category_filter):
            candidates.append(mt_hint)

    if not candidates:
        return None

    # Sort by (-severity, index) so the first non-None structural
    # detector wins on ties. Python's ``sorted`` is stable, so
    # candidates.append order itself encodes the original priority
    # order — we only need to break severity ties.
    candidates.sort(key=lambda h: -h.severity)
    return candidates[0]


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
    category_filter: dict[str, bool] | None = None,
) -> BeginnerHint | None:
    """Phase 179 + 182 + 186: Compute a summary hint from existing metrics.

    Args:
        node: GameNode.
        summary_flags: Group-level flags (e.g. ``summary_mistake``,
            ``summary_freedom``). When a group flag is False, the entire
            group is skipped.
        require_reliable: If True, skip when root visits are below
            ``MIN_SUMMARY_VISITS``.
        threshold_blunder: Phase 179: blunder threshold (in score loss).
        threshold_mistake: Phase 179: mistake threshold (in score loss).
        threshold_score_stdev: Phase 179: KataGo uncertain threshold.
        user_weak_tags: Phase 186: meaning-tag frequency from curator
            profile. ``None`` / empty disables the curator hint.
        curator_min_occurrences: Phase 186: minimum tag occurrences to
            count as a "weak axis".
        category_filter: Phase 251 — per-category enable map. Even if
            a group flag is on, an individual category whose key is
            ``False`` is filtered out before returning. ``None`` /
            empty means no individual filter.
    """
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
        if hint and _category_enabled(hint.category, category_filter):
            return hint

    if _flag("summary_freedom"):
        hint = _hints_pkg.detect_freedom_summary(ctx)
        if hint and _category_enabled(hint.category, category_filter):
            return hint

    if _flag("summary_difficulty"):
        hint = _hints_pkg.detect_difficulty_summary(ctx)
        if hint and _category_enabled(hint.category, category_filter):
            return hint

    if _flag("katago_uncertain"):
        hint = _hints_pkg.detect_katago_uncertain(ctx)
        if hint and _category_enabled(hint.category, category_filter):
            return hint

    if _flag("summary_ownership"):
        hint = _hints_pkg.detect_ownership_dominant(ctx)
        if hint and _category_enabled(hint.category, category_filter):
            return hint

    if _flag("summary_policy"):
        hint = _hints_pkg.detect_policy_confident(ctx)
        if hint and _category_enabled(hint.category, category_filter):
            return hint
        hint = _hints_pkg.detect_policy_conflict(ctx)
        if hint and _category_enabled(hint.category, category_filter):
            return hint

    if _flag("curator_hint"):
        hint = _hints_pkg.detect_curator_weak_axis(
            node,
            user_weak_tags,
            min_occurrences=curator_min_occurrences,
        )
        if hint and _category_enabled(hint.category, category_filter):
            return hint

    return None
