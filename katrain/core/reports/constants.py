"""Constants for Report and Summary features.

This module contains constants used in report generation, including
thresholds for mistake classification, urgent miss detection, and
confidence levels.

Note: RELIABILITY_VISITS_THRESHOLD was moved to
katrain.core.analysis.models.reliability (single source of truth,
Phase 149 A-4).
"""

from enum import Enum
from typing import Final

# --- Game Phases (Phase B-5) ---
# Internal canonical phase keys. JSON serialization uses the
# ``.value`` (string) for backward compatibility with existing
# consumer code; new code should prefer the enum members directly.

_GAME_PHASE_OPENING = "opening"
_GAME_PHASE_MIDDLE = "middle"
_GAME_PHASE_YOSE = "yose"  # alias for the public-facing "endgame" string
_GAME_PHASE_UNKNOWN = "unknown"


class GamePhase(Enum):
    """Game phase buckets used for loss / move aggregation.

    The string values are the canonical JSON keys (matching the
    historical literals in ``summary_logic.phase_moves`` etc.) so
    that ``phase_moves[GamePhase.OPENING]`` round-trips through
    JSON without any transformation. UI code may translate the
    values to user-visible labels via the i18n system; the value
    itself is the public contract.
    """

    OPENING = _GAME_PHASE_OPENING
    MIDDLE = _GAME_PHASE_MIDDLE
    YOSE = _GAME_PHASE_YOSE
    UNKNOWN = _GAME_PHASE_UNKNOWN

    @classmethod
    def from_tag(cls, tag: str | None) -> "GamePhase":
        """Map a ``Move.tag`` string to a :class:`GamePhase`.

        Unknown / empty tags fall back to :attr:`UNKNOWN`. The
        ``"endgame"`` alias is normalised to :attr:`YOSE` so the
        four buckets match what ``summary_logic.py`` aggregates.
        """
        if not tag:
            return cls.UNKNOWN
        normalized = tag.strip().lower()
        # Treat both "yose" (internal) and "endgame" (PHASES constant)
        # as the same bucket. Other phase values (e.g. "fuseki") fall
        # through to UNKNOWN so the bucket count stays at 4.
        if normalized in (_GAME_PHASE_YOSE, "endgame"):
            return cls.YOSE
        for member in cls:
            if member.value == normalized:
                return member
        return cls.UNKNOWN


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
