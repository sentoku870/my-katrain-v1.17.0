"""Tests for katrain.core.engine_query module."""

from unittest.mock import MagicMock

import pytest

from katrain.core.engine_query import _build_avoid_list, build_analysis_query


@pytest.fixture
def mock_game_node():
    """Create a mock GameNode for testing."""
    node = MagicMock()
    node.komi = 6.5
    node.ruleset = "japanese"
    node.initial_player = "B"
    node.next_player = "B"
    node.board_size = (19, 19)
    node.nodes_from_root = [node]
    node.moves = []
    node.placements = []
    node.analysis = {"moves": {}}
    return node


class TestBuildAnalysisQuery:
    """Tests for build_analysis_query function."""

    def test_basic_query_structure(self, mock_game_node):
        """Query should have all required KataGo fields."""
        query = build_analysis_query(
            analysis_node=mock_game_node,
            visits=100,
            ponder=False,
            ownership=True,
            rules="japanese",
            base_priority=0,
            priority=0,
            override_settings={"reportAnalysisWinratesAs": "BLACK"},
            wide_root_noise=0.0,
        )

        assert "rules" in query
        assert "maxVisits" in query
        assert "komi" in query
        assert "boardXSize" in query
        assert "boardYSize" in query
        assert "analyzeTurns" in query
        assert "initialStones" in query
        assert "moves" in query
        assert "overrideSettings" in query

    def test_visits_is_set(self, mock_game_node):
        """visits parameter should set maxVisits."""
        query = build_analysis_query(
            analysis_node=mock_game_node,
            visits=500,
            ponder=False,
            ownership=True,
            rules="japanese",
            base_priority=0,
            priority=0,
            override_settings={},
            wide_root_noise=0.0,
        )

        assert query["maxVisits"] == 500

    def test_ponder_key_is_set(self, mock_game_node):
        """ponder parameter should set the ponder key."""
        query = build_analysis_query(
            analysis_node=mock_game_node,
            visits=100,
            ponder=True,
            ownership=True,
            rules="japanese",
            base_priority=0,
            priority=0,
            override_settings={},
            wide_root_noise=0.0,
            ponder_key="_kt_continuous",
        )

        assert query["_kt_continuous"] is True

    def test_ownership_included(self, mock_game_node):
        """ownership=True should set includeOwnership."""
        query = build_analysis_query(
            analysis_node=mock_game_node,
            visits=100,
            ponder=False,
            ownership=True,
            rules="japanese",
            base_priority=0,
            priority=0,
            override_settings={},
            wide_root_noise=0.0,
        )

        assert query["includeOwnership"] is True
        assert query["includeMovesOwnership"] is True

    def test_ownership_disabled_with_next_move(self, mock_game_node):
        """ownership should be disabled when next_move is provided."""
        next_move = MagicMock()
        next_move.player = "B"
        next_move.gtp = MagicMock(return_value="D4")

        query = build_analysis_query(
            analysis_node=mock_game_node,
            visits=100,
            ponder=False,
            ownership=True,
            rules="japanese",
            base_priority=0,
            priority=0,
            override_settings={},
            wide_root_noise=0.0,
            next_move=next_move,
        )

        assert query["includeOwnership"] is False
        assert query["includeMovesOwnership"] is False

    def test_priority_combined(self, mock_game_node):
        """base_priority and priority should be combined."""
        query = build_analysis_query(
            analysis_node=mock_game_node,
            visits=100,
            ponder=False,
            ownership=True,
            rules="japanese",
            base_priority=10,
            priority=5,
            override_settings={},
            wide_root_noise=0.0,
        )

        assert query["priority"] == 15

    def test_time_limit_applied(self, mock_game_node):
        """time_limit=True should set maxTime in settings."""
        query = build_analysis_query(
            analysis_node=mock_game_node,
            visits=100,
            ponder=False,
            ownership=True,
            rules="japanese",
            base_priority=0,
            priority=0,
            override_settings={},
            wide_root_noise=0.0,
            max_time=5.0,
            time_limit=True,
        )

        assert query["overrideSettings"]["maxTime"] == 5.0

    def test_time_limit_not_applied(self, mock_game_node):
        """time_limit=False should not set maxTime."""
        query = build_analysis_query(
            analysis_node=mock_game_node,
            visits=100,
            ponder=False,
            ownership=True,
            rules="japanese",
            base_priority=0,
            priority=0,
            override_settings={},
            wide_root_noise=0.0,
            max_time=5.0,
            time_limit=False,
        )

        assert "maxTime" not in query["overrideSettings"]

    def test_report_every_sets_field(self, mock_game_node):
        """report_every should set reportDuringSearchEvery."""
        query = build_analysis_query(
            analysis_node=mock_game_node,
            visits=100,
            ponder=False,
            ownership=True,
            rules="japanese",
            base_priority=0,
            priority=0,
            override_settings={},
            wide_root_noise=0.0,
            report_every=0.5,
        )

        assert query["reportDuringSearchEvery"] == 0.5

    def test_extra_settings_merged(self, mock_game_node):
        """extra_settings should be merged into overrideSettings."""
        query = build_analysis_query(
            analysis_node=mock_game_node,
            visits=100,
            ponder=False,
            ownership=True,
            rules="japanese",
            base_priority=0,
            priority=0,
            override_settings={"existing": "value"},
            wide_root_noise=0.0,
            extra_settings={"custom": "setting"},
        )

        assert query["overrideSettings"]["existing"] == "value"
        assert query["overrideSettings"]["custom"] == "setting"

    def test_no_id_field(self, mock_game_node):
        """Query should NOT have id field (engine assigns it)."""
        query = build_analysis_query(
            analysis_node=mock_game_node,
            visits=100,
            ponder=False,
            ownership=True,
            rules="japanese",
            base_priority=0,
            priority=0,
            override_settings={},
            wide_root_noise=0.0,
        )

        assert "id" not in query


class TestBuildAvoidList:
    """Tests for _build_avoid_list helper."""

    def test_empty_when_no_options(self, mock_game_node):
        """Should return empty list when no avoid options."""
        avoid = _build_avoid_list(
            analysis_node=mock_game_node,
            find_alternatives=False,
            region_of_interest=None,
            size_x=19,
            size_y=19,
        )

        assert avoid == []

    def test_find_alternatives(self, mock_game_node):
        """find_alternatives should avoid already analyzed moves."""
        mock_game_node.analysis = {"moves": {"D4": {}, "Q16": {}}}

        avoid = _build_avoid_list(
            analysis_node=mock_game_node,
            find_alternatives=True,
            region_of_interest=None,
            size_x=19,
            size_y=19,
        )

        assert len(avoid) == 1
        assert set(avoid[0]["moves"]) == {"D4", "Q16"}
        assert avoid[0]["untilDepth"] == 1

    def test_region_of_interest(self, mock_game_node):
        """region_of_interest should avoid moves outside region."""
        avoid = _build_avoid_list(
            analysis_node=mock_game_node,
            find_alternatives=False,
            region_of_interest=[2, 5, 2, 5],  # 4x4 region
            size_x=9,
            size_y=9,
        )

        assert len(avoid) == 2  # One for each player
        # Should have moves outside the region
        assert len(avoid[0]["moves"]) > 0
