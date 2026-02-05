"""Integration tests for skill_radar_popup (mock-based, CI-safe)."""

import os
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.analysis.skill_radar import SkillTier

# Skip tests that import Kivy-dependent modules on CI (no display available)
_CI_SKIP = pytest.mark.skipif(
    os.environ.get("CI", "").lower() == "true", reason="Requires display - cannot import Kivy modules on headless CI"
)


@_CI_SKIP
class TestPopupValidation:
    """Tests for popup validation logic."""

    @patch("katrain.gui.features.skill_radar_popup.Clock")
    def test_rejects_no_game(self, _):
        """Should reject when no game is loaded."""
        from katrain.core.constants import OUTPUT_ERROR
        from katrain.gui.features.skill_radar_popup import _show_impl

        ctx = MagicMock(game=None)
        _show_impl(ctx)
        ctx.log.assert_called_once()
        # Check that error output was used
        call_args = ctx.log.call_args
        assert call_args[0][1] == OUTPUT_ERROR

    @patch("katrain.gui.features.skill_radar_popup.Clock")
    def test_rejects_non_19x19(self, _):
        """Should reject non-19x19 boards."""
        from katrain.core.constants import OUTPUT_ERROR
        from katrain.gui.features.skill_radar_popup import _show_impl

        ctx = MagicMock()
        ctx.game.board_size = (9, 9)
        _show_impl(ctx)
        ctx.log.assert_called_once()
        call_args = ctx.log.call_args
        assert call_args[0][1] == OUTPUT_ERROR

    @patch("katrain.gui.features.skill_radar_popup.Clock")
    def test_rejects_empty_moves(self, _):
        """Should reject when snapshot has no moves."""
        from katrain.core.constants import OUTPUT_ERROR
        from katrain.gui.features.skill_radar_popup import _show_impl

        ctx = MagicMock()
        ctx.game.board_size = (19, 19)
        ctx.game.build_eval_snapshot.return_value = MagicMock(moves=[])
        _show_impl(ctx)
        ctx.log.assert_called()
        call_args = ctx.log.call_args
        assert call_args[0][1] == OUTPUT_ERROR

    @patch("katrain.gui.features.skill_radar_popup.Clock")
    def test_rejects_13x13(self, _):
        """Should reject 13x13 boards."""
        from katrain.core.constants import OUTPUT_ERROR
        from katrain.gui.features.skill_radar_popup import _show_impl

        ctx = MagicMock()
        ctx.game.board_size = (13, 13)
        _show_impl(ctx)
        ctx.log.assert_called()
        call_args = ctx.log.call_args
        assert call_args[0][1] == OUTPUT_ERROR

    @patch("katrain.gui.features.skill_radar_popup.Clock")
    def test_handles_snapshot_exception(self, _):
        """Should handle exception when building snapshot."""
        from katrain.core.constants import OUTPUT_ERROR
        from katrain.gui.features.skill_radar_popup import _show_impl

        ctx = MagicMock()
        ctx.game.board_size = (19, 19)
        ctx.game.build_eval_snapshot.side_effect = Exception("Test error")
        _show_impl(ctx)
        ctx.log.assert_called()
        call_args = ctx.log.call_args
        assert call_args[0][1] == OUTPUT_ERROR
        # Verify error message is included
        assert "Test error" in str(call_args[0][0])


class TestTierColorConsistency:
    """Tests for tier color consistency."""

    def test_all_tiers_have_colors(self):
        """All tier values should have associated colors."""
        from katrain.gui.widgets.radar_geometry import tier_to_color

        for tier in ["tier_1", "tier_2", "tier_3", "tier_4", "tier_5", "unknown"]:
            c = tier_to_color(tier)
            assert len(c) == 4
            assert all(0 <= v <= 1 for v in c)

    def test_tier_4_5_same_color(self):
        """Tier 4 and 5 should have the same color (both advanced)."""
        from katrain.gui.widgets.radar_geometry import tier_to_color

        assert tier_to_color("tier_4") == tier_to_color("tier_5")

    def test_tier_1_2_same_color(self):
        """Tier 1 and 2 should have the same color (both novice)."""
        from katrain.gui.widgets.radar_geometry import tier_to_color

        assert tier_to_color("tier_1") == tier_to_color("tier_2")


@_CI_SKIP
class TestTierI18NMapping:
    """Tests for tier to i18n key mapping."""

    def test_all_skill_tiers_have_i18n_keys(self):
        """All SkillTier values should have i18n key mappings."""
        from katrain.gui.features.skill_radar_popup import TIER_I18N

        for tier in SkillTier:
            assert tier in TIER_I18N, f"Missing i18n key for {tier}"

    def test_i18n_keys_format(self):
        """All i18n keys should follow radar:tier-* format."""
        from katrain.gui.features.skill_radar_popup import TIER_I18N

        for _tier, key in TIER_I18N.items():
            assert key.startswith("radar:tier-"), f"Invalid key format: {key}"


@_CI_SKIP
class TestAxisI18NMapping:
    """Tests for axis to i18n key mapping."""

    def test_all_axes_have_i18n_keys(self):
        """All axes should have i18n key mappings."""
        from katrain.gui.widgets.radar_chart import AXIS_I18N
        from katrain.gui.widgets.radar_geometry import AXIS_ORDER

        for axis in AXIS_ORDER:
            assert axis in AXIS_I18N, f"Missing i18n key for axis {axis}"

    def test_axis_i18n_keys_format(self):
        """All axis i18n keys should follow radar:axis-* format."""
        from katrain.gui.widgets.radar_chart import AXIS_I18N

        for _axis, key in AXIS_I18N.items():
            assert key.startswith("radar:axis-"), f"Invalid key format: {key}"


class TestMinMovesConstant:
    """Tests for MIN_MOVES_FOR_RADAR constant usage."""

    def test_min_moves_imported(self):
        """MIN_MOVES_FOR_RADAR should be importable from skill_radar."""
        from katrain.core.analysis.skill_radar import MIN_MOVES_FOR_RADAR

        assert isinstance(MIN_MOVES_FOR_RADAR, int)
        assert MIN_MOVES_FOR_RADAR > 0

    def test_min_moves_used_in_popup(self):
        """Popup should use MIN_MOVES_FOR_RADAR constant."""
        import inspect

        from katrain.gui.features import skill_radar_popup

        source = inspect.getsource(skill_radar_popup)
        assert "MIN_MOVES_FOR_RADAR" in source
