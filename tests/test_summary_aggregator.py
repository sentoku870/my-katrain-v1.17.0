"""
Tests for katrain/gui/features/summary_aggregator.py

This module tests:
1. scan_player_names() - Scans SGF files for player names
2. categorize_games_by_stats() - Categorizes games (even/handicap)
3. collect_rank_info() - Collects rank info for focus player

Test philosophy:
- Align with current implementation behavior
- Use mocks for KaTrainSGF.parse_file
- No Kivy imports required
"""

from unittest.mock import MagicMock, patch

import pytest

from katrain.gui.features.summary_aggregator import (
    scan_player_names,
    categorize_games_by_stats,
    collect_rank_info,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def create_game_stats(
    game_name: str = "test.sgf",
    player_black: str = "PlayerB",
    player_white: str = "PlayerW",
    handicap: int = 0,
    rank_black: str | None = None,
    rank_white: str | None = None,
) -> dict:
    """Create a minimal game stats dictionary for testing."""
    return {
        "game_name": game_name,
        "player_black": player_black,
        "player_white": player_white,
        "handicap": handicap,
        "rank_black": rank_black,
        "rank_white": rank_white,
    }


def create_mock_move_tree(
    player_black: str = "",
    player_white: str = "",
) -> MagicMock:
    """Create a mock move tree with get_property method."""
    move_tree = MagicMock()

    def get_property(prop, default=""):
        if prop == "PB":
            return player_black
        elif prop == "PW":
            return player_white
        return default

    move_tree.get_property = get_property
    return move_tree


# ---------------------------------------------------------------------------
# Tests for scan_player_names()
# ---------------------------------------------------------------------------

class TestScanPlayerNames:
    """Tests for scan_player_names() function."""

    @pytest.fixture
    def mock_log_fn(self):
        """Create a mock log function."""
        return MagicMock()

    @patch("katrain.gui.features.summary_aggregator.KaTrainSGF")
    def test_scan_single_file(self, mock_sgf_cls, mock_log_fn):
        """Single SGF file should return both player names."""
        mock_sgf_cls.parse_file.return_value = create_mock_move_tree(
            player_black="Alice",
            player_white="Bob",
        )

        result = scan_player_names(["game1.sgf"], mock_log_fn)

        assert result == {"Alice": 1, "Bob": 1}

    @patch("katrain.gui.features.summary_aggregator.KaTrainSGF")
    def test_scan_multiple_files(self, mock_sgf_cls, mock_log_fn):
        """Multiple SGF files should accumulate counts."""
        mock_sgf_cls.parse_file.side_effect = [
            create_mock_move_tree("Alice", "Bob"),
            create_mock_move_tree("Alice", "Charlie"),
            create_mock_move_tree("Bob", "Charlie"),
        ]

        result = scan_player_names(
            ["game1.sgf", "game2.sgf", "game3.sgf"],
            mock_log_fn,
        )

        assert result == {"Alice": 2, "Bob": 2, "Charlie": 2}

    @patch("katrain.gui.features.summary_aggregator.KaTrainSGF")
    def test_scan_empty_player_names(self, mock_sgf_cls, mock_log_fn):
        """Empty player names should be ignored."""
        mock_sgf_cls.parse_file.return_value = create_mock_move_tree(
            player_black="",
            player_white="Bob",
        )

        result = scan_player_names(["game1.sgf"], mock_log_fn)

        assert result == {"Bob": 1}
        assert "" not in result

    @patch("katrain.gui.features.summary_aggregator.KaTrainSGF")
    def test_scan_whitespace_player_names(self, mock_sgf_cls, mock_log_fn):
        """Whitespace-only player names should be ignored."""
        mock_sgf_cls.parse_file.return_value = create_mock_move_tree(
            player_black="   ",
            player_white="Bob",
        )

        result = scan_player_names(["game1.sgf"], mock_log_fn)

        assert result == {"Bob": 1}

    @patch("katrain.gui.features.summary_aggregator.KaTrainSGF")
    def test_scan_empty_file_list(self, mock_sgf_cls, mock_log_fn):
        """Empty file list should return empty dict."""
        result = scan_player_names([], mock_log_fn)

        assert result == {}
        mock_sgf_cls.parse_file.assert_not_called()

    @patch("katrain.gui.features.summary_aggregator.KaTrainSGF")
    def test_scan_parse_error_logs(self, mock_sgf_cls, mock_log_fn):
        """Parse errors should be logged but not raise."""
        mock_sgf_cls.parse_file.side_effect = Exception("Parse error")

        result = scan_player_names(["bad.sgf"], mock_log_fn)

        assert result == {}
        mock_log_fn.assert_called()

    @patch("katrain.gui.features.summary_aggregator.KaTrainSGF")
    def test_scan_partial_error(self, mock_sgf_cls, mock_log_fn):
        """Partial errors should not affect other files."""
        mock_sgf_cls.parse_file.side_effect = [
            create_mock_move_tree("Alice", "Bob"),
            Exception("Parse error"),
            create_mock_move_tree("Charlie", "Dave"),
        ]

        result = scan_player_names(
            ["good1.sgf", "bad.sgf", "good2.sgf"],
            mock_log_fn,
        )

        assert result == {"Alice": 1, "Bob": 1, "Charlie": 1, "Dave": 1}
        mock_log_fn.assert_called()  # Error was logged


# ---------------------------------------------------------------------------
# Tests for categorize_games_by_stats()
# ---------------------------------------------------------------------------

class TestCategorizeGamesByStats:
    """Tests for categorize_games_by_stats() function."""

    def test_categorize_even_games(self):
        """Even games (handicap=0) should be in 'even' category."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob", handicap=0),
            create_game_stats("game2.sgf", "Alice", "Charlie", handicap=0),
        ]

        result = categorize_games_by_stats(stats_list, focus_player="Alice")

        assert len(result["even"]) == 2
        assert len(result["handi_weak"]) == 0
        assert len(result["handi_strong"]) == 0

    def test_categorize_handicap_games_as_black(self):
        """Handicap games where focus_player is Black go to handi_weak."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob", handicap=4),
        ]

        result = categorize_games_by_stats(stats_list, focus_player="Alice")

        assert len(result["even"]) == 0
        assert len(result["handi_weak"]) == 1
        assert len(result["handi_strong"]) == 0

    def test_categorize_handicap_games_as_white(self):
        """Handicap games where focus_player is White go to handi_strong."""
        stats_list = [
            create_game_stats("game1.sgf", "Bob", "Alice", handicap=4),
        ]

        result = categorize_games_by_stats(stats_list, focus_player="Alice")

        assert len(result["even"]) == 0
        assert len(result["handi_weak"]) == 0
        assert len(result["handi_strong"]) == 1

    def test_categorize_filters_non_focus_player(self):
        """Games without focus_player should be skipped."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob", handicap=0),
            create_game_stats("game2.sgf", "Charlie", "Dave", handicap=0),
        ]

        result = categorize_games_by_stats(stats_list, focus_player="Alice")

        assert len(result["even"]) == 1
        assert result["even"][0]["player_black"] == "Alice"

    def test_categorize_no_focus_player(self):
        """Without focus_player, all games should be categorized."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob", handicap=0),
            create_game_stats("game2.sgf", "Charlie", "Dave", handicap=0),
        ]

        result = categorize_games_by_stats(stats_list, focus_player=None)

        assert len(result["even"]) == 2

    def test_categorize_handicap_no_focus_player(self):
        """Handicap games without focus_player go to handi_weak."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob", handicap=4),
        ]

        result = categorize_games_by_stats(stats_list, focus_player=None)

        assert len(result["handi_weak"]) == 1
        assert len(result["handi_strong"]) == 0

    def test_categorize_empty_list(self):
        """Empty stats list should return empty categories."""
        result = categorize_games_by_stats([], focus_player="Alice")

        assert result == {
            "even": [],
            "handi_weak": [],
            "handi_strong": [],
        }

    def test_categorize_handicap_boundary(self):
        """Handicap=1 is not considered handicap (komi adjustment only)."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob", handicap=1),
        ]

        result = categorize_games_by_stats(stats_list, focus_player="Alice")

        # handicap=1 doesn't match >= 2, so not in handi categories
        # But also doesn't match == 0, so not in even
        assert len(result["even"]) == 0
        assert len(result["handi_weak"]) == 0
        assert len(result["handi_strong"]) == 0

    def test_categorize_mixed_games(self):
        """Mixed game types should be correctly categorized."""
        stats_list = [
            create_game_stats("even1.sgf", "Alice", "Bob", handicap=0),
            create_game_stats("even2.sgf", "Charlie", "Alice", handicap=0),
            create_game_stats("handi1.sgf", "Alice", "Bob", handicap=3),  # Alice is Black (weak)
            create_game_stats("handi2.sgf", "Bob", "Alice", handicap=2),  # Alice is White (strong)
        ]

        result = categorize_games_by_stats(stats_list, focus_player="Alice")

        assert len(result["even"]) == 2
        assert len(result["handi_weak"]) == 1
        assert len(result["handi_strong"]) == 1


# ---------------------------------------------------------------------------
# Tests for collect_rank_info()
# ---------------------------------------------------------------------------

class TestCollectRankInfo:
    """Tests for collect_rank_info() function."""

    def test_collect_rank_from_black(self):
        """Rank should be collected when focus_player is Black."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob", rank_black="5d"),
        ]

        result = collect_rank_info(stats_list, focus_player="Alice")

        assert result == "5d"

    def test_collect_rank_from_white(self):
        """Rank should be collected when focus_player is White."""
        stats_list = [
            create_game_stats("game1.sgf", "Bob", "Alice", rank_white="3k"),
        ]

        result = collect_rank_info(stats_list, focus_player="Alice")

        assert result == "3k"

    def test_collect_most_common_rank(self):
        """Most common rank should be returned."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob", rank_black="5d"),
            create_game_stats("game2.sgf", "Alice", "Charlie", rank_black="4d"),
            create_game_stats("game3.sgf", "Alice", "Dave", rank_black="5d"),
        ]

        result = collect_rank_info(stats_list, focus_player="Alice")

        assert result == "5d"  # Most common

    def test_collect_rank_no_focus_player(self):
        """No focus_player should return None."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob", rank_black="5d"),
        ]

        result = collect_rank_info(stats_list, focus_player=None)

        assert result is None

    def test_collect_rank_not_found(self):
        """Missing rank should return None."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob"),  # No rank_black
        ]

        result = collect_rank_info(stats_list, focus_player="Alice")

        assert result is None

    def test_collect_rank_empty_list(self):
        """Empty stats list should return None."""
        result = collect_rank_info([], focus_player="Alice")

        assert result is None

    def test_collect_rank_player_not_in_games(self):
        """Focus player not in any game should return None."""
        stats_list = [
            create_game_stats("game1.sgf", "Bob", "Charlie", rank_black="5d"),
        ]

        result = collect_rank_info(stats_list, focus_player="Alice")

        assert result is None

    def test_collect_rank_mixed_colors(self):
        """Ranks should be collected from both colors."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob", rank_black="5d"),
            create_game_stats("game2.sgf", "Charlie", "Alice", rank_white="5d"),
            create_game_stats("game3.sgf", "Alice", "Dave", rank_black="4d"),
        ]

        result = collect_rank_info(stats_list, focus_player="Alice")

        assert result == "5d"  # 5d appears twice, 4d once

    def test_collect_rank_japanese_format(self):
        """Japanese rank format should be handled."""
        stats_list = [
            create_game_stats("game1.sgf", "Alice", "Bob", rank_black="五段"),
        ]

        result = collect_rank_info(stats_list, focus_player="Alice")

        assert result == "五段"
