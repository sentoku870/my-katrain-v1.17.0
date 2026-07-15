"""Phase 221: JSON type detection + multi-game summary support.

Distinguishes between single-game Karte JSON and multi-game Summary JSON
and provides metric extractors that work for both.

A summary JSON is identified by:
- presence of ``meta.games_analyzed`` (or ``games_analyzed``)
- presence of ``players`` block (per-player aggregated stats)
- absence of ``weaknesses`` at the top level (summary uses
  ``phase_x_mistake`` instead)

A karte JSON is identified by:
- presence of ``weaknesses`` keyed by player color
- presence of ``important_moves`` array

This module keeps detection logic pure / Kivy-free.
"""

from __future__ import annotations

from typing import Any, Literal

JsonType = Literal["karte", "summary", "unknown"]


def detect_json_type(data: dict[str, Any]) -> JsonType:
    """Identify whether a parsed JSON is a karte or summary.

    Returns:
        - ``"karte"`` if the JSON is a single-game Karte
        - ``"summary"`` if it's a multi-game Summary
        - ``"unknown"`` if neither pattern matches (caller should warn)

    Heuristics (Phase 226-C C4 — karte is checked first to avoid the
    false-positive where a single-game karte with ``meta.game_count: 1``
    was misidentified as a summary):

    1. karte: top-level ``weaknesses`` keyed by color AND non-empty
       ``important_moves`` list.
    2. summary: ``meta.games_analyzed`` / ``meta.game_count`` /
       ``meta.game_count > 1`` OR top-level ``players`` block.
    3. summary (fallback): ``phase_x_mistake`` block (Phase 149 C-3).
    """
    if not isinstance(data, dict):
        return "unknown"

    # Phase 226-C (C4): karte-shaped check FIRST. Previously the
    # ``meta.games_analyzed`` / ``meta.game_count`` short-circuit
    # fired before the karte check, so a single-game karte with
    # ``meta.game_count: 1`` (set by ``normalize_summary_to_karte_shape``
    # round-trips or by Phase 218 calibration fixtures) was wrongly
    # classified as ``"summary"``.
    if (
        isinstance(data.get("weaknesses"), dict)
        and isinstance(data.get("important_moves"), list)
        and len(data["important_moves"]) > 0
    ):
        return "karte"

    meta = data.get("meta", {}) or {}
    if isinstance(meta, dict):
        # ``games_analyzed`` is the canonical summary marker.
        if "games_analyzed" in meta:
            return "summary"
        # ``game_count`` only counts as summary when it's > 1 — single
        # game is just a karte.
        game_count = meta.get("game_count")
        if isinstance(game_count, int) and game_count > 1:
            return "summary"

    if isinstance(data.get("players"), dict):
        return "summary"

    # Fallback heuristic: summary has ``phase_x_mistake`` but no
    # important_moves (the karte marker checked above).
    if isinstance(data.get("phase_x_mistake"), dict) and not isinstance(
        data.get("important_moves"), list
    ):
        return "summary"

    return "unknown"


def is_karte(data: dict[str, Any]) -> bool:
    """Convenience: True if data is a single-game Karte."""
    return detect_json_type(data) == "karte"


def is_summary(data: dict[str, Any]) -> bool:
    """Convenience: True if data is a multi-game Summary."""
    return detect_json_type(data) == "summary"


def extract_summary_game_count(data: dict[str, Any]) -> int | None:
    """Return number of games summarised, or None if unknown."""
    meta = data.get("meta", {}) or {}
    if isinstance(meta, dict):
        v = meta.get("games_analyzed") or meta.get("game_count")
        if isinstance(v, int):
            return v
    if isinstance(data.get("games"), list):
        return len(data["games"])
    return None


def extract_summary_total_loss(data: dict[str, Any]) -> float | None:
    """Sum of total_loss across all weaknesses in summary.

    Useful as a summary-level "size of problem" indicator.
    """
    total = 0.0
    found = False
    weaknesses = data.get("weaknesses", {}) or {}
    if isinstance(weaknesses, dict):
        for color_list in weaknesses.values():
            if not isinstance(color_list, list):
                continue
            for w in color_list:
                if isinstance(w, dict):
                    v = w.get("total_loss")
                    if isinstance(v, (int, float)):
                        total += float(v)
                        found = True
    return total if found else None


def extract_summary_mistake_buckets(data: dict[str, Any]) -> dict[str, int]:
    """Return phase x category bucket counts from ``phase_x_mistake``.

    Returns dict like ``{"opening:mistake": 5, "middle:blunder": 8}``.
    Empty dict when no buckets.
    """
    buckets = data.get("phase_x_mistake", {}) or {}
    if not isinstance(buckets, dict):
        return {}
    return {
        str(k): int(v)
        for k, v in buckets.items()
        if isinstance(v, (int, float))
    }


def extract_summary_weakness_patterns(
    data: dict[str, Any],
    *,
    top_n: int = 0,
) -> list[dict[str, Any]]:
    """Phase 227-A: aggregate per-color weaknesses into frequency-ranked patterns.

    Each summary weakness entry typically looks like::

        {"phase": "middle", "category": "blunder",
         "count": 5, "total_loss": 30.0}

    This helper flattens ``weaknesses[<color>]`` lists across both colors
    and returns one record per (color, phase, category) combination with
    an added ``frequency_ratio`` field (``count / games_analyzed``).

    Args:
        data: Summary JSON dict.
        top_n: If > 0, return only the top-N patterns by total_loss.
            If 0 (default), return all patterns.

    Returns:
        Sorted list of pattern dicts (highest total_loss first), e.g.::

            [
              {"color": "black", "phase": "middle",
               "category": "blunder", "count": 5,
               "total_loss": 30.0, "frequency_ratio": 1.0},
              ...
            ]

        Returns an empty list when the summary has no ``weaknesses`` block
        or when ``games_analyzed`` cannot be determined (frequency_ratio
        degrades to 0.0 in that case but entries are still returned).
    """
    weaknesses = data.get("weaknesses", {}) or {}
    if not isinstance(weaknesses, dict):
        return []

    games = extract_summary_game_count(data) or 0

    patterns: list[dict[str, Any]] = []
    for color, items in weaknesses.items():
        if not isinstance(items, list):
            continue
        for w in items:
            if not isinstance(w, dict):
                continue
            count = w.get("count")
            total_loss = w.get("total_loss")
            if count is None and total_loss is None:
                # Skip entries that carry no quantitative signal.
                continue
            freq = (float(count) / games) if (games and isinstance(count, (int, float))) else 0.0
            patterns.append({
                "color": str(color),
                "phase": str(w.get("phase", "unknown")),
                "category": str(w.get("category", "unknown")),
                "count": int(count) if isinstance(count, (int, float)) else 0,
                "total_loss": float(total_loss) if isinstance(total_loss, (int, float)) else 0.0,
                "frequency_ratio": freq,
            })

    # Sort by total_loss desc, then count desc, then category asc for stability.
    patterns.sort(key=lambda p: (-p["total_loss"], -p["count"], p["category"]))

    if top_n > 0:
        return patterns[:top_n]
    return patterns


def normalize_summary_to_karte_shape(data: dict[str, Any]) -> dict[str, Any]:
    """Project a summary JSON into a Karte-shaped view for downstream consumers.

    Builds a minimal Karte-like dict that the coach pipeline can consume:

    - ``meta.game_count``: total games summarised
    - ``weaknesses``: passthrough from summary
    - ``mistake_streaks``: passthrough if present, else empty
    - ``loss_progression``: passthrough if present, else empty
    - ``important_moves``: empty (summary doesn't have per-move data)
    - ``summary``: combined summary block
    - ``_is_summary``: True (downstream code can detect)

    Note: This is a *projection* — round-trip loss is acceptable for
    prompt-generation purposes but not for full data preservation.
    """
    if not is_summary(data):
        # Already karte-shaped; pass through.
        return data

    meta = data.get("meta", {}) or {}
    games_count = extract_summary_game_count(data) or 0

    projected: dict[str, Any] = {
        "schema_version": data.get("schema_version", "3.4"),
        "_is_summary": True,
        "meta": {
            **meta,
            "game_count": games_count,
        },
        "summary": data.get("summary", {}),
        "weaknesses": data.get("weaknesses", {}),
        "mistake_streaks": data.get("mistake_streaks", {}),
        "loss_progression": data.get("loss_progression", {}).get("all", [])
        if isinstance(data.get("loss_progression"), dict)
        else data.get("loss_progression", []),
        "important_moves": [],
        # Summary-specific fields exposed for debugging
        "_phase_x_mistake": data.get("phase_x_mistake", {}),
        "_games": data.get("games", []),
        "_players": data.get("players", {}),
    }
    return projected


__all__ = [
    "JsonType",
    "detect_json_type",
    "is_karte",
    "is_summary",
    "extract_summary_game_count",
    "extract_summary_total_loss",
    "extract_summary_mistake_buckets",
    "extract_summary_weakness_patterns",  # Phase 227-A
    "normalize_summary_to_karte_shape",
]
