"""Public entry point for the beginner hints subpackage.

Phase 196: the previous monolithic ``katrain.core.beginner.hints`` is now
this package. Implementation is split across:

* :mod:`._gate`    — pure gating functions (should_show_*, is_coords_valid)
* :mod:`._extract` — node attribute extractors (ownership / policy / endgame)
* :mod:`._dispatch`— detector chains + SummaryHintContext builder
* :mod:`._cache`   — sentinel + cached public entry points
* :mod:`.api`      — flat facade re-exporting everything for legacy callers

Importing from this package's ``__init__`` is the preferred path for
new code. Symbols re-exported here keep the legacy
``katrain.core.beginner.hints`` namespace working for tests and
downstream callers (``patch("katrain.core.beginner.hints.detect_*")``
etc.).
"""

from __future__ import annotations

from katrain.core.beginner.detector import (
    detect_cut_risk,
    detect_ignore_atari,
    detect_missed_capture,
    detect_self_atari,
)
from katrain.core.beginner.detector_difficulty import detect_difficulty_summary
from katrain.core.beginner.detector_freedom import count_freedom_candidates, detect_freedom_summary
from katrain.core.beginner.detector_katago import detect_katago_uncertain
from katrain.core.beginner.detector_mistake import detect_mistake_summary
from katrain.core.beginner.detector_ownership import detect_ownership_dominant
from katrain.core.beginner.detector_policy import detect_policy_confident, detect_policy_conflict
from katrain.core.beginner.hints.api import (
    _DETECTOR_CATEGORIES,
    _NOT_COMPUTED,
    MIN_RELIABLE_VISITS,
    MIN_SUMMARY_VISITS,
    _category_enabled,
    _compute_summary_context,
    _extract_best_policy,
    _extract_predicted_territory,
    _get_meaning_tag_hint,
    _get_visits_from_node,
    _is_endgame_position,
    _is_reliable,
    _normalize_board_size,
    build_category_filter,
    compute_beginner_hint,
    compute_summary_hint,
    get_beginner_hint_cached,
    get_summary_hint_cached,
    is_coords_valid,
    should_draw_board_highlight,
    should_show_beginner_hints,
    should_show_summary_hint,
)
from katrain.core.board_analysis import extract_groups_from_game

__all__ = [
    # Public entry points
    "compute_beginner_hint",
    "compute_summary_hint",
    "get_beginner_hint_cached",
    "get_summary_hint_cached",
    "is_coords_valid",
    "should_draw_board_highlight",
    "should_show_beginner_hints",
    "should_show_summary_hint",
    "MIN_RELIABLE_VISITS",
    "MIN_SUMMARY_VISITS",
    "build_category_filter",
    # Private helpers exposed for tests + downstream callers
    "_NOT_COMPUTED",
    "_DETECTOR_CATEGORIES",
    "_category_enabled",
    "_compute_summary_context",
    "_extract_best_policy",
    "_extract_predicted_territory",
    "_get_meaning_tag_hint",
    "_get_visits_from_node",
    "_is_endgame_position",
    "_is_reliable",
    "_normalize_board_size",
    # Detector functions (exposed so ``patch("katrain.core.beginner.hints.detect_*")``
    # in tests still works).
    "detect_cut_risk",
    "detect_ignore_atari",
    "detect_missed_capture",
    "detect_self_atari",
    "detect_difficulty_summary",
    "count_freedom_candidates",
    "detect_freedom_summary",
    "detect_katago_uncertain",
    "detect_mistake_summary",
    "detect_ownership_dominant",
    "detect_policy_confident",
    "detect_policy_conflict",
    "extract_groups_from_game",
]
