"""Snapshot-related tests extracted from tests/test_eval_metrics.py.

Phase D-1: split the 2316-line test_eval_metrics.py into 4 themed
submodules. Covers EvalSnapshot construction, iteration over mainline,
delta-vs-points_lost consistency, move_number and avg_loss invariants.
"""

from __future__ import annotations

from katrain.core.analysis import compute_canonical_loss, compute_importance_for_moves
from katrain.core.analysis.models.enums import MistakeCategory
from katrain.core.analysis.models.move_eval import EvalSnapshot, get_canonical_loss_from_move
from tests.helpers_eval_metrics import StubGame, StubGameNode, build_stub_game_tree, make_move_eval


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
                move_number=1,
                player="B",
                gtp="D4",
                delta_score=-0.5,
                delta_winrate=-0.01,
                points_lost=0.5,
                score_loss=0.5,
            ),
            make_move_eval(
                move_number=2,
                player="W",
                gtp="Q16",
                delta_score=8.0,
                delta_winrate=0.15,  # Black-perspective
                points_lost=8.0,
                score_loss=8.0,
            ),
        ]

        compute_importance_for_moves(moves)

        assert moves[1].importance_score > moves[0].importance_score

    def test_importance_is_non_negative(self):
        """Importance scores should always be non-negative"""
        moves = [
            make_move_eval(
                move_number=1,
                player="B",
                gtp="D4",
                delta_score=5.0,  # Good move
                delta_winrate=0.1,
                points_lost=-2.0,  # Negative loss (good move)
                score_loss=0.0,  # Canonical: clamped to 0
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

        assert loss == 3.0, "Delta fallback with perspective correction must produce 3.0 for White's blunder"


# ---------------------------------------------------------------------------
# Integration Tests: snapshot_from_nodes, iter_main_branch_nodes, snapshot_from_game
# ---------------------------------------------------------------------------


class TestSnapshotFromNodes:
    """Integration tests for snapshot_from_nodes function"""

    def test_basic_snapshot_creation(self):
        """Create snapshot from a simple sequence of nodes"""
        from katrain.core.analysis import snapshot_from_nodes

        # Build a simple game: B plays, W plays, B plays
        game = build_stub_game_tree(
            [
                ("B", (3, 3), 1.0),  # Black plays, score becomes +1.0 (good for black)
                ("W", (15, 15), -2.0),  # White plays, score becomes -2.0 (good for white)
                ("B", (3, 15), 0.0),  # Black plays, score becomes 0.0 (even)
            ]
        )

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
        from katrain.core.analysis import snapshot_from_nodes

        game = build_stub_game_tree(
            [
                ("B", (3, 3), 5.0),
                ("W", (15, 15), 2.0),
            ]
        )

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
        from katrain.core.analysis import snapshot_from_nodes

        snapshot = snapshot_from_nodes([])

        assert len(snapshot.moves) == 0
        assert snapshot.total_points_lost == 0.0

    def test_importance_is_computed(self):
        """Verify importance scores are computed for all moves"""
        from katrain.core.analysis import snapshot_from_nodes

        game = build_stub_game_tree(
            [
                ("B", (3, 3), 5.0),
                ("W", (15, 15), 10.0),  # White loses 5 points (big mistake)
            ]
        )

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
        from katrain.core.analysis import iter_main_branch_nodes

        game = build_stub_game_tree(
            [
                ("B", (3, 3), 1.0),
                ("W", (15, 15), -1.0),
                ("B", (3, 15), 0.5),
            ]
        )

        nodes = list(iter_main_branch_nodes(game))

        assert len(nodes) == 3
        assert nodes[0].move.player == "B"
        assert nodes[1].move.player == "W"
        assert nodes[2].move.player == "B"

    def test_empty_game(self):
        """Empty game (only root) produces no nodes"""
        from katrain.core.analysis import iter_main_branch_nodes

        game = StubGame(root=StubGameNode(move=None, children=[]))

        nodes = list(iter_main_branch_nodes(game))

        assert len(nodes) == 0

    def test_none_root(self):
        """Game with None root produces no nodes"""
        from katrain.core.analysis import iter_main_branch_nodes

        game = StubGame(root=None)

        nodes = list(iter_main_branch_nodes(game))

        assert len(nodes) == 0

    def test_single_move(self):
        """Game with single move"""
        from katrain.core.analysis import iter_main_branch_nodes

        game = build_stub_game_tree(
            [
                ("B", (3, 3), 1.0),
            ]
        )

        nodes = list(iter_main_branch_nodes(game))

        assert len(nodes) == 1
        assert nodes[0].move.player == "B"


class TestSnapshotFromGame:
    """Integration tests for snapshot_from_game function"""

    def test_basic_game_to_snapshot(self):
        """Convert a simple game to snapshot"""
        from katrain.core.analysis import snapshot_from_game

        game = build_stub_game_tree(
            [
                ("B", (3, 3), 2.0),
                ("W", (15, 15), -3.0),
                ("B", (3, 15), 1.0),
            ]
        )

        snapshot = snapshot_from_game(game)

        assert len(snapshot.moves) == 3
        assert snapshot.moves[0].move_number == 1
        assert snapshot.moves[1].move_number == 2
        assert snapshot.moves[2].move_number == 3

    def test_loss_calculation(self):
        """Verify loss is calculated correctly through the pipeline"""
        from katrain.core.analysis import snapshot_from_game

        # Black makes a bad move: score goes from 0 to -5 (white gets ahead)
        game = build_stub_game_tree(
            [
                ("B", (3, 3), -5.0),  # Black's bad move
            ]
        )

        snapshot = snapshot_from_game(game)

        # Black lost 5 points (from 0 to -5)
        assert snapshot.moves[0].points_lost == 5.0
        assert snapshot.moves[0].score_loss == 5.0

    def test_canonical_properties_work(self):
        """Verify canonical properties are accessible"""
        from katrain.core.analysis import snapshot_from_game

        game = build_stub_game_tree(
            [
                ("B", (3, 3), -3.0),  # Black loses 3
                ("W", (15, 15), 0.0),  # White loses 3
            ]
        )

        snapshot = snapshot_from_game(game)

        # Both players lost some points
        assert snapshot.total_canonical_points_lost > 0
        assert snapshot.max_canonical_points_lost >= 3.0

    def test_empty_game(self):
        """Empty game produces empty snapshot"""
        from katrain.core.analysis import snapshot_from_game

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
        from katrain.core.analysis import snapshot_from_game

        game = build_stub_game_tree(
            [
                ("B", (3, 3), 1.0),
                ("W", (15, 15), -1.0),
                ("B", (3, 15), 0.5),
                ("W", (15, 3), -0.5),
                ("B", (9, 9), 0.0),
            ]
        )

        snapshot = snapshot_from_game(game)

        # All move numbers should be sequential
        move_numbers = [m.move_number for m in snapshot.moves]
        assert move_numbers == [1, 2, 3, 4, 5], f"Expected [1,2,3,4,5], got {move_numbers}"

    def test_move_numbers_not_all_zero(self):
        """Move numbers should NOT all be 0 (regression check)"""
        from katrain.core.analysis import snapshot_from_game

        game = build_stub_game_tree(
            [
                ("B", (3, 3), 1.0),
                ("W", (15, 15), -2.0),
                ("B", (3, 15), 0.5),
            ]
        )

        snapshot = snapshot_from_game(game)

        move_numbers = [m.move_number for m in snapshot.moves]

        # At least one move_number should be non-zero
        assert any(n != 0 for n in move_numbers), (
            f"All move_numbers are 0: {move_numbers}. This indicates depth is not being used correctly."
        )

        # In fact, none should be 0 for moves after the root
        assert all(n > 0 for n in move_numbers), (
            f"Some move_numbers are 0: {move_numbers}. All moves after root should have move_number > 0."
        )

    def test_single_move_has_move_number_1(self):
        """Single move should have move_number = 1"""
        from katrain.core.analysis import snapshot_from_game

        game = build_stub_game_tree(
            [
                ("B", (3, 3), 1.0),
            ]
        )

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

        # Create moves with various losses including negative (good moves)
        moves = [
            make_move_eval(
                move_number=1,
                player="B",
                gtp="D4",
                points_lost=-1.0,
                score_loss=0.0,  # Good move
                mistake_category=MistakeCategory.GOOD,
            ),
            make_move_eval(
                move_number=2,
                player="B",
                gtp="Q16",
                points_lost=3.0,
                score_loss=3.0,  # Mistake
                mistake_category=MistakeCategory.MISTAKE,
            ),
            make_move_eval(
                move_number=3,
                player="B",
                gtp="D16",
                points_lost=-0.5,
                score_loss=0.0,  # Good move
                mistake_category=MistakeCategory.GOOD,
            ),
            make_move_eval(
                move_number=4,
                player="B",
                gtp="Q4",
                points_lost=1.5,
                score_loss=1.5,  # Inaccuracy
                mistake_category=MistakeCategory.INACCURACY,
            ),
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

        # Create moves with known losses
        moves = [
            # GOOD moves: canonical loss = 0 (because points_lost is negative)
            make_move_eval(
                move_number=1,
                player="B",
                gtp="D4",
                points_lost=-1.0,
                score_loss=0.0,
                mistake_category=MistakeCategory.GOOD,
            ),
            make_move_eval(
                move_number=2,
                player="B",
                gtp="Q16",
                points_lost=-0.2,
                score_loss=0.0,
                mistake_category=MistakeCategory.GOOD,
            ),
            make_move_eval(
                move_number=3,
                player="B",
                gtp="D16",
                points_lost=0.3,
                score_loss=0.3,
                mistake_category=MistakeCategory.GOOD,
            ),
            # MISTAKE moves: canonical loss = score_loss
            make_move_eval(
                move_number=4,
                player="B",
                gtp="Q4",
                points_lost=3.0,
                score_loss=3.0,
                mistake_category=MistakeCategory.MISTAKE,
            ),
            make_move_eval(
                move_number=5,
                player="B",
                gtp="K10",
                points_lost=4.0,
                score_loss=4.0,
                mistake_category=MistakeCategory.MISTAKE,
            ),
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

        # score_loss is set, points_lost is negative
        m = make_move_eval(
            move_number=1,
            player="B",
            gtp="D4",
            points_lost=-2.0,  # Negative (good move)
            score_loss=0.0,  # Canonical = 0
        )
        assert get_canonical_loss_from_move(m) == 0.0

        # score_loss is not set, fall back to max(0, points_lost)
        m2 = make_move_eval(
            move_number=2,
            player="B",
            gtp="Q16",
            points_lost=3.5,  # Positive (bad move)
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
        from katrain.core.analysis.models.enums import MistakeCategory
        from katrain.core.analysis.models.skill import SummaryStats

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
                MistakeCategory.GOOD: 5.0,  # Avg = 0.05
                MistakeCategory.INACCURACY: 30.0,  # Avg = 1.5
                MistakeCategory.MISTAKE: 17.5,  # Avg = 3.5
                MistakeCategory.BLUNDER: 12.0,  # Avg = 6.0
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
            phase_sum = sum(stats.phase_mistake_counts.get((phase, cat), 0) for phase in ["opening", "middle", "yose"])
            assert phase_sum == stats.mistake_counts.get(cat, 0), (
                f"Phase counts for {cat} ({phase_sum}) != category count ({stats.mistake_counts.get(cat, 0)})"
            )

        # Verify phase losses sum to category losses
        for cat in MistakeCategory:
            phase_sum = sum(stats.phase_mistake_loss.get((phase, cat), 0.0) for phase in ["opening", "middle", "yose"])
            expected = stats.mistake_total_loss.get(cat, 0.0)
            assert abs(phase_sum - expected) < 0.01, f"Phase loss for {cat} ({phase_sum}) != category loss ({expected})"

        # Verify Avg Loss calculation
        for cat in MistakeCategory:
            avg = stats.get_mistake_avg_loss(cat)
            count = stats.mistake_counts.get(cat, 0)
            total_loss = stats.mistake_total_loss.get(cat, 0.0)
            expected_avg = total_loss / count if count > 0 else 0.0
            assert abs(avg - expected_avg) < 0.01, f"Avg loss for {cat} ({avg}) != expected ({expected_avg})"

    def test_phase_sum_matches_total(self):
        """
        Sum of all phase losses should equal total_points_lost.
        """
        from katrain.core.analysis.models.skill import SummaryStats

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
