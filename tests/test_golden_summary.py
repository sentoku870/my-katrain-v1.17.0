"""
Golden tests for Multi-Game Summary output.

These tests verify the complete structure and content of Summary reports
using snapshot testing. They use synthetic stats_list data to avoid
dependency on actual SGF files and KataGo analysis.

Key principles:
1. Use synthetic stats_list directly (no SGF dependency)
2. Normalize timestamps, paths, and float precision
3. Use --update-goldens flag to update expected output
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from katrain.core import eval_metrics

from tests.conftest import normalize_output, load_golden, save_golden, GOLDEN_DIR


# ---------------------------------------------------------------------------
# Helper to create synthetic stats for testing
# ---------------------------------------------------------------------------

def create_single_game_stats(
    game_name: str = "test_game.sgf",
    player_black: str = "PlayerB",
    player_white: str = "PlayerW",
    handicap: int = 0,
    total_moves: int = 50,
    total_points_lost: float = 15.0,
    date: str = "2025-01-05",
) -> dict:
    """
    Create a synthetic game stats dictionary.

    This mirrors the structure returned by extract_sgf_statistics().
    """
    # Distribute moves and loss across phases
    opening_moves = total_moves // 3
    middle_moves = total_moves // 3
    yose_moves = total_moves - opening_moves - middle_moves

    opening_loss = total_points_lost * 0.2
    middle_loss = total_points_lost * 0.5
    yose_loss = total_points_lost * 0.3

    # Create mistake counts distribution
    mistake_counts = {
        eval_metrics.MistakeCategory.GOOD: int(total_moves * 0.6),
        eval_metrics.MistakeCategory.INACCURACY: int(total_moves * 0.2),
        eval_metrics.MistakeCategory.MISTAKE: int(total_moves * 0.15),
        eval_metrics.MistakeCategory.BLUNDER: int(total_moves * 0.05),
    }

    mistake_total_loss = {
        eval_metrics.MistakeCategory.GOOD: 0.0,
        eval_metrics.MistakeCategory.INACCURACY: total_points_lost * 0.15,
        eval_metrics.MistakeCategory.MISTAKE: total_points_lost * 0.35,
        eval_metrics.MistakeCategory.BLUNDER: total_points_lost * 0.50,
    }

    # Freedom counts (all UNKNOWN for simplicity)
    freedom_counts = {diff: 0 for diff in eval_metrics.PositionDifficulty}
    freedom_counts[eval_metrics.PositionDifficulty.UNKNOWN] = total_moves

    # Phase moves and loss
    phase_moves = {
        "opening": opening_moves,
        "middle": middle_moves,
        "yose": yose_moves,
        "unknown": 0,
    }
    phase_loss = {
        "opening": opening_loss,
        "middle": middle_loss,
        "yose": yose_loss,
        "unknown": 0.0,
    }

    # Phase × Mistake cross-tabulation
    phase_mistake_counts = {}
    phase_mistake_loss = {}
    for phase in ["opening", "middle", "yose"]:
        for cat in eval_metrics.MistakeCategory:
            key = (phase, cat)
            if cat == eval_metrics.MistakeCategory.GOOD:
                phase_mistake_counts[key] = phase_moves[phase] // 2
                phase_mistake_loss[key] = 0.0
            elif cat == eval_metrics.MistakeCategory.BLUNDER:
                phase_mistake_counts[key] = 1 if phase == "middle" else 0
                phase_mistake_loss[key] = 5.0 if phase == "middle" else 0.0
            else:
                phase_mistake_counts[key] = phase_moves[phase] // 6
                phase_mistake_loss[key] = phase_loss[phase] / 3

    # Worst moves
    worst_moves = [
        (15, "B", "D4", 5.0, 6.0, eval_metrics.MistakeCategory.BLUNDER),
        (28, "W", "Q10", 3.5, 4.0, eval_metrics.MistakeCategory.MISTAKE),
        (42, "B", "R5", 2.5, 3.0, eval_metrics.MistakeCategory.MISTAKE),
    ]

    # Player-specific stats
    moves_by_player = {"B": total_moves // 2, "W": total_moves // 2}
    loss_by_player = {"B": total_points_lost * 0.55, "W": total_points_lost * 0.45}

    return {
        "game_name": game_name,
        "player_black": player_black,
        "player_white": player_white,
        "rank_black": "5d",
        "rank_white": "4d",
        "handicap": handicap,
        "date": date,
        "board_size": (19, 19),
        "total_moves": total_moves,
        "total_points_lost": total_points_lost,
        "moves_by_player": moves_by_player,
        "loss_by_player": loss_by_player,
        "mistake_counts": mistake_counts,
        "mistake_total_loss": mistake_total_loss,
        "freedom_counts": freedom_counts,
        "phase_moves": phase_moves,
        "phase_loss": phase_loss,
        "phase_mistake_counts": phase_mistake_counts,
        "phase_mistake_loss": phase_mistake_loss,
        "worst_moves": worst_moves,
        "reason_tags_counts": {
            "reading_error": 3,
            "direction_error": 2,
            "timing_error": 1,
        },
    }


def create_multi_game_stats_list(num_games: int = 3) -> list:
    """Create a list of synthetic game stats for testing."""
    stats_list = []
    for i in range(num_games):
        stats = create_single_game_stats(
            game_name=f"game_{i + 1}.sgf",
            player_black="TestPlayer" if i % 2 == 0 else "Opponent",
            player_white="Opponent" if i % 2 == 0 else "TestPlayer",
            total_moves=40 + i * 10,
            total_points_lost=10.0 + i * 5.0,
            date=f"2025-01-0{i + 1}",
        )
        stats_list.append(stats)
    return stats_list


# ---------------------------------------------------------------------------
# Mock KaTrainGui for testing _build_summary_from_stats
# ---------------------------------------------------------------------------

def create_mock_katrain_gui():
    """Create a mock KaTrainGui instance for testing."""
    mock_gui = MagicMock()

    # Mock config method
    def mock_config(setting, default=None):
        config_values = {
            "general/skill_preset": "standard",
            "mykatrain_settings": {
                "opponent_info_mode": "auto",
            },
        }
        if "/" in setting:
            parts = setting.split("/")
            if len(parts) == 2:
                section, key = parts
                if section in config_values and isinstance(config_values[section], dict):
                    return config_values[section].get(key, default)
            return config_values.get(setting, default)
        return config_values.get(setting, default)

    mock_gui.config = mock_config

    # Import the actual method for testing
    from katrain.__main__ import KaTrainGui

    # Bind the actual method to the mock
    mock_gui._build_summary_from_stats = lambda stats_list, focus_player=None: \
        KaTrainGui._build_summary_from_stats(mock_gui, stats_list, focus_player)
    mock_gui._collect_rank_info = lambda stats_list, focus_player: \
        KaTrainGui._collect_rank_info(mock_gui, stats_list, focus_player)

    return mock_gui


# ---------------------------------------------------------------------------
# Golden Tests for Summary Output
# ---------------------------------------------------------------------------

class TestSummaryGolden:
    """Golden tests for summary output."""

    GOLDEN_FILE = "summary_output.txt"

    def test_summary_output_matches_golden(self, request):
        """Summary Markdown output should match golden file."""
        # 1. Create synthetic stats_list
        stats_list = create_multi_game_stats_list(num_games=3)

        # 2. Create mock GUI and call _build_summary_from_stats
        mock_gui = create_mock_katrain_gui()
        output = mock_gui._build_summary_from_stats(stats_list, focus_player="TestPlayer")

        # 3. Normalize output
        normalized = normalize_output(output)

        # 4. Update golden if requested
        if request.config.getoption("--update-goldens", default=False):
            save_golden(self.GOLDEN_FILE, normalized)
            pytest.skip("Golden file updated")

        # 5. Compare with golden file
        try:
            expected = load_golden(self.GOLDEN_FILE)
        except FileNotFoundError:
            # First run: save the golden file
            save_golden(self.GOLDEN_FILE, normalized)
            pytest.skip(f"Golden file created: {self.GOLDEN_FILE}")

        assert normalized == expected, (
            f"Summary output differs from golden file.\n"
            f"Run with --update-goldens to update.\n\n"
            f"=== ACTUAL ===\n{normalized}\n\n"
            f"=== EXPECTED ===\n{expected}"
        )

    def test_summary_without_focus_player(self, request):
        """Summary without focus_player should still work."""
        stats_list = create_multi_game_stats_list(num_games=2)
        mock_gui = create_mock_katrain_gui()

        # Call without focus_player
        output = mock_gui._build_summary_from_stats(stats_list, focus_player=None)

        # Should contain basic sections
        assert "# Multi-Game Summary" in output
        assert "## Meta" in output
        assert "## Overall Statistics" in output
        assert "## Mistake Distribution" in output

    def test_summary_empty_stats_list(self):
        """Empty stats_list should return minimal output."""
        mock_gui = create_mock_katrain_gui()

        output = mock_gui._build_summary_from_stats([], focus_player=None)

        assert "# Multi-Game Summary" in output
        assert "No games provided" in output

    def test_summary_single_game(self, request):
        """Single game summary should work correctly."""
        stats_list = [create_single_game_stats()]
        mock_gui = create_mock_katrain_gui()

        output = mock_gui._build_summary_from_stats(stats_list, focus_player="PlayerB")

        # Should contain all main sections
        assert "# Multi-Game Summary" in output
        assert "## Meta" in output
        assert "Games analyzed: 1" in output
        assert "Focus player: PlayerB" in output


# ---------------------------------------------------------------------------
# Tests for Summary Structure
# ---------------------------------------------------------------------------

class TestSummaryStructure:
    """Tests verifying summary report structure."""

    def test_meta_section_content(self):
        """Meta section should contain key information."""
        stats_list = create_multi_game_stats_list(num_games=3)
        mock_gui = create_mock_katrain_gui()

        output = mock_gui._build_summary_from_stats(stats_list, focus_player="TestPlayer")

        assert "## Meta" in output
        assert "Games analyzed: 3" in output
        assert "Focus player: TestPlayer" in output
        assert "Rank:" in output  # Should show rank

    def test_overall_statistics_section(self):
        """Overall Statistics section should have key metrics."""
        stats_list = create_multi_game_stats_list(num_games=2)
        mock_gui = create_mock_katrain_gui()

        output = mock_gui._build_summary_from_stats(stats_list, focus_player="TestPlayer")

        assert "## Overall Statistics" in output
        assert "Total games:" in output
        assert "Total moves analyzed:" in output
        assert "Total points lost:" in output
        assert "Average points lost per move:" in output

    def test_mistake_distribution_table(self):
        """Mistake Distribution should be a proper table."""
        stats_list = create_multi_game_stats_list(num_games=2)
        mock_gui = create_mock_katrain_gui()

        output = mock_gui._build_summary_from_stats(stats_list, focus_player="TestPlayer")

        assert "## Mistake Distribution" in output
        assert "| Category | Count | Percentage | Avg Loss |" in output
        assert "Good" in output
        assert "Inaccuracy" in output
        assert "Mistake" in output
        assert "Blunder" in output

    def test_phase_mistake_breakdown_table(self):
        """Phase × Mistake Breakdown should be present."""
        stats_list = create_multi_game_stats_list(num_games=2)
        mock_gui = create_mock_katrain_gui()

        output = mock_gui._build_summary_from_stats(stats_list, focus_player="TestPlayer")

        assert "## Phase × Mistake Breakdown" in output
        assert "Opening" in output
        assert "Middle game" in output
        assert "Endgame" in output

    def test_worst_moves_section(self):
        """Top Worst Moves section should be present."""
        stats_list = create_multi_game_stats_list(num_games=2)
        mock_gui = create_mock_katrain_gui()

        output = mock_gui._build_summary_from_stats(stats_list, focus_player="TestPlayer")

        assert "## Top Worst Moves" in output

    def test_weakness_hypothesis_section(self):
        """Weakness Hypothesis section should be present."""
        stats_list = create_multi_game_stats_list(num_games=2)
        mock_gui = create_mock_katrain_gui()

        output = mock_gui._build_summary_from_stats(stats_list, focus_player="TestPlayer")

        assert "## Weakness Hypothesis" in output

    def test_practice_priorities_section(self):
        """Practice Priorities section should be present."""
        stats_list = create_multi_game_stats_list(num_games=2)
        mock_gui = create_mock_katrain_gui()

        output = mock_gui._build_summary_from_stats(stats_list, focus_player="TestPlayer")

        assert "## Practice Priorities" in output


# ---------------------------------------------------------------------------
# Tests for Reason Tags
# ---------------------------------------------------------------------------

class TestSummaryReasonTags:
    """Tests for reason tags in summary."""

    def test_reason_tags_section_present(self):
        """Reason tags section should appear when tags exist."""
        stats_list = create_multi_game_stats_list(num_games=2)
        mock_gui = create_mock_katrain_gui()

        output = mock_gui._build_summary_from_stats(stats_list, focus_player="TestPlayer")

        # The section title is in Japanese
        assert "ミス理由タグ分布" in output

    def test_no_reason_tags_section_when_empty(self):
        """Reason tags section should not appear when no tags."""
        stats = create_single_game_stats()
        stats["reason_tags_counts"] = {}  # Empty
        stats_list = [stats]

        mock_gui = create_mock_katrain_gui()
        output = mock_gui._build_summary_from_stats(stats_list, focus_player="PlayerB")

        # Section should not appear
        assert "ミス理由タグ分布" not in output
