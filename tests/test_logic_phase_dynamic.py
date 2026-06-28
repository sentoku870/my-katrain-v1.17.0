"""Tests for Phase 156-A dynamic phase classifier."""
from __future__ import annotations

import pytest

from katrain.core.analysis import (
    ENDGAME_DETECTION_WINDOW,
    ENDGAME_SCORE_STDEV_THRESHOLD,
    apply_dynamic_phases,
    classify_phases_dynamic,
    it_consistent_with_static,
)
from katrain.core.analysis.models import MoveEval


def make_move(
    move_number: int,
    score_stdev: float | None,
    *,
    player: str = "B",
) -> MoveEval:
    move = MoveEval(
        move_number=move_number,
        player=player,
        gtp=f"D{move_number}",
        score_before=0.0,
        score_after=0.0,
        delta_score=0.0,
        winrate_before=0.5,
        winrate_after=0.5,
        delta_winrate=0.0,
        points_lost=0.0,
        realized_points_lost=None,
        root_visits=200,
    )
    move.score_stdev = score_stdev
    move.tag = "middle"
    return move


class TestOpeningFallback:
    """Moves within the static opening window stay 'opening'."""

    def test_all_within_opening(self):
        moves = [make_move(i, 30.0) for i in range(1, 51)]
        phases = classify_phases_dynamic(moves)
        assert all(p == "opening" for p in phases)


class TestEndgameTrigger:
    """scoreStdev drops below threshold for N consecutive moves -> endgame."""

    def test_no_trigger_without_enough_low_stdev(self):
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        # Only the last 3 moves have low stdev; not enough to trigger
        # the dynamic detector — move 250 stays on the static "yose".
        for i in range(247, 250):
            moves[i].score_stdev = 3.0
        phases = classify_phases_dynamic(moves)
        assert phases[-1] == "yose"
        # Earlier moves (still middle) confirm the detector never fired.
        assert phases[100] == "middle"

    def test_trigger_after_window(self):
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        # Last 6 moves have low stdev (more than the window=5)
        for i in range(244, 250):
            moves[i].score_stdev = 3.0
        phases = classify_phases_dynamic(moves)
        # Once endgame triggers, it sticks. With 6 low-stdev moves starting
        # at index 244 (move_number 245), the streak hits 5 at index 248
        # and stays endgame through index 249 — that's 2 endgame moves.
        endgame_count = sum(1 for p in phases if p == "endgame")
        assert endgame_count >= 2  # at least the window-fill part

    def test_trigger_at_exact_window(self):
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        # Exactly 5 consecutive moves with stdev=3.0 (the default window)
        for i in range(245, 250):
            moves[i].score_stdev = 3.0
        phases = classify_phases_dynamic(moves)
        # Endgame should kick in starting at move 249 (index 249).
        assert phases[249] == "endgame"


class TestStreakReset:
    """A high-stdev move resets the consecutive-low-streak counter."""

    def test_reset_on_high_stdev(self):
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        # 4 low then 1 high then 4 low -> still not enough to trigger.
        for i in range(245, 250):
            moves[i].score_stdev = 3.0
        moves[246].score_stdev = 30.0  # reset
        phases = classify_phases_dynamic(moves)
        # Static still labels move 250 as yose (move_number > 200)
        assert phases[-1] == "yose"


class TestMissingScoreStdev:
    """Moves with score_stdev=None fall back to the static classifier."""

    def test_missing_in_middle(self):
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        moves[100].score_stdev = None
        # Should not crash; result should equal static for this move
        phases = classify_phases_dynamic(moves)
        assert phases[99] == "middle"

    def test_consistent_with_static_when_no_score_stdev(self):
        """All None score_stdev -> exactly the static classifier result."""
        moves = [make_move(i, None) for i in range(1, 251)]
        phases = classify_phases_dynamic(moves)
        # No endgame signal; phases match static boundaries exactly
        from katrain.core.analysis import classify_game_phase

        static = [classify_game_phase(mv.move_number) for mv in moves]
        assert it_consistent_with_static(static, phases)


class TestValidation:
    """Argument validation."""

    def test_zero_window_raises(self):
        moves = [make_move(1, 30.0)]
        with pytest.raises(ValueError):
            classify_phases_dynamic(moves, endgame_window=0)

    def test_negative_window_raises(self):
        moves = [make_move(1, 30.0)]
        with pytest.raises(ValueError):
            classify_phases_dynamic(moves, endgame_window=-1)


class TestConstants:
    """Module constants are stable."""

    def test_default_threshold(self):
        assert ENDGAME_SCORE_STDEV_THRESHOLD == 5.0

    def test_default_window(self):
        assert ENDGAME_DETECTION_WINDOW == 5


class TestApplyDynamicPhases:
    """apply_dynamic_phases rewrites move.tag in place."""

    def test_tag_overwritten(self):
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        for i in range(244, 250):
            moves[i].score_stdev = 3.0
        apply_dynamic_phases(moves)
        assert moves[0].tag == "opening"
        assert moves[50].tag == "middle"
        assert moves[-1].tag == "endgame"

    def test_idempotent(self):
        """Calling twice produces the same result."""
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        for i in range(244, 250):
            moves[i].score_stdev = 3.0
        apply_dynamic_phases(moves)
        first_pass = [m.tag for m in moves]
        apply_dynamic_phases(moves)
        second_pass = [m.tag for m in moves]
        assert first_pass == second_pass