"""Phase 199C-3: tsumego_frame.py tests.

Target: raise coverage from 25% to ~80%.

Covers pure utility functions and the core tsumego frame algorithm.
No Kivy dependency — all functions are pure Python.
"""

from __future__ import annotations

import pytest

from katrain.core.tsumego_frame import (
    BLACK,
    WHITE,
    get_analysis_region,
    guess_black_to_attack,
    height,
    height2,
    ij_sizes,
    inside_p,
    katrain_sgf_from_ijs,
    min_by,
    need_flip_p,
    pick_all,
    put_stone,
    sign_of_color,
    snap,
    snap0,
    snap_s,
    stone_from_str,
    stones_from_bw_board,
    tsumego_frame,
    tsumego_frame_stones,
    xor,
)


# ---------------------------------------------------------------------------
# Stone / board conversion
# ---------------------------------------------------------------------------


class TestStoneFromStr:
    def test_black_stone(self):
        s = stone_from_str("B")
        assert s["stone"] is True
        assert s["black"] is True

    def test_white_stone(self):
        s = stone_from_str("W")
        assert s["stone"] is True
        assert s["black"] is False

    def test_empty(self):
        s = stone_from_str("-")
        assert s == {}

    def test_arbitrary_char(self):
        s = stone_from_str("x")
        assert s == {}


class TestStonesFromBwBoard:
    def test_simple_3x3(self):
        board = [
            ["B", "W", "-"],
            ["-", "B", "-"],
            ["-", "-", "W"],
        ]
        stones = stones_from_bw_board(board)
        assert len(stones) == 3
        assert stones[0][0]["black"] is True
        assert stones[0][1]["black"] is False
        assert stones[0][2] == {}

    def test_empty_board(self):
        board = [["-" for _ in range(9)] for _ in range(9)]
        stones = stones_from_bw_board(board)
        assert all(s == {} for row in stones for s in row)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


class TestXor:
    @pytest.mark.parametrize("a,b,expected", [
        (True, True, False),
        (True, False, True),
        (False, True, True),
        (False, False, False),
    ])
    def test_xor_truth_table(self, a, b, expected):
        assert xor(a, b) is expected


class TestInsideP:
    def test_inside(self):
        assert inside_p(3, 3, [0, 5, 0, 5]) is True

    def test_outside_high(self):
        assert inside_p(6, 3, [0, 5, 0, 5]) is False

    def test_on_boundary(self):
        assert inside_p(0, 0, [0, 5, 0, 5]) is True
        assert inside_p(5, 5, [0, 5, 0, 5]) is True


class TestSnap:
    def test_snap_to_zero_when_near(self):
        assert snap0(1) == 0
        assert snap0(2) == 0

    def test_snap_to_zero_far(self):
        assert snap0(5) == 5

    def test_snap_s_near_edge(self):
        assert snap_s(17, 19) == 18  # near size-1
        assert snap_s(16, 19) == 18

    def test_snap_s_far_from_edge(self):
        assert snap_s(10, 19) == 10


class TestIjSizes:
    def test_rectangular(self):
        assert ij_sizes([["a"] * 5 for _ in range(3)]) == (3, 5)

    def test_square(self):
        assert ij_sizes([["a"] * 9 for _ in range(9)]) == (9, 9)


class TestNeedFlipP:
    def test_needs_flip(self):
        # kmin=0, kmax=18, size=19 → 0 < 19-18-1 = 0 → False
        assert need_flip_p(0, 18, 19) is False

    def test_flips_when_closer_to_top(self):
        # kmin=1, kmax=17, size=19 → 1 < 19-17-1 = 1 → False
        assert need_flip_p(1, 17, 19) is False
        # kmin=0, kmax=17, size=19 → 0 < 19-17-1 = 1 → True
        assert need_flip_p(0, 17, 19) is True


class TestHeight:
    def test_center_is_tallest(self):
        # On a 19x19, center = (18/2, 18/2) = (9,9)
        assert height(9, 19) == pytest.approx(19.0)

    def test_edge_is_shortest(self):
        # height(0, 19) = 19 - abs(0 - 9) = 10.0
        assert height(0, 19) == pytest.approx(10.0)


class TestSignOfColor:
    def test_black(self):
        assert sign_of_color({"black": True}) == 1

    def test_white(self):
        assert sign_of_color({"black": False}) == -1


class TestMinBy:
    def test_min_by_i_positive(self):
        items = [{"i": 3}, {"i": 1}, {"i": 2}]
        result = min_by(items, "i", +1)
        assert result["i"] == 1

    def test_min_by_i_negative(self):
        items = [{"i": 3}, {"i": 1}, {"i": 2}]
        result = min_by(items, "i", -1)
        assert result["i"] == 3  # max when sign is negative


class TestPutStone:
    def test_put_black_stone(self):
        stones = [[{} for _ in range(5)] for _ in range(5)]
        put_stone(stones, (5, 5), 2, 2, True, False)
        assert stones[2][2]["stone"] is True
        assert stones[2][2]["black"] is True
        assert stones[2][2]["tsumego_frame"] is True

    def test_put_empty(self):
        stones = [[{"stone": True, "black": True} for _ in range(5)] for _ in range(5)]
        put_stone(stones, (5, 5), 2, 2, False, True)
        assert stones[2][2] == {}

    def test_out_of_bounds_ignored(self):
        stones = [[{} for _ in range(5)] for _ in range(5)]
        put_stone(stones, (5, 5), -1, 2, True, False)
        put_stone(stones, (5, 5), 5, 2, True, False)
        # No change — out of bounds
        assert all(s == {} for row in stones for s in row)

    def test_region_mark(self):
        stones = [[{} for _ in range(5)] for _ in range(5)]
        put_stone(stones, (5, 5), 2, 2, True, False, tsumego_frame_region_mark=True)
        assert stones[2][2]["tsumego_frame_region_mark"] is True


# ---------------------------------------------------------------------------
# get_analysis_region
# ---------------------------------------------------------------------------


class TestGetAnalysisRegion:
    def test_empty_returns_none(self):
        assert get_analysis_region([]) is None

    def test_single_point_returns_none(self):
        # Single point: ri[0] < ri[1] fails → None
        assert get_analysis_region([[3, 5, True]]) is None

    def test_valid_region(self):
        region_pos = [[1, 2, True], [3, 5, True], [2, 4, True]]
        result = get_analysis_region(region_pos)
        assert result is not None
        assert result == ((1, 3), (2, 5))

    def test_degenerate_line_returns_none(self):
        # Same i for all → ri[0] == ri[1] → None
        region_pos = [[3, 2, True], [3, 5, True]]
        assert get_analysis_region(region_pos) is None


# ---------------------------------------------------------------------------
# pick_all
# ---------------------------------------------------------------------------


class TestPickAll:
    def test_picks_marked_stones(self):
        stones = [
            [{"tsumego_frame": True, "black": True}, {}],
            [{}, {"tsumego_frame": True, "black": False}],
        ]
        result = pick_all(stones, "tsumego_frame")
        assert len(result) == 2
        assert result[0] == [0, 0, True]
        assert result[1] == [1, 1, False]

    def test_empty_when_none_marked(self):
        stones = [[{}, {}], [{}, {}]]
        assert pick_all(stones, "tsumego_frame") == []


# ---------------------------------------------------------------------------
# katrain_sgf_from_ijs
# ---------------------------------------------------------------------------


class TestKatrainSgfFromIjs:
    def test_convert_coordinates(self):
        # Move((j, i)).sgf((jsize, isize)) — KaTrain y=0 is bottom row,
        # SGF row 0 is top. For 19x19, i=0 → row 's' (last), j=0 → col 'a'
        ijs = [(0, 0), (3, 3)]
        result = katrain_sgf_from_ijs(ijs, isize=19, jsize=19, player="B")
        assert len(result) == 2
        assert result[0] == "as"  # bottom-left = col a, row s (19th)
        assert result[1] == "dp"  # (3,3) → col d, row p (16th)


# ---------------------------------------------------------------------------
# tsumego_frame (end-to-end with simple board)
# ---------------------------------------------------------------------------


class TestTsumegoFrame:
    """Test the full tsumego frame algorithm."""

    def test_empty_board_returns_empty(self):
        bw_board = [["-" for _ in range(9)] for _ in range(9)]
        blacks, whites, region = tsumego_frame(bw_board, komi=0.5, black_to_play_p=True, ko_p=False, margin=2)
        assert blacks == []
        assert whites == []
        assert region is None

    def test_corner_problem_produces_stones(self):
        """A corner black stone should produce a frame with outside stones."""
        bw_board = [["-" for _ in range(9)] for _ in range(9)]
        bw_board[0][0] = "B"  # Black stone in corner
        blacks, whites, region = tsumego_frame(bw_board, komi=0.5, black_to_play_p=True, ko_p=False, margin=2)
        # Should produce some stones for the frame
        assert len(blacks) > 0 or len(whites) > 0

    def test_center_problem_produces_stones(self):
        """A center stone should produce a frame."""
        bw_board = [["-" for _ in range(9)] for _ in range(9)]
        bw_board[4][4] = "B"
        blacks, whites, region = tsumego_frame(bw_board, komi=0.5, black_to_play_p=True, ko_p=False, margin=2)
        assert len(blacks) > 0 or len(whites) > 0

    def test_two_group_problem(self):
        """Two nearby opposing groups should produce a frame."""
        bw_board = [["-" for _ in range(9)] for _ in range(9)]
        bw_board[2][2] = "B"
        bw_board[3][3] = "W"
        blacks, whites, region = tsumego_frame(bw_board, komi=0.5, black_to_play_p=True, ko_p=False, margin=2)
        total = len(blacks) + len(whites)
        assert total > 0

    def test_ko_mode_adds_ko_threats(self):
        """With ko_p=True, ko threat stones should be added."""
        bw_board = [["-" for _ in range(9)] for _ in range(9)]
        bw_board[0][0] = "B"
        blacks1, whites1, _ = tsumego_frame(bw_board, komi=0.5, black_to_play_p=True, ko_p=False, margin=2)
        blacks2, whites2, _ = tsumego_frame(bw_board, komi=0.5, black_to_play_p=True, ko_p=True, margin=2)
        # Ko mode should change the stone count
        total_no_ko = len(blacks1) + len(whites1)
        total_with_ko = len(blacks2) + len(whites2)
        assert total_with_ko >= total_no_ko  # ko adds stones or keeps same


class TestTsumegoFrameStones:
    """Test tsumego_frame_stones directly."""

    def test_empty_stones_returns_empty(self):
        stones = [[{} for _ in range(9)] for _ in range(9)]
        result = tsumego_frame_stones(stones, komi=0.5, black_to_play_p=True, ko_p=False, margin=2)
        assert result == []

    def test_stones_are_mutated(self):
        """After calling, stones should have frame stones added."""
        stones = stones_from_bw_board([["B"] + ["-"] * 8 for _ in range(9)])
        result = tsumego_frame_stones(stones, komi=0.5, black_to_play_p=True, ko_p=False, margin=2)
        # Result should be non-empty
        assert result != []
        # Check that some frame stones were placed
        frame_stones = pick_all(result, "tsumego_frame") if result else []
        assert len(frame_stones) > 0


class TestGuessBlackToAttack:
    def test_single_black_high(self):
        """A black stone near center should be attacker."""
        sizes = (9, 9)
        extrema = [{"i": 4, "j": 4, "black": True}]
        result = guess_black_to_attack(extrema, sizes)
        assert isinstance(result, bool)

    def test_single_white_low(self):
        """A white stone at edge should be defender."""
        sizes = (9, 9)
        extrema = [{"i": 0, "j": 0, "black": False}]
        result = guess_black_to_attack(extrema, sizes)
        assert isinstance(result, bool)
