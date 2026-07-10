"""Karte error handling and streak-edge-case tests (Phase E-1).

Extracted from tests/test_karte_structure.py. Covers
:class:`KarteGenerationError` lifecycle, ``build_karte_report`` failure
paths, and ``detect_mistake_streaks`` with ``None`` / sparse data.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from katrain.core.eval_metrics import (
    MoveEval,
    detect_mistake_streaks,
)


class TestKarteGenerationError:
    """Tests for KarteGenerationError exception (A2)."""

    def test_exception_attributes(self):
        """KarteGenerationError should have all expected attributes."""
        from katrain.core.game import KarteGenerationError

        error = KarteGenerationError(
            message="Test error",
            game_id="game123",
            focus_player="B",
            context="test_context",
            original_error=ValueError("original"),
        )
        assert error.game_id == "game123"
        assert error.focus_player == "B"
        assert error.context == "test_context"
        assert isinstance(error.original_error, ValueError)

    def test_exception_str_format(self):
        """Exception string should include context info."""
        from katrain.core.game import KarteGenerationError

        error = KarteGenerationError(
            message="Test error",
            game_id="game123",
            focus_player="W",
            context="build_karte",
        )
        error_str = str(error)
        assert "Test error" in error_str
        assert "game123" in error_str
        assert "focus_player=W" in error_str

    def test_exception_minimal(self):
        """Exception with minimal info should work."""
        from katrain.core.game import KarteGenerationError

        error = KarteGenerationError(message="Simple error")
        assert str(error) == "Simple error"


class TestBuildKarteReportErrorHandling:
    """Tests for build_karte_report error handling (A2).

    Note: PR #119 moved karte implementation to katrain.core.reports.karte_report.
    These tests now directly test the karte_report module functions.
    """

    def test_returns_error_markdown_on_failure(self):
        """Should return error markdown when generation fails."""
        from katrain.core.reports.karte_report import build_karte_report

        # Create a mock game that will fail during karte generation
        game = Mock()
        game.game_id = "test_game"
        game.sgf_filename = "test.sgf"
        game.katrain = None
        # Make build_eval_snapshot raise an exception to trigger error handling
        game.build_eval_snapshot = Mock(side_effect=ValueError("Test failure"))

        result = build_karte_report(game)

        assert "ERROR" in result
        assert "Test failure" in result
        assert "test_game" in result

    def test_raises_exception_when_requested(self):
        """Should raise KarteGenerationError when raise_on_error=True."""
        from katrain.core.reports.karte_report import (
            KarteGenerationError,
            build_karte_report,
        )

        game = Mock()
        game.game_id = "test_game"
        game.sgf_filename = None
        game.katrain = None
        game.build_eval_snapshot = Mock(side_effect=RuntimeError("Boom"))

        with pytest.raises(KarteGenerationError) as exc_info:
            build_karte_report(game, raise_on_error=True)

        assert "Boom" in str(exc_info.value)
        assert exc_info.value.game_id == "test_game"

    def test_error_karte_structure(self):
        """Error karte should have expected structure."""
        from katrain.core.reports.karte.builder import _build_error_karte

        result = _build_error_karte(
            game_id="game123",
            player_filter="B",
            error_msg="Something went wrong",
        )

        assert "# Karte (ERROR)" in result
        assert "## Meta" in result
        assert "game123" in result
        assert "## ERROR" in result
        assert "Something went wrong" in result


# ==============================================================================
# PR#1 Tests: Threshold Consistency + Urgent Miss Detection
# ==============================================================================


class TestDetectMistakeStreaksNoneHandling:
    """Tests for detect_mistake_streaks handling of None points_lost."""

    def test_none_points_lost_breaks_streak(self):
        """moves with points_lost=None should conservatively break streaks."""
        moves = [
            MoveEval(
                move_number=2,
                player="B",
                gtp="D4",
                score_before=0.0,
                score_after=-3.0,
                delta_score=-3.0,
                winrate_before=0.5,
                winrate_after=0.45,
                delta_winrate=-0.05,
                points_lost=3.0,  # Start of potential streak
                realized_points_lost=None,
                root_visits=100,
            ),
            MoveEval(
                move_number=4,
                player="B",
                gtp="Q10",
                score_before=-3.0,
                score_after=-7.0,
                delta_score=-4.0,
                winrate_before=0.45,
                winrate_after=0.35,
                delta_winrate=-0.1,
                points_lost=None,  # Unknown loss - should break streak
                realized_points_lost=None,
                root_visits=100,
            ),
            MoveEval(
                move_number=6,
                player="B",
                gtp="R15",
                score_before=-7.0,
                score_after=-12.0,
                delta_score=-5.0,
                winrate_before=0.35,
                winrate_after=0.25,
                delta_winrate=-0.1,
                points_lost=5.0,  # After the break
                realized_points_lost=None,
                root_visits=100,
            ),
        ]
        # Should not form a streak because None in the middle breaks it
        streaks = detect_mistake_streaks(moves, loss_threshold=2.0, min_consecutive=2)
        assert streaks == []

    def test_zero_points_lost_not_treated_as_none(self):
        """points_lost=0.0 should NOT be treated as None (truthiness bug check)."""
        moves = [
            MoveEval(
                move_number=2,
                player="B",
                gtp="D4",
                score_before=0.0,
                score_after=-3.0,
                delta_score=-3.0,
                winrate_before=0.5,
                winrate_after=0.45,
                delta_winrate=-0.05,
                points_lost=3.0,  # Above threshold
                realized_points_lost=None,
                root_visits=100,
            ),
            MoveEval(
                move_number=4,
                player="B",
                gtp="Q10",
                score_before=-3.0,
                score_after=-3.0,
                delta_score=0.0,
                winrate_before=0.45,
                winrate_after=0.45,
                delta_winrate=0.0,
                points_lost=0.0,  # Zero - should NOT be treated as None
                realized_points_lost=None,
                root_visits=100,
            ),
            MoveEval(
                move_number=6,
                player="B",
                gtp="R15",
                score_before=-3.0,
                score_after=-8.0,
                delta_score=-5.0,
                winrate_before=0.45,
                winrate_after=0.30,
                delta_winrate=-0.15,
                points_lost=5.0,  # Above threshold
                realized_points_lost=None,
                root_visits=100,
            ),
        ]
        # 0.0 is below threshold, so it breaks the streak normally (not as None)
        # The first move alone doesn't form a streak (min_consecutive=2)
        # The last move alone doesn't form a streak
        streaks = detect_mistake_streaks(moves, loss_threshold=2.0, min_consecutive=2)
        assert streaks == []

    def test_none_at_end_flushes_streak(self):
        """Streak before None should be flushed correctly."""
        moves = [
            MoveEval(
                move_number=2,
                player="B",
                gtp="D4",
                score_before=0.0,
                score_after=-3.0,
                delta_score=-3.0,
                winrate_before=0.5,
                winrate_after=0.45,
                delta_winrate=-0.05,
                points_lost=3.0,
                realized_points_lost=None,
                root_visits=100,
            ),
            MoveEval(
                move_number=4,
                player="B",
                gtp="Q10",
                score_before=-3.0,
                score_after=-7.0,
                delta_score=-4.0,
                winrate_before=0.45,
                winrate_after=0.35,
                delta_winrate=-0.1,
                points_lost=4.0,
                realized_points_lost=None,
                root_visits=100,
            ),
            MoveEval(
                move_number=6,
                player="B",
                gtp="R15",
                score_before=-7.0,
                score_after=-7.0,
                delta_score=0.0,
                winrate_before=0.35,
                winrate_after=0.35,
                delta_winrate=0.0,
                points_lost=None,  # None at end - should flush the streak
                realized_points_lost=None,
                root_visits=100,
            ),
        ]
        streaks = detect_mistake_streaks(moves, loss_threshold=2.0, min_consecutive=2)
        assert len(streaks) == 1
        assert streaks[0].move_count == 2
        assert streaks[0].total_loss == 7.0
