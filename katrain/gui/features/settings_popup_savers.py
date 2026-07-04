# katrain/gui/features/settings_popup_savers.py
#
# Per-section save helpers for the myKatrain settings popup.
#
# Phase 175: Extracted from settings_popup.py to enable Kivy-free unit
# testing on CI. This module holds ONLY the ``_save_*`` helpers; it has
# NO dependency on Kivy widgets (only FeatureContext Protocol + stdlib),
# so ``tests/test_settings_savers.py`` no longer needs to skip on CI.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from katrain.core.constants import STATUS_ERROR
from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def _save_general_settings(ctx: FeatureContext, skill_preset: str, pv_filter_level: str) -> None:
    """Save general config (skill_preset, pv_filter_level)."""
    general = ctx.config("general") or {}
    general["skill_preset"] = skill_preset
    general["pv_filter_level"] = pv_filter_level
    ctx.set_config_section("general", general)
    ctx.save_config("general")


def _save_beginner_hints_settings(ctx: FeatureContext, enabled: bool) -> None:
    """Save beginner_hints enabled state (Phase 91)."""
    beginner_hints_config = ctx.config("beginner_hints") or {}
    beginner_hints_config["enabled"] = enabled
    ctx.set_config_section("beginner_hints", beginner_hints_config)
    ctx.save_config("beginner_hints")


def _save_engine_settings(ctx: FeatureContext, new_engine_value: str) -> None:
    """Save analysis engine selection with error handling (Phase 34, Phase 102)."""
    try:
        ctx.update_engine_config(analysis_engine=new_engine_value)
    except OSError as e:
        # File write failure during engine config save
        logging.error(f"Failed to save engine config (file error): {e}", exc_info=True)
        ctx.controls.set_status(
            i18n._("mykatrain:settings:engine_save_error"),
            STATUS_ERROR,
        )
    except Exception as e:
        # Boundary fallback: unexpected error (config structure issue, etc.)
        logging.error(f"Failed to save engine config (unexpected): {e}", exc_info=True)
        ctx.controls.set_status(
            i18n._("mykatrain:settings:engine_save_error"),
            STATUS_ERROR,
        )


def _save_mykatrain_settings(
    ctx: FeatureContext,
    default_user_name: str,
    karte_output_directory: str,
    batch_export_input_directory: str,
    karte_format: str,
    opponent_info_mode: str,
    disabled_katago: bool,
) -> None:
    """Save mykatrain_settings section + engine disabled flag (Phase 27)."""
    mykatrain_settings = {
        "default_user_name": default_user_name,
        "karte_output_directory": karte_output_directory,
        "batch_export_input_directory": batch_export_input_directory,
        "karte_format": karte_format,
        "opponent_info_mode": opponent_info_mode,
    }
    ctx.set_config_section("mykatrain_settings", mykatrain_settings)
    ctx.save_config("mykatrain_settings")
    # Save engine config (Phase 3 Extension)
    ctx.update_engine_config(disabled=disabled_katago)
