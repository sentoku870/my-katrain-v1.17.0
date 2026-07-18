"""Tests for Phase 252: board-size-aware threshold helpers.

Covers:
- ``min_reliable_visits_for_board_size`` (19x19/13x13/9x9 + fallback)
- ``endgame_move_threshold_for_board_size`` (19x19/13x13/9x9 + fallback)
- ``min_loss_display_for_board_size`` (19x19/13x13/9x9 + fallback)

All three helpers share a common shape: board_size int or (w, h) tuple
in, scalar threshold out, fall back to the 19x19 default for unknown
sizes. They are intentionally written to mirror each other so a test
on one shape can be cross-checked against the others.
"""

from __future__ import annotations

import pytest

from katrain.core.analysis.models.important_moves import min_loss_display_for_board_size
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
