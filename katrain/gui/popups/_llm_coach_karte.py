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

    Phase 272-B: stash the detected info on ``popup._last_player_info``
    so :meth:`on_generate_and_copy` can render a precise error message
    when auto-detection fails (the player names from the Karte are
    not known to the generate handler otherwise).
    """
    try:
        from katrain.gui.features.llm_coach import detect_player_info

        info = detect_player_info(popup.katrain, karte_path)
    except Exception as exc:
        popup._set_status(
            i18n._("mykatrain:llm-coach:auto-detect-failed").format(error=str(exc)),
            error=True,
        )
        # Phase 272-B (post-merge fix): mark the cache as missing so
        # the generate / validate handlers' safety check recognises a
        # genuine detect failure instead of treating an empty cache
        # as "first invocation".
        popup._last_player_info = {"source": "missing"}
        popup._last_player_info_path = str(karte_path)
        return

    # Phase 272-B: cache so the generate handler can produce a precise
    # error message when auto-detection fails.
    popup._last_player_info = info
    # PR-01 (⑥): remember the path so the generate / validate guards
    # can detect a stale cache after the user picks a different file
    # via the file browser.
    popup._last_player_info_path = str(karte_path)

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

    Phase 272-B: the rank_input widget is now a Spinner. We convert
    the resolved value into the corresponding localised label before
    setting it on the widget, and only set it when the current value
    is empty (so manual user edits aren't overwritten).
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
            # Phase 272-B: Spinner needs a label, not a raw rank.
            # ``detected`` may be a free-text value like ``"4d"`` /
            # ``"4段"`` from the Karte, or an already-normalised mode
            # key like ``"advanced"`` from ``general/player_rank``.
            # Normalise first so the Spinner label is always a
            # 5-level entry.
            try:
                from katrain.core.coach.player_rank_mode import parse_mode_key
                from katrain.gui.popups.llm_coach_popup import rank_spinner_key_to_label

                mode_key = parse_mode_key(detected) or "intermediate"
                label = rank_spinner_key_to_label(mode_key)
            except ImportError:
                label = detected
            popup._set_widget_text("rank_input", label)
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

    Phase 272-B: when ``color is None`` (auto-detection failed), display
    a dedicated error message naming the actual player names from the
    Karte so the user understands why the perspective is unresolved.
    Previously the status showed ``color="?"`` with no actionable
    advice, which led to silent "PlayerColor: unknown" prompts.
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
        # Phase 272-B: name the actual players so the user knows
        # exactly why auto-detection failed.
        popup._set_status(
            i18n._("mykatrain:llm-coach:auto-detect-user-not-found").format(
                user=default_user,
                black=black_name,
                white=white_name,
            ),
            error=True,
        )
        return
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
