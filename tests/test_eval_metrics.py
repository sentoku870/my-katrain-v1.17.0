"""
Tests for katrain/core/eval_metrics.py

These tests ensure that:
1. Perspective conventions are consistent (black-perspective vs side-to-move)
2. Loss calculations are always >= 0 for bad moves
3. Mistake classification works correctly for both Black and White
4. Importance scoring is stable

Key insight about perspectives:
- GameNode.score/winrate: Always BLACK-PERSPECTIVE (positive = black ahead)
- GameNode.points_lost: Already converted to SIDE-TO-MOVE (uses player_sign)
- MoveEval.delta_score/delta_winrate: BLACK-PERSPECTIVE (score_after - score_before)
- MoveEval.score_loss/winrate_loss: Always >= 0 (computed by compute_canonical_loss)
"""

import pytest
from typing import Optional

from katrain.core.eval_metrics import (
    MoveEval,
    MistakeCategory,
    PositionDifficulty,
    EvalSnapshot,
    compute_loss_from_delta,
    compute_canonical_loss,
    classify_mistake,
    compute_importance_for_moves,
    SCORE_THRESHOLDS,
    WINRATE_THRESHOLDS,
)

# Import shared helpers
from tests.helpers_eval_metrics import make_move_eval, StubGameNode, StubMove


# ---------------------------------------------------------------------------
# Test: compute_loss_from_delta (legacy function)
# ---------------------------------------------------------------------------

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

    @pytest.mark.parametrize("score_loss,expected", [
        (0.0, MistakeCategory.GOOD),
        (0.3, MistakeCategory.GOOD),
        (0.99, MistakeCategory.GOOD),
    ])
    def test_good_move(self, score_loss, expected):
        """Loss below inaccuracy threshold is GOOD"""
        assert classify_mistake(score_loss, None) == expected

    @pytest.mark.parametrize("score_loss,expected", [
        (1.0, MistakeCategory.INACCURACY),
        (1.5, MistakeCategory.INACCURACY),
        (1.99, MistakeCategory.INACCURACY),
    ])
    def test_inaccuracy(self, score_loss, expected):
        """Loss in inaccuracy range"""
        assert classify_mistake(score_loss, None) == expected

    @pytest.mark.parametrize("score_loss,expected", [
        # Standard thresholds: (1.0, 2.5, 5.0) - mistake is >= 2.5
        (2.5, MistakeCategory.MISTAKE),
        (3.0, MistakeCategory.MISTAKE),
        (4.99, MistakeCategory.MISTAKE),
    ])
    def test_mistake(self, score_loss, expected):
        """Loss in mistake range (standard: 2.5 <= loss < 5.0)"""
        assert classify_mistake(score_loss, None) == expected

    @pytest.mark.parametrize("score_loss,expected", [
        # Standard thresholds: blunder is >= 5.0
        (5.0, MistakeCategory.BLUNDER),
        (10.0, MistakeCategory.BLUNDER),
        (100.0, MistakeCategory.BLUNDER),
    ])
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

    @pytest.mark.parametrize("loss,expected", [
        (0.5, MistakeCategory.GOOD),
        (1.0, MistakeCategory.INACCURACY),
        (2.0, MistakeCategory.INACCURACY),
        (2.5, MistakeCategory.MISTAKE),
        (4.9, MistakeCategory.MISTAKE),
        (5.0, MistakeCategory.BLUNDER),
        (6.1, MistakeCategory.BLUNDER),  # This was the problematic case
        (10.0, MistakeCategory.BLUNDER),
    ])
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

    @pytest.mark.parametrize("player,parent_score,current_score,expected_loss", [
        # Black blunders
        ("B", 5.0, 2.0, 3.0),    # Black lost 3 points
        ("B", 10.0, 0.0, 10.0),  # Black lost 10 points
        ("B", 0.0, -5.0, 5.0),   # Black went behind
        # White blunders
        ("W", -5.0, -2.0, 3.0),  # White lost 3 points of advantage
        ("W", -10.0, 0.0, 10.0), # White lost 10 points of advantage
        ("W", 0.0, 5.0, 5.0),    # White went behind
    ])
    def test_blunder_produces_positive_canonical_loss(
        self, player, parent_score, current_score, expected_loss
    ):
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

    @pytest.mark.parametrize("player,parent_score,current_score", [
        # Black good moves
        ("B", 2.0, 5.0),    # Black gained 3 points
        ("B", 0.0, 10.0),   # Black gained 10 points
        ("B", -5.0, 0.0),   # Black recovered
        # White good moves
        ("W", -2.0, -5.0),  # White gained 3 points of advantage
        ("W", 0.0, -10.0),  # White gained 10 points of advantage
        ("W", 5.0, 0.0),    # White recovered
    ])
    def test_good_move_produces_zero_canonical_loss(
        self, player, parent_score, current_score
    ):
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

        assert score_loss == 0.0, (
            f"{player}'s good move must have zero canonical loss, got {score_loss}"
        )

    def test_delta_fallback_white_blunder(self):
        """
        CRITICAL: When points_lost is None, delta fallback must still
        produce correct loss for White's blunder.
        """
        # White blunders: score goes from -5.0 to -2.0 (black-perspective)
        # delta_score = -2.0 - (-5.0) = +3.0 (black got better)
        score_loss, _ = compute_canonical_loss(
            points_lost=None,  # Force delta fallback
            delta_score=3.0,   # Black-perspective delta
            player="W",
        )

        assert score_loss == 3.0, (
            "Delta fallback must produce correct loss for White's blunder"
        )

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

        assert score_loss == 0.0, (
            "Delta fallback must produce zero for White's good move"
        )


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


class TestEvalSnapshot:
    """Tests for EvalSnapshot container"""

    def test_total_points_lost_includes_negative(self):
        """
        total_points_lost sums raw points_lost (can include negative).

        NOTE: This is for backward compatibility. Use total_canonical_points_lost
        for clamped (>=0) totals.
        """
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", points_lost=2.0),
            make_move_eval(move_number=2, player="W", gtp="Q16", points_lost=1.5),
            make_move_eval(move_number=3, player="B", gtp="D16", points_lost=-0.5),  # Good move
        ]
        snapshot = EvalSnapshot(moves=moves)

        # Includes negative
        assert snapshot.total_points_lost == 3.0  # 2.0 + 1.5 + (-0.5)

    def test_total_canonical_points_lost_clamps(self):
        """
        total_canonical_points_lost sums clamped (>=0) score_loss values.
        """
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", points_lost=2.0, score_loss=2.0),
            make_move_eval(move_number=2, player="W", gtp="Q16", points_lost=1.5, score_loss=1.5),
            make_move_eval(move_number=3, player="B", gtp="D16", points_lost=-0.5, score_loss=0.0),
        ]
        snapshot = EvalSnapshot(moves=moves)

        # Uses score_loss (already clamped)
        assert snapshot.total_canonical_points_lost == 3.5  # 2.0 + 1.5 + 0.0

    def test_max_canonical_points_lost(self):
        """max_canonical_points_lost returns the maximum score_loss"""
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=2.0),
            make_move_eval(move_number=2, player="W", gtp="Q16", score_loss=5.5),
            make_move_eval(move_number=3, player="B", gtp="D16", score_loss=1.0),
        ]
        snapshot = EvalSnapshot(moves=moves)

        assert snapshot.max_canonical_points_lost == 5.5

    def test_worst_move(self):
        """worst_move returns the move with highest points_lost"""
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", points_lost=2.0),
            make_move_eval(move_number=2, player="W", gtp="Q16", points_lost=5.5),
            make_move_eval(move_number=3, player="B", gtp="D16", points_lost=1.0),
        ]
        snapshot = EvalSnapshot(moves=moves)

        worst = snapshot.worst_move
        assert worst is not None
        assert worst.move_number == 2
        assert worst.points_lost == 5.5

    def test_worst_canonical_move(self):
        """worst_canonical_move returns move with highest score_loss"""
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", score_loss=2.0),
            make_move_eval(move_number=2, player="W", gtp="Q16", score_loss=5.5),
            make_move_eval(move_number=3, player="B", gtp="D16", score_loss=1.0),
        ]
        snapshot = EvalSnapshot(moves=moves)

        worst = snapshot.worst_canonical_move
        assert worst is not None
        assert worst.move_number == 2
        assert worst.score_loss == 5.5

    def test_filter_by_player(self):
        """by_player returns only moves by specified player"""
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4", points_lost=2.0),
            make_move_eval(move_number=2, player="W", gtp="Q16", points_lost=5.5),
            make_move_eval(move_number=3, player="B", gtp="D16", points_lost=1.0),
        ]
        snapshot = EvalSnapshot(moves=moves)

        black_snapshot = snapshot.by_player("B")
        assert len(black_snapshot.moves) == 2
        assert all(m.player == "B" for m in black_snapshot.moves)


# ---------------------------------------------------------------------------
# Test: Importance scoring
# ---------------------------------------------------------------------------

class TestComputeImportance:
    """Tests for compute_importance_for_moves function"""

    def test_high_loss_has_high_importance(self):
        """Moves with high loss should have high importance"""
        moves = [
            make_move_eval(
                move_number=1, player="B", gtp="D4",
                delta_score=-0.5, delta_winrate=-0.01,
                points_lost=0.5, score_loss=0.5,
            ),
            make_move_eval(
                move_number=2, player="W", gtp="Q16",
                delta_score=8.0, delta_winrate=0.15,  # Black-perspective
                points_lost=8.0, score_loss=8.0,
            ),
        ]

        compute_importance_for_moves(moves)

        assert moves[1].importance_score > moves[0].importance_score

    def test_importance_is_non_negative(self):
        """Importance scores should always be non-negative"""
        moves = [
            make_move_eval(
                move_number=1, player="B", gtp="D4",
                delta_score=5.0,  # Good move
                delta_winrate=0.1,
                points_lost=-2.0,  # Negative loss (good move)
                score_loss=0.0,   # Canonical: clamped to 0
            ),
        ]

        compute_importance_for_moves(moves)

        assert moves[0].importance_score >= 0.0


# ---------------------------------------------------------------------------
# Test: Delta vs Points Lost consistency (documentation)
# ---------------------------------------------------------------------------

class TestDeltaVsPointsLostConsistency:
    """
    Tests documenting the relationship between delta and points_lost.

    These tests ensure compute_canonical_loss correctly handles both.
    """

    def test_delta_and_points_lost_produce_same_canonical_loss(self):
        """
        When both are provided, points_lost takes priority.
        When only delta is available, perspective correction is applied.
        """
        # Black's bad move
        parent_score = 5.0
        current_score = 2.0
        player = "B"

        player_sign = 1
        points_lost = player_sign * (parent_score - current_score)  # = 3.0
        delta_score = current_score - parent_score  # = -3.0

        # With both: uses points_lost
        loss1, _ = compute_canonical_loss(points_lost=points_lost, delta_score=delta_score, player=player)

        # With only delta: applies correction
        loss2, _ = compute_canonical_loss(points_lost=None, delta_score=delta_score, player=player)

        assert loss1 == loss2 == 3.0

    def test_white_perspective_correction_in_delta_fallback(self):
        """
        Critical test: delta fallback must apply player_sign for White.
        """
        # White's bad move (black-perspective)
        parent_score = -5.0  # White ahead
        current_score = -2.0  # White's advantage shrunk

        delta_score = current_score - parent_score  # = +3.0 (black got better)

        # Without correction: would give 0 (wrong!)
        # With correction: should give 3.0
        loss, _ = compute_canonical_loss(
            points_lost=None,
            delta_score=delta_score,
            player="W",
        )

        assert loss == 3.0, (
            "Delta fallback with perspective correction must produce 3.0 for White's blunder"
        )


# ---------------------------------------------------------------------------
# Integration Tests: snapshot_from_nodes, iter_main_branch_nodes, snapshot_from_game
# ---------------------------------------------------------------------------

from tests.helpers_eval_metrics import build_stub_game_tree, StubGame


class TestSnapshotFromNodes:
    """Integration tests for snapshot_from_nodes function"""

    def test_basic_snapshot_creation(self):
        """Create snapshot from a simple sequence of nodes"""
        from katrain.core.eval_metrics import snapshot_from_nodes

        # Build a simple game: B plays, W plays, B plays
        game = build_stub_game_tree([
            ("B", (3, 3), 1.0),    # Black plays, score becomes +1.0 (good for black)
            ("W", (15, 15), -2.0), # White plays, score becomes -2.0 (good for white)
            ("B", (3, 15), 0.0),   # Black plays, score becomes 0.0 (even)
        ])

        # Collect all nodes with moves
        nodes = []
        node = game.root
        while node:
            if node.move is not None:
                nodes.append(node)
            node = node.children[0] if node.children else None

        snapshot = snapshot_from_nodes(nodes)

        assert len(snapshot.moves) == 3
        assert snapshot.moves[0].player == "B"
        assert snapshot.moves[1].player == "W"
        assert snapshot.moves[2].player == "B"

    def test_before_after_are_chained(self):
        """Verify score_before/after are chained correctly"""
        from katrain.core.eval_metrics import snapshot_from_nodes

        game = build_stub_game_tree([
            ("B", (3, 3), 5.0),
            ("W", (15, 15), 2.0),
        ])

        nodes = []
        node = game.root
        while node:
            if node.move is not None:
                nodes.append(node)
            node = node.children[0] if node.children else None

        snapshot = snapshot_from_nodes(nodes)

        # First move: no before (from root)
        assert snapshot.moves[0].score_after == 5.0

        # Second move: before = first move's after
        assert snapshot.moves[1].score_before == 5.0
        assert snapshot.moves[1].score_after == 2.0

    def test_empty_nodes_produce_empty_snapshot(self):
        """Empty node list produces empty snapshot"""
        from katrain.core.eval_metrics import snapshot_from_nodes

        snapshot = snapshot_from_nodes([])

        assert len(snapshot.moves) == 0
        assert snapshot.total_points_lost == 0.0

    def test_importance_is_computed(self):
        """Verify importance scores are computed for all moves"""
        from katrain.core.eval_metrics import snapshot_from_nodes

        game = build_stub_game_tree([
            ("B", (3, 3), 5.0),
            ("W", (15, 15), 10.0),  # White loses 5 points (big mistake)
        ])

        nodes = []
        node = game.root
        while node:
            if node.move is not None:
                nodes.append(node)
            node = node.children[0] if node.children else None

        snapshot = snapshot_from_nodes(nodes)

        # All moves should have importance_score set
        for mv in snapshot.moves:
            assert mv.importance_score is not None


class TestIterMainBranchNodes:
    """Integration tests for iter_main_branch_nodes function"""

    def test_basic_iteration(self):
        """Iterate through a simple main branch"""
        from katrain.core.eval_metrics import iter_main_branch_nodes

        game = build_stub_game_tree([
            ("B", (3, 3), 1.0),
            ("W", (15, 15), -1.0),
            ("B", (3, 15), 0.5),
        ])

        nodes = list(iter_main_branch_nodes(game))

        assert len(nodes) == 3
        assert nodes[0].move.player == "B"
        assert nodes[1].move.player == "W"
        assert nodes[2].move.player == "B"

    def test_empty_game(self):
        """Empty game (only root) produces no nodes"""
        from katrain.core.eval_metrics import iter_main_branch_nodes

        game = StubGame(root=StubGameNode(move=None, children=[]))

        nodes = list(iter_main_branch_nodes(game))

        assert len(nodes) == 0

    def test_none_root(self):
        """Game with None root produces no nodes"""
        from katrain.core.eval_metrics import iter_main_branch_nodes

        game = StubGame(root=None)

        nodes = list(iter_main_branch_nodes(game))

        assert len(nodes) == 0

    def test_single_move(self):
        """Game with single move"""
        from katrain.core.eval_metrics import iter_main_branch_nodes

        game = build_stub_game_tree([
            ("B", (3, 3), 1.0),
        ])

        nodes = list(iter_main_branch_nodes(game))

        assert len(nodes) == 1
        assert nodes[0].move.player == "B"


class TestSnapshotFromGame:
    """Integration tests for snapshot_from_game function"""

    def test_basic_game_to_snapshot(self):
        """Convert a simple game to snapshot"""
        from katrain.core.eval_metrics import snapshot_from_game

        game = build_stub_game_tree([
            ("B", (3, 3), 2.0),
            ("W", (15, 15), -3.0),
            ("B", (3, 15), 1.0),
        ])

        snapshot = snapshot_from_game(game)

        assert len(snapshot.moves) == 3
        assert snapshot.moves[0].move_number == 1
        assert snapshot.moves[1].move_number == 2
        assert snapshot.moves[2].move_number == 3

    def test_loss_calculation(self):
        """Verify loss is calculated correctly through the pipeline"""
        from katrain.core.eval_metrics import snapshot_from_game

        # Black makes a bad move: score goes from 0 to -5 (white gets ahead)
        game = build_stub_game_tree([
            ("B", (3, 3), -5.0),  # Black's bad move
        ])

        snapshot = snapshot_from_game(game)

        # Black lost 5 points (from 0 to -5)
        assert snapshot.moves[0].points_lost == 5.0
        assert snapshot.moves[0].score_loss == 5.0

    def test_canonical_properties_work(self):
        """Verify canonical properties are accessible"""
        from katrain.core.eval_metrics import snapshot_from_game

        game = build_stub_game_tree([
            ("B", (3, 3), -3.0),  # Black loses 3
            ("W", (15, 15), 0.0),  # White loses 3
        ])

        snapshot = snapshot_from_game(game)

        # Both players lost some points
        assert snapshot.total_canonical_points_lost > 0
        assert snapshot.max_canonical_points_lost >= 3.0

    def test_empty_game(self):
        """Empty game produces empty snapshot"""
        from katrain.core.eval_metrics import snapshot_from_game

        game = StubGame(root=StubGameNode(move=None, children=[]))

        snapshot = snapshot_from_game(game)

        assert len(snapshot.moves) == 0


# ---------------------------------------------------------------------------
# Regression Tests: move_number and Avg Loss calculations
# ---------------------------------------------------------------------------


class TestMoveNumberNotAllZero:
    """
    Regression tests to ensure move_number is correctly populated from depth.

    Bug fixed: GameNode.move_number was always 0 (never updated).
    Solution: move_eval_from_node() now prioritizes depth over move_number.
    """

    def test_move_numbers_are_sequential(self):
        """Move numbers should be sequential (1, 2, 3, ...)"""
        from katrain.core.eval_metrics import snapshot_from_game

        game = build_stub_game_tree([
            ("B", (3, 3), 1.0),
            ("W", (15, 15), -1.0),
            ("B", (3, 15), 0.5),
            ("W", (15, 3), -0.5),
            ("B", (9, 9), 0.0),
        ])

        snapshot = snapshot_from_game(game)

        # All move numbers should be sequential
        move_numbers = [m.move_number for m in snapshot.moves]
        assert move_numbers == [1, 2, 3, 4, 5], f"Expected [1,2,3,4,5], got {move_numbers}"

    def test_move_numbers_not_all_zero(self):
        """Move numbers should NOT all be 0 (regression check)"""
        from katrain.core.eval_metrics import snapshot_from_game

        game = build_stub_game_tree([
            ("B", (3, 3), 1.0),
            ("W", (15, 15), -2.0),
            ("B", (3, 15), 0.5),
        ])

        snapshot = snapshot_from_game(game)

        move_numbers = [m.move_number for m in snapshot.moves]

        # At least one move_number should be non-zero
        assert any(n != 0 for n in move_numbers), (
            f"All move_numbers are 0: {move_numbers}. "
            "This indicates depth is not being used correctly."
        )

        # In fact, none should be 0 for moves after the root
        assert all(n > 0 for n in move_numbers), (
            f"Some move_numbers are 0: {move_numbers}. "
            "All moves after root should have move_number > 0."
        )

    def test_single_move_has_move_number_1(self):
        """Single move should have move_number = 1"""
        from katrain.core.eval_metrics import snapshot_from_game

        game = build_stub_game_tree([
            ("B", (3, 3), 1.0),
        ])

        snapshot = snapshot_from_game(game)

        assert len(snapshot.moves) == 1
        assert snapshot.moves[0].move_number == 1


class TestAvgLossUsesCanonicalLoss:
    """
    Tests to ensure Avg Loss calculations use canonical loss (>= 0).

    Canonical loss = max(0, points_lost) via get_canonical_loss_from_move().
    This prevents negative losses from skewing averages.
    """

    def test_avg_loss_per_category_is_non_negative(self):
        """Average loss per category should never be negative"""
        from katrain.core.eval_metrics import (
            get_canonical_loss_from_move,
            EvalSnapshot,
        )

        # Create moves with various losses including negative (good moves)
        moves = [
            make_move_eval(move_number=1, player="B", gtp="D4",
                           points_lost=-1.0, score_loss=0.0,  # Good move
                           mistake_category=MistakeCategory.GOOD),
            make_move_eval(move_number=2, player="B", gtp="Q16",
                           points_lost=3.0, score_loss=3.0,  # Mistake
                           mistake_category=MistakeCategory.MISTAKE),
            make_move_eval(move_number=3, player="B", gtp="D16",
                           points_lost=-0.5, score_loss=0.0,  # Good move
                           mistake_category=MistakeCategory.GOOD),
            make_move_eval(move_number=4, player="B", gtp="Q4",
                           points_lost=1.5, score_loss=1.5,  # Inaccuracy
                           mistake_category=MistakeCategory.INACCURACY),
        ]

        # Verify canonical loss is always >= 0
        for m in moves:
            canonical_loss = get_canonical_loss_from_move(m)
            assert canonical_loss >= 0, f"Canonical loss should be >= 0, got {canonical_loss}"

    def test_avg_loss_matches_sum_divided_by_count(self):
        """
        Average loss = sum(canonical_loss) / count for each category.

        This test verifies the expected behavior for the _build_summary_from_stats function.
        """
        from katrain.core.eval_metrics import get_canonical_loss_from_move

        # Create moves with known losses
        moves = [
            # GOOD moves: canonical loss = 0 (because points_lost is negative)
            make_move_eval(move_number=1, player="B", gtp="D4",
                           points_lost=-1.0, score_loss=0.0,
                           mistake_category=MistakeCategory.GOOD),
            make_move_eval(move_number=2, player="B", gtp="Q16",
                           points_lost=-0.2, score_loss=0.0,
                           mistake_category=MistakeCategory.GOOD),
            make_move_eval(move_number=3, player="B", gtp="D16",
                           points_lost=0.3, score_loss=0.3,
                           mistake_category=MistakeCategory.GOOD),
            # MISTAKE moves: canonical loss = score_loss
            make_move_eval(move_number=4, player="B", gtp="Q4",
                           points_lost=3.0, score_loss=3.0,
                           mistake_category=MistakeCategory.MISTAKE),
            make_move_eval(move_number=5, player="B", gtp="K10",
                           points_lost=4.0, score_loss=4.0,
                           mistake_category=MistakeCategory.MISTAKE),
        ]

        # Calculate expected avg loss per category
        # GOOD: (0 + 0 + 0.3) / 3 = 0.1
        # MISTAKE: (3.0 + 4.0) / 2 = 3.5

        good_moves = [m for m in moves if m.mistake_category == MistakeCategory.GOOD]
        mistake_moves = [m for m in moves if m.mistake_category == MistakeCategory.MISTAKE]

        good_total = sum(get_canonical_loss_from_move(m) for m in good_moves)
        mistake_total = sum(get_canonical_loss_from_move(m) for m in mistake_moves)

        expected_good_avg = good_total / len(good_moves) if good_moves else 0
        expected_mistake_avg = mistake_total / len(mistake_moves) if mistake_moves else 0

        assert abs(expected_good_avg - 0.1) < 0.01, f"GOOD avg should be ~0.1, got {expected_good_avg}"
        assert abs(expected_mistake_avg - 3.5) < 0.01, f"MISTAKE avg should be ~3.5, got {expected_mistake_avg}"

    def test_canonical_loss_uses_score_loss_over_points_lost(self):
        """get_canonical_loss_from_move prefers score_loss over points_lost"""
        from katrain.core.eval_metrics import get_canonical_loss_from_move

        # score_loss is set, points_lost is negative
        m = make_move_eval(
            move_number=1,
            player="B",
            gtp="D4",
            points_lost=-2.0,  # Negative (good move)
            score_loss=0.0,    # Canonical = 0
        )
        assert get_canonical_loss_from_move(m) == 0.0

        # score_loss is not set, fall back to max(0, points_lost)
        m2 = make_move_eval(
            move_number=2,
            player="B",
            gtp="Q16",
            points_lost=3.5,   # Positive (bad move)
            score_loss=None,
        )
        assert get_canonical_loss_from_move(m2) == 3.5

        # Negative points_lost with no score_loss should give 0
        m3 = make_move_eval(
            move_number=3,
            player="B",
            gtp="D16",
            points_lost=-1.0,  # Negative (good move)
            score_loss=None,
        )
        assert get_canonical_loss_from_move(m3) == 0.0


class TestMistakeDistributionConsistency:
    """
    Regression tests to ensure Mistake Distribution Avg Loss matches
    Phase × Mistake table loss totals.

    Bug: Mistake Distribution Avg Loss used different loss metric than Phase table.
    Solution: Both now use get_canonical_loss_from_move() consistently.
    """

    def test_mistake_avg_loss_equals_phase_sum_divided_by_count(self):
        """
        Avg Loss for each category should equal:
        sum(phase_mistake_loss for all phases) / sum(phase_mistake_counts for all phases)
        """
        from katrain.core.eval_metrics import (
            SummaryStats,
            MistakeCategory,
            PositionDifficulty,
        )

        # Create a SummaryStats with known values
        stats = SummaryStats(
            player_name="TestPlayer",
            mistake_counts={
                MistakeCategory.GOOD: 100,
                MistakeCategory.INACCURACY: 20,
                MistakeCategory.MISTAKE: 5,
                MistakeCategory.BLUNDER: 2,
            },
            mistake_total_loss={
                MistakeCategory.GOOD: 5.0,      # Avg = 0.05
                MistakeCategory.INACCURACY: 30.0,  # Avg = 1.5
                MistakeCategory.MISTAKE: 17.5,     # Avg = 3.5
                MistakeCategory.BLUNDER: 12.0,     # Avg = 6.0
            },
            phase_mistake_counts={
                ("opening", MistakeCategory.GOOD): 30,
                ("opening", MistakeCategory.INACCURACY): 5,
                ("opening", MistakeCategory.MISTAKE): 1,
                ("opening", MistakeCategory.BLUNDER): 0,
                ("middle", MistakeCategory.GOOD): 60,
                ("middle", MistakeCategory.INACCURACY): 12,
                ("middle", MistakeCategory.MISTAKE): 3,
                ("middle", MistakeCategory.BLUNDER): 2,
                ("yose", MistakeCategory.GOOD): 10,
                ("yose", MistakeCategory.INACCURACY): 3,
                ("yose", MistakeCategory.MISTAKE): 1,
                ("yose", MistakeCategory.BLUNDER): 0,
            },
            phase_mistake_loss={
                ("opening", MistakeCategory.GOOD): 1.5,
                ("opening", MistakeCategory.INACCURACY): 7.5,
                ("opening", MistakeCategory.MISTAKE): 3.5,
                ("opening", MistakeCategory.BLUNDER): 0.0,
                ("middle", MistakeCategory.GOOD): 3.0,
                ("middle", MistakeCategory.INACCURACY): 18.0,
                ("middle", MistakeCategory.MISTAKE): 10.5,
                ("middle", MistakeCategory.BLUNDER): 12.0,
                ("yose", MistakeCategory.GOOD): 0.5,
                ("yose", MistakeCategory.INACCURACY): 4.5,
                ("yose", MistakeCategory.MISTAKE): 3.5,
                ("yose", MistakeCategory.BLUNDER): 0.0,
            },
        )

        # Verify phase counts sum to category counts
        for cat in MistakeCategory:
            phase_sum = sum(
                stats.phase_mistake_counts.get((phase, cat), 0)
                for phase in ["opening", "middle", "yose"]
            )
            assert phase_sum == stats.mistake_counts.get(cat, 0), (
                f"Phase counts for {cat} ({phase_sum}) != category count ({stats.mistake_counts.get(cat, 0)})"
            )

        # Verify phase losses sum to category losses
        for cat in MistakeCategory:
            phase_sum = sum(
                stats.phase_mistake_loss.get((phase, cat), 0.0)
                for phase in ["opening", "middle", "yose"]
            )
            expected = stats.mistake_total_loss.get(cat, 0.0)
            assert abs(phase_sum - expected) < 0.01, (
                f"Phase loss for {cat} ({phase_sum}) != category loss ({expected})"
            )

        # Verify Avg Loss calculation
        for cat in MistakeCategory:
            avg = stats.get_mistake_avg_loss(cat)
            count = stats.mistake_counts.get(cat, 0)
            total_loss = stats.mistake_total_loss.get(cat, 0.0)
            expected_avg = total_loss / count if count > 0 else 0.0
            assert abs(avg - expected_avg) < 0.01, (
                f"Avg loss for {cat} ({avg}) != expected ({expected_avg})"
            )

    def test_phase_sum_matches_total(self):
        """
        Sum of all phase losses should equal total_points_lost.
        """
        from katrain.core.eval_metrics import (
            SummaryStats,
            MistakeCategory,
        )

        stats = SummaryStats(
            player_name="TestPlayer",
            total_moves=50,
            total_points_lost=100.0,
            phase_loss={
                "opening": 20.0,
                "middle": 65.0,
                "yose": 15.0,
            },
        )

        phase_sum = sum(stats.phase_loss.values())
        assert abs(phase_sum - stats.total_points_lost) < 0.01, (
            f"Phase loss sum ({phase_sum}) != total_points_lost ({stats.total_points_lost})"
        )


# ---------------------------------------------------------------------------
# Test: Reason Tags Completeness (A1)
# ---------------------------------------------------------------------------

class TestReasonTagsCompleteness:
    """Tests to ensure all reason tags are properly defined (A1)."""

    def test_all_emittable_tags_have_labels(self):
        """Every tag that can be emitted must have a label."""
        from katrain.core.eval_metrics import (
            REASON_TAG_LABELS,
            VALID_REASON_TAGS,
            validate_reason_tag,
        )

        # Tags that get_reason_tags_for_move can emit (from board_analysis.py)
        emittable_tags = [
            "atari",
            "low_liberties",
            "cut_risk",
            "need_connect",
            "thin",
            "chase_mode",
            # "too_many_choices",  # Disabled but defined
            "endgame_hint",
            "heavy_loss",
            "reading_failure",
        ]

        # Tags used as fallback in game.py
        fallback_tags = ["unknown"]

        all_used_tags = emittable_tags + fallback_tags

        for tag in all_used_tags:
            assert tag in REASON_TAG_LABELS, f"Tag '{tag}' is used but not in REASON_TAG_LABELS"
            assert validate_reason_tag(tag), f"validate_reason_tag('{tag}') should return True"

    def test_validate_reason_tag_function(self):
        """validate_reason_tag should correctly identify valid/invalid tags."""
        from katrain.core.eval_metrics import validate_reason_tag

        # Valid tags
        assert validate_reason_tag("atari") is True
        assert validate_reason_tag("unknown") is True
        assert validate_reason_tag("heavy_loss") is True

        # Invalid tags
        assert validate_reason_tag("undefined_tag") is False
        assert validate_reason_tag("") is False
        assert validate_reason_tag("ATARI") is False  # Case-sensitive

    def test_get_reason_tag_label_function(self):
        """get_reason_tag_label should return correct labels."""
        from katrain.core.eval_metrics import get_reason_tag_label

        # Known tags
        assert get_reason_tag_label("atari") == "アタリ (atari)"
        assert get_reason_tag_label("unknown") == "不明 (unknown)"

        # Unknown tag with fallback
        assert get_reason_tag_label("undefined") == "undefined"
        assert get_reason_tag_label("undefined", fallback_to_raw=False) == "??? (undefined)"

    def test_valid_reason_tags_matches_labels(self):
        """VALID_REASON_TAGS should exactly match REASON_TAG_LABELS keys."""
        from katrain.core.eval_metrics import REASON_TAG_LABELS, VALID_REASON_TAGS

        assert VALID_REASON_TAGS == set(REASON_TAG_LABELS.keys())

    def test_no_duplicate_labels(self):
        """Each tag should have a unique label."""
        from katrain.core.eval_metrics import REASON_TAG_LABELS

        labels = list(REASON_TAG_LABELS.values())
        unique_labels = set(labels)

        assert len(labels) == len(unique_labels), "Duplicate labels found in REASON_TAG_LABELS"


# ---------------------------------------------------------------------------
# Test: 5-level Skill Presets
# ---------------------------------------------------------------------------

class TestSkillPresets:
    """Tests for SKILL_PRESETS configuration (5-level system)."""

    def test_all_five_presets_exist(self):
        """All 5 skill presets should be defined."""
        from katrain.core.eval_metrics import SKILL_PRESETS

        expected_keys = {"relaxed", "beginner", "standard", "advanced", "pro"}
        assert set(SKILL_PRESETS.keys()) == expected_keys

    def test_standard_unchanged(self):
        """Standard preset should maintain backward-compatible values."""
        from katrain.core.eval_metrics import SKILL_PRESETS

        standard = SKILL_PRESETS["standard"]
        # Original standard thresholds must remain unchanged
        assert standard.score_thresholds == (1.0, 2.5, 5.0)
        assert standard.quiz.loss_threshold == 2.0

    def test_advanced_unchanged(self):
        """Advanced preset should maintain backward-compatible values."""
        from katrain.core.eval_metrics import SKILL_PRESETS

        advanced = SKILL_PRESETS["advanced"]
        # Advanced thresholds preserved from original implementation
        assert advanced.score_thresholds == (0.5, 1.5, 3.0)
        assert advanced.quiz.loss_threshold == 1.0

    def test_score_thresholds_follow_formula(self):
        """New presets (relaxed, beginner, pro) should follow t1=0.2*t3, t2=0.5*t3 formula."""
        from katrain.core.eval_metrics import SKILL_PRESETS

        # Only check formula for new presets (relaxed, beginner, pro)
        formula_presets = ["relaxed", "beginner", "pro"]
        for key in formula_presets:
            preset = SKILL_PRESETS[key]
            t1, t2, t3 = preset.score_thresholds
            assert abs(t1 - 0.2 * t3) < 0.01, f"{key}: t1 should be 0.2 * t3"
            assert abs(t2 - 0.5 * t3) < 0.01, f"{key}: t2 should be 0.5 * t3"

    def test_thresholds_increasing_strictness(self):
        """Presets should have decreasing t3 values from relaxed to pro (increasing strictness)."""
        from katrain.core.eval_metrics import SKILL_PRESETS

        order = ["relaxed", "beginner", "standard", "advanced", "pro"]
        prev_t3 = float("inf")
        for key in order:
            t3 = SKILL_PRESETS[key].score_thresholds[2]
            assert t3 < prev_t3, f"{key}: t3={t3} should be less than previous {prev_t3}"
            prev_t3 = t3

    def test_get_skill_preset_fallback(self):
        """Unknown preset names should fall back to 'standard'."""
        from katrain.core.eval_metrics import get_skill_preset, SKILL_PRESETS

        result = get_skill_preset("nonexistent")
        assert result == SKILL_PRESETS["standard"]

    def test_default_skill_preset_is_standard(self):
        """DEFAULT_SKILL_PRESET should be 'standard' for backward compatibility."""
        from katrain.core.eval_metrics import DEFAULT_SKILL_PRESET

        assert DEFAULT_SKILL_PRESET == "standard"

    def test_preset_t3_values(self):
        """Verify expected t3 (blunder) values for each preset."""
        from katrain.core.eval_metrics import SKILL_PRESETS

        expected_t3 = {
            "relaxed": 15.0,
            "beginner": 10.0,
            "standard": 5.0,
            "advanced": 3.0,
            "pro": 1.0,
        }
        for key, expected in expected_t3.items():
            actual = SKILL_PRESETS[key].score_thresholds[2]
            assert actual == expected, f"{key}: expected t3={expected}, got {actual}"


class TestUrgentMissConfigs:
    """Tests for URGENT_MISS_CONFIGS (5-level system)."""

    def test_all_five_configs_exist(self):
        """All 5 urgent miss configs should be defined."""
        from katrain.core.eval_metrics import URGENT_MISS_CONFIGS

        expected_keys = {"relaxed", "beginner", "standard", "advanced", "pro"}
        assert set(URGENT_MISS_CONFIGS.keys()) == expected_keys

    def test_threshold_loss_decreasing(self):
        """threshold_loss should decrease from relaxed to pro (stricter detection)."""
        from katrain.core.eval_metrics import URGENT_MISS_CONFIGS

        order = ["relaxed", "beginner", "standard", "advanced", "pro"]
        prev_threshold = float("inf")
        for key in order:
            threshold = URGENT_MISS_CONFIGS[key].threshold_loss
            assert threshold < prev_threshold, f"{key}: threshold should decrease"
            prev_threshold = threshold

    def test_min_consecutive_reasonable(self):
        """min_consecutive should be reasonable (2-5 range)."""
        from katrain.core.eval_metrics import URGENT_MISS_CONFIGS

        for key, config in URGENT_MISS_CONFIGS.items():
            assert 2 <= config.min_consecutive <= 5, f"{key}: min_consecutive out of range"
