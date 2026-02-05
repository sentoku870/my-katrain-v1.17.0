"""Tests for Phase 59: Pacing & Tilt Core.

This module tests the pacing analysis functionality including:
- Coverage gap detection
- Per-player median thresholds
- Tilt episode detection
- Severity classification
- Edge cases
"""

from __future__ import annotations

from katrain.core.analysis.models import MoveEval
from katrain.core.analysis.time.models import GameTimeData, TimeMetrics
from katrain.core.analysis.time.pacing import (
    LossSource,
    PacingConfig,
    TiltSeverity,
    _compute_median,
    _compute_percentile_90,
    _compute_severity,
    _detect_loss_sources,
    analyze_pacing,
)

# =============================================================================
# Test Fixtures / Helpers
# =============================================================================


def make_time_metrics(move_number: int, player: str, time_spent: float | None = None) -> TimeMetrics:
    """Create a TimeMetrics instance for testing."""
    return TimeMetrics(
        move_number=move_number,
        player=player,
        time_left_sec=100.0 if time_spent is not None else None,
        time_spent_sec=time_spent,
    )


def make_time_data(
    move_numbers: list[int],
    players: list[str] | None = None,
    time_spents: list[float | None] | None = None,
) -> GameTimeData:
    """Create GameTimeData for testing."""
    if players is None:
        players = ["B" if i % 2 == 1 else "W" for i in move_numbers]
    if time_spents is None:
        time_spents = [10.0] * len(move_numbers)

    metrics = tuple(make_time_metrics(mn, p, ts) for mn, p, ts in zip(move_numbers, players, time_spents, strict=False))
    has_time = any(m.time_left_sec is not None for m in metrics)

    return GameTimeData(
        metrics=metrics,
        has_time_data=has_time,
        black_moves_with_time=sum(1 for m in metrics if m.player == "B" and m.time_left_sec is not None),
        white_moves_with_time=sum(1 for m in metrics if m.player == "W" and m.time_left_sec is not None),
    )


def make_move_eval(
    move_number: int,
    player: str = "B",
    score_loss: float | None = None,
    leela_loss_est: float | None = None,
    points_lost: float | None = None,
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
        points_lost=points_lost,
        realized_points_lost=None,
        root_visits=500,
        score_loss=score_loss,
        leela_loss_est=leela_loss_est,
    )


# =============================================================================
# Test: Percentile Algorithm
# =============================================================================


class TestPercentileAlgorithm:
    """Test the p90 nearest-rank algorithm."""

    def test_p90_10_values(self):
        """[1..10] -> p90 = 9.0"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        assert _compute_percentile_90(values) == 9.0

    def test_p90_2_values(self):
        """[1, 5] -> p90 = 5.0"""
        assert _compute_percentile_90([1.0, 5.0]) == 5.0

    def test_p90_single_value(self):
        """[3.0] -> p90 = 3.0"""
        assert _compute_percentile_90([3.0]) == 3.0

    def test_p90_empty_list(self):
        """Empty list -> 0.0"""
        assert _compute_percentile_90([]) == 0.0

    def test_p90_unsorted_input(self):
        """Sorts internally."""
        values = [10.0, 1.0, 5.0, 3.0, 8.0]
        # Sorted: [1, 3, 5, 8, 10], n=5, rank=ceil(4.5)=5, index=4
        assert _compute_percentile_90(values) == 10.0


class TestMedianComputation:
    """Test median calculation."""

    def test_median_odd(self):
        """Odd count: middle value."""
        assert _compute_median([1.0, 2.0, 3.0]) == 2.0

    def test_median_even(self):
        """Even count: average of two middle values."""
        assert _compute_median([1.0, 2.0, 3.0, 4.0]) == 2.5

    def test_median_empty(self):
        """Empty list -> 0.0"""
        assert _compute_median([]) == 0.0

    def test_median_single(self):
        """Single value."""
        assert _compute_median([5.0]) == 5.0


# =============================================================================
# Test: Severity Classification
# =============================================================================


class TestSeverityClassification:
    """Test tilt severity classification."""

    def test_severe_both_conditions(self):
        """SEVERE: move_count >= 4 AND cumulative_loss > 15.0"""
        assert _compute_severity(4, 15.1) == TiltSeverity.SEVERE
        assert _compute_severity(5, 20.0) == TiltSeverity.SEVERE

    def test_severe_boundary(self):
        """SEVERE requires > 15.0, not >= 15.0"""
        assert _compute_severity(4, 15.0) == TiltSeverity.MODERATE
        assert _compute_severity(4, 14.9) == TiltSeverity.MODERATE

    def test_severe_requires_move_count(self):
        """SEVERE requires >= 4 moves."""
        assert _compute_severity(3, 20.0) == TiltSeverity.MODERATE

    def test_moderate_move_count(self):
        """MODERATE: move_count >= 3."""
        assert _compute_severity(3, 4.9) == TiltSeverity.MODERATE
        assert _compute_severity(3, 0.0) == TiltSeverity.MODERATE

    def test_moderate_loss(self):
        """MODERATE: cumulative_loss >= 5.0"""
        assert _compute_severity(2, 5.0) == TiltSeverity.MODERATE
        assert _compute_severity(2, 10.0) == TiltSeverity.MODERATE

    def test_mild_default(self):
        """MILD: 2 moves, loss < 5.0"""
        assert _compute_severity(2, 4.9) == TiltSeverity.MILD
        assert _compute_severity(2, 0.0) == TiltSeverity.MILD


# =============================================================================
# Test: Coverage Gap Detection
# =============================================================================


class TestCoverageGapDetection:
    """Test detection of missing MoveEval entries."""

    def test_complete_coverage_no_gaps(self, caplog):
        """Full coverage: no warning, has_coverage_gaps=False."""
        time_data = make_time_data(move_numbers=[1, 2, 3, 4, 5])
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0) for i in range(1, 6)]
        result = analyze_pacing(time_data, moves)
        assert "coverage incomplete" not in caplog.text
        assert result.game_stats.has_coverage_gaps is False
        assert result.game_stats.missing_move_eval_count == 0

    def test_middle_gap_detected(self, caplog):
        """Missing move in middle: warning, gap flagged."""
        time_data = make_time_data(move_numbers=[1, 2, 3, 4, 5])
        moves = [
            make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0)
            for i in [1, 2, 4, 5]  # Missing 3
        ]
        result = analyze_pacing(time_data, moves)
        assert "coverage incomplete" in caplog.text
        assert result.game_stats.has_coverage_gaps is True
        assert result.game_stats.missing_move_eval_count == 1
        # Move 3 not in pacing_metrics
        assert 3 not in {m.move_number for m in result.pacing_metrics}

    def test_tail_truncation_detected(self, caplog):
        """MoveEval truncated at end: warning, gap flagged."""
        time_data = make_time_data(move_numbers=list(range(1, 11)))
        moves = [
            make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0)
            for i in range(1, 8)  # Missing 8, 9, 10
        ]
        result = analyze_pacing(time_data, moves)
        assert "coverage incomplete" in caplog.text
        assert result.game_stats.has_coverage_gaps is True
        assert result.game_stats.missing_move_eval_count == 3
        assert result.game_stats.expected_move_count == 10

    def test_time_metrics_determines_expected(self):
        """expected_move_count comes from TimeMetrics max."""
        time_data = make_time_data(move_numbers=list(range(1, 11)))
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0) for i in range(1, 6)]
        result = analyze_pacing(time_data, moves)
        assert result.game_stats.expected_move_count == 10
        assert result.game_stats.missing_move_eval_count == 5

    def test_no_time_data_uses_move_eval_max(self):
        """Without TimeMetrics, expected from MoveEval max."""
        time_data = GameTimeData(
            metrics=(),
            has_time_data=False,
            black_moves_with_time=0,
            white_moves_with_time=0,
        )
        moves = [
            make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0)
            for i in [1, 2, 4]  # Missing 3
        ]
        result = analyze_pacing(time_data, moves)
        assert result.game_stats.expected_move_count == 4
        assert result.game_stats.missing_move_eval_count == 1


# =============================================================================
# Test: Per-Player Median
# =============================================================================


class TestPerPlayerMedian:
    """Test per-player median computation."""

    def test_separate_medians(self):
        """Black and White have independent medians."""
        # Black times: 10s median, White times: 30s median
        time_data = make_time_data(
            move_numbers=[1, 2, 3, 4, 5, 6, 7, 8],
            players=["B", "W", "B", "W", "B", "W", "B", "W"],
            time_spents=[10.0, 30.0, 10.0, 30.0, 10.0, 30.0, 10.0, 30.0],
        )
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0) for i in range(1, 9)]
        result = analyze_pacing(time_data, moves)
        assert result.game_stats.time_median_black == 10.0
        assert result.game_stats.time_median_white == 30.0
        assert result.game_stats.blitz_threshold_black == 3.0  # 10 * 0.3
        assert result.game_stats.blitz_threshold_white == 9.0  # 30 * 0.3

    def test_one_player_no_time_data(self):
        """Only Black has time data -> White thresholds are None."""
        time_data = make_time_data(
            move_numbers=[1, 3, 5, 7],  # Only Black moves
            players=["B", "B", "B", "B"],
            time_spents=[10.0, 10.0, 10.0, 10.0],
        )
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0) for i in range(1, 9)]
        result = analyze_pacing(time_data, moves)
        assert result.game_stats.time_median_black == 10.0
        assert result.game_stats.time_median_white is None
        assert result.game_stats.blitz_threshold_white is None


# =============================================================================
# Test: Trigger Semantics (Strict >)
# =============================================================================


class TestTriggerSemantics:
    """Test strict '>' trigger condition."""

    def test_p90_equals_max_no_triggers(self):
        """When all losses equal, p90=max, no triggers."""
        time_data = make_time_data(move_numbers=list(range(1, 11)))
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=3.0) for i in range(1, 11)]
        result = analyze_pacing(time_data, moves)
        assert result.game_stats.loss_p90 == 3.0
        assert result.tilt_episodes == ()

    def test_trigger_requires_strict_greater(self):
        """Trigger requires loss > p90, not >=."""
        time_data = make_time_data(move_numbers=list(range(1, 11)))
        # losses = [1, 2, 3, 4, 5, 5, 5, 5, 5, 5]
        # p90 = sorted[8] = 5.0
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=float(min(i, 5))) for i in range(1, 11)]
        result = analyze_pacing(time_data, moves)
        # Max loss is 5.0, p90 is 5.0, so no triggers
        assert result.tilt_episodes == ()


# =============================================================================
# Test: Tilt Episode Detection
# =============================================================================


class TestTiltEpisodeDetection:
    """Test tilt episode detection."""

    def test_single_trigger_no_continuation(self):
        """Single high-loss move without continuation -> no episode."""
        time_data = make_time_data(move_numbers=list(range(1, 11)))
        # One outlier at move 5, others are low
        moves = []
        for i in range(1, 11):
            if i == 5:
                moves.append(make_move_eval(i, "B", score_loss=10.0))
            else:
                player = "B" if i % 2 == 1 else "W"
                moves.append(make_move_eval(i, player, score_loss=0.5))
        result = analyze_pacing(time_data, moves)
        # p90 of [0.5, 0.5, 0.5, 0.5, 10, 0.5, 0.5, 0.5, 0.5, 0.5] = 0.5
        # Move 5 triggers (10 > 0.5)
        # But no continuation (need another Black move with loss >= 0.25)
        # Next Black move is 7 with loss 0.5 >= 0.25, should be continuation
        # Actually, continuation threshold = 0.5 * 0.5 = 0.25
        # Move 7 (Black, 0.5) >= 0.25 -> continuation
        assert len(result.tilt_episodes) >= 1

    def test_episode_minimum_2_moves(self):
        """Need at least 2 moves for episode."""
        time_data = make_time_data(move_numbers=list(range(1, 11)))
        # Outlier at move 9 (Black), but move 11 doesn't exist
        moves = []
        for i in range(1, 11):
            if i == 9:
                moves.append(make_move_eval(i, "B", score_loss=10.0))
            else:
                player = "B" if i % 2 == 1 else "W"
                moves.append(make_move_eval(i, player, score_loss=0.1))
        result = analyze_pacing(time_data, moves)
        # Move 9 triggers, window is 10-14
        # Move 10 is White (different player)
        # No other Black moves in window
        # Episode requires same player
        assert len([e for e in result.tilt_episodes if e.player == "B" and 9 in e.move_numbers]) == 0

    def test_claimed_move_cannot_trigger(self):
        """Move in episode 1 cannot start episode 2."""
        time_data = make_time_data(move_numbers=list(range(1, 21)))
        moves = []
        for i in range(1, 21):
            player = "B" if i % 2 == 1 else "W"
            if i == 1:
                # Move 1: high loss (trigger, > p90)
                moves.append(make_move_eval(i, player, score_loss=10.0))
            elif i in [3, 5]:
                # Moves 3, 5: moderate loss (continuation, >= threshold)
                moves.append(make_move_eval(i, player, score_loss=3.0))
            else:
                moves.append(make_move_eval(i, player, score_loss=0.5))
        result = analyze_pacing(time_data, moves)
        # With losses [10.0, 3.0, 3.0, 0.5×17], p90 = 3.0
        # continuation_threshold = 3.0 * 0.5 = 1.5
        # Move 1 (loss=10.0 > 3.0) triggers
        # Move 3 (loss=3.0 >= 1.5) continues
        # Move 5 (loss=3.0 >= 1.5) continues
        # Move 3 and 5 are claimed, cannot be new triggers
        black_episodes = [e for e in result.tilt_episodes if e.player == "B"]
        # Should only be 1 episode starting at move 1
        assert len(black_episodes) == 1
        assert black_episodes[0].trigger_move == 1
        # Episode should include moves 1, 3, 5
        assert black_episodes[0].move_numbers == (1, 3, 5)


# =============================================================================
# Test: Mixed Engine Detection
# =============================================================================


class TestMixedEngineDetection:
    """Test loss source detection."""

    def test_single_source_score(self):
        """All score_loss -> loss_source=SCORE."""
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0) for i in range(1, 11)]
        source, mixed = _detect_loss_sources(moves)
        assert source == LossSource.SCORE
        assert mixed is False

    def test_single_source_leela(self):
        """All leela_loss_est -> loss_source=LEELA."""
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", leela_loss_est=2.0) for i in range(1, 11)]
        source, mixed = _detect_loss_sources(moves)
        assert source == LossSource.LEELA
        assert mixed is False

    def test_mixed_sources_detected(self, caplog):
        """Mix of score_loss and leela_loss_est detected."""
        time_data = make_time_data(move_numbers=list(range(1, 11)))
        moves = [
            make_move_eval(1, "B", score_loss=1.0),
            make_move_eval(2, "W", leela_loss_est=2.0),
        ]
        for i in range(3, 11):
            moves.append(make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0))
        result = analyze_pacing(time_data, moves)
        assert result.game_stats.has_mixed_sources is True
        assert "Mixed loss sources" in caplog.text

    def test_no_loss_data(self):
        """All loss values None -> loss_source=NONE."""
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W") for i in range(1, 11)]
        source, mixed = _detect_loss_sources(moves)
        assert source == LossSource.NONE
        assert mixed is False


# =============================================================================
# Test: Pacing Flags
# =============================================================================


class TestPacingFlags:
    """Test pacing classification flags."""

    def test_blitz_detection(self):
        """is_blitz when time < median * 0.3."""
        # Black median = 10, blitz threshold = 3.0
        time_data = make_time_data(
            move_numbers=[1, 2, 3, 4, 5, 6, 7, 8],
            players=["B", "W", "B", "W", "B", "W", "B", "W"],
            time_spents=[2.0, 30.0, 10.0, 30.0, 10.0, 30.0, 10.0, 30.0],  # Move 1 is blitz
        )
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0) for i in range(1, 9)]
        # Use custom config to allow fewer than 10 moves
        config = PacingConfig(min_moves_for_stats=1)
        result = analyze_pacing(time_data, moves, config)
        move1 = next(m for m in result.pacing_metrics if m.move_number == 1)
        # Median Black times: [2, 10, 10, 10] -> median = 10
        # Blitz threshold = 10 * 0.3 = 3.0
        # Move 1 time = 2.0 < 3.0 -> is_blitz
        assert move1.is_blitz is True

    def test_long_think_detection(self):
        """is_long_think when time > median * 3.0."""
        time_data = make_time_data(
            move_numbers=[1, 2, 3, 4, 5, 6, 7, 8],
            players=["B", "W", "B", "W", "B", "W", "B", "W"],
            time_spents=[35.0, 30.0, 10.0, 30.0, 10.0, 30.0, 10.0, 30.0],  # Move 1 is long
        )
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0) for i in range(1, 9)]
        # Use custom config to allow fewer than 10 moves
        config = PacingConfig(min_moves_for_stats=1)
        result = analyze_pacing(time_data, moves, config)
        move1 = next(m for m in result.pacing_metrics if m.move_number == 1)
        # Median Black times: [35, 10, 10, 10] -> median = 10
        # Long think threshold = 10 * 3.0 = 30.0
        # Move 1 time = 35.0 > 30.0 -> is_long_think
        assert move1.is_long_think is True


# =============================================================================
# Test: has_time_data and Tilt Disabled
# =============================================================================


class TestFlags:
    """Test result flags."""

    def test_has_time_data_false_when_no_time(self):
        """has_time_data=False when no time data."""
        time_data = GameTimeData(
            metrics=(),
            has_time_data=False,
            black_moves_with_time=0,
            white_moves_with_time=0,
        )
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0) for i in range(1, 11)]
        result = analyze_pacing(time_data, moves)
        assert result.has_time_data is False

    def test_loss_p90_zero_disables_tilt(self):
        """All canonical_loss=0.0 -> tilt disabled."""
        time_data = make_time_data(move_numbers=list(range(1, 11)))
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=0.0) for i in range(1, 11)]
        result = analyze_pacing(time_data, moves)
        assert result.game_stats.loss_p90 == 0.0
        assert result.game_stats.tilt_detection_enabled is False
        assert result.tilt_episodes == ()

    def test_one_positive_loss_insufficient(self):
        """Only 1 move with loss > 0 -> p90=0.0."""
        time_data = make_time_data(move_numbers=list(range(1, 11)))
        moves = [make_move_eval(1, "B", score_loss=5.0)]
        for i in range(2, 11):
            moves.append(make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=0.0))
        result = analyze_pacing(time_data, moves)
        assert result.game_stats.loss_p90 == 0.0
        assert result.game_stats.tilt_detection_enabled is False


# =============================================================================
# Test: Ordering
# =============================================================================


class TestOrdering:
    """Test ordering guarantees."""

    def test_pacing_metrics_ascending(self):
        """pacing_metrics are in ascending move_number order."""
        time_data = make_time_data(move_numbers=list(range(1, 11)))
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0) for i in range(1, 11)]
        result = analyze_pacing(time_data, moves)
        nums = [m.move_number for m in result.pacing_metrics]
        assert nums == sorted(nums)

    def test_episode_move_numbers_ascending(self):
        """TiltEpisode.move_numbers is ascending."""
        time_data = make_time_data(move_numbers=list(range(1, 21)))
        moves = []
        for i in range(1, 21):
            player = "B" if i % 2 == 1 else "W"
            if i in [1, 3, 5]:
                moves.append(make_move_eval(i, player, score_loss=10.0))
            else:
                moves.append(make_move_eval(i, player, score_loss=0.5))
        result = analyze_pacing(time_data, moves)
        for episode in result.tilt_episodes:
            assert list(episode.move_numbers) == sorted(episode.move_numbers)


# =============================================================================
# Test: game_stats Always Present
# =============================================================================


class TestGameStatsPresence:
    """Test that game_stats is always populated."""

    def test_game_stats_with_empty_moves(self):
        """game_stats present even with empty moves."""
        time_data = make_time_data(move_numbers=[1, 2, 3])
        result = analyze_pacing(time_data, [])
        assert result.game_stats is not None
        assert result.game_stats.total_moves_analyzed == 0

    def test_game_stats_with_insufficient_moves(self):
        """game_stats present even with < min_moves."""
        time_data = make_time_data(move_numbers=[1, 2, 3])
        moves = [make_move_eval(i, "B" if i % 2 == 1 else "W", score_loss=1.0) for i in range(1, 4)]
        config = PacingConfig(min_moves_for_stats=10)  # Require 10, have 3
        result = analyze_pacing(time_data, moves, config)
        assert result.game_stats is not None
        # Empty pacing_metrics due to insufficient moves
        assert result.pacing_metrics == ()


# =============================================================================
# Test: Import Safety
# =============================================================================


class TestImportSafety:
    """Test that imports are correct."""

    def test_pacing_module_imports(self):
        """pacing.py can be imported without errors."""
        from katrain.core.analysis.time import pacing

        assert hasattr(pacing, "analyze_pacing")
        assert hasattr(pacing, "PacingConfig")
        assert hasattr(pacing, "TiltSeverity")

    def test_package_exports(self):
        """Package exports all expected symbols."""
        from katrain.core.analysis.time import (
            PacingConfig,
            analyze_pacing,
        )

        assert analyze_pacing is not None
        assert PacingConfig is not None
