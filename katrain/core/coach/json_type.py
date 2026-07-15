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
    """Phase 227-A + 228-A: aggregate summary weaknesses into frequency-ranked patterns.

    Supports two summary JSON shapes (auto-detected):

    **Shape A** (Phase 227-A / fixture-style): top-level ``weaknesses``::

        {"weaknesses": {"black": [{"phase": "middle", "category": "blunder",
                                   "count": 5, "total_loss": 30.0}, ...],
                        "white": [...]}}

    **Shape B** (Phase 228-A / real ``summary_json_export.py`` output):
    per-player ``players.<name>.mistakes``::

        {"players": {"sentoku870": {"mistakes": {"blunder": {"count": 5,
                                                              "pct": 1.3,
                                                              "avg_loss": 19.04},
                                                   "mistake": {...}, ...}}}}}

    When Shape B is detected, each ``(player, mistake_category)`` becomes
    one pattern. ``total_loss`` is reconstructed as ``avg_loss * count``
    (preserves the magnitude signal the LLM needs to rank severity),
    and ``frequency_ratio`` is ``count / games_analyzed``.

    Shape A wins when both are present (because Shape A's
    ``weaknesses[*].total_loss`` is more precise than the reconstructed
    value from Shape B).

    Args:
        data: Summary JSON dict.
        top_n: If > 0, return only the top-N patterns by total_loss.
            If 0 (default), return all patterns.

    Returns:
        Sorted list of pattern dicts (highest total_loss first), e.g.::

            [
              {"color": "black", "phase": "middle",
               "category": "blunder", "count": 5,
               "total_loss": 30.0, "frequency_ratio": 1.0,
               "player": "sentoku870"},
              ...
            ]

        ``player`` is only populated for Shape B patterns; Shape A
        patterns omit the field (callers default to the colour label).

        Returns an empty list when no recognisable weakness data exists.
    """
    weaknesses = data.get("weaknesses", {}) or {}
    games = extract_summary_game_count(data) or 0

    patterns: list[dict[str, Any]] = []

    # ---- Shape A: top-level weaknesses[*] (Phase 227-A legacy) ----
    if isinstance(weaknesses, dict) and weaknesses:
        for color, items in weaknesses.items():
            if not isinstance(items, list):
                continue
            for w in items:
                if not isinstance(w, dict):
                    continue
                count = w.get("count")
                total_loss = w.get("total_loss")
                if count is None and total_loss is None:
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

    # ---- Shape B: players.<name>.mistakes[*] (Phase 228-A real shape) ----
    # Only synthesise Shape B patterns when Shape A returned nothing
    # (avoids duplicate signals when both shapes coexist).
    if not patterns:
        for player_name, mistakes in extract_summary_player_mistakes(data).items():
            for m in mistakes:
                cat = m["category"]
                count = m["count"]
                total_loss = m["total_loss"]
                # Shape B's ``count`` is per-move (e.g. 5 blunder moves
                # out of 388 total moves), NOT per-game. So
                # ``count / games_analyzed`` would be misleading
                # (e.g. 5/3 ≈ 1.67). We surface the per-move
                # ``pct`` field instead and leave ``frequency_ratio``
                # at 0.0. The prompt renderer (Phase 228-B) detects
                # this and prefers ``pct``.
                freq = 0.0
                patterns.append({
                    "color": player_name,  # player name doubles as "color" for Shape B
                    "player": player_name,
                    "phase": "all",  # Shape B has no per-phase breakdown per mistake category
                    "category": cat,
                    "count": count,
                    "total_loss": total_loss,
                    "frequency_ratio": freq,
                    "pct": float(m.get("pct", 0.0) or 0.0),
                })

    # Sort by total_loss desc, then count desc, then category asc for stability.
    patterns.sort(key=lambda p: (-p["total_loss"], -p["count"], p["category"]))

    if top_n > 0:
        return patterns[:top_n]
    return patterns


# Phase 228-A: New extractors for the real summary_json_export.py shape.


# Known mistake categories in the players.<name>.mistakes block. Order
# matches the standard KataGo mistake ladder (good → inaccuracy → mistake
# → blunder) so the rendered prompt reads top-down by severity.
_PLAYER_MISTAKE_CATEGORIES: tuple[str, ...] = (
    "blunder",
    "mistake",
    "inaccuracy",
    "good",
)


def extract_summary_player_mistakes(
    data: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Phase 228-A: extract per-player mistake distribution.

    The real ``summary_json_export.py`` writes per-player mistake stats
    under ``players.<name>.mistakes`` rather than at the top level::

        "mistakes": {
            "good":       {"count": 310, "pct": 79.9,
                           "denominator": 388, "avg_loss": 0.28},
            "inaccuracy": {"count": 51,  "pct": 13.1,
                           "denominator": 388, "avg_loss": 3.11},
            "mistake":    {"count": 22,  "pct": 5.7,
                           "denominator": 388, "avg_loss": 5.69},
            "blunder":    {"count": 5,   "pct": 1.3,
                           "denominator": 388, "avg_loss": 19.04},
        }

    Returns:
        ``{player_name: [{"category", "count", "pct", "avg_loss",
                            "total_loss", "denominator"}, ...], ...}``

        Categories are emitted in ``_PLAYER_MISTAKE_CATEGORIES`` order
        (blunder first) so callers can render top-down by severity.

        Returns ``{}`` when no ``players`` block exists or when no
        player carries a ``mistakes`` sub-block. Empty sub-blocks
        (no categories) are skipped.
    """
    players = data.get("players", {}) or {}
    if not isinstance(players, dict):
        return {}

    out: dict[str, list[dict[str, Any]]] = {}
    for player_name, block in players.items():
        if not isinstance(block, dict):
            continue
        mistakes = block.get("mistakes")
        if not isinstance(mistakes, dict) or not mistakes:
            continue
        entries: list[dict[str, Any]] = []
        # Emit in severity order so callers don't have to re-sort.
        for category in _PLAYER_MISTAKE_CATEGORIES:
            if category not in mistakes:
                continue
            m = mistakes[category]
            if not isinstance(m, dict):
                continue
            count = m.get("count", 0) or 0
            avg_loss = m.get("avg_loss", 0.0) or 0.0
            total_loss = m.get("total_loss")
            if total_loss is None and isinstance(count, (int, float)) and isinstance(avg_loss, (int, float)):
                # Reconstruct total_loss when the export omitted it
                # (the field was added in a later schema revision).
                total_loss = float(avg_loss) * float(count)
            entries.append({
                "category": category,
                "count": int(count) if isinstance(count, (int, float)) else 0,
                "pct": float(m.get("pct", 0.0) or 0.0),
                "avg_loss": float(avg_loss) if isinstance(avg_loss, (int, float)) else 0.0,
                "total_loss": float(total_loss) if isinstance(total_loss, (int, float)) else 0.0,
                "denominator": int(m.get("denominator", 0) or 0),
            })
        if entries:
            out[str(player_name)] = entries
    return out


# Standard phase labels in the players.<name>.phases block.
_PLAYER_PHASE_LABELS: tuple[str, ...] = (
    "opening",
    "middle",
    "endgame",
)


def extract_summary_player_phase_losses(
    data: dict[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Phase 228-A: extract per-player per-phase loss breakdown.

    The real ``summary_json_export.py`` writes per-player per-phase
    stats under ``players.<name>.phases``::

        "phases": {
            "opening": {"moves": 75,  "total_loss": 47.01, "avg_loss": 0.627},
            "middle":  {"moves": 173, "total_loss": 370.78, "avg_loss": 2.143},
            "endgame": {"moves": 140, "total_loss": 48.6,  "avg_loss": 0.347},
        }

    Returns:
        ``{player_name: {phase: {"moves", "total_loss", "avg_loss"}, ...}, ...}``

        Phases are emitted in ``_PLAYER_PHASE_LABELS`` order
        (opening → middle → endgame) so callers can render the
        standard temporal progression.

        Returns ``{}`` when no ``players`` block exists or when no
        player carries a ``phases`` sub-block.
    """
    players = data.get("players", {}) or {}
    if not isinstance(players, dict):
        return {}

    out: dict[str, dict[str, dict[str, Any]]] = {}
    for player_name, block in players.items():
        if not isinstance(block, dict):
            continue
        phases = block.get("phases")
        if not isinstance(phases, dict) or not phases:
            continue
        per_player: dict[str, dict[str, Any]] = {}
        for phase in _PLAYER_PHASE_LABELS:
            if phase not in phases:
                continue
            p = phases[phase]
            if not isinstance(p, dict):
                continue
            per_player[phase] = {
                "moves": int(p.get("moves", 0) or 0),
                "total_loss": float(p.get("total_loss", 0.0) or 0.0),
                "avg_loss": float(p.get("avg_loss", 0.0) or 0.0),
            }
        if per_player:
            out[str(player_name)] = per_player
    return out


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
    "extract_summary_weakness_patterns",  # Phase 227-A + 228-A
    "extract_summary_player_mistakes",  # Phase 228-A
    "extract_summary_player_phase_losses",  # Phase 228-A
    "normalize_summary_to_karte_shape",
]
