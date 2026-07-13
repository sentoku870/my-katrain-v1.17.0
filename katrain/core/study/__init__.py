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
from katrain.core.study.kifunarabe import (
    MIN_CANDIDATE_VISITS,
    SIDE_BLACK,
    SIDE_BOTH,
    SIDE_WHITE,
    VALID_HINT_COUNTS,
    VALID_TURNS,
    GuessOutcome,
    KifunarabeConfig,
    KifunarabeGuessResult,
    KifunarabeSession,
    KifunarabeSummary,
    build_kifunarabe_options,
    evaluate_guess,
    get_hint_candidates,
    should_auto_advance,
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
    # kifunarabe (棋譜並べ)
    "MIN_CANDIDATE_VISITS",
    "SIDE_BLACK",
    "SIDE_BOTH",
    "SIDE_WHITE",
    "VALID_HINT_COUNTS",
    "VALID_TURNS",
    "GuessOutcome",
    "KifunarabeConfig",
    "KifunarabeGuessResult",
    "KifunarabeSession",
    "KifunarabeSummary",
    "build_kifunarabe_options",
    "evaluate_guess",
    "get_hint_candidates",
    "should_auto_advance",
]
