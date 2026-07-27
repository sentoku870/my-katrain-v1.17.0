"""Phase 270: Multi-karte aggregation helpers.

Aggregates fields from multiple single-game Karte JSONs into a single
view that the LLM Coach (summary path) can consume. The motivation is
that the per-game Karte carries rich per-move data
(``area`` / ``position_difficulty`` / ``meaning_tag_label`` /
``reason_tags_distribution`` / ``data_quality``) which is currently
dropped when the summary path builds a multi-game view from
``GameSummaryData`` directly.

What this module provides:

- :func:`aggregate_reason_tags_by_color` — cross-game sum of
  ``reason_tags_distribution`` keyed by color, then tag.
- :func:`aggregate_area_difficulty` — count matrix of
  ``{area: {position_difficulty: N}}`` from ``important_moves`` and
  ``critical_3`` entries.
- :func:`detect_loss_spike_windows` — consecutive 10-move loss
  buckets whose ``avg_loss`` exceeds ``multiplier × overall_avg``.
- :func:`group_representative_moves_by_tag` — for each
  ``primary_tag`` the top-N highest-loss moves across all kartes
  (with ``coords`` and ``move_number``).
- :func:`aggregate_data_quality` — mean of ``avg_visits`` /
  ``reliability_pct`` / ``coverage_pct`` across kartes that have
  a ``data_quality`` block.
- :func:`build_meaning_tag_label_map` — ``primary_tag`` →
  ``meaning_tag_label`` map. Sources labels from karte entries
  first, then falls back to :data:`MEANING_TAG_REGISTRY` for tags
  the kartes did not see.

Kivy-free. All functions accept a list of karte JSON ``dict``s and
return plain Python data structures (no Kivy widgets, no
:class:`GameNode`). Safe to call from CLI / tests / GUI.

Phase 270 schema: the aggregated view is rendered with
``schema_version = "3.6"``. Existing summary consumers continue
to work because the aggregation is opt-in: callers that do not pass
karte JSONs see the same prompt body as before.

(2026-07: bumped 3.5 -> 3.6 because the base report schema moved to
3.5; the aggregated view stays one step ahead of the base schema.)
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# All known board areas in the Karte JSON ``area`` field. Order is
# corner → edge → center so the rendered matrix reads clockwise from
# the corner.
_BOARD_AREAS: tuple[str, ...] = (
    "corner",
    "edge",
    "center",
)

# All known position_difficulty values. ``unknown`` is the fallback
# when the field is missing or unparseable. The leading ``only`` is
# the most severe (KataGo labeled it ONLY_MOVE).
_DIFFICULTY_LEVELS: tuple[str, ...] = (
    "only",
    "hard",
    "normal",
    "easy",
    "unknown",
)

# Default multiplier for :func:`detect_loss_spike_windows`. A 10-move
# bucket is a "spike" when its ``avg_loss`` exceeds
# ``multiplier × overall_avg_loss``. 2.0 is a reasonable default
# that matches the ux conventions in :mod:`katrain.core.reports` —
# the LLM Coach popup surfaces 2× avg loss as a "noticeable dip".
_LOSS_SPIKE_MULTIPLIER_DEFAULT: float = 2.0


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _safe_get(d: Any, *keys: str, default: Any = None) -> Any:
    """Nested ``dict.get`` that swallows non-dict intermediates.

    Used throughout this module to keep the per-karte loops robust
    against partial / older shapes. Returns ``default`` if any
    segment along the chain is missing or not a dict.
    """
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def _normalize_difficulty(value: Any) -> str:
    """Coerce a ``position_difficulty`` value to one of ``_DIFFICULTY_LEVELS``.

    Returns ``"unknown"`` for missing or unrecognised values. This
    is the only acceptable value outside the known set, so the
    matrix is always a complete 2-D grid.
    """
    if not isinstance(value, str):
        return "unknown"
    v = value.lower().strip()
    if v in _DIFFICULTY_LEVELS:
        return v
    return "unknown"


def _normalize_area(value: Any) -> str | None:
    """Coerce an ``area`` value to one of ``_BOARD_AREAS`` or ``None``.

    Returns ``None`` for missing or unrecognised values. The
    aggregator skips ``None`` rows so the matrix does not grow a
    bogus "unknown" area bucket.
    """
    if not isinstance(value, str):
        return None
    v = value.lower().strip()
    if v in _BOARD_AREAS:
        return v
    return None


def _iter_kartes(kartes: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    """Yield the dicts in ``kartes`` that look like karte JSONs.

    A "karte JSON" is a dict with a top-level ``schema_version`` key.
    Summary JSONs and other dicts are filtered out so callers can
    pass a mixed list (e.g. ``kartes + summaries``) without
    crashing. The filter is intentionally lenient — we do not
    verify the schema version, just the structural shape.
    """
    for k in kartes:
        if isinstance(k, dict) and "schema_version" in k:
            yield k


def _game_id_for(karte: dict[str, Any]) -> str:
    """Best-effort game id for spike-window reporting.

    Falls back to ``"<unknown>"`` so the output is always a
    non-empty string. Callers can still identify the window by
    ``(start_move, end_move)``.
    """
    return str(_safe_get(karte, "meta", "game_id", default="<unknown>") or "<unknown>")


# ---------------------------------------------------------------------------
# 1. reason_tags_by_color
# ---------------------------------------------------------------------------


def aggregate_reason_tags_by_color(
    kartes: Iterable[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Sum ``reason_tags_distribution`` across kartes, keyed by color then tag.

    Each karte carries::

        "reason_tags_distribution": {
            "black": {"endgame_hint": 3, "heavy_loss": 2},
            "white": {"endgame_hint": 1}
        }

    The aggregated output is::

        {
            "black": {"endgame_hint": 7, "heavy_loss": 4, ...},
            "white": {"endgame_hint": 2, ...},
        }

    Colors other than ``"black"`` / ``"white"`` (e.g. the
    single-game "B" / "W" form, or a custom alias) are preserved
    as-is so downstream consumers see the same key the karte used.

    Returns an empty dict when no karte has a
    ``reason_tags_distribution`` block.
    """
    out: dict[str, dict[str, int]] = {}
    for k in _iter_kartes(kartes):
        dist = k.get("reason_tags_distribution")
        if not isinstance(dist, dict):
            continue
        for color, tags in dist.items():
            if not isinstance(tags, dict):
                continue
            bucket = out.setdefault(str(color), {})
            for tag, count in tags.items():
                if isinstance(count, (int, float)):
                    bucket[str(tag)] = bucket.get(str(tag), 0) + int(count)
    return out


# ---------------------------------------------------------------------------
# 2. area_difficulty_matrix
# ---------------------------------------------------------------------------


def aggregate_area_difficulty(
    kartes: Iterable[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Count ``(area, position_difficulty)`` pairs across all
    ``important_moves`` and ``critical_3`` entries.

    Each karte contributes:

    - every entry in ``important_moves`` that has a non-null
      ``area`` and a parseable ``position_difficulty``
    - every entry in ``critical_3.<color>`` (same fields)

    The result is a complete 2-D grid::

        {
            "corner": {"only": N, "hard": N, "normal": N,
                       "easy":  N, "unknown": N},
            "edge":   {...},
            "center": {...},
        }

    Every (area, difficulty) cell is present even when its count is
    zero so downstream rendering does not have to special-case
    missing keys. Areas outside the known set are skipped (no
    "unknown" area bucket).

    Returns an empty dict when no karte contributes any
    (area, difficulty) pair.
    """
    # Pre-fill the full grid so missing cells stay at 0.
    out: dict[str, dict[str, int]] = {area: {diff: 0 for diff in _DIFFICULTY_LEVELS} for area in _BOARD_AREAS}

    def _ingest_move(move: Any) -> None:
        if not isinstance(move, dict):
            return
        area = _normalize_area(move.get("area"))
        if area is None:
            return
        diff = _normalize_difficulty(move.get("position_difficulty"))
        out[area][diff] += 1

    for k in _iter_kartes(kartes):
        for mv in k.get("important_moves") or ():
            _ingest_move(mv)
        for cm_list in (k.get("critical_3") or {}).values():
            if isinstance(cm_list, list):
                for cm in cm_list:
                    _ingest_move(cm)

    return out


# ---------------------------------------------------------------------------
# 3. loss_spike_windows
# ---------------------------------------------------------------------------


def detect_loss_spike_windows(
    kartes: Iterable[dict[str, Any]],
    *,
    multiplier: float = _LOSS_SPIKE_MULTIPLIER_DEFAULT,
) -> list[dict[str, Any]]:
    """Detect consecutive high-loss 10-move buckets per karte.

    The Karte JSON's ``loss_progression`` is a list of
    ``{start_move, end_move, move_count, total_loss, avg_loss,
    mistake_count}`` buckets (typically 10 moves wide). A
    **spike** is a run of consecutive buckets whose ``avg_loss``
    exceeds ``multiplier × overall_avg_loss``.

    Args:
        kartes: Iterable of karte JSON dicts.
        multiplier: Threshold multiplier applied to the overall
            average. Defaults to ``2.0`` (matches the existing
            2×-avg convention). Pass a smaller value to be more
            aggressive, larger to be stricter.

    Returns:
        A list of spike-window dicts, one per detected run::

            [
              {"game_id": "g1", "start_move": 31, "end_move": 60,
               "total_loss": 80.0, "bucket_count": 3,
               "avg_loss": 26.67},
              ...
            ]

        ``total_loss`` is the sum across the run, ``avg_loss`` the
        mean of per-bucket avg_loss values. Empty list when no
        karte has a usable ``loss_progression``.
    """
    if multiplier <= 0:
        raise ValueError(f"multiplier must be > 0, got {multiplier}")

    out: list[dict[str, Any]] = []
    for k in _iter_kartes(kartes):
        progression = k.get("loss_progression")
        if not isinstance(progression, list) or not progression:
            continue
        game_id = _game_id_for(k)

        # Filter to dict-shaped buckets; skip legacy list shapes.
        buckets: list[dict[str, Any]] = [b for b in progression if isinstance(b, dict) and "avg_loss" in b]
        if not buckets:
            continue

        # Compute the overall avg_loss as a mean of the bucket
        # avg_loss values. We intentionally do NOT use
        # ``total_loss / move_count`` here because a single game
        # with very different move counts per bucket would skew
        # the result; the mean of per-bucket avg_loss is the
        # stable measure the LLM Coach popup already surfaces.
        overall_avg = sum(float(b["avg_loss"]) for b in buckets) / len(buckets)
        threshold = overall_avg * multiplier

        # Walk the buckets once and collect runs of consecutive
        # spikes. We require at least one bucket per run, but
        # prefer to report the full run (start of first spike to
        # end of last spike) so the LLM gets a contiguous window.
        run_start_idx: int | None = None
        for i, b in enumerate(buckets):
            is_spike = float(b["avg_loss"]) > threshold
            if is_spike and run_start_idx is None:
                run_start_idx = i
            elif not is_spike and run_start_idx is not None:
                _append_spike(out, buckets, run_start_idx, i - 1, game_id)
                run_start_idx = None
        if run_start_idx is not None:
            _append_spike(out, buckets, run_start_idx, len(buckets) - 1, game_id)

    return out


def _append_spike(
    out: list[dict[str, Any]],
    buckets: list[dict[str, Any]],
    start_idx: int,
    end_idx: int,
    game_id: str,
) -> None:
    """Append one spike run to ``out`` (helper for the walker above)."""
    run = buckets[start_idx : end_idx + 1]
    total_loss = round(sum(float(b.get("total_loss", 0.0) or 0.0) for b in run), 2)
    avg_loss = round(sum(float(b.get("avg_loss", 0.0) or 0.0) for b in run) / len(run), 3)
    out.append(
        {
            "game_id": game_id,
            "start_move": int(buckets[start_idx].get("start_move", 0) or 0),
            "end_move": int(buckets[end_idx].get("end_move", 0) or 0),
            "total_loss": total_loss,
            "bucket_count": len(run),
            "avg_loss": avg_loss,
        }
    )


# ---------------------------------------------------------------------------
# 4. representative_moves_by_tag
# ---------------------------------------------------------------------------


def group_representative_moves_by_tag(
    kartes: Iterable[dict[str, Any]],
    *,
    top_n: int = 2,
) -> dict[str, list[dict[str, Any]]]:
    """For each ``primary_tag``, return the top-N highest-loss moves
    across all kartes.

    Sources moves from, in order:

    1. ``important_moves`` (single-game Karte field, the canonical
       place per-move data lives)
    2. ``critical_3.<color>`` (Phase 248-B2: also carries
       ``area`` / ``position_difficulty`` / ``meaning_tag_label`` /
       ``game_phase``)
    3. ``top_mistakes`` (only when the karte happens to also carry
       one — usually the summary path, not the per-game path)

    Each move must have a non-null ``primary_tag`` to be grouped;
    moves with ``primary_tag is None`` are skipped (the LLM cannot
    ground a tag-less move in the symptom taxonomy).

    Args:
        kartes: Iterable of karte JSON dicts.
        top_n: Maximum moves to keep per tag. ``2`` matches the
            user spec ("loss上位1-2件"). Pass ``0`` to keep all
            moves (caller is responsible for size).

    Returns:
        A dict keyed by ``primary_tag`` value::

            {
                "life_death_error": [
                    {"coords": "Q16", "move_number": 87,
                     "loss": 19.0, "game_id": "g1",
                     "meaning_tag_label": "死活ミス"},
                    ...
                ],
                "reading_failure": [...],
                ...
            }

        Tags are ordered by total loss of their first (worst) move,
        so the most severe tag appears first when callers iterate.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}

    def _add(move: Any, game_id: str) -> None:
        if not isinstance(move, dict):
            return
        tag = move.get("primary_tag")
        if not isinstance(tag, str) or not tag:
            return
        # Prefer loss_clamped / score_loss / points_lost; fall back
        # to 0.0 so the move still shows up under the tag (just
        # ranked last). We do not use raw ``points_lost`` to keep
        # ordering stable across kartes that predate Phase 158-I.
        # PR-06 (M8): use ``is None`` checks rather than truthy ``or``
        # so a legitimate ``0.0`` loss is preserved instead of falling
        # through to the next field (the same pattern was fixed for
        # summary_json_export in Phase 159A).
        loss: float | int | None = move.get("loss_clamped")
        if loss is None:
            loss = move.get("score_loss")
        if loss is None:
            loss = move.get("points_lost")
        if loss is None:
            loss = 0.0
        try:
            loss_f = float(loss)
        except (TypeError, ValueError):
            loss_f = 0.0
        entry = {
            "coords": move.get("coords") or move.get("gtp_coord") or "",
            "move_number": int(move.get("move_number") or 0),
            "loss": round(loss_f, 2),
            "game_id": game_id,
            "meaning_tag_label": move.get("meaning_tag_label"),
        }
        # Phase 270: ``game_id`` is informational; we keep
        # ``coords`` and ``move_number`` for LLM grounding.
        grouped.setdefault(tag, []).append(entry)

    for k in _iter_kartes(kartes):
        game_id = _game_id_for(k)
        for mv in k.get("important_moves") or ():
            _add(mv, game_id)
        for cm_list in (k.get("critical_3") or {}).values():
            if isinstance(cm_list, list):
                for cm in cm_list:
                    _add(cm, game_id)
        for tm in k.get("top_mistakes") or ():
            _add(tm, game_id)

    # Sort each tag bucket by loss desc, then move_number asc for
    # stability, then trim to ``top_n`` (0 = no cap).
    for tag, entries in grouped.items():
        entries.sort(key=lambda e: (-e["loss"], e["move_number"]))
        if top_n > 0:
            grouped[tag] = entries[:top_n]

    # Re-order the outer dict by descending worst-move loss so the
    # most severe tag appears first.
    ordered = dict(
        sorted(
            grouped.items(),
            key=lambda kv: (-(kv[1][0]["loss"] if kv[1] else 0.0), kv[0]),
        )
    )
    return ordered


# ---------------------------------------------------------------------------
# 5. data_quality_aggregate
# ---------------------------------------------------------------------------


def aggregate_data_quality(
    kartes: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Average ``data_quality`` stats across kartes.

    Aggregates the following numeric fields (others are
    surfaced as the per-game "majority vote" or last-seen value):

    - ``avg_visits`` (mean)
    - ``reliability_pct`` (mean)
    - ``coverage_pct`` (mean)
    - ``total_moves`` (sum)
    - ``moves_with_visits`` (sum)
    - ``reliable_count`` (sum)
    - ``low_confidence_count`` (sum)

    The ``confidence_level`` field is reported as the most-seen
    value across kartes ("high" / "medium" / "low"). When there is
    a tie, "medium" wins (the safe middle).

    Args:
        kartes: Iterable of karte JSON dicts.

    Returns:
        A flat dict. Returns ``{"games_count": 0, ...}`` with all
        numeric fields at 0 when no karte has a ``data_quality``
        block.
    """
    games_count = 0
    sum_avg_visits = 0.0
    sum_reliability_pct = 0.0
    sum_coverage_pct = 0.0
    sum_total_moves = 0
    sum_moves_with_visits = 0
    sum_reliable_count = 0
    sum_low_confidence_count = 0
    confidence_counts: dict[str, int] = {}

    for k in _iter_kartes(kartes):
        dq = k.get("data_quality")
        if not isinstance(dq, dict):
            continue
        games_count += 1
        # Numeric fields — accept int / float, default 0.
        sum_avg_visits += float(dq.get("avg_visits") or 0)
        sum_reliability_pct += float(dq.get("reliability_pct") or 0.0)
        sum_coverage_pct += float(dq.get("coverage_pct") or 0.0)
        sum_total_moves += int(dq.get("total_moves") or 0)
        sum_moves_with_visits += int(dq.get("moves_with_visits") or 0)
        sum_reliable_count += int(dq.get("reliable_count") or 0)
        sum_low_confidence_count += int(dq.get("low_confidence_count") or 0)
        # Confidence level — string vote.
        cl = dq.get("confidence_level")
        if isinstance(cl, str) and cl:
            confidence_counts[cl] = confidence_counts.get(cl, 0) + 1

    def _mean(total: float, n: int) -> float:
        return round(total / n, 2) if n > 0 else 0.0

    # Resolve confidence_level: most-seen wins. On a tie, always
    # prefer "medium" as the safe middle ground — "high" / "low"
    # both overstate the signal when the votes split evenly, and
    # the LLM should not be told the player is a strong / weak
    # learner based on a coin-flip tie. This is the Phase 270
    # design decision: ambiguous confidence == "medium".
    if confidence_counts:
        max_count = max(confidence_counts.values())
        leaders = [k for k, v in confidence_counts.items() if v == max_count]
        confidence_level = leaders[0] if len(leaders) == 1 else "medium"
    else:
        confidence_level = "unknown"

    return {
        "games_count": games_count,
        "avg_visits": _mean(sum_avg_visits, games_count),
        "reliability_pct": _mean(sum_reliability_pct, games_count),
        "coverage_pct": _mean(sum_coverage_pct, games_count),
        "total_moves": sum_total_moves,
        "moves_with_visits": sum_moves_with_visits,
        "reliable_count": sum_reliable_count,
        "low_confidence_count": sum_low_confidence_count,
        "confidence_level": confidence_level,
    }


# ---------------------------------------------------------------------------
# 6. meaning_tag_label_map
# ---------------------------------------------------------------------------


def build_meaning_tag_label_map(
    kartes: Iterable[dict[str, Any]],
) -> dict[str, str]:
    """Build ``primary_tag`` → ``meaning_tag_label`` mapping.

    Sources labels from karte ``important_moves`` /
    ``critical_3`` entries first (per-game Japanese labels as the
    user saw them). Falls back to the central
    :data:`MEANING_TAG_REGISTRY` for tags the kartes did not see
    (so the LLM always gets a complete mapping).

    Args:
        kartes: Iterable of karte JSON dicts.

    Returns:
        Flat dict ``{primary_tag: japanese_label, ...}``. Empty
        when no karte has any move with a non-null
        ``meaning_tag_label`` AND the registry import fails.
    """
    out: dict[str, str] = {}
    for k in _iter_kartes(kartes):
        for mv in k.get("important_moves") or ():
            if not isinstance(mv, dict):
                continue
            tag = mv.get("primary_tag")
            label = mv.get("meaning_tag_label")
            if isinstance(tag, str) and tag and isinstance(label, str) and label:
                out.setdefault(tag, label)
        for cm_list in (k.get("critical_3") or {}).values():
            if isinstance(cm_list, list):
                for cm in cm_list:
                    if not isinstance(cm, dict):
                        continue
                    tag = cm.get("meaning_tag_id") or cm.get("primary_tag")
                    label = cm.get("meaning_tag_label")
                    if isinstance(tag, str) and tag and isinstance(label, str) and label:
                        out.setdefault(tag, label)

    # Fall back to the registry for any tag the kartes did not
    # surface. This is the standard Phase 46 registry — the labels
    # match what ``get_meaning_tag_label_safe(tag, "ja")`` would
    # return at runtime.
    try:
        from katrain.core.analysis.meaning_tags.registry import (
            MEANING_TAG_REGISTRY,
        )

        for tag_id, definition in MEANING_TAG_REGISTRY.items():
            out.setdefault(str(tag_id.value), definition.ja_label)
    except Exception:
        logger.debug("meaning_tags registry import failed in karte aggregator", exc_info=True)

    return out


# ---------------------------------------------------------------------------
# 7. aggregate_kartes — the one-shot entry point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AggregatedKarteView:
    """Bundle of all 6 aggregation results for the LLM Coach.

    Attributes:
        reason_tags_by_color: Output of
            :func:`aggregate_reason_tags_by_color`.
        area_difficulty_matrix: Output of
            :func:`aggregate_area_difficulty`.
        loss_spike_windows: Output of
            :func:`detect_loss_spike_windows`.
        representative_moves_by_tag: Output of
            :func:`group_representative_moves_by_tag`.
        data_quality_aggregate: Output of
            :func:`aggregate_data_quality`.
        meaning_tag_label_map: Output of
            :func:`build_meaning_tag_label_map`.
        games_count: Number of karte JSONs that contributed at
            least one field. ``0`` for an empty input.
        schema_version: Always ``"3.6"`` for this Phase 270 view.
    """

    reason_tags_by_color: dict[str, dict[str, int]]
    area_difficulty_matrix: dict[str, dict[str, int]]
    loss_spike_windows: list[dict[str, Any]]
    representative_moves_by_tag: dict[str, list[dict[str, Any]]]
    data_quality_aggregate: dict[str, Any]
    meaning_tag_label_map: dict[str, str]
    games_count: int
    schema_version: str = "3.6"


def aggregate_kartes(
    kartes: Iterable[dict[str, Any]],
    *,
    loss_spike_multiplier: float = _LOSS_SPIKE_MULTIPLIER_DEFAULT,
    representative_top_n: int = 2,
) -> AggregatedKarteView:
    """One-shot entry point: aggregate multiple karte JSONs.

    Args:
        kartes: Iterable of karte JSON dicts. Non-karte dicts
            (summary JSONs, etc.) are filtered out by
            :func:`_iter_kartes`.
        loss_spike_multiplier: Forwarded to
            :func:`detect_loss_spike_windows`.
        representative_top_n: Forwarded to
            :func:`group_representative_moves_by_tag`.

    Returns:
        :class:`AggregatedKarteView` with all 6 fields populated.
    """
    kartes_list = list(_iter_kartes(kartes))
    return AggregatedKarteView(
        reason_tags_by_color=aggregate_reason_tags_by_color(kartes_list),
        area_difficulty_matrix=aggregate_area_difficulty(kartes_list),
        loss_spike_windows=detect_loss_spike_windows(kartes_list, multiplier=loss_spike_multiplier),
        representative_moves_by_tag=group_representative_moves_by_tag(kartes_list, top_n=representative_top_n),
        data_quality_aggregate=aggregate_data_quality(kartes_list),
        meaning_tag_label_map=build_meaning_tag_label_map(kartes_list),
        games_count=len(kartes_list),
    )


__all__ = [
    "AggregatedKarteView",
    "aggregate_kartes",
    "aggregate_reason_tags_by_color",
    "aggregate_area_difficulty",
    "detect_loss_spike_windows",
    "group_representative_moves_by_tag",
    "aggregate_data_quality",
    "build_meaning_tag_label_map",
]
