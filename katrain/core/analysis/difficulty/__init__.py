"""Position difficulty subpackage (Phase B2).

Public API re-exports. The actual implementation lives in:

- :mod:`katrain.core.analysis.difficulty.api` — the four published entry points
- :mod:`katrain.core.analysis.difficulty._io` — analysis payload extraction
- :mod:`katrain.core.analysis.difficulty._policy` — policy signal
- :mod:`katrain.core.analysis.difficulty._transition` — transition (drop) signal
- :mod:`katrain.core.analysis.difficulty._state` — board complexity signal
- :mod:`katrain.core.analysis.difficulty._error_pressure` — KataGo uncertainty
- :mod:`katrain.core.analysis.difficulty._lcb_gap` — LCB gap
"""

from __future__ import annotations

from katrain.core.analysis.difficulty._io import (
    determine_reliability,
    get_candidates_from_node,
    get_root_visits,
    normalize_candidates,
)
from katrain.core.analysis.difficulty._policy import (
    assess_difficulty_from_policy,
    compute_policy_difficulty,
)
from katrain.core.analysis.difficulty._state import compute_state_difficulty
from katrain.core.analysis.difficulty._transition import compute_transition_difficulty
from katrain.core.analysis.difficulty.api import (
    assess_position_difficulty_from_parent,
    compute_difficulty_metrics,
    difficulty_metrics_from_node,
    extract_difficult_positions,
)

__all__ = [
    "assess_difficulty_from_policy",
    "assess_position_difficulty_from_parent",
    "compute_difficulty_metrics",
    "compute_policy_difficulty",
    "compute_state_difficulty",
    "compute_transition_difficulty",
    "determine_reliability",
    "difficulty_metrics_from_node",
    "extract_difficult_positions",
    "get_candidates_from_node",
    "get_root_visits",
    "normalize_candidates",
]
