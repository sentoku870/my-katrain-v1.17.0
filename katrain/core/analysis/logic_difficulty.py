"""DEPRECATED backwards-compat shim for ``katrain.core.analysis.logic_difficulty``.

Phase B2: The position-difficulty pipeline has moved to the
``katrain.core.analysis.difficulty`` subpackage. This module remains
in place so existing imports like
``from katrain.core.analysis.logic_difficulty import difficulty_metrics_from_node``
keep working unchanged, but **new code should import from the new
subpackage**.

Both the public and private symbols from the original 756-line
file are re-exported here so test files that reach into
``_compute_policy_difficulty`` (etc.) keep compiling.

History:
- Phase 144-C extracted this from ``katrain.core.analysis.logic``.
- Phase B2 (Architecture Review follow-up) split the file into a
  7-module subpackage while keeping this module as a thin shim.
"""

from __future__ import annotations

# Transition / state / error-pressure / lcb-gap
from katrain.core.analysis.difficulty._error_pressure import compute_error_pressure

# IO / candidates helpers
from katrain.core.analysis.difficulty._io import (
    _difficulty_logger,
    determine_reliability,
    get_candidates_from_node,
    get_root_visits,
    normalize_candidates,
)
from katrain.core.analysis.difficulty._lcb_gap import compute_lcb_gap

# Policy signal
from katrain.core.analysis.difficulty._policy import (
    assess_difficulty_from_policy,
    compute_policy_difficulty,
)
from katrain.core.analysis.difficulty._state import compute_state_difficulty
from katrain.core.analysis.difficulty._transition import compute_transition_difficulty

# Public API (top-level)
from katrain.core.analysis.difficulty.api import (  # noqa: E402
    assess_position_difficulty_from_parent,
    compute_difficulty_metrics,
    difficulty_metrics_from_node,
    extract_difficult_positions,
)

# Private aliases for tests + downstream modules that historically
# reached into this module's underscore-prefixed helpers. The new
# subpackage uses leading-underscore names ("_compute_*") but the
# public naming there is just "compute_*" (no underscore). We
# therefore re-export them under both spellings here so legacy
# imports keep working.
_compute_policy_difficulty = compute_policy_difficulty
_compute_transition_difficulty = compute_transition_difficulty
_compute_state_difficulty = compute_state_difficulty
_determine_reliability = determine_reliability
_get_root_visits = get_root_visits
_get_candidates_from_node = get_candidates_from_node
_normalize_candidates = normalize_candidates
_assess_difficulty_from_policy = assess_difficulty_from_policy

__all__ = [
    # Public API
    "assess_position_difficulty_from_parent",
    "compute_difficulty_metrics",
    "difficulty_metrics_from_node",
    "extract_difficult_positions",
    # Helpers (kept under their original underscore names so existing
    # imports keep binding).
    "_compute_policy_difficulty",
    "_compute_transition_difficulty",
    "_compute_state_difficulty",
    "_determine_reliability",
    "_get_root_visits",
    "_get_candidates_from_node",
    "_normalize_candidates",
    "_assess_difficulty_from_policy",
    "_difficulty_logger",
    # New naming (canonical).
    "assess_difficulty_from_policy",
    "compute_policy_difficulty",
    "compute_transition_difficulty",
    "compute_state_difficulty",
    "compute_error_pressure",
    "compute_lcb_gap",
    "determine_reliability",
    "get_root_visits",
    "normalize_candidates",
    "get_candidates_from_node",
]
