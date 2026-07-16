"""Phase 229-A: tests for the shared :mod:`katrain.common.rank` module.

The shared module is the single source of truth for *parsing* and
*comparing* rank strings across the analysis and LLM coach subsystems.
These tests pin its public API:

* :py:class:`Rank` dataclass (``parse`` / ``from_canonical`` / ``is_dan``
  / ``display_jp`` / ``display_ascii``)
* :py:func:`canonical_rank_key` / :py:func:`normalise_rank_str`
  (also re-exported from ``master_db`` for backward compatibility)
* :py:func:`cmp_rank` / :py:func:`format_rank`
* :py:func:`rank_to_skill_preset` (rank -> analysis preset mapping)
* :data:`RANK_ORDER` / :data:`RANK_ALIASES` public aliases
"""

from __future__ import annotations

import dataclasses

import pytest

from katrain.common.rank import (
    RANK_ALIASES,
    RANK_ORDER,
    Rank,
    canonical_rank_key,
    cmp_rank,
    format_rank,
    normalise_rank_str,
)

# ---------------------------------------------------------------------------
# Rank dataclass — parse() factory
# ---------------------------------------------------------------------------


class TestRankParse:
    @pytest.mark.parametrize(
        "raw,expected_kyu_dan",
        [
            # ASCII kyu / dan
            ("30k", 0),
            ("10k", 5),
            ("5k", 10),
            ("1k", 14),
            ("1d", 15),
            ("5d", 19),
            ("9d", 23),
            # Kanji
            ("30級", 0),
            ("10級", 5),
            ("5級", 10),
            ("1級", 14),
            ("初段", 15),
            ("1段", 15),
            ("4段", 18),
            ("5段", 19),
            ("9段", 23),
            # Full-width digits
            ("４段", 18),
            ("１０級", 5),
            # ASCII suffix synonyms
            ("4kyu", 11),
            ("5dan", 19),
            # Whitespace / case
            (" 4d ", 18),
            ("4D", 18),
            # Trailing punctuation
            ("4d?", 18),
            ("4d.", 18),
            # Boundary aliases
            ("10段", 23),  # 10段 -> 9d
            ("99段", 99),  # 99段 -> 99d sentinel
        ],
    )
    def test_valid_inputs(self, raw: str, expected_kyu_dan: int) -> None:
        rank = Rank.parse(raw)
        assert rank is not None
        assert rank.kyu_dan == expected_kyu_dan

    @pytest.mark.parametrize("empty", ["", "  ", "\t", None])
    def test_empty_inputs(self, empty) -> None:
        assert Rank.parse(empty) is None

    @pytest.mark.parametrize(
        "garbage",
        [
            "xyzzy",
            "100段",
            "abc",
            "k",  # missing number
            "4e",  # suffix not in alphabet
            "4.5段",  # decimal not supported
            "九段",  # Chinese numerals not supported
        ],
    )
    def test_garbage_inputs(self, garbage: str) -> None:
        assert Rank.parse(garbage) is None

    def test_frozen(self) -> None:
        rank = Rank.parse("5k")
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            rank.kyu_dan = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Rank dataclass — from_canonical
# ---------------------------------------------------------------------------


class TestRankFromCanonical:
    @pytest.mark.parametrize(
        "canonical,expected_kyu_dan",
        [
            ("30k", 0),
            ("5k", 10),
            ("1d", 15),
            ("9d", 23),
            ("99d", 99),
        ],
    )
    def test_valid_canonical(self, canonical: str, expected_kyu_dan: int) -> None:
        rank = Rank.from_canonical(canonical)
        assert rank.kyu_dan == expected_kyu_dan

    def test_unknown_canonical_raises(self) -> None:
        with pytest.raises(KeyError):
            Rank.from_canonical("100d")


# ---------------------------------------------------------------------------
# Rank dataclass — properties
# ---------------------------------------------------------------------------


class TestRankProperties:
    @pytest.mark.parametrize(
        "raw,is_dan,ascii_repr,jp_repr",
        [
            ("30k", False, "30k", "30級"),
            ("10k", False, "10k", "10級"),
            ("5k", False, "5k", "5級"),
            ("1k", False, "1k", "1級"),
            ("1d", True, "1d", "初段"),
            ("4d", True, "4d", "4段"),
            ("9d", True, "9d", "9段"),
            ("99d", True, "99d", "99段"),
        ],
    )
    def test_properties(self, raw: str, is_dan: bool, ascii_repr: str, jp_repr: str) -> None:
        rank = Rank.parse(raw)
        assert rank is not None
        assert rank.is_dan is is_dan
        assert rank.display_ascii == ascii_repr
        assert rank.canonical == ascii_repr
        assert rank.display_jp == jp_repr

    def test_ordering_via_dataclass_order(self) -> None:
        # Rank is frozen with order=True, so Python's < / > / == operators
        # all derive from kyu_dan.
        weak = Rank.parse("30k")
        strong = Rank.parse("7d")
        assert weak is not None
        assert strong is not None
        assert weak < strong
        assert strong > weak
        assert Rank.parse("5k") == Rank.parse("5k")

    def test_repr(self) -> None:
        assert repr(Rank.parse("5k")) == "Rank(kyu_dan=10)"


# ---------------------------------------------------------------------------
# cmp_rank / format_rank helpers
# ---------------------------------------------------------------------------


class TestCmpRank:
    def test_weaker_is_less(self) -> None:
        a = Rank.parse("5k")
        b = Rank.parse("4段")
        assert a is not None and b is not None
        assert cmp_rank(a, b) < 0
        assert cmp_rank(b, a) > 0

    def test_equal_ranks(self) -> None:
        a = Rank.parse("5k")
        b = Rank.parse("5K")  # case-insensitive parse
        assert a is not None and b is not None
        assert cmp_rank(a, b) == 0

    def test_cross_mode_boundaries(self) -> None:
        # DAN band max (1d) and ADVANCED band min (2d)
        dan_top = Rank.parse("1d")
        adv_bot = Rank.parse("2d")
        assert dan_top is not None and adv_bot is not None
        assert cmp_rank(dan_top, adv_bot) < 0


class TestFormatRank:
    def test_default_is_ascii(self) -> None:
        rank = Rank.parse("4段")
        assert rank is not None
        assert format_rank(rank) == "4d"

    def test_ascii_style(self) -> None:
        rank = Rank.parse("5k")
        assert rank is not None
        assert format_rank(rank, "ascii") == "5k"

    def test_jp_style(self) -> None:
        rank = Rank.parse("5k")
        assert rank is not None
        assert format_rank(rank, "jp") == "5級"

    def test_jp_style_for_shodan(self) -> None:
        rank = Rank.parse("1d")
        assert rank is not None
        assert format_rank(rank, "jp") == "初段"

    def test_unknown_style_raises(self) -> None:
        rank = Rank.parse("5k")
        assert rank is not None
        with pytest.raises(ValueError):
            format_rank(rank, "binary")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# rank_to_skill_preset mapping
# ---------------------------------------------------------------------------


class TestRankToSkillPreset:
    @pytest.mark.parametrize(
        "rank_str,expected_preset",
        [
            # BEGINNER band -> relaxed
            ("30k", "relaxed"),
            ("25k", "relaxed"),
            ("20k", "relaxed"),
            ("15k", "relaxed"),
            ("11k", "relaxed"),
            # INTERMEDIATE band -> beginner
            ("10k", "beginner"),
            ("7k", "beginner"),
            ("5k", "beginner"),
            # DAN band -> standard
            ("4k", "standard"),
            ("2k", "standard"),
            ("1k", "standard"),
            ("1d", "standard"),
            # ADVANCED band -> advanced
            ("2d", "advanced"),
            ("4d", "advanced"),
            ("5d", "advanced"),
            # EXPERT band -> pro
            ("6d", "pro"),
            ("7d", "pro"),
            ("9d", "pro"),
            ("99d", "pro"),
        ],
    )
    def test_rank_to_preset(self, rank_str: str, expected_preset: str) -> None:
        from katrain.core.analysis.logic_skill import rank_to_skill_preset

        rank = Rank.parse(rank_str)
        assert rank is not None
        assert rank_to_skill_preset(rank) == expected_preset

    def test_accepts_string_input(self) -> None:
        from katrain.core.analysis.logic_skill import rank_to_skill_preset

        # Function accepts raw rank string and parses internally.
        assert rank_to_skill_preset("4段") == "advanced"
        assert rank_to_skill_preset("5k") == "beginner"

    def test_none_falls_back_to_default(self) -> None:
        from katrain.core.analysis.logic_skill import rank_to_skill_preset
        from katrain.core.analysis.models.skill import DEFAULT_SKILL_PRESET

        # When rank is unknown we fall back to DEFAULT_SKILL_PRESET.
        assert rank_to_skill_preset(None) == DEFAULT_SKILL_PRESET

    def test_garbage_string_falls_back_to_default(self) -> None:
        from katrain.core.analysis.logic_skill import rank_to_skill_preset
        from katrain.core.analysis.models.skill import DEFAULT_SKILL_PRESET

        assert rank_to_skill_preset("xyzzy") == DEFAULT_SKILL_PRESET

    def test_kanji_input_resolves(self) -> None:
        from katrain.core.analysis.logic_skill import rank_to_skill_preset

        assert rank_to_skill_preset(Rank.parse("4段")) == "advanced"
        assert rank_to_skill_preset(Rank.parse("6段")) == "pro"


# ---------------------------------------------------------------------------
# RANK_ORDER / RANK_ALIASES public aliases (cross-module consistency)
# ---------------------------------------------------------------------------


class TestRankTables:
    def test_rank_order_covers_all_canonical_keys(self) -> None:
        # Every canonical key listed in RANK_ALIASES must resolve to an
        # entry in RANK_ORDER (otherwise the alias is a dead code).
        for alias_target in set(RANK_ALIASES.values()):
            assert alias_target in RANK_ORDER, f"Alias target {alias_target!r} missing from RANK_ORDER"

    def test_no_duplicate_kyu_dan_values(self) -> None:
        # Two different canonical keys mapping to the same kyu_dan would
        # cause ambiguity in cmp_rank / rank_to_skill_preset.
        values = list(RANK_ORDER.values())
        assert len(values) == len(set(values)), "Duplicate kyu_dan in RANK_ORDER"

    def test_kyu_dan_monotonic_for_canonical_ranks(self) -> None:
        # Within the canonical 30k..9d sequence, kyu_dan should be strictly
        # monotonic (no gaps inbetween should cause inversions). 99d is a
        # sentinel for "stronger than 9d" and is intentionally non-monotonic.
        canonical_sequence = [
            "30k",
            "25k",
            "20k",
            "15k",
            "11k",
            "10k",
            "9k",
            "8k",
            "7k",
            "6k",
            "5k",
            "4k",
            "3k",
            "2k",
            "1k",
            "1d",
            "2d",
            "3d",
            "4d",
            "5d",
            "6d",
            "7d",
            "8d",
            "9d",
        ]
        values = [RANK_ORDER[k] for k in canonical_sequence]
        assert values == sorted(values)
        assert len(set(values)) == len(values), "Internal duplicates in canonical sequence"

    def test_aliases_map_to_known_keys(self) -> None:
        for alias, target in RANK_ALIASES.items():
            assert target in RANK_ORDER, f"Alias {alias!r} -> {target!r} but {target!r} not in RANK_ORDER"

    def test_rank_to_preset_has_all_kyu_dan_keys(self) -> None:
        # Every kyu_dan integer in RANK_ORDER should have a preset mapping.
        from katrain.core.analysis.models.skill import RANK_TO_PRESET_DEFAULT

        for kyu_dan in RANK_ORDER.values():
            assert kyu_dan in RANK_TO_PRESET_DEFAULT, f"RANK_TO_PRESET_DEFAULT missing entry for kyu_dan={kyu_dan}"


# ---------------------------------------------------------------------------
# normalise_rank_str / canonical_rank_key (cross-check against existing
# master_db tests, including a few edge cases not covered there)
# ---------------------------------------------------------------------------


class TestNormaliseAndCanonical:
    def test_normalise_preserves_already_canonical(self) -> None:
        assert normalise_rank_str("4d") == "4d"
        assert normalise_rank_str("5k") == "5k"

    def test_normalise_handles_whitespace_variants(self) -> None:
        assert normalise_rank_str(" 4d ") == "4d"
        assert normalise_rank_str("4 d") == "4d"

    def test_normalise_handles_full_width_space(self) -> None:
        # Full-width / ideographic space (U+3000) is stripped before the
        # kanji suffix is replaced, so the full sequence still resolves
        # to its canonical ASCII key.
        assert normalise_rank_str("４\u3000段") == "4d"

    def test_canonical_handles_whitespace_then_alias(self) -> None:
        # Pre-normalisation alias lookup strips whitespace, so a kanji
        # notation surrounded by spaces still resolves.
        assert canonical_rank_key(" 4段 ") == "4d"

    def test_canonical_empty_for_garbage(self) -> None:
        assert canonical_rank_key("xxx") == ""

    def test_canonical_returns_canonical_key(self) -> None:
        # canonical_rank_key should return a key present in RANK_ORDER or "".
        for raw in ["4d", "5k", "4段", "1級", "初段", "10段"]:
            key = canonical_rank_key(raw)
            assert key == "" or key in RANK_ORDER
