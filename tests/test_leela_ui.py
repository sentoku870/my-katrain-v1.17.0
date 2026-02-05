"""Tests for Leela UI components."""

from katrain.core.constants import (
    LEELA_COLOR_BEST,
    LEELA_COLOR_LARGE,
    LEELA_COLOR_MEDIUM,
    LEELA_COLOR_SMALL,
    LEELA_LOSS_THRESHOLD_MEDIUM,
    LEELA_LOSS_THRESHOLD_SMALL,
)
from katrain.core.leela.models import LeelaCandidate
from katrain.core.leela.presentation import (
    format_loss_est,
    format_visits,
    format_winrate_pct,
    lerp_color,
    loss_to_color,
)


class TestLerpColor:
    """Tests for color interpolation."""

    def test_t_zero_returns_c1(self):
        """t=0 should return c1."""
        c1 = (1.0, 0.0, 0.0, 1.0)
        c2 = (0.0, 1.0, 0.0, 1.0)
        result = lerp_color(c1, c2, 0.0)
        assert result == c1

    def test_t_one_returns_c2(self):
        """t=1 should return c2."""
        c1 = (1.0, 0.0, 0.0, 1.0)
        c2 = (0.0, 1.0, 0.0, 1.0)
        result = lerp_color(c1, c2, 1.0)
        assert result == c2

    def test_t_half_returns_midpoint(self):
        """t=0.5 should return midpoint."""
        c1 = (0.0, 0.0, 0.0, 0.0)
        c2 = (1.0, 1.0, 1.0, 1.0)
        result = lerp_color(c1, c2, 0.5)
        assert result == (0.5, 0.5, 0.5, 0.5)


class TestLossToColor:
    """Tests for loss to color conversion."""

    def test_zero_loss_is_best_color(self):
        """Zero loss should return best (green) color."""
        result = loss_to_color(0.0)
        assert result == LEELA_COLOR_BEST

    def test_negative_loss_is_best_color(self):
        """Negative loss should be treated as zero (best)."""
        result = loss_to_color(-1.0)
        assert result == LEELA_COLOR_BEST

    def test_small_loss_interpolates_to_yellow(self):
        """Small loss should interpolate between green and yellow."""
        result = loss_to_color(LEELA_LOSS_THRESHOLD_SMALL)
        # At threshold, should be LEELA_COLOR_SMALL
        assert result == LEELA_COLOR_SMALL

    def test_medium_loss_interpolates_to_orange(self):
        """Medium loss should interpolate between yellow and orange."""
        result = loss_to_color(LEELA_LOSS_THRESHOLD_MEDIUM)
        # At threshold, should be LEELA_COLOR_MEDIUM
        assert result == LEELA_COLOR_MEDIUM

    def test_large_loss_approaches_red(self):
        """Large loss should approach red color."""
        result = loss_to_color(50.0)
        # Should be at or near LEELA_COLOR_LARGE
        # Due to interpolation, check it's close to red
        assert result[0] > 0.9  # High red component


class TestFormatWinratePct:
    """Tests for winrate percentage formatting."""

    def test_format_50_percent(self):
        """50% winrate."""
        assert format_winrate_pct(0.5) == "50.0%"

    def test_format_100_percent(self):
        """100% winrate."""
        assert format_winrate_pct(1.0) == "100.0%"

    def test_format_0_percent(self):
        """0% winrate."""
        assert format_winrate_pct(0.0) == "0.0%"

    def test_format_precision(self):
        """Check decimal precision."""
        assert format_winrate_pct(0.523) == "52.3%"
        assert format_winrate_pct(0.5237) == "52.4%"  # Rounded


class TestFormatVisits:
    """Tests for visits formatting."""

    def test_small_visits(self):
        """Small visit counts."""
        assert format_visits(100) == "100"
        assert format_visits(999) == "999"

    def test_thousands(self):
        """Thousands should show 'K'."""
        assert format_visits(1000) == "1.0K"
        assert format_visits(1500) == "1.5K"
        assert format_visits(10000) == "10.0K"

    def test_zero_visits(self):
        """Zero visits."""
        assert format_visits(0) == "0"


class TestFormatLossEst:
    """Tests for loss estimate formatting (from logic module)."""

    def test_none_value(self):
        """None should show '--'."""
        assert format_loss_est(None) == "--"

    def test_zero_value(self):
        """Zero should show '0.0'."""
        assert format_loss_est(0.0) == "0.0"

    def test_positive_value(self):
        """Positive values should format correctly."""
        assert format_loss_est(2.3) == "2.3"
        assert format_loss_est(10.0) == "10.0"


class TestColorConstants:
    """Tests for color constant values."""

    def test_colors_are_rgba_tuples(self):
        """All colors should be 4-element tuples."""
        colors = [
            LEELA_COLOR_BEST,
            LEELA_COLOR_SMALL,
            LEELA_COLOR_MEDIUM,
            LEELA_COLOR_LARGE,
        ]
        for color in colors:
            assert len(color) == 4
            assert all(0.0 <= c <= 1.0 for c in color)

    def test_colors_have_full_alpha(self):
        """All colors should have alpha=1.0."""
        colors = [
            LEELA_COLOR_BEST,
            LEELA_COLOR_SMALL,
            LEELA_COLOR_MEDIUM,
            LEELA_COLOR_LARGE,
        ]
        for color in colors:
            assert color[3] == 1.0


class TestLeelaUIIntegration:
    """Integration tests for Leela UI data flow."""

    def test_candidate_with_loss_for_display(self):
        """Test that a candidate with loss_est can be formatted for display."""
        candidate = LeelaCandidate(
            move="D4",
            winrate=0.52,
            visits=1000,
            loss_est=0.0,
        )

        # These are the values that would be displayed
        loss_str = format_loss_est(candidate.loss_est)
        winrate_str = format_winrate_pct(candidate.winrate)
        visits_str = format_visits(candidate.visits)

        assert loss_str == "0.0"
        assert winrate_str == "52.0%"
        assert visits_str == "1.0K"

    def test_multiple_candidates_color_sequence(self):
        """Test that candidates with increasing loss get progressively warmer colors."""
        losses = [0.0, 1.0, 3.0, 7.0]
        colors = [loss_to_color(loss) for loss in losses]

        # First should be green (best)
        assert colors[0] == LEELA_COLOR_BEST

        # The last color should have high red component (approaching red)
        assert colors[-1][0] > 0.8  # High red component for large loss

        # Color at threshold should match expected
        assert loss_to_color(LEELA_LOSS_THRESHOLD_SMALL) == LEELA_COLOR_SMALL
        assert loss_to_color(LEELA_LOSS_THRESHOLD_MEDIUM) == LEELA_COLOR_MEDIUM
