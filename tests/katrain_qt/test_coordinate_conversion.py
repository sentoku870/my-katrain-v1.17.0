"""
Tests for coordinate conversion functions in katrain_qt.analysis.models.

These tests verify:
1. internal_to_gtp / gtp_to_internal round-trip for corners and special cases
2. GTP column letters correctly skip 'I' (J is col 8, not 9)
3. coord_to_display produces correct human-readable strings
"""

import pytest

from katrain_qt.analysis.models import (
    internal_to_gtp,
    gtp_to_internal,
    coord_to_display,
    GTP_COLUMNS,
)


class TestGTPColumns:
    """Verify GTP column letter string is correct."""

    def test_gtp_columns_skips_i(self):
        """GTP columns must skip 'I' to avoid confusion with '1'."""
        assert "I" not in GTP_COLUMNS
        assert GTP_COLUMNS == "ABCDEFGHJKLMNOPQRST"

    def test_gtp_columns_length(self):
        """GTP columns should have 19 letters for 19x19 boards."""
        assert len(GTP_COLUMNS) == 19

    def test_column_8_is_j(self):
        """Column index 8 should be 'J' (not 'I')."""
        assert GTP_COLUMNS[8] == "J"

    def test_column_7_is_h(self):
        """Column index 7 should be 'H' (last before skip)."""
        assert GTP_COLUMNS[7] == "H"


class TestInternalToGTP:
    """Test internal_to_gtp conversion."""

    def test_corner_a1_bottom_left(self):
        """Bottom-left corner: Qt row=18 -> GTP A1."""
        # In Qt coords: col=0, row=18 (bottom-left when row=0 is top)
        assert internal_to_gtp(0, 18, 19) == "A1"

    def test_corner_a19_top_left(self):
        """Top-left corner: Qt row=0 -> GTP A19."""
        assert internal_to_gtp(0, 0, 19) == "A19"

    def test_corner_t1_bottom_right(self):
        """Bottom-right corner: Qt (18, 18) -> GTP T1."""
        assert internal_to_gtp(18, 18, 19) == "T1"

    def test_corner_t19_top_right(self):
        """Top-right corner: Qt (18, 0) -> GTP T19."""
        assert internal_to_gtp(18, 0, 19) == "T19"

    def test_tengen_k10(self):
        """Center point (tengen): Qt (9, 9) -> GTP K10."""
        assert internal_to_gtp(9, 9, 19) == "K10"

    def test_d4_common_opening(self):
        """Common opening point D4: Qt (3, 15) -> GTP D4."""
        assert internal_to_gtp(3, 15, 19) == "D4"

    def test_q16_common_opening(self):
        """Common opening point Q16: Qt (15, 3) -> GTP Q16."""
        assert internal_to_gtp(15, 3, 19) == "Q16"

    def test_i_skip_column_8_is_j(self):
        """Column 8 should produce 'J' (I is skipped)."""
        assert internal_to_gtp(8, 9, 19) == "J10"

    def test_i_skip_column_9_is_k(self):
        """Column 9 should produce 'K'."""
        assert internal_to_gtp(9, 9, 19) == "K10"

    def test_invalid_negative_col(self):
        """Negative column should return 'pass'."""
        assert internal_to_gtp(-1, 5, 19) == "pass"

    def test_invalid_negative_row(self):
        """Negative row should return 'pass'."""
        assert internal_to_gtp(5, -1, 19) == "pass"

    def test_invalid_col_too_large(self):
        """Column >= board_size should return 'pass'."""
        assert internal_to_gtp(19, 5, 19) == "pass"

    def test_invalid_row_too_large(self):
        """Row >= board_size should return 'pass'."""
        assert internal_to_gtp(5, 19, 19) == "pass"

    def test_13x13_board(self):
        """Test 13x13 board coordinates."""
        assert internal_to_gtp(0, 0, 13) == "A13"
        assert internal_to_gtp(12, 12, 13) == "N1"
        assert internal_to_gtp(6, 6, 13) == "G7"

    def test_9x9_board(self):
        """Test 9x9 board coordinates."""
        assert internal_to_gtp(0, 0, 9) == "A9"
        assert internal_to_gtp(8, 8, 9) == "J1"
        assert internal_to_gtp(4, 4, 9) == "E5"


class TestGTPToInternal:
    """Test gtp_to_internal conversion."""

    def test_corner_a1(self):
        """GTP A1 -> Qt (0, 18)."""
        assert gtp_to_internal("A1", 19) == (0, 18)

    def test_corner_a19(self):
        """GTP A19 -> Qt (0, 0)."""
        assert gtp_to_internal("A19", 19) == (0, 0)

    def test_corner_t1(self):
        """GTP T1 -> Qt (18, 18)."""
        assert gtp_to_internal("T1", 19) == (18, 18)

    def test_corner_t19(self):
        """GTP T19 -> Qt (18, 0)."""
        assert gtp_to_internal("T19", 19) == (18, 0)

    def test_tengen_k10(self):
        """GTP K10 -> Qt (9, 9)."""
        assert gtp_to_internal("K10", 19) == (9, 9)

    def test_d4(self):
        """GTP D4 -> Qt (3, 15)."""
        assert gtp_to_internal("D4", 19) == (3, 15)

    def test_q16(self):
        """GTP Q16 -> Qt (15, 3)."""
        assert gtp_to_internal("Q16", 19) == (15, 3)

    def test_i_skip_j_is_col_8(self):
        """GTP J10 should map to column 8 (I is skipped)."""
        col, row = gtp_to_internal("J10", 19)
        assert col == 8

    def test_case_insensitive(self):
        """GTP coordinates should be case-insensitive."""
        assert gtp_to_internal("d4", 19) == (3, 15)
        assert gtp_to_internal("D4", 19) == (3, 15)

    def test_pass_string(self):
        """'pass' should return (-1, -1)."""
        assert gtp_to_internal("pass", 19) == (-1, -1)
        assert gtp_to_internal("PASS", 19) == (-1, -1)

    def test_whitespace_stripped(self):
        """Whitespace should be stripped."""
        assert gtp_to_internal("  D4  ", 19) == (3, 15)

    def test_invalid_letter_i(self):
        """Letter 'I' should be invalid (it's skipped)."""
        assert gtp_to_internal("I10", 19) == (-1, -1)

    def test_invalid_empty_string(self):
        """Empty string should return (-1, -1)."""
        assert gtp_to_internal("", 19) == (-1, -1)

    def test_invalid_single_char(self):
        """Single character should return (-1, -1)."""
        assert gtp_to_internal("A", 19) == (-1, -1)

    def test_invalid_number_only(self):
        """Number only should return (-1, -1)."""
        assert gtp_to_internal("10", 19) == (-1, -1)

    def test_invalid_out_of_bounds(self):
        """Out of bounds coordinate should return (-1, -1)."""
        assert gtp_to_internal("A20", 19) == (-1, -1)
        assert gtp_to_internal("U1", 19) == (-1, -1)
        assert gtp_to_internal("A0", 19) == (-1, -1)


class TestRoundTrip:
    """Test round-trip conversion: internal -> gtp -> internal."""

    @pytest.mark.parametrize("col,row", [
        (0, 0),    # A19 top-left
        (0, 18),   # A1 bottom-left
        (18, 0),   # T19 top-right
        (18, 18),  # T1 bottom-right
        (9, 9),    # K10 tengen
        (3, 15),   # D4
        (15, 3),   # Q16
        (8, 9),    # J10 (column after I-skip)
    ])
    def test_round_trip_19x19(self, col, row):
        """Convert to GTP and back should give same coordinates."""
        gtp = internal_to_gtp(col, row, 19)
        back_col, back_row = gtp_to_internal(gtp, 19)
        assert (back_col, back_row) == (col, row), f"Round-trip failed for ({col}, {row}) -> {gtp}"

    def test_round_trip_all_corners_13x13(self):
        """Test all corners on 13x13 board."""
        corners = [(0, 0), (0, 12), (12, 0), (12, 12)]
        for col, row in corners:
            gtp = internal_to_gtp(col, row, 13)
            back_col, back_row = gtp_to_internal(gtp, 13)
            assert (back_col, back_row) == (col, row)

    def test_round_trip_all_corners_9x9(self):
        """Test all corners on 9x9 board."""
        corners = [(0, 0), (0, 8), (8, 0), (8, 8)]
        for col, row in corners:
            gtp = internal_to_gtp(col, row, 9)
            back_col, back_row = gtp_to_internal(gtp, 9)
            assert (back_col, back_row) == (col, row)


class TestCoordToDisplay:
    """Test coord_to_display (alias for internal_to_gtp for display purposes)."""

    def test_basic_conversion(self):
        """Basic conversion matches internal_to_gtp."""
        assert coord_to_display(3, 15, 19) == "D4"
        assert coord_to_display(0, 0, 19) == "A19"
        assert coord_to_display(18, 18, 19) == "T1"

    def test_invalid_returns_question_marks(self):
        """Invalid coordinates return '??'."""
        assert coord_to_display(-1, 5, 19) == "??"
        assert coord_to_display(5, -1, 19) == "??"
        assert coord_to_display(19, 5, 19) == "??"
        assert coord_to_display(5, 19, 19) == "??"

    def test_tengen(self):
        """Center point displays correctly."""
        assert coord_to_display(9, 9, 19) == "K10"
