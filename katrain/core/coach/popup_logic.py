"""Phase 242-E: Pure logic helpers for the LLM Coach popup.

The popup in :mod:`katrain.gui.popups.llm_coach_popup` historically
mixed:

- Kivy widget plumbing (ids-first reads, ObjectProperty updates)
- Pure decision logic (which player color was selected, how to
  format the validation summary, what text to put in the type label)

The Kivy parts can only be exercised in a real display environment,
which made 94 of 96 popup tests fail in headless CI
(KivyMD's ``dp()`` call at module load requires a window).

Phase 242-E extracts the pure decision logic into this module so
tests can exercise it without a display. The popup becomes a thin
wrapper that reads widget values, calls these helpers, and writes
the results back to the widgets.

Kivy-free. Safe to import from CLI / tests / CI.

Public API
----------

- :func:`resolve_summary_spinner_values` — build the values list +
  default index for the summary-mode perspective spinner.
- :func:`resolve_player_color_internal` — pick a "B"/"W"/None player
  color from the perspective value + auto-detected fallback.
- :func:`is_summary_birdseye_value` — check whether a perspective
  value corresponds to the bird's-eye view.
- :func:`detect_path_type_from_file` — read a JSON file and decide
  whether it is ``"karte"`` / ``"summary"`` / ``"unknown"``.
- :func:`format_type_label` — compose the type_label text including
  the schema_version suffix (Phase 242-B).
- :func:`format_validation_status_summary` — build the
  status_label line for the karte/summary validation result, including
  truncation warning (Phase 242-B).
- :func:`cap_response_text` — truncate response input that exceeds
  the size limit and return the (possibly new) text + a warning
  status string (Phase 242-B).
- :func:`SUMMARY_BIRDSEYE_SENTINEL` — the bird's-eye sentinel
  string used by the popup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from katrain.core.coach.json_type import detect_json_type
from katrain.core.lang import i18n

# Phase 242-E: stable internal values for the perspective spinner.
# Mirrors the constants in :mod:`katrain.gui.popups.llm_coach_popup`
# but lives in core so the tests can import them without loading Kivy.
PERSPECTIVE_AUTO: str = "auto"
PERSPECTIVE_BLACK: str = "B"
PERSPECTIVE_WHITE: str = "W"

# Phase 242-E: bird's-eye sentinel. The summary-mode perspective
# spinner uses index 0 for "no focus" (全体俯瞰). Phase 241-D
# separated this from the out-of-range fallback by giving it a
# dedicated string sentinel that never collides with a real player
# name. The popup imports this constant; tests can too.
SUMMARY_BIRDSEYE_SENTINEL: str = "__birdseye__"

# Phase 242-E: response input cap. Mirrors the popup constant.
# 100k is well above realistic LLM outputs (~10-30k) and matches
# the validator's report size cap so the two limits align.
MAX_RESPONSE_INPUT_CHARS: int = 100_000


# --- Spinner / perspective helpers --------------------------------------


def resolve_player_color_internal(
    perspective_value: str,
    detected: str | None,
) -> str | None:
    """Resolve the perspective spinner value to a player color.

    Args:
        perspective_value: The spinner's stable internal value
            (``"auto"`` / ``"B"`` / ``"W"``). ``""`` (empty) is
            normalised to ``"auto"`` because StringProperty cannot
            store ``None``.
        detected: The auto-detected color from the Karte/SGF
            (``"B"`` / ``"W"`` / ``None``).

    Returns:
        - ``"B"`` / ``"W"`` when the spinner explicitly chose a side.
        - The detected color when the spinner is in ``"auto"``.
        - ``None`` when the spinner is auto and no auto-detection
          succeeded.

    Note:
        The previous convention used ``""`` (empty string) as a
        sentinel for "auto" because the StringProperty default was
        historically inconsistent. The current contract is to use
        :data:`PERSPECTIVE_AUTO` for the auto case.
    """
    val = perspective_value or PERSPECTIVE_AUTO
    if val == PERSPECTIVE_BLACK:
        return PERSPECTIVE_BLACK
    if val == PERSPECTIVE_WHITE:
        return PERSPECTIVE_WHITE
    # auto: prefer detected, else None
    return detected


def is_summary_birdseye_value(value: str | None) -> bool:
    """Check whether ``value`` is the bird's-eye sentinel.

    Centralised here so callers (popup handlers, tests) don't have
    to import the constant directly. Returns ``False`` for ``None``
    (no value at all is NOT bird's-eye, it's a bug state).
    """
    return value == SUMMARY_BIRDSEYE_SENTINEL


def resolve_summary_spinner_values(
    players: list[tuple[str, str | None]],
    matched_player: str | None = None,
    *,
    birdseye_label: str = "全体俯瞰",
) -> tuple[list[str], int]:
    """Build the values list + default index for the summary-mode spinner.

    The popup uses this to populate its perspective selector with
    one row per player plus a "bird's-eye" entry at index 0.

    Args:
        players: List of (name, rank) tuples — the players from the
            summary JSON.
        matched_player: Optional name of the player that matches
            ``default_user_name``. When provided, this player is
            placed first in the spinner (so the default selection
            at index 1 focuses on them).
        birdseye_label: Localised label for the bird's-eye entry.
            Defaults to Japanese "全体俯瞰" because the test harness
            runs in the default locale.

    Returns:
        ``(values, default_index)``:
        - ``values`` is the list of spinner labels starting with
          ``birdseye_label`` followed by one entry per player.
        - ``default_index`` is the spinner index to select on open
          (1 when a matched player exists, 0 otherwise).
    """
    # Stable ordering: matched_player first, then alphabetical.
    if matched_player:
        ordered_names = [matched_player] + [p[0] for p in players if p[0] != matched_player]
    else:
        ordered_names = [p[0] for p in players]
    # Drop empties defensively.
    ordered_names = [n for n in ordered_names if n]
    rank_lookup = {name: rank for name, rank in players}

    values: list[str] = [birdseye_label]
    for name in ordered_names:
        rank = rank_lookup.get(name)
        if rank:
            values.append(f"{name} ({rank})")
        else:
            values.append(name)

    default_index = 1 if matched_player and ordered_names else 0
    return values, default_index


def _summary_index_to_internal(
    index: int,
    players: list[tuple[str, str | None]],
) -> str | None:
    """Map a summary perspective spinner index to a player name or the
    bird's-eye sentinel.

    Returns:
        - :data:`SUMMARY_BIRDSEYE_SENTINEL` when ``index <= 0``
        - The player's ``name`` when ``0 < index <= len(players)``
        - ``None`` when the index is out of range (defensive fallback
          for stale spinner state).
    """
    if index <= 0:
        return SUMMARY_BIRDSEYE_SENTINEL
    if index > len(players):
        return None
    return players[index - 1][0]


# --- File / type detection helpers --------------------------------------


@dataclass(frozen=True)
class PathTypeResult:
    """Result of :func:`detect_path_type_from_file`.

    Attributes:
        path_type: ``"karte"`` / ``"summary"`` / ``"unknown"``.
        schema_version: The JSON's ``schema_version`` field if
            present and scalar, else ``None``.
        games_analyzed: For summary files, the
            ``meta.games_analyzed`` count. ``0`` for karte / unknown.
    """

    path_type: str
    schema_version: str | None = None
    games_analyzed: int = 0


def detect_path_type_from_file(path: str) -> PathTypeResult:
    """Read a JSON file and decide whether it is karte / summary / unknown.

    The function is the Kivy-free version of
    :meth:`katrain.gui.popups.llm_coach_popup.LLMCoachPopupContent._detect_path_type`.
    It returns the type AND the auxiliary fields the popup needs
    (schema_version, games_analyzed) so the popup does not need to
    open the file a second time.

    Errors during detection (file missing, malformed JSON) are mapped
    to ``"unknown"`` with empty auxiliary fields so the popup can
    surface a user-facing error message instead of crashing.
    """
    if not path:
        return PathTypeResult(path_type="unknown")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return PathTypeResult(path_type="unknown")
    except Exception:  # noqa: BLE001
        return PathTypeResult(path_type="unknown")
    if not isinstance(data, dict):
        return PathTypeResult(path_type="unknown")
    path_type = detect_json_type(data)

    schema_version: str | None = None
    sv = data.get("schema_version")
    if isinstance(sv, (str, int, float)):
        schema_version = str(sv)

    games_analyzed = 0
    if path_type == "summary":
        meta = data.get("meta") or {}
        if isinstance(meta, dict):
            g = meta.get("games_analyzed")
            if isinstance(g, int):
                games_analyzed = g

    return PathTypeResult(
        path_type=path_type,
        schema_version=schema_version,
        games_analyzed=games_analyzed,
    )


# --- Status / label formatters ------------------------------------------


def format_type_label(
    path_type: str,
    *,
    games_analyzed: int = 0,
    schema_version: str | None = None,
    single_label: str = "単局カルテ",
    multi_label: str = "複数局サマリ ({games}局)",
    unknown_label: str = "(未確定)",
) -> str:
    """Compose the type_label text including the schema_version suffix.

    Phase 242-B: the type label now appends ``" · Schema X.Y"`` when
    the JSON declares a schema_version. This helper is the Kivy-free
    version so the test harness can verify the format directly.
    """
    if path_type == "karte":
        base = single_label
    elif path_type == "summary":
        base = multi_label.format(games=games_analyzed)
    else:
        base = unknown_label
    if schema_version:
        return f"{base} · Schema {schema_version}"
    return base


def count_issue_markers(markdown: str) -> tuple[int, int, int]:
    """Count issue severity markers in a validation Markdown report.

    Returns:
        ``(high, medium, low)`` counts of ``[HIGH]`` / ``[MEDIUM]`` /
        ``[LOW]`` markers in the report. The popup uses this to
        surface a one-line summary in the status label.

    Note:
        Both the Karte validator and the Summary validator produce
        markers in the same ``[SEVERITY]`` format so a single
        counting function works for both. False positives are
        possible if the LLM output itself contains the literal
        ``[HIGH]`` etc. inside a code block, but the validator
        runs after the LLM response is past the system instruction
        so this is acceptable.
    """
    high = markdown.count("[HIGH]")
    medium = markdown.count("[MEDIUM]")
    low = markdown.count("[LOW]")
    return high, medium, low


def was_truncated(markdown: str) -> bool:
    """Phase 242-B: detect whether ``markdown`` is a truncated report.

    The trailing marker is the i18n-truncated suffix that
    :func:`katrain.gui.features.llm_coach.validate_llm_response` (and
    its summary counterpart) appends. We check the substring rather
    than recomputing the length so we stay robust to i18n edits
    to the truncated marker.
    """
    marker = i18n._("mykatrain:llm-coach:truncated")
    return bool(marker) and markdown.endswith(marker)


def format_validation_status_summary(
    is_clean: bool,
    high: int,
    medium: int,
    low: int,
    *,
    truncated: bool = False,
) -> str:
    """Build the status_label line for a validation result.

    Mirrors the popup's status message logic in :meth:`on_validate`
    and :meth:`_on_validate_summary`. Returns the final string the
    popup should write to status_label.

    Args:
        is_clean: True when the validator reported no issues.
        high, medium, low: Counts of issues by severity (from
            :func:`count_issue_markers`).
        truncated: True when the report was truncated (Phase 242-B
            ``was_truncated`` flag).
    """
    total = high + medium + low
    if is_clean:
        if total == 0:
            status = i18n._("mykatrain:llm-coach:validation-clean")
        else:
            status = i18n._("mykatrain:llm-coach:validation-clean-with-notes").format(count=total)
    else:
        status = i18n._("mykatrain:llm-coach:validation-issues-with-count").format(
            high=high, medium=medium, low=low, total=total
        )
    if truncated:
        status = i18n._("mykatrain:llm-coach:truncation-warning").format(base=status)
    return status


def cap_response_text(text: str) -> tuple[str, str | None]:
    """Truncate response input that exceeds :data:`MAX_RESPONSE_INPUT_CHARS`.

    Phase 242-B: the popup binds ``on_text`` of response_input to a
    callback that calls this helper. When the pasted text exceeds
    the cap, the helper returns the truncated text and a
    user-facing status string. When the text is within the cap, it
    returns the text unchanged and ``None``.

    Args:
        text: The current response_input content.

    Returns:
        ``(new_text, status_or_none)``:
        - ``new_text`` is either the original text (within cap) or
          the truncated version (over cap).
        - ``status_or_none`` is a status string to display when
          truncation happened, or ``None`` when no action was
          needed.
    """
    if not text or len(text) <= MAX_RESPONSE_INPUT_CHARS:
        return text, None
    return (
        text[:MAX_RESPONSE_INPUT_CHARS],
        i18n._("mykatrain:llm-coach:paste-too-long").format(
            original=len(text), kept=MAX_RESPONSE_INPUT_CHARS
        ),
    )


__all__ = [
    # Constants
    "PERSPECTIVE_AUTO",
    "PERSPECTIVE_BLACK",
    "PERSPECTIVE_WHITE",
    "SUMMARY_BIRDSEYE_SENTINEL",
    "MAX_RESPONSE_INPUT_CHARS",
    # Data classes
    "PathTypeResult",
    # Spinner / perspective
    "resolve_player_color_internal",
    "is_summary_birdseye_value",
    "resolve_summary_spinner_values",
    "_summary_index_to_internal",
    # File / type detection
    "detect_path_type_from_file",
    # Status / label formatters
    "format_type_label",
    "count_issue_markers",
    "was_truncated",
    "format_validation_status_summary",
    "cap_response_text",
]
