"""
Structural tests for karte (single-game report) improvements.

These tests verify the structure of generated karte reports without
depending on exact text content (which would be brittle).
"""

from unittest.mock import Mock, patch

import pytest
from katrain.core.eval_metrics import (
    EvalSnapshot,
    MistakeStreak,
    MoveEval,
    PhaseMistakeStats,
    PositionDifficulty,
    _assess_difficulty_from_policy,
    aggregate_phase_mistake_stats,
    classify_game_phase,
    detect_mistake_streaks,
    get_practice_priorities_from_stats,
    snapshot_from_nodes,
)


class TestPhaseMistakeStats:
    """Tests for PhaseMistakeStats dataclass."""

    def test_empty_stats(self):
        """Empty stats should have zero counts."""
        stats = PhaseMistakeStats()
        assert stats.total_moves == 0
        assert stats.total_loss == 0.0
        assert stats.phase_mistake_counts == {}
        assert stats.phase_mistake_loss == {}


class TestAggregatePhaseMistakeStats:
    """Tests for aggregate_phase_mistake_stats function."""

    def test_empty_moves(self):
        """Empty move list should produce empty stats."""
        stats = aggregate_phase_mistake_stats([])
        assert stats.total_moves == 0
        assert stats.total_loss == 0.0

    def test_single_move_opening(self):
        """Single opening move should be classified correctly."""
        move = MoveEval(
            move_number=10,  # opening (<50)
            player="B",
            gtp="D4",
            score_before=0.0,
            score_after=0.0,
            delta_score=0.0,
            winrate_before=0.5,
            winrate_after=0.5,
            delta_winrate=0.0,
            points_lost=0.5,  # GOOD (<1.0)
            realized_points_lost=None,
            root_visits=100,
        )
        stats = aggregate_phase_mistake_stats([move])
        assert stats.total_moves == 1
        assert ("opening", "GOOD") in stats.phase_mistake_counts
        assert stats.phase_mistake_counts[("opening", "GOOD")] == 1

    def test_middle_game_blunder(self):
        """Middle game blunder should be classified correctly."""
        move = MoveEval(
            move_number=100,  # middle (50-200)
            player="W",
            gtp="Q16",
            score_before=5.0,
            score_after=-3.0,
            delta_score=-8.0,
            winrate_before=0.6,
            winrate_after=0.4,
            delta_winrate=-0.2,
            points_lost=8.0,  # BLUNDER (>=7.0)
            realized_points_lost=None,
            root_visits=100,
        )
        stats = aggregate_phase_mistake_stats([move])
        assert stats.total_moves == 1
        assert ("middle", "BLUNDER") in stats.phase_mistake_counts
        assert stats.phase_mistake_counts[("middle", "BLUNDER")] == 1
        assert stats.phase_mistake_loss[("middle", "BLUNDER")] == 8.0

    def test_yose_mistake(self):
        """Endgame (yose) mistake should be classified correctly."""
        move = MoveEval(
            move_number=250,  # yose (>=200)
            player="B",
            gtp="S1",
            score_before=10.0,
            score_after=7.0,
            delta_score=-3.0,
            winrate_before=0.7,
            winrate_after=0.65,
            delta_winrate=-0.05,
            points_lost=4.0,  # MISTAKE (3.0-7.0)
            realized_points_lost=None,
            root_visits=100,
        )
        stats = aggregate_phase_mistake_stats([move])
        assert stats.total_moves == 1
        assert ("yose", "MISTAKE") in stats.phase_mistake_counts

    def test_custom_thresholds(self):
        """Custom thresholds should be respected."""
        move = MoveEval(
            move_number=10,
            player="B",
            gtp="D4",
            score_before=0.0,
            score_after=0.0,
            delta_score=0.0,
            winrate_before=0.5,
            winrate_after=0.5,
            delta_winrate=0.0,
            points_lost=2.0,  # Would be INACCURACY with default, but BLUNDER with strict
            realized_points_lost=None,
            root_visits=100,
        )
        # With strict thresholds (0.5, 1.0, 2.0)
        stats = aggregate_phase_mistake_stats([move], score_thresholds=(0.5, 1.0, 2.0))
        assert ("opening", "BLUNDER") in stats.phase_mistake_counts

    def test_multiple_moves(self):
        """Multiple moves should be aggregated correctly."""
        moves = [
            MoveEval(
                move_number=10, player="B", gtp="D4",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.5, realized_points_lost=None, root_visits=100,
            ),
            MoveEval(
                move_number=100, player="B", gtp="Q10",
                score_before=0.0, score_after=-5.0, delta_score=-5.0,
                winrate_before=0.5, winrate_after=0.4, delta_winrate=-0.1,
                points_lost=5.0, realized_points_lost=None, root_visits=100,
            ),
            MoveEval(
                move_number=150, player="B", gtp="R15",
                score_before=-5.0, score_after=-10.0, delta_score=-5.0,
                winrate_before=0.4, winrate_after=0.3, delta_winrate=-0.1,
                points_lost=5.0, realized_points_lost=None, root_visits=100,
            ),
        ]
        stats = aggregate_phase_mistake_stats(moves)
        assert stats.total_moves == 3
        assert stats.phase_moves["opening"] == 1
        assert stats.phase_moves["middle"] == 2


class TestGetPracticePrioritiesFromStats:
    """Tests for get_practice_priorities_from_stats function."""

    def test_empty_stats_returns_empty(self):
        """Empty stats should return empty priorities."""
        stats = PhaseMistakeStats()
        priorities = get_practice_priorities_from_stats(stats)
        assert priorities == []

    def test_returns_priorities_for_losses(self):
        """Should return priorities based on loss data."""
        stats = PhaseMistakeStats(
            phase_mistake_counts={("middle", "BLUNDER"): 3},
            phase_mistake_loss={("middle", "BLUNDER"): 25.0},
            total_moves=10,
        )
        priorities = get_practice_priorities_from_stats(stats)
        assert len(priorities) >= 1
        # Should mention middle game and blunder
        assert "中盤" in priorities[0]
        assert "大悪手" in priorities[0]

    def test_max_priorities_respected(self):
        """Should respect max_priorities parameter."""
        stats = PhaseMistakeStats(
            phase_mistake_counts={
                ("opening", "INACCURACY"): 5,
                ("middle", "MISTAKE"): 4,
                ("yose", "BLUNDER"): 3,
            },
            phase_mistake_loss={
                ("opening", "INACCURACY"): 10.0,
                ("middle", "MISTAKE"): 20.0,
                ("yose", "BLUNDER"): 30.0,
            },
            total_moves=20,
        )
        priorities = get_practice_priorities_from_stats(stats, max_priorities=1)
        assert len(priorities) == 1

    def test_excludes_good_moves(self):
        """GOOD moves should not appear in priorities."""
        stats = PhaseMistakeStats(
            phase_mistake_counts={("opening", "GOOD"): 50},
            phase_mistake_loss={("opening", "GOOD"): 0.0},
            total_moves=50,
        )
        priorities = get_practice_priorities_from_stats(stats)
        assert priorities == []

    def test_fallback_to_phase_loss(self):
        """Should fallback to phase_loss if no mistake data."""
        stats = PhaseMistakeStats(
            phase_loss={"middle": 15.0},
            total_moves=10,
        )
        priorities = get_practice_priorities_from_stats(stats)
        assert len(priorities) >= 1
        assert "中盤" in priorities[0]


class TestReasonTagsHandling:
    """Tests for reason_tags handling in MoveEval."""

    def test_move_eval_default_reason_tags(self):
        """MoveEval should default to empty reason_tags."""
        move = MoveEval(
            move_number=1, player="B", gtp="D4",
            score_before=0.0, score_after=0.0, delta_score=0.0,
            winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
            points_lost=0.0, realized_points_lost=None, root_visits=100,
        )
        assert move.reason_tags == []

    def test_move_eval_with_reason_tags(self):
        """MoveEval should accept reason_tags."""
        move = MoveEval(
            move_number=1, player="B", gtp="D4",
            score_before=0.0, score_after=0.0, delta_score=0.0,
            winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
            points_lost=0.0, realized_points_lost=None, root_visits=100,
            reason_tags=["atari", "low_liberties"],
        )
        assert move.reason_tags == ["atari", "low_liberties"]

    def test_unknown_tag_is_valid(self):
        """'unknown' should be a valid reason tag."""
        move = MoveEval(
            move_number=1, player="B", gtp="D4",
            score_before=0.0, score_after=0.0, delta_score=0.0,
            winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
            points_lost=0.0, realized_points_lost=None, root_visits=100,
            reason_tags=["unknown"],
        )
        assert move.reason_tags == ["unknown"]
        assert "unknown" in move.reason_tags


class TestClassifyGamePhase:
    """Tests for classify_game_phase with board size support."""

    def test_19x19_opening(self):
        """19x19 opening phase."""
        assert classify_game_phase(10, board_size=19) == "opening"
        assert classify_game_phase(49, board_size=19) == "opening"

    def test_19x19_middle(self):
        """19x19 middle game phase."""
        assert classify_game_phase(50, board_size=19) == "middle"
        assert classify_game_phase(100, board_size=19) == "middle"
        assert classify_game_phase(199, board_size=19) == "middle"

    def test_19x19_yose(self):
        """19x19 endgame phase."""
        assert classify_game_phase(200, board_size=19) == "yose"
        assert classify_game_phase(300, board_size=19) == "yose"

    def test_13x13_opening(self):
        """13x13 opening phase (shorter than 19x19)."""
        assert classify_game_phase(10, board_size=13) == "opening"
        assert classify_game_phase(29, board_size=13) == "opening"

    def test_13x13_middle(self):
        """13x13 middle game phase."""
        assert classify_game_phase(30, board_size=13) == "middle"
        assert classify_game_phase(50, board_size=13) == "middle"
        assert classify_game_phase(99, board_size=13) == "middle"

    def test_13x13_yose(self):
        """13x13 endgame phase."""
        assert classify_game_phase(100, board_size=13) == "yose"

    def test_9x9_opening(self):
        """9x9 opening phase (much shorter)."""
        assert classify_game_phase(5, board_size=9) == "opening"
        assert classify_game_phase(14, board_size=9) == "opening"

    def test_9x9_middle(self):
        """9x9 middle game phase."""
        assert classify_game_phase(15, board_size=9) == "middle"
        assert classify_game_phase(30, board_size=9) == "middle"
        assert classify_game_phase(49, board_size=9) == "middle"

    def test_9x9_yose(self):
        """9x9 endgame phase."""
        assert classify_game_phase(50, board_size=9) == "yose"

    def test_default_board_size(self):
        """Default board size should be 19."""
        assert classify_game_phase(10) == "opening"
        assert classify_game_phase(100) == "middle"
        assert classify_game_phase(250) == "yose"


class TestAggregatePhaseMistakeStatsWithBoardSize:
    """Tests for aggregate_phase_mistake_stats with board_size parameter."""

    def test_9x9_phase_classification(self):
        """9x9 moves should use correct phase thresholds."""
        move = MoveEval(
            move_number=20,  # Would be opening on 19x19, but middle on 9x9
            player="B",
            gtp="D4",
            score_before=0.0, score_after=-5.0, delta_score=-5.0,
            winrate_before=0.5, winrate_after=0.4, delta_winrate=-0.1,
            points_lost=5.0,
            realized_points_lost=None, root_visits=100,
        )
        stats_19 = aggregate_phase_mistake_stats([move], board_size=19)
        stats_9 = aggregate_phase_mistake_stats([move], board_size=9)

        # On 19x19, move 20 is opening
        assert ("opening", "MISTAKE") in stats_19.phase_mistake_counts
        # On 9x9, move 20 is middle
        assert ("middle", "MISTAKE") in stats_9.phase_mistake_counts


class TestMistakeStreak:
    """Tests for MistakeStreak dataclass."""

    def test_avg_loss(self):
        """avg_loss should compute correctly."""
        streak = MistakeStreak(
            player="B",
            start_move=10,
            end_move=14,
            move_count=3,
            total_loss=15.0,
        )
        assert streak.avg_loss == 5.0

    def test_avg_loss_zero_moves(self):
        """avg_loss should handle zero moves."""
        streak = MistakeStreak(
            player="B",
            start_move=0,
            end_move=0,
            move_count=0,
            total_loss=0.0,
        )
        assert streak.avg_loss == 0.0


class TestDetectMistakeStreaks:
    """Tests for detect_mistake_streaks function."""

    def test_empty_moves(self):
        """Empty moves should return no streaks."""
        streaks = detect_mistake_streaks([])
        assert streaks == []

    def test_no_mistakes(self):
        """Moves with no significant loss should return no streaks."""
        moves = [
            MoveEval(
                move_number=i, player="B" if i % 2 == 1 else "W", gtp="D4",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.5,  # Below threshold
                realized_points_lost=None, root_visits=100,
            )
            for i in range(1, 11)
        ]
        streaks = detect_mistake_streaks(moves, loss_threshold=2.0)
        assert streaks == []

    def test_single_mistake_not_streak(self):
        """Single mistake should not form a streak."""
        moves = [
            MoveEval(
                move_number=2, player="B", gtp="D4",
                score_before=0.0, score_after=-5.0, delta_score=-5.0,
                winrate_before=0.5, winrate_after=0.4, delta_winrate=-0.1,
                points_lost=5.0,
                realized_points_lost=None, root_visits=100,
            ),
            MoveEval(
                move_number=4, player="B", gtp="Q10",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.5,  # Good move, breaks streak
                realized_points_lost=None, root_visits=100,
            ),
        ]
        streaks = detect_mistake_streaks(moves, loss_threshold=2.0, min_consecutive=2)
        assert streaks == []

    def test_consecutive_mistakes_form_streak(self):
        """Consecutive mistakes by same player should form a streak."""
        moves = [
            MoveEval(
                move_number=2, player="B", gtp="D4",
                score_before=0.0, score_after=-3.0, delta_score=-3.0,
                winrate_before=0.5, winrate_after=0.45, delta_winrate=-0.05,
                points_lost=3.0,
                realized_points_lost=None, root_visits=100,
            ),
            MoveEval(
                move_number=4, player="B", gtp="Q10",
                score_before=-3.0, score_after=-7.0, delta_score=-4.0,
                winrate_before=0.45, winrate_after=0.35, delta_winrate=-0.1,
                points_lost=4.0,
                realized_points_lost=None, root_visits=100,
            ),
            MoveEval(
                move_number=6, player="B", gtp="R15",
                score_before=-7.0, score_after=-12.0, delta_score=-5.0,
                winrate_before=0.35, winrate_after=0.25, delta_winrate=-0.1,
                points_lost=5.0,
                realized_points_lost=None, root_visits=100,
            ),
        ]
        streaks = detect_mistake_streaks(moves, loss_threshold=2.0, min_consecutive=2)
        assert len(streaks) == 1
        assert streaks[0].player == "B"
        assert streaks[0].move_count == 3
        assert streaks[0].total_loss == 12.0
        assert streaks[0].start_move == 2
        assert streaks[0].end_move == 6

    def test_go_aware_streak_detection(self):
        """Streak should only count same-player moves (Go-aware)."""
        # Black makes 3 consecutive mistakes, with White moves in between
        moves = [
            MoveEval(
                move_number=1, player="B", gtp="D4",
                score_before=0.0, score_after=-3.0, delta_score=-3.0,
                winrate_before=0.5, winrate_after=0.45, delta_winrate=-0.05,
                points_lost=3.0,
                realized_points_lost=None, root_visits=100,
            ),
            MoveEval(
                move_number=2, player="W", gtp="Q16",
                score_before=-3.0, score_after=-3.0, delta_score=0.0,
                winrate_before=0.45, winrate_after=0.45, delta_winrate=0.0,
                points_lost=0.0,  # White plays well
                realized_points_lost=None, root_visits=100,
            ),
            MoveEval(
                move_number=3, player="B", gtp="Q10",
                score_before=-3.0, score_after=-7.0, delta_score=-4.0,
                winrate_before=0.45, winrate_after=0.35, delta_winrate=-0.1,
                points_lost=4.0,
                realized_points_lost=None, root_visits=100,
            ),
        ]
        streaks = detect_mistake_streaks(moves, loss_threshold=2.0, min_consecutive=2)
        assert len(streaks) == 1
        assert streaks[0].player == "B"
        assert streaks[0].move_count == 2  # Only Black's moves count

    def test_multiple_streaks(self):
        """Should detect multiple streaks for same player."""
        moves = [
            # First streak
            MoveEval(
                move_number=2, player="B", gtp="D4", score_before=0.0, score_after=-3.0,
                delta_score=-3.0, winrate_before=0.5, winrate_after=0.45, delta_winrate=-0.05,
                points_lost=3.0, realized_points_lost=None, root_visits=100,
            ),
            MoveEval(
                move_number=4, player="B", gtp="Q10", score_before=-3.0, score_after=-6.0,
                delta_score=-3.0, winrate_before=0.45, winrate_after=0.4, delta_winrate=-0.05,
                points_lost=3.0, realized_points_lost=None, root_visits=100,
            ),
            # Good move breaks streak
            MoveEval(
                move_number=6, player="B", gtp="R15", score_before=-6.0, score_after=-6.0,
                delta_score=0.0, winrate_before=0.4, winrate_after=0.4, delta_winrate=0.0,
                points_lost=0.0, realized_points_lost=None, root_visits=100,
            ),
            # Second streak
            MoveEval(
                move_number=8, player="B", gtp="S1", score_before=-6.0, score_after=-10.0,
                delta_score=-4.0, winrate_before=0.4, winrate_after=0.3, delta_winrate=-0.1,
                points_lost=4.0, realized_points_lost=None, root_visits=100,
            ),
            MoveEval(
                move_number=10, player="B", gtp="A1", score_before=-10.0, score_after=-15.0,
                delta_score=-5.0, winrate_before=0.3, winrate_after=0.2, delta_winrate=-0.1,
                points_lost=5.0, realized_points_lost=None, root_visits=100,
            ),
        ]
        streaks = detect_mistake_streaks(moves, loss_threshold=2.0, min_consecutive=2)
        assert len(streaks) == 2
        assert streaks[0].start_move == 2
        assert streaks[1].start_move == 8


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
                move_number=1, player="B", gtp="D4",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.0, realized_points_lost=None, root_visits=100,
                position_difficulty=PositionDifficulty.EASY,
            ),
            MoveEval(
                move_number=2, player="W", gtp="Q16",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.0, realized_points_lost=None, root_visits=100,
                position_difficulty=PositionDifficulty.UNKNOWN,
            ),
            MoveEval(
                move_number=3, player="B", gtp="D16",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.0, realized_points_lost=None, root_visits=100,
                position_difficulty=None,  # Also counts as UNKNOWN
            ),
        ]
        snapshot = EvalSnapshot(moves=moves)
        assert snapshot.difficulty_unknown_count == 2

    def test_difficulty_unknown_rate(self):
        """Should calculate UNKNOWN rate correctly."""
        moves = [
            MoveEval(
                move_number=1, player="B", gtp="D4",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.0, realized_points_lost=None, root_visits=100,
                position_difficulty=PositionDifficulty.EASY,
            ),
            MoveEval(
                move_number=2, player="W", gtp="Q16",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.0, realized_points_lost=None, root_visits=100,
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
                move_number=1, player="B", gtp="D4",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.0, realized_points_lost=None, root_visits=100,
                position_difficulty=PositionDifficulty.EASY,
            ),
            MoveEval(
                move_number=2, player="W", gtp="Q16",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.0, realized_points_lost=None, root_visits=100,
                position_difficulty=PositionDifficulty.EASY,
            ),
            MoveEval(
                move_number=3, player="B", gtp="D16",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.0, realized_points_lost=None, root_visits=100,
                position_difficulty=PositionDifficulty.HARD,
            ),
            MoveEval(
                move_number=4, player="W", gtp="Q4",
                score_before=0.0, score_after=0.0, delta_score=0.0,
                winrate_before=0.5, winrate_after=0.5, delta_winrate=0.0,
                points_lost=0.0, realized_points_lost=None, root_visits=100,
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
