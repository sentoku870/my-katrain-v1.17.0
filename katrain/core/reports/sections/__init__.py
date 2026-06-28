"""Reports sections package (Phase 154-D, 155-D).

Currently exposes:
- :mod:`katrain.core.reports.sections.win_loss`: per-game win/loss breakdown.
- :mod:`katrain.core.reports.sections.opponent_analysis`: opponent-strength
  loss correlation.
"""

from katrain.core.reports.sections.opponent_analysis import (
    build_opponent_strength_loss_correlation,
)
from katrain.core.reports.sections.win_loss import build_win_loss_analysis

__all__ = [
    "build_opponent_strength_loss_correlation",
    "build_win_loss_analysis",
]