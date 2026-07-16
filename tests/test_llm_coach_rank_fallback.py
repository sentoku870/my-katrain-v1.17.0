"""Phase 229-D: tests for :func:`resolve_rank_fallback_chain`.

The LLM Coach rank auto-detection priority chain has three sources:

1. Karte/SGF ``info`` dict (Karte ``meta.player_info``, SGF ``BR``/``WR``)
2. ``general/player_rank`` (new global setting added in Phase 229-C)
3. ``mykatrain_settings.default_user_rank`` (Phase 225.8 legacy fallback)

These tests pin the chain without requiring Kivy.
"""

from __future__ import annotations

import pytest

from katrain.gui.features.llm_coach import resolve_rank_fallback_chain


# ---------------------------------------------------------------------------
# Priority 1: Karte/SGF info dict
# ---------------------------------------------------------------------------


class TestKarteSgfTakesPriority:
    def test_info_black_rank_wins(self) -> None:
        info = {"black": {"rank": "5d"}, "white": {"rank": "3k"}}
        assert (
            resolve_rank_fallback_chain(info, "B", general_player_rank="1d", default_user_rank="7k")
            == "5d"
        )

    def test_info_white_rank_wins(self) -> None:
        info = {"black": {"rank": "5d"}, "white": {"rank": "3k"}}
        assert (
            resolve_rank_fallback_chain(info, "W", general_player_rank="1d", default_user_rank="7k")
            == "3k"
        )

    def test_auto_perspective_picks_black_first(self) -> None:
        info = {"black": {"rank": "5d"}, "white": {"rank": "3k"}}
        # Auto picks whichever is set; black takes precedence.
        assert (
            resolve_rank_fallback_chain(info, "auto", general_player_rank="1d")
            == "5d"
        )

    def test_auto_falls_through_to_white(self) -> None:
        info = {"black": {}, "white": {"rank": "3k"}}
        assert resolve_rank_fallback_chain(info, "auto") == "3k"

    def test_info_partial_dict(self) -> None:
        # Karte may omit one side entirely.
        info = {"black": {"rank": "4段"}}
        assert (
            resolve_rank_fallback_chain(info, "auto", general_player_rank="1d")
            == "4段"
        )


# ---------------------------------------------------------------------------
# Priority 2: general/player_rank (Phase 229-C setting)
# ---------------------------------------------------------------------------


class TestGeneralPlayerRank:
    def test_no_info_falls_to_general(self) -> None:
        assert resolve_rank_fallback_chain(None, "auto", general_player_rank="5d") == "5d"

    def test_general_wins_over_default_user_rank(self) -> None:
        assert (
            resolve_rank_fallback_chain(None, "auto", general_player_rank="5d", default_user_rank="1k")
            == "5d"
        )

    def test_empty_general_falls_to_default_user_rank(self) -> None:
        assert resolve_rank_fallback_chain(None, "auto", general_player_rank="", default_user_rank="1k") == "1k"

    def test_none_general_falls_to_default_user_rank(self) -> None:
        assert (
            resolve_rank_fallback_chain(None, "auto", general_player_rank=None, default_user_rank="4段")
            == "4段"
        )


# ---------------------------------------------------------------------------
# Priority 3: default_user_rank (Phase 225.8 fallback)
# ---------------------------------------------------------------------------


class TestDefaultUserRank:
    def test_only_default_user_rank(self) -> None:
        assert resolve_rank_fallback_chain(None, "auto", default_user_rank="2d") == "2d"

    def test_default_user_rank_used_when_no_others(self) -> None:
        assert resolve_rank_fallback_chain({}, "auto", default_user_rank="4段") == "4段"


# ---------------------------------------------------------------------------
# Empty chain
# ---------------------------------------------------------------------------


class TestEmptyChain:
    def test_all_none_returns_none(self) -> None:
        assert resolve_rank_fallback_chain(None, "auto") is None

    def test_all_empty_returns_none(self) -> None:
        assert (
            resolve_rank_fallback_chain({"black": {}, "white": {}}, "auto", general_player_rank="", default_user_rank="")
            is None
        )

    def test_info_with_no_ranks_falls_through(self) -> None:
        info = {"black": {"name": "alice"}, "white": {"name": "bob"}}
        # No rank in info -> falls through to general_player_rank.
        assert resolve_rank_fallback_chain(info, "auto", general_player_rank="5k") == "5k"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_info_empty_rank_string_treated_as_missing(self) -> None:
        # An empty string rank in info should not "win"; it should
        # fall through to the next source.
        info = {"black": {"rank": ""}, "white": {"rank": ""}}
        assert resolve_rank_fallback_chain(info, "auto", general_player_rank="5d") == "5d"

    def test_whitespace_in_general_player_rank(self) -> None:
        # We do NOT strip whitespace here (the rank input handler
        # in the popup does the stripping).  The chain returns
        # what the caller passed in.
        assert resolve_rank_fallback_chain(None, "auto", general_player_rank=" 5d ") == " 5d "

    def test_kanji_rank_preserved(self) -> None:
        # Phase 229-D does not parse the rank string — that's the job
        # of :func:`katrain.common.rank.canonical_rank_key` which the
        # prompt builder invokes later.  We just pass through.
        info = {"black": {"rank": "4段"}}
        assert resolve_rank_fallback_chain(info, "B") == "4段"