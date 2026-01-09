"""
Tests for ownership (territory) overlay support.

M5.2: Territory overlay display
"""

import pytest
from katrain_qt.analysis.katago_engine import parse_ownership, build_query
from katrain_qt.analysis.models import AnalysisResult, PositionSnapshot


class TestParseOwnership:
    """Tests for parse_ownership function."""

    def test_valid_ownership_19x19(self):
        """Test parsing a valid 19x19 ownership array."""
        board_size = 19
        # Create flat array: all zeros except known values
        ownership_flat = [0.0] * (board_size * board_size)
        # Set bottom-left corner (GTP A1) to black territory
        ownership_flat[0] = 0.9  # GTP row 1, col A
        # Set top-right corner (GTP T19) to white territory
        ownership_flat[-1] = -0.8  # GTP row 19, col T

        response = {"ownership": ownership_flat}
        grid = parse_ownership(response, board_size)

        assert grid is not None
        assert len(grid) == 19
        assert len(grid[0]) == 19

        # Qt row 0 = top (GTP row 19)
        # Qt row 18 = bottom (GTP row 1)
        # GTP T19 (top-right) -> Qt (18, 0)
        assert grid[0][18] == pytest.approx(-0.8)
        # GTP A1 (bottom-left) -> Qt (0, 18)
        assert grid[18][0] == pytest.approx(0.9)

    def test_valid_ownership_9x9(self):
        """Test parsing a 9x9 ownership array."""
        board_size = 9
        ownership_flat = [0.5] * (board_size * board_size)

        response = {"ownership": ownership_flat}
        grid = parse_ownership(response, board_size)

        assert grid is not None
        assert len(grid) == 9
        assert len(grid[0]) == 9
        assert all(v == pytest.approx(0.5) for row in grid for v in row)

    def test_no_ownership_in_response(self):
        """Test when ownership is not present in response."""
        response = {"moveInfos": []}
        grid = parse_ownership(response, 19)
        assert grid is None

    def test_wrong_size_ownership(self):
        """Test when ownership array has wrong size."""
        board_size = 19
        # Wrong size array
        ownership_flat = [0.0] * 100  # Not 361

        response = {"ownership": ownership_flat}
        grid = parse_ownership(response, board_size)

        assert grid is None

    def test_ownership_coordinate_conversion(self):
        """Test that ownership coordinates are correctly converted from GTP to Qt."""
        board_size = 19
        ownership_flat = [0.0] * (board_size * board_size)

        # Set specific point: GTP D4 (col=3, row=4 from bottom)
        # GTP row 4 from bottom = index 3 in 0-indexed
        # Flat array index = gtp_row_0idx * size + col = 3 * 19 + 3 = 60
        ownership_flat[60] = 0.75

        response = {"ownership": ownership_flat}
        grid = parse_ownership(response, board_size)

        # D4 in Qt coords: col=3, row=15 (19 - 4 = 15)
        assert grid[15][3] == pytest.approx(0.75)


class TestBuildQueryOwnership:
    """Tests for includeOwnership in query building."""

    def test_default_includes_ownership(self):
        """Test that ownership is included by default."""
        snapshot = PositionSnapshot(
            stones={(3, 15): "B"},
            next_player="W",
            board_size=19,
            komi=6.5,
        )
        query = build_query(snapshot, "test-1")

        assert "includeOwnership" in query
        assert query["includeOwnership"] is True

    def test_can_disable_ownership(self):
        """Test that ownership can be disabled."""
        snapshot = PositionSnapshot(
            stones={(3, 15): "B"},
            next_player="W",
            board_size=19,
            komi=6.5,
        )
        query = build_query(snapshot, "test-1", include_ownership=False)

        assert query["includeOwnership"] is False


class TestAnalysisResultOwnership:
    """Tests for AnalysisResult ownership field."""

    def test_analysis_result_without_ownership(self):
        """Test AnalysisResult without ownership data."""
        result = AnalysisResult(
            query_id="test",
            candidates=[],
            score_lead_black=1.5,
            winrate_black=0.55,
            next_player="B",
            root_visits=100,
        )
        assert result.ownership is None

    def test_analysis_result_with_ownership(self):
        """Test AnalysisResult with ownership data."""
        ownership_grid = [[0.5] * 19 for _ in range(19)]
        result = AnalysisResult(
            query_id="test",
            candidates=[],
            score_lead_black=1.5,
            winrate_black=0.55,
            next_player="B",
            root_visits=100,
            ownership=ownership_grid,
        )
        assert result.ownership is not None
        assert len(result.ownership) == 19
        assert len(result.ownership[0]) == 19


class TestOwnershipEndToEnd:
    """End-to-end tests for ownership parsing from mock KataGo response."""

    def test_parse_full_response_with_ownership(self):
        """Test parsing a complete response with ownership."""
        from katrain_qt.analysis.katago_engine import build_analysis_result

        board_size = 19
        ownership_flat = [0.0] * (board_size * board_size)
        # Set some ownership values
        ownership_flat[0] = 0.9     # Bottom-left black
        ownership_flat[-1] = -0.9   # Top-right white
        ownership_flat[180] = 0.5   # Middle somewhere

        response = {
            "id": "test-query",
            "ownership": ownership_flat,
            "moveInfos": [
                {
                    "move": "D4",
                    "visits": 100,
                    "scoreLead": 1.5,
                    "winrate": 0.55,
                    "pv": ["D4", "Q16", "D16"],
                }
            ],
            "rootInfo": {
                "visits": 1000,
                "scoreLead": 1.2,
                "winrate": 0.54,
            },
        }

        result = build_analysis_result(
            query_id="test-query",
            response=response,
            next_player="B",
            board_size=board_size,
        )

        assert result.ownership is not None
        assert len(result.ownership) == 19

        # Verify specific values converted correctly
        # GTP A1 (bottom-left) -> Qt row 18, col 0
        assert result.ownership[18][0] == pytest.approx(0.9)
        # GTP T19 (top-right) -> Qt row 0, col 18
        assert result.ownership[0][18] == pytest.approx(-0.9)

    def test_parse_response_without_ownership(self):
        """Test parsing a response without ownership."""
        from katrain_qt.analysis.katago_engine import build_analysis_result

        response = {
            "id": "test-query",
            "moveInfos": [
                {
                    "move": "D4",
                    "visits": 100,
                    "scoreLead": 1.5,
                    "winrate": 0.55,
                    "pv": ["D4"],
                }
            ],
            "rootInfo": {
                "visits": 1000,
                "scoreLead": 1.2,
                "winrate": 0.54,
            },
        }

        result = build_analysis_result(
            query_id="test-query",
            response=response,
            next_player="B",
            board_size=19,
        )

        assert result.ownership is None


class TestOwnershipClearedOnNavigation:
    """Test that ownership is cleared when navigating to unanalyzed nodes."""

    def test_ownership_cleared_when_no_cached_analysis(self):
        """Test that stale ownership is cleared when navigating to node without analysis."""
        from katrain_qt.widgets.board_widget import GoBoardWidget

        widget = GoBoardWidget()
        widget._board_size = 19

        # Set some ownership data
        ownership_grid = [[0.5] * 19 for _ in range(19)]
        widget.set_ownership(ownership_grid)
        widget.set_show_ownership(True)

        assert widget._ownership is not None

        # Clear ownership (simulating navigation to unanalyzed node)
        widget.clear_ownership()

        assert widget._ownership is None
