"""Public facade for the beginner hints subpackage.

Phase 196: ``katrain.core.beginner.hints`` is now a subpackage; this
``api`` module exposes the public entry points plus the original
private helpers that tests and downstream modules reach into. New code
should import from ``katrain.core.beginner.hints`` directly (the
package ``__init__`` re-exports the same names).
"""

from __future__ import annotations

from katrain.core.beginner.hints._cache import (
    _NOT_COMPUTED,
    MIN_SUMMARY_VISITS,
    get_beginner_hint_cached,
    get_summary_hint_cached,
)
from katrain.core.beginner.hints._dispatch import (
    _DETECTOR_CATEGORIES,
    _category_enabled,
    _compute_summary_context,
    _get_meaning_tag_hint,
    _get_visits_from_node,
    _is_reliable,
    compute_beginner_hint,
    compute_summary_hint,
)
from katrain.core.beginner.hints._extract import (
    _extract_best_policy,
    _extract_predicted_territory,
    _is_endgame_position,
)
from katrain.core.beginner.hints._gate import (
    MIN_RELIABLE_VISITS,
    _normalize_board_size,
    build_category_filter,
    is_coords_valid,
    should_draw_board_highlight,
    should_show_beginner_hints,
    should_show_summary_hint,
)

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
    # Private helpers (kept for tests + downstream compatibility)
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
]
