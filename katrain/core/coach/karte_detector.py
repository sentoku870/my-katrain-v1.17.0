"""Phase 215: Karte-aware symptom detection (orchestrator).

Builds a SymptomContext from a real Karte JSON so that
``detect_auto_symptoms`` can be run end-to-end against actual data.

This module bridges the gap between:
- The aggregate Karte JSON produced by ``json_export.build_karte_json``
  (top-level weaknesses / mistake_streaks / critical_3 / reason_tags)
- The per-move SymptomContext the symptom_index detectors expect

Functions:
- ``build_symptom_context_from_karte(karte)`` → SymptomContext
- ``detect_symptoms_from_karte(karte)`` → tuple[SymptomId, ...]
- ``extract_avg_points_lost(karte)`` → float | None
- ``extract_weakness_concentration(karte)`` → float | None

All functions are pure / Kivy-free.

Implementation note (Phase C refactor):

The 30 top-level functions that previously lived in this module have
been split into two cohesive sub-modules to narrow the blast radius
of future changes:

- :mod:`katrain.coach.karte_extractors` — pure ``extract_*`` helpers
  that read Karte JSON fields and return primitive statistics.
- :mod:`katrain.coach.karte_symptom_context` — ``_collect_*`` /
  ``_infer_*`` / ``_board_size`` helpers, ``build_symptom_context_from_karte``,
  and the per-category ``_symptom_ids_from_*`` mapping helpers.
- :mod:`katrain.coach.karte_detector` (this module) — the top-level
  :func:`detect_symptoms_from_karte` orchestrator and re-exports for
  backward compatibility.

Backward compatibility:

Every public symbol previously importable from
``katrain.coach.karte_detector`` remains importable from the same
path. ``tests/test_coach_karte_detector.py`` and other callers do not
need to update their imports.
"""

from __future__ import annotations

from typing import Any

from katrain.core.coach.karte_extractors import (  # noqa: F401 (re-export)
    extract_avg_points_lost,
    extract_avg_streak_loss,
    extract_avg_winrate_lost,
    extract_consecutive_loss_run,
    extract_critical_move_count,
    extract_game_count,
    extract_good_move_count,
    extract_longest_streak,
    extract_max_overall_difficulty,
    extract_max_score_stdev,
    extract_max_winrate_drop,
    extract_streak_count,
    extract_total_streak_loss,
    extract_weakness_concentration,
    extract_winrate_scorelead_correlation,
    extract_winrate_scorelead_pairs,
)
from katrain.core.coach.karte_symptom_context import (  # noqa: F401 (re-export)
    _board_size,
    _collect_hint_categories,
    _collect_meaning_tags,
    _infer_current_phase,
    _is_endgame_karte,
    _move_number_range,
    _symptom_ids_from_aggregate_patterns,
    _symptom_ids_from_streaks,
    _symptom_ids_from_weakness_categories,
    build_symptom_context_from_karte,
    detect_position_evaluation,
)
from katrain.core.coach.symptom_index import (
    SymptomId,
    detect_auto_symptoms,
)


def detect_symptoms_from_karte(
    karte: dict[str, Any],
    *,
    player_color: str | None = None,
) -> tuple[SymptomId, ...]:
    """Run auto-detection against the karte's derived SymptomContext.

    Returns the union of:
    (a) Symptoms fired by SymptomContext-based detectors (per-move heuristics)
    (b) Symptoms directly extracted from weakness[*].category
    (c) Streak-based symptoms from mistake_streaks + loss_progression (Phase 216)
    (d) Aggregate-pattern symptoms (Phase 217: POSITION_EVALUATION via
        winrate/scoreLead correlation)

    Order is the symptom-table order, which is stable across calls.

    PR-04a (H5): ``player_color`` (``"black"`` / ``"white"`` /
    ``None``) scopes the detection to one colour. ``None`` keeps the
    legacy "both colours" behaviour. Use ``"black"`` / ``"white"`` so
    opponent mistakes are not reported as the user's symptoms.
    """
    ctx = build_symptom_context_from_karte(karte, player_color=player_color)
    per_move = set(detect_auto_symptoms(ctx))
    from_categories = set(_symptom_ids_from_weakness_categories(karte, player_color=player_color))
    from_streaks = set(_symptom_ids_from_streaks(karte, player_color=player_color))
    from_aggregate = set(_symptom_ids_from_aggregate_patterns(karte))
    combined = per_move | from_categories | from_streaks | from_aggregate
    # Stable ordering by table order
    table_order = list(SymptomId)
    combined_sorted = tuple(sid for sid in table_order if sid in combined)
    return combined_sorted


__all__ = [
    "extract_avg_points_lost",
    "extract_avg_winrate_lost",
    "extract_max_winrate_drop",
    "extract_max_score_stdev",
    "extract_max_overall_difficulty",
    "extract_good_move_count",
    "extract_critical_move_count",
    "extract_weakness_concentration",
    "extract_game_count",
    "build_symptom_context_from_karte",
    "detect_symptoms_from_karte",
]
