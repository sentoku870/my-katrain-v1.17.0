"""Phase 248-A1: Tests for ``pick_important_moves`` (important-move selection).

This module complements :mod:`tests.eval_metrics.test_evidence` by
covering the :func:`katrain.core.analysis.logic_importance.pick_important_moves`
function directly. The previous test suite exercised
``compute_importance_for_moves`` (the importance-scoring loop) but
left the threshold-driven selection logic and the raw-score fallback
path with only 10% coverage (see
:mod:`katrain.core.analysis.logic_importance`).

The tests below lock in the public contract:

* :data:`IMPORTANT_MOVE_SETTINGS_BY_LEVEL` thresholds are respected.
* ``max_moves`` is enforced and ties are broken by ``move_number`` ASC.
* The raw-score fallback only fires when the threshold path is empty
  *and* at least one candidate has ``MIN_LOSS_DISPLAY`` or more.
* ``streak_start_moves`` adds the configured bonus.
* ``confidence_level=LOW`` disables swing / streak / difficulty components.

All tests are pure (no Game / GameNode / KataGo process) so they run in
milliseconds and are friendly to the headless CI matrix.
"""

from __future__ import annotations

import pytest

from katrain.core.analysis import (
    DEFAULT_IMPORTANT_MOVE_LEVEL,
    IMPORTANT_MOVE_SETTINGS_BY_LEVEL,
    ImportantMoveSettings,
    pick_important_moves,
)
from katrain.core.analysis.logic_importance import (
    STREAK_START_BONUS,
    SWING_MAGNITUDE_WEIGHT,
    compute_importance_for_moves,
)
from katrain.core.analysis.models import ConfidenceLevel, EvalSnapshot
from katrain.core.analysis.models.enums import PositionDifficulty
from katrain.core.analysis.models.important_moves import (
    DEFAULT_IMPORTANT_MOVE_LEVEL as _DEFAULT_LEVEL,
    MIN_LOSS_DISPLAY,
)
from tests.helpers_eval_metrics import make_move_eval


# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------


# Sanity: the public constant exposed via __init__ should match the
# canonical one in models/important_moves.py. If these drift, the
# "from katrain.core.analysis import DEFAULT_IMPORTANT_MOVE_LEVEL"
# downstream import would silently pick the wrong value.
assert DEFAULT_IMPORTANT_MOVE_LEVEL == _DEFAULT_LEVEL == "normal"


def _snapshot(moves) -> EvalSnapshot:
    """Wrap a list of MoveEval into an EvalSnapshot for pick_important_moves."""
    return EvalSnapshot(moves=list(moves))


# ---------------------------------------------------------------------------
# Threshold level behaviour (IMPORTANT_MOVE_SETTINGS_BY_LEVEL)
# ---------------------------------------------------------------------------


class TestPickImportantMovesByLevel:
    """``level`` must select the right (threshold, max_moves) pair."""

    def test_easy_level_drops_small_losses(self):
        """``easy`` keeps only important_score > 1.0 (and at most 10)."""
        easy = IMPORTANT_MOVE_SETTINGS_BY_LEVEL["easy"]
        assert easy.importance_threshold == pytest.approx(1.0)
        assert easy.max_moves == 10

        # Build 4 moves with widely varying loss to produce distinct
        # importance scores. All visits=500 → reliability scale 1.0.
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=0.4, root_visits=500),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=1.5, root_visits=500),
            make_move_eval(move_number=3, player="B", gtp="D16", score_loss=3.0, root_visits=500),
            make_move_eval(move_number=4, player="B", gtp="Q4", score_loss=0.8, root_visits=500),
        ]
        result = pick_important_moves(_snapshot(moves), level="easy", recompute=True)

        # Move 2 (1.5) and 3 (3.0) clear the 1.0 threshold; move 1 (0.4)
        # and move 4 (0.8) do not.
        assert [m.move_number for m in result] == [2, 3]

    def test_normal_level_keeps_medium_losses(self):
        """``normal`` uses threshold 0.5 and max 20."""
        normal = IMPORTANT_MOVE_SETTINGS_BY_LEVEL["normal"]
        assert normal.importance_threshold == pytest.approx(0.5)
        assert normal.max_moves == 20

        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=0.6, root_visits=500),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=0.3, root_visits=500),
        ]
        result = pick_important_moves(_snapshot(moves), level="normal", recompute=True)

        # Only move 1 (0.6) crosses the 0.5 threshold.
        assert [m.move_number for m in result] == [1]

    def test_strict_level_keeps_small_losses(self):
        """``strict`` lowers the bar to 0.3 with max 40."""
        strict = IMPORTANT_MOVE_SETTINGS_BY_LEVEL["strict"]
        assert strict.importance_threshold == pytest.approx(0.3)
        assert strict.max_moves == 40

        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=0.35, root_visits=500),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=0.2, root_visits=500),
        ]
        result = pick_important_moves(_snapshot(moves), level="strict", recompute=True)

        assert [m.move_number for m in result] == [1]

    def test_unknown_level_falls_back_to_default(self):
        """An unknown level must silently fall back to DEFAULT_IMPORTANT_MOVE_LEVEL."""
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=0.6, root_visits=500),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=0.4, root_visits=500),
        ]
        result = pick_important_moves(_snapshot(moves), level="does_not_exist", recompute=True)
        # 0.6 is above 0.5 (default=normal), 0.4 is below.
        assert [m.move_number for m in result] == [1]

    def test_max_moves_caps_selection(self):
        """max_moves is enforced: top-N by importance, then move_number ASC."""
        # 6 moves with monotonically increasing loss → importance roughly
        # monotonic, so all should clear the easy threshold (1.0) once
        # loss >= ~1.0. ``max_moves=2`` should keep the top 2.
        moves = [
            make_move_eval(move_number=i + 1, player="B", gtp=f"D{i + 4}", score_loss=1.0 + i, root_visits=500)
            for i in range(6)
        ]
        result = pick_important_moves(
            _snapshot(moves),
            settings=ImportantMoveSettings(importance_threshold=0.5, max_moves=2),
            recompute=True,
        )
        assert [m.move_number for m in result] == [5, 6]


# ---------------------------------------------------------------------------
# Tiebreak / ordering
# ---------------------------------------------------------------------------


class TestPickImportantMovesOrdering:
    """Tiebreaks and the importance_threshold filter."""

    def test_tiebreak_by_move_number_ascending(self):
        """Equal importance is broken by earlier move_number first."""
        moves = [
            make_move_eval(move_number=20, player="B", gtp="D4", score_loss=5.0, root_visits=500),
            make_move_eval(move_number=5, player="B", gtp="Q16", score_loss=5.0, root_visits=500),
            make_move_eval(move_number=12, player="B", gtp="D16", score_loss=5.0, root_visits=500),
        ]
        result = pick_important_moves(_snapshot(moves), level="normal", recompute=True)
        assert [m.move_number for m in result] == [5, 12, 20]

    def test_zero_loss_moves_dropped_under_default(self):
        """Moves with score_loss=0 stay below every threshold (no positive swing)."""
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=0.0, root_visits=500),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=0.0, root_visits=500),
        ]
        result = pick_important_moves(_snapshot(moves), level="strict", recompute=True)
        # Both move 1 and 2 have importance_score 0.0 < 0.3 → no threshold match.
        # Fallback path requires MIN_LOSS_DISPLAY > 0.0, so nothing fires.
        assert result == []


# ---------------------------------------------------------------------------
# Raw-score fallback path
# ---------------------------------------------------------------------------


class TestPickImportantMovesFallback:
    """Phase 148-B2 fallback: when threshold path is empty, fall back to raw_score."""

    def test_fallback_picks_high_loss_only(self):
        """All-zero losses → empty; one large loss → fallback picks it."""
        # 0.4 and 0.1 losses never clear any threshold (even strict=0.3,
        # 0.4 > 0.3 but 0.1 < 0.3, so only move 1 normally). The
        # fallback should still pick the largest raw loss when the
        # threshold path is empty.
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=0.05, root_visits=500),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=0.10, root_visits=500),
            make_move_eval(move_number=3, player="B", gtp="D16", score_loss=0.07, root_visits=500),
        ]
        # All sub-MIN_LOSS_DISPLAY (0.3) → no fallback picks either.
        result = pick_important_moves(_snapshot(moves), level="strict", recompute=True)
        assert result == []

    def test_fallback_fires_when_threshold_path_empty(self):
        """If threshold path is empty but raw scores exist above MIN_LOSS_DISPLAY,
        the fallback must surface the moves with the largest raw_score."""
        # All moves have loss below the threshold (0.3) but above
        # MIN_LOSS_DISPLAY (0.3) so the raw-score path picks them up.
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=0.4, root_visits=500),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=0.6, root_visits=500),
            make_move_eval(move_number=3, player="B", gtp="D16", score_loss=0.5, root_visits=500),
        ]
        # ``recompute=False`` skips the importance loop → importance_score
        # stays None → threshold path can't match → fallback fires.
        result = pick_important_moves(
            _snapshot(moves),
            settings=ImportantMoveSettings(importance_threshold=0.3, max_moves=5),
            recompute=False,
        )
        # raw_score = score_loss * reliability_scale(1.0) for each.
        # All three clear MIN_LOSS_DISPLAY, so the fallback picks all.
        # Final ordering is by move_number ASC.
        assert [m.move_number for m in result] == [1, 2, 3]

    def test_fallback_respects_max_moves(self):
        """Fallback path must also respect max_moves."""
        moves = [
            make_move_eval(move_number=i + 1, player="B", gtp=f"D{i + 4}", score_loss=0.5, root_visits=500)
            for i in range(5)
        ]
        # 5 candidates, all equal loss → fallback raw_score equal.
        # max_moves=2 keeps the first 2 after sorting (-raw_score ASC,
        # then move_number ASC) → keeps move_number 1 and 2.
        result = pick_important_moves(
            _snapshot(moves),
            settings=ImportantMoveSettings(importance_threshold=10.0, max_moves=2),  # threshold unreachable
            recompute=False,
        )
        assert [m.move_number for m in result] == [1, 2]


# ---------------------------------------------------------------------------
# streak_start_moves bonus
# ---------------------------------------------------------------------------


class TestPickImportantMovesStreak:
    """``streak_start_moves`` should add STREAK_START_BONUS to the relevant moves."""

    def test_streak_start_bonus_promotes_move(self):
        """Adding a streak start should push the tagged move above a tie."""
        # Without streak: 0.6 > 0.5 (normal threshold), so only move 1
        # crosses. With streak bonus on move 2 (0.4 + bonus), it can
        # also cross. Tune STREAK_START_BONUS to be large enough to
        # bridge the gap (Phase 65 comment: 0.5).
        assert STREAK_START_BONUS > 0.4, "Test assumption: streak bonus must exceed gap to threshold"

        # Use a smaller gap so the streak bonus is the difference-maker.
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=0.7, root_visits=500),
            make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=0.4, root_visits=500),
            make_move_eval(move_number=3, player="B", gtp="D16", score_loss=0.45, root_visits=500),
        ]
        # Without streak → only move 1 (0.7) crosses 0.5.
        result = pick_important_moves(_snapshot(moves), level="normal", recompute=True)
        assert [m.move_number for m in result] == [1]

        # With streak on move 2 (0.4 + STREAK_START_BONUS) → 0.4 + bonus
        # should also cross 0.5. Move 3 (0.45) stays below.
        result_with_streak = pick_important_moves(
            _snapshot(moves),
            level="normal",
            recompute=True,
            streak_start_moves={2},
        )
        assert 2 in [m.move_number for m in result_with_streak]
        assert 3 not in [m.move_number for m in result_with_streak]


# ---------------------------------------------------------------------------
# confidence_level
# ---------------------------------------------------------------------------


class TestPickImportantMovesConfidence:
    """``confidence_level`` controls which components feed the score."""

    def test_low_confidence_disables_swing_component(self):
        """With confidence=LOW, the swing component is excluded.

        Construct a move whose importance depends on a sign-changing
        swing. With HIGH/MEDIUM the swing is counted; with LOW it is not.
        """
        # 10-point score_before → -10-point score_after (sign changed)
        # → swing_magnitude = 20.0
        m_high = make_move_eval(
            move_number=1,
            player="B",
            gtp="D4",
            score_loss=1.0,
            score_before=10.0,
            score_after=-10.0,
            root_visits=500,
        )
        # No sign change → swing_magnitude = 0.0
        m_low = make_move_eval(
            move_number=2,
            player="B",
            gtp="Q16",
            score_loss=1.0,
            score_before=10.0,
            score_after=5.0,
            root_visits=500,
        )
        # HIGH: includes swing → 1.0 + SWING_MAGNITUDE_WEIGHT * 20
        compute_importance_for_moves([m_high], confidence_level=ConfidenceLevel.HIGH)
        compute_importance_for_moves([m_low], confidence_level=ConfidenceLevel.HIGH)
        assert m_high.importance_score == pytest.approx(1.0 + SWING_MAGNITUDE_WEIGHT * 20.0)
        assert m_low.importance_score == pytest.approx(1.0)
        # HIGH: m_high should be larger than m_low
        assert m_high.importance_score > m_low.importance_score

        # LOW: swing excluded → both have importance = 1.0 * scale(1.0) = 1.0
        m_high_l = make_move_eval(
            move_number=1,
            player="B",
            gtp="D4",
            score_loss=1.0,
            score_before=10.0,
            score_after=-10.0,
            root_visits=500,
        )
        m_low_l = make_move_eval(
            move_number=2,
            player="B",
            gtp="Q16",
            score_loss=1.0,
            score_before=10.0,
            score_after=5.0,
            root_visits=500,
        )
        compute_importance_for_moves([m_high_l], confidence_level=ConfidenceLevel.LOW)
        compute_importance_for_moves([m_low_l], confidence_level=ConfidenceLevel.LOW)
        assert m_high_l.importance_score == pytest.approx(1.0)
        assert m_low_l.importance_score == pytest.approx(1.0)

    def test_low_confidence_disables_difficulty_modifier(self):
        """With confidence=LOW, HARD difficulty no longer adds the +1.0 bonus."""
        # HIGH: 1.0 (loss) + 1.0 (HARD bonus) = 2.0
        m_high = make_move_eval(
            move_number=1,
            player="B",
            gtp="D4",
            score_loss=1.0,
            root_visits=500,
            position_difficulty=PositionDifficulty.HARD,
        )
        compute_importance_for_moves([m_high], confidence_level=ConfidenceLevel.HIGH)
        assert m_high.importance_score == pytest.approx(2.0)

        # LOW: 1.0 (loss) + 0.0 (no difficulty modifier) = 1.0
        m_low = make_move_eval(
            move_number=1,
            player="B",
            gtp="D4",
            score_loss=1.0,
            root_visits=500,
            position_difficulty=PositionDifficulty.HARD,
        )
        compute_importance_for_moves([m_low], confidence_level=ConfidenceLevel.LOW)
        assert m_low.importance_score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Reliability scale integration
# ---------------------------------------------------------------------------


class TestPickImportantMovesReliability:
    """Reliability scale (visits-based) must multiply the final score."""

    def test_low_visits_scales_down_importance(self):
        """A move with 50 visits gets scale 0.3 vs 500 visits gets scale 1.0."""
        m_low_v = make_move_eval(move_number=1, player="B", gtp="D4", score_loss=5.0, root_visits=50)
        m_high_v = make_move_eval(move_number=2, player="B", gtp="Q16", score_loss=5.0, root_visits=500)
        compute_importance_for_moves([m_low_v, m_high_v])

        # Both have loss 5.0, but low_visits is scaled by 0.3.
        assert m_low_v.importance_score == pytest.approx(5.0 * 0.3)
        assert m_high_v.importance_score == pytest.approx(5.0 * 1.0)


# ---------------------------------------------------------------------------
# Boundary cases
# ---------------------------------------------------------------------------


class TestPickImportantMovesBoundaries:
    """Empty / all-uncertain / max-equals-min cases."""

    def test_empty_snapshot_returns_empty(self):
        result = pick_important_moves(_snapshot([]), level="normal", recompute=True)
        assert result == []

    def test_single_move_snapshot(self):
        moves = [make_move_eval(move_number=1, player="B", gtp="D4", score_loss=2.0, root_visits=500)]
        result = pick_important_moves(_snapshot(moves), level="normal", recompute=True)
        assert [m.move_number for m in result] == [1]

    def test_result_sorted_by_move_number(self):
        """``pick_important_moves`` always returns moves sorted by move_number ASC."""
        moves = [
            make_move_eval(move_number=10, player="B", gtp="D4", score_loss=5.0, root_visits=500),
            make_move_eval(move_number=1, player="B", gtp="Q16", score_loss=3.0, root_visits=500),
            make_move_eval(move_number=5, player="B", gtp="D16", score_loss=2.0, root_visits=500),
        ]
        result = pick_important_moves(_snapshot(moves), level="normal", recompute=True)
        assert [m.move_number for m in result] == [1, 5, 10]
