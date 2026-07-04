"""Phase 174 P1-E: coverage uplift for katrain.core.utils.

Architecture review (Phase 173) flagged ``core/game_node.py`` at 41%
coverage. The largest uncovered block is ``analysis_dumps`` which uses
``pack_floats`` / ``unpack_floats`` from ``katrain.core.utils``. These
two pure helpers had no direct test coverage.

This file adds 8 focused cases for pack/unpack symmetry, None/empty
handling, and a round-trip check.
"""

from __future__ import annotations

import math

import pytest

from katrain.core.utils import pack_floats, unpack_floats


class TestPackFloats:
    """``pack_floats`` packs a list of floats into little-endian half-float bytes."""

    def test_none_returns_empty_bytes(self):
        assert pack_floats(None) == b""

    def test_empty_list_returns_empty_bytes(self):
        assert pack_floats([]) == b""

    def test_single_float(self):
        packed = pack_floats([1.5])
        assert len(packed) == 2  # half-precision float = 2 bytes
        assert unpack_floats(packed, 1) == pytest.approx((1.5,), rel=1e-2)

    def test_multiple_floats(self):
        values = [1.0, 2.0, 3.0, 4.5]
        packed = pack_floats(values)
        # 4 floats × 2 bytes = 8 bytes
        assert len(packed) == 8
        unpacked = unpack_floats(packed, len(values))
        assert unpacked is not None
        # half-precision has ~3 decimal digits; allow rel=1e-2 tolerance.
        for actual, expected in zip(unpacked, values, strict=True):
            assert actual == pytest.approx(expected, rel=1e-2)

    def test_zero_value(self):
        packed = pack_floats([0.0, -0.0])
        # 0.0 round-trips exactly.
        assert unpack_floats(packed, 2) == pytest.approx((0.0, -0.0), abs=1e-9)

    def test_negative_values(self):
        # half-precision ('e' format) covers ~±65504; stay within range.
        values = [-1.5, -100.25, -1000.0]
        packed = pack_floats(values)
        unpacked = unpack_floats(packed, len(values))
        for actual, expected in zip(unpacked, values, strict=True):
            assert actual == pytest.approx(expected, rel=1e-2)

    def test_overflow_raises(self):
        # Values beyond half-precision's range raise OverflowError.
        # Documenting this contract so future refactors notice.
        with pytest.raises(OverflowError):
            pack_floats([1e9])


class TestUnpackFloats:
    def test_empty_data_returns_none(self):
        assert unpack_floats(b"", 5) is None

    def test_unpack_count_must_match_bytes(self):
        packed = pack_floats([1.0, 2.0])
        # 4 bytes but we ask for 10 → struct.error (caller bug, but it does raise).
        with pytest.raises(Exception):
            unpack_floats(packed, 10)


class TestPackUnpackRoundTrip:
    @pytest.mark.parametrize("n", [1, 4, 9, 16, 25, 81])
    def test_various_sizes_round_trip(self, n):
        values = [float(i) * 0.5 for i in range(n)]
        packed = pack_floats(values)
        assert len(packed) == 2 * n
        unpacked = unpack_floats(packed, n)
        assert unpacked is not None
        for actual, expected in zip(unpacked, values, strict=True):
            assert actual == pytest.approx(expected, rel=1e-2)

    def test_specific_ownership_values(self):
        """Real-world: ownership grid is typically 81 floats (-1..+1)."""
        values = [math.sin(i / 4.0) for i in range(81)]
        packed = pack_floats(values)
        unpacked = unpack_floats(packed, 81)
        assert unpacked is not None
        for actual, expected in zip(unpacked, values, strict=True):
            assert actual == pytest.approx(expected, rel=1e-2)
