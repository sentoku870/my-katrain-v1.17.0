"""Phase 272-B: tests for :func:`resolve_rank_fallback_chain`.

The LLM Coach rank auto-detection priority chain has three sources
(Phase 272-B reordered):

1. ``general/player_rank`` (analysis-tab global setting — always wins)
2. Karte/SGF ``info`` dict (Karte ``meta.player_info``, SGF ``BR``/``WR``)
3. ``mykatrain_settings.default_user_rank`` (Phase 225.8 legacy fallback)

Phase 272-B flipped the legacy priority (Karte was first). The new
order reflects the user's intent: the analysis-tab Spinner is the
authoritative source because the user just changed it explicitly.

These tests pin the chain without requiring Kivy.
"""

from __future__ import annotations

from katrain.gui.features.llm_coach import resolve_rank_fallback_chain

# ---------------------------------------------------------------------------
# Priority 1: general/player_rank (Phase 272-B always wins)
# ---------------------------------------------------------------------------


class TestGeneralPlayerRankWins:
    def test_general_wins_over_info_black(self) -> None:
        info = {"black": {"rank": "5d"}, "white": {"rank": "3k"}}
        assert resolve_rank_fallback_chain(info, "B", general_player_rank="1d", default_user_rank="7k") == "1d"

    def test_general_wins_over_info_white(self) -> None:
        info = {"black": {"rank": "5d"}, "white": {"rank": "3k"}}
        assert resolve_rank_fallback_chain(info, "W", general_player_rank="1d", default_user_rank="7k") == "1d"

    def test_general_wins_over_auto_perspective(self) -> None:
        info = {"black": {"rank": "5d"}, "white": {"rank": "3k"}}
        # Phase 272-B: even with auto perspective, general_player_rank wins.
        assert resolve_rank_fallback_chain(info, "auto", general_player_rank="advanced") == "advanced"

    def test_general_wins_over_partial_info(self) -> None:
        info = {"black": {"rank": "4段"}}
        assert resolve_rank_fallback_chain(info, "auto", general_player_rank="advanced") == "advanced"

    def test_general_wins_over_default_user_rank(self) -> None:
        assert resolve_rank_fallback_chain(None, "auto", general_player_rank="5d", default_user_rank="1k") == "5d"

    def test_empty_general_falls_to_default_user_rank(self) -> None:
        assert resolve_rank_fallback_chain(None, "auto", general_player_rank="", default_user_rank="1k") == "1k"

    def test_none_general_falls_to_default_user_rank(self) -> None:
        assert resolve_rank_fallback_chain(None, "auto", general_player_rank=None, default_user_rank="4段") == "4段"


# ---------------------------------------------------------------------------
# Priority 2: Karte/SGF info dict (used when no general_player_rank)
# ---------------------------------------------------------------------------


class TestKarteSgfAsFallback:
    def test_info_black_used_when_no_general(self) -> None:
        info = {"black": {"rank": "5d"}, "white": {"rank": "3k"}}
        assert resolve_rank_fallback_chain(info, "B") == "5d"

    def test_info_white_used_when_no_general(self) -> None:
        info = {"black": {"rank": "5d"}, "white": {"rank": "3k"}}
        assert resolve_rank_fallback_chain(info, "W") == "3k"

    def test_auto_picks_black_first_when_no_general(self) -> None:
        info = {"black": {"rank": "5d"}, "white": {"rank": "3k"}}
        assert resolve_rank_fallback_chain(info, "auto") == "5d"

    def test_auto_falls_through_to_white(self) -> None:
        info = {"black": {}, "white": {"rank": "3k"}}
        assert resolve_rank_fallback_chain(info, "auto") == "3k"

    def test_info_partial_dict(self) -> None:
        info = {"black": {"rank": "4段"}}
        assert resolve_rank_fallback_chain(info, "auto") == "4段"

    def test_info_used_when_general_empty(self) -> None:
        info = {"black": {"rank": "5d"}}
        assert resolve_rank_fallback_chain(info, "auto", general_player_rank="") == "5d"


# ---------------------------------------------------------------------------
# Priority 3: default_user_rank (Phase 225.8 legacy fallback)
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
            resolve_rank_fallback_chain(
                {"black": {}, "white": {}}, "auto", general_player_rank="", default_user_rank=""
            )
            is None
        )

    def test_info_with_no_ranks_falls_through_to_general(self) -> None:
        info = {"black": {"name": "alice"}, "white": {"name": "bob"}}
        # No rank in info -> falls through to general_player_rank.
        assert resolve_rank_fallback_chain(info, "auto", general_player_rank="5k") == "5k"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_info_empty_rank_string_treated_as_missing(self) -> None:
        info = {"black": {"rank": ""}, "white": {"rank": ""}}
        # Empty rank in info should not "win"; fall through to general.
        assert resolve_rank_fallback_chain(info, "auto", general_player_rank="advanced") == "advanced"

    def test_whitespace_in_general_player_rank(self) -> None:
        assert resolve_rank_fallback_chain(None, "auto", general_player_rank=" 5d ") == " 5d "

    def test_kanji_rank_preserved(self) -> None:
        info = {"black": {"rank": "4段"}}
        # No general_player_rank; info wins.
        assert resolve_rank_fallback_chain(info, "B") == "4段"

    def test_mode_key_passes_through_general(self) -> None:
        # Phase 272: general_player_rank is now a mode key like "advanced".
        assert resolve_rank_fallback_chain(None, "auto", general_player_rank="advanced") == "advanced"

    def test_mode_key_overrides_info_kanji(self) -> None:
        # Critical regression test for Phase 272-B.
        info = {"black": {"rank": "4段"}, "white": {"rank": "4段"}}
        # User explicitly chose ADVANCED in the analysis-tab Spinner.
        assert resolve_rank_fallback_chain(info, "auto", general_player_rank="advanced") == "advanced"
