# katrain/core/analysis/user_aggregate.py
"""User radar aggregation for tracking player progress.

PR #Phase55: Report foundation + User aggregation

This module provides:
- GameRadarEntry: Single game radar data with metadata
- UserRadarAggregate: Aggregated radar for a player across recent games
- UserAggregateStore: In-memory store for batch processing
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .skill_radar import (
    AggregatedRadarResult,
    RadarMetrics,
    aggregate_radar,
    radar_from_dict,
)

DEFAULT_HISTORY_SIZE = 10


@dataclass
class GameRadarEntry:
    """Single game radar entry. player_name is used as-is (no normalization)."""

    game_id: str
    player_name: str
    player_color: str
    radar: RadarMetrics
    date: str | None = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "game_id": self.game_id,
            "player_name": self.player_name,
            "player_color": self.player_color,
            "radar": self.radar.to_dict(),
            "date": self.date,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GameRadarEntry | None:
        """Deserialize from dictionary.

        Returns:
            GameRadarEntry if valid, None if radar data is invalid
        """
        radar = radar_from_dict(d.get("radar"))
        if radar is None:
            return None
        return cls(
            game_id=d["game_id"],
            player_name=d["player_name"],
            player_color=d["player_color"],
            radar=radar,
            date=d.get("date"),
            timestamp=d.get("timestamp", 0.0),
        )


@dataclass
class UserRadarAggregate:
    """Aggregate radar for a user. Aggregation key: player_name only."""

    player_name: str
    history_size: int = DEFAULT_HISTORY_SIZE
    entries: list[GameRadarEntry] = field(default_factory=list)

    def add_game(
        self,
        game_id: str,
        player_color: str,
        radar: RadarMetrics,
        date: str | None = None,
    ) -> None:
        """Add a game to the history with FIFO trimming."""
        self.entries.append(
            GameRadarEntry(
                game_id=game_id,
                player_name=self.player_name,
                player_color=player_color,
                radar=radar,
                date=date,
            )
        )
        if len(self.entries) > self.history_size:
            self.entries = self.entries[-self.history_size :]

    def get_aggregate(self) -> AggregatedRadarResult | None:
        """Get aggregated radar from all entries.

        Returns:
            AggregatedRadarResult if entries exist, None otherwise
        """
        if not self.entries:
            return None
        return aggregate_radar([e.radar for e in self.entries])

    @property
    def game_count(self) -> int:
        """Number of games in history."""
        return len(self.entries)

    def get_recent_games(self, n: int | None = None) -> list[GameRadarEntry]:
        """Get recent games in reverse chronological order.

        Args:
            n: Number of games to return, None for all

        Returns:
            List of GameRadarEntry, most recent first
        """
        entries = list(reversed(self.entries))
        return entries[:n] if n else entries

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "player_name": self.player_name,
            "history_size": self.history_size,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UserRadarAggregate:
        """Deserialize from dictionary."""
        entries = [e for ed in d.get("entries", []) if (e := GameRadarEntry.from_dict(ed))]
        return cls(
            player_name=d["player_name"],
            history_size=d.get("history_size", DEFAULT_HISTORY_SIZE),
            entries=entries,
        )


class UserAggregateStore:
    """In-memory store for batch processing."""

    def __init__(self, history_size: int = DEFAULT_HISTORY_SIZE) -> None:
        """Initialize store with default history size."""
        self._history_size = history_size
        self._aggregates: dict[str, UserRadarAggregate] = {}

    def get_or_create(self, player_name: str) -> UserRadarAggregate:
        """Get or create aggregate for player."""
        if player_name not in self._aggregates:
            self._aggregates[player_name] = UserRadarAggregate(player_name=player_name, history_size=self._history_size)
        return self._aggregates[player_name]

    def get(self, player_name: str) -> UserRadarAggregate | None:
        """Get aggregate for player if exists."""
        return self._aggregates.get(player_name)

    def all_players(self) -> list[str]:
        """Get list of all player names in store."""
        return list(self._aggregates.keys())

    def clear(self) -> None:
        """Clear all aggregates."""
        self._aggregates.clear()
