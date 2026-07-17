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
    """Mutable state shared across the tab builders and the popup orchestrator.

    Phase 145-D+: Replaces the deep closure nesting that previously lived
    inside ``do_mykatrain_settings_popup``. Checkbox callbacks in each tab
    mutate the ``selected_*`` lists which are later read by ``save_settings``.

    Phase 171: Leela タブ削除のため tab 数は 3 → 2 に。
    ``leela_config`` フィールドも削除。
    Phase 177: Kifunarabe タブ追加のため tab 数は 2 → 3 に。
    Phase 230-B: Leela 検証用の disable_katago チェックボックスを
    削除。``selected_disable_katago`` フィールドも廃止。

    Attributes:
        ctx: FeatureContext providing config, save_config, controls.
        current_settings: ``mykatrain_settings`` section dict (or empty).
        engine_config: ``engine`` section dict (or empty).
        current_engine: Resolved engine id via ``get_analysis_engine``.
            Phase 171 からは常に ``"katago"``。
        selected_engine: [engine_id] - 後方互換のため維持。常に ``"katago"``。
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
    selected_engine: list[str]
    # Phase 229: the analysis tab no longer exposes skill_preset as a
    # radio button group.  Instead, the user types ``player_rank`` (e.g.
    # ``5k`` / ``4段``) and the preset is auto-derived.  The selected_*
    # fields below are kept so existing save logic continues to work;
    # ``selected_skill_preset`` is now populated from
    # :func:`resolve_skill_preset` for display purposes only.
    selected_skill_preset: list[str]
    selected_player_rank: list[str]
    selected_pv_filter: list[str]
    selected_beginner_hints: list[bool]
    selected_format: list[str]
    selected_opp_info: list[str]
    # Phase 179: per-category summary hint toggles (all default True).
    selected_summary_mistake: list[bool]
    selected_summary_freedom: list[bool]
    selected_summary_difficulty: list[bool]
    selected_katago_uncertain: list[bool]
    # Phase 182: ownership / policy toggles.
    selected_summary_ownership: list[bool]
    selected_summary_policy: list[bool]
    # Phase 186: curator weak-axis hint toggle.
    selected_curator_hint: list[bool]
    searchable_widgets: list[dict[str, Any]] = field(default_factory=list)
    register_searchable: Callable[[str, Any], None] | None = None
    reopen_popup: Callable[[], None] | None = None
    popup: Any = None
    # Phase 229: stash a reference to the inferred-rank label so the
    # text callback can refresh it in-place without rebuilding the
    # layout (avoids focus loss). The label is created by the analysis
    # tab builder, so we hold a typed ``Any`` to keep the dataclass
    # Kivy-free.
    _rank_inferred_label: Any = None
    # Phase 246-A (H2): stash a reference to the PV filter status
    # label so the radio + rank-input callbacks can refresh it in place
    # without rebuilding the layout. Same Kivy-free pattern as above.
    _pv_filter_status_label: Any = None
    # Phase 247-B (H3): same pattern for the position-aware N → M
    # preview label. Refreshed alongside the static status label.
    _pv_filter_preview_label: Any = None
