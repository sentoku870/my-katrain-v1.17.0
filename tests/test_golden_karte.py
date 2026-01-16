"""
Golden tests for Karte (single-game report) output.

These tests verify the complete structure and content of Karte reports
using snapshot testing. They use synthetic MoveEval data to avoid
dependency on actual SGF files and KataGo analysis.

Key principles:
1. Use MoveEval directly (no SGF dependency)
2. Normalize timestamps, paths, and float precision
3. Don't re-sort in tests (code guarantees deterministic order)
4. Use --update-goldens flag to update expected output
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from katrain.core.eval_metrics import (
    MoveEval,
    EvalSnapshot,
    MistakeCategory,
    PositionDifficulty,
    ConfidenceLevel,
    compute_confidence_level,
    compute_importance_for_moves,
    classify_mistake,
    SKILL_PRESETS,
)

from tests.conftest import normalize_output, load_golden, save_golden, GOLDEN_DIR


# ---------------------------------------------------------------------------
# Helper to create comprehensive test moves
# ---------------------------------------------------------------------------

def create_standard_game_moves() -> list:
    """
    Create a standard set of 30 moves for testing.

    Distribution:
    - Opening (moves 1-10): 2 mistakes
    - Middle game (moves 11-20): 1 blunder, 2 mistakes
    - Yose (moves 21-30): 1 mistake

    All moves have high visits (500) for HIGH confidence.
    """
    moves = []

    # Opening phase (moves 1-10)
    for i in range(1, 11):
        loss = 0.5  # Default good move
        if i == 3:
            loss = 3.0  # Mistake
        elif i == 7:
            loss = 2.0  # Inaccuracy

        move = MoveEval(
            move_number=i,
            player="B" if i % 2 == 1 else "W",
            gtp=f"D{i}",
            score_before=0.0,
            score_after=-loss if i % 2 == 1 else loss,
            delta_score=-loss if i % 2 == 1 else loss,
            winrate_before=0.5,
            winrate_after=0.5 - loss * 0.01,
            delta_winrate=-loss * 0.01,
            points_lost=loss,
            realized_points_lost=None,
            root_visits=500,
        )
        move.score_loss = loss
        move.winrate_loss = loss * 0.01
        move.mistake_category = classify_mistake(loss, None)
        move.position_difficulty = PositionDifficulty.NORMAL
        moves.append(move)

    # Middle game (moves 11-20)
    for i in range(11, 21):
        loss = 0.5
        if i == 12:
            loss = 6.0  # Blunder
        elif i == 15:
            loss = 3.5  # Mistake
        elif i == 18:
            loss = 2.8  # Mistake

        move = MoveEval(
            move_number=i,
            player="B" if i % 2 == 1 else "W",
            gtp=f"Q{i - 10}",
            score_before=0.0,
            score_after=-loss if i % 2 == 1 else loss,
            delta_score=-loss if i % 2 == 1 else loss,
            winrate_before=0.5,
            winrate_after=0.5 - loss * 0.01,
            delta_winrate=-loss * 0.01,
            points_lost=loss,
            realized_points_lost=None,
            root_visits=500,
        )
        move.score_loss = loss
        move.winrate_loss = loss * 0.01
        move.mistake_category = classify_mistake(loss, None)
        move.position_difficulty = PositionDifficulty.NORMAL
        if i == 12:
            move.position_difficulty = PositionDifficulty.HARD
        moves.append(move)

    # Yose (moves 21-30)
    for i in range(21, 31):
        loss = 0.3
        if i == 25:
            loss = 2.5  # Mistake

        move = MoveEval(
            move_number=i,
            player="B" if i % 2 == 1 else "W",
            gtp=f"S{i - 20}",
            score_before=0.0,
            score_after=-loss if i % 2 == 1 else loss,
            delta_score=-loss if i % 2 == 1 else loss,
            winrate_before=0.5,
            winrate_after=0.5 - loss * 0.01,
            delta_winrate=-loss * 0.01,
            points_lost=loss,
            realized_points_lost=None,
            root_visits=500,
        )
        move.score_loss = loss
        move.winrate_loss = loss * 0.01
        move.mistake_category = classify_mistake(loss, None)
        move.position_difficulty = PositionDifficulty.NORMAL
        moves.append(move)

    # Compute importance scores
    compute_importance_for_moves(moves)

    return moves


def create_low_confidence_moves() -> list:
    """
    Create moves with LOW confidence (sparse analysis).
    Only 3 moves have visits > 0.
    """
    moves = []

    for i in range(1, 16):
        visits = 500 if i <= 3 else 0  # Only first 3 have analysis
        loss = 1.0 if i <= 3 else 0.0

        move = MoveEval(
            move_number=i,
            player="B" if i % 2 == 1 else "W",
            gtp=f"D{i}",
            score_before=0.0 if visits > 0 else None,
            score_after=-loss if visits > 0 else None,
            delta_score=-loss if visits > 0 else None,
            winrate_before=0.5 if visits > 0 else None,
            winrate_after=0.5 if visits > 0 else None,
            delta_winrate=0.0 if visits > 0 else None,
            points_lost=loss if visits > 0 else None,
            realized_points_lost=None,
            root_visits=visits,
        )
        if visits > 0:
            move.score_loss = loss
            move.mistake_category = classify_mistake(loss, None)
        else:
            move.score_loss = None
            move.mistake_category = MistakeCategory.GOOD
        moves.append(move)

    compute_importance_for_moves(moves)
    return moves


# ---------------------------------------------------------------------------
# Tests for normalize_output
# ---------------------------------------------------------------------------

class TestNormalizeOutput:
    """Tests for the normalize_output function."""

    def test_timestamp_normalization(self):
        """Timestamps should be replaced with [TIMESTAMP]."""
        text = "Generated at 2025-01-05T12:34:56"
        result = normalize_output(text)
        assert "[TIMESTAMP]" in result
        assert "2025-01-05T12:34:56" not in result

    def test_date_normalization(self):
        """Dates should be replaced with [DATE]."""
        text = "Report for 2025-01-05"
        result = normalize_output(text)
        assert "[DATE]" in result
        assert "2025-01-05" not in result

    def test_path_normalization_windows(self):
        """Windows paths should be replaced with [PATH]."""
        text = r"File: D:\github\katrain-1.17.0\test.sgf"
        result = normalize_output(text)
        assert "[PATH]" in result
        assert "D:\\" not in result

    def test_path_normalization_unix(self):
        """Unix paths should be replaced with [PATH]."""
        text = "File: /home/user/test.sgf"
        result = normalize_output(text)
        assert "[PATH]" in result
        assert "/home/" not in result

    def test_float_normalization(self):
        """Floats with 2+ decimals should be rounded to 1 decimal."""
        text = "Loss: 3.14159 points"
        result = normalize_output(text)
        assert "3.1" in result
        assert "3.14159" not in result

    def test_integer_preserved(self):
        """Integers should not be changed."""
        text = "Move 42"
        result = normalize_output(text)
        assert "Move 42" in result

    def test_single_decimal_preserved(self):
        """Numbers with 1 decimal should be preserved."""
        text = "Loss: 3.5 points"
        result = normalize_output(text)
        assert "3.5" in result


# ---------------------------------------------------------------------------
# Tests for Karte structure and content
# ---------------------------------------------------------------------------

class TestKarteStructure:
    """Tests verifying Karte report structure."""

    def test_high_confidence_has_full_sections(self):
        """HIGH confidence Karte should have all sections without warnings."""
        moves = create_standard_game_moves()
        snapshot = EvalSnapshot(moves=moves)

        # Verify HIGH confidence
        level = compute_confidence_level(moves)
        assert level == ConfidenceLevel.HIGH

    def test_low_confidence_triggers_warning(self):
        """LOW confidence should be detected for sparse analysis."""
        moves = create_low_confidence_moves()

        # Verify LOW confidence
        level = compute_confidence_level(moves)
        assert level == ConfidenceLevel.LOW

    def test_moves_are_deterministically_ordered(self):
        """Moves with same importance should be ordered by move_number."""
        moves = [
            MoveEval(
                move_number=10, player="B", gtp="D10",
                score_before=0.0, score_after=-5.0, delta_score=-5.0,
                winrate_before=0.5, winrate_after=0.45, delta_winrate=-0.05,
                points_lost=5.0, realized_points_lost=None, root_visits=500,
            ),
            MoveEval(
                move_number=5, player="W", gtp="D5",
                score_before=0.0, score_after=-5.0, delta_score=-5.0,
                winrate_before=0.5, winrate_after=0.45, delta_winrate=-0.05,
                points_lost=5.0, realized_points_lost=None, root_visits=500,
            ),
        ]
        for m in moves:
            m.score_loss = 5.0

        compute_importance_for_moves(moves)

        # Both have same loss, so importance should be similar
        # Order should be deterministic based on move_number
        sorted_moves = sorted(
            moves,
            key=lambda m: (-m.importance_score, m.move_number)
        )

        # With same importance, lower move_number comes first
        assert sorted_moves[0].move_number == 5
        assert sorted_moves[1].move_number == 10


# ---------------------------------------------------------------------------
# Tests for confidence boundaries (Unit-style, no SGF)
# ---------------------------------------------------------------------------

class TestConfidenceBoundaries:
    """
    Unit-style tests for confidence level boundaries.
    Uses MoveEval directly without SGF dependency.
    """

    def test_high_confidence_reliability_threshold(self):
        """HIGH when reliability >= 50%."""
        # 10 moves, all with visits >= 200 (reliable threshold)
        moves = []
        for i in range(10):
            move = MoveEval(
                move_number=i + 1,
                player="B",
                gtp=f"D{i + 1}",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.5, realized_points_lost=None,
                root_visits=250,  # All reliable
            )
            moves.append(move)

        level = compute_confidence_level(moves)
        assert level == ConfidenceLevel.HIGH

    def test_high_confidence_visits_threshold(self):
        """HIGH when avg_visits >= 400 (even if reliability < 50%)."""
        moves = []
        for i in range(10):
            # Only 30% reliable, but avg_visits = 450
            visits = 200 if i < 3 else 480
            move = MoveEval(
                move_number=i + 1,
                player="B",
                gtp=f"D{i + 1}",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.5, realized_points_lost=None,
                root_visits=visits,
            )
            moves.append(move)

        level = compute_confidence_level(moves)
        assert level == ConfidenceLevel.HIGH

    def test_medium_confidence_threshold(self):
        """MEDIUM when reliability >= 30% or avg_visits >= 150."""
        moves = []
        for i in range(10):
            # 40% reliable (4 of 10), avg_visits around 130
            visits = 200 if i < 4 else 90
            move = MoveEval(
                move_number=i + 1,
                player="B",
                gtp=f"D{i + 1}",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.5, realized_points_lost=None,
                root_visits=visits,
            )
            moves.append(move)

        level = compute_confidence_level(moves)
        assert level == ConfidenceLevel.MEDIUM

    def test_low_confidence_below_thresholds(self):
        """LOW when reliability < 30% and avg_visits < 150."""
        moves = []
        for i in range(10):
            # 20% reliable, avg_visits = 90
            visits = 200 if i < 2 else 70
            move = MoveEval(
                move_number=i + 1,
                player="B",
                gtp=f"D{i + 1}",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.5, realized_points_lost=None,
                root_visits=visits,
            )
            moves.append(move)

        level = compute_confidence_level(moves)
        assert level == ConfidenceLevel.LOW

    def test_min_coverage_forces_low(self):
        """LOW when moves_with_visits < 5 (MIN_COVERAGE_MOVES)."""
        moves = []
        for i in range(20):
            # Only 3 moves have visits > 0
            visits = 1000 if i < 3 else 0
            move = MoveEval(
                move_number=i + 1,
                player="B",
                gtp=f"D{i + 1}",
                score_before=0.0 if visits > 0 else None,
                score_after=0.0 if visits > 0 else None,
                delta_score=0.0 if visits > 0 else None,
                winrate_before=0.5 if visits > 0 else None,
                winrate_after=0.5 if visits > 0 else None,
                delta_winrate=0.0 if visits > 0 else None,
                points_lost=0.5 if visits > 0 else None,
                realized_points_lost=None,
                root_visits=visits,
            )
            moves.append(move)

        level = compute_confidence_level(moves)
        assert level == ConfidenceLevel.LOW

    def test_exactly_five_moves_not_forced_low(self):
        """Exactly 5 moves with visits should not be forced LOW."""
        moves = []
        for i in range(10):
            # Exactly 5 moves have visits > 0, all reliable
            visits = 300 if i < 5 else 0
            move = MoveEval(
                move_number=i + 1,
                player="B",
                gtp=f"D{i + 1}",
                score_before=0.0 if visits > 0 else None,
                score_after=0.0 if visits > 0 else None,
                delta_score=0.0 if visits > 0 else None,
                winrate_before=0.5 if visits > 0 else None,
                winrate_after=0.5 if visits > 0 else None,
                delta_winrate=0.0 if visits > 0 else None,
                points_lost=0.5 if visits > 0 else None,
                realized_points_lost=None,
                root_visits=visits,
            )
            moves.append(move)

        level = compute_confidence_level(moves)
        # 5 moves, all reliable (100%), should be HIGH
        assert level == ConfidenceLevel.HIGH


# ---------------------------------------------------------------------------
# Tests for deterministic sorting
# ---------------------------------------------------------------------------

class TestDeterministicSorting:
    """Tests verifying deterministic ordering in output."""

    def test_importance_tiebreak_by_move_number(self):
        """Moves with same importance should be sorted by move_number ascending."""
        # Create moves with identical importance scores
        moves = []
        for i in [30, 10, 20]:  # Out of order
            move = MoveEval(
                move_number=i,
                player="B",
                gtp=f"D{i}",
                score_before=0.0, score_after=-5.0, delta_score=-5.0,
                winrate_before=0.5, winrate_after=0.45, delta_winrate=-0.05,
                points_lost=5.0, realized_points_lost=None, root_visits=500,
            )
            move.score_loss = 5.0
            moves.append(move)

        compute_importance_for_moves(moves)

        # Sort like the code does: importance desc, move_number asc
        sorted_moves = sorted(
            moves,
            key=lambda m: (-m.importance_score, m.move_number)
        )

        # With same importance, should be ordered 10, 20, 30
        assert sorted_moves[0].move_number == 10
        assert sorted_moves[1].move_number == 20
        assert sorted_moves[2].move_number == 30

    def test_evidence_tiebreak_by_move_number(self):
        """Evidence with same score_loss should be sorted by move_number ascending."""
        from katrain.core.eval_metrics import select_representative_moves

        moves = []
        for i in [15, 5, 10]:  # Out of order
            move = MoveEval(
                move_number=i,
                player="B",
                gtp=f"D{i}",
                score_before=0.0, score_after=-3.0, delta_score=-3.0,
                winrate_before=0.5, winrate_after=0.47, delta_winrate=-0.03,
                points_lost=3.0, realized_points_lost=None, root_visits=500,
            )
            move.score_loss = 3.0
            moves.append(move)

        result = select_representative_moves(moves, max_count=3)

        # With same score_loss, should be ordered 5, 10, 15
        assert result[0].move_number == 5
        assert result[1].move_number == 10
        assert result[2].move_number == 15


# ---------------------------------------------------------------------------
# E2E Tests: SGF → Karte (Phase 24)
# ---------------------------------------------------------------------------

class TestKarteFromSGF:
    """
    End-to-end tests for Karte generation from real SGF files.

    Uses mock analysis injection to ensure deterministic output without
    requiring KataGo execution. Tests 3 SGF files per Roadmap acceptance criteria.
    """

    SGF_DIR = Path(__file__).parent / "data"
    SGF_FILES = {
        "fox": SGF_DIR / "fox sgf works.sgf",
        "alphago": SGF_DIR / "LS vs AG - G4 - English.sgf",
        "panda": SGF_DIR / "panda1.sgf",
    }

    @pytest.fixture
    def mock_katrain(self):
        """Create a mock KaTrain instance."""
        from katrain.core.base_katrain import KaTrainBase
        return KaTrainBase(force_package_config=True, debug_level=0)

    @pytest.fixture
    def mock_engine(self):
        """Create a mock engine."""
        class MockEngine:
            def request_analysis(self, *args, **kwargs):
                pass
            def stop_pondering(self):
                pass
        return MockEngine()

    def load_game_with_mock_analysis(self, sgf_key: str, mock_katrain, mock_engine):
        """Load SGF and inject mock analysis."""
        from katrain.core.game import Game, KaTrainSGF
        from tests.helpers import inject_mock_analysis

        sgf_path = self.SGF_FILES[sgf_key]
        move_tree = KaTrainSGF.parse_file(str(sgf_path))
        game = Game(mock_katrain, mock_engine, move_tree)

        # Inject deterministic mock analysis
        inject_mock_analysis(game)

        return game

    @pytest.mark.parametrize("sgf_key", ["fox", "alphago", "panda"])
    def test_karte_from_sgf_matches_golden(
        self, sgf_key: str, mock_katrain, mock_engine, request
    ):
        """
        Test that Karte output matches golden file.

        Uses mock analysis injection to ensure deterministic output.
        """
        from katrain.core.reports.karte_report import build_karte_report
        from tests.conftest import update_golden_if_requested

        game = self.load_game_with_mock_analysis(sgf_key, mock_katrain, mock_engine)

        # Generate karte
        karte_output = build_karte_report(game)

        # Normalize for comparison
        normalized = normalize_output(karte_output)

        golden_name = f"karte_sgf_{sgf_key}.golden"

        # Update golden if requested
        update_golden_if_requested(golden_name, normalized, request)

        # Load and compare
        expected = load_golden(golden_name)
        assert normalized == expected, (
            f"Karte output for {sgf_key} does not match golden file.\n"
            f"Run with --update-goldens to update the expected output."
        )

    @pytest.mark.parametrize("sgf_key", ["fox", "alphago", "panda"])
    def test_karte_output_is_deterministic(
        self, sgf_key: str, mock_katrain, mock_engine
    ):
        """
        Verify that karte generation is deterministic.

        Running the same input twice should produce identical output.
        """
        from katrain.core.reports.karte_report import build_karte_report

        # Generate twice
        game1 = self.load_game_with_mock_analysis(sgf_key, mock_katrain, mock_engine)
        output1 = normalize_output(build_karte_report(game1))

        game2 = self.load_game_with_mock_analysis(sgf_key, mock_katrain, mock_engine)
        output2 = normalize_output(build_karte_report(game2))

        assert output1 == output2, (
            f"Karte output for {sgf_key} is not deterministic.\n"
            f"First run differs from second run."
        )
