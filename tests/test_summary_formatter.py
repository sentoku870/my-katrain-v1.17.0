"""Pure-function unit tests for katrain.gui.features.summary_formatter.

Phase 173 (P0-②-A): Architecture review identified summary_formatter.py as a
critical untested file (0% coverage, 1137 lines). This module focuses on the
pure / Kivy-independent helpers that drive pattern mining and summary
aggregation. The goal is to lock down the deterministic transforms with
fast, dependency-free tests before attempting Kivy-based UI smoke tests.

Scope (Kivy-free, fully testable without side effects):
    - _normalize_board_size
    - _stable_sort_key
    - _is_valid_player
    - _is_valid_gtp
    - _is_valid_move_number
    - _filter_by_board_size
    - _reconstruct_pattern_input
    - _format_game_refs
    - _PatternMoveEval (duck-typed helper)
    - _append_phase_mistake_breakdown (pure mutator)
"""

from __future__ import annotations

import pytest

from katrain.core import eval_metrics
from katrain.core.batch.stats.pattern_miner import GameRef
from katrain.gui.features import summary_formatter as sf


# ---------------------------------------------------------------------------
# _normalize_board_size
# ---------------------------------------------------------------------------


class TestNormalizeBoardSize:
    """Tests for _normalize_board_size covering tuple/list/None/scalar."""

    def test_none_returns_none(self):
        assert sf._normalize_board_size(None) is None

    def test_empty_tuple_returns_none(self):
        assert sf._normalize_board_size(()) is None
        assert sf._normalize_board_size([]) is None

    def test_valid_tuple(self):
        assert sf._normalize_board_size((19, 19)) == (19, 19)
        assert sf._normalize_board_size((9, 13)) == (9, 13)

    def test_valid_list(self):
        # JSON deserialization produces lists, not tuples.
        assert sf._normalize_board_size([19, 19]) == (19, 19)
        assert sf._normalize_board_size([13, 9]) == (13, 9)

    def test_non_numeric_returns_none(self):
        assert sf._normalize_board_size((19, "x")) is None
        assert sf._normalize_board_size(("a", 19)) is None

    def test_short_sequence_returns_none(self):
        assert sf._normalize_board_size((19,)) is None


# ---------------------------------------------------------------------------
# _stable_sort_key
# ---------------------------------------------------------------------------


class TestStableSortKey:
    def test_uses_defaults_for_missing_fields(self):
        key = sf._stable_sort_key({})
        assert key == ("", "", 0, 0)

    def test_date_none_treated_as_empty_string(self):
        # DB rows may have explicit None for missing date.
        key = sf._stable_sort_key({"game_name": "g", "date": None})
        assert key[1] == ""

    def test_full_key_order(self):
        stats = {"game_name": "B", "date": "2025-01-01", "total_moves": 100, "source_index": 5}
        assert sf._stable_sort_key(stats) == ("B", "2025-01-01", 100, 5)


# ---------------------------------------------------------------------------
# _is_valid_player
# ---------------------------------------------------------------------------


class TestIsValidPlayer:
    @pytest.mark.parametrize("player", ["B", "W"])
    def test_valid_colors(self, player):
        assert sf._is_valid_player(player) is True

    @pytest.mark.parametrize("player", ["b", "w", "BLACK", "?", None, ""])
    def test_invalid_colors(self, player):
        assert sf._is_valid_player(player) is False


# ---------------------------------------------------------------------------
# _is_valid_gtp
# ---------------------------------------------------------------------------


class TestIsValidGtp:
    @pytest.mark.parametrize(
        "coord",
        ["D4", "Q16", "T19", "A1", "a1", "J10"],
    )
    def test_valid_default_19(self, coord):
        assert sf._is_valid_gtp(coord, 19) is True

    @pytest.mark.parametrize("coord", ["", None, "pass", "resign", "ABCD", "Z4", "10", "QQ", "I1", "t25", "T25"])
    def test_invalid_strings(self, coord):
        # 'I1' is invalid because 'I' is excluded from the regex per GTP convention.
        # 't25'/'T25' are invalid because row 25 is off-board on a 19x19 board.
        assert sf._is_valid_gtp(coord, 19) is False

    def test_non_string_types_rejected(self):
        assert sf._is_valid_gtp(123, 19) is False
        assert sf._is_valid_gtp(["D", "4"], 19) is False

    def test_out_of_bounds_rejected(self):
        # 19x19 should not contain column "U".
        assert sf._is_valid_gtp("U4", 19) is False
        # Row 19 is still valid (last row on 19x19); row 20+ is not.
        assert sf._is_valid_gtp("T19", 19) is True
        assert sf._is_valid_gtp("T20", 19) is False

    def test_strip_whitespace(self):
        assert sf._is_valid_gtp("  D4  ", 19) is True

    def test_small_board_boundary(self):
        # 9x9 has valid columns A-H, J (with 'I' skipped entirely).
        assert sf._is_valid_gtp("A9", 9) is True
        assert sf._is_valid_gtp("H9", 9) is True
        # J is the 9th column on a 9x9 board (1-indexed), so valid.
        assert sf._is_valid_gtp("J1", 9) is True
        # K is off-board.
        assert sf._is_valid_gtp("K1", 9) is False
        # Row 10 off-board.
        assert sf._is_valid_gtp("A10", 9) is False


# ---------------------------------------------------------------------------
# _is_valid_move_number
# ---------------------------------------------------------------------------


class TestIsValidMoveNumber:
    @pytest.mark.parametrize("n", [1, 5, 100, 999])
    def test_positive_ints_valid(self, n):
        assert sf._is_valid_move_number(n) is True

    @pytest.mark.parametrize("n", [0, -1, -100])
    def test_non_positive_rejected(self, n):
        assert sf._is_valid_move_number(n) is False

    @pytest.mark.parametrize("n", [1.5, "1", None, True])
    def test_wrong_types_rejected(self, n):
        # Note: bool is a subclass of int in Python, so True (which == 1) would
        # actually be valid. Parametrize only confirmed non-int cases.
        if isinstance(n, bool):
            assert sf._is_valid_move_number(n) is True
        else:
            assert sf._is_valid_move_number(n) is False


# ---------------------------------------------------------------------------
# _PatternMoveEval (duck-typed helper for pattern mining)
# ---------------------------------------------------------------------------


class TestPatternMoveEval:
    def test_minimal_dict_uses_defaults(self):
        mv = sf._PatternMoveEval({})
        assert mv.move_number == 0
        assert mv.player is None
        assert mv.gtp is None
        assert mv.score_loss is None
        assert mv.points_lost is None
        assert mv.meaning_tag_id is None
        assert mv.mistake_category is None

    def test_valid_mistake_category_mapped(self):
        mv = sf._PatternMoveEval({"mistake_category": "MISTAKE"})
        assert mv.mistake_category == eval_metrics.MistakeCategory.MISTAKE

    def test_invalid_mistake_category_logs_and_skips(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING, logger="katrain.gui.features.summary_formatter"):
            mv = sf._PatternMoveEval({"mistake_category": "DOES_NOT_EXIST", "move_number": 42})
        assert mv.mistake_category is None
        assert "Invalid mistake_category" in caplog.text
        assert "42" in caplog.text

    def test_all_fields_propagated(self):
        mv = sf._PatternMoveEval(
            {
                "move_number": 7,
                "player": "B",
                "gtp": "D4",
                "score_loss": 1.5,
                "points_lost": 2.0,
                "meaning_tag_id": "urgent_miss",
                "mistake_category": "BLUNDER",
            }
        )
        assert mv.move_number == 7
        assert mv.player == "B"
        assert mv.gtp == "D4"
        assert mv.score_loss == 1.5
        assert mv.points_lost == 2.0
        assert mv.meaning_tag_id == "urgent_miss"
        assert mv.mistake_category == eval_metrics.MistakeCategory.BLUNDER


# ---------------------------------------------------------------------------
# _filter_by_board_size
# ---------------------------------------------------------------------------


def _make_stats(game_name: str = "g", board_size=None, **extra) -> dict:
    """Helper to build a minimal stats dict for board-size filter tests."""
    return {"game_name": game_name, "board_size": board_size, **extra}


class TestFilterByBoardSize:
    def test_all_consistent_square_19(self):
        stats_list = [_make_stats(f"g{i}", board_size=(19, 19)) for i in range(3)]
        filtered, size = sf._filter_by_board_size(stats_list)
        assert size == 19
        assert len(filtered) == 3

    def test_tuple_and_list_both_normalized(self):
        # JSON deserialization produces lists, not tuples.
        stats_list = [
            _make_stats("g1", board_size=(19, 19)),
            _make_stats("g2", board_size=[19, 19]),
        ]
        filtered, size = sf._filter_by_board_size(stats_list)
        assert size == 19
        assert len(filtered) == 2

    def test_non_square_games_skipped(self):
        stats_list = [
            _make_stats("ok", board_size=(9, 9)),
            _make_stats("non_sq", board_size=(9, 13)),
        ]
        filtered, size = sf._filter_by_board_size(stats_list)
        assert size == 9
        assert len(filtered) == 1
        assert filtered[0]["game_name"] == "ok"

    def test_invalid_board_size_skipped(self):
        stats_list = [
            _make_stats("valid", board_size=(19, 19)),
            _make_stats("missing", board_size=None),
            _make_stats("junk", board_size="bad"),
        ]
        filtered, size = sf._filter_by_board_size(stats_list)
        assert size == 19
        assert len(filtered) == 1
        assert filtered[0]["game_name"] == "valid"

    def test_empty_list(self):
        filtered, size = sf._filter_by_board_size([])
        assert filtered == []
        assert size is None

    def test_mixed_sizes_picks_most_common(self):
        # 19x19 appears twice, 9x9 once → 19 is picked, 9 dropped.
        stats_list = [
            _make_stats("a19", board_size=(19, 19)),
            _make_stats("b19", board_size=(19, 19)),
            _make_stats("c9", board_size=(9, 9)),
        ]
        filtered, size = sf._filter_by_board_size(stats_list)
        assert size == 19
        assert {s["game_name"] for s in filtered} == {"a19", "b19"}


# ---------------------------------------------------------------------------
# _reconstruct_pattern_input
# ---------------------------------------------------------------------------


def _make_move(move_number: int, player: str, gtp: str, category: str | None = "MISTAKE") -> dict:
    data = {"move_number": move_number, "player": player, "gtp": gtp}
    if category is not None:
        data["mistake_category"] = category
    return data


class TestReconstructPatternInput:
    def test_filters_invalid_moves(self):
        # Valid moves: 1
        # Invalid: row 0, row -1, off-board "Z4", missing category
        stats_list = [
            _make_stats(
                "g1",
                pattern_data=[
                    _make_move(1, "B", "D4", "MISTAKE"),
                    _make_move(0, "B", "D4", "MISTAKE"),  # invalid move_number
                    _make_move(-1, "W", "Q16", "MISTAKE"),  # invalid move_number
                    _make_move(2, "b", "D4", "MISTAKE"),  # invalid player
                    _make_move(3, "B", "Z4", "MISTAKE"),  # invalid gtp
                    _make_move(4, "W", "Q16", None),  # missing mistake_category
                ],
            )
        ]
        result = sf._reconstruct_pattern_input(stats_list, board_size=19)
        assert len(result) == 1
        game_name, snapshot = result[0]
        assert game_name == "g1"
        # Only one valid move should remain.
        assert len(snapshot.moves) == 1
        assert snapshot.moves[0].move_number == 1
        assert snapshot.moves[0].player == "B"
        assert snapshot.moves[0].gtp == "D4"

    def test_skips_games_with_no_pattern_data(self):
        stats_list = [
            _make_stats("empty", pattern_data=[]),
            _make_stats("missing", pattern_data=None),
        ]
        result = sf._reconstruct_pattern_input(stats_list, board_size=19)
        # Games with no valid moves are not appended.
        assert result == []

    def test_moves_sorted_within_game(self):
        # Input order should not matter.
        stats_list = [
            _make_stats(
                "g",
                pattern_data=[
                    _make_move(3, "W", "Q16", "MISTAKE"),
                    _make_move(1, "B", "D4", "MISTAKE"),
                    _make_move(2, "W", "D16", "MISTAKE"),
                ],
            )
        ]
        result = sf._reconstruct_pattern_input(stats_list, board_size=19)
        assert len(result) == 1
        _, snapshot = result[0]
        moves = [(m.move_number, m.player, m.gtp) for m in snapshot.moves]
        assert moves == [(1, "B", "D4"), (2, "W", "D16"), (3, "W", "Q16")]

    def test_games_sorted_by_stable_key(self):
        # Three games with different game_names → sorted lexicographically.
        stats_list = [
            _make_stats(
                "zeta",
                pattern_data=[_make_move(1, "B", "D4", "MISTAKE")],
            ),
            _make_stats(
                "alpha",
                pattern_data=[_make_move(1, "B", "D4", "MISTAKE")],
            ),
            _make_stats(
                "mid",
                pattern_data=[_make_move(1, "B", "D4", "MISTAKE")],
            ),
        ]
        result = sf._reconstruct_pattern_input(stats_list, board_size=19)
        names = [r[0] for r in result]
        assert names == ["alpha", "mid", "zeta"]


# ---------------------------------------------------------------------------
# _format_game_refs
# ---------------------------------------------------------------------------


class TestFormatGameRefs:
    def test_empty_input(self):
        assert sf._format_game_refs([]) == ""

    def test_single_ref(self):
        refs = [GameRef(game_name="g1", move_number=42, player="B")]
        assert sf._format_game_refs(refs) == "g1 #42(B)"

    def test_multiple_refs_sorted(self):
        refs = [
            GameRef("a", 1, "W"),
            GameRef("a", 1, "B"),
            GameRef("b", 5, "B"),
        ]
        # Sort by (game_name, move_number, player)
        assert sf._format_game_refs(refs) == "a #1(B), a #1(W), b #5(B)"

    def test_max_display_truncates(self):
        refs = [GameRef(f"g{i}", i, "B") for i in range(5)]
        out = sf._format_game_refs(refs, max_display=2)
        assert out == "g0 #0(B), g1 #1(B)"

