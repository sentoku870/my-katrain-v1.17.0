"""Phase 221: Tests for json_type detection + summary projection."""

from __future__ import annotations

import pytest

from katrain.core.coach.json_type import (
    detect_json_type,
    extract_summary_game_count,
    extract_summary_mistake_buckets,
    extract_summary_total_loss,
    is_karte,
    is_summary,
    normalize_summary_to_karte_shape,
)

# --- Fixtures ---


@pytest.fixture
def sample_karte() -> dict:
    return {
        "schema_version": "3.4",
        "weaknesses": {
            "black": [{"category": "atari_blindness", "total_loss": 5.0}],
            "white": [],
        },
        "important_moves": [
            {"meaning_tag_id": "atari_blindness", "points_lost": 1.5},
        ],
        "mistake_streaks": {"black": [], "white": []},
    }


@pytest.fixture
def sample_summary() -> dict:
    return {
        "schema_version": "3.4",
        "meta": {
            "games_analyzed": 5,
            "date_range": ["2026-07-10", "2026-07-15"],
            "games_by_type": {"even": 3, "handicapped": 2, "unknown": 0},
        },
        "summary": {"total_games": 5, "win_rate": 0.4, "total_moves": 1200},
        "phase_x_mistake": {
            "opening:mistake": 5,
            "middle:blunder": 8,
            "endgame:mistake": 2,
        },
        "weaknesses": {
            "black": [
                {"phase": "middle", "category": "blunder", "count": 5, "total_loss": 30.0},
                {"phase": "opening", "category": "mistake", "count": 4, "total_loss": 12.0},
            ],
            "white": [],
        },
        "mistake_streaks": {
            "black": [{"move_count": 4, "total_loss": 12.0}],
            "white": [],
        },
        "loss_progression": {
            "all": [
                {"mistake_count": 2}, {"mistake_count": 1}, {"mistake_count": 3},
            ],
            "even": [{"mistake_count": 1}, {"mistake_count": 0}],
        },
        "games": [
            {"game_id": "g1", "result": "B+R"},
            {"game_id": "g2", "result": "W+2.5"},
        ],
        "players": {"Player1": {"win_rate": 0.4}, "Player2": {"win_rate": 0.6}},
    }


# --- Detection ---


class TestDetectJsonType:
    def test_karte_detected(self, sample_karte):
        assert detect_json_type(sample_karte) == "karte"
        assert is_karte(sample_karte) is True
        assert is_summary(sample_karte) is False

    def test_summary_detected(self, sample_summary):
        assert detect_json_type(sample_summary) == "summary"
        assert is_karte(sample_summary) is False
        assert is_summary(sample_summary) is True

    def test_empty_dict_unknown(self):
        assert detect_json_type({}) == "unknown"

    def test_non_dict_unknown(self):
        assert detect_json_type([1, 2, 3]) == "unknown"
        assert detect_json_type("string") == "unknown"

    def test_summary_via_phase_x_mistake(self):
        # summary without explicit meta.games_analyzed
        data = {
            "phase_x_mistake": {"middle:blunder": 5},
            "players": {"P1": {}},
        }
        assert detect_json_type(data) == "summary"

    def test_summary_via_players_only(self):
        data = {"players": {"P1": {}}}
        assert detect_json_type(data) == "summary"

    def test_single_game_karte_not_misread_as_summary(self):
        # Phase 226-C (C4): a karte with ``meta.game_count: 1`` and
        # empty weaknesses must NOT be misread as a summary. The
        # pre-Phase-226-C implementation would short-circuit on the
        # presence of game_count even when the rest of the document is
        # karte-shaped.
        data = {
            "schema_version": "3.4",
            "meta": {"game_count": 1, "player_info": {}},
            "weaknesses": {"black": [], "white": []},
            "important_moves": [
                {"meaning_tag_id": "atari_blindness", "points_lost": 1.5},
            ],
        }
        assert detect_json_type(data) == "karte"

    def test_summary_with_game_count_above_one(self):
        data = {
            "schema_version": "3.4",
            "meta": {"game_count": 5},
            "phase_x_mistake": {"middle:blunder": 5},
        }
        assert detect_json_type(data) == "summary"

    def test_karte_with_important_moves_wins_over_players(self):
        # Phase 226-C (C4): karte-shaped (weaknesses + important_moves)
        # is checked BEFORE any summary marker, even when ``players``
        # is present.
        data = {
            "weaknesses": {"black": [], "white": []},
            "important_moves": [{"points_lost": 1.0}],
            "players": {"P1": {}},  # would otherwise trigger summary
        }
        assert detect_json_type(data) == "karte"


# --- Summary extractors ---


class TestSummaryExtractors:
    def test_game_count_from_meta(self, sample_summary):
        assert extract_summary_game_count(sample_summary) == 5

    def test_game_count_fallback_to_games_list(self):
        data = {"games": [{}, {}, {}]}
        assert extract_summary_game_count(data) == 3

    def test_game_count_unknown(self):
        assert extract_summary_game_count({}) is None

    def test_total_loss_summed(self, sample_summary):
        # 30.0 + 12.0 = 42.0
        assert extract_summary_total_loss(sample_summary) == 42.0

    def test_total_loss_empty(self):
        assert extract_summary_total_loss({}) is None

    def test_mistake_buckets(self, sample_summary):
        buckets = extract_summary_mistake_buckets(sample_summary)
        assert buckets == {
            "opening:mistake": 5,
            "middle:blunder": 8,
            "endgame:mistake": 2,
        }

    def test_mistake_buckets_empty(self):
        assert extract_summary_mistake_buckets({}) == {}


# --- Normalization ---


class TestNormalizeSummary:
    def test_passthrough_for_karte(self, sample_karte):
        # Karte JSONs are passed through unchanged
        out = normalize_summary_to_karte_shape(sample_karte)
        assert out is sample_karte

    def test_summary_projected(self, sample_summary):
        out = normalize_summary_to_karte_shape(sample_summary)
        assert out["_is_summary"] is True
        assert out["meta"]["game_count"] == 5
        assert out["important_moves"] == []
        assert isinstance(out["weaknesses"], dict)
        assert isinstance(out["loss_progression"], list)
        # Per-game fields preserved under _
        assert "_phase_x_mistake" in out
        assert "_games" in out
        assert "_players" in out

    def test_summary_loss_progression_unwraps_all(self, sample_summary):
        out = normalize_summary_to_karte_shape(sample_summary)
        # loss_progression should be the 'all' bucket only
        assert isinstance(out["loss_progression"], list)
        assert len(out["loss_progression"]) == 3

    def test_summary_empty_loss_progression(self):
        data = {
            "meta": {"games_analyzed": 1},
            "players": {},
        }
        out = normalize_summary_to_karte_shape(data)
        assert out["loss_progression"] == []


# --- Public API ---


class TestExports:
    def test_json_type_exports(self):
        import katrain.core.coach as pkg
        for name in [
            "JsonType",
            "detect_json_type",
            "is_karte",
            "is_summary",
            "normalize_summary_to_karte_shape",
            "extract_summary_game_count",
            "extract_summary_total_loss",
            "extract_summary_mistake_buckets",
        ]:
            assert hasattr(pkg, name), f"__init__ missing {name}"
