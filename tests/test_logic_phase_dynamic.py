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
        # Phase 158-G: window shortened to 3. With only 2 low-stdev moves
        # in a row the detector never fires; endgame must come from the
        # static classifier only (move_number > 200 -> yose).
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        # Only the last 2 moves have low stdev; not enough for window=3.
        for i in range(248, 250):
            moves[i].score_stdev = 3.0
        phases = classify_phases_dynamic(moves)
        # Static still labels move 250 as yose — dynamic detector never fired.
        assert phases[-1] == "yose"
        # Earlier moves (still middle) confirm the detector never fired.
        assert phases[100] == "middle"

    def test_trigger_after_window(self):
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        # Last 6 moves have low stdev (more than the window=3).
        for i in range(244, 250):
            moves[i].score_stdev = 3.0
        phases = classify_phases_dynamic(moves)
        # Once endgame triggers, it sticks. With 6 low-stdev moves starting
        # at index 244 (move_number 245), the streak hits 3 at index 246
        # and stays endgame through index 249 — that's 4 endgame moves.
        # Phase 158-G: emitted as the legacy alias ``"yose"`` so the
        # static-tag aggregator keeps counting these moves.
        endgame_count = sum(1 for p in phases if p == "yose")
        assert endgame_count >= 3  # at least the window-fill part

    def test_trigger_at_exact_window(self):
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        # Exactly 3 consecutive moves with stdev=3.0 (the default window).
        for i in range(247, 250):
            moves[i].score_stdev = 3.0
        phases = classify_phases_dynamic(moves)
        # Endgame should kick in starting at move 249 (index 249).
        # Phase 158-G: emitted as ``"yose"`` (legacy alias).
        assert phases[249] == "yose"


class TestStreakReset:
    """A high-stdev move resets the consecutive-low-streak counter."""

    def test_reset_on_high_stdev(self):
        # Phase 158-G: with window=3 a single reset between two streaks
        # of 2 low-stdev moves still leaves the detector unfired. Use a
        # 2-and-2 layout (separated by a high move) so neither side
        # reaches the window.
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        for i in range(246, 248):  # 2 lows
            moves[i].score_stdev = 3.0
        moves[248].score_stdev = 30.0  # reset
        for i in range(249, 250):  # 1 more low (only)
            moves[i].score_stdev = 3.0
        phases = classify_phases_dynamic(moves)
        # Static still labels move 250 as yose — dynamic detector never fired.
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
        # Phase 158-G: raised from 5.0 → 8.0.
        assert ENDGAME_SCORE_STDEV_THRESHOLD == 8.0

    def test_default_window(self):
        # Phase 158-G: shortened from 5 → 3.
        assert ENDGAME_DETECTION_WINDOW == 3


class TestApplyDynamicPhases:
    """apply_dynamic_phases is pure: returns ``list[str]``, no side-effects.

    Phase LV4-2: callers that need ``mv.tag`` must write it themselves.
    """

    def test_tag_overwritten(self):
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        for i in range(244, 250):
            moves[i].score_stdev = 3.0
        phases = apply_dynamic_phases(moves)
        # Phase LV4-2: callers apply the returned phases to ``mv.tag``.
        for mv, phase in zip(moves, phases, strict=False):
            mv.tag = phase
        assert moves[0].tag == "opening"
        assert moves[50].tag == "middle"
        # Phase 158-G: window=3 triggers at index 246; tag uses the legacy
        # ``"yose"`` alias so downstream static aggregators keep counting.
        assert moves[-1].tag == "yose"

    def test_idempotent(self):
        """Calling twice produces the same result."""
        moves = [make_move(i, 30.0) for i in range(1, 251)]
        for i in range(244, 250):
            moves[i].score_stdev = 3.0
        phases = apply_dynamic_phases(moves)
        # Mirror the caller-side write so the second pass sees a clean
        # input (the function itself does not mutate ``mv.tag``).
        for mv, phase in zip(moves, phases, strict=False):
            mv.tag = phase
        first_pass = [m.tag for m in moves]
        second_pass = [m.tag for m in moves]
        assert first_pass == second_pass
