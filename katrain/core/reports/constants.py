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

# --- Mistake Streak Detection (Phase 158-F) ---
# Threshold for ``mistake_streaks`` in the Karte JSON. The previous
# implementation reused ``URGENT_MISS_*`` (>=20.0 points, min 3 moves),
# which is calibrated for catastrophic life-and-death collapses and
# almost never fires for sub-5-dan games. ``mistake_streaks`` is a
# distinct section ("streak of mistakes", not "streak of blunders"), so
# it now uses a mistake-level threshold: a run of 2+ moves each losing
# at least ``MISTAKE_STREAK_THRESHOLD_LOSS`` points.
MISTAKE_STREAK_THRESHOLD_LOSS: Final[float] = 2.0
MISTAKE_STREAK_MIN_CONSECUTIVE: Final[int] = 2

# --- Mistake Classification ---
# Loss threshold for considering a move as a "bad" move worthy of reporting
BAD_MOVE_LOSS_THRESHOLD: Final[float] = 0.5

# --- Report Types ---
REPORT_TYPE_KARTE: Final[str] = "karte"
REPORT_TYPE_SUMMARY: Final[str] = "summary"
REPORT_TYPE_PACKAGE: Final[str] = "package"

# --- Summary Report Defaults ---
SUMMARY_DEFAULT_MAX_WORST_MOVES: Final[int] = 10
