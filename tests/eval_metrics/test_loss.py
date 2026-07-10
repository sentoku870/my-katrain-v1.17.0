"""Loss-related tests extracted from tests/test_eval_metrics.py.

Phase D-1: split the 2316-line test_eval_metrics.py into 4 themed
submodules so each test file stays under ~800 lines and test discovery
is faster. The class names, ordering, and behaviour are preserved
verbatim from the original monolithic file.
"""

from __future__ import annotations

import pytest

from katrain.core.eval_metrics import (
    SCORE_THRESHOLDS,
    WINRATE_THRESHOLDS,
    MistakeCategory,
    PositionDifficulty,
    classify_mistake,
    compute_canonical_loss,
    compute_loss_from_delta,
)
from tests.helpers_eval_metrics import StubGameNode, StubMove, make_move_eval


class TestComputeLossFromDelta:
    """Tests for compute_loss_from_delta function (side-to-move expected)"""

    def test_positive_delta_means_no_loss(self):
        """If delta is positive (position improved), loss should be 0"""
        score_loss, winrate_loss = compute_loss_from_delta(
            delta_score=3.0,  # Position improved by 3 points
            delta_winrate=0.1,  # Winrate improved by 10%
        )
        assert score_loss == 0.0
        assert winrate_loss == 0.0

    def test_negative_delta_means_loss(self):
        """If delta is negative (position worsened), loss should be positive"""
        score_loss, winrate_loss = compute_loss_from_delta(
            delta_score=-5.0,  # Position worsened by 5 points
            delta_winrate=-0.15,  # Winrate dropped by 15%
        )
        assert score_loss == 5.0
        assert winrate_loss == 0.15

    def test_none_values_return_none(self):
        """None inputs should produce None outputs"""
        score_loss, winrate_loss = compute_loss_from_delta(None, None)
        assert score_loss is None
        assert winrate_loss is None

        score_loss, winrate_loss = compute_loss_from_delta(3.0, None)
        assert score_loss == 0.0
        assert winrate_loss is None


# ---------------------------------------------------------------------------
# Test: classify_mistake
# ---------------------------------------------------------------------------


class TestClassifyMistake:
    """Tests for classify_mistake function with standard thresholds"""

    @pytest.mark.parametrize(
        "score_loss,expected",
        [
            (0.0, MistakeCategory.GOOD),
            (0.3, MistakeCategory.GOOD),
            (0.99, MistakeCategory.GOOD),
        ],
    )
    def test_good_move(self, score_loss, expected):
        """Loss below inaccuracy threshold is GOOD"""
        assert classify_mistake(score_loss, None) == expected

    @pytest.mark.parametrize(
        "score_loss,expected",
        [
            (1.0, MistakeCategory.INACCURACY),
            (1.5, MistakeCategory.INACCURACY),
            (1.99, MistakeCategory.INACCURACY),
        ],
    )
    def test_inaccuracy(self, score_loss, expected):
        """Loss in inaccuracy range"""
        assert classify_mistake(score_loss, None) == expected

    @pytest.mark.parametrize(
        "score_loss,expected",
        [
            # Standard thresholds: (1.0, 2.5, 5.0) - mistake is >= 2.5
            (2.5, MistakeCategory.MISTAKE),
            (3.0, MistakeCategory.MISTAKE),
            (4.99, MistakeCategory.MISTAKE),
        ],
    )
    def test_mistake(self, score_loss, expected):
        """Loss in mistake range (standard: 2.5 <= loss < 5.0)"""
        assert classify_mistake(score_loss, None) == expected

    @pytest.mark.parametrize(
        "score_loss,expected",
        [
            # Standard thresholds: blunder is >= 5.0
            (5.0, MistakeCategory.BLUNDER),
            (10.0, MistakeCategory.BLUNDER),
            (100.0, MistakeCategory.BLUNDER),
        ],
    )
    def test_blunder(self, score_loss, expected):
        """Loss above blunder threshold (standard: >= 5.0)"""
        assert classify_mistake(score_loss, None) == expected

    def test_score_priority_over_winrate(self):
        """Score loss takes priority when available"""
        cat = classify_mistake(
            score_loss=0.5,  # GOOD
            winrate_loss=0.30,  # Would be BLUNDER if used
            score_thresholds=SCORE_THRESHOLDS,
            winrate_thresholds=WINRATE_THRESHOLDS,
        )
        assert cat == MistakeCategory.GOOD

    def test_winrate_fallback(self):
        """Uses winrate when score is None"""
        cat = classify_mistake(
            score_loss=None,
            winrate_loss=0.15,  # MISTAKE threshold for standard
            score_thresholds=SCORE_THRESHOLDS,
            winrate_thresholds=WINRATE_THRESHOLDS,
        )
        assert cat == MistakeCategory.MISTAKE


class TestCategoryConsistencyBetweenKarteAndSummary:
    """
    Verify that mistake classification is consistent across all code paths.

    Issue: Previously, build_karte_report() used hardcoded thresholds (1, 3, 7)
    while classify_mistake() used skill preset thresholds (1, 2.5, 5 for standard).
    This caused the same move to show different categories in Karte vs Summary.

    Fix: mistake_label_from_loss() now delegates to classify_mistake().
    """

    @pytest.mark.parametrize(
        "loss,expected",
        [
            (0.5, MistakeCategory.GOOD),
            (1.0, MistakeCategory.INACCURACY),
            (2.0, MistakeCategory.INACCURACY),
            (2.5, MistakeCategory.MISTAKE),
            (4.9, MistakeCategory.MISTAKE),
            (5.0, MistakeCategory.BLUNDER),
            (6.1, MistakeCategory.BLUNDER),  # This was the problematic case
            (10.0, MistakeCategory.BLUNDER),
        ],
    )
    def test_classify_mistake_standard_thresholds(self, loss, expected):
        """classify_mistake uses standard thresholds: 1.0, 2.5, 5.0"""
        assert classify_mistake(score_loss=loss, winrate_loss=None) == expected

    def test_6_1_loss_is_blunder(self):
        """
        Specific regression test: 6.1 points lost should be BLUNDER.

        Previously Karte showed 6.1 as 'mistake' (using < 7.0 threshold)
        while Summary showed it as 'BLUNDER' (using < 5.0 threshold).
        Now both should show BLUNDER.
        """
        cat = classify_mistake(score_loss=6.1, winrate_loss=None)
        assert cat == MistakeCategory.BLUNDER
        assert cat.value == "blunder"


# ---------------------------------------------------------------------------
# Test: Perspective consistency with StubGameNode
# ---------------------------------------------------------------------------


class TestPerspectiveConsistency:
    """
    Tests using StubGameNode to verify perspective conventions are correct.

    These tests verify our understanding of KaTrain's perspective handling:
    - score: BLACK-PERSPECTIVE (positive = black ahead)
    - points_lost: SIDE-TO-MOVE (positive = loss for moving player)
    """

    def test_black_bad_move_has_positive_points_lost(self):
        """Black makes a bad move, score drops - points_lost should be positive"""
        parent = StubGameNode(_score=5.0)
        child = StubGameNode(
            move=StubMove(player="B", coords=(3, 3)),
            parent=parent,
            _score=2.0,  # Black's score dropped
        )
        assert child.points_lost == 3.0

    def test_black_good_move_has_negative_points_lost(self):
        """Black makes a good move, score rises - points_lost should be negative"""
        parent = StubGameNode(_score=2.0)
        child = StubGameNode(
            move=StubMove(player="B", coords=(3, 3)),
            parent=parent,
            _score=5.0,  # Black's score improved
        )
        assert child.points_lost == -3.0

    def test_white_bad_move_has_positive_points_lost(self):
        """White makes a bad move, score rises (toward black) - points_lost positive"""
        parent = StubGameNode(_score=-5.0)  # White ahead 5
        child = StubGameNode(
            move=StubMove(player="W", coords=(3, 3)),
            parent=parent,
            _score=-2.0,  # White's advantage shrunk
        )
        assert child.points_lost == 3.0

    def test_white_good_move_has_negative_points_lost(self):
        """White makes a good move, score drops (toward white) - points_lost negative"""
        parent = StubGameNode(_score=-2.0)  # White ahead 2
        child = StubGameNode(
            move=StubMove(player="W", coords=(3, 3)),
            parent=parent,
            _score=-5.0,  # White extended advantage
        )
        assert child.points_lost == -3.0


# ---------------------------------------------------------------------------
# CRITICAL REGRESSION TESTS - Using compute_canonical_loss
# ---------------------------------------------------------------------------


class TestCanonicalLossRequirements:
    """
    CRITICAL REGRESSION TESTS for canonical loss calculation.

    These tests call compute_canonical_loss() directly to ensure the
    implementation produces correct results. If these tests fail,
    the implementation has regressed.

    Key requirement: canonical loss must be >= 0 for bad moves, 0 for good moves.
    """

    @pytest.mark.parametrize(
        "player,parent_score,current_score,expected_loss",
        [
            # Black blunders
            ("B", 5.0, 2.0, 3.0),  # Black lost 3 points
            ("B", 10.0, 0.0, 10.0),  # Black lost 10 points
            ("B", 0.0, -5.0, 5.0),  # Black went behind
            # White blunders
            ("W", -5.0, -2.0, 3.0),  # White lost 3 points of advantage
            ("W", -10.0, 0.0, 10.0),  # White lost 10 points of advantage
            ("W", 0.0, 5.0, 5.0),  # White went behind
        ],
    )
    def test_blunder_produces_positive_canonical_loss(self, player, parent_score, current_score, expected_loss):
        """
        REGRESSION TEST: Blunders must produce positive canonical loss.

        Tests both Black and White perspectives to ensure perspective
        correction is working in compute_canonical_loss().
        """
        # Compute points_lost as KaTrain does
        player_sign = {"B": 1, "W": -1}[player]
        points_lost = player_sign * (parent_score - current_score)

        # Compute delta_score (black-perspective)
        delta_score = current_score - parent_score

        # Call the actual implementation
        score_loss, _ = compute_canonical_loss(
            points_lost=points_lost,
            delta_score=delta_score,
            player=player,
        )

        assert score_loss == expected_loss, (
            f"{player}'s blunder must have canonical loss {expected_loss}, got {score_loss}"
        )

    @pytest.mark.parametrize(
        "player,parent_score,current_score",
        [
            # Black good moves
            ("B", 2.0, 5.0),  # Black gained 3 points
            ("B", 0.0, 10.0),  # Black gained 10 points
            ("B", -5.0, 0.0),  # Black recovered
            # White good moves
            ("W", -2.0, -5.0),  # White gained 3 points of advantage
            ("W", 0.0, -10.0),  # White gained 10 points of advantage
            ("W", 5.0, 0.0),  # White recovered
        ],
    )
    def test_good_move_produces_zero_canonical_loss(self, player, parent_score, current_score):
        """
        REGRESSION TEST: Good moves must produce zero canonical loss.
        """
        player_sign = {"B": 1, "W": -1}[player]
        points_lost = player_sign * (parent_score - current_score)
        delta_score = current_score - parent_score

        score_loss, _ = compute_canonical_loss(
            points_lost=points_lost,
            delta_score=delta_score,
            player=player,
        )

        assert score_loss == 0.0, f"{player}'s good move must have zero canonical loss, got {score_loss}"

    def test_delta_fallback_white_blunder(self):
        """
        CRITICAL: When points_lost is None, delta fallback must still
        produce correct loss for White's blunder.
        """
        # White blunders: score goes from -5.0 to -2.0 (black-perspective)
        # delta_score = -2.0 - (-5.0) = +3.0 (black got better)
        score_loss, _ = compute_canonical_loss(
            points_lost=None,  # Force delta fallback
            delta_score=3.0,  # Black-perspective delta
            player="W",
        )

        assert score_loss == 3.0, "Delta fallback must produce correct loss for White's blunder"

    def test_delta_fallback_white_good_move(self):
        """
        When points_lost is None, delta fallback must produce zero
        for White's good move.
        """
        # White improves: score goes from -2.0 to -5.0 (black-perspective)
        # delta_score = -5.0 - (-2.0) = -3.0 (black got worse)
        score_loss, _ = compute_canonical_loss(
            points_lost=None,  # Force delta fallback
            delta_score=-3.0,  # Black-perspective delta
            player="W",
        )

        assert score_loss == 0.0, "Delta fallback must produce zero for White's good move"


# ---------------------------------------------------------------------------
# Test: compute_canonical_loss function
# ---------------------------------------------------------------------------


class TestComputeCanonicalLoss:
    """
    Tests for compute_canonical_loss function.

    This function is the core of perspective-correct loss calculation:
    - Primary: use points_lost (already has player_sign applied)
    - Fallback: use delta with player-sign correction
    """

    def test_points_lost_primary_for_black_bad_move(self):
        """points_lost is used when available (Black bad move)"""
        score_loss, _ = compute_canonical_loss(
            points_lost=3.0,  # Bad move
            delta_score=-3.0,  # Would also give 3.0
            player="B",
        )
        assert score_loss == 3.0

    def test_points_lost_primary_for_white_bad_move(self):
        """points_lost is used when available (White bad move)"""
        score_loss, _ = compute_canonical_loss(
            points_lost=3.0,  # Bad move (already player_sign applied)
            delta_score=3.0,  # Raw black-perspective delta (wrong without correction)
            player="W",
        )
        assert score_loss == 3.0

    def test_points_lost_clamps_negative_to_zero(self):
        """Negative points_lost (good move) should be clamped to 0"""
        score_loss, _ = compute_canonical_loss(
            points_lost=-3.0,  # Good move
            player="B",
        )
        assert score_loss == 0.0

    def test_delta_fallback_for_black(self):
        """Uses delta when points_lost is None (Black)"""
        score_loss, _ = compute_canonical_loss(
            points_lost=None,
            delta_score=-3.0,  # Black-perspective: Black got worse
            player="B",
        )
        assert score_loss == 3.0

    def test_winrate_loss_calculation(self):
        """Winrate loss follows same pattern"""
        _, winrate_loss = compute_canonical_loss(
            points_lost=None,
            delta_winrate=0.1,  # Black-perspective: Black improved (White got worse)
            player="W",
        )
        assert winrate_loss == 0.1

    def test_all_none_returns_none(self):
        """If all inputs are None, returns None"""
        score_loss, winrate_loss = compute_canonical_loss(
            points_lost=None,
            delta_score=None,
            delta_winrate=None,
            player="B",
        )
        assert score_loss is None
        assert winrate_loss is None


# ---------------------------------------------------------------------------
# Test: MoveEval and EvalSnapshot
# ---------------------------------------------------------------------------


class TestMoveEval:
    """Tests for MoveEval dataclass"""

    def test_create_basic_move_eval(self):
        """Can create a basic MoveEval with required fields"""
        m = make_move_eval(move_number=1, player="B", gtp="D4")
        assert m.move_number == 1
        assert m.player == "B"
        assert m.gtp == "D4"
        assert m.points_lost is None
        assert m.mistake_category == MistakeCategory.GOOD

    def test_move_eval_with_all_fields(self):
        """Can create MoveEval with all evaluation data"""
        m = make_move_eval(
            move_number=45,
            player="W",
            gtp="Q16",
            score_before=-2.0,
            score_after=-5.0,
            delta_score=-3.0,
            points_lost=3.0,
            score_loss=3.0,
            winrate_loss=0.07,
            mistake_category=MistakeCategory.MISTAKE,
            position_difficulty=PositionDifficulty.HARD,
        )
        assert m.score_loss == 3.0
        assert m.mistake_category == MistakeCategory.MISTAKE
