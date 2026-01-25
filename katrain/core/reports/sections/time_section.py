# -*- coding: utf-8 -*-
"""Time Management section formatting for reports.

Phase 60: Pacing/Tilt integration.

This module provides i18n-aware formatting functions for time analysis results.
"""

from dataclasses import dataclass
from typing import List, Optional

from katrain.core.lang import i18n


@dataclass(frozen=True)
class TimeStatsData:
    """Aggregated time statistics for a player."""

    blitz_count: int
    blitz_mistake_count: int
    long_think_count: int
    long_think_mistake_count: int


def format_time_stats(stats: TimeStatsData) -> List[str]:
    """Format time statistics as markdown lines.

    Args:
        stats: Aggregated time statistics

    Returns:
        List of markdown-formatted lines
    """
    lines = []

    # Blitz stats
    lines.append(f"- {i18n._('time:blitz_moves')}: {stats.blitz_count}")
    if stats.blitz_count > 0:
        rate = stats.blitz_mistake_count / stats.blitz_count * 100
        lines.append(
            f"- {i18n._('time:blitz_mistake_rate')}: {rate:.1f}% "
            f"({stats.blitz_mistake_count}/{stats.blitz_count})"
        )
    else:
        lines.append(f"- {i18n._('time:blitz_mistake_rate')}: N/A")

    # Long think stats
    lines.append(f"- {i18n._('time:long_think_moves')}: {stats.long_think_count}")
    if stats.long_think_count > 0:
        rate = stats.long_think_mistake_count / stats.long_think_count * 100
        lines.append(
            f"- {i18n._('time:long_think_mistake_rate')}: {rate:.1f}% "
            f"({stats.long_think_mistake_count}/{stats.long_think_count})"
        )
    else:
        lines.append(f"- {i18n._('time:long_think_mistake_rate')}: N/A")

    return lines


def format_tilt_episode(
    game_name: str,
    start_move: int,
    end_move: int,
    severity: str,
    cumulative_loss: float,
) -> str:
    """Format a single tilt episode as a markdown line.

    Args:
        game_name: Name of the game (truncated if needed)
        start_move: Starting move number
        end_move: Ending move number
        severity: Severity level (e.g., "moderate", "severe")
        cumulative_loss: Total loss during the episode

    Returns:
        Markdown-formatted line
    """
    game_short = game_name[:20] if game_name else ""
    return f"- {game_short} #{start_move}-{end_move}: {severity} (loss: {cumulative_loss:.1f})"


def get_section_title() -> str:
    """Get localized section title."""
    return i18n._("time:section_title")


def get_tilt_episodes_label() -> str:
    """Get localized tilt episodes label."""
    return i18n._("time:tilt_episodes")


def get_player_label(player_color: Optional[str], focus_player: Optional[str] = None) -> str:
    """Get localized player label.

    Args:
        player_color: "B" or "W", or None
        focus_player: Player name if focusing on specific player

    Returns:
        Localized label
    """
    if focus_player:
        return focus_player
    if player_color == "B":
        return i18n._("time:all_black_moves")
    elif player_color == "W":
        return i18n._("time:all_white_moves")
    return ""
