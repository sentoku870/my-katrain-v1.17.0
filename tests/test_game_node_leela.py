"""Tests for GameNode Leela analysis support."""

from katrain.core.game_node import GameNode
from katrain.core.leela.models import LeelaCandidate, LeelaPositionEval


class TestGameNodeLeelaAnalysis:
    """Tests for Leela analysis storage in GameNode."""

    def test_initial_leela_analysis_is_none(self):
        """Test that leela_analysis is None initially."""
        node = GameNode()
        assert node.leela_analysis is None

    def test_set_leela_analysis(self):
        """Test setting Leela analysis."""
        node = GameNode()

        candidates = [
            LeelaCandidate(move="D4", winrate=0.52, visits=100, loss_est=0.0),
            LeelaCandidate(move="Q16", winrate=0.48, visits=80, loss_est=2.0),
        ]
        eval_result = LeelaPositionEval(candidates=candidates)

        node.set_leela_analysis(eval_result)

        assert node.leela_analysis is not None
        assert node.leela_analysis.is_valid
        assert len(node.leela_analysis.candidates) == 2

    def test_clear_leela_analysis(self):
        """Test clearing Leela analysis."""
        node = GameNode()

        # Set first
        eval_result = LeelaPositionEval(candidates=[LeelaCandidate(move="D4", winrate=0.5, visits=100)])
        node.set_leela_analysis(eval_result)
        assert node.leela_analysis is not None

        # Clear
        node.clear_leela_analysis()
        assert node.leela_analysis is None

    def test_clear_analysis_also_clears_leela(self):
        """Test that clear_analysis() also clears Leela analysis."""
        node = GameNode()

        # Set Leela analysis
        eval_result = LeelaPositionEval(candidates=[LeelaCandidate(move="D4", winrate=0.5, visits=100)])
        node.set_leela_analysis(eval_result)
        assert node.leela_analysis is not None

        # Clear all analysis
        node.clear_analysis()
        assert node.leela_analysis is None

    def test_leela_analysis_independent_of_katago(self):
        """Test that Leela analysis is independent of KataGo analysis."""
        node = GameNode()

        # Set Leela analysis
        leela_result = LeelaPositionEval(candidates=[LeelaCandidate(move="D4", winrate=0.52, visits=100)])
        node.set_leela_analysis(leela_result)

        # KataGo analysis should still be default
        assert node.analysis == {
            "moves": {},
            "root": None,
            "ownership": None,
            "policy": None,
            "completed": False,
        }

        # Both should coexist
        assert node.leela_analysis is not None
        assert node.leela_analysis.candidates[0].move == "D4"

    def test_katago_analysis_independent_of_leela(self):
        """Test that KataGo analysis changes don't affect Leela analysis."""
        node = GameNode()

        # Set Leela analysis
        leela_result = LeelaPositionEval(candidates=[LeelaCandidate(move="D4", winrate=0.52, visits=100)])
        node.set_leela_analysis(leela_result)

        # Modify KataGo analysis
        node.analysis["completed"] = True
        node.analysis["root"] = {"winrate": 0.5}

        # Leela analysis should be unaffected
        assert node.leela_analysis.candidates[0].move == "D4"

    def test_leela_analysis_after_init(self):
        """Test accessing leela_analysis on new node without clear_analysis."""
        # Create node directly without calling clear_analysis
        node = GameNode.__new__(GameNode)
        # Don't call __init__, simulate incomplete initialization

        # Property should handle missing attribute gracefully
        # This tests the getattr fallback in leela_analysis property
        assert node.leela_analysis is None


class TestGameNodeRegressionKataGo:
    """Regression tests to ensure KataGo functionality is not affected."""

    def test_analysis_structure_unchanged(self):
        """Test that KataGo analysis structure is unchanged."""
        node = GameNode()

        expected_keys = {"moves", "root", "ownership", "policy", "completed"}
        assert set(node.analysis.keys()) == expected_keys

    def test_analysis_visits_requested(self):
        """Test that analysis_visits_requested is still 0 after init."""
        node = GameNode()
        assert node.analysis_visits_requested == 0

    def test_clear_analysis_resets_visits(self):
        """Test that clear_analysis resets visits."""
        node = GameNode()
        node.analysis_visits_requested = 1000
        node.clear_analysis()
        assert node.analysis_visits_requested == 0
