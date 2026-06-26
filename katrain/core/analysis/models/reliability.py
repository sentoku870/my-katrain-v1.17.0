"""katrain.core.analysis.models.reliability - Reliability stats and confidence constants.

Phase 144-B: Extracted from models.py (1230 lines → 6 focused modules).

Contains:
- ReliabilityStats: Data quality / reliability statistics dataclass
- RELIABILITY_VISITS_THRESHOLD, RELIABILITY_RATIO, etc.: Reliability constants
- DIFFICULTY_MODIFIER_*: Difficulty-based importance modifiers
- STREAK_START_BONUS, SWING_*: Scoring bonuses
- MIN_COVERAGE_MOVES, _CONFIDENCE_THRESHOLDS: Confidence level computation
- RELIABILITY_SCALE_THRESHOLDS: Visit count to weight mapping
"""
from __future__ import annotations

from dataclasses import dataclass


# =============================================================================
# Reliability constants and structures
# =============================================================================


RELIABILITY_VISITS_THRESHOLD = 200
RELIABILITY_RATIO = 0.9  # 90% of target visits considered reliable (Phase 44)
UNRELIABLE_IMPORTANCE_SCALE = 0.25
SWING_SCORE_SIGN_BONUS = 1.0
SWING_WINRATE_CROSS_BONUS = 1.0

# Importance Scoring Constants (PR#4: Ranking Redesign)
DIFFICULTY_MODIFIER_HARD = 1.0
DIFFICULTY_MODIFIER_ONLY_MOVE = -1.0  # Phase 23: -2.0 → -1.0 (緩和)
DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_BONUS = 0.5  # Phase 23: 大損失時の追加緩和
DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_THRESHOLD = 2.0  # Phase 23: 大損失閾値（目数）
DIFFICULTY_MODIFIER_EASY = 0.0
DIFFICULTY_MODIFIER_NORMAL = 0.0

STREAK_START_BONUS = 2.0
SWING_MAGNITUDE_WEIGHT = 0.5

# Reliability scale thresholds
RELIABILITY_SCALE_THRESHOLDS = [
    (500, 1.0),  # visits >= 500: full weight
    (200, 0.8),  # visits >= 200: 80%
    (100, 0.5),  # visits >= 100: 50%
    (0, 0.3),  # visits < 100: 30%
]


@dataclass
class ReliabilityStats:
    """Data Quality / Reliability statistics for a set of moves."""

    total_moves: int = 0
    reliable_count: int = 0
    low_confidence_count: int = 0
    zero_visits_count: int = 0
    total_visits: int = 0
    moves_with_visits: int = 0
    max_visits: int = 0
    effective_threshold: int = RELIABILITY_VISITS_THRESHOLD  # Phase 44: for display

    @property
    def reliability_pct(self) -> float:
        """Percentage of analyzed moves that are reliable."""
        if self.moves_with_visits == 0:
            return 0.0
        return 100.0 * self.reliable_count / self.moves_with_visits

    @property
    def coverage_pct(self) -> float:
        """Percentage of total moves that have valid analysis."""
        if self.total_moves == 0:
            return 0.0
        return 100.0 * self.moves_with_visits / self.total_moves

    @property
    def low_confidence_pct(self) -> float:
        """Percentage of moves that are low confidence."""
        if self.total_moves == 0:
            return 0.0
        return 100.0 * self.low_confidence_count / self.total_moves

    @property
    def avg_visits(self) -> float:
        """Average visits for moves that have valid visits."""
        if self.moves_with_visits == 0:
            return 0.0
        return self.total_visits / self.moves_with_visits

    @property
    def is_low_reliability(self) -> bool:
        """True if reliability percentage is below 20%."""
        return self.reliability_pct < 20.0


# Constants for confidence level computation
MIN_COVERAGE_MOVES = 5

_CONFIDENCE_THRESHOLDS = {
    "high_reliability_pct": 50.0,
    "high_avg_visits": 400,
    "medium_reliability_pct": 30.0,
    "medium_avg_visits": 150,
}
