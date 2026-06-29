# katrain/gui/features/settings_popup_state.py
#
# Shared state container for the settings popup tab builders.
#
# Phase 145-D+: Extracted from settings_popup.py to enable cleaner separation.
# This module holds ONLY the _SettingsPopupContext dataclass; it has no
# dependency on Kivy widgets beyond type hints.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


@dataclass
class _SettingsPopupContext:
    """Mutable state shared across the 3 tab builders and the popup orchestrator.

    Phase 145-D+: Replaces the deep closure nesting that previously lived
    inside ``do_mykatrain_settings_popup``. Checkbox callbacks in each tab
    mutate the ``selected_*`` lists which are later read by ``save_settings``.

    Attributes:
        ctx: FeatureContext providing config, save_config, controls.
        current_settings: ``mykatrain_settings`` section dict (or empty).
        engine_config: ``engine`` section dict (or empty).
        current_engine: Resolved engine id via ``get_analysis_engine``.
        leela_config: Typed LeelaConfig via ``ctx.get_leela_config()``.
        selected_engine: [engine_id] - mutated by engine radio buttons.
        selected_disable_katago: [bool] - mutated by disable-katago checkbox.
        selected_skill_preset: [str] - mutated by skill preset radio buttons.
        selected_pv_filter: [str] - mutated by PV filter radio buttons.
        selected_beginner_hints: [bool] - mutated by beginner hints checkbox.
        selected_format: [str] - mutated by karte_format radio buttons.
        selected_opp_info: [str] - mutated by opponent_info_mode radio buttons.
        searchable_widgets: Items appended by ``register_searchable``.
        register_searchable: Closure set by the orchestrator (initially None).
        reopen_popup: Closure set by the orchestrator (initially None).
        popup: Popup reference, set by the orchestrator after creation.
    """

    ctx: FeatureContext
    current_settings: dict[str, Any]
    engine_config: dict[str, Any]
    current_engine: str
    leela_config: Any
    selected_engine: list[str]
    selected_disable_katago: list[bool]
    selected_skill_preset: list[str]
    selected_pv_filter: list[str]
    selected_beginner_hints: list[bool]
    selected_format: list[str]
    selected_opp_info: list[str]
    searchable_widgets: list[dict[str, Any]] = field(default_factory=list)
    register_searchable: Callable[[str, Any], None] | None = None
    reopen_popup: Callable[[], None] | None = None
    popup: Any = None
