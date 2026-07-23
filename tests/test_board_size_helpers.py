"""Tests for Phase 252: board-size-aware threshold helpers.

Covers:

- :func:`min_reliable_visits_for_board_size` (9x9 → 100, 13x13 → 150, 19x19 → 200)
- :func:`endgame_move_threshold_for_board_size` (9x9 → 60, 13x13 → 100, 19x19 → 200)
- :func:`min_loss_display_for_board_size` (9x9 → 0.15, 13x13 → 0.2, 19x19 → 0.3)
- Integration check that ``logic_importance.pick_important_moves`` honours
  the board-size-aware threshold via the fallback path (no
  ``importance_score``).

All three helpers share a common shape: ``board_size`` int or ``(w, h)``
tuple in, scalar threshold out, fall back to the 19x19 default for
unknown sizes.

Phase 3 of the test-suite audit merged
``test_phase252_board_size_helpers.py`` and
``test_phase252_logic_importance_integration.py`` since the integration
test exercises the same board-size-aware helpers in a slightly larger
context.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from katrain.core.analysis.models.enums import PositionDifficulty
from katrain.core.analysis.models.important_moves import min_loss_display_for_board_size
from katrain.core.analysis.models.move_eval import MoveEval
from katrain.core.beginner.hints._extract import endgame_move_threshold_for_board_size
from katrain.core.beginner.hints._gate import min_reliable_visits_for_board_size


class TestMinReliableVisitsForBoardSize:
    """Phase 252 I-5: 9x9 → 100, 13x13 → 150, 19x19 → 200."""

    def test_19x19_default(self):
        assert min_reliable_visits_for_board_size(19) == 200

    def test_13x13_scaled(self):
        assert min_reliable_visits_for_board_size(13) == 150

    def test_9x9_scaled(self):
        assert min_reliable_visits_for_board_size(9) == 100

    def test_none_falls_back_to_19x19(self):
        assert min_reliable_visits_for_board_size(None) == 200

    def test_tuple_falls_back_to_min_side(self):
        assert min_reliable_visits_for_board_size((9, 19)) == 100  # min(9, 19)
        assert min_reliable_visits_for_board_size((13, 13)) == 150
        assert min_reliable_visits_for_board_size((19, 19)) == 200

    def test_unknown_size_falls_back_to_19x19(self):
        assert min_reliable_visits_for_board_size(25) == 200  # 25x25 not in table
        assert min_reliable_visits_for_board_size(7) == 200  # 7x7 not in table
        assert min_reliable_visits_for_board_size(0) == 200  # 0x0 not in table

    def test_garbage_input_falls_back(self):
        # Non-numeric input → falls back to 19x19 default.
        assert min_reliable_visits_for_board_size("nope") == 200  # type: ignore[arg-type]
        # The function takes ``min`` of the first two elements when
        # they convert cleanly — ``[9, 19, "x"]`` therefore resolves
        # to size 9 (the min of the two ints) and yields the 9x9
        # threshold 100. That's a feature, not a bug: trailing junk
        # is ignored, the leading two ints are the authoritative
        # size hint.
        assert min_reliable_visits_for_board_size([9, 19, "x"]) == 100  # type: ignore[list-item]

    def test_empty_tuple_falls_back(self):
        assert min_reliable_visits_for_board_size(()) == 200


class TestEndgameMoveThresholdForBoardSize:
    """Phase 252 I-6: 9x9 → 60, 13x13 → 100, 19x19 → 200."""

    def test_19x19_default(self):
        assert endgame_move_threshold_for_board_size(19) == 200

    def test_13x13_scaled(self):
        assert endgame_move_threshold_for_board_size(13) == 100

    def test_9x9_scaled(self):
        assert endgame_move_threshold_for_board_size(9) == 60

    def test_none_falls_back_to_19x19(self):
        assert endgame_move_threshold_for_board_size(None) == 200

    def test_tuple_falls_back_to_min_side(self):
        assert endgame_move_threshold_for_board_size((9, 19)) == 60
        assert endgame_move_threshold_for_board_size((13, 13)) == 100
        assert endgame_move_threshold_for_board_size((19, 19)) == 200

    def test_unknown_size_falls_back(self):
        assert endgame_move_threshold_for_board_size(25) == 200
        assert endgame_move_threshold_for_board_size(7) == 200


class TestMinLossDisplayForBoardSize:
    """Phase 252 I-7: 9x9 → 0.15, 13x13 → 0.2, 19x19 → 0.3."""

    def test_19x19_default(self):
        assert min_loss_display_for_board_size(19) == pytest.approx(0.3)

    def test_13x13_scaled(self):
        assert min_loss_display_for_board_size(13) == pytest.approx(0.2)

    def test_9x9_scaled(self):
        assert min_loss_display_for_board_size(9) == pytest.approx(0.15)

    def test_none_falls_back(self):
        assert min_loss_display_for_board_size(None) == pytest.approx(0.3)

    def test_tuple_falls_back_to_min_side(self):
        assert min_loss_display_for_board_size((9, 19)) == pytest.approx(0.15)
        assert min_loss_display_for_board_size((13, 13)) == pytest.approx(0.2)
        assert min_loss_display_for_board_size((19, 19)) == pytest.approx(0.3)

    def test_unknown_size_falls_back(self):
        assert min_loss_display_for_board_size(25) == pytest.approx(0.3)
        assert min_loss_display_for_board_size(7) == pytest.approx(0.3)

    def test_strictly_smaller_for_smaller_boards(self):
        """Sanity: 9x9 threshold < 13x13 < 19x19."""
        assert (
            min_loss_display_for_board_size(9)
            < min_loss_display_for_board_size(13)
            < min_loss_display_for_board_size(19)
        )


# ---------------------------------------------------------------------------
# Integration: pick_important_moves uses min_loss_display_for_board_size
# ---------------------------------------------------------------------------


def _move(move_number: int, score_loss: float, root_visits: int = 500) -> MoveEval:
    """Tiny MoveEval factory: no importance_score, so fallback is used.

    root_visits defaults to 500 (full reliability) so the raw_score
    multiplier is 1.0 and the threshold comparison is unambiguous.
    """
    return MoveEval(
        move_number=move_number,
        player="B",
        gtp="D4",
        score_before=0.0,
        score_after=0.0,
        delta_score=0.0,
        winrate_before=0.5,
        winrate_after=0.5,
        delta_winrate=0.0,
        points_lost=score_loss,
        realized_points_lost=score_loss,
        root_visits=root_visits,
        is_reliable=True,
        importance_score=None,
        score_loss=score_loss,
        position_difficulty=PositionDifficulty.UNKNOWN,
    )


class _GameStub:
    """Stub: only board_size is read by logic_importance.pick_important_moves."""

    def __init__(self, board_size):
        self.board_size = board_size
        # Each move's parent points at this game so the
        # board_size lookup works the same as in production.


def _wire_parents(moves, game):
    for m in moves:
        m.parent = SimpleNamespace(game=game)
    return moves


class TestPickImportantMovesBoardSizeFallback:
    """The fallback path uses the board-size-aware threshold."""

    def test_pick_important_moves_9x9_fallback_threshold(self):
        """9x9 game: a 0.2-point loss (above 0.15, below 0.3) is selected."""
        from katrain.core.analysis import logic_importance

        # Snapshot 5 moves with score_loss in [0.05, 0.4]. None have an
        # importance_score, so the fallback raw-score path is used.
        moves = [
            _move(1, 0.05),
            _move(2, 0.10),
            _move(3, 0.20),  # 0.20 > 0.15 (9x9), < 0.3 (19x19) — key test
            _move(4, 0.30),
            _move(5, 0.40),
        ]
        game_9x9 = _GameStub(9)
        _wire_parents(moves, game_9x9)
        snapshot = SimpleNamespace(moves=moves)

        selected = logic_importance.pick_important_moves(snapshot, level="normal", recompute=True)
        selected_nums = sorted(m.move_number for m in selected)

        # 9x9 threshold is 0.15 → moves 3, 4, 5 (score_loss 0.20/0.30/0.40) qualify.
        # Moves 1, 2 fall below 0.15 and are filtered out.
        assert selected_nums == [3, 4, 5], (
            f"9x9 fallback should select 0.2+ losses, got {selected_nums}. "
            "Either min_loss_display_for_board_size is wrong or the wiring is broken."
        )

    def test_pick_important_moves_19x19_fallback_threshold(self):
        """19x19 game: a 0.2-point loss is below the 0.3 threshold and is filtered out."""
        from katrain.core.analysis import logic_importance

        moves = [
            _move(1, 0.05),
            _move(2, 0.10),
            _move(3, 0.20),  # 0.20 < 0.30 → filtered out
            _move(4, 0.30),
            _move(5, 0.40),
        ]
        game_19 = _GameStub(19)
        _wire_parents(moves, game_19)
        snapshot = SimpleNamespace(moves=moves)

        selected = logic_importance.pick_important_moves(snapshot, level="normal", recompute=True)
        selected_nums = sorted(m.move_number for m in selected)

        # 19x19 threshold is 0.3 → only moves 4, 5 qualify.
        assert selected_nums == [4, 5], f"19x19 fallback should filter 0.2-loss moves, got {selected_nums}."

    def test_pick_important_moves_13x13_fallback_threshold(self):
        """13x13 game: threshold is 0.2 — move 3 (0.20) is on the boundary."""
        from katrain.core.analysis import logic_importance

        moves = [
            _move(1, 0.10),
            _move(2, 0.15),  # < 0.20 → filtered
            _move(3, 0.20),  # >= 0.20 → selected
            _move(4, 0.30),
        ]
        game_13 = _GameStub(13)
        _wire_parents(moves, game_13)
        snapshot = SimpleNamespace(moves=moves)

        selected = logic_importance.pick_important_moves(snapshot, level="normal", recompute=True)
        selected_nums = sorted(m.move_number for m in selected)
        assert selected_nums == [3, 4], f"13x13 fallback should select losses >= 0.20, got {selected_nums}."

    def test_pick_important_moves_unknown_board_size_uses_19x19_default(self):
        """No game (board_size=None) → falls back to 0.3 (19x19 default)."""
        from katrain.core.analysis import logic_importance

        moves = [
            _move(1, 0.10),
            _move(2, 0.20),  # < 0.30 → filtered
            _move(3, 0.30),  # >= 0.30 → selected
        ]
        # No parent wiring → board_size ends up None
        snapshot = SimpleNamespace(moves=moves)

        selected = logic_importance.pick_important_moves(snapshot, level="normal", recompute=True)
        selected_nums = sorted(m.move_number for m in selected)
        assert selected_nums == [3], f"No-game fallback should mirror 19x19 (0.30), got {selected_nums}."
