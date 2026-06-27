"""Constants for Report and Summary features.

This module contains constants used in report generation, including
thresholds for mistake classification, urgent miss detection, and
confidence levels.

Note: RELIABILITY_VISITS_THRESHOLD was moved to
katrain.core.analysis.models.reliability (single source of truth,
Phase 149 A-4).
"""

from typing import Final

# --- Urgent Miss Detection ---
URGENT_MISS_THRESHOLD_LOSS: Final[float] = 20.0
URGENT_MISS_MIN_CONSECUTIVE: Final[int] = 3

# --- Mistake Classification ---
# Loss threshold for considering a move as a "bad" move worthy of reporting
BAD_MOVE_LOSS_THRESHOLD: Final[float] = 0.5

# --- Report Types ---
REPORT_TYPE_KARTE: Final[str] = "karte"
REPORT_TYPE_SUMMARY: Final[str] = "summary"
REPORT_TYPE_PACKAGE: Final[str] = "package"

# --- Summary Report Defaults ---
SUMMARY_DEFAULT_MAX_WORST_MOVES: Final[int] = 10
