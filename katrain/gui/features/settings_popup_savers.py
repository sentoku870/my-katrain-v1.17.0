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


def _save_beginner_hints_settings(
    ctx: FeatureContext,
    enabled: bool,
    *,
    summary_mistake: bool = True,
    summary_freedom: bool = True,
    summary_difficulty: bool = True,
    katago_uncertain: bool = True,
    summary_ownership: bool = True,
    summary_policy: bool = True,
    curator_hint: bool = True,
) -> None:
    """Save beginner_hints section (Phase 91 + Phase 179 + Phase 182 + 186).

    Phase 179: 4 per-category-group toggles persisted alongside master.
    Phase 182: 2 additional toggles (``summary_ownership``,
    ``summary_policy``).
    Phase 186: ``curator_hint`` toggle for CURATOR_WEAK_AXIS.

    All default to True; missing keys keep their previous value.
    """
    beginner_hints_config = ctx.config("beginner_hints") or {}
    beginner_hints_config["enabled"] = enabled
    beginner_hints_config["summary_mistake"] = bool(summary_mistake)
    beginner_hints_config["summary_freedom"] = bool(summary_freedom)
    beginner_hints_config["summary_difficulty"] = bool(summary_difficulty)
    beginner_hints_config["katago_uncertain"] = bool(katago_uncertain)
    beginner_hints_config["summary_ownership"] = bool(summary_ownership)
    beginner_hints_config["summary_policy"] = bool(summary_policy)
    beginner_hints_config["curator_hint"] = bool(curator_hint)
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
