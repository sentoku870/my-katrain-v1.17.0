"""Tests for Leela estimated loss calculation logic."""

import pytest

from katrain.core.leela.models import LeelaCandidate, LeelaPositionEval
from katrain.core.leela.logic import (
    LEELA_K_DEFAULT,
    LEELA_K_MIN,
    LEELA_K_MAX,
    LEELA_LOSS_EST_MAX,
    clamp_k,
    compute_estimated_loss,
    format_loss_est,
    compute_loss_color_ratio,
)


class TestClampK:
    """Tests for K value clamping."""

    def test_normal_values(self):
        """Test normal K values within range."""
        assert clamp_k(0.5) == 0.5
        assert clamp_k(1.0) == 1.0
        assert clamp_k(0.2) == 0.2

    def test_low_values(self):
        """Test K values below minimum."""
        assert clamp_k(0.05) == LEELA_K_MIN
        assert clamp_k(0.0) == LEELA_K_MIN
        assert clamp_k(-1.0) == LEELA_K_MIN

    def test_high_values(self):
        """Test K values above maximum."""
        assert clamp_k(3.0) == LEELA_K_MAX
        assert clamp_k(2.5) == LEELA_K_MAX
        assert clamp_k(100.0) == LEELA_K_MAX

    def test_boundary_values(self):
        """Test K values at boundaries."""
        assert clamp_k(LEELA_K_MIN) == LEELA_K_MIN
        assert clamp_k(LEELA_K_MAX) == LEELA_K_MAX


class TestComputeEstimatedLoss:
    """Tests for estimated loss computation."""

    def test_basic_calculation(self):
        """Test basic loss calculation with 3 candidates."""
        candidates = [
            LeelaCandidate(move="D4", winrate=0.52, visits=200),  # Best
            LeelaCandidate(move="C4", winrate=0.50, visits=100),  # 2% worse
            LeelaCandidate(move="E4", winrate=0.42, visits=50),  # 10% worse
        ]
        position = LeelaPositionEval(candidates=candidates)

        result = compute_estimated_loss(position, k=0.5)

        assert result.is_valid
        assert len(result.candidates) == 3

        # Find candidates by move
        d4 = next(c for c in result.candidates if c.move == "D4")
        c4 = next(c for c in result.candidates if c.move == "C4")
        e4 = next(c for c in result.candidates if c.move == "E4")

        # Best candidate: loss = 0
        assert d4.loss_est == 0.0

        # 2% worse: loss = 2 * 0.5 = 1.0
        assert c4.loss_est == 1.0

        # 10% worse: loss = 10 * 0.5 = 5.0
        assert e4.loss_est == 5.0

    def test_single_candidate(self):
        """Test with single candidate (loss should be 0)."""
        candidates = [LeelaCandidate(move="D4", winrate=0.5, visits=100)]
        position = LeelaPositionEval(candidates=candidates)

        result = compute_estimated_loss(position)

        assert result.is_valid
        assert len(result.candidates) == 1
        assert result.candidates[0].loss_est == 0.0

    def test_empty_candidates(self):
        """Test with empty candidates list."""
        position = LeelaPositionEval(candidates=[])

        result = compute_estimated_loss(position)

        assert not result.is_valid
        assert result.parse_error is not None

    def test_k_scaling(self):
        """Test different K values affect loss proportionally."""
        candidates = [
            LeelaCandidate(move="D4", winrate=0.60, visits=100),  # Best
            LeelaCandidate(move="C4", winrate=0.50, visits=100),  # 10% worse
        ]
        position = LeelaPositionEval(candidates=candidates)

        # K = 0.5: loss = 10 * 0.5 = 5.0
        result_05 = compute_estimated_loss(position, k=0.5)
        c4_05 = next(c for c in result_05.candidates if c.move == "C4")
        assert c4_05.loss_est == 5.0

        # K = 1.0: loss = 10 * 1.0 = 10.0
        result_10 = compute_estimated_loss(position, k=1.0)
        c4_10 = next(c for c in result_10.candidates if c.move == "C4")
        assert c4_10.loss_est == 10.0

        # K = 0.2: loss = 10 * 0.2 = 2.0
        result_02 = compute_estimated_loss(position, k=0.2)
        c4_02 = next(c for c in result_02.candidates if c.move == "C4")
        assert c4_02.loss_est == 2.0

    def test_k_clamped_low(self):
        """Test that low K values are clamped."""
        candidates = [
            LeelaCandidate(move="D4", winrate=0.60, visits=100),
            LeelaCandidate(move="C4", winrate=0.50, visits=100),  # 10% worse
        ]
        position = LeelaPositionEval(candidates=candidates)

        # K = 0.05 should be clamped to 0.1
        result = compute_estimated_loss(position, k=0.05)
        c4 = next(c for c in result.candidates if c.move == "C4")
        # loss = 10 * 0.1 = 1.0
        assert c4.loss_est == 1.0

    def test_k_clamped_high(self):
        """Test that high K values are clamped."""
        candidates = [
            LeelaCandidate(move="D4", winrate=0.60, visits=100),
            LeelaCandidate(move="C4", winrate=0.50, visits=100),  # 10% worse
        ]
        position = LeelaPositionEval(candidates=candidates)

        # K = 3.0 should be clamped to 2.0
        result = compute_estimated_loss(position, k=3.0)
        c4 = next(c for c in result.candidates if c.move == "C4")
        # loss = 10 * 2.0 = 20.0
        assert c4.loss_est == 20.0

    def test_loss_clamped_at_max(self):
        """Test that loss_est is clamped at LEELA_LOSS_EST_MAX."""
        candidates = [
            LeelaCandidate(move="D4", winrate=1.0, visits=100),  # 100%
            LeelaCandidate(move="C4", winrate=0.0, visits=100),  # 0% (100% diff)
        ]
        position = LeelaPositionEval(candidates=candidates)

        # K = 2.0: loss = 100 * 2.0 = 200, but clamped to 50.0
        result = compute_estimated_loss(position, k=2.0)
        c4 = next(c for c in result.candidates if c.move == "C4")
        assert c4.loss_est == LEELA_LOSS_EST_MAX  # 50.0

    def test_small_loss_rounded_to_zero(self):
        """Test that very small losses are rounded to 0."""
        candidates = [
            LeelaCandidate(move="D4", winrate=0.5000, visits=100),
            LeelaCandidate(move="C4", winrate=0.4999, visits=100),  # 0.01% diff
        ]
        position = LeelaPositionEval(candidates=candidates)

        # loss = 0.01 * 0.5 = 0.005, which is < 0.05, should round to 0.0
        result = compute_estimated_loss(position, k=0.5)
        c4 = next(c for c in result.candidates if c.move == "C4")
        assert c4.loss_est == 0.0

    def test_visits_zero_excluded(self):
        """Test that candidates with visits=0 are excluded."""
        candidates = [
            LeelaCandidate(move="D4", winrate=0.60, visits=100),
            LeelaCandidate(move="C4", winrate=0.50, visits=0),  # Will be excluded
        ]
        position = LeelaPositionEval(candidates=candidates)

        result = compute_estimated_loss(position)

        assert result.is_valid
        assert len(result.candidates) == 1
        assert result.candidates[0].move == "D4"

    def test_original_position_unchanged(self):
        """Test that original position is not modified (immutability)."""
        candidates = [
            LeelaCandidate(move="D4", winrate=0.60, visits=100),
            LeelaCandidate(move="C4", winrate=0.50, visits=100),
        ]
        position = LeelaPositionEval(candidates=candidates)

        # Store original loss_est (should be None)
        original_loss_d4 = position.candidates[0].loss_est
        original_loss_c4 = position.candidates[1].loss_est

        # Compute estimated loss
        result = compute_estimated_loss(position)

        # Original should be unchanged
        assert position.candidates[0].loss_est == original_loss_d4
        assert position.candidates[1].loss_est == original_loss_c4
        assert position.candidates[0].loss_est is None
        assert position.candidates[1].loss_est is None

        # Result should have computed values
        assert result.candidates[0].loss_est is not None
        assert result.candidates[1].loss_est is not None

    def test_pv_copied(self):
        """Test that PV list is copied, not shared."""
        pv_original = ["D4", "C16", "Q4"]
        candidates = [
            LeelaCandidate(move="D4", winrate=0.5, visits=100, pv=pv_original)
        ]
        position = LeelaPositionEval(candidates=candidates)

        result = compute_estimated_loss(position)

        # Modify original PV
        pv_original.append("Q16")

        # Result PV should not be affected
        assert len(result.candidates[0].pv) == 3
        assert result.candidates[0].pv == ["D4", "C16", "Q4"]


class TestFormatLossEst:
    """Tests for loss display formatting."""

    def test_none(self):
        """Test None value."""
        assert format_loss_est(None) == "--"

    def test_zero(self):
        """Test zero value."""
        assert format_loss_est(0.0) == "0.0"

    def test_normal_values(self):
        """Test normal loss values."""
        assert format_loss_est(2.3) == "2.3"
        assert format_loss_est(5.0) == "5.0"
        assert format_loss_est(10.5) == "10.5"

    def test_rounding(self):
        """Test decimal rounding."""
        assert format_loss_est(2.34) == "2.3"
        assert format_loss_est(2.35) == "2.4"  # Round half up
        assert format_loss_est(2.999) == "3.0"


class TestComputeLossColorRatio:
    """Tests for color ratio calculation."""

    def test_zero_loss(self):
        """Test zero loss gives 0.0 ratio."""
        assert compute_loss_color_ratio(0.0) == 0.0

    def test_threshold_loss(self):
        """Test threshold loss gives 1.0 ratio."""
        assert compute_loss_color_ratio(5.0, threshold_large=5.0) == 1.0

    def test_half_threshold(self):
        """Test half threshold gives 0.5 ratio."""
        assert compute_loss_color_ratio(2.5, threshold_large=5.0) == 0.5

    def test_clamped_at_one(self):
        """Test that ratio is clamped at 1.0."""
        assert compute_loss_color_ratio(10.0, threshold_large=5.0) == 1.0
        assert compute_loss_color_ratio(50.0, threshold_large=5.0) == 1.0

    def test_negative_treated_as_zero(self):
        """Test that negative values give 0.0 ratio."""
        assert compute_loss_color_ratio(-1.0) == 0.0


class TestIntegration:
    """Integration tests for loss calculation pipeline."""

    def test_parse_to_loss_pipeline(self):
        """Test full pipeline from parsed data to loss calculation."""
        from katrain.core.leela.parser import parse_lz_analyze

        sample = (
            "info move R14 visits 59871 winrate 4997 order 0 pv R14 R5 "
            "info move R13 visits 18346 winrate 4948 order 1 pv R13 R5 "
            "info move M17 visits 5254 winrate 4913 order 2 pv M17 F17"
        )

        # Parse
        parsed = parse_lz_analyze(sample)
        assert parsed.is_valid

        # Compute loss
        with_loss = compute_estimated_loss(parsed, k=0.5)
        assert with_loss.is_valid

        # Best candidate should have loss 0
        best = max(with_loss.candidates, key=lambda c: c.winrate)
        assert best.loss_est == 0.0

        # Other candidates should have positive loss
        for c in with_loss.candidates:
            if c.move != best.move:
                assert c.loss_est > 0.0 or c.winrate == best.winrate
