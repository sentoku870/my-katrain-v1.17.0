"""Tests for build_karte_json function (Phase 23 PR #2).

Tests the JSON output functionality for LLM consumption.
Uses mock game objects following the pattern established in test_golden_karte.py.
"""

from unittest.mock import Mock

from katrain.core.eval_metrics import (
    EvalSnapshot,
    MoveEval,
    PositionDifficulty,
    classify_mistake,
)
from katrain.core.reports.karte_report import build_karte_json


def create_mock_game_with_analysis():
    """Create a mock game object with analysis data.

    This fixture contains:
    - 10 moves total
    - At least 1 move with points_lost >= 1.0 (for important_moves)
    - Mix of good moves and mistakes
    """
    # Create moves with various loss values
    moves = []

    # Opening moves (1-5) - mostly good
    for i in range(1, 6):
        loss = 0.3 if i != 3 else 2.5  # Move 3 is a mistake (2.5 points)
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
        move.reason_tags = ["test_tag"] if loss >= 2.0 else []
        move.importance_score = loss * 1.5  # Simple importance calculation
        moves.append(move)

    # Later moves (6-10) - one blunder
    for i in range(6, 11):
        loss = 0.4 if i != 8 else 6.0  # Move 8 is a blunder (6.0 points)
        move = MoveEval(
            move_number=i,
            player="B" if i % 2 == 1 else "W",
            gtp=f"Q{i - 5}",
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
        move.reason_tags = ["blunder_tag"] if loss >= 5.0 else []
        move.importance_score = loss * 1.5
        moves.append(move)

    # Create snapshot
    snapshot = EvalSnapshot(moves=moves)

    # Create mock game
    mock_game = Mock()
    mock_game.build_eval_snapshot.return_value = snapshot
    mock_game.board_size = (19, 19)
    mock_game.sgf_filename = "test_game.sgf"
    mock_game.game_id = "test_game_001"
    mock_game.komi = 6.5
    mock_game.rules = "Japanese"
    mock_game.katrain = None  # No katrain context needed

    # Mock root node properties
    mock_root = Mock()
    mock_root.get_property = Mock(
        side_effect=lambda prop, default=None: {
            "PB": "TestBlack",
            "PW": "TestWhite",
            "DT": "2024-01-15",
            "RE": "B+5.5",
            "GN": "Test Game",
        }.get(prop, default)
    )
    mock_root.handicap = None
    mock_game.root = mock_root

    # Mock get_important_move_evals - return moves with high loss
    important_moves = [m for m in moves if m.points_lost >= 1.0]
    mock_game.get_important_move_evals.return_value = important_moves

    return mock_game


class TestBuildKarteJson:
    """Tests for build_karte_json function."""

    def test_json_schema_version(self):
        """Schema version should be 1.0."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)
        assert result["schema_version"] == "1.0"

    def test_meta_section_present(self):
        """Meta section should contain required fields."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        assert "meta" in result
        meta = result["meta"]
        assert "game_name" in meta
        assert "date" in meta
        assert "players" in meta
        assert "black" in meta["players"]
        assert "white" in meta["players"]
        assert "result" in meta
        assert "skill_preset" in meta
        assert "units" in meta
        assert "points_lost" in meta["units"]

    def test_meta_values(self):
        """Meta section should contain correct values."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        meta = result["meta"]
        assert meta["game_name"] == "test_game"
        assert meta["date"] == "2024-01-15"
        assert meta["players"]["black"] == "TestBlack"
        assert meta["players"]["white"] == "TestWhite"
        assert meta["result"] == "B+5.5"

    def test_summary_section_present(self):
        """Summary section should contain required fields."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        assert "summary" in result
        summary = result["summary"]
        assert "total_moves" in summary
        assert "total_points_lost" in summary
        assert "black" in summary["total_points_lost"]
        assert "white" in summary["total_points_lost"]
        assert "mistake_distribution" in summary

    def test_summary_total_moves(self):
        """Summary should have correct total moves count."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        assert result["summary"]["total_moves"] == 10

    def test_summary_mistake_distribution(self):
        """Mistake distribution should have all categories."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        dist = result["summary"]["mistake_distribution"]
        for player in ["black", "white"]:
            assert player in dist
            assert "good" in dist[player]
            assert "inaccuracy" in dist[player]
            assert "mistake" in dist[player]
            assert "blunder" in dist[player]

    def test_at_least_one_important_move(self):
        """Fixture must contain at least 1 important move."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        assert len(result["important_moves"]) >= 1, "Fixture must contain at least 1 important move"

    def test_important_moves_structure(self):
        """Each important move should have required fields."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        assert len(result["important_moves"]) >= 1
        for move in result["important_moves"]:
            assert "move_number" in move
            assert isinstance(move["move_number"], int)
            assert move["move_number"] >= 1
            assert "coords" in move
            assert "points_lost" in move
            assert "importance" in move
            assert "reason_tags" in move
            assert "phase" in move
            assert "player" in move

    def test_points_lost_nonnegative(self):
        """points_lost should always be >= 0.0."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        for move in result["important_moves"]:
            assert move["points_lost"] >= 0.0, f"Move {move['move_number']} has negative points_lost"

    def test_phase_values(self):
        """Phase should be one of opening/middle/yose/unknown."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        valid_phases = {"opening", "middle", "yose", "unknown"}
        for move in result["important_moves"]:
            assert move["phase"] in valid_phases, f"Invalid phase: {move['phase']}"

    def test_player_values(self):
        """Player should be black, white, or None."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        valid_players = {"black", "white", None}
        for move in result["important_moves"]:
            assert move["player"] in valid_players, f"Invalid player: {move['player']}"

    def test_reason_tags_is_list(self):
        """reason_tags should always be a list."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        for move in result["important_moves"]:
            assert isinstance(move["reason_tags"], list)

    def test_player_filter_black(self):
        """Player filter should filter to black moves only."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game, player_filter="B")

        for move in result["important_moves"]:
            assert move["player"] == "black", f"Found non-black move: {move['player']}"

    def test_player_filter_white(self):
        """Player filter should filter to white moves only."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game, player_filter="W")

        for move in result["important_moves"]:
            assert move["player"] == "white", f"Found non-white move: {move['player']}"

    def test_units_description(self):
        """Units should contain points_lost description for LLM."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        units = result["meta"]["units"]
        assert "points_lost" in units
        assert len(units["points_lost"]) > 10  # Has meaningful description

    def test_coords_format(self):
        """Coords should be GTP format or pass or null."""
        game = create_mock_game_with_analysis()
        result = build_karte_json(game)

        for move in result["important_moves"]:
            coords = move["coords"]
            if coords is not None:
                # Should be GTP format (letter + number) or "pass"
                assert coords == "pass" or (len(coords) >= 2 and coords[0].isalpha() and coords[1:].isdigit()), (
                    f"Invalid coords format: {coords}"
                )
