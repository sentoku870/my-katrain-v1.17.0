"""Difficulty-assessment tests (Phase E-1).

Extracted from tests/test_karte_structure.py. Covers
:func:`_assess_difficulty_from_policy` and the EvalSnapshot
difficulty-stats fields populated by the karte pipeline.
"""

from __future__ import annotations

from unittest.mock import Mock

from katrain.core.analysis.logic_difficulty import _assess_difficulty_from_policy
from katrain.core.eval_metrics import (
    EvalSnapshot,
    MoveEval,
    PositionDifficulty,
    snapshot_from_nodes,
)


class TestPolicyBasedDifficulty:
    """Tests for policy-based difficulty assessment (Freedom estimation fallback)."""

    def test_empty_policy(self):
        """Empty policy should return UNKNOWN."""
        difficulty, score = _assess_difficulty_from_policy([])
        assert difficulty == PositionDifficulty.UNKNOWN
        assert score == 0.5

    def test_high_entropy_policy(self):
        """High entropy policy (distributed) should be EASY."""
        # Create a policy with many moves having similar probability
        policy = [0.05] * 19 + [0.05]  # 20 moves with 5% each
        difficulty, score = _assess_difficulty_from_policy(
            policy,
            entropy_easy_threshold=2.0,  # Lower threshold for test
            top5_easy_threshold=0.4,
        )
        # High entropy, low top5 mass -> should be easy
        assert difficulty in (PositionDifficulty.EASY, PositionDifficulty.NORMAL)

    def test_low_entropy_policy(self):
        """Low entropy policy (concentrated) should be HARD or ONLY_MOVE."""
        # Create a policy with one dominant move
        policy = [0.9] + [0.01] * 10
        difficulty, score = _assess_difficulty_from_policy(policy)
        assert difficulty in (PositionDifficulty.HARD, PositionDifficulty.ONLY_MOVE)
        assert score >= 0.8

    def test_only_move_detection(self):
        """Policy with single dominant move should be ONLY_MOVE."""
        # Create a policy where top move has >80% probability
        policy = [0.85] + [0.015] * 10
        difficulty, score = _assess_difficulty_from_policy(policy)
        assert difficulty == PositionDifficulty.ONLY_MOVE
        assert score == 1.0

    def test_normal_policy(self):
        """Moderate entropy policy should be NORMAL."""
        # Create a balanced policy
        policy = [0.3, 0.25, 0.2, 0.15, 0.1]
        difficulty, score = _assess_difficulty_from_policy(policy)
        # Should be somewhere in the middle
        assert difficulty in (
            PositionDifficulty.EASY,
            PositionDifficulty.NORMAL,
            PositionDifficulty.HARD,
        )


class TestEvalSnapshotDifficultyStats:
    """Tests for EvalSnapshot difficulty statistics."""

    def test_difficulty_unknown_count(self):
        """Should count UNKNOWN difficulties correctly."""
        moves = [
            MoveEval(
                move_number=1,
                player="B",
                gtp="D4",
                score_before=0.0,
                score_after=0.0,
                delta_score=0.0,
                winrate_before=0.5,
                winrate_after=0.5,
                delta_winrate=0.0,
                points_lost=0.0,
                realized_points_lost=None,
                root_visits=100,
                position_difficulty=PositionDifficulty.EASY,
            ),
            MoveEval(
                move_number=2,
                player="W",
                gtp="Q16",
                score_before=0.0,
                score_after=0.0,
                delta_score=0.0,
                winrate_before=0.5,
                winrate_after=0.5,
                delta_winrate=0.0,
                points_lost=0.0,
                realized_points_lost=None,
                root_visits=100,
                position_difficulty=PositionDifficulty.UNKNOWN,
            ),
            MoveEval(
                move_number=3,
                player="B",
                gtp="D16",
                score_before=0.0,
                score_after=0.0,
                delta_score=0.0,
                winrate_before=0.5,
                winrate_after=0.5,
                delta_winrate=0.0,
                points_lost=0.0,
                realized_points_lost=None,
                root_visits=100,
                position_difficulty=None,  # Also counts as UNKNOWN
            ),
        ]
        snapshot = EvalSnapshot(moves=moves)
        assert snapshot.difficulty_unknown_count == 2

    def test_difficulty_unknown_rate(self):
        """Should calculate UNKNOWN rate correctly."""
        moves = [
            MoveEval(
                move_number=1,
                player="B",
                gtp="D4",
                score_before=0.0,
                score_after=0.0,
                delta_score=0.0,
                winrate_before=0.5,
                winrate_after=0.5,
                delta_winrate=0.0,
                points_lost=0.0,
                realized_points_lost=None,
                root_visits=100,
                position_difficulty=PositionDifficulty.EASY,
            ),
            MoveEval(
                move_number=2,
                player="W",
                gtp="Q16",
                score_before=0.0,
                score_after=0.0,
                delta_score=0.0,
                winrate_before=0.5,
                winrate_after=0.5,
                delta_winrate=0.0,
                points_lost=0.0,
                realized_points_lost=None,
                root_visits=100,
                position_difficulty=PositionDifficulty.UNKNOWN,
            ),
        ]
        snapshot = EvalSnapshot(moves=moves)
        assert snapshot.difficulty_unknown_rate == 0.5

    def test_empty_snapshot_unknown_rate(self):
        """Empty snapshot should have 0.0 unknown rate."""
        snapshot = EvalSnapshot(moves=[])
        assert snapshot.difficulty_unknown_rate == 0.0

    def test_difficulty_distribution(self):
        """Should calculate difficulty distribution correctly."""
        moves = [
            MoveEval(
                move_number=1,
                player="B",
                gtp="D4",
                score_before=0.0,
                score_after=0.0,
                delta_score=0.0,
                winrate_before=0.5,
                winrate_after=0.5,
                delta_winrate=0.0,
                points_lost=0.0,
                realized_points_lost=None,
                root_visits=100,
                position_difficulty=PositionDifficulty.EASY,
            ),
            MoveEval(
                move_number=2,
                player="W",
                gtp="Q16",
                score_before=0.0,
                score_after=0.0,
                delta_score=0.0,
                winrate_before=0.5,
                winrate_after=0.5,
                delta_winrate=0.0,
                points_lost=0.0,
                realized_points_lost=None,
                root_visits=100,
                position_difficulty=PositionDifficulty.EASY,
            ),
            MoveEval(
                move_number=3,
                player="B",
                gtp="D16",
                score_before=0.0,
                score_after=0.0,
                delta_score=0.0,
                winrate_before=0.5,
                winrate_after=0.5,
                delta_winrate=0.0,
                points_lost=0.0,
                realized_points_lost=None,
                root_visits=100,
                position_difficulty=PositionDifficulty.HARD,
            ),
            MoveEval(
                move_number=4,
                player="W",
                gtp="Q4",
                score_before=0.0,
                score_after=0.0,
                delta_score=0.0,
                winrate_before=0.5,
                winrate_after=0.5,
                delta_winrate=0.0,
                points_lost=0.0,
                realized_points_lost=None,
                root_visits=100,
                position_difficulty=PositionDifficulty.ONLY_MOVE,
            ),
        ]
        snapshot = EvalSnapshot(moves=moves)
        dist = snapshot.difficulty_distribution
        assert dist[PositionDifficulty.EASY] == 2
        assert dist[PositionDifficulty.HARD] == 1
        assert dist[PositionDifficulty.ONLY_MOVE] == 1
        assert dist[PositionDifficulty.NORMAL] == 0
        assert dist[PositionDifficulty.UNKNOWN] == 0


class TestSnapshotFromNodesLoadAnalysis:
    """Tests for snapshot_from_nodes() calling load_analysis() correctly."""

    def test_load_analysis_called_for_analysis_from_sgf_nodes(self):
        """Should call load_analysis() on nodes with analysis_from_sgf=True."""
        # Create mock nodes
        node1 = Mock()
        node1.analysis_from_sgf = True
        node1.load_analysis = Mock()
        node1.move = None  # Will be skipped for eval but should still load
        node1.parent = None

        node2 = Mock()
        node2.analysis_from_sgf = True
        node2.load_analysis = Mock()
        node2.move = None
        node2.parent = node1

        # Call snapshot_from_nodes
        snapshot_from_nodes([node1, node2])

        # Verify load_analysis was called on both nodes
        node1.load_analysis.assert_called_once()
        node2.load_analysis.assert_called_once()

    def test_load_analysis_not_called_for_live_analysis_nodes(self):
        """Should NOT call load_analysis() on nodes without analysis_from_sgf."""
        # Create mock node without analysis_from_sgf
        node = Mock()
        node.analysis_from_sgf = False
        node.load_analysis = Mock()
        node.move = None
        node.parent = None

        snapshot_from_nodes([node])

        # load_analysis should NOT be called
        node.load_analysis.assert_not_called()

    def test_load_analysis_called_on_parent_nodes(self):
        """Should call load_analysis() on parent nodes with analysis_from_sgf."""
        # Create parent node with analysis_from_sgf
        parent = Mock()
        parent.analysis_from_sgf = True
        parent.load_analysis = Mock()
        parent.move = None
        parent.parent = None

        # Create child node without analysis_from_sgf
        child = Mock()
        child.analysis_from_sgf = False
        child.load_analysis = Mock()
        child.move = None
        child.parent = parent

        snapshot_from_nodes([child])

        # Parent's load_analysis should be called
        parent.load_analysis.assert_called_once()
        # Child's load_analysis should NOT be called
        child.load_analysis.assert_not_called()

    def test_load_analysis_deduplication(self):
        """Should call load_analysis() only once per node even if referenced multiple times."""
        # Create a parent node
        parent = Mock()
        parent.analysis_from_sgf = True
        parent.load_analysis = Mock()
        parent.move = None
        parent.parent = None

        # Create two child nodes sharing the same parent
        child1 = Mock()
        child1.analysis_from_sgf = True
        child1.load_analysis = Mock()
        child1.move = None
        child1.parent = parent

        child2 = Mock()
        child2.analysis_from_sgf = True
        child2.load_analysis = Mock()
        child2.move = None
        child2.parent = parent

        # Call snapshot_from_nodes with nodes that share a parent
        snapshot_from_nodes([parent, child1, child2])

        # Parent's load_analysis should be called exactly once (not 3 times)
        parent.load_analysis.assert_called_once()
        child1.load_analysis.assert_called_once()
        child2.load_analysis.assert_called_once()

    def test_load_analysis_not_called_if_method_missing(self):
        """Should safely handle nodes without load_analysis method."""
        # Create a node-like object without load_analysis method
        node = Mock(spec=["analysis_from_sgf", "move", "parent"])
        node.analysis_from_sgf = True
        node.move = None
        node.parent = None

        # Should not raise an error
        snapshot_from_nodes([node])
