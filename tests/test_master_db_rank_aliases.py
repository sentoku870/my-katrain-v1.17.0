"""Phase 225.8: tests for the rank-notational-alias helpers.

The user reported that entering ``"4段"`` (the kanji notation that
野狐 / KGS write to SGF BR/WR properties) made
``estimate_mode_from_rank`` return ``None``, causing the LLM Coach
to fall back to BEGINNER. These tests pin the kanji / full-width /
suffix aliases so the fix doesn't regress.
"""

from __future__ import annotations

import pytest

from katrain.core.coach.master_db import (
    CoachMode,
    _canonical_rank_key,
    _normalise_rank_str,
    estimate_mode_from_rank,
)


class TestNormaliseRankStr:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("4d", "4d"),
            ("4D", "4d"),
            (" 4d ", "4d"),
            ("4 d", "4d"),
            ("4段", "4d"),
            ("４段", "4d"),       # full-width digits
            ("４ 段", "4d"),
            ("10級", "10k"),
            ("30級", "30k"),
            ("4kyu", "4k"),
            ("5dan", "5d"),
            ("4d?", "4d"),         # trailing punctuation
            ("4d.", "4d"),
            ("4d !", "4d"),
            ("初段", "1d"),
            ("99段", "99d"),
        ],
    )
    def test_normalisation(self, raw: str, expected: str) -> None:
        assert _normalise_rank_str(raw) == expected

    @pytest.mark.parametrize("empty", ["", "  ", None])
    def test_empty_inputs(self, empty) -> None:
        assert _normalise_rank_str(empty) == ""


class TestCanonicalRankKey:
    def test_ascii_passthrough(self):
        assert _canonical_rank_key("4d") == "4d"
        assert _canonical_rank_key("5k") == "5k"

    def test_kanji_routes_to_ascii(self):
        assert _canonical_rank_key("4段") == "4d"
        assert _canonical_rank_key("6級") == "6k"
        assert _canonical_rank_key("初段") == "1d"

    def test_full_width_digits(self):
        assert _canonical_rank_key("４段") == "4d"

    def test_empty_returns_empty(self):
        assert _canonical_rank_key("") == ""
        assert _canonical_rank_key(None) == ""  # type: ignore[arg-type]

    def test_unknown_returns_empty(self):
        assert _canonical_rank_key("foobar") == ""

    def test_ten_dan_aliases_to_nine_dan(self):
        # Phase 226-C (C1): ``10段`` was previously dead-code in
        # _RANK_ALIASES because _normalise_rank_str collapsed it to
        # ``10d`` first. Now it routes through the pre-normalisation
        # alias lookup and resolves to ``9d``.
        assert _canonical_rank_key("10段") == "9d"

    def test_aliases_with_whitespace(self):
        # Pre-normalisation lookup strips whitespace.
        assert _canonical_rank_key(" 4段 ") == "4d"


class TestEstimateModeFromRank:
    """End-to-end: the previously-broken kanji notations now resolve."""

    @pytest.mark.parametrize(
        "rank,expected",
        [
            # ASCII (regression — must still work)
            ("4d", CoachMode.ADVANCED),
            ("5k", CoachMode.INTERMEDIATE),
            ("10k", CoachMode.INTERMEDIATE),
            ("7d", CoachMode.EXPERT),
            # Phase 225.8: kanji / full-width / suffix variants.
            # Actual mode ranges from master_db §0-1:
            #   BEGINNER:    rank 0-4  (30k-11k)
            #   INTERMEDIATE: rank 5-10 (10k-5k)
            #   DAN:         rank 11-15 (4k-1d)
            #   ADVANCED:    rank 16-19 (2d-5d)
            #   EXPERT:      rank 20+  (6d+)
            ("4段", CoachMode.ADVANCED),   # 4d = rank 18
            ("5段", CoachMode.ADVANCED),   # 5d = rank 19
            ("6段", CoachMode.EXPERT),     # 6d = rank 20 (boundary)
            ("3段", CoachMode.ADVANCED),   # 3d = rank 17 (boundary)
            ("2段", CoachMode.ADVANCED),   # 2d = rank 16 (boundary, ADVANCED inclusive)
            ("初段", CoachMode.DAN),       # 1d = rank 15 (shodan, DAN inclusive)
            ("1段", CoachMode.DAN),        # 1d = rank 15
            ("6級", CoachMode.INTERMEDIATE),  # 6k = rank 9
            ("10級", CoachMode.INTERMEDIATE), # 10k = rank 5 (boundary)
            ("1級", CoachMode.DAN),           # 1k = rank 14, in DAN
            ("4kyu", CoachMode.DAN),          # 4k = rank 11, in DAN
            ("5dan", CoachMode.ADVANCED),     # 5d = rank 19
            ("４段", CoachMode.ADVANCED),     # full-width digits
        ],
    )
    def test_returns_expected_mode(self, rank: str, expected: CoachMode) -> None:
        assert estimate_mode_from_rank(rank) == expected

    def test_none_returns_none(self):
        assert estimate_mode_from_rank(None) is None

    def test_empty_returns_none(self):
        assert estimate_mode_from_rank("") is None

    def test_garbage_returns_none(self):
        assert estimate_mode_from_rank("xyzzy") is None

    def test_ten_dan_kanji_resolves_to_expert(self):
        # Phase 226-C (C1): ``10段`` routes through _RANK_ALIASES
        # (now a *pre*-normalisation lookup) to ``9d`` → EXPERT.
        assert estimate_mode_from_rank("10段") == CoachMode.EXPERT
