"""Phase 272: tests for :mod:`katrain.core.coach.player_rank_mode`.

The 5-level :class:`CoachMode` selector is the single source of truth
for the player rank in Phase 272. This module is the bridge that
keeps the analysis tab, LLM Coach, AI opponent, PV Filter and
Beginner Hints in sync, while remaining backward compatible with
existing config files that still contain free-text rank values like
``"4d"`` / ``"4段"``.

Coverage:

- :func:`parse_mode_key` — accepts both mode keys and legacy text,
  normalises to a stable CoachMode.value string.
- :func:`is_valid_mode_key` — strict validation.
- :func:`coerce_to_mode_key` — safe default fallback.
- :func:`migrate_general_player_rank` — config-dict in-place migration
  used by the saver and by startup migration.

Note:
    Tests are pure-function unit tests; no Kivy required.
"""

from __future__ import annotations

import pytest

from katrain.core.coach.master_db import CoachMode
from katrain.core.coach.player_rank_mode import (
    coerce_to_mode_key,
    is_valid_mode_key,
    migrate_general_player_rank,
    parse_mode_key,
)

# ---------------------------------------------------------------------------
# parse_mode_key — happy path
# ---------------------------------------------------------------------------


class TestParseModeKey:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("beginner", "beginner"),
            ("intermediate", "intermediate"),
            ("dan", "dan"),
            ("advanced", "advanced"),
            ("expert", "expert"),
        ],
    )
    def test_mode_key_passes_through(self, raw: str, expected: str) -> None:
        assert parse_mode_key(raw) == expected

    def test_mode_key_case_insensitive(self) -> None:
        assert parse_mode_key("ADVANCED") == "advanced"
        assert parse_mode_key("Expert") == "expert"

    def test_mode_key_with_whitespace(self) -> None:
        assert parse_mode_key("  advanced  ") == "advanced"

    # Legacy rank text → nearest mode
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("30k", "beginner"),
            ("11k", "beginner"),
            ("10k", "intermediate"),
            ("5k", "intermediate"),
            ("4k", "dan"),
            ("1k", "dan"),
            ("1d", "dan"),
            ("2d", "advanced"),
            ("4d", "advanced"),
            ("5d", "advanced"),
            ("6d", "expert"),
            ("9d", "expert"),
            ("4段", "advanced"),
            ("5級", "intermediate"),
            ("初段", "dan"),
            ("10段", "expert"),
        ],
    )
    def test_legacy_rank_maps_to_mode(self, raw: str, expected: str) -> None:
        assert parse_mode_key(raw) == expected

    def test_empty_returns_none(self) -> None:
        assert parse_mode_key("") is None
        assert parse_mode_key("   ") is None
        assert parse_mode_key(None) is None

    def test_unrecognised_returns_none(self) -> None:
        assert parse_mode_key("xyzzy") is None
        assert parse_mode_key("not-a-rank") is None


# ---------------------------------------------------------------------------
# is_valid_mode_key
# ---------------------------------------------------------------------------


class TestIsValidModeKey:
    @pytest.mark.parametrize("key", ["beginner", "intermediate", "dan", "advanced", "expert"])
    def test_valid(self, key: str) -> None:
        assert is_valid_mode_key(key) is True

    def test_valid_with_whitespace_and_case(self) -> None:
        assert is_valid_mode_key(" ADVANCED ") is True

    @pytest.mark.parametrize("raw", ["", None, "xyzzy", "4d", "4段", "beginners", "advanced1"])
    def test_invalid(self, raw) -> None:
        assert is_valid_mode_key(raw) is False


# ---------------------------------------------------------------------------
# coerce_to_mode_key
# ---------------------------------------------------------------------------


class TestCoerceToModeKey:
    def test_returns_default_for_none(self) -> None:
        assert coerce_to_mode_key(None) == CoachMode.INTERMEDIATE.value

    def test_returns_default_for_empty(self) -> None:
        assert coerce_to_mode_key("") == CoachMode.INTERMEDIATE.value

    def test_returns_default_for_invalid(self) -> None:
        # Falls back to INTERMEDIATE — NEVER BEGINNER. This is the
        # whole point of the Phase 272 helper: the previous code path
        # `modes_for_voice(voice)[0]` always returned BEGINNER for any
        # TOMOKO voice, which produced wrong `Level:` headers.
        assert coerce_to_mode_key("xyzzy") == CoachMode.INTERMEDIATE.value

    def test_custom_default(self) -> None:
        assert coerce_to_mode_key(None, default=CoachMode.EXPERT) == "expert"
        assert coerce_to_mode_key("xyzzy", default=CoachMode.DAN) == "dan"

    def test_valid_input_returns_as_is(self) -> None:
        assert coerce_to_mode_key("advanced") == "advanced"
        assert coerce_to_mode_key("5d") == "advanced"
        assert coerce_to_mode_key("4段") == "advanced"


# ---------------------------------------------------------------------------
# migrate_general_player_rank
# ---------------------------------------------------------------------------


class TestMigrateGeneralPlayerRank:
    def test_migrates_4d_to_advanced(self) -> None:
        config = {"general": {"player_rank": "4d"}}
        migrate_general_player_rank(config)
        assert config["general"]["player_rank"] == "advanced"

    def test_migrates_kanji_to_mode(self) -> None:
        config = {"general": {"player_rank": "4段"}}
        migrate_general_player_rank(config)
        assert config["general"]["player_rank"] == "advanced"

    def test_already_mode_key_no_op(self) -> None:
        config = {"general": {"player_rank": "advanced"}}
        original = dict(config)
        migrate_general_player_rank(config)
        assert config == original

    def test_already_mode_key_with_other_keys(self) -> None:
        config = {"general": {"player_rank": "intermediate", "lang": "en"}}
        migrate_general_player_rank(config)
        assert config["general"]["player_rank"] == "intermediate"
        assert config["general"]["lang"] == "en"  # unrelated keys preserved

    def test_empty_to_intermediate(self) -> None:
        config = {"general": {"player_rank": ""}}
        migrate_general_player_rank(config)
        assert config["general"]["player_rank"] == "intermediate"

    def test_missing_player_rank_to_intermediate(self) -> None:
        config = {"general": {"lang": "en"}}
        migrate_general_player_rank(config)
        assert config["general"]["player_rank"] == "intermediate"

    def test_missing_general_section_no_op(self) -> None:
        config: dict = {}
        migrate_general_player_rank(config)
        assert config == {}

    def test_invalid_to_intermediate(self) -> None:
        config = {"general": {"player_rank": "xyzzy"}}
        migrate_general_player_rank(config)
        assert config["general"]["player_rank"] == "intermediate"

    def test_idempotent(self) -> None:
        config = {"general": {"player_rank": "4段"}}
        migrate_general_player_rank(config)
        first = config["general"]["player_rank"]
        migrate_general_player_rank(config)
        assert config["general"]["player_rank"] == first

    def test_non_dict_general_no_op(self) -> None:
        # Defensive: if general is somehow not a dict, skip.
        config = {"general": "not a dict"}
        migrate_general_player_rank(config)
        assert config["general"] == "not a dict"

    def test_returns_input_for_chaining(self) -> None:
        config = {"general": {"player_rank": "4d"}}
        result = migrate_general_player_rank(config)
        assert result is config
