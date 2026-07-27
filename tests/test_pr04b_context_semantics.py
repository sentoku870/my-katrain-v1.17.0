"""PR-04b regression tests for SymptomContext field semantics.

PR-04b (H6): ``build_symptom_context_from_karte`` previously wrote the
game-average ``points_lost`` / ``winrate_lost`` into the per-move
fields of ``SymptomContext``. The SymptomContext docstring says those
fields are "current move's pointsLost / winrate drop", so the average
semantic was leaking through.

The fix sets both fields to ``None`` for the Karte-derived context
(no per-move data) and keeps the average in ``avg_points_lost``.
This restores the documented contract for downstream detectors.
"""

from __future__ import annotations

from typing import Any

import pytest

from katrain.core.coach.karte_symptom_context import (
    build_symptom_context_from_karte,
)


def _karte_with_avg_points_lost(value: float) -> dict[str, Any]:
    """Build a Karte shape that yields the requested avg_points_lost.

    The extractor averages ``loss_clamped`` over ``important_moves``,
    so we populate two entries with the target average. ``winrate_lost``
    follows the same convention.
    """
    return {
        "meta": {"schema_version": "3.5"},
        "weaknesses": {"black": [], "white": []},
        "important_moves": [
            {"loss_clamped": value, "winrate_lost": 0.05},
            {"loss_clamped": value, "winrate_lost": 0.05},
        ],
    }


class TestSymptomContextPerMoveFieldsAreNone:
    def test_points_lost_is_none_for_karte_context(self) -> None:
        ctx = build_symptom_context_from_karte(_karte_with_avg_points_lost(3.5))
        assert ctx.points_lost is None, (
            "points_lost must be None for Karte-derived context (no per-move data). PR-04b (H6) regression."
        )

    def test_winrate_lost_is_none_for_karte_context(self) -> None:
        ctx = build_symptom_context_from_karte(_karte_with_avg_points_lost(3.5))
        assert ctx.winrate_lost is None

    def test_move_number_is_none_for_karte_context(self) -> None:
        # Already was None, but pin it so a future refactor doesn't
        # accidentally inject an aggregate here too.
        ctx = build_symptom_context_from_karte(_karte_with_avg_points_lost(3.5))
        assert ctx.move_number is None


class TestSymptomContextAvgFieldsArePopulated:
    def test_avg_points_lost_carries_average(self) -> None:
        ctx = build_symptom_context_from_karte(_karte_with_avg_points_lost(3.5))
        assert ctx.avg_points_lost == pytest.approx(3.5)

    def test_avg_points_lost_does_not_leak_to_points_lost(self) -> None:
        """The whole point: avg must NOT show up in per-move."""
        ctx = build_symptom_context_from_karte(_karte_with_avg_points_lost(3.5))
        assert ctx.points_lost != ctx.avg_points_lost
