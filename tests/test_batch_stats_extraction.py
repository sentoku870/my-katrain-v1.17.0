"""Phase 199C-2: batch/stats/extraction.py tests.

Target: raise coverage from 17% to ~80%.

Covers:
- extract_game_stats: metadata extraction, phase classification,
  mistake categorization, reliability tracking, worst moves,
  pattern data, summary_data creation, error handling
- extract_players_from_stats: player grouping, min_games filter,
  skip_names, name normalization

Uses mock Game/snapshot objects to avoid full Kivy/engine setup.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, PropertyMock

import pytest

from katrain.core.analysis.models import MoveEval
from katrain.core.analysis.models.enums import MistakeCategory, PositionDifficulty
from katrain.core.batch.stats.extraction import extract_game_stats, extract_players_from_stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_move(
    move_number: int = 1,
    player: str = "B",
    gtp: str = "D4",
    points_lost: float = 0.0,
    score_loss: float | None = None,
    mistake_category: MistakeCategory = MistakeCategory.GOOD,
    position_difficulty: PositionDifficulty | None = None,
    root_visits: int = 200,
    reason_tags: list[str] | None = None,
    meaning_tag_id: str | None = None,
) -> MoveEval:
    return MoveEval(
        move_number=move_number,
        player=player,
        gtp=gtp,
        score_before=0.0,
        score_after=0.0,
        delta_score=0.0,
        winrate_before=0.5,
        winrate_after=0.5,
        delta_winrate=0.0,
        points_lost=points_lost,
        realized_points_lost=None,
        root_visits=root_visits,
        score_loss=score_loss,
        mistake_category=mistake_category,
        position_difficulty=position_difficulty,
        reason_tags=reason_tags or [],
        meaning_tag_id=meaning_tag_id,
    )


def _make_mock_snapshot(moves: list[MoveEval], total_points_lost: float | None = None) -> MagicMock:
    snap = MagicMock()
    snap.moves = moves
    snap.total_points_lost = total_points_lost if total_points_lost is not None else sum(
        (m.points_lost or 0) for m in moves
    )
    return snap


def _make_mock_game(
    snapshot: Any = None,
    properties: dict[str, Any] | None = None,
    important_moves: list[MoveEval] | None = None,
    game_id: str = "test_game",
) -> MagicMock:
    game = MagicMock()
    props = properties or {"PB": "Alice", "PW": "Bob", "SZ": "19", "KM": "6.5", "HA": "0"}
    root = MagicMock()
    root.get_property = lambda key, default=None: props.get(key, default)
    game.root = root

    if snapshot is not None:
        game.build_eval_snapshot.return_value = snapshot
    else:
        game.build_eval_snapshot.return_value = _make_mock_snapshot([])

    game.get_important_move_evals.return_value = important_moves or []
    game.game_id = game_id
    return game


# ---------------------------------------------------------------------------
# extract_game_stats
# ---------------------------------------------------------------------------


class TestExtractGameStatsBasic:
    """Test basic extract_game_stats functionality."""

    def test_returns_none_for_empty_snapshot(self):
        snapshot = _make_mock_snapshot([])
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "test.sgf")
        assert result is None

    def test_returns_none_on_log_cb(self):
        snapshot = _make_mock_snapshot([])
        game = _make_mock_game(snapshot=snapshot)
        logs: list[str] = []
        result = extract_game_stats(game, "test.sgf", log_cb=logs.append)
        assert result is None
        assert any("no valid moves" in msg for msg in logs)

    def test_returns_none_on_exception(self):
        game = MagicMock()
        game.build_eval_snapshot.side_effect = RuntimeError("boom")
        result = extract_game_stats(game, "test.sgf")
        assert result is None

    def test_logs_exception_message(self):
        game = MagicMock()
        game.build_eval_snapshot.side_effect = RuntimeError("kaboom")
        logs: list[str] = []
        result = extract_game_stats(game, "test.sgf", log_cb=logs.append)
        assert result is None
        assert any("Stats extraction failed" in msg for msg in logs)

    def test_uses_provided_snapshot(self):
        moves = [_make_move(move_number=1, player="B")]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=None)  # build_eval_snapshot not called
        result = extract_game_stats(game, "test.sgf", snapshot=snapshot)
        assert result is not None
        game.build_eval_snapshot.assert_not_called()


class TestExtractGameStatsMetadata:
    """Test metadata extraction from game root."""

    def test_extracts_player_names(self):
        moves = [_make_move(player="B"), _make_move(move_number=2, player="W")]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(
            snapshot=snapshot,
            properties={"PB": "Hikaru", "PW": "Magnus", "SZ": "19", "KM": "6.5", "HA": "0"},
        )
        result = extract_game_stats(game, "game.sgf")
        assert result["player_black"] == "Hikaru"
        assert result["player_white"] == "Magnus"

    def test_extracts_handicap(self):
        moves = [_make_move()]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot, properties={"SZ": "19", "HA": "3"})
        result = extract_game_stats(game, "game.sgf")
        assert result["handicap"] == 3

    def test_extracts_board_size(self):
        moves = [_make_move()]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot, properties={"SZ": "9"})
        result = extract_game_stats(game, "game.sgf")
        assert result["board_size"] == (9, 9)

    def test_invalid_board_size_defaults_19(self):
        moves = [_make_move()]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot, properties={"SZ": "invalid"})
        result = extract_game_stats(game, "game.sgf")
        assert result["board_size"] == (19, 19)

    def test_extracts_komi(self):
        moves = [_make_move()]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot, properties={"SZ": "19", "KM": "7.5"})
        result = extract_game_stats(game, "game.sgf")
        assert result is not None

    def test_invalid_komi_defaults(self):
        moves = [_make_move()]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot, properties={"SZ": "19", "KM": "invalid"})
        result = extract_game_stats(game, "game.sgf")
        assert result is not None

    def test_extracts_rank_tags(self):
        moves = [_make_move()]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(
            snapshot=snapshot,
            properties={"SZ": "19", "BR": "7d", "WR": "3d"},
        )
        result = extract_game_stats(game, "game.sgf")
        assert result["rank_black"] == "7d"
        assert result["rank_white"] == "3d"


class TestExtractGameStatsMoveIteration:
    """Test stats computation during move iteration."""

    def test_counts_moves_by_player(self):
        moves = [
            _make_move(move_number=1, player="B"),
            _make_move(move_number=2, player="W"),
            _make_move(move_number=3, player="B"),
        ]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert result["moves_by_player"]["B"] == 2
        assert result["moves_by_player"]["W"] == 1

    def test_total_moves(self):
        moves = [_make_move(move_number=i, player="B" if i % 2 else "W") for i in range(1, 6)]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert result["total_moves"] == 5

    def test_loss_by_player(self):
        moves = [
            _make_move(move_number=1, player="B", points_lost=3.0),
            _make_move(move_number=2, player="W", points_lost=2.0),
        ]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert result["loss_by_player"]["B"] == 3.0
        assert result["loss_by_player"]["W"] == 2.0

    def test_mistake_categories_counted(self):
        moves = [
            _make_move(move_number=1, player="B", points_lost=3.0, mistake_category=MistakeCategory.MISTAKE),
            _make_move(move_number=2, player="W", points_lost=6.0, mistake_category=MistakeCategory.BLUNDER),
        ]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert result["mistake_counts"][MistakeCategory.MISTAKE] == 1
        assert result["mistake_counts"][MistakeCategory.BLUNDER] == 1

    def test_forced_blunder_excluded(self):
        """BLUNDER on ONLY_MOVE should be excluded from mistake aggregation."""
        moves = [
            _make_move(
                move_number=1,
                player="B",
                points_lost=6.0,
                mistake_category=MistakeCategory.BLUNDER,
                position_difficulty=PositionDifficulty.ONLY_MOVE,
            ),
        ]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert result["mistake_counts"][MistakeCategory.BLUNDER] == 0

    def test_freedom_counts_tracked(self):
        moves = [
            _make_move(move_number=1, player="B", position_difficulty=PositionDifficulty.EASY),
            _make_move(move_number=2, player="W", position_difficulty=PositionDifficulty.HARD),
        ]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert result["freedom_counts"][PositionDifficulty.EASY] == 1
        assert result["freedom_counts"][PositionDifficulty.HARD] == 1

    def test_worst_moves_tracked_and_sorted(self):
        moves = [
            _make_move(move_number=1, player="B", gtp="D4", points_lost=2.0),
            _make_move(move_number=2, player="W", gtp="Q16", points_lost=5.0),
            _make_move(move_number=3, player="B", gtp="D16", points_lost=3.0),
            _make_move(move_number=4, player="W", gtp="Q4", points_lost=0.5),  # Below threshold
        ]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert len(result["worst_moves"]) == 3  # Only >=2.0
        # Sorted by loss descending
        assert result["worst_moves"][0][3] == 5.0
        assert result["worst_moves"][1][3] == 3.0

    def test_worst_moves_limited_to_10(self):
        moves = [
            _make_move(move_number=i, player="B" if i % 2 else "W", gtp=f"D{i}", points_lost=2.0 + i * 0.1)
            for i in range(1, 16)
        ]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert len(result["worst_moves"]) == 10

    def test_per_player_mistake_stats(self):
        moves = [
            _make_move(move_number=1, player="B", points_lost=3.0, mistake_category=MistakeCategory.MISTAKE),
            _make_move(move_number=2, player="W", points_lost=5.0, mistake_category=MistakeCategory.BLUNDER),
        ]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert result["mistake_counts_by_player"]["B"][MistakeCategory.MISTAKE] == 1
        assert result["mistake_counts_by_player"]["W"][MistakeCategory.BLUNDER] == 1


class TestExtractGameStatsReliability:
    """Test reliability tracking."""

    def test_reliable_move(self):
        moves = [_make_move(move_number=1, player="B", root_visits=300)]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        rel = result["reliability_by_player"]["B"]
        assert rel["total"] == 1
        assert rel["reliable"] == 1
        assert rel["low_confidence"] == 0
        assert rel["max_visits"] == 300

    def test_low_confidence_move(self):
        moves = [_make_move(move_number=1, player="B", root_visits=50)]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        rel = result["reliability_by_player"]["B"]
        assert rel["low_confidence"] == 1
        assert rel["reliable"] == 0

    def test_zero_visits_move(self):
        moves = [_make_move(move_number=1, player="B", root_visits=0)]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        rel = result["reliability_by_player"]["B"]
        assert rel["low_confidence"] == 1
        assert rel["total_visits"] == 0


class TestExtractGameStatsPhaseClassification:
    """Test phase (opening/middle/yose) tracking."""

    def test_phase_moves_tracked(self):
        moves = [_make_move(move_number=i, player="B" if i % 2 else "W") for i in range(1, 6)]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        total_phase = sum(result["phase_moves"].values())
        assert total_phase == 5

    def test_per_player_phase_moves(self):
        moves = [
            _make_move(move_number=1, player="B"),
            _make_move(move_number=2, player="W"),
            _make_move(move_number=3, player="B"),
        ]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        b_total = sum(result["phase_moves_by_player"]["B"].values())
        w_total = sum(result["phase_moves_by_player"]["W"].values())
        assert b_total == 2
        assert w_total == 1


class TestExtractGameStatsPatternData:
    """Test pattern data extraction for MISTAKE/BLUNDER moves."""

    def test_pattern_data_only_mistakes_and_blunders(self):
        moves = [
            _make_move(move_number=1, player="B", points_lost=1.0, mistake_category=MistakeCategory.INACCURACY),
            _make_move(move_number=2, player="W", points_lost=3.0, mistake_category=MistakeCategory.MISTAKE),
            _make_move(move_number=3, player="B", points_lost=6.0, mistake_category=MistakeCategory.BLUNDER),
        ]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert len(result["pattern_data"]) == 2  # MISTAKE + BLUNDER only
        assert result["pattern_data"][0]["mistake_category"] == "MISTAKE"
        assert result["pattern_data"][1]["mistake_category"] == "BLUNDER"

    def test_pattern_data_excludes_no_loss(self):
        moves = [
            _make_move(move_number=1, player="B", mistake_category=MistakeCategory.MISTAKE, points_lost=None, score_loss=None),
        ]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert len(result["pattern_data"]) == 0


class TestExtractGameStatsSummaryData:
    """Test GameSummaryData creation."""

    def test_summary_data_created(self):
        moves = [_make_move(move_number=1, player="B")]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf")
        assert "summary_data" in result
        assert result["summary_data"] is not None
        assert result["summary_data"].game_name == "game.sgf"


class TestExtractGameStatsSourceIndex:
    """Test source_index parameter."""

    def test_source_index_stored(self):
        moves = [_make_move()]
        snapshot = _make_mock_snapshot(moves)
        game = _make_mock_game(snapshot=snapshot)
        result = extract_game_stats(game, "game.sgf", source_index=42)
        assert result["source_index"] == 42


# ---------------------------------------------------------------------------
# extract_players_from_stats
# ---------------------------------------------------------------------------


class TestExtractPlayersFromStats:
    """Test player grouping from stats list."""

    def test_basic_grouping(self):
        stats_list = [
            {"player_black": "Alice", "player_white": "Bob"},
            {"player_black": "Alice", "player_white": "Charlie"},
            {"player_black": "Alice", "player_white": "Bob"},
        ]
        result = extract_players_from_stats(stats_list, min_games=1)
        assert "Alice" in result
        assert len(result["Alice"]) == 3
        # Bob has 2 games
        assert "Bob" in result
        assert len(result["Bob"]) == 2

    def test_min_games_filter(self):
        stats_list = [
            {"player_black": "Alice", "player_white": "Bob"},
            {"player_black": "Alice", "player_white": "Charlie"},
            {"player_black": "Alice", "player_white": "Bob"},
        ]
        result = extract_players_from_stats(stats_list, min_games=3)
        assert "Alice" in result
        assert "Bob" not in result  # Only 2 games

    def test_skip_names(self):
        stats_list = [
            {"player_black": "Black", "player_white": "Bob"},  # "Black" is generic
            {"player_black": "Black", "player_white": "Bob"},
            {"player_black": "Black", "player_white": "Bob"},
        ]
        result = extract_players_from_stats(stats_list, min_games=1)
        assert "Bob" in result
        assert "Black" not in result  # Should be in default skip names

    def test_role_tracking(self):
        stats_list = [
            {"player_black": "Alice", "player_white": "Bob"},
            {"player_black": "Bob", "player_white": "Alice"},
        ]
        result = extract_players_from_stats(stats_list, min_games=1)
        alice_games = result.get("Alice", [])
        roles = [role for _, role in alice_games]
        assert "B" in roles
        assert "W" in roles

    def test_empty_list(self):
        result = extract_players_from_stats([], min_games=1)
        assert result == {}

    def test_empty_player_names_skipped(self):
        stats_list = [
            {"player_black": "", "player_white": ""},
        ]
        result = extract_players_from_stats(stats_list, min_games=1)
        assert result == {}

    def test_custom_skip_names(self):
        stats_list = [
            {"player_black": "SkipMe", "player_white": "Bob"},
            {"player_black": "SkipMe", "player_white": "Bob"},
        ]
        result = extract_players_from_stats(stats_list, min_games=1, skip_names=frozenset({"SkipMe"}))
        assert "SkipMe" not in result
        assert "Bob" in result
