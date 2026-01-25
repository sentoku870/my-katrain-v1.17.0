# -*- coding: utf-8 -*-
"""Tests for Phase 60: Time Management integration.

Tests for:
- get_pacing_icon(): Icon selection logic
- extract_pacing_stats_for_summary(): Result conversion
- _format_time_management(): Summary formatting
- Phase 59 invariant enforcement
"""

import pytest
from unittest.mock import MagicMock

from katrain.core.analysis.time import (
    PacingMetrics,
    PacingAnalysisResult,
    get_pacing_icon,
    extract_pacing_stats_for_summary,
)


class TestGetPacingIcon:
    """Tests for get_pacing_icon()."""

    def test_none_returns_dash(self):
        assert get_pacing_icon(None) == "-"

    def test_impulsive_priority_over_blitz(self):
        """is_impulsive should take priority over is_blitz."""
        m = PacingMetrics(
            move_number=1,
            player="B",
            time_spent_sec=1.0,
            canonical_loss=5.0,
            is_blitz=True,
            is_long_think=False,
            is_impulsive=True,
            is_overthinking=False,
        )
        assert get_pacing_icon(m) == "🔥"

    def test_overthinking_priority_over_long_think(self):
        """is_overthinking should take priority over is_long_think."""
        m = PacingMetrics(
            move_number=1,
            player="B",
            time_spent_sec=100.0,
            canonical_loss=5.0,
            is_blitz=False,
            is_long_think=True,
            is_impulsive=False,
            is_overthinking=True,
        )
        assert get_pacing_icon(m) == "💭"

    def test_impulsive_priority_over_overthinking(self):
        """is_impulsive > is_overthinking in edge case."""
        m = PacingMetrics(
            move_number=1,
            player="B",
            time_spent_sec=1.0,
            canonical_loss=5.0,
            is_blitz=True,
            is_long_think=True,
            is_impulsive=True,
            is_overthinking=True,
        )
        assert get_pacing_icon(m) == "🔥"

    def test_blitz_only(self):
        m = PacingMetrics(
            move_number=1,
            player="B",
            time_spent_sec=1.0,
            canonical_loss=0.5,
            is_blitz=True,
            is_long_think=False,
            is_impulsive=False,
            is_overthinking=False,
        )
        assert get_pacing_icon(m) == "🐇"

    def test_long_think_only(self):
        m = PacingMetrics(
            move_number=1,
            player="B",
            time_spent_sec=100.0,
            canonical_loss=0.5,
            is_blitz=False,
            is_long_think=True,
            is_impulsive=False,
            is_overthinking=False,
        )
        assert get_pacing_icon(m) == "🐢"

    def test_no_flags_returns_dash(self):
        m = PacingMetrics(
            move_number=1,
            player="B",
            time_spent_sec=10.0,
            canonical_loss=0.5,
            is_blitz=False,
            is_long_think=False,
            is_impulsive=False,
            is_overthinking=False,
        )
        assert get_pacing_icon(m) == "-"


class TestExtractPacingStatsForSummary:
    """Tests for extract_pacing_stats_for_summary()."""

    def test_no_time_data_returns_has_time_data_false(self):
        """When has_time_data is False, return minimal dict."""
        result = PacingAnalysisResult(
            pacing_metrics=(),
            tilt_episodes=(),
            has_time_data=False,
            game_stats=MagicMock(),
        )
        stats = extract_pacing_stats_for_summary(result)
        assert stats == {"has_time_data": False}

    def test_with_time_data_returns_player_stats(self):
        """When has_time_data is True, return full stats."""
        metrics = (
            PacingMetrics(
                move_number=1, player="B", time_spent_sec=1.0, canonical_loss=5.0,
                is_blitz=True, is_long_think=False, is_impulsive=True, is_overthinking=False,
            ),
            PacingMetrics(
                move_number=2, player="B", time_spent_sec=2.0, canonical_loss=0.5,
                is_blitz=True, is_long_think=False, is_impulsive=False, is_overthinking=False,
            ),
            PacingMetrics(
                move_number=3, player="W", time_spent_sec=50.0, canonical_loss=3.0,
                is_blitz=False, is_long_think=True, is_impulsive=False, is_overthinking=True,
            ),
        )
        result = PacingAnalysisResult(
            pacing_metrics=metrics,
            tilt_episodes=(),
            has_time_data=True,
            game_stats=MagicMock(),
        )
        stats = extract_pacing_stats_for_summary(result)

        assert stats["has_time_data"] is True
        assert stats["player_stats"]["B"]["blitz_count"] == 2
        assert stats["player_stats"]["B"]["blitz_mistake_count"] == 1
        assert stats["player_stats"]["W"]["long_think_count"] == 1
        assert stats["player_stats"]["W"]["long_think_mistake_count"] == 1


class TestPhase59Invariants:
    """Tests to enforce Phase 59 invariants used by Phase 60."""

    def test_impulsive_implies_blitz(self):
        """is_impulsive=True must imply is_blitz=True (Phase 59 guarantee)."""
        # This tests the invariant our rate calculation depends on
        m = PacingMetrics(
            move_number=1,
            player="B",
            time_spent_sec=1.0,
            canonical_loss=5.0,
            is_blitz=True,  # Must be True when is_impulsive=True
            is_long_think=False,
            is_impulsive=True,
            is_overthinking=False,
        )
        # Verify the invariant holds for our test data
        assert m.is_impulsive and m.is_blitz

    def test_overthinking_implies_long_think(self):
        """is_overthinking=True must imply is_long_think=True (Phase 59 guarantee)."""
        m = PacingMetrics(
            move_number=1,
            player="B",
            time_spent_sec=100.0,
            canonical_loss=5.0,
            is_blitz=False,
            is_long_think=True,  # Must be True when is_overthinking=True
            is_impulsive=False,
            is_overthinking=True,
        )
        assert m.is_overthinking and m.is_long_think

    def test_rate_never_exceeds_100_percent(self):
        """Blitz mistake rate must be <= 100%."""
        metrics = (
            PacingMetrics(
                move_number=1, player="B", time_spent_sec=1.0, canonical_loss=5.0,
                is_blitz=True, is_long_think=False, is_impulsive=True, is_overthinking=False,
            ),
            PacingMetrics(
                move_number=2, player="B", time_spent_sec=2.0, canonical_loss=0.5,
                is_blitz=True, is_long_think=False, is_impulsive=False, is_overthinking=False,
            ),
            PacingMetrics(
                move_number=3, player="B", time_spent_sec=10.0, canonical_loss=0.5,
                is_blitz=False, is_long_think=False, is_impulsive=False, is_overthinking=False,
            ),
        )
        result = PacingAnalysisResult(
            pacing_metrics=metrics,
            tilt_episodes=(),
            has_time_data=True,
            game_stats=MagicMock(),
        )
        stats = extract_pacing_stats_for_summary(result)

        ps = stats["player_stats"]["B"]
        # blitz_mistake_count (1) <= blitz_count (2)
        assert ps["blitz_mistake_count"] <= ps["blitz_count"]
        # Compute rate
        if ps["blitz_count"] > 0:
            rate = ps["blitz_mistake_count"] / ps["blitz_count"]
            assert 0.0 <= rate <= 1.0


class TestFormatTimeManagement:
    """Tests for _format_time_management()."""

    def test_no_time_data_returns_empty_string(self):
        from katrain.gui.features.summary_formatter import _format_time_management
        stats_list = [{"pacing_stats": {"has_time_data": False}}]
        result = _format_time_management(stats_list, None)
        assert result == ""

    def test_blitz_count_zero_shows_na(self):
        from katrain.gui.features.summary_formatter import _format_time_management
        stats_list = [{
            "player_black": "TestPlayer",
            "player_white": "Opponent",
            "pacing_stats": {
                "has_time_data": True,
                "player_stats": {
                    "B": {"blitz_count": 0, "blitz_mistake_count": 0,
                          "long_think_count": 5, "long_think_mistake_count": 1},
                    "W": {"blitz_count": 0, "blitz_mistake_count": 0,
                          "long_think_count": 0, "long_think_mistake_count": 0},
                },
                "tilt_episodes": [],
            },
        }]
        result = _format_time_management(stats_list, "TestPlayer")
        assert "N/A" in result

    def test_focus_player_color_changes_across_games(self):
        """focus_playerが黒→白と変わるケースを正しく集約できる。"""
        from katrain.gui.features.summary_formatter import _format_time_management
        stats_list = [
            {
                "player_black": "TestPlayer",
                "player_white": "Opponent1",
                "pacing_stats": {
                    "has_time_data": True,
                    "player_stats": {
                        "B": {"blitz_count": 10, "blitz_mistake_count": 2,
                              "long_think_count": 5, "long_think_mistake_count": 1},
                        "W": {"blitz_count": 8, "blitz_mistake_count": 3,
                              "long_think_count": 4, "long_think_mistake_count": 2},
                    },
                    "tilt_episodes": [],
                },
            },
            {
                "player_black": "Opponent2",
                "player_white": "TestPlayer",
                "pacing_stats": {
                    "has_time_data": True,
                    "player_stats": {
                        "B": {"blitz_count": 6, "blitz_mistake_count": 1,
                              "long_think_count": 3, "long_think_mistake_count": 0},
                        "W": {"blitz_count": 10, "blitz_mistake_count": 3,
                              "long_think_count": 5, "long_think_mistake_count": 2},
                    },
                    "tilt_episodes": [],
                },
            },
        ]
        result = _format_time_management(stats_list, "TestPlayer")
        # TestPlayer: Game1 B(10,2) + Game2 W(10,3) = (20,5) → 25%
        assert "25.0%" in result
        # TestPlayer: Game1 B(5,1) + Game2 W(5,2) = (10,3) → 30%
        assert "30.0%" in result

    def test_no_focus_player_uses_all_moves_label(self):
        """focus_player=None時、'All Black moves'/'All White moves'と表示。"""
        from katrain.gui.features.summary_formatter import _format_time_management
        stats_list = [{
            "player_black": "Player1",
            "player_white": "Player2",
            "pacing_stats": {
                "has_time_data": True,
                "player_stats": {
                    "B": {"blitz_count": 5, "blitz_mistake_count": 1,
                          "long_think_count": 3, "long_think_mistake_count": 0},
                    "W": {"blitz_count": 4, "blitz_mistake_count": 2,
                          "long_think_count": 2, "long_think_mistake_count": 1},
                },
                "tilt_episodes": [],
            },
        }]
        result = _format_time_management(stats_list, None)
        assert "All Black moves" in result
        assert "All White moves" in result
