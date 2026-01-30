"""
Tests for katrain/core/study/active_review.py

These tests ensure that:
1. is_review_ready() correctly validates node analysis state
2. ActiveReviewer.evaluate_guess() correctly grades user moves
3. Grade thresholds work correctly for different skill presets
4. score_loss is None (not inf) for NOT_IN_CANDIDATES
"""

import pytest
from unittest.mock import MagicMock, PropertyMock
from typing import List, Dict, Optional

from katrain.core.study.active_review import (
    MIN_RELIABLE_VISITS,
    GRADE_THRESHOLDS,
    GuessGrade,
    ReviewReadyResult,
    GuessEvaluation,
    is_review_ready,
    ActiveReviewer,
    _is_pass_move,
)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


def make_mock_node(
    analysis_exists: bool = True,
    root_visits: int = 200,
    candidate_moves: Optional[List[Dict]] = None,
    next_player: str = "B",
    ordered_children: Optional[List] = None,
) -> MagicMock:
    """Create a mock GameNode for testing.

    Args:
        analysis_exists: Whether analysis data exists
        root_visits: Number of root visits
        candidate_moves: List of candidate move dicts
        next_player: "B" or "W"
        ordered_children: List of child nodes (for game move comparison)
    """
    node = MagicMock()
    type(node).analysis_exists = PropertyMock(return_value=analysis_exists)
    type(node).root_visits = PropertyMock(return_value=root_visits)
    type(node).next_player = PropertyMock(return_value=next_player)

    if candidate_moves is None:
        candidate_moves = [
            {"move": "D4", "order": 0, "pointsLost": 0.0, "visits": 1000},
            {"move": "Q16", "order": 1, "pointsLost": 0.3, "visits": 500},
            {"move": "C3", "order": 2, "pointsLost": 1.5, "visits": 200},
        ]
    type(node).candidate_moves = PropertyMock(return_value=candidate_moves)

    if ordered_children is None:
        ordered_children = []
    type(node).ordered_children = PropertyMock(return_value=ordered_children)

    return node


def make_mock_child_node(move_gtp: str) -> MagicMock:
    """Create a mock child node with a move."""
    child = MagicMock()
    child.move = MagicMock()
    child.move.gtp.return_value = move_gtp
    return child


# ---------------------------------------------------------------------------
# Test: _is_pass_move helper
# ---------------------------------------------------------------------------


class TestIsPassMove:
    """Tests for _is_pass_move helper function."""

    def test_lowercase_pass(self):
        assert _is_pass_move("pass") is True

    def test_uppercase_pass(self):
        assert _is_pass_move("PASS") is True

    def test_mixed_case_pass(self):
        assert _is_pass_move("Pass") is True

    def test_regular_move(self):
        assert _is_pass_move("D4") is False

    def test_none(self):
        assert _is_pass_move(None) is False

    def test_empty_string(self):
        assert _is_pass_move("") is False


# ---------------------------------------------------------------------------
# Test: is_review_ready
# ---------------------------------------------------------------------------


class TestIsReviewReady:
    """Tests for is_review_ready function."""

    def test_ready_when_sufficient_analysis(self):
        """Node with good analysis should be ready."""
        node = make_mock_node(
            analysis_exists=True,
            root_visits=200,
        )
        result = is_review_ready(node)
        assert result.ready is True
        assert result.message_key == ""
        assert result.visits == 200

    def test_not_ready_when_no_node(self):
        """None node should not be ready."""
        result = is_review_ready(None)
        assert result.ready is False
        assert result.message_key == "active_review:no_node"

    def test_not_ready_when_no_analysis(self):
        """Node without analysis should not be ready."""
        node = make_mock_node(analysis_exists=False)
        result = is_review_ready(node)
        assert result.ready is False
        assert result.message_key == "active_review:analysis_required"

    def test_not_ready_when_low_visits(self):
        """Node with insufficient visits should not be ready."""
        node = make_mock_node(root_visits=50)
        result = is_review_ready(node)
        assert result.ready is False
        assert result.message_key == "active_review:analysis_low_visits"
        assert result.visits == 50

    def test_not_ready_when_no_candidates(self):
        """Node without candidate moves should not be ready."""
        node = make_mock_node(candidate_moves=[])
        result = is_review_ready(node)
        assert result.ready is False
        assert result.message_key == "active_review:no_candidates"

    def test_not_ready_when_best_is_pass(self):
        """Node where best move is pass should not be ready."""
        node = make_mock_node(
            candidate_moves=[
                {"move": "pass", "order": 0, "pointsLost": 0.0},
            ]
        )
        result = is_review_ready(node)
        assert result.ready is False
        assert result.message_key == "active_review:best_is_pass"

    def test_ready_when_pass_is_not_best(self):
        """Node where pass is a candidate but not best should be ready."""
        node = make_mock_node(
            candidate_moves=[
                {"move": "D4", "order": 0, "pointsLost": 0.0},
                {"move": "pass", "order": 1, "pointsLost": 5.0},
            ]
        )
        result = is_review_ready(node)
        assert result.ready is True

    def test_min_reliable_visits_threshold(self):
        """Test the exact threshold for MIN_RELIABLE_VISITS."""
        # Just below threshold
        node = make_mock_node(root_visits=MIN_RELIABLE_VISITS - 1)
        result = is_review_ready(node)
        assert result.ready is False

        # Exactly at threshold
        node = make_mock_node(root_visits=MIN_RELIABLE_VISITS)
        result = is_review_ready(node)
        assert result.ready is True


# ---------------------------------------------------------------------------
# Test: ActiveReviewer.evaluate_guess
# ---------------------------------------------------------------------------


class TestActiveReviewer:
    """Tests for ActiveReviewer class."""

    def test_perfect_when_order_zero(self):
        """Guessing the best move should get PERFECT grade."""
        node = make_mock_node(
            candidate_moves=[
                {"move": "D4", "order": 0, "pointsLost": 0.0, "visits": 1000},
                {"move": "Q16", "order": 1, "pointsLost": 0.5, "visits": 500},
            ]
        )
        reviewer = ActiveReviewer("standard")

        # Mock Move.gtp() to return "D4" for coords (3, 3)
        with pytest.MonkeyPatch().context() as m:
            mock_move = MagicMock()
            mock_move.gtp.return_value = "D4"
            m.setattr(
                "katrain.core.sgf_parser.Move",
                lambda coords, player: mock_move,
            )

            result = reviewer.evaluate_guess((3, 3), node)

        assert result.grade == GuessGrade.PERFECT
        assert result.score_loss == 0.0
        assert result.policy_rank == 1

    def test_excellent_grade(self):
        """Move with small loss should get EXCELLENT grade."""
        node = make_mock_node(
            candidate_moves=[
                {"move": "D4", "order": 0, "pointsLost": 0.0, "visits": 1000},
                {"move": "Q16", "order": 1, "pointsLost": 0.3, "visits": 500},
            ]
        )
        reviewer = ActiveReviewer("standard")  # excellent threshold = 0.5

        with pytest.MonkeyPatch().context() as m:
            mock_move = MagicMock()
            mock_move.gtp.return_value = "Q16"
            m.setattr(
                "katrain.core.sgf_parser.Move",
                lambda coords, player: mock_move,
            )

            result = reviewer.evaluate_guess((15, 15), node)

        assert result.grade == GuessGrade.EXCELLENT
        assert result.score_loss == 0.3
        assert result.policy_rank == 2

    def test_not_in_candidates(self):
        """Move not in candidates should get NOT_IN_CANDIDATES grade."""
        node = make_mock_node(
            candidate_moves=[
                {"move": "D4", "order": 0, "pointsLost": 0.0, "visits": 1000},
            ]
        )
        reviewer = ActiveReviewer("standard")

        with pytest.MonkeyPatch().context() as m:
            mock_move = MagicMock()
            mock_move.gtp.return_value = "A1"  # Not in candidates
            m.setattr(
                "katrain.core.sgf_parser.Move",
                lambda coords, player: mock_move,
            )

            result = reviewer.evaluate_guess((0, 0), node)

        assert result.grade == GuessGrade.NOT_IN_CANDIDATES
        assert result.policy_rank is None

    def test_not_in_candidates_score_loss_is_none(self):
        """NOT_IN_CANDIDATES should have score_loss=None, not inf."""
        node = make_mock_node(
            candidate_moves=[
                {"move": "D4", "order": 0, "pointsLost": 0.0, "visits": 1000},
            ]
        )
        reviewer = ActiveReviewer("standard")

        with pytest.MonkeyPatch().context() as m:
            mock_move = MagicMock()
            mock_move.gtp.return_value = "A1"
            m.setattr(
                "katrain.core.sgf_parser.Move",
                lambda coords, player: mock_move,
            )

            result = reviewer.evaluate_guess((0, 0), node)

        # Critical: score_loss should be None, not float('inf')
        assert result.score_loss is None

    def test_matches_game_move(self):
        """Should detect when guess matches actual game continuation."""
        child = make_mock_child_node("Q16")
        node = make_mock_node(
            candidate_moves=[
                {"move": "D4", "order": 0, "pointsLost": 0.0, "visits": 1000},
                {"move": "Q16", "order": 1, "pointsLost": 0.5, "visits": 500},
            ],
            ordered_children=[child],
        )
        reviewer = ActiveReviewer("standard")

        with pytest.MonkeyPatch().context() as m:
            mock_move = MagicMock()
            mock_move.gtp.return_value = "Q16"
            m.setattr(
                "katrain.core.sgf_parser.Move",
                lambda coords, player: mock_move,
            )

            result = reviewer.evaluate_guess((15, 15), node)

        assert result.matches_game_move is True

    def test_does_not_match_game_move(self):
        """Should detect when guess differs from actual game continuation."""
        child = make_mock_child_node("C3")
        node = make_mock_node(
            candidate_moves=[
                {"move": "D4", "order": 0, "pointsLost": 0.0, "visits": 1000},
                {"move": "Q16", "order": 1, "pointsLost": 0.5, "visits": 500},
            ],
            ordered_children=[child],
        )
        reviewer = ActiveReviewer("standard")

        with pytest.MonkeyPatch().context() as m:
            mock_move = MagicMock()
            mock_move.gtp.return_value = "D4"
            m.setattr(
                "katrain.core.sgf_parser.Move",
                lambda coords, player: mock_move,
            )

            result = reviewer.evaluate_guess((3, 3), node)

        assert result.matches_game_move is False

    def test_uses_precomputed_pointsLost(self):
        """Should use pre-computed pointsLost from candidate_moves."""
        node = make_mock_node(
            candidate_moves=[
                {"move": "D4", "order": 0, "pointsLost": 0.0, "visits": 1000},
                {"move": "Q16", "order": 1, "pointsLost": 2.5, "visits": 500},
            ]
        )
        reviewer = ActiveReviewer("standard")

        with pytest.MonkeyPatch().context() as m:
            mock_move = MagicMock()
            mock_move.gtp.return_value = "Q16"
            m.setattr(
                "katrain.core.sgf_parser.Move",
                lambda coords, player: mock_move,
            )

            result = reviewer.evaluate_guess((15, 15), node)

        # Should use the pre-computed value, not calculate it
        assert result.score_loss == 2.5


# ---------------------------------------------------------------------------
# Test: Grade Thresholds
# ---------------------------------------------------------------------------


class TestGradeThresholds:
    """Tests for grade threshold configuration."""

    def test_all_presets_valid(self):
        """All presets should have required threshold keys."""
        required_keys = {"excellent", "good", "blunder"}
        for preset_name, thresholds in GRADE_THRESHOLDS.items():
            assert set(thresholds.keys()) == required_keys, f"Preset {preset_name} missing keys"

    def test_thresholds_ordered(self):
        """Thresholds should be in order: excellent < good < blunder."""
        for preset_name, thresholds in GRADE_THRESHOLDS.items():
            assert thresholds["excellent"] < thresholds["good"], f"Preset {preset_name}: excellent >= good"
            assert thresholds["good"] < thresholds["blunder"], f"Preset {preset_name}: good >= blunder"

    def test_beginner_preset_lenient(self):
        """Beginner preset should have higher thresholds than standard."""
        assert GRADE_THRESHOLDS["beginner"]["blunder"] > GRADE_THRESHOLDS["standard"]["blunder"]

    def test_pro_preset_strict(self):
        """Pro preset should have lower thresholds than standard."""
        assert GRADE_THRESHOLDS["pro"]["blunder"] < GRADE_THRESHOLDS["standard"]["blunder"]


# ---------------------------------------------------------------------------
# Test: Grade determination per preset
# ---------------------------------------------------------------------------


class TestGradeThresholdsPerPreset:
    """Tests for grade determination with different presets."""

    @pytest.mark.parametrize(
        "preset,loss,expected_grade",
        [
            # Standard preset
            ("standard", 0.3, GuessGrade.EXCELLENT),  # < 0.5
            ("standard", 0.6, GuessGrade.GOOD),  # 0.5 <= x < 2.0
            ("standard", 2.5, GuessGrade.SLACK),  # 2.0 <= x < 5.0
            ("standard", 6.0, GuessGrade.BLUNDER),  # >= 5.0
            # Beginner preset (more lenient)
            ("beginner", 1.0, GuessGrade.EXCELLENT),  # < 1.5
            ("beginner", 3.0, GuessGrade.GOOD),  # 1.5 <= x < 4.0
            ("beginner", 6.0, GuessGrade.SLACK),  # 4.0 <= x < 8.0
            ("beginner", 10.0, GuessGrade.BLUNDER),  # >= 8.0
            # Pro preset (strict)
            ("pro", 0.1, GuessGrade.EXCELLENT),  # < 0.2
            ("pro", 0.3, GuessGrade.GOOD),  # 0.2 <= x < 0.5
            ("pro", 1.0, GuessGrade.SLACK),  # 0.5 <= x < 2.0
            ("pro", 3.0, GuessGrade.BLUNDER),  # >= 2.0
        ],
    )
    def test_grade_per_preset(self, preset, loss, expected_grade):
        """Grade should match expected for given preset and loss."""
        reviewer = ActiveReviewer(preset)
        # order > 0 to avoid PERFECT grade
        grade = reviewer._determine_grade(loss, order=1)
        assert grade == expected_grade


# ---------------------------------------------------------------------------
# Test: Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module constants."""

    def test_min_reliable_visits_positive(self):
        """MIN_RELIABLE_VISITS should be positive."""
        assert MIN_RELIABLE_VISITS > 0

    def test_min_reliable_visits_value(self):
        """MIN_RELIABLE_VISITS should be 100 as documented."""
        assert MIN_RELIABLE_VISITS == 100
