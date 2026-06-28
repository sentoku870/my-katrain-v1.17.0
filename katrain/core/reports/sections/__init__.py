"""Reports sections package (Phase 154-D).

Currently exposes:
- :mod:`katrain.core.reports.sections.win_loss`: per-game win/loss breakdown.
"""

from katrain.core.reports.sections.win_loss import build_win_loss_analysis

__all__ = ["build_win_loss_analysis"]