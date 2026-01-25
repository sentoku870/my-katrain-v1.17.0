# tests/test_user_aggregate.py
"""Tests for user radar aggregation.

PR #Phase55: Report foundation + User aggregation
"""

import json

import pytest
from types import MappingProxyType

from katrain.core.analysis.skill_radar import RadarAxis, RadarMetrics, SkillTier
from katrain.core.analysis.user_aggregate import (
    DEFAULT_HISTORY_SIZE,
    GameRadarEntry,
    UserAggregateStore,
    UserRadarAggregate,
)


def make_radar(opening: float = 3.0) -> RadarMetrics:
    """Create a RadarMetrics with specified opening value."""
    return RadarMetrics(
        opening=opening,
        fighting=3.0,
        endgame=3.0,
        stability=3.0,
        awareness=3.0,
        opening_tier=SkillTier.TIER_3,
        fighting_tier=SkillTier.TIER_3,
        endgame_tier=SkillTier.TIER_3,
        stability_tier=SkillTier.TIER_3,
        awareness_tier=SkillTier.TIER_3,
        overall_tier=SkillTier.TIER_3,
        valid_move_counts=MappingProxyType(
            {
                RadarAxis.OPENING: 50,
                RadarAxis.FIGHTING: 20,
                RadarAxis.ENDGAME: 30,
                RadarAxis.STABILITY: 100,
                RadarAxis.AWARENESS: 100,
            }
        ),
    )


class TestGameRadarEntry:
    """Tests for GameRadarEntry dataclass."""

    def test_to_dict(self):
        """Entry serializes to dict correctly."""
        entry = GameRadarEntry(
            game_id="test.sgf",
            player_name="Alice",
            player_color="B",
            radar=make_radar(4.0),
            date="2025-01-25",
            timestamp=1234567890.0,
        )
        d = entry.to_dict()
        assert d["game_id"] == "test.sgf"
        assert d["player_name"] == "Alice"
        assert d["player_color"] == "B"
        assert d["date"] == "2025-01-25"
        assert d["timestamp"] == 1234567890.0
        assert "radar" in d

    def test_from_dict(self):
        """Entry deserializes from dict correctly."""
        entry = GameRadarEntry(
            game_id="test.sgf",
            player_name="Alice",
            player_color="B",
            radar=make_radar(4.0),
            date="2025-01-25",
        )
        restored = GameRadarEntry.from_dict(entry.to_dict())
        assert restored is not None
        assert restored.game_id == "test.sgf"
        assert restored.player_name == "Alice"
        assert restored.radar.opening == 4.0

    def test_from_dict_invalid_radar(self):
        """Invalid radar data returns None."""
        d = {
            "game_id": "test.sgf",
            "player_name": "Alice",
            "player_color": "B",
            "radar": None,
        }
        assert GameRadarEntry.from_dict(d) is None


class TestUserRadarAggregate:
    """Tests for UserRadarAggregate class."""

    def test_empty_returns_none(self):
        """Empty aggregate returns None for get_aggregate."""
        agg = UserRadarAggregate(player_name="test")
        assert agg.get_aggregate() is None

    def test_add_single_game(self):
        """Single game is stored and aggregated correctly."""
        agg = UserRadarAggregate(player_name="test")
        agg.add_game("game1.sgf", "B", make_radar(4.0))
        result = agg.get_aggregate()
        assert result is not None
        assert result.opening == 4.0

    def test_fifo_trim(self):
        """History is trimmed to history_size with FIFO."""
        agg = UserRadarAggregate(player_name="test", history_size=3)
        for i in range(5):
            agg.add_game(f"game{i}.sgf", "B", make_radar(float(i)))
        assert agg.game_count == 3
        assert agg.get_recent_games()[0].game_id == "game4.sgf"

    def test_average(self):
        """Multiple games are averaged correctly."""
        agg = UserRadarAggregate(player_name="test")
        agg.add_game("g1.sgf", "B", make_radar(2.0))
        agg.add_game("g2.sgf", "W", make_radar(4.0))
        result = agg.get_aggregate()
        assert result is not None
        assert result.opening == 3.0

    def test_roundtrip(self):
        """Aggregate serializes and deserializes correctly."""
        agg = UserRadarAggregate(player_name="test", history_size=5)
        agg.add_game("game.sgf", "B", make_radar(4.0), date="2025-01-25")
        restored = UserRadarAggregate.from_dict(agg.to_dict())
        assert restored.player_name == "test"
        assert restored.history_size == 5
        assert len(restored.entries) == 1
        assert restored.entries[0].date == "2025-01-25"

    def test_json_safe(self):
        """Aggregate can be serialized via JSON."""
        agg = UserRadarAggregate(player_name="test")
        agg.add_game("game.sgf", "B", make_radar())
        json_str = json.dumps(agg.to_dict())
        restored = UserRadarAggregate.from_dict(json.loads(json_str))
        assert restored.game_count == 1

    def test_get_recent_games_limit(self):
        """get_recent_games respects limit parameter."""
        agg = UserRadarAggregate(player_name="test")
        for i in range(5):
            agg.add_game(f"game{i}.sgf", "B", make_radar())
        recent = agg.get_recent_games(2)
        assert len(recent) == 2
        assert recent[0].game_id == "game4.sgf"
        assert recent[1].game_id == "game3.sgf"

    def test_game_count(self):
        """game_count returns correct number."""
        agg = UserRadarAggregate(player_name="test")
        assert agg.game_count == 0
        agg.add_game("g1.sgf", "B", make_radar())
        assert agg.game_count == 1
        agg.add_game("g2.sgf", "W", make_radar())
        assert agg.game_count == 2


class TestUserAggregateStore:
    """Tests for UserAggregateStore class."""

    def test_get_or_create_same_instance(self):
        """get_or_create returns same instance for same player."""
        store = UserAggregateStore()
        assert store.get_or_create("Alice") is store.get_or_create("Alice")

    def test_different_players(self):
        """Different players have different aggregates."""
        store = UserAggregateStore()
        store.get_or_create("Alice")
        store.get_or_create("Bob")
        assert set(store.all_players()) == {"Alice", "Bob"}

    def test_clear(self):
        """clear removes all aggregates."""
        store = UserAggregateStore()
        store.get_or_create("Alice")
        store.clear()
        assert store.get("Alice") is None

    def test_get_nonexistent(self):
        """get returns None for nonexistent player."""
        store = UserAggregateStore()
        assert store.get("Alice") is None

    def test_custom_history_size(self):
        """Store uses custom history_size for new aggregates."""
        store = UserAggregateStore(history_size=5)
        agg = store.get_or_create("Alice")
        assert agg.history_size == 5

    def test_all_players_empty(self):
        """all_players returns empty list for empty store."""
        store = UserAggregateStore()
        assert store.all_players() == []
