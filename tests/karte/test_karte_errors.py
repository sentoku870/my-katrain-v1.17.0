"""Karte error handling and streak-edge-case tests (Phase E-1).

Extracted from tests/test_karte_structure.py. Covers
:class:`KarteGenerationError` lifecycle, ``build_karte_json_string`` failure
paths (Phase 231 renamed from ``build_karte_report``), and
``detect_mistake_streaks`` with ``None`` / sparse data.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from katrain.core.analysis import detect_mistake_streaks
from katrain.core.analysis.models.move_eval import MoveEval


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


class TestBuildKarteJsonStringErrorHandling:
    """Tests for build_karte_json_string error handling (A2, Phase 231 renamed).

    Note: PR #119 moved karte implementation to
    ``katrain.core.reports.karte.builder``. Phase 232 further removed
    the ``karte_report.py`` compatibility shim; these tests now
    directly exercise ``build_karte_json_string`` in
    ``katrain.core.reports.karte.builder``.
    """

    def test_returns_error_markdown_on_failure(self):
        """Should return error markdown when generation fails.

        Phase 235: the embedded error message is sanitised via
        :func:`sanitize_error_message` so paths and other internals
        cannot leak into the LLM prompt. The substring ``"Test failure"``
        is not path-like so it is preserved verbatim in the surfaced
        text.
        """
        from katrain.core.reports.karte.builder import build_karte_json_string

        # Create a mock game that will fail during karte generation
        game = Mock()
        game.game_id = "test_game"
        game.sgf_filename = "test.sgf"
        game.katrain = None
        # Make build_eval_snapshot raise an exception to trigger error handling
        game.build_eval_snapshot = Mock(side_effect=ValueError("Test failure"))

        result = build_karte_json_string(game)

        assert "ERROR" in result
        assert "Test failure" in result
        assert "test_game" in result

    def test_raises_exception_when_requested(self):
        """Should raise KarteGenerationError when raise_on_error=True."""
        from katrain.core.reports.karte.builder import build_karte_json_string
        from katrain.core.reports.karte.models import KarteGenerationError

        game = Mock()
        game.game_id = "test_game"
        game.sgf_filename = None
        game.katrain = None
        game.build_eval_snapshot = Mock(side_effect=RuntimeError("Boom"))

        with pytest.raises(KarteGenerationError) as exc_info:
            build_karte_json_string(game, raise_on_error=True)

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


class TestSanitizeErrorMessage:
    """Phase 235: ``sanitize_error_message`` must strip path-like substrings
    and enforce length / punctuation so the surfaced text is safe to embed
    in a Karte error karte or an LLM prompt."""

    def test_none_returns_placeholder(self):
        from katrain.core.reports.karte.models import sanitize_error_message

        assert sanitize_error_message(None) == "Unknown error."
        assert sanitize_error_message("") == "Unknown error."

    def test_simple_message_keeps_essence(self):
        from katrain.core.reports.karte.models import sanitize_error_message

        result = sanitize_error_message("Snapshot construction failed: ValueError")
        # No path, no special characters, message preserved
        assert "Snapshot construction failed" in result
        assert result.endswith(".")

    def test_strips_unix_absolute_path(self):
        from katrain.core.reports.karte.models import sanitize_error_message

        result = sanitize_error_message("Failed to read /home/user/private/data.sgf")
        assert "/home/user/private/data.sgf" not in result
        assert "<path>" in result
        assert result.endswith(".")

    def test_strips_windows_path(self):
        from katrain.core.reports.karte.models import sanitize_error_message

        result = sanitize_error_message("Cannot open C:\\Users\\sentoku\\AppData\\Local\\Temp\\katrain\\abc.json")
        assert "C:\\Users" not in result
        assert "<path>" in result

    def test_strips_home_relative_path(self):
        from katrain.core.reports.karte.models import sanitize_error_message

        result = sanitize_error_message("Failed at ~/katrain/data/file.sgf")
        assert "~/" not in result
        assert "<path>" in result

    def test_takes_first_line_only(self):
        from katrain.core.reports.karte.models import sanitize_error_message

        multiline = "Top-level error\nTraceback (most recent call last):\n  File foo.py"
        result = sanitize_error_message(multiline)
        assert "Traceback" not in result
        assert "Top-level error" in result

    def test_truncates_long_messages(self):
        from katrain.core.reports.karte.models import sanitize_error_message

        long = "x" * 500
        result = sanitize_error_message(long)
        # 200 char cap + "..."
        assert len(result) <= 203
        assert result.endswith("...")

    def test_preserves_existing_punctuation(self):
        from katrain.core.reports.karte.models import sanitize_error_message

        # Already ends with "!" — no extra "." appended
        result = sanitize_error_message("Boom!")
        assert result == "Boom!"
        # Already ends with "?" — same
        result = sanitize_error_message("What happened?")
        assert result == "What happened?"

    def test_appends_period_when_missing(self):
        from katrain.core.reports.karte.models import sanitize_error_message

        result = sanitize_error_message("Failure happened")
        assert result == "Failure happened."


class TestKarteGenerationErrorUserMessage:
    """Phase 235: ``KarteGenerationError`` exposes a pre-computed
    ``user_message`` attribute holding the sanitised message."""

    def test_user_message_is_sanitised(self):
        from katrain.core.game import KarteGenerationError

        err = KarteGenerationError(
            message="Failed to read /home/user/private/file.sgf",
            game_id="g1",
        )
        assert err.user_message is not None
        assert "/home/user/private/file.sgf" not in err.user_message
        assert "<path>" in err.user_message

    def test_user_message_handles_none_original(self):
        from katrain.core.game import KarteGenerationError

        err = KarteGenerationError(
            message="",
            game_id="g1",
        )
        assert err.user_message == "Unknown error."

    def test_user_message_does_not_affect_str(self):
        """``str(err)`` still returns the unsanitised full message so
        logs / exception chains keep the diagnostic context."""
        from katrain.core.game import KarteGenerationError

        err = KarteGenerationError(
            message="Failed to read /home/user/private/file.sgf",
            game_id="g1",
        )
        text = str(err)
        assert "/home/user/private/file.sgf" in text  # unsanitised
        # str includes game_id, but user_message does not
        assert "g1" in text
        assert "g1" not in err.user_message
