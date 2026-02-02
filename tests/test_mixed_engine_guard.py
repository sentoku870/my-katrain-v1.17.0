"""Tests for mixed-engine snapshot detection (Phase 37).

This module tests the mixed-engine guard functionality that prevents
combining KataGo and Leela analysis data in a single karte report.

Test classes:
    TestIsSingleEngineSnapshot: Pure function tests (no mocks needed)
    TestBuildKarteReportMixedEngineGuard: Integration tests (Game mock)
"""

from unittest.mock import MagicMock

import pytest

from katrain.core.analysis.models import EvalSnapshot, MoveEval
from katrain.core.reports.karte_report import (
    KARTE_ERROR_CODE_MIXED_ENGINE,
    MixedEngineSnapshotError,
    build_karte_report,
    is_single_engine_snapshot,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def make_move_eval(
    move_number: int,
    player: str,
    score_loss: float | None = None,
    leela_loss_est: float | None = None,
) -> MoveEval:
    """Create a MoveEval for testing with minimal required fields.

    Args:
        move_number: Move number in the game
        player: "B" or "W"
        score_loss: KataGo score loss (set for KataGo moves)
        leela_loss_est: Leela estimated loss (set for Leela moves)

    Returns:
        MoveEval instance with the specified loss fields
    """
    return MoveEval(
        move_number=move_number,
        player=player,
        gtp="D4",
        score_before=None,
        score_after=None,
        delta_score=None,
        winrate_before=None,
        winrate_after=None,
        delta_winrate=None,
        points_lost=None,
        realized_points_lost=None,
        root_visits=0,
        score_loss=score_loss,
        leela_loss_est=leela_loss_est,
    )


def create_katago_snapshot(num_moves: int = 5) -> EvalSnapshot:
    """Create a snapshot with only KataGo analysis data."""
    moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0) for i in range(1, num_moves + 1)]
    return EvalSnapshot(moves=moves)


def create_leela_snapshot(num_moves: int = 5) -> EvalSnapshot:
    """Create a snapshot with only Leela analysis data."""
    moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", leela_loss_est=1.0) for i in range(1, num_moves + 1)]
    return EvalSnapshot(moves=moves)


def create_unanalyzed_snapshot(num_moves: int = 5) -> EvalSnapshot:
    """Create a snapshot with no analysis data (all None)."""
    moves = [make_move_eval(i, "B" if i % 2 == 1 else "W") for i in range(1, num_moves + 1)]
    return EvalSnapshot(moves=moves)


def create_mixed_snapshot() -> EvalSnapshot:
    """Create a snapshot with both KataGo and Leela data (invalid)."""
    return EvalSnapshot(
        moves=[
            make_move_eval(1, "B", score_loss=1.0, leela_loss_est=None),
            make_move_eval(2, "W", score_loss=None, leela_loss_est=2.0),
        ],
    )


def create_partial_katago_snapshot() -> EvalSnapshot:
    """Create a snapshot with partial KataGo analysis (some moves unanalyzed)."""
    return EvalSnapshot(
        moves=[
            make_move_eval(1, "B", score_loss=1.0),
            make_move_eval(2, "W"),  # Unanalyzed
            make_move_eval(3, "B", score_loss=0.5),
        ],
    )


# ---------------------------------------------------------------------------
# Pure function tests: is_single_engine_snapshot()
# ---------------------------------------------------------------------------


class TestIsSingleEngineSnapshot:
    """Tests for is_single_engine_snapshot() pure function.

    No mocks needed - tests the validation logic directly.
    """

    def test_all_katago_returns_true(self):
        """All moves with score_loss (KataGo) -> True."""
        snapshot = create_katago_snapshot()
        assert is_single_engine_snapshot(snapshot) is True

    def test_all_leela_returns_true(self):
        """All moves with leela_loss_est (Leela) -> True."""
        snapshot = create_leela_snapshot()
        assert is_single_engine_snapshot(snapshot) is True

    def test_all_none_returns_true(self):
        """All moves with no loss data (unanalyzed) -> True."""
        snapshot = create_unanalyzed_snapshot()
        assert is_single_engine_snapshot(snapshot) is True

    def test_partial_analysis_returns_true(self):
        """Some moves analyzed + some unanalyzed (partial) -> True."""
        snapshot = create_partial_katago_snapshot()
        assert is_single_engine_snapshot(snapshot) is True

    def test_mixed_engines_returns_false(self):
        """KataGo move + Leela move in same snapshot -> False."""
        snapshot = create_mixed_snapshot()
        assert is_single_engine_snapshot(snapshot) is False

    def test_empty_snapshot_returns_true(self):
        """Empty moves list -> True (vacuously true)."""
        snapshot = EvalSnapshot(moves=[])
        assert is_single_engine_snapshot(snapshot) is True

    def test_single_katago_move_returns_true(self):
        """Single KataGo move -> True."""
        snapshot = EvalSnapshot(
            moves=[make_move_eval(1, "B", score_loss=1.0)],
        )
        assert is_single_engine_snapshot(snapshot) is True

    def test_single_leela_move_returns_true(self):
        """Single Leela move -> True."""
        snapshot = EvalSnapshot(
            moves=[make_move_eval(1, "B", leela_loss_est=1.0)],
        )
        assert is_single_engine_snapshot(snapshot) is True

    def test_zero_loss_values_still_detected(self):
        """score_loss=0.0 and leela_loss_est=0.0 are still detected as non-None."""
        # Both engines with zero loss values
        snapshot = EvalSnapshot(
            moves=[
                make_move_eval(1, "B", score_loss=0.0),
                make_move_eval(2, "W", leela_loss_est=0.0),
            ],
        )
        assert is_single_engine_snapshot(snapshot) is False


# ---------------------------------------------------------------------------
# Integration tests: build_karte_report() with mixed-engine check
# ---------------------------------------------------------------------------


class TestBuildKarteReportMixedEngineGuard:
    """Integration tests for build_karte_report() mixed-engine detection.

    Uses Game mocks to test the full flow.
    """

    @pytest.fixture
    def mixed_game_fixture(self):
        """Create a Game mock that returns a mixed snapshot."""
        game = MagicMock()
        game.build_eval_snapshot.return_value = create_mixed_snapshot()
        game.game_id = "test_game"
        game.sgf_filename = "test.sgf"
        game.katrain = None
        game.board_size = (19, 19)
        game.komi = 6.5
        game.rules = "chinese"
        # CRITICAL: Set children to empty list to prevent infinite loop in parse_time_data
        game.root.children = []
        return game

    @pytest.fixture
    def katago_game_fixture(self):
        """Create a Game mock that returns a KataGo-only snapshot."""
        game = MagicMock()
        game.build_eval_snapshot.return_value = create_katago_snapshot()
        game.game_id = "katago_game"
        game.sgf_filename = "katago.sgf"
        game.katrain = None
        game.board_size = (19, 19)
        game.komi = 6.5
        game.rules = "chinese"
        # CRITICAL: Set children to empty list to prevent infinite loop in parse_time_data
        game.root.children = []
        return game

    def test_mixed_snapshot_returns_error_markdown(self, mixed_game_fixture):
        """raise_on_error=False (default) -> returns error markdown."""
        result = build_karte_report(mixed_game_fixture)

        # Verify error code is in the result (stable assertion, not text-dependent)
        assert KARTE_ERROR_CODE_MIXED_ENGINE in result
        # Also verify it's a markdown error karte
        assert "# Karte (ERROR)" in result

    def test_mixed_snapshot_raises_when_requested(self, mixed_game_fixture):
        """raise_on_error=True -> raises MixedEngineSnapshotError."""
        with pytest.raises(MixedEngineSnapshotError) as exc_info:
            build_karte_report(mixed_game_fixture, raise_on_error=True)

        # Verify error code is in the exception message
        assert KARTE_ERROR_CODE_MIXED_ENGINE in str(exc_info.value)

    def test_mixed_snapshot_exception_is_valueerror_subclass(self, mixed_game_fixture):
        """MixedEngineSnapshotError is a ValueError subclass for compatibility."""
        with pytest.raises(ValueError):
            build_karte_report(mixed_game_fixture, raise_on_error=True)

    def test_katago_snapshot_does_not_trigger_error(self, katago_game_fixture):
        """KataGo-only snapshot should not trigger mixed-engine error."""
        # This will fail because the mock doesn't fully implement Game,
        # but it should NOT fail with MixedEngineSnapshotError
        try:
            build_karte_report(katago_game_fixture)
        except MixedEngineSnapshotError:
            pytest.fail("KataGo-only snapshot should not trigger MixedEngineSnapshotError")
        except Exception:
            # Other exceptions are expected (incomplete mock)
            pass

    def test_snapshot_computed_only_once(self, mixed_game_fixture):
        """Verify snapshot is computed only once (not twice)."""
        build_karte_report(mixed_game_fixture)

        # build_eval_snapshot should be called exactly once
        assert mixed_game_fixture.build_eval_snapshot.call_count == 1
