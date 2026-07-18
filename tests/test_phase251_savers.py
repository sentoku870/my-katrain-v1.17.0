"""Tests for Phase 251: per-category save logic in settings_popup_savers.

Verifies that ``_save_beginner_hints_settings`` correctly persists the
10 individual category toggles, and that callers can mix group +
individual parameters freely.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from katrain.gui.features.settings_popup_savers import _save_beginner_hints_settings


@pytest.fixture
def mock_ctx() -> MagicMock:
    """Minimal FeatureContext stand-in: only ``config`` / ``set_config_section`` / ``save_config`` are used."""
    ctx = MagicMock()
    ctx.config.return_value = {}
    return ctx


class TestSaveBeginnerHintsSettingsPhase251:
    """Phase 251: 10 individual category toggles are persisted."""

    def test_all_individual_keys_persisted(self, mock_ctx):
        _save_beginner_hints_settings(
            mock_ctx,
            enabled=True,
            summary_mistake=True,
            summary_freedom=True,
            summary_difficulty=True,
            katago_uncertain=True,
            summary_ownership=True,
            summary_policy=True,
            curator_hint=True,
            self_atari=False,
            ignore_atari=False,
            missed_capture=True,
            cut_risk=False,
            low_liberties=True,
            self_capture_like=True,
            bad_shape=False,
            heavy_group=True,
            missed_defense=True,
            urgent_vs_big=False,
        )
        call_args, _ = mock_ctx.set_config_section.call_args
        # call_args is a positional tuple: ("beginner_hints", dict)
        assert call_args[0] == "beginner_hints"
        bh = call_args[1]
        # Group toggles
        assert bh["summary_mistake"] is True
        assert bh["summary_freedom"] is True
        # Individual toggles (Phase 251)
        assert bh["self_atari"] is False
        assert bh["ignore_atari"] is False
        assert bh["missed_capture"] is True
        assert bh["cut_risk"] is False
        assert bh["low_liberties"] is True
        assert bh["self_capture_like"] is True
        assert bh["bad_shape"] is False
        assert bh["heavy_group"] is True
        assert bh["missed_defense"] is True
        assert bh["urgent_vs_big"] is False

    def test_all_defaults_keep_keys(self, mock_ctx):
        """Default values (True for everything) still persist the keys so
        a fresh export contains the per-category booleans."""
        _save_beginner_hints_settings(mock_ctx, enabled=True)
        call_args, _ = mock_ctx.set_config_section.call_args
        bh = call_args[1]
        for key in (
            "self_atari",
            "ignore_atari",
            "missed_capture",
            "cut_risk",
            "low_liberties",
            "self_capture_like",
            "bad_shape",
            "heavy_group",
            "missed_defense",
            "urgent_vs_big",
        ):
            assert key in bh, f"missing {key} in persisted beginner_hints"
            assert bh[key] is True, f"{key} default must be True"

    def test_preserves_pre_existing_keys(self, mock_ctx):
        """Existing keys (e.g. ``board_highlight``) are preserved through save."""
        mock_ctx.config.return_value = {
            "enabled": True,
            "board_highlight": True,  # legacy key, still in use
            "require_reliable": True,  # another legacy key
        }
        _save_beginner_hints_settings(mock_ctx, enabled=True, cut_risk=False)
        call_args, _ = mock_ctx.set_config_section.call_args
        bh = call_args[1]
        assert bh["board_highlight"] is True
        assert bh["require_reliable"] is True
        assert bh["cut_risk"] is False
