"""Karte-mode helpers for LLMCoachPopupContent (Phase PR2-P2).

Pure helper functions extracted from ``katrain.gui.popups.llm_coach_popup``
to limit the popup class's responsibility surface. Each helper takes
the popup instance as its first argument so it can read/write widget
attributes (``self.karte_path_input``, ``self.detected_rank``, etc.)
without being a method on the popup class.

These helpers are intentionally module-level rather than methods on
``LLMCoachPopupContent`` so:

1. The popup class shrinks from 1373 → ~930 lines (god class reduction).
2. Karte-mode and Summary-mode helpers can be reasoned about
   independently.
3. KV bindings (``on_perspective_changed`` etc.) remain on the popup
   class for compatibility — the popup method just forwards to the
   corresponding helper here.

Backward compatibility:
    All existing ``LLMCoachPopupContent`` methods (``_populate_karte_player_info``
    / ``_apply_karte_rank_fallback`` / ``_detect_and_apply_player_color`` /
    ``_update_karte_status_summary`` / ``_refresh_rank_hint`` /
    ``_refresh_perspective_hint``) are kept as thin wrappers that call
    the helpers below. Tests and KV rules that referenced those methods
    continue to work unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.gui.popups.llm_coach_popup import LLMCoachPopupContent


def populate_karte_player_info(popup: LLMCoachPopupContent, karte_path: str, settings: dict[str, str]) -> None:
    """Karte-mode rank + colour + status update.

    Equivalent to ``LLMCoachPopupContent._populate_karte_player_info``
    (Phase 272-E).
    """
    try:
        from katrain.gui.features.llm_coach import detect_player_info

        info = detect_player_info(popup.katrain, karte_path)
    except Exception as exc:
        popup._set_status(
            i18n._("mykatrain:llm-coach:auto-detect-failed").format(error=str(exc)),
            error=True,
        )
        return

    apply_karte_rank_fallback(
        popup,
        info,
        general_player_rank=settings["general_player_rank"],
        default_user_rank=settings["default_user_rank"],
    )

    color = detect_and_apply_player_color(popup, karte_path, info)
    update_karte_status_summary(popup, settings["default_user"], info, color)


def apply_karte_rank_fallback(
    popup: LLMCoachPopupContent,
    info: dict[str, Any],
    *,
    general_player_rank: str,
    default_user_rank: str,
) -> None:
    """Run the 3-tier rank fallback chain for a Karte JSON.

    Equivalent to ``LLMCoachPopupContent._apply_karte_rank_fallback``.
    """
    from katrain.gui.features.llm_coach import resolve_rank_fallback_chain

    detected = resolve_rank_fallback_chain(
        info,
        popup.perspective_value,
        general_player_rank=general_player_rank,
        default_user_rank=default_user_rank,
    )
    if detected:
        popup.detected_rank = detected
        current = popup._read_text("rank_input")
        if not current:
            popup._set_widget_text("rank_input", detected)
    popup._refresh_rank_hint()


def detect_and_apply_player_color(popup: LLMCoachPopupContent, karte_path: str, info: dict[str, Any]) -> str | None:
    """Resolve the player colour for a Karte JSON and update the hint.

    Equivalent to ``LLMCoachPopupContent._detect_and_apply_player_color``.
    """
    from katrain.gui.features.llm_coach import detect_player_color_for_user

    try:
        color, _ = detect_player_color_for_user(popup.katrain, karte_path, player_info=info)
    except Exception as exc:
        popup._set_status(
            i18n._("mykatrain:llm-coach:auto-detect-failed").format(error=str(exc)),
            error=True,
        )
        color = None
    if color in ("B", "W"):
        popup.detected_player_color = color
    popup._refresh_perspective_hint()
    return color


def update_karte_status_summary(
    popup: LLMCoachPopupContent,
    default_user: str,
    info: dict[str, Any],
    color: str | None,
) -> None:
    """Surface the Karte detection result in the status line.

    Equivalent to ``LLMCoachPopupContent._update_karte_status_summary``.
    """
    if not default_user:
        popup._set_status(
            i18n._("mykatrain:llm-coach:auto-detect-no-default-user"),
            error=True,
        )
        return
    black_name = (info.get("black") or {}).get("name") or "?"
    white_name = (info.get("white") or {}).get("name") or "?"
    if color == "B":
        color_label = i18n._("mykatrain:llm-coach:perspective-black")
    elif color == "W":
        color_label = i18n._("mykatrain:llm-coach:perspective-white")
    else:
        color_label = "?"
    popup._set_status(
        i18n._("mykatrain:llm-coach:auto-detect-summary").format(
            user=default_user,
            black=black_name,
            white=white_name,
            color=color_label,
        )
    )


def refresh_perspective_hint(popup: LLMCoachPopupContent) -> None:
    """Update the small hint under the perspective spinner (Karte mode).

    Equivalent to ``LLMCoachPopupContent._refresh_perspective_hint``.
    """
    label = popup._get_widget("perspective_auto_label")
    if label is None:
        return
    detected = popup.detected_player_color
    if detected == "B":
        text = i18n._("mykatrain:llm-coach:perspective-auto-detected").format(
            color=i18n._("mykatrain:llm-coach:perspective-black")
        )
    elif detected == "W":
        text = i18n._("mykatrain:llm-coach:perspective-auto-detected").format(
            color=i18n._("mykatrain:llm-coach:perspective-white")
        )
    else:
        text = i18n._("mykatrain:llm-coach:perspective-auto-fallback")
    label.text = text
