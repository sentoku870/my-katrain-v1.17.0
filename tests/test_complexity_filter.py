# -*- coding: utf-8 -*-
"""Unit tests for Phase 83 Complexity filter.

All tests are CI-friendly (no real engine, no file I/O).
"""
import pytest

from katrain.core.analysis.critical_moves import (
    THRESHOLD_SCORE_STDEV_CHAOS,
    COMPLEXITY_DISCOUNT_FACTOR,
    _compute_complexity_discount,
    ComplexityFilterStats,
)


class TestComputeComplexityDiscount:
    """Tests for _compute_complexity_discount() boundary behavior."""

    def test_none_stdev_returns_no_discount(self):
        """None scoreStdev (Leela/unanalyzed) returns 1.0."""
        assert _compute_complexity_discount(None) == 1.0

    def test_zero_stdev_returns_no_discount(self):
        """Zero stdev (rare but valid) returns 1.0."""
        assert _compute_complexity_discount(0.0) == 1.0

    def test_low_stdev_returns_no_discount(self):
        """Low stdev (< threshold) returns 1.0."""
        assert _compute_complexity_discount(5.0) == 1.0
        assert _compute_complexity_discount(19.99) == 1.0

    def test_exactly_at_threshold_returns_no_discount(self):
        """Exactly at threshold (==20.0) returns 1.0 (boundary: > not >=)."""
        assert _compute_complexity_discount(20.0) == 1.0
        assert _compute_complexity_discount(THRESHOLD_SCORE_STDEV_CHAOS) == 1.0

    def test_above_threshold_returns_discount(self):
        """Above threshold (>20.0) returns discount factor."""
        assert _compute_complexity_discount(20.01) == COMPLEXITY_DISCOUNT_FACTOR
        assert _compute_complexity_discount(20.1) == COMPLEXITY_DISCOUNT_FACTOR
        assert _compute_complexity_discount(50.0) == COMPLEXITY_DISCOUNT_FACTOR

    def test_discount_factor_in_valid_range(self):
        """Verify discount factor is in valid range (0, 1)."""
        assert 0.0 < COMPLEXITY_DISCOUNT_FACTOR < 1.0

    def test_threshold_value(self):
        """Verify threshold is 20.0 as specified."""
        assert THRESHOLD_SCORE_STDEV_CHAOS == 20.0


class TestComplexityFilterStats:
    """Tests for ComplexityFilterStats dataclass."""

    def test_discount_rate_zero_candidates_no_division_error(self):
        """Zero candidates returns 0.0 rate (no ZeroDivisionError)."""
        stats = ComplexityFilterStats(total_candidates=0, discounted_count=0)
        assert stats.discount_rate == 0.0

    def test_discount_rate_calculation(self):
        """Discount rate calculated correctly."""
        stats = ComplexityFilterStats(total_candidates=10, discounted_count=3)
        assert stats.discount_rate == 30.0

    def test_discount_rate_100_percent(self):
        """100% discount rate."""
        stats = ComplexityFilterStats(total_candidates=5, discounted_count=5)
        assert stats.discount_rate == 100.0

    def test_max_stdev_default_is_none(self):
        """max_stdev defaults to None (not 0.0)."""
        stats = ComplexityFilterStats()
        assert stats.max_stdev_seen is None

    def test_default_values(self):
        """Default values are all zero/None."""
        stats = ComplexityFilterStats()
        assert stats.total_candidates == 0
        assert stats.discounted_count == 0
        assert stats.max_stdev_seen is None
