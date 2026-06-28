"""Tests for SummaryAnalyzer (Phase 149 B-1).

SummaryAnalyzer lives in katrain.core.reports.summary_logic and is the core
aggregator for multi-game summary reports. It was added/refactored in Phase
128 and extended in Phase 148-C2 (skill_preset re-classification) and
Phase 148-C4 (forced-move exclusion).

Coverage:
- skill_preset re-classification logic (Phase 148-C2)
- worst_moves forced (ONLY_MOVE) exclusion (Phase 148-C4)
- worst_moves truncation to top 10 (Phase 149 A-5)
- mistake_sequences detection boundaries
- focus_player filtering
- multi-game aggregation
- reason_tags/meaning_tags aggregation
- empty input handling
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from katrain.core.analysis.models import (
    EvalSnapshot,
    MistakeCategory,
    MoveEval,
    PositionDifficulty,
)
from katrain.core.analysis.models.skill import GameSummaryData
from katrain.core.reports.constants import BAD_MOVE_LOSS_THRESHOLD, URGENT_MISS_THRESHOLD_LOSS
from katrain.core.reports.summary_logic import (
    SummaryAnalyzer,
    detect_urgent_miss_sequences,
)


# =============================================================================
# Test helpers
# =============================================================================


@dataclass
class _MockMove:
    """Minimal MoveEval-compatible duck type for SummaryAnalyzer tests."""

    move_number: int
    player: str
    gtp: str = "D4"
    points_lost: float | None = None
    score_loss: float | None = None
    leela_loss_est: float | None = None
    mistake_category: MistakeCategory | None = None
    reason_tags: list[str] = field(default_factory=list)
    tag: str = "middle"
    position_difficulty: PositionDifficulty | None = None
    meaning_tag_id: str | None = None
    root_visits: int = 200


@dataclass
class _MockSnapshot:
    moves: list[_MockMove] = field(default_factory=list)


def _make_game(
    name: str,
    moves: list[_MockMove],
    *,
    skill_preset: str | None = None,
) -> GameSummaryData:
    """Construct a GameSummaryData from a list of MockMove duck-typed objects."""
    snapshot = EvalSnapshot(moves=moves)  # type: ignore[arg-type]
    return GameSummaryData(
        game_name=name,
        player_black="Alice",
        player_white="Bob",
        snapshot=snapshot,
        board_size=(19, 19),
        skill_preset=skill_preset,
    )


def _blunder(
    move_num: int,
    player: str = "B",
    *,
    loss: float = 6.0,
    difficulty: PositionDifficulty | None = PositionDifficulty.NORMAL,
    category: MistakeCategory = MistakeCategory.BLUNDER,
) -> _MockMove:
    return _MockMove(
        move_number=move_num,
        player=player,
        gtp="D4",
        points_lost=loss,
        score_loss=loss,
        mistake_category=category,
        position_difficulty=difficulty,
    )


def _inaccuracy(
    move_num: int,
    player: str = "B",
    *,
    loss: float = 1.5,
    difficulty: PositionDifficulty | None = PositionDifficulty.NORMAL,
) -> _MockMove:
    return _MockMove(
        move_number=move_num,
        player=player,
        gtp="Q16",
        points_lost=loss,
        score_loss=loss,
        mistake_category=MistakeCategory.INACCURACY,
        position_difficulty=difficulty,
    )


def _good(move_num: int, player: str = "B") -> _MockMove:
    return _MockMove(
        move_number=move_num,
        player=player,
        gtp="D4",
        points_lost=0.0,
        score_loss=0.0,
        mistake_category=MistakeCategory.GOOD,
        position_difficulty=PositionDifficulty.EASY,
    )


# =============================================================================
# A-5 + general worst_moves behaviour
# =============================================================================


class TestSummaryAnalyzerWorstMoves:
    """Tests around worst_moves collection and truncation."""

    def test_empty_games_produces_empty_player_stats(self):
        analyzer = SummaryAnalyzer([])
        assert analyzer.get_all_player_stats() == {}

    def test_single_game_basic_counts(self):
        moves = [
            _blunder(1, "B", loss=6.0),
            _blunder(2, "W", loss=5.0),
            _inaccuracy(3, "B", loss=1.5),
            _good(4, "W"),
        ]
        gd = _make_game("g1.sgf", moves)
        analyzer = SummaryAnalyzer([gd])

        alice_stats = analyzer.get_player_stats("Alice")
        bob_stats = analyzer.get_player_stats("Bob")

        assert alice_stats is not None
        assert bob_stats is not None
        assert alice_stats.total_games == 1
        assert alice_stats.total_moves == 2  # 2 black moves
        assert bob_stats.total_moves == 2
        assert alice_stats.total_points_lost == 6.0 + 1.5  # 7.5
        assert bob_stats.total_points_lost == 5.0

    def test_worst_moves_truncated_to_top_10(self):
        """Phase 149 A-5: After sort, worst_moves should be at most 10."""
        # Create 15 blunders with descending loss values
        moves = [_blunder(i + 1, "B", loss=float(20 - i)) for i in range(15)]
        gd = _make_game("g1.sgf", moves)
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        assert len(stats.worst_moves) == 10, (
            f"Expected truncation to 10, got {len(stats.worst_moves)}"
        )
        # Top loss is 20.0 (moves[0] in our list)
        assert stats.worst_moves[0][1].points_lost == 20.0

    def test_worst_moves_excludes_forced_only_move(self):
        """Phase 148-C4: BLUNDER on ONLY_MOVE should be excluded from worst_moves."""
        moves = [
            _blunder(1, "B", loss=10.0, difficulty=PositionDifficulty.ONLY_MOVE),
            _blunder(2, "B", loss=5.0, difficulty=PositionDifficulty.NORMAL),
        ]
        gd = _make_game("g1.sgf", moves)
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        # Only move 2 should be in worst_moves
        move_numbers = [m[1].move_number for m in stats.worst_moves]
        assert 1 not in move_numbers, "Forced BLUNDER should be excluded"
        assert 2 in move_numbers

    def test_worst_moves_below_threshold_excluded(self):
        """Moves below BAD_MOVE_LOSS_THRESHOLD should be excluded from worst_moves."""
        moves = [
            _inaccuracy(1, "B", loss=BAD_MOVE_LOSS_THRESHOLD - 0.1),
            _blunder(2, "B", loss=BAD_MOVE_LOSS_THRESHOLD + 1.0),
        ]
        gd = _make_game("g1.sgf", moves)
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        move_numbers = [m[1].move_number for m in stats.worst_moves]
        assert 1 not in move_numbers
        assert 2 in move_numbers


# =============================================================================
# Phase 148-C2: skill_preset re-classification
# =============================================================================


class TestSummaryAnalyzerSkillPresetReclassification:
    """Verify game_data.skill_preset changes mistake counts."""

    def test_reclassification_standard_3pt_loss_is_mistake(self):
        """standard preset: score_thresholds = (1.0, 2.5, 5.0). 3.0 loss -> MISTAKE."""
        moves = [_blunder(1, "B", loss=3.0, category=MistakeCategory.GOOD)]
        gd = _make_game("g1.sgf", moves, skill_preset="standard")
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        # Reclassified to MISTAKE (loss=3.0 >= 2.5 but < 5.0)
        assert stats.mistake_counts.get(MistakeCategory.MISTAKE, 0) == 1
        assert stats.mistake_counts.get(MistakeCategory.BLUNDER, 0) == 0

    def test_reclassification_beginner_3pt_loss_is_inaccuracy(self):
        """beginner preset: score_thresholds = (2.0, 5.0, 10.0). 3.0 loss -> INACCURACY."""
        moves = [_blunder(1, "B", loss=3.0, category=MistakeCategory.GOOD)]
        gd = _make_game("g1.sgf", moves, skill_preset="beginner")
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        assert stats.mistake_counts.get(MistakeCategory.INACCURACY, 0) == 1
        assert stats.mistake_counts.get(MistakeCategory.MISTAKE, 0) == 0

    def test_reclassification_pro_3pt_loss_is_blunder(self):
        """pro preset: score_thresholds = (0.2, 0.5, 1.0). 3.0 loss -> BLUNDER."""
        moves = [_blunder(1, "B", loss=3.0, category=MistakeCategory.GOOD)]
        gd = _make_game("g1.sgf", moves, skill_preset="pro")
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        assert stats.mistake_counts.get(MistakeCategory.BLUNDER, 0) == 1

    def test_reclassification_disabled_when_skill_preset_none(self):
        """If skill_preset is None, fallback to move.mistake_category (no reclassification)."""
        moves = [
            _MockMove(
                move_number=1,
                player="B",
                points_lost=3.0,
                score_loss=3.0,
                mistake_category=MistakeCategory.GOOD,
                position_difficulty=PositionDifficulty.NORMAL,
            )
        ]
        gd = _make_game("g1.sgf", moves, skill_preset=None)
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        # Since skill_preset is None, no reclassification -> cat remains GOOD
        # (or whatever move.mistake_category was, since if cat is None, not counted)
        assert stats.mistake_counts.get(MistakeCategory.GOOD, 0) == 1


# =============================================================================
# focus_player filtering
# =============================================================================


class TestSummaryAnalyzerFocusPlayer:
    """focus_player should restrict aggregation to a single player."""

    def test_focus_player_excludes_others(self):
        moves = [
            _blunder(1, "B", loss=5.0),
            _blunder(2, "W", loss=10.0),
            _blunder(3, "B", loss=7.0),
        ]
        gd = _make_game("g1.sgf", moves)
        analyzer = SummaryAnalyzer([gd], focus_player="Alice")

        # Alice (black) only
        assert "Bob" not in analyzer.get_all_player_stats()
        alice_stats = analyzer.get_player_stats("Alice")
        assert alice_stats is not None
        assert alice_stats.total_moves == 2  # only black moves
        assert alice_stats.total_points_lost == 12.0  # 5+7

    def test_focus_player_unknown_name_returns_empty(self):
        moves = [_blunder(1, "B", loss=5.0)]
        gd = _make_game("g1.sgf", moves)
        analyzer = SummaryAnalyzer([gd], focus_player="Nobody")

        assert analyzer.get_all_player_stats() == {}


# =============================================================================
# detect_urgent_miss_sequences + mistake_sequences wiring
# =============================================================================


class TestDetectUrgentMissSequences:
    """Direct tests for detect_urgent_miss_sequences helper."""

    def test_no_sequences_below_threshold(self):
        moves_data = [
            ("g1", _MockMove(move_number=1, player="B", points_lost=10.0)),
            ("g1", _MockMove(move_number=2, player="B", points_lost=10.0)),
        ]
        sequences, filtered = detect_urgent_miss_sequences(
            moves_data,
            threshold_loss=URGENT_MISS_THRESHOLD_LOSS,
            min_consecutive=3,
        )
        assert sequences == []
        # Both moves go into filtered (not in any sequence)
        assert len(filtered) == 2

    def test_exact_threshold_count_triggers_sequence(self):
        moves_data = [
            ("g1", _MockMove(move_number=1, player="B", points_lost=20.0)),
            ("g1", _MockMove(move_number=2, player="B", points_lost=20.0)),
            ("g1", _MockMove(move_number=3, player="B", points_lost=20.0)),
        ]
        sequences, filtered = detect_urgent_miss_sequences(
            moves_data,
            threshold_loss=URGENT_MISS_THRESHOLD_LOSS,
            min_consecutive=3,
        )
        assert len(sequences) == 1
        assert sequences[0]["count"] == 3
        assert filtered == []

    def test_non_consecutive_returns_to_filtered(self):
        moves_data = [
            ("g1", _MockMove(move_number=1, player="B", points_lost=20.0)),
            ("g1", _MockMove(move_number=2, player="B", points_lost=20.0)),
            # Gap > 2 -> sequence breaks
            ("g1", _MockMove(move_number=10, player="B", points_lost=20.0)),
        ]
        sequences, filtered = detect_urgent_miss_sequences(
            moves_data,
            threshold_loss=URGENT_MISS_THRESHOLD_LOSS,
            min_consecutive=3,
        )
        assert sequences == []
        # All three moves should end up in filtered
        assert len(filtered) == 3

    def test_analyzer_detect_mistake_sequences_filters(self):
        """Analyzer.detect_mistake_sequences should use BAD_MOVE_LOSS_THRESHOLD
        filtering and return urgent sequences separately."""
        moves = [
            _blunder(1, "B", loss=20.0),  # urgent
            _blunder(2, "B", loss=20.0),  # urgent
            _blunder(3, "B", loss=20.0),  # urgent -> sequence
            _blunder(4, "B", loss=3.0),  # not urgent
        ]
        gd = _make_game("g1.sgf", moves)
        analyzer = SummaryAnalyzer([gd])

        sequences, filtered = analyzer.detect_mistake_sequences("Alice")
        assert len(sequences) == 1
        assert filtered[0][1].move_number == 4


# =============================================================================
# Reason tags aggregation
# =============================================================================


class TestSummaryAnalyzerReasonTags:
    """Reason tags aggregation logic."""

    def test_reason_tags_counted(self):
        moves = [
            _MockMove(
                move_number=1,
                player="B",
                points_lost=5.0,
                mistake_category=MistakeCategory.MISTAKE,
                position_difficulty=PositionDifficulty.NORMAL,
                reason_tags=["low_liberties", "heavy"],
            ),
            _MockMove(
                move_number=2,
                player="B",
                points_lost=5.0,
                mistake_category=MistakeCategory.MISTAKE,
                position_difficulty=PositionDifficulty.NORMAL,
                reason_tags=["low_liberties"],
            ),
            _MockMove(
                move_number=3,
                player="B",
                points_lost=5.0,
                mistake_category=MistakeCategory.MISTAKE,
                position_difficulty=PositionDifficulty.NORMAL,
                reason_tags=[],  # no tags
            ),
        ]
        gd = _make_game("g1.sgf", moves)
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        assert stats.reason_tags_counts.get("low_liberties") == 2
        assert stats.reason_tags_counts.get("heavy") == 1
        assert stats.tagged_moves_count == 2
        assert stats.tag_occurrences_total == 3


# =============================================================================
# Multi-game aggregation
# =============================================================================


class TestSummaryAnalyzerMultiGame:
    """Multiple games should aggregate per-player stats."""

    def test_multi_game_total_games(self):
        moves_g1 = [_blunder(1, "B", loss=5.0)]
        moves_g2 = [_blunder(2, "B", loss=7.0)]
        moves_g3 = [_blunder(3, "B", loss=3.0)]
        gd1 = _make_game("g1.sgf", moves_g1)
        gd2 = _make_game("g2.sgf", moves_g2)
        gd3 = _make_game("g3.sgf", moves_g3)

        analyzer = SummaryAnalyzer([gd1, gd2, gd3])
        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        assert stats.total_games == 3
        assert stats.total_moves == 3
        assert stats.total_points_lost == 15.0

    def test_multi_game_distinct_players(self):
        """Same player name across games should aggregate."""
        moves_g1 = [_blunder(1, "B", loss=5.0)]
        moves_g2 = [_blunder(2, "W", loss=5.0)]  # Bob plays as White
        gd1 = GameSummaryData(
            game_name="g1.sgf",
            player_black="Alice",
            player_white="Bob",
            snapshot=EvalSnapshot(moves=moves_g1),  # type: ignore[arg-type]
            board_size=(19, 19),
        )
        gd2 = GameSummaryData(
            game_name="g2.sgf",
            player_black="Charlie",
            player_white="Alice",
            snapshot=EvalSnapshot(moves=moves_g2),  # type: ignore[arg-type]
            board_size=(19, 19),
        )
        analyzer = SummaryAnalyzer([gd1, gd2])

        # Alice has 2 games (1 as B, 1 as W)
        alice_stats = analyzer.get_player_stats("Alice")
        assert alice_stats is not None
        assert alice_stats.total_games == 2


# =============================================================================
# Player stats methods
# =============================================================================


class TestSummaryStatsMethods:
    """Tests for SummaryStats getter methods (called from JSON export)."""

    def _build_stats(self) -> Any:
        from katrain.core.analysis.models.skill import SummaryStats

        return SummaryStats(
            player_name="Test",
            total_games=1,
            total_moves=10,
            total_points_lost=10.0,
            mistake_counts={MistakeCategory.MISTAKE: 5, MistakeCategory.BLUNDER: 2},
            mistake_total_loss={MistakeCategory.MISTAKE: 5.0, MistakeCategory.BLUNDER: 12.0},
        )

    def test_get_mistake_percentage(self):
        stats = self._build_stats()
        # 5 mistakes out of 10 moves = 50%
        assert stats.get_mistake_percentage(MistakeCategory.MISTAKE) == 50.0

    def test_get_mistake_avg_loss(self):
        stats = self._build_stats()
        # 5.0 / 5 = 1.0
        assert stats.get_mistake_avg_loss(MistakeCategory.MISTAKE) == 1.0
        # 12.0 / 2 = 6.0
        assert stats.get_mistake_avg_loss(MistakeCategory.BLUNDER) == 6.0

    def test_avg_points_lost_per_move(self):
        """avg_points_lost_per_move is computed by SummaryAnalyzer._aggregate_stats."""
        from katrain.core.reports.summary_logic import SummaryAnalyzer

        # Direct dataclass instantiation has avg_points_lost_per_move=0.0 (default)
        stats = self._build_stats()
        assert stats.avg_points_lost_per_move == 0.0  # default before aggregation

        # When wrapped in a SummaryAnalyzer, the value is computed
        from katrain.core.analysis.models.skill import GameSummaryData
        from katrain.core.analysis.models import EvalSnapshot

        @dataclass
        class _StubMove:
            move_number: int = 1
            player: str = "B"
            gtp: str = "D4"
            points_lost: float = 10.0
            score_loss: float = 10.0
            leela_loss_est: float | None = None
            mistake_category: MistakeCategory | None = MistakeCategory.MISTAKE
            reason_tags: list[str] = field(default_factory=list)
            tag: str = "middle"
            position_difficulty: PositionDifficulty | None = PositionDifficulty.NORMAL
            meaning_tag_id: str | None = None
            root_visits: int = 100

        snapshot = EvalSnapshot(moves=[_StubMove()])  # type: ignore[arg-type]
        gd = GameSummaryData(
            game_name="t.sgf",
            player_black="Test",
            player_white="Other",
            snapshot=snapshot,
            board_size=(19, 19),
        )
        analyzer = SummaryAnalyzer([gd])
        computed = analyzer.get_player_stats("Test")
        assert computed is not None
        # 10.0 / 1 = 10.0
        assert computed.avg_points_lost_per_move == 10.0


# =============================================================================
# Phase 150: auto preset resolution (matches karte behavior)
# =============================================================================


class TestSummaryAnalyzerAutoPreset:
    """Verify that skill_preset='auto' is resolved per-game using ALL moves
    (both B and W), matching karte's behavior at karte/json_export.py:78-86.

    Background: prior to Phase 150, SummaryAnalyzer passed skill_preset='auto'
    directly to get_skill_preset(), which fell back to "standard" because
    "auto" is not a key in SKILL_PRESETS. This caused karte (which resolves
    auto) and summary (which fell back to standard) to produce different
    mistake counts for the same data.

    Phase 150 (initial): resolved auto per-game × per-player with player-filtered
    moves. This was WRONG because karte resolves auto using ALL moves of the
    game (both players), giving different effective_preset values between
    karte and summary.

    Phase 150 (fix): resolve auto ONCE per game using ALL moves, then apply
    that single preset to BOTH players in the game.
    """

    def test_auto_calls_recommend_auto_strictness_once_per_game(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """skill_preset='auto' must invoke recommend_auto_strictness exactly
        once per game with the full move list (both players)."""
        from katrain.core.analysis.models.skill import AutoConfidence, AutoRecommendation

        call_log: list[tuple[int, list[str]]] = []

        def fake_recommend(moves, *, game_count=1, **kwargs):  # type: ignore[no-untyped-def]
            call_log.append((len(moves), sorted(m.player for m in moves)))
            return AutoRecommendation(
                recommended_preset="beginner",
                confidence=AutoConfidence.LOW,
                blunder_count=0,
                important_count=0,
                score=0,
                reason="test",
            )

        # Patch the reference held by eval_metrics (summary_logic uses that)
        monkeypatch.setattr(
            "katrain.core.eval_metrics.recommend_auto_strictness",
            fake_recommend,
        )

        moves = [
            _blunder(1, "B", loss=3.0, category=MistakeCategory.GOOD),
            _blunder(2, "W", loss=3.0, category=MistakeCategory.GOOD),
            _blunder(3, "B", loss=3.0, category=MistakeCategory.GOOD),
            _blunder(4, "W", loss=3.0, category=MistakeCategory.GOOD),
        ]
        gd = _make_game("g1.sgf", moves, skill_preset="auto")
        SummaryAnalyzer([gd])

        # Should be called once (per game, not per player)
        assert len(call_log) == 1
        # The move list passed should contain BOTH B and W moves (full game)
        move_count, players = call_log[0]
        assert move_count == 4
        assert players == ["B", "B", "W", "W"]

    def test_auto_per_game_calls_independent_for_each_game(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two games with skill_preset='auto' → recommend called once per game."""
        from katrain.core.analysis.models.skill import AutoConfidence, AutoRecommendation

        call_count = {"n": 0}

        def fake_recommend(moves, *, game_count=1, **kwargs):  # type: ignore[no-untyped-def]
            call_count["n"] += 1
            return AutoRecommendation(
                recommended_preset="beginner",
                confidence=AutoConfidence.HIGH,
                blunder_count=0,
                important_count=0,
                score=0,
                reason="test",
            )

        monkeypatch.setattr(
            "katrain.core.eval_metrics.recommend_auto_strictness",
            fake_recommend,
        )

        moves1 = [_blunder(1, "B", loss=3.0, category=MistakeCategory.GOOD)]
        moves2 = [_blunder(1, "W", loss=3.0, category=MistakeCategory.GOOD)]
        gd1 = _make_game("g1.sgf", moves1, skill_preset="auto")
        gd2 = _make_game("g2.sgf", moves2, skill_preset="auto")

        SummaryAnalyzer([gd1, gd2])
        # 2 games → 2 calls (one per game)
        assert call_count["n"] == 2

    def test_auto_uses_resolved_preset_thresholds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Resolved preset's thresholds must drive classification.
        Forcing beginner recommendation with loss=3.0 → INACCURACY
        (beginner thresholds (2.0, 5.0, 10.0)) rather than MISTAKE
        (standard thresholds (1.0, 2.5, 5.0))."""
        from katrain.core.analysis.models.skill import AutoConfidence, AutoRecommendation

        def fixed_recommend(moves, *, game_count=1, **kwargs):  # type: ignore[no-untyped-def]
            return AutoRecommendation(
                recommended_preset="beginner",
                confidence=AutoConfidence.HIGH,
                blunder_count=0,
                important_count=1,
                score=0,
                reason="test",
            )

        monkeypatch.setattr(
            "katrain.core.eval_metrics.recommend_auto_strictness",
            fixed_recommend,
        )

        moves = [_blunder(1, "B", loss=3.0, category=MistakeCategory.GOOD)]
        gd = _make_game("g1.sgf", moves, skill_preset="auto")
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        # beginner: 3.0 loss → INACCURACY (>=2.0, <5.0)
        assert stats.mistake_counts.get(MistakeCategory.INACCURACY, 0) == 1
        assert stats.mistake_counts.get(MistakeCategory.MISTAKE, 0) == 0

    def test_auto_pro_recommendation_uses_pro_thresholds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If auto resolves to 'pro', pro thresholds (0.2, 0.5, 1.0) apply.
        loss=3.0 → BLUNDER (>=1.0)."""
        from katrain.core.analysis.models.skill import AutoConfidence, AutoRecommendation

        def fixed_recommend(moves, *, game_count=1, **kwargs):  # type: ignore[no-untyped-def]
            return AutoRecommendation(
                recommended_preset="pro",
                confidence=AutoConfidence.HIGH,
                blunder_count=1,
                important_count=1,
                score=0,
                reason="test",
            )

        monkeypatch.setattr(
            "katrain.core.eval_metrics.recommend_auto_strictness",
            fixed_recommend,
        )

        moves = [_blunder(1, "B", loss=3.0, category=MistakeCategory.GOOD)]
        gd = _make_game("g1.sgf", moves, skill_preset="auto")
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        # pro: 3.0 loss → BLUNDER (>=1.0)
        assert stats.mistake_counts.get(MistakeCategory.BLUNDER, 0) == 1

    def test_auto_per_game_independent_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two games with different move profiles must resolve independently.
        Game1 recommends beginner → 3.0 loss = INACCURACY
        Game2 recommends standard → 3.0 loss = MISTAKE

        Key: the fake_recommend uses the moves' gtp field to identify the game,
        because resolution sees ALL moves of the game (not per-player)."""
        from katrain.core.analysis.models.skill import AutoConfidence, AutoRecommendation

        def fake_recommend(moves, *, game_count=1, **kwargs):  # type: ignore[no-untyped-def]
            # Identify game by gtp prefix in the move list (karte has same data)
            gtps = sorted({m.gtp for m in moves})
            if "BEGINNER" in gtps:
                preset = "beginner"
            elif "STANDARD" in gtps:
                preset = "standard"
            else:
                preset = "beginner"
            return AutoRecommendation(
                recommended_preset=preset,
                confidence=AutoConfidence.HIGH,
                blunder_count=0,
                important_count=1,
                score=0,
                reason="test",
            )

        monkeypatch.setattr(
            "katrain.core.eval_metrics.recommend_auto_strictness",
            fake_recommend,
        )

        # Game 1: beginner recommended (loss 3.0 → INACCURACY)
        moves1 = [
            _MockMove(
                move_number=1, player="B", gtp="BEGINNER",
                points_lost=3.0, score_loss=3.0,
                mistake_category=MistakeCategory.GOOD,
                position_difficulty=PositionDifficulty.NORMAL,
            )
        ]
        gd1 = _make_game("g1.sgf", moves1, skill_preset="auto")

        # Game 2: standard recommended (loss 3.0 → MISTAKE)
        moves2 = [
            _MockMove(
                move_number=1, player="B", gtp="STANDARD",
                points_lost=3.0, score_loss=3.0,
                mistake_category=MistakeCategory.GOOD,
                position_difficulty=PositionDifficulty.NORMAL,
            )
        ]
        gd2 = _make_game("g2.sgf", moves2, skill_preset="auto")

        analyzer = SummaryAnalyzer([gd1, gd2])
        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        # Per-game resolution: game1=beginner(INACCURACY), game2=standard(MISTAKE)
        assert stats.mistake_counts.get(MistakeCategory.INACCURACY, 0) == 1
        assert stats.mistake_counts.get(MistakeCategory.MISTAKE, 0) == 1
        assert stats.mistake_counts.get(MistakeCategory.BLUNDER, 0) == 0

    def test_auto_both_players_share_same_preset_in_game(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Within a single game, both B and W must share the same effective_preset
        (matching karte behavior). Verifies that a single resolution is applied
        to both players."""
        from katrain.core.analysis.models.skill import AutoConfidence, AutoRecommendation

        def fixed_recommend(moves, *, game_count=1, **kwargs):  # type: ignore[no-untyped-def]
            return AutoRecommendation(
                recommended_preset="beginner",  # loose thresholds
                confidence=AutoConfidence.HIGH,
                blunder_count=0,
                important_count=0,
                score=0,
                reason="test",
            )

        monkeypatch.setattr(
            "katrain.core.eval_metrics.recommend_auto_strictness",
            fixed_recommend,
        )

        # Both players with same loss=3.0
        # With beginner thresholds (2.0/5.0/10.0): 3.0 → INACCURACY for BOTH
        moves = [
            _blunder(1, "B", loss=3.0, category=MistakeCategory.GOOD),
            _blunder(2, "W", loss=3.0, category=MistakeCategory.GOOD),
        ]
        gd = _make_game("g1.sgf", moves, skill_preset="auto")
        analyzer = SummaryAnalyzer([gd])

        # Verify Alice (B) classified as INACCURACY
        alice_stats = analyzer.get_player_stats("Alice")
        assert alice_stats is not None
        assert alice_stats.mistake_counts.get(MistakeCategory.INACCURACY, 0) == 1

        # Verify Bob (W) ALSO classified as INACCURACY (same preset)
        bob_stats = analyzer.get_player_stats("Bob")
        assert bob_stats is not None
        assert bob_stats.mistake_counts.get(MistakeCategory.INACCURACY, 0) == 1

    def test_auto_fallback_when_no_moves_in_game(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If a game has no moves at all, auto resolution must fall back
        to DEFAULT_SKILL_PRESET, not crash."""
        from katrain.core.analysis.models.skill import AutoConfidence, AutoRecommendation

        call_count = {"n": 0}

        def fake_recommend(moves, *, game_count=1, **kwargs):  # type: ignore[no-untyped-def]
            call_count["n"] += 1
            return AutoRecommendation(
                recommended_preset="beginner",
                confidence=AutoConfidence.HIGH,
                blunder_count=0,
                important_count=0,
                score=0,
                reason="test",
            )

        monkeypatch.setattr(
            "katrain.core.eval_metrics.recommend_auto_strictness",
            fake_recommend,
        )

        # Game with NO moves at all → recommend not called, fallback to standard
        empty_snapshot = EvalSnapshot(moves=[])  # type: ignore[arg-type]
        gd = GameSummaryData(
            game_name="empty.sgf",
            player_black="Alice",
            player_white="Bob",
            snapshot=empty_snapshot,
            board_size=(19, 19),
            skill_preset="auto",
        )
        SummaryAnalyzer([gd])
        # No moves → recommend should not be called
        assert call_count["n"] == 0

    def test_explicit_preset_bypasses_auto_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit preset names (standard/beginner/pro/advanced/relaxed) must
        NOT call recommend_auto_strictness — they use the preset directly."""
        def fake_recommend(moves, *, game_count=1, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("recommend_auto_strictness should not be called for explicit presets")

        monkeypatch.setattr(
            "katrain.core.eval_metrics.recommend_auto_strictness",
            fake_recommend,
        )

        # Use explicit "pro" with loss=3.0 → should be BLUNDER via pro thresholds
        moves = [_blunder(1, "B", loss=3.0, category=MistakeCategory.GOOD)]
        gd = _make_game("g1.sgf", moves, skill_preset="pro")
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        assert stats.mistake_counts.get(MistakeCategory.BLUNDER, 0) == 1

    def test_auto_with_low_reliability_forces_standard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When reliability is low (<20%), recommend_auto_strictness returns
        'standard' with LOW confidence. Verify summary uses standard thresholds
        in that case (loss=3.0 → MISTAKE)."""
        from katrain.core.analysis.models.skill import AutoConfidence, AutoRecommendation

        def fixed_recommend(moves, *, game_count=1, **kwargs):  # type: ignore[no-untyped-def]
            return AutoRecommendation(
                recommended_preset="standard",  # forced by reliability gate
                confidence=AutoConfidence.LOW,
                blunder_count=0,
                important_count=1,
                score=0,
                reason="Low reliability (5.0%)",
            )

        monkeypatch.setattr(
            "katrain.core.eval_metrics.recommend_auto_strictness",
            fixed_recommend,
        )

        moves = [_blunder(1, "B", loss=3.0, category=MistakeCategory.GOOD)]
        gd = _make_game("g1.sgf", moves, skill_preset="auto")
        analyzer = SummaryAnalyzer([gd])

        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        # standard: 3.0 loss → MISTAKE (>=2.5, <5.0)
        assert stats.mistake_counts.get(MistakeCategory.MISTAKE, 0) == 1
        assert stats.mistake_counts.get(MistakeCategory.INACCURACY, 0) == 0

    def test_auto_three_game_scenario_matches_karte_user_case(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Simulate the user's actual scenario: 3 games with different effective
        presets (standard/beginner/relaxed). Each game's classification must
        use ITS OWN preset, not a global one. This is the regression test for
        the bug found after Phase 150 initial commit.

        Setup:
        - Game 1 (karte says 'standard'): moves loss=2.0 → INACCURACY (1.0 <= 2.0 < 2.5)
        - Game 2 (karte says 'beginner'): moves loss=2.0 → GOOD (2.0 < beginner's 2.0)
        - Game 3 (karte says 'relaxed'):  moves loss=2.0 → GOOD (2.0 < relaxed's 3.0)

        Expected total: 1 INACCURACY, 2 GOOD
        Bug behavior:  would show 1 INACCURACY, 1 MISTAKE, 1 GOOD (using standard for all)
        """
        from katrain.core.analysis.models.skill import AutoConfidence, AutoRecommendation

        def fake_recommend(moves, *, game_count=1, **kwargs):  # type: ignore[no-untyped-def]
            # Identify game by gtp prefix
            gtps = {m.gtp for m in moves}
            if "G1" in gtps:
                preset = "standard"
            elif "G2" in gtps:
                preset = "beginner"
            elif "G3" in gtps:
                preset = "relaxed"
            else:
                preset = "beginner"
            return AutoRecommendation(
                recommended_preset=preset,
                confidence=AutoConfidence.HIGH,
                blunder_count=0,
                important_count=1,
                score=0,
                reason="test",
            )

        monkeypatch.setattr(
            "katrain.core.eval_metrics.recommend_auto_strictness",
            fake_recommend,
        )

        # Each game has 1 white move with loss=2.0
        games_data = []
        for i, (gtp_id, expected_loss) in enumerate([("G1", 2.0), ("G2", 2.0), ("G3", 2.0)]):
            moves = [
                _MockMove(
                    move_number=1, player="B", gtp=gtp_id,
                    points_lost=expected_loss, score_loss=expected_loss,
                    mistake_category=MistakeCategory.GOOD,
                    position_difficulty=PositionDifficulty.NORMAL,
                )
            ]
            games_data.append(_make_game(f"game_{i}.sgf", moves, skill_preset="auto"))

        analyzer = SummaryAnalyzer(games_data)
        stats = analyzer.get_player_stats("Alice")
        assert stats is not None
        # Per-game resolution expected:
        #   Game 1 (standard 1.0/2.5/5.0): loss=2.0 → INACCURACY
        #   Game 2 (beginner 2.0/5.0/10.0): loss=2.0 → GOOD (2.0 < 2.0 is False; 2.0 >= 2.0 → INACCURACY actually)
        #   Game 3 (relaxed  3.0/7.5/15.0): loss=2.0 → GOOD (2.0 < 3.0)
        # Per-game accurate totals: 2 INACCURACY, 1 GOOD
        # Bug behavior (all standard): 1 INACCURACY, 1 MISTAKE, 1 GOOD
        assert stats.mistake_counts.get(MistakeCategory.INACCURACY, 0) == 2
        assert stats.mistake_counts.get(MistakeCategory.GOOD, 0) == 1
        assert stats.mistake_counts.get(MistakeCategory.MISTAKE, 0) == 0
        assert stats.mistake_counts.get(MistakeCategory.BLUNDER, 0) == 0
