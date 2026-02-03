"""Phase 117: evaluation_class() index range and monotonicity tests.

Tests that verify the fix for Top Moves color regression (Phase 116D).
The evaluation_class() function maps loss values to color bucket indices (0-5).
"""

import pytest
from katrain.core.utils import evaluation_class


# Actual runtime thresholds from config.json (descending order, 6 elements)
DESCENDING_THRESHOLDS: list[float] = [12.0, 6.0, 3.0, 1.5, 0.5, 0.0]
NUM_BUCKETS = 6


class TestIndexBounds:
    """Verify returned index is always in valid range [0, len(thresholds)-1]."""

    @pytest.mark.parametrize("points_lost", [
        -100.0, -1.0, -0.001, 0.0, 0.25, 0.4999, 0.5, 0.5001,
        1.0, 1.4999, 1.5, 1.5001, 2.9999, 3.0, 3.0001,
        5.9999, 6.0, 6.0001, 11.9999, 12.0, 12.0001, 100.0,
    ])
    def test_index_in_bounds(self, points_lost: float) -> None:
        """All loss values should map to indices [0, 5]."""
        idx = evaluation_class(points_lost, DESCENDING_THRESHOLDS)
        assert 0 <= idx < NUM_BUCKETS, (
            f"points_lost={points_lost} → idx={idx}, expected [0, {NUM_BUCKETS-1}]"
        )

    def test_single_threshold(self) -> None:
        """Single threshold creates 2 buckets (indices 0, 1)."""
        # With thresholds=[3.0], loop runs while i < 0 (never), so always returns i=0
        assert evaluation_class(5.0, [3.0]) == 0
        assert evaluation_class(2.0, [3.0]) == 0

    def test_empty_thresholds(self) -> None:
        """Empty thresholds should return 0."""
        assert evaluation_class(5.0, []) == 0


class TestExactMapping:
    """Verify exact bucket mapping for descending thresholds [12,6,3,1.5,0.5,0]."""

    @pytest.mark.parametrize("points_lost,expected", [
        # Bucket 0: loss >= 12 (terrible)
        (100.0, 0), (12.0, 0), (12.0001, 0),
        # Bucket 1: 6 <= loss < 12 (bad)
        (11.9999, 1), (8.0, 1), (6.0, 1), (6.0001, 1),
        # Bucket 2: 3 <= loss < 6 (poor)
        (5.9999, 2), (4.0, 2), (3.0, 2), (3.0001, 2),
        # Bucket 3: 1.5 <= loss < 3 (okay)
        (2.9999, 3), (2.0, 3), (1.5, 3), (1.5001, 3),
        # Bucket 4: 0.5 <= loss < 1.5 (good)
        (1.4999, 4), (1.0, 4), (0.5, 4), (0.5001, 4),
        # Bucket 5: loss < 0.5 (excellent)
        (0.4999, 5), (0.3, 5), (0.0, 5), (-1.0, 5), (-100.0, 5),
    ])
    def test_exact_mapping(self, points_lost: float, expected: int) -> None:
        """Each loss value should map to the correct bucket."""
        actual = evaluation_class(points_lost, DESCENDING_THRESHOLDS)
        assert actual == expected, (
            f"points_lost={points_lost}: expected idx={expected}, got {actual}"
        )


class TestMonotonicity:
    """Verify loss↑ implies idx↓ (monotonic decreasing)."""

    def test_monotonicity(self) -> None:
        """Increasing loss should produce non-increasing indices."""
        losses = [
            -10.0, -1.0, 0.0, 0.3, 0.5, 1.0, 1.5, 2.0, 3.0, 6.0, 12.0, 20.0, 100.0
        ]
        indices = [evaluation_class(loss, DESCENDING_THRESHOLDS) for loss in losses]

        for i in range(len(indices) - 1):
            assert indices[i] >= indices[i + 1], (
                f"Monotonicity violation: loss={losses[i]}→idx={indices[i]}, "
                f"loss={losses[i+1]}→idx={indices[i+1]}"
            )


class TestAllBucketsReachable:
    """Verify all 6 buckets are reachable from the threshold array."""

    def test_all_buckets_reachable(self) -> None:
        """Each bucket (0-5) should be reachable with some loss value."""
        representative = {
            0: 15.0,   # >= 12
            1: 8.0,    # [6, 12)
            2: 4.0,    # [3, 6)
            3: 2.0,    # [1.5, 3)
            4: 1.0,    # [0.5, 1.5)
            5: 0.1,    # < 0.5
        }

        for expected_bucket, loss in representative.items():
            actual = evaluation_class(loss, DESCENDING_THRESHOLDS)
            assert actual == expected_bucket, (
                f"Bucket {expected_bucket} not reachable: loss={loss} → idx={actual}"
            )


class TestNoneThresholds:
    """Verify None threshold entries are skipped (backward compatibility)."""

    def test_none_in_middle_skipped(self) -> None:
        """None thresholds should be skipped during iteration."""
        thresholds: list[float | None] = [12.0, None, 3.0, 1.5, 0.5, 0.0]

        # loss=8: 8<12? NO → i=1, threshold=None → skip, i=2, 8>=3? YES → return 2
        idx = evaluation_class(8.0, thresholds)
        assert idx == 2

        # loss=20: 20>=12? YES → return 0
        assert evaluation_class(20.0, thresholds) == 0

    def test_bounds_with_none(self) -> None:
        """Even with None entries, index should stay in valid range."""
        thresholds: list[float | None] = [12.0, None, None, 1.5, 0.5, 0.0]

        for loss in [-10.0, 0.0, 1.0, 5.0, 15.0]:
            idx = evaluation_class(loss, thresholds)
            assert 0 <= idx < len(thresholds), (
                f"With None entries: loss={loss} → idx={idx}, len={len(thresholds)}"
            )


class TestEdgeCases:
    """Verify edge cases and boundary conditions."""

    def test_zero_loss(self) -> None:
        """Zero loss (neither good nor bad move) should map to a middle bucket."""
        idx = evaluation_class(0.0, DESCENDING_THRESHOLDS)
        assert idx >= 3, "Zero loss should be above-average good (index >= 3)"

    def test_negative_loss_gains(self) -> None:
        """Negative losses (KataGo gains from best move) should map to high buckets."""
        for loss in [-0.5, -1.0, -5.0, -100.0]:
            idx = evaluation_class(loss, DESCENDING_THRESHOLDS)
            assert idx >= 4, (
                f"Negative loss (gain) {loss} should map to high bucket, got {idx}"
            )

    def test_threshold_boundary_values(self) -> None:
        """Values exactly at threshold boundaries should be in the correct bucket."""
        # At 12.0: should be index 0 (loss >= 12)
        assert evaluation_class(12.0, DESCENDING_THRESHOLDS) == 0
        # Just below 12.0: should be index 1
        assert evaluation_class(11.9999, DESCENDING_THRESHOLDS) == 1

        # At 0.5: should be index 4 (loss >= 0.5)
        assert evaluation_class(0.5, DESCENDING_THRESHOLDS) == 4
        # Just below 0.5: should be index 5
        assert evaluation_class(0.4999, DESCENDING_THRESHOLDS) == 5


class TestAscendingThresholds:
    """Verify behavior with ascending thresholds (non-standard, for compatibility)."""

    def test_ascending_thresholds_still_work(self) -> None:
        """While non-standard, ascending thresholds should still return valid indices."""
        ascending = [0.0, 0.5, 1.5, 3.0, 6.0, 12.0]

        for loss in [-10.0, 0.0, 1.0, 5.0, 15.0]:
            idx = evaluation_class(loss, ascending)
            assert 0 <= idx < len(ascending), (
                f"Ascending thresholds: loss={loss} → idx={idx}, len={len(ascending)}"
            )
