"""Tests for Leela→MoveEval conversion module.

Phase 31: 31 tests covering conversion logic, winrate perspective,
loss calculation, edge cases, and EvalSnapshot compatibility.
"""

import logging
import pytest

from katrain.core.analysis.models import (
    EvalSnapshot,
    MistakeCategory,
    MoveEval,
)
from katrain.core.leela.models import LeelaCandidate, LeelaPositionEval
from katrain.core.leela.logic import LEELA_K_DEFAULT, LEELA_LOSS_EST_MAX
from katrain.core.leela.conversion import (
    _normalize_move,
    _round_loss_est,
    _convert_to_black_perspective,
    _compute_winrate_loss,
    _compute_leela_loss_for_played_move,
    leela_position_to_move_eval,
    leela_sequence_to_eval_snapshot,
    LEELA_LOSS_EST_EPSILON,
)


# =============================================================================
# Helper functions for creating test data
# =============================================================================


def make_candidate(move: str, eval_pct: float, visits: int = 100) -> LeelaCandidate:
    """Create a LeelaCandidate for testing.

    Args:
        move: GTP coordinate
        eval_pct: Evaluation as percentage (0-100), converted to winrate internally
        visits: Visit count
    """
    return LeelaCandidate(
        move=move,
        winrate=eval_pct / 100.0,  # Convert percentage to 0.0-1.0 ratio
        visits=visits,
        pv=[move],
    )


def make_position_eval(
    candidates: list[LeelaCandidate],
    root_visits: int = 500,
) -> LeelaPositionEval:
    """Create a LeelaPositionEval for testing."""
    return LeelaPositionEval(
        candidates=candidates,
        root_visits=root_visits,
    )


def make_empty_position_eval(root_visits: int = 0) -> LeelaPositionEval:
    """Create an empty LeelaPositionEval (no candidates)."""
    return LeelaPositionEval(candidates=[], root_visits=root_visits)


# =============================================================================
# Section 4.1: Basic Tests (16 tests)
# =============================================================================


class TestBasicConversion:
    """Basic conversion tests (#1-#16)."""

    def test_single_move_conversion(self):
        """#1: Single move conversion works correctly."""
        parent = make_position_eval([
            make_candidate("D4", 55.0),  # best
            make_candidate("Q16", 50.0),  # played
        ])
        current = make_position_eval([
            make_candidate("Q4", 48.0),
        ])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="Q16",
        )

        assert result.move_number == 1
        assert result.player == "B"
        assert result.gtp == "Q16"
        assert result.leela_loss_est is not None
        assert result.leela_loss_est > 0  # Q16 is worse than D4

    def test_parent_none_returns_none_loss(self):
        """#2: Parent None (first move) returns leela_loss_est=None."""
        current = make_position_eval([make_candidate("D4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=None,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="D4",
        )

        assert result.leela_loss_est is None
        assert result.winrate_before is None
        assert result.delta_winrate is None

    def test_score_fields_are_none(self):
        """#3: score_* fields are all None for Leela."""
        current = make_position_eval([make_candidate("D4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=None,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="D4",
        )

        assert result.score_before is None
        assert result.score_after is None
        assert result.delta_score is None
        assert result.score_loss is None
        assert result.points_lost is None

    def test_winrate_fields_populated(self):
        """#4: winrate_* fields are correctly populated."""
        parent = make_position_eval([make_candidate("D4", 60.0)])
        current = make_position_eval([make_candidate("Q4", 55.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="D4",
        )

        assert result.winrate_before is not None
        assert result.winrate_after is not None
        assert result.delta_winrate is not None
        # Black played: parent is B-to-move (60%), current is W-to-move (55%)
        # winrate_before = 0.60, winrate_after = 1 - 0.55 = 0.45
        assert abs(result.winrate_before - 0.60) < 0.001
        assert abs(result.winrate_after - 0.45) < 0.001

    def test_best_move_loss_zero(self):
        """#5: Best move has loss_est = 0.0."""
        parent = make_position_eval([
            make_candidate("D4", 55.0),  # best
            make_candidate("Q16", 50.0),
        ])
        current = make_position_eval([make_candidate("Q4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="D4",  # best move
        )

        assert result.leela_loss_est == 0.0

    def test_worse_move_positive_loss(self):
        """#6: Worse move has positive loss_est."""
        parent = make_position_eval([
            make_candidate("D4", 60.0),  # best
            make_candidate("Q16", 50.0),  # 10% worse
        ])
        current = make_position_eval([make_candidate("Q4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="Q16",
            k=LEELA_K_DEFAULT,
        )

        # loss = (60 - 50) * 0.5 = 5.0
        assert result.leela_loss_est == 5.0

    def test_k_scaling_affects_loss(self):
        """#7: K coefficient scales the loss."""
        parent = make_position_eval([
            make_candidate("D4", 60.0),
            make_candidate("Q16", 50.0),
        ])
        current = make_position_eval([make_candidate("Q4", 50.0)])

        result_k05 = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="Q16",
            k=0.5,
        )

        result_k10 = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="Q16",
            k=1.0,
        )

        # K=0.5: (60-50)*0.5 = 5.0
        # K=1.0: (60-50)*1.0 = 10.0
        assert result_k05.leela_loss_est == 5.0
        assert result_k10.leela_loss_est == 10.0

    def test_loss_clamped_at_max(self):
        """#8: Loss is clamped at LEELA_LOSS_EST_MAX."""
        parent = make_position_eval([
            make_candidate("D4", 99.0),  # best
            make_candidate("Q16", 1.0),  # worst (98% diff)
        ])
        current = make_position_eval([make_candidate("Q4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="Q16",
            k=1.0,  # loss = 98 * 1.0 = 98 -> clamped to 50
        )

        assert result.leela_loss_est == LEELA_LOSS_EST_MAX

    def test_black_player_winrate_delta(self):
        """#9: Black player delta_winrate is calculated correctly (black perspective)."""
        # Black plays: parent is B-to-move (60%), current is W-to-move (50%)
        parent = make_position_eval([make_candidate("D4", 60.0)])
        current = make_position_eval([make_candidate("Q4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="D4",
        )

        # winrate_before = 0.60 (B's WR at parent, B-to-move)
        # winrate_after = 1.0 - 0.50 = 0.50 (B's WR at current, W-to-move)
        # delta = 0.50 - 0.60 = -0.10
        assert abs(result.winrate_before - 0.60) < 0.001
        assert abs(result.winrate_after - 0.50) < 0.001
        assert abs(result.delta_winrate - (-0.10)) < 0.001

    def test_white_player_winrate_delta(self):
        """#10: White player delta_winrate is calculated correctly (black perspective)."""
        # White plays: parent is W-to-move (60%), current is B-to-move (55%)
        parent = make_position_eval([make_candidate("D4", 60.0)])
        current = make_position_eval([make_candidate("Q4", 55.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=2,
            player="W",
            played_move="D4",
        )

        # winrate_before = 1.0 - 0.60 = 0.40 (B's WR at parent, W-to-move)
        # winrate_after = 0.55 (B's WR at current, B-to-move)
        # delta = 0.55 - 0.40 = +0.15
        assert abs(result.winrate_before - 0.40) < 0.001
        assert abs(result.winrate_after - 0.55) < 0.001
        assert abs(result.delta_winrate - 0.15) < 0.001

    def test_classify_by_winrate_only(self):
        """#11: Mistake classification uses winrate_loss (score_loss=None)."""
        parent = make_position_eval([make_candidate("D4", 70.0)])
        current = make_position_eval([make_candidate("Q4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="D4",
        )

        # delta = (1-0.50) - 0.70 = -0.20 (black worsened by 20%)
        # winrate_loss = 0.20 for black
        # classify_mistake with score_loss=None falls back to winrate_loss
        assert result.score_loss is None
        assert result.winrate_loss is not None
        assert result.mistake_category is not None

    def test_sequence_to_snapshot(self):
        """#12: Sequence conversion produces EvalSnapshot."""
        evals = [
            make_position_eval([make_candidate("D4", 55.0)]),
            make_position_eval([make_candidate("Q16", 50.0)]),
        ]
        moves_info = [
            (1, "B", "D4"),
            (2, "W", "Q16"),
        ]

        result = leela_sequence_to_eval_snapshot(evals, moves_info)

        assert isinstance(result, EvalSnapshot)
        assert len(result.moves) == 2

    def test_snapshot_has_correct_move_count(self):
        """#13: EvalSnapshot has correct move count."""
        evals = [
            make_position_eval([make_candidate("D4", 55.0)]),
            make_position_eval([make_candidate("Q16", 50.0)]),
            make_position_eval([make_candidate("D16", 48.0)]),
        ]
        moves_info = [
            (1, "B", "D4"),
            (2, "W", "Q16"),
            (3, "B", "D16"),
        ]

        result = leela_sequence_to_eval_snapshot(evals, moves_info)

        assert len(result.moves) == 3
        assert result.moves[0].move_number == 1
        assert result.moves[1].move_number == 2
        assert result.moves[2].move_number == 3

    def test_empty_candidates_handled(self):
        """#14: Empty candidates list is handled gracefully."""
        parent = make_empty_position_eval()
        current = make_position_eval([make_candidate("Q4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="D4",
        )

        # Empty parent: is_valid=False, best_winrate=None
        assert result.winrate_before is None
        assert result.leela_loss_est is None

    def test_single_candidate_handled(self):
        """#15: Single candidate is handled correctly."""
        parent = make_position_eval([make_candidate("D4", 55.0)])
        current = make_position_eval([make_candidate("Q4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="D4",  # only candidate
        )

        # Best = D4, played = D4, loss = 0
        assert result.leela_loss_est == 0.0

    def test_pass_move_handled(self):
        """#16: Pass move is handled correctly."""
        parent = make_position_eval([
            make_candidate("D4", 55.0),
            make_candidate("PASS", 45.0),
        ])
        current = make_position_eval([make_candidate("Q4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=10,
            player="B",
            played_move="pass",  # lowercase
        )

        # pass -> PASS, (55-45)*0.5 = 5.0
        assert result.leela_loss_est == 5.0


# =============================================================================
# Section 4.2: Review 1 Tests (5 tests, #17-#21)
# =============================================================================


class TestReview1Issues:
    """Tests for Review 1 issues (#17-#21)."""

    def test_played_move_not_in_candidates_returns_none(self):
        """#17: Played move not in candidates returns leela_loss_est=None."""
        parent = make_position_eval([
            make_candidate("D4", 55.0),
            make_candidate("Q16", 50.0),
        ])
        current = make_position_eval([make_candidate("Q4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="E5",  # not in candidates
        )

        assert result.leela_loss_est is None

    def test_winrate_perspective_black_bad_move(self):
        """#18: Black's bad move: delta_winrate<0, winrate_loss>0."""
        # Black plays bad: 60% -> 50% (black's perspective worsens)
        parent = make_position_eval([make_candidate("D4", 60.0)])
        current = make_position_eval([make_candidate("Q4", 50.0)])  # W-to-move

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="D4",
        )

        # winrate_after = 1 - 0.50 = 0.50
        # delta = 0.50 - 0.60 = -0.10
        assert result.delta_winrate < 0
        assert result.winrate_loss > 0
        assert abs(result.winrate_loss - 0.10) < 0.001

    def test_winrate_perspective_white_bad_move(self):
        """#19: White's bad move: delta_winrate>0 (black improved), winrate_loss>0."""
        # White plays bad: black improves from 40% to 55%
        parent = make_position_eval([make_candidate("D4", 60.0)])  # W-to-move, W=60%, B=40%
        current = make_position_eval([make_candidate("Q4", 55.0)])  # B-to-move, B=55%

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=2,
            player="W",
            played_move="D4",
        )

        # winrate_before = 1 - 0.60 = 0.40 (B's WR)
        # winrate_after = 0.55 (B's WR)
        # delta = 0.55 - 0.40 = +0.15 (black improved = white worsened)
        assert result.delta_winrate > 0
        assert result.winrate_loss > 0
        assert abs(result.winrate_loss - 0.15) < 0.001

    def test_leela_snapshot_properties_do_not_crash(self):
        """#20: Leela MoveEval doesn't crash EvalSnapshot properties."""
        moves = [
            MoveEval(
                move_number=1,
                player="B",
                gtp="D4",
                score_before=None,
                score_after=None,
                delta_score=None,
                winrate_before=0.55,
                winrate_after=0.50,
                delta_winrate=-0.05,
                points_lost=None,
                realized_points_lost=None,
                root_visits=100,
                score_loss=None,
                winrate_loss=0.05,
                mistake_category=MistakeCategory.INACCURACY,
                leela_loss_est=2.5,
            ),
        ]
        snapshot = EvalSnapshot(moves=moves)

        # Access properties - should not crash
        total_loss = snapshot.total_canonical_points_lost
        assert isinstance(total_loss, (int, float))

        max_loss = snapshot.max_canonical_points_lost
        assert isinstance(max_loss, (int, float))

        worst = snapshot.worst_canonical_move
        assert worst is None or isinstance(worst, MoveEval)

    def test_leela_snapshot_filtering_does_not_crash(self):
        """#21: Leela MoveEval doesn't crash EvalSnapshot filtering."""
        moves = [
            MoveEval(
                move_number=1,
                player="B",
                gtp="D4",
                score_before=None,
                score_after=None,
                delta_score=None,
                winrate_before=0.55,
                winrate_after=0.50,
                delta_winrate=-0.05,
                points_lost=None,
                realized_points_lost=None,
                root_visits=100,
                score_loss=None,
                winrate_loss=0.05,
                mistake_category=MistakeCategory.INACCURACY,
                leela_loss_est=2.5,
            ),
            MoveEval(
                move_number=2,
                player="W",
                gtp="Q16",
                score_before=None,
                score_after=None,
                delta_score=None,
                winrate_before=0.50,
                winrate_after=0.52,
                delta_winrate=0.02,
                points_lost=None,
                realized_points_lost=None,
                root_visits=100,
                score_loss=None,
                winrate_loss=0.02,
                mistake_category=MistakeCategory.GOOD,
                leela_loss_est=1.0,
            ),
        ]
        snapshot = EvalSnapshot(moves=moves)

        # Filtering operations - should not crash
        filtered = snapshot.by_player("B")
        assert isinstance(filtered, EvalSnapshot)
        assert filtered is not None

        first_n = snapshot.first_n_moves(5)
        assert isinstance(first_n, EvalSnapshot)


# =============================================================================
# Section 4.3: Review 2 Tests (6 tests, #22-#27)
# =============================================================================


class TestReview2Issues:
    """Tests for Review 2 issues (#22-#27)."""

    def test_move_normalization_variants(self):
        """#22: Move normalization handles case and pass variants."""
        # Case normalization
        assert _normalize_move("d4") == "D4"
        assert _normalize_move("D4") == "D4"
        assert _normalize_move("q16") == "Q16"

        # Pass variants
        assert _normalize_move("pass") == "PASS"
        assert _normalize_move("Pass") == "PASS"
        assert _normalize_move("PASS") == "PASS"

        # Whitespace handling
        assert _normalize_move("  D4  ") == "D4"

    def test_leela_loss_est_independent_of_delta_winrate(self):
        """#23: leela_loss_est is independent of delta_winrate."""
        # Create a scenario where loss_est and delta_winrate differ
        parent = make_position_eval([
            make_candidate("D4", 60.0),  # best
            make_candidate("Q16", 55.0),  # played (5% worse)
        ])
        # Current position: black now has 70% (improved despite suboptimal move)
        current = make_position_eval([make_candidate("Q4", 30.0)])  # W-to-move, W=30%, B=70%

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="Q16",
        )

        # leela_loss_est = (60-55)*0.5 = 2.5
        assert result.leela_loss_est == 2.5

        # delta_winrate = (1-0.30) - 0.60 = 0.70 - 0.60 = +0.10 (positive!)
        assert result.delta_winrate > 0

        # These can be different - that's expected

    def test_length_mismatch_raises_valueerror(self):
        """#24: Length mismatch between evals and moves_info raises ValueError."""
        evals = [
            make_position_eval([make_candidate("D4", 55.0)]),
            make_position_eval([make_candidate("Q16", 50.0)]),
        ]
        moves_info = [
            (1, "B", "D4"),
            # Missing second entry
        ]

        with pytest.raises(ValueError, match="Length mismatch"):
            leela_sequence_to_eval_snapshot(evals, moves_info)

    def test_non_monotonic_move_number_raises_valueerror(self):
        """#25: Non-monotonic move_number raises ValueError."""
        evals = [
            make_position_eval([make_candidate("D4", 55.0)]),
            make_position_eval([make_candidate("Q16", 50.0)]),
        ]
        moves_info = [
            (2, "B", "D4"),
            (1, "W", "Q16"),  # Non-monotonic (2 -> 1)
        ]

        with pytest.raises(ValueError, match="Non-monotonic"):
            leela_sequence_to_eval_snapshot(evals, moves_info)

    def test_non_alternating_players_logs_warning_but_continues(self, caplog):
        """#26: Non-alternating players logs warning but doesn't raise."""
        evals = [
            make_position_eval([make_candidate("D4", 55.0)]),
            make_position_eval([make_candidate("Q16", 50.0)]),
        ]
        moves_info = [
            (1, "B", "D4"),
            (2, "B", "Q16"),  # Same player (handicap game or pass?)
        ]

        with caplog.at_level(logging.WARNING):
            result = leela_sequence_to_eval_snapshot(evals, moves_info)

        # Should succeed
        assert isinstance(result, EvalSnapshot)
        assert len(result.moves) == 2

        # Should log warning
        assert "Non-alternating" in caplog.text

    def test_leela_loss_est_same_perspective_no_flip(self):
        """#27: leela_loss_est uses same perspective (no flip needed)."""
        # Both candidates are in the same position, so same perspective
        parent = make_position_eval([
            make_candidate("D4", 60.0),  # best
            make_candidate("Q16", 40.0),  # 20% worse
        ])
        current = make_position_eval([make_candidate("Q4", 50.0)])

        result = leela_position_to_move_eval(
            parent_eval=parent,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="Q16",
            k=0.5,
        )

        # loss = (60 - 40) * 0.5 = 10.0
        # No perspective flip needed - same position comparison
        assert result.leela_loss_est == 10.0


# =============================================================================
# Section 4.4: Review 3 Tests (4 tests, #28-#31)
# =============================================================================


class TestReview3Issues:
    """Tests for Review 3 issues (#28-#31)."""

    def test_winrate_loss_black_bad_move_positive(self):
        """#28: Black bad move: delta=-0.1 -> winrate_loss=0.1."""
        delta = -0.1
        winrate_loss = _compute_winrate_loss(delta, "B")

        assert winrate_loss == 0.1

    def test_winrate_loss_white_bad_move_positive(self):
        """#29: White bad move: delta=+0.1 -> winrate_loss=0.1."""
        delta = 0.1
        winrate_loss = _compute_winrate_loss(delta, "W")

        assert winrate_loss == 0.1

    def test_empty_move_returns_none(self):
        """#30: Empty string normalizes to None."""
        assert _normalize_move("") is None
        assert _normalize_move("   ") is None

    def test_loss_est_rounding_threshold(self):
        """#31: Loss rounding: epsilon->0, round to 1 decimal, clamp to max."""
        # Below epsilon (0.05) -> 0.0
        assert _round_loss_est(0.04) == 0.0
        assert _round_loss_est(0.049) == 0.0

        # At/above epsilon -> round to 1 decimal
        assert _round_loss_est(0.06) == 0.1
        assert _round_loss_est(0.14) == 0.1
        # Note: Python uses banker's rounding (0.15 rounds to 0.2, but 0.25 rounds to 0.2)
        assert _round_loss_est(0.16) == 0.2

        # Above max -> clamp to 50.0
        assert _round_loss_est(51.0) == 50.0
        assert _round_loss_est(100.0) == 50.0


# =============================================================================
# Additional edge case tests
# =============================================================================


class TestEdgeCases:
    """Additional edge case tests."""

    def test_move_number_less_than_one_raises(self):
        """Invalid move_number < 1 raises ValueError."""
        evals = [make_position_eval([make_candidate("D4", 55.0)])]
        moves_info = [(0, "B", "D4")]  # move_number = 0

        with pytest.raises(ValueError, match="Invalid move_number"):
            leela_sequence_to_eval_snapshot(evals, moves_info)

    def test_root_visits_propagated(self):
        """root_visits from current_eval is propagated to MoveEval."""
        current = make_position_eval([make_candidate("D4", 50.0)], root_visits=1234)

        result = leela_position_to_move_eval(
            parent_eval=None,
            current_eval=current,
            move_number=1,
            player="B",
            played_move="D4",
        )

        assert result.root_visits == 1234

    def test_compute_winrate_loss_none_input(self):
        """_compute_winrate_loss returns None for None input."""
        assert _compute_winrate_loss(None, "B") is None
        assert _compute_winrate_loss(None, "W") is None

    def test_convert_to_black_perspective_none_input(self):
        """_convert_to_black_perspective handles None inputs."""
        result = _convert_to_black_perspective(None, 0.5, "B")
        assert result == (None, None, None)

        result = _convert_to_black_perspective(0.5, None, "B")
        assert result == (None, None, None)

    def test_empty_sequence(self):
        """Empty sequence produces empty EvalSnapshot."""
        result = leela_sequence_to_eval_snapshot([], [])
        assert isinstance(result, EvalSnapshot)
        assert len(result.moves) == 0
