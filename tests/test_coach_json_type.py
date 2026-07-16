"""Phase 221: Tests for json_type detection + summary projection.

Phase 227-A: extended with ``extract_summary_weakness_patterns`` tests.
"""

from __future__ import annotations

import pytest

from katrain.core.coach.json_type import (
    detect_json_type,
    extract_summary_game_count,
    extract_summary_mistake_buckets,
    extract_summary_player_mistakes,
    extract_summary_player_phase_losses,
    extract_summary_total_loss,
    extract_summary_weakness_patterns,
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
                {"mistake_count": 2},
                {"mistake_count": 1},
                {"mistake_count": 3},
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
            "extract_summary_weakness_patterns",  # Phase 227-A + 228-A
            "extract_summary_player_mistakes",  # Phase 228-A
            "extract_summary_player_phase_losses",  # Phase 228-A
        ]:
            assert hasattr(pkg, name), f"__init__ missing {name}"


# --- Weakness patterns (Phase 227-A) ---


class TestExtractWeaknessPatterns:
    def test_aggregates_across_colors(self, sample_summary):
        # sample_summary fixture: 2 black entries, 0 white entries
        patterns = extract_summary_weakness_patterns(sample_summary)
        assert len(patterns) == 2

    def test_sorted_by_total_loss_desc(self, sample_summary):
        patterns = extract_summary_weakness_patterns(sample_summary)
        losses = [p["total_loss"] for p in patterns]
        assert losses == sorted(losses, reverse=True)
        # Top entry: black/middle/blunder/30.0
        top = patterns[0]
        assert top["color"] == "black"
        assert top["phase"] == "middle"
        assert top["category"] == "blunder"
        assert top["total_loss"] == 30.0

    def test_frequency_ratio(self, sample_summary):
        # games_analyzed = 5
        # black/blunder: 5/5 = 1.0
        # black/mistake: 4/5 = 0.8
        patterns = extract_summary_weakness_patterns(sample_summary)
        assert patterns[0]["frequency_ratio"] == 1.0
        assert patterns[1]["frequency_ratio"] == 0.8

    def test_top_n_cap(self, sample_summary):
        patterns = extract_summary_weakness_patterns(sample_summary, top_n=1)
        assert len(patterns) == 1
        assert patterns[0]["total_loss"] == 30.0

    def test_empty_weaknesses(self):
        data = {"meta": {"games_analyzed": 5}}
        assert extract_summary_weakness_patterns(data) == []

    def test_no_games_analyzed_degrades_to_zero_freq(self):
        # No games_analyzed / game_count: frequency_ratio = 0.0 but
        # entries are still returned
        data = {
            "weaknesses": {
                "black": [{"phase": "middle", "category": "blunder", "count": 3, "total_loss": 10.0}],
            },
        }
        patterns = extract_summary_weakness_patterns(data)
        assert len(patterns) == 1
        assert patterns[0]["frequency_ratio"] == 0.0

    def test_skips_entries_without_signal(self):
        # Entries with neither count nor total_loss are skipped
        data = {
            "meta": {"games_analyzed": 5},
            "weaknesses": {
                "black": [
                    {"phase": "middle", "category": "blunder"},  # no count/loss
                    {"phase": "opening", "category": "mistake", "count": 2, "total_loss": 5.0},
                ],
            },
        }
        patterns = extract_summary_weakness_patterns(data)
        assert len(patterns) == 1
        assert patterns[0]["category"] == "mistake"

    def test_pattern_dict_keys(self, sample_summary):
        patterns = extract_summary_weakness_patterns(sample_summary)
        for p in patterns:
            assert set(p.keys()) == {
                "color",
                "phase",
                "category",
                "count",
                "total_loss",
                "frequency_ratio",
            }

    def test_non_dict_weaknesses_returns_empty(self):
        data = {"weaknesses": "not a dict", "meta": {"games_analyzed": 5}}
        assert extract_summary_weakness_patterns(data) == []

    def test_non_list_items_skipped(self):
        data = {
            "weaknesses": {"black": "not a list"},
            "meta": {"games_analyzed": 5},
        }
        assert extract_summary_weakness_patterns(data) == []

    def test_missing_phase_defaults_to_unknown(self):
        data = {
            "meta": {"games_analyzed": 5},
            "weaknesses": {
                "black": [{"category": "blunder", "count": 2, "total_loss": 5.0}],
            },
        }
        patterns = extract_summary_weakness_patterns(data)
        assert patterns[0]["phase"] == "unknown"

    def test_stable_tiebreaker(self):
        # Two entries with same total_loss: should be sorted by count desc,
        # then category asc for deterministic ordering
        data = {
            "meta": {"games_analyzed": 5},
            "weaknesses": {
                "black": [
                    {"phase": "m", "category": "z_category", "count": 1, "total_loss": 10.0},
                    {"phase": "m", "category": "a_category", "count": 1, "total_loss": 10.0},
                    {"phase": "m", "category": "m_category", "count": 5, "total_loss": 10.0},
                ],
            },
        }
        patterns = extract_summary_weakness_patterns(data)
        cats = [p["category"] for p in patterns]
        # Same total_loss=10.0; sorted by count desc then category asc
        # count=5 first, then count=1 by category asc
        assert cats == ["m_category", "a_category", "z_category"]


# --- Phase 228-A: Real-shape extractors (players.<name>.mistakes / phases) ---


def _real_shape_summary() -> dict:
    """A realistic summary JSON shaped like what ``summary_json_export.py``
    actually produces (no top-level ``weaknesses`` or ``phase_x_mistake``).
    """
    return {
        "schema_version": "3.4",
        "meta": {
            "games_analyzed": 3,
            "date_range": ["2025-10-31", "2025-11-06"],
            "games_by_type": {"even": 3, "handicapped": 0, "unknown": 0},
        },
        "games": [{"game_id": "g1"}, {"game_id": "g2"}, {"game_id": "g3"}],
        "players": {
            "sentoku870": {
                "mistakes": {
                    "good": {"count": 310, "pct": 79.9, "denominator": 388, "avg_loss": 0.28},
                    "inaccuracy": {"count": 51, "pct": 13.1, "denominator": 388, "avg_loss": 3.11},
                    "mistake": {"count": 22, "pct": 5.7, "denominator": 388, "avg_loss": 5.69},
                    "blunder": {"count": 5, "pct": 1.3, "denominator": 388, "avg_loss": 19.04},
                },
                "phases": {
                    "opening": {"moves": 75, "total_loss": 47.01, "avg_loss": 0.627},
                    "middle": {"moves": 173, "total_loss": 370.78, "avg_loss": 2.143},
                    "endgame": {"moves": 140, "total_loss": 48.6, "avg_loss": 0.347},
                },
            },
            "opponent1": {
                "mistakes": {
                    "good": {"count": 350, "pct": 90.2, "denominator": 388, "avg_loss": 0.22},
                    "inaccuracy": {"count": 28, "pct": 7.2, "denominator": 388, "avg_loss": 2.95},
                    "mistake": {"count": 8, "pct": 2.1, "denominator": 388, "avg_loss": 5.5},
                    "blunder": {"count": 2, "pct": 0.5, "denominator": 388, "avg_loss": 18.0},
                },
                "phases": {
                    "opening": {"moves": 75, "total_loss": 30.0, "avg_loss": 0.4},
                    "middle": {"moves": 173, "total_loss": 150.0, "avg_loss": 0.87},
                    "endgame": {"moves": 140, "total_loss": 25.0, "avg_loss": 0.18},
                },
            },
        },
        "loss_progression": {"all": [{"mistake_count": 5}] * 3},
    }


class TestExtractPlayerMistakes:
    """Phase 228-A: ``extract_summary_player_mistakes`` for the real
    ``summary_json_export.py`` shape."""

    def test_extracts_two_players(self):
        data = _real_shape_summary()
        result = extract_summary_player_mistakes(data)
        assert set(result.keys()) == {"sentoku870", "opponent1"}

    def test_severity_order_blunder_first(self):
        # Categories emitted in severity order: blunder → mistake →
        # inaccuracy → good (descending severity).
        data = _real_shape_summary()
        categories = [m["category"] for m in extract_summary_player_mistakes(data)["sentoku870"]]
        assert categories == ["blunder", "mistake", "inaccuracy", "good"]

    def test_total_loss_reconstructed_from_avg_times_count(self):
        data = _real_shape_summary()
        sentoku = {m["category"]: m for m in extract_summary_player_mistakes(data)["sentoku870"]}
        # blunder: 5 * 19.04 = 95.20
        assert abs(sentoku["blunder"]["total_loss"] - 95.20) < 1e-9
        # mistake: 22 * 5.69 = 125.18
        assert abs(sentoku["mistake"]["total_loss"] - 125.18) < 1e-9
        # good: 310 * 0.28 = 86.80
        assert abs(sentoku["good"]["total_loss"] - 86.80) < 1e-9

    def test_entry_dict_keys(self):
        data = _real_shape_summary()
        entries = extract_summary_player_mistakes(data)["sentoku870"]
        for m in entries:
            assert set(m.keys()) == {
                "category",
                "count",
                "pct",
                "avg_loss",
                "total_loss",
                "denominator",
            }

    def test_no_players_block(self):
        assert extract_summary_player_mistakes({}) == {}

    def test_players_block_without_mistakes(self):
        # Players exist but no ``mistakes`` sub-block
        data = {"players": {"alice": {"phases": {}}}}
        assert extract_summary_player_mistakes(data) == {}

    def test_empty_mistakes_block_skipped(self):
        data = {"players": {"alice": {"mistakes": {}}}}
        assert extract_summary_player_mistakes(data) == {}

    def test_partial_mistakes_block(self):
        # Only "good" and "blunder" present — both should be returned
        data = {
            "players": {
                "alice": {
                    "mistakes": {
                        "good": {"count": 100, "pct": 90.0, "denominator": 111, "avg_loss": 0.1},
                        "blunder": {"count": 2, "pct": 1.8, "denominator": 111, "avg_loss": 10.0},
                    }
                }
            }
        }
        result = extract_summary_player_mistakes(data)
        assert len(result["alice"]) == 2
        # Severity order preserved
        assert result["alice"][0]["category"] == "blunder"
        assert result["alice"][1]["category"] == "good"

    def test_non_dict_player_block_skipped(self):
        data = {"players": {"alice": "not a dict"}}
        assert extract_summary_player_mistakes(data) == {}

    def test_non_dict_mistakes_block_skipped(self):
        data = {"players": {"alice": {"mistakes": "not a dict"}}}
        assert extract_summary_player_mistakes(data) == {}

    def test_non_dict_category_entry_skipped(self):
        # One category is malformed (not a dict) — should be skipped, others kept
        data = {
            "players": {
                "alice": {
                    "mistakes": {
                        "blunder": "not a dict",  # malformed
                        "good": {"count": 100, "pct": 90.0, "denominator": 111, "avg_loss": 0.1},
                    }
                }
            }
        }
        result = extract_summary_player_mistakes(data)
        assert len(result["alice"]) == 1
        assert result["alice"][0]["category"] == "good"

    def test_total_loss_field_in_json_takes_precedence(self):
        # When total_loss is explicitly in the JSON, don't overwrite it
        # with avg_loss * count.
        data = {
            "players": {
                "alice": {
                    "mistakes": {
                        "blunder": {
                            "count": 5,
                            "pct": 1.0,
                            "denominator": 500,
                            "avg_loss": 10.0,
                            "total_loss": 999.99,  # explicit
                        }
                    }
                }
            }
        }
        result = extract_summary_player_mistakes(data)
        assert result["alice"][0]["total_loss"] == 999.99

    def test_zero_count_does_not_crash(self):
        data = {
            "players": {
                "alice": {
                    "mistakes": {
                        "blunder": {"count": 0, "pct": 0.0, "denominator": 100, "avg_loss": 0.0},
                    }
                }
            }
        }
        result = extract_summary_player_mistakes(data)
        assert result["alice"][0]["count"] == 0
        assert result["alice"][0]["total_loss"] == 0.0


class TestExtractPlayerPhaseLosses:
    """Phase 228-A: ``extract_summary_player_phase_losses`` for the real
    ``summary_json_export.py`` shape."""

    def test_extracts_three_phases_per_player(self):
        data = _real_shape_summary()
        result = extract_summary_player_phase_losses(data)
        assert set(result["sentoku870"].keys()) == {"opening", "middle", "endgame"}
        assert set(result["opponent1"].keys()) == {"opening", "middle", "endgame"}

    def test_temporal_order(self):
        # opening → middle → endgame
        data = _real_shape_summary()
        phases = list(extract_summary_player_phase_losses(data)["sentoku870"].keys())
        assert phases == ["opening", "middle", "endgame"]

    def test_phase_entry_keys(self):
        data = _real_shape_summary()
        phases = extract_summary_player_phase_losses(data)["sentoku870"]
        for phase_data in phases.values():
            assert set(phase_data.keys()) == {"moves", "total_loss", "avg_loss"}

    def test_phase_values_preserved(self):
        data = _real_shape_summary()
        middle = extract_summary_player_phase_losses(data)["sentoku870"]["middle"]
        assert middle["moves"] == 173
        assert middle["total_loss"] == 370.78
        assert abs(middle["avg_loss"] - 2.143) < 1e-9

    def test_no_players_block(self):
        assert extract_summary_player_phase_losses({}) == {}

    def test_no_phases_block(self):
        data = {"players": {"alice": {"mistakes": {}}}}
        assert extract_summary_player_phase_losses(data) == {}

    def test_partial_phases_block(self):
        # Only opening and endgame present
        data = {
            "players": {
                "alice": {
                    "phases": {
                        "opening": {"moves": 50, "total_loss": 10.0, "avg_loss": 0.2},
                        "endgame": {"moves": 80, "total_loss": 25.0, "avg_loss": 0.3},
                    }
                }
            }
        }
        result = extract_summary_player_phase_losses(data)
        assert set(result["alice"].keys()) == {"opening", "endgame"}

    def test_non_dict_phase_entry_skipped(self):
        data = {
            "players": {
                "alice": {
                    "phases": {
                        "opening": "not a dict",
                        "middle": {"moves": 100, "total_loss": 50.0, "avg_loss": 0.5},
                    }
                }
            }
        }
        result = extract_summary_player_phase_losses(data)
        assert set(result["alice"].keys()) == {"middle"}


class TestExtractWeaknessPatternsShapeB:
    """Phase 228-A: ``extract_summary_weakness_patterns`` accepts the
    real ``players.<name>.mistakes`` shape when Shape A (top-level
    ``weaknesses``) is absent."""

    def test_synthesizes_patterns_from_player_mistakes(self):
        data = _real_shape_summary()
        # No top-level weaknesses → Shape B kicks in
        patterns = extract_summary_weakness_patterns(data)
        # 4 categories × 2 players = 8 patterns
        assert len(patterns) == 8

    def test_patterns_sorted_by_total_loss_desc(self):
        data = _real_shape_summary()
        patterns = extract_summary_weakness_patterns(data)
        losses = [p["total_loss"] for p in patterns]
        assert losses == sorted(losses, reverse=True)

    def test_player_field_present(self):
        data = _real_shape_summary()
        patterns = extract_summary_weakness_patterns(data)
        for p in patterns:
            assert "player" in p
            assert p["player"] in {"sentoku870", "opponent1"}

    def test_phase_is_all_for_shape_b(self):
        # Shape B doesn't carry phase info per mistake category
        data = _real_shape_summary()
        patterns = extract_summary_weakness_patterns(data)
        for p in patterns:
            assert p["phase"] == "all"

    def test_color_field_is_player_name(self):
        # For Shape B, the ``color`` field carries the player name
        # (matches Shape A's "color" semantics for compatibility)
        data = _real_shape_summary()
        patterns = extract_summary_weakness_patterns(data)
        for p in patterns:
            assert p["color"] == p["player"]

    def test_frequency_ratio_zero_for_shape_b_with_pct_alternative(self):
        # Phase 228-B: Shape B's ``count`` is per-move (e.g. 5 blunder
        # moves out of 388), so ``count / games_analyzed`` is
        # meaningless. The extractor surfaces the per-move ``pct``
        # field instead and leaves ``frequency_ratio`` at 0.0.
        data = _real_shape_summary()
        patterns = extract_summary_weakness_patterns(data)
        sentoku_blunder = next(p for p in patterns if p["player"] == "sentoku870" and p["category"] == "blunder")
        assert sentoku_blunder["frequency_ratio"] == 0.0
        # pct field carries the per-move percentage
        assert abs(sentoku_blunder["pct"] - 1.3) < 1e-9

    def test_top_n_cap(self):
        data = _real_shape_summary()
        patterns = extract_summary_weakness_patterns(data, top_n=3)
        assert len(patterns) == 3

    def test_no_games_analyzed_degrades_to_zero_freq(self):
        # No games_analyzed: frequency_ratio = 0.0 for all entries
        data = {
            "players": {
                "alice": {"mistakes": {"blunder": {"count": 5, "pct": 1.0, "denominator": 500, "avg_loss": 10.0}}}
            }
        }
        patterns = extract_summary_weakness_patterns(data)
        assert patterns[0]["frequency_ratio"] == 0.0
        assert patterns[0]["total_loss"] == 50.0

    def test_shape_a_wins_when_both_present(self):
        # When both shapes exist, Shape A takes priority (more precise
        # total_loss values)
        data = {
            "meta": {"games_analyzed": 3},
            "weaknesses": {"black": [{"phase": "middle", "category": "blunder", "count": 5, "total_loss": 100.0}]},
            "players": {
                "alice": {"mistakes": {"blunder": {"count": 5, "pct": 1.0, "denominator": 500, "avg_loss": 10.0}}}
            },
        }
        patterns = extract_summary_weakness_patterns(data)
        assert len(patterns) == 1
        # Shape A pattern has total_loss=100.0 (not the reconstructed 50.0)
        assert patterns[0]["total_loss"] == 100.0
        # Shape A patterns don't have the "player" field
        assert "player" not in patterns[0]
        # Shape A pattern has the literal "color"="black"
        assert patterns[0]["color"] == "black"

    def test_empty_when_no_recognisable_data(self):
        # No weaknesses and no players → empty
        assert extract_summary_weakness_patterns({}) == []
