"""Unit tests for ``katrain.gui.features.summary_pattern`` (Phase 282-P1B).

Pattern-mining input helpers were extracted from ``summary_formatter``
into a dedicated module but had no direct tests. The existing
``test_pattern_summary_contract.py`` exercises ``summary_formatter``
re-exports; this file covers the validators and aggregators in the
underlying module.

The functions tested here are pure (no Kivy, no I/O), so they can run
under standard pytest without headless-mode configuration.

Coverage targets:
- ``_normalize_board_size``: tuple/list/int/None shapes
- ``_is_valid_player``: 'B' / 'W' only
- ``_is_valid_gtp``: GTP convention with 'I' skip, board-size bounds
- ``_is_valid_move_number``: positive int
- ``_stable_sort_key``: 4-tuple composite key
- ``_filter_by_board_size``: dominant size selection + invalid filtering
- ``_format_game_refs``: deterministic ordering
- ``_PatternMoveEval``: invalid mistake_category handling
"""

from __future__ import annotations

import pytest

from katrain.gui.features.summary_pattern import (
    _filter_by_board_size,
    _format_game_refs,
    _is_valid_gtp,
    _is_valid_move_number,
    _is_valid_player,
    _normalize_board_size,
    _PatternMoveEval,
    _stable_sort_key,
)

# =============================================================================
# _normalize_board_size
# =============================================================================


class TestNormalizeBoardSize:
    def test_none_returns_none(self):
        assert _normalize_board_size(None) is None

    def test_valid_tuple(self):
        assert _normalize_board_size((19, 19)) == (19, 19)

    def test_valid_list(self):
        assert _normalize_board_size([9, 9]) == (9, 9)

    def test_int_returns_none(self):
        assert _normalize_board_size(19) is None

    def test_string_returns_none(self):
        assert _normalize_board_size("19x19") is None

    def test_too_short_tuple_returns_none(self):
        assert _normalize_board_size((19,)) is None

    def test_non_numeric_returns_none(self):
        assert _normalize_board_size(("x", "y")) is None

    def test_coerces_to_int(self):
        """Float values are accepted and truncated."""
        assert _normalize_board_size((19.5, 19.0)) == (19, 19)


# =============================================================================
# _is_valid_player
# =============================================================================


class TestIsValidPlayer:
    @pytest.mark.parametrize("p", ["B", "W"])
    def test_accepts_b_and_w(self, p):
        assert _is_valid_player(p) is True

    @pytest.mark.parametrize("p", ["b", "w", "X", "", None, 1])
    def test_rejects_others(self, p):
        assert _is_valid_player(p) is False


# =============================================================================
# _is_valid_gtp
# =============================================================================


class TestIsValidGtp:
    def test_uppercase_accepts(self):
        assert _is_valid_gtp("D4") is True

    def test_lowercase_accepts(self):
        assert _is_valid_gtp("d4") is True

    def test_skips_i_column(self):
        """GTP convention: 'I' is skipped between H and J."""
        assert _is_valid_gtp("H4") is True
        assert _is_valid_gtp("J4") is True
        # 'I4' would be column index 8 (skipping I), 19x19 board has 19 columns (a-t excluding i)
        assert _is_valid_gtp("I4", board_size=19) is False  # 'I' is not a valid column letter

    def test_pass_rejected(self):
        assert _is_valid_gtp("pass") is False

    def test_resign_rejected(self):
        assert _is_valid_gtp("resign") is False

    def test_empty_rejected(self):
        assert _is_valid_gtp("") is False
        assert _is_valid_gtp(None) is False

    def test_non_string_rejected(self):
        assert _is_valid_gtp(123) is False  # type: ignore[arg-type]

    def test_off_board_rejected(self):
        """Coordinates outside the board are rejected."""
        assert _is_valid_gtp("a99", board_size=19) is False
        # 't' = column 18 (0-indexed, skipping 'i' at index 8 -> 'j' is index 8)
        # On 19x19, valid columns are a-h, j-t (18 columns)
        assert _is_valid_gtp("z1", board_size=19) is False

    def test_9x9_board_size(self):
        """A coordinate valid on 19x19 but not on 9x9."""
        assert _is_valid_gtp("d4", board_size=9) is True
        # 'j4' is column 8 (after skipping 'i'). On 9x9, valid columns are a-i (9 columns, index 0-8)
        # Wait: 'i' is skipped so 'j' is index 8 -> still valid on 9x9
        assert _is_valid_gtp("j4", board_size=9) is True
        # 'k4' is column 9 -> out of bounds for 9x9
        assert _is_valid_gtp("k4", board_size=9) is False


# =============================================================================
# _is_valid_move_number
# =============================================================================


class TestIsValidMoveNumber:
    @pytest.mark.parametrize("n", [1, 5, 100, 1000])
    def test_positive_int_accepted(self, n):
        assert _is_valid_move_number(n) is True

    @pytest.mark.parametrize("n", [0, -1, -100])
    def test_non_positive_rejected(self, n):
        assert _is_valid_move_number(n) is False

    @pytest.mark.parametrize("n", ["1", 1.0, None, [1]])
    def test_wrong_type_rejected(self, n):
        assert _is_valid_move_number(n) is False


# =============================================================================
# _stable_sort_key
# =============================================================================


class TestStableSortKey:
    def test_4_tuple(self):
        stats = {"game_name": "g1", "date": "2026-07-21", "total_moves": 50, "source_index": 3}
        assert _stable_sort_key(stats) == ("g1", "2026-07-21", 50, 3)

    def test_missing_keys_become_defaults(self):
        assert _stable_sort_key({}) == ("", "", 0, 0)

    def test_none_date_becomes_empty_string(self):
        """None or missing date is normalized to empty string (not 'None')."""
        stats = {"game_name": "g1", "date": None, "total_moves": 10, "source_index": 0}
        assert _stable_sort_key(stats)[1] == ""


# =============================================================================
# _filter_by_board_size
# =============================================================================


class TestFilterByBoardSize:
    def test_single_size_passes_through(self):
        stats = [
            {"game_name": "g1", "board_size": (19, 19)},
            {"game_name": "g2", "board_size": [19, 19]},
        ]
        filtered, dominant = _filter_by_board_size(stats)
        assert dominant == 19
        assert {s["game_name"] for s in filtered} == {"g1", "g2"}

    def test_mixed_sizes_filters_to_dominant(self):
        stats = [
            {"game_name": "g1", "board_size": (19, 19)},
            {"game_name": "g2", "board_size": (19, 19)},
            {"game_name": "g3", "board_size": (9, 9)},
        ]
        filtered, dominant = _filter_by_board_size(stats)
        assert dominant == 19
        assert {s["game_name"] for s in filtered} == {"g1", "g2"}

    def test_non_square_filtered_out(self):
        stats = [
            {"game_name": "g1", "board_size": (19, 19)},
            {"game_name": "g2", "board_size": (19, 18)},
        ]
        filtered, dominant = _filter_by_board_size(stats)
        assert dominant == 19
        assert {s["game_name"] for s in filtered} == {"g1"}

    def test_invalid_board_size_filtered_out(self):
        stats = [
            {"game_name": "g1", "board_size": (19, 19)},
            {"game_name": "g2"},  # missing board_size
            {"game_name": "g3", "board_size": None},
        ]
        filtered, dominant = _filter_by_board_size(stats)
        assert dominant == 19
        assert {s["game_name"] for s in filtered} == {"g1"}

    def test_all_invalid_returns_none_size(self):
        stats = [
            {"game_name": "g1"},
            {"game_name": "g2", "board_size": None},
        ]
        filtered, dominant = _filter_by_board_size(stats)
        assert filtered == []
        assert dominant is None

    def test_empty_input(self):
        assert _filter_by_board_size([]) == ([], None)


# =============================================================================
# _format_game_refs
# =============================================================================


class TestFormatGameRefs:
    def _ref(self, game_name: str, move_number: int, player: str):
        from katrain.core.batch.stats.pattern_miner import GameRef

        return GameRef(game_name=game_name, move_number=move_number, player=player)

    def test_empty(self):
        assert _format_game_refs([]) == ""

    def test_single_ref(self):
        ref = self._ref("g1", 10, "B")
        assert _format_game_refs([ref]) == "g1 #10(B)"

    def test_multiple_refs_sorted(self):
        refs = [
            self._ref("g2", 5, "W"),
            self._ref("g1", 10, "B"),
            self._ref("g1", 5, "B"),
        ]
        # Sorted by (game_name, move_number, player)
        result = _format_game_refs(refs, max_display=10)
        assert result == "g1 #5(B), g1 #10(B), g2 #5(W)"

    def test_max_display_truncates(self):
        refs = [self._ref(f"g{i}", i, "B") for i in range(5)]
        result = _format_game_refs(refs, max_display=3)
        assert result == "g0 #0(B), g1 #1(B), g2 #2(B)"


# =============================================================================
# _PatternMoveEval
# =============================================================================


class TestPatternMoveEval:
    def test_basic_construction(self):
        data = {
            "move_number": 5,
            "player": "B",
            "gtp": "D4",
            "score_loss": 1.5,
            "points_lost": 1.5,
            "meaning_tag_id": "overplay",
            "mistake_category": "MISTAKE",
        }
        move = _PatternMoveEval(data)
        assert move.move_number == 5
        assert move.player == "B"
        assert move.gtp == "D4"
        assert move.score_loss == 1.5
        assert move.points_lost == 1.5
        assert move.meaning_tag_id == "overplay"
        from katrain.core.analysis.models.enums import MistakeCategory

        assert move.mistake_category == MistakeCategory.MISTAKE

    def test_missing_keys_default(self):
        move = _PatternMoveEval({})
        assert move.move_number == 0
        assert move.player is None
        assert move.gtp is None
        assert move.mistake_category is None

    def test_invalid_mistake_category_set_to_none(self):
        """Bad enum value -> None (warning logged, not raised)."""
        data = {"move_number": 1, "mistake_category": "NOT_A_REAL_CATEGORY"}
        move = _PatternMoveEval(data)
        assert move.mistake_category is None

    def test_no_mistake_category(self):
        move = _PatternMoveEval({"move_number": 1})
        assert move.mistake_category is None
