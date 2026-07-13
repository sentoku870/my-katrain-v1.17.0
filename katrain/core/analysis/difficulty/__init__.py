"""Position difficulty subpackage (Phase B2).

Public API re-exports. The actual implementation lives in:

- :mod:`katrain.core.analysis.difficulty.api` — the four published entry points
- :mod:`katrain.core.analysis.difficulty._io` — analysis payload extraction
- :mod:`katrain.core.analysis.difficulty._policy` — policy signal
- :mod:`katrain.core.analysis.difficulty._transition` — transition (drop) signal
- :mod:`katrain.core.analysis.difficulty._state` — board complexity signal
- :mod:`katrain.core.analysis.difficulty._error_pressure` — KataGo uncertainty
- :mod:`katrain.core.analysis.difficulty._lcb_gap` — LCB gap

History: this subpackage replaces the 756-line
``katrain.core.analysis.logic_difficulty`` (Phase 144-C) in Phase B2.
The legacy module is preserved as a thin re-export shim for backwards
compatibility.
"""

from __future__ import annotations

from katrain.core.analysis.difficulty.api import (
    assess_position_difficulty_from_parent,
    compute_difficulty_metrics,
    difficulty_metrics_from_node,
    extract_difficult_positions,
)

__all__ = [
    "assess_position_difficulty_from_parent",
    "compute_difficulty_metrics",
    "difficulty_metrics_from_node",
    "extract_difficult_positions",
]
