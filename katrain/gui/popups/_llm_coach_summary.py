"""Summary-mode helpers for LLMCoachPopupContent (Phase PR2-P2).

Pure helper functions extracted from ``katrain.gui.popups.llm_coach_popup``
to limit the popup class's responsibility surface. See the docstring
in :mod:`katrain.gui.popups._llm_coach_karte` for the rationale and
backward-compatibility guarantees.

Helpers extracted here:

- ``populate_summary_perspective``     — main dispatcher (Phase 227-D)
- ``detect_summary_player_info``       — read player list from summary JSON
- ``build_summary_player_pairs``       — project to ``(name, rank)`` tuples
- ``update_summary_spinner``           — rebuild perspective spinner values
- ``resolve_summary_spinner_index``    — pick default spinner index
- ``update_perspective_value_from_index`` — project index back to internal value
- ``apply_summary_rank_fallback``      — 3-tier rank fallback (Phase 269)
- ``update_summary_status``            — surface summary detection in status line
- ``generate_summary_prompt``          — summary-mode prompt build (Phase 227-D)
- ``validate_summary_response``        — summary-mode response validation
- ``on_summary_perspective_changed``   — KV-side callback (Phase 241-E)
- ``refresh_summary_perspective_hint`` — small hint under perspective spinner
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from kivy.core.clipboard import Clipboard

from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.gui.popups.llm_coach_popup import LLMCoachPopupContent


def populate_summary_perspective(
    popup: LLMCoachPopupContent,
    summary_path: str,
    default_user: str | None,
    default_user_rank: str | None,
    *,
    general_player_rank: str | None = None,
) -> None:
    """Load summary players and rebuild the perspective spinner.

    Equivalent to ``LLMCoachPopupContent._populate_summary_perspective``.
    """
    info = detect_summary_player_info(popup, summary_path, default_user)
    if info is None:
        return

    matched = info.get("matched_player", {}) or {}
    matched_name = matched.get("name") if isinstance(matched, dict) else None

    popup.summary_players = build_summary_player_pairs(info)
    update_summary_spinner(popup, info, matched_name)
    apply_summary_rank_fallback(popup, info, general_player_rank, default_user_rank)
    refresh_summary_perspective_hint(popup, matched.get("name"))
    update_summary_status(popup, summary_path, info, matched, default_user)


def detect_summary_player_info(
    popup: LLMCoachPopupContent,
    summary_path: str,
    default_user: str | None,
) -> dict[str, Any] | None:
    """Read the summary JSON's player list and matched player."""
    from katrain.gui.features.llm_coach import detect_player_info_for_summary

    try:
        return detect_player_info_for_summary(summary_path, default_user_name=default_user or None)
    except Exception as exc:
        popup._set_status(
            i18n._("mykatrain:llm-coach:auto-detect-failed").format(error=str(exc)),
            error=True,
        )
        return None


def build_summary_player_pairs(
    info: dict[str, Any],
) -> list[tuple[str, str | None]]:
    """Project the summary's ``all_players`` into ``(name, rank)`` tuples."""
    players_raw = info.get("all_players", []) or []
    return [(str(p["name"]), p.get("rank")) for p in players_raw if isinstance(p, dict) and p.get("name")]


def update_summary_spinner(
    popup: LLMCoachPopupContent,
    info: dict[str, Any],
    matched_name: str | None,
) -> None:
    """Rebuild the perspective spinner values + default index."""
    from katrain.core.coach.popup_logic import resolve_summary_spinner_values

    values, _default_idx = resolve_summary_spinner_values(
        popup.summary_players,
        matched_player=matched_name,
        birdseye_label=i18n._("mykatrain:llm-coach:summary-perspective-birdseye"),
    )
    spinner = popup._get_widget("perspective_select")
    if spinner is None:
        return
    spinner.values = values
    resolve_summary_spinner_index(popup, info)
    try:
        spinner.text = values[popup.summary_perspective_index]
    except (IndexError, AttributeError):
        spinner.text = values[0]
    update_perspective_value_from_index(popup)


def resolve_summary_spinner_index(
    popup: LLMCoachPopupContent,
    info: dict[str, Any],
) -> None:
    """Pick which spinner index to land on (Phase 241-E)."""
    user_preserved = popup._summary_perspective_user_set and 0 < popup.summary_perspective_index <= len(
        popup.summary_players
    )
    if user_preserved:
        return
    popup.summary_perspective_index = 1 if info.get("default_user_matched") and popup.summary_players else 0


def update_perspective_value_from_index(popup: LLMCoachPopupContent) -> None:
    """Project the spinner index back into ``perspective_value`` (Phase 241-D)."""
    from katrain.core.coach.popup_logic import (
        PERSPECTIVE_AUTO as _PERSPECTIVE_AUTO_INTERNAL,
    )
    from katrain.core.coach.popup_logic import (
        SUMMARY_BIRDSEYE_SENTINEL as _SUMMARY_BIRDSEYE_SENTINEL,
    )
    from katrain.core.coach.popup_logic import _summary_index_to_internal

    internal_value = _summary_index_to_internal(popup.summary_perspective_index, popup.summary_players)
    if internal_value is None or internal_value == _SUMMARY_BIRDSEYE_SENTINEL:
        popup.perspective_value = _PERSPECTIVE_AUTO_INTERNAL
    else:
        popup.perspective_value = internal_value


def apply_summary_rank_fallback(
    popup: LLMCoachPopupContent,
    info: dict[str, Any],
    general_player_rank: str | None,
    default_user_rank: str | None,
) -> None:
    """3-tier priority chain for the rank auto-fill on summary kifu (Phase 269)."""
    from katrain.core.coach.popup_logic import resolve_summary_rank

    detected_rank = resolve_summary_rank(
        info,
        general_player_rank=general_player_rank,
        default_user_rank=default_user_rank,
    )
    popup.detected_rank = detected_rank
    if detected_rank:
        current = popup._read_text("rank_input")
        if not current:
            popup._set_widget_text("rank_input", detected_rank)
    popup._refresh_rank_hint()


def update_summary_status(
    popup: LLMCoachPopupContent,
    summary_path: str,
    info: dict[str, Any],
    matched: dict[str, Any],
    default_user: str | None,
) -> None:
    """Surface the summary-detection result in the status line."""
    games = getattr(popup, "path_games_analyzed", 0)
    if default_user and matched.get("name"):
        popup._set_status(
            i18n._("mykatrain:llm-coach:summary-perspective-summary").format(
                user=default_user,
                player=matched.get("name"),
                games=games,
            )
        )
    else:
        popup._set_status(
            i18n._("mykatrain:llm-coach:auto-detect-no-default-user"),
            error=not bool(matched.get("name")),
        )


def generate_summary_prompt(
    popup: LLMCoachPopupContent,
    karte_path: str,
    rank: str | None,
) -> bool:
    """Build the summary-mode LLM prompt and copy it to the clipboard.

    Returns ``True`` on success, ``False`` if any step failed (status
    is set in the latter case).

    Equivalent to ``LLMCoachPopupContent._on_generate_summary``.
    """
    from katrain.gui.features.llm_coach import build_summary_llm_prompt

    player_name: str | None = None
    idx = popup.summary_perspective_index
    if 0 < idx <= len(popup.summary_players):
        player_name = popup.summary_players[idx - 1][0]
    ok, content = build_summary_llm_prompt(
        popup.katrain,
        karte_path,
        rank=rank,
        player_name=player_name,
    )
    if not ok:
        popup._set_status(content, error=True)
        popup._set_result(content)
        return False
    try:
        Clipboard.copy(content)
    except Exception as exc:  # noqa: BLE001
        popup._set_status(
            i18n._("mykatrain:llm-coach:copy-failed").format(error=str(exc)),
            error=True,
        )
        return False
    games_match = re.search(r"\*\*(\d+)\s*局\*\*", content)
    games = int(games_match.group(1)) if games_match else 0
    patterns_match = re.search(r"top\s+(\d+)", content)
    patterns = int(patterns_match.group(1)) if patterns_match else 0
    popup._set_status(
        i18n._("mykatrain:llm-coach:summary-copy-success").format(
            chars=len(content),
            games=games,
            patterns=patterns,
        )
    )
    popup._set_result(content)
    return True


def validate_summary_response(
    popup: LLMCoachPopupContent,
    karte_path: str,
    response_text: str,
    rank: str | None,
) -> bool:
    """Validate the user-pasted LLM response against a summary JSON.

    Returns ``True`` on success. Equivalent to
    ``LLMCoachPopupContent._on_validate_summary``.
    """
    from katrain.core.coach.popup_logic import (
        count_issue_markers,
        format_validation_status_summary,
        was_truncated,
    )
    from katrain.gui.features.llm_coach import validate_summary_llm_response

    player_name: str | None = None
    idx = popup.summary_perspective_index
    if 0 < idx <= len(popup.summary_players):
        player_name = popup.summary_players[idx - 1][0]
    is_clean, markdown = validate_summary_llm_response(
        popup.katrain,
        karte_path,
        response_text,
        rank=rank,
        player_name=player_name,
    )
    popup._set_result(markdown)
    high, medium, low = count_issue_markers(markdown)
    status = format_validation_status_summary(
        is_clean=is_clean,
        high=high,
        medium=medium,
        low=low,
        truncated=was_truncated(markdown),
    )
    popup._set_status(status)
    return True


def on_summary_perspective_changed(popup: LLMCoachPopupContent) -> None:
    """KV-side callback: summary perspective spinner selection changed (Phase 241-E)."""
    from katrain.core.coach.popup_logic import (
        PERSPECTIVE_AUTO as _PERSPECTIVE_AUTO_INTERNAL,
    )
    from katrain.core.coach.popup_logic import (
        SUMMARY_BIRDSEYE_SENTINEL as _SUMMARY_BIRDSEYE_SENTINEL,
    )
    from katrain.core.coach.popup_logic import _summary_index_to_internal

    spinner = popup._get_widget("perspective_select")
    if spinner is None:
        return
    values = getattr(spinner, "values", []) or []
    raw = getattr(spinner, "text", "") or ""
    try:
        idx = values.index(raw)
    except ValueError:
        idx = 0
    popup.summary_perspective_index = idx
    popup._summary_perspective_user_set = True
    internal_value = _summary_index_to_internal(popup.summary_perspective_index, popup.summary_players)
    if internal_value is None or internal_value == _SUMMARY_BIRDSEYE_SENTINEL:
        popup.perspective_value = _PERSPECTIVE_AUTO_INTERNAL
    else:
        popup.perspective_value = internal_value
    if 0 < idx <= len(popup.summary_players):
        _, rank = popup.summary_players[idx - 1]
        if rank:
            popup.detected_rank = rank
            current = popup._read_text("rank_input")
            if not current:
                popup._set_widget_text("rank_input", rank)
            popup._refresh_rank_hint()


def refresh_summary_perspective_hint(
    popup: LLMCoachPopupContent,
    player_name: str | None,
) -> None:
    """Update the small hint under the perspective spinner."""
    label = popup._get_widget("perspective_auto_label")
    if label is None:
        return
    if player_name:
        label.text = i18n._("mykatrain:llm-coach:perspective-auto-detected").format(color=player_name)
    else:
        label.text = i18n._("mykatrain:llm-coach:perspective-auto-fallback")
