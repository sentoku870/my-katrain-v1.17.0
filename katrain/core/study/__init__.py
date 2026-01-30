# katrain/core/study/__init__.py
"""Active study and review features for KaTrain.

This package contains tools for interactive learning and self-testing
while reviewing game records.
"""

from katrain.core.study.active_review import (
    GRADE_THRESHOLDS,
    MIN_RELIABLE_VISITS,
    ActiveReviewer,
    GuessEvaluation,
    GuessGrade,
    ReviewReadyResult,
    get_hint_for_best_move,
    is_review_ready,
)
from katrain.core.study.review_session import (
    GuessResult,
    ReviewSession,
    SessionSummary,
)

__all__ = [
    "MIN_RELIABLE_VISITS",
    "GRADE_THRESHOLDS",
    "GuessGrade",
    "ReviewReadyResult",
    "GuessEvaluation",
    "is_review_ready",
    "ActiveReviewer",
    # Phase 94 additions
    "GuessResult",
    "SessionSummary",
    "ReviewSession",
    "get_hint_for_best_move",
]
