"""Regression tests for Phase 55-64 features.

Part of Phase 65: Post-54 Integration.

Tests:
- API signature regression for existing features
- Graceful handling of missing/empty data for new features

Note: Golden test compatibility is verified by running existing golden tests
in the acceptance criteria, not duplicated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.analysis.models import EvalSnapshot, MoveEval
from katrain.core.analysis.time.models import GameTimeData, TimeMetrics
from katrain.core.analysis.time.pacing import analyze_pacing
from katrain.core.curator.batch import generate_curator_outputs


def make_move_eval(
    move_number: int,
    player: str = "B",
    score_loss: float | None = None,
) -> MoveEval:
    """Create a MoveEval instance for testing."""
    return MoveEval(
        move_number=move_number,
        player=player,
        gtp="aa",
        score_before=None,
        score_after=None,
        delta_score=None,
        winrate_before=None,
        winrate_after=None,
        delta_winrate=None,
        points_lost=score_loss,
        realized_points_lost=None,
        root_visits=500,
        score_loss=score_loss,
    )


@dataclass
class MockMove:
    """Mock Move object for testing."""

    player: str
    coords: tuple | None = None

    @property
    def is_pass(self) -> bool:
        return self.coords is None


@dataclass
class MockNode:
    """Mock GameNode for testing."""

    analysis_exists: bool = False
    analysis: dict[str, Any] | None = None
    move: Optional[MockMove] = None
    parent: Optional[MockNode] = None
    children: list[MockNode] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass
class MockGame:
    """Mock Game object for testing."""

    root: MockNode

    @property
    def current_node(self):
        return self.root


# =============================================================================
# TestRegressionExistingFeatures
# =============================================================================


class TestRegressionExistingFeatures:
    """API signature regression tests for existing features.

    These tests verify that functions are callable with expected arguments.
    They do NOT verify exact output values (that's what unit tests do).
    """

    def test_eval_snapshot_api_signature(self):
        """EvalSnapshot can be constructed with expected API."""
        # Can construct with moves list
        moves = [make_move_eval(1), make_move_eval(2)]
        snapshot = EvalSnapshot(moves=moves)

        assert snapshot is not None
        assert hasattr(snapshot, "moves")
        assert hasattr(snapshot, "total_points_lost")
        assert hasattr(snapshot, "max_points_lost")

    def test_eval_snapshot_empty_moves(self):
        """EvalSnapshot handles empty moves list."""
        snapshot = EvalSnapshot(moves=[])

        assert snapshot is not None
        assert snapshot.total_points_lost == 0.0

    def test_eval_snapshot_empty_moves(self):
        """analyze_pacing handles missing time data gracefully."""
        # GameTimeData with no time info
        time_data = GameTimeData(
            metrics=(),
            has_time_data=False,
            black_moves_with_time=0,
            white_moves_with_time=0,
        )
        moves: list[MoveEval] = []

        # Should not raise
        result = analyze_pacing(time_data, moves)
        assert result is not None
        assert isinstance(result.pacing_metrics, tuple)
        assert isinstance(result.tilt_episodes, tuple)

    def test_pacing_on_empty_moves(self):
        """analyze_pacing handles empty moves list gracefully."""
        time_data = GameTimeData(
            metrics=(TimeMetrics(move_number=1, player="B", time_left_sec=100.0, time_spent_sec=10.0),),
            has_time_data=True,
            black_moves_with_time=1,
            white_moves_with_time=0,
        )
        moves: list[MoveEval] = []  # Empty

        # Should not raise
        result = analyze_pacing(time_data, moves)
        assert result is not None





    def test_curator_on_no_user_aggregate(self, tmp_path):
        """generate_curator_outputs handles None user_aggregate gracefully."""
        # Should not raise
        result = generate_curator_outputs(
            games_and_stats=[],
            curator_dir=str(tmp_path),
            batch_timestamp="20260126-120000",
            user_aggregate=None,  # Explicitly None
        )

        assert result is not None
        assert result.ranking_path is not None
        assert result.guide_path is not None

    def test_curator_on_empty_games(self, tmp_path):
        """generate_curator_outputs handles empty games list gracefully."""
        result = generate_curator_outputs(
            games_and_stats=[],  # Empty
            curator_dir=str(tmp_path),
            batch_timestamp="20260126-120000",
        )

        assert result is not None
        assert result.games_scored == 0
        assert result.guides_generated == 0
