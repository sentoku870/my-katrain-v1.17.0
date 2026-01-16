"""Snapshot test for summary_formatter.py (Phase 23 PR #3).

Tests that type hint additions don't change output behavior.
Uses the same test data pattern as test_golden_summary.py.
"""

import os
import re
from pathlib import Path

import pytest

from katrain.core import eval_metrics
from katrain.gui.features.summary_formatter import build_summary_from_stats


# Test fixture path
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def normalize_summary(text: str) -> str:
    """Normalize summary output for comparison.

    Normalization rules (v2.4):
    1. Strip trailing whitespace from lines
    2. Collapse multiple blank lines to single blank line
    3. Preserve section order (no line sorting)
    4. Keep floating point values as-is (meaningful changes should be detected)
    """
    lines = []
    for line in text.strip().split("\n"):
        line = line.rstrip()
        lines.append(line)

    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def create_test_summary_stats() -> list:
    """Create fixed test data for snapshot comparison.

    This data must be stable - any changes here will invalidate the snapshot.
    """
    # Simple stats with deterministic values
    stats = {
        "game_name": "test_snapshot_game.sgf",
        "player_black": "SnapshotBlack",
        "player_white": "SnapshotWhite",
        "handicap": 0,
        "total_moves": 30,
        "total_points_lost": 10.0,
        "date": "2024-01-01",
        "loss_by_player": {"B": 5.0, "W": 5.0},

        # Mistake counts
        "mistake_counts": {
            eval_metrics.MistakeCategory.GOOD: 20,
            eval_metrics.MistakeCategory.INACCURACY: 5,
            eval_metrics.MistakeCategory.MISTAKE: 3,
            eval_metrics.MistakeCategory.BLUNDER: 2,
        },
        "mistake_total_loss": {
            eval_metrics.MistakeCategory.GOOD: 0.0,
            eval_metrics.MistakeCategory.INACCURACY: 2.0,
            eval_metrics.MistakeCategory.MISTAKE: 3.0,
            eval_metrics.MistakeCategory.BLUNDER: 5.0,
        },

        # Freedom counts (all UNKNOWN)
        "freedom_counts": {
            eval_metrics.PositionDifficulty.EASY: 0,
            eval_metrics.PositionDifficulty.NORMAL: 0,
            eval_metrics.PositionDifficulty.HARD: 0,
            eval_metrics.PositionDifficulty.ONLY_MOVE: 0,
            eval_metrics.PositionDifficulty.UNKNOWN: 30,
        },

        # Phase data
        "phase_moves": {"opening": 10, "middle": 15, "yose": 5, "unknown": 0},
        "phase_loss": {"opening": 2.0, "middle": 6.0, "yose": 2.0, "unknown": 0.0},

        # Phase × Mistake cross-tabulation
        "phase_mistake_counts": {
            ("opening", eval_metrics.MistakeCategory.GOOD): 8,
            ("opening", eval_metrics.MistakeCategory.INACCURACY): 1,
            ("opening", eval_metrics.MistakeCategory.MISTAKE): 1,
            ("opening", eval_metrics.MistakeCategory.BLUNDER): 0,
            ("middle", eval_metrics.MistakeCategory.GOOD): 10,
            ("middle", eval_metrics.MistakeCategory.INACCURACY): 3,
            ("middle", eval_metrics.MistakeCategory.MISTAKE): 1,
            ("middle", eval_metrics.MistakeCategory.BLUNDER): 1,
            ("yose", eval_metrics.MistakeCategory.GOOD): 2,
            ("yose", eval_metrics.MistakeCategory.INACCURACY): 1,
            ("yose", eval_metrics.MistakeCategory.MISTAKE): 1,
            ("yose", eval_metrics.MistakeCategory.BLUNDER): 1,
        },
        "phase_mistake_loss": {
            ("opening", eval_metrics.MistakeCategory.GOOD): 0.0,
            ("opening", eval_metrics.MistakeCategory.INACCURACY): 0.5,
            ("opening", eval_metrics.MistakeCategory.MISTAKE): 1.5,
            ("opening", eval_metrics.MistakeCategory.BLUNDER): 0.0,
            ("middle", eval_metrics.MistakeCategory.GOOD): 0.0,
            ("middle", eval_metrics.MistakeCategory.INACCURACY): 1.0,
            ("middle", eval_metrics.MistakeCategory.MISTAKE): 1.0,
            ("middle", eval_metrics.MistakeCategory.BLUNDER): 4.0,
            ("yose", eval_metrics.MistakeCategory.GOOD): 0.0,
            ("yose", eval_metrics.MistakeCategory.INACCURACY): 0.5,
            ("yose", eval_metrics.MistakeCategory.MISTAKE): 0.5,
            ("yose", eval_metrics.MistakeCategory.BLUNDER): 1.0,
        },

        # Reason tags
        "reason_tags_counts": {},

        # Worst moves
        "worst_moves": [
            (10, "B", "Q10", 4.0, 5.0, eval_metrics.MistakeCategory.BLUNDER),
            (25, "W", "D16", 3.0, 3.5, eval_metrics.MistakeCategory.MISTAKE),
        ],
    }
    return [stats]


def mock_config_fn(key: str):
    """Mock config function for testing."""
    return {
        "general/skill_preset": "standard",
        "mykatrain_settings": {"opponent_info_mode": "auto"},
    }.get(key)


class TestSummarySnapshot:
    """Snapshot tests for summary_formatter.py."""

    def test_summary_output_structure(self):
        """Summary output should have expected sections."""
        stats_list = create_test_summary_stats()
        output = build_summary_from_stats(stats_list, None, mock_config_fn)

        # Check for expected sections
        assert "# Multi-Game Summary" in output
        assert "## Meta" in output
        assert "## Overall Statistics" in output
        assert "## Mistake Distribution" in output
        assert "## Phase × Mistake Breakdown" in output
        assert "## Weakness Hypothesis" in output
        assert "## Practice Priorities" in output

    def test_summary_output_unchanged(self):
        """Summary output should match snapshot after type hint changes.

        Uses UPDATE_SNAPSHOT=1 environment variable to update fixture.
        """
        stats_list = create_test_summary_stats()
        output = build_summary_from_stats(stats_list, None, mock_config_fn)
        normalized = normalize_summary(output)

        expected_path = FIXTURES_DIR / "summary_expected.txt"

        # Update mode: save current output as new expected
        if os.environ.get("UPDATE_SNAPSHOT") == "1":
            expected_path.parent.mkdir(parents=True, exist_ok=True)
            expected_path.write_text(normalized, encoding="utf-8")
            pytest.skip("Snapshot updated")

        # Normal mode: compare with expected
        if not expected_path.exists():
            # First run: create the fixture
            expected_path.parent.mkdir(parents=True, exist_ok=True)
            expected_path.write_text(normalized, encoding="utf-8")
            pytest.skip("Snapshot fixture created for first time")

        expected = normalize_summary(expected_path.read_text(encoding="utf-8"))
        assert normalized == expected, "Summary output changed unexpectedly"

    def test_summary_with_focus_player(self):
        """Summary with focus player should include player-specific sections."""
        stats_list = create_test_summary_stats()
        output = build_summary_from_stats(stats_list, "SnapshotBlack", mock_config_fn)

        assert "Focus player: SnapshotBlack" in output
        assert "(SnapshotBlack)" in output

    def test_empty_stats_list(self):
        """Empty stats list should return minimal output."""
        output = build_summary_from_stats([], None, mock_config_fn)

        assert "# Multi-Game Summary" in output
        assert "No games provided" in output
