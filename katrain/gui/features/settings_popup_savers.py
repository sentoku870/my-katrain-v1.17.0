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
from typing import TYPE_CHECKING, Any

from katrain.core.constants import STATUS_ERROR
from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def _save_general_settings(
    ctx: FeatureContext,
    skill_preset: str,
    pv_filter_level: str,
    player_rank: str = "",
) -> None:
    """Save general config (skill_preset, player_rank, pv_filter_level).

    Phase 229: the user types ``player_rank`` (e.g. ``5k`` / ``4段``) and
    the preset is auto-derived.  We still persist the resolved preset
    name into ``general/skill_preset`` so existing readers (and legacy
    configs that pre-date Phase 229) keep working unchanged.
    """
    general = ctx.config("general") or {}
    general["player_rank"] = player_rank.strip()
    # Persist the resolved preset so old code paths reading
    # ``general/skill_preset`` continue to work without modification.
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


def migrate_default_user_rank(
    ctx: FeatureContext,
    current_settings: dict[str, Any],
) -> None:
    """Phase 230-E: Fold the legacy ``default_user_rank`` into ``player_rank``.

    The export tab used to expose a ``ユーザー棋力 (任意)`` field that wrote
    to ``mykatrain_settings.default_user_rank``. Phase 229-D already
    reads ``general/player_rank`` first in the LLM Coach fallback chain,
    so the duplicate input has been removed. This helper transparently
    migrates any pre-existing ``default_user_rank`` value so users do
    not lose their setting.

    Rules:
    - ``player_rank`` empty + ``default_user_rank`` set → copy across.
    - ``player_rank`` set + ``default_user_rank`` set → keep ``player_rank``.
    - ``default_user_rank`` always cleared after migration.
    - No-op when ``default_user_rank`` is already empty.

    This function lives in the Kivy-free savers module so it can be
    unit-tested without a Kivy environment.
    """
    legacy_rank = (current_settings.get("default_user_rank") or "").strip()
    if not legacy_rank:
        return

    general = ctx.config("general") or {}
    if not isinstance(general, dict):
        general = {}
    current_player_rank = (general.get("player_rank") or "").strip()

    if not current_player_rank:
        general["player_rank"] = legacy_rank
        ctx.set_config_section("general", general)
        ctx.save_config("general")

    # Clear the legacy field so the export tab stays clean on future opens.
    updated_settings = dict(current_settings)
    updated_settings["default_user_rank"] = ""
    ctx.set_config_section("mykatrain_settings", updated_settings)
    ctx.save_config("mykatrain_settings")
    # Reflect the mutation so the in-memory dict the rest of the popup
    # reads from stays consistent.
    current_settings["default_user_rank"] = ""


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
    default_user_rank: str = "",  # Phase 225.8
) -> None:
    """Save mykatrain_settings section (Phase 27).

    Phase 230-B: Leela 検証用の ``disabled_katago`` パラメータと
    ``engine/disabled`` 更新を削除。Leela は Phase 171 で完全廃止済み。
    """
    mykatrain_settings = {
        "default_user_name": default_user_name,
        # Phase 225.8: optional default user rank (e.g. "4段" / "5k").
        # The LLM Coach uses this as a fallback when no Karte is loaded
        # or the Karte has no BR/WR info.
        "default_user_rank": default_user_rank,
        "karte_output_directory": karte_output_directory,
        "batch_export_input_directory": batch_export_input_directory,
        "karte_format": karte_format,
        "opponent_info_mode": opponent_info_mode,
    }
    ctx.set_config_section("mykatrain_settings", mykatrain_settings)
    ctx.save_config("mykatrain_settings")
