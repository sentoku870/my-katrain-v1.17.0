"""PR-04a regression tests for player-colour-scoped symptom detection.

PR-04a (H5): symptom detection previously flattened both colours'
``mistake_streaks`` and ``weaknesses``, so an opponent's mistake could
be reported as the user's symptom. The fix threads a ``player_color``
kwarg through ``detect_symptoms_from_karte`` and the helpers it calls
(``build_symptom_context_from_karte``, ``_all_streaks``, the
``extract_*`` streak helpers, ``_symptom_ids_from_streaks``,
``_symptom_ids_from_weakness_categories``).

``player_color="black"`` / ``"white"`` scope detection to one side.
``None`` keeps the legacy "both colours" behaviour. ``"invalid"``
silently falls back to both colours (defensive — matches the
behaviour the rest of the coach code already uses for unknown
colours).
"""

from __future__ import annotations

from typing import Any

import pytest

from katrain.core.coach.karte_detector import detect_symptoms_from_karte
from katrain.core.coach.karte_extractors import (
    _all_streaks,
    extract_avg_streak_loss,
    extract_longest_streak,
    extract_streak_count,
    extract_total_streak_loss,
)
from katrain.core.coach.symptom_index import SymptomContext


def _make_karte(
    black_streaks: list[dict[str, Any]] | None = None,
    white_streaks: list[dict[str, Any]] | None = None,
    black_weaknesses: list[dict[str, Any]] | None = None,
    white_weaknesses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a minimal Karte shape that exercises streak + weakness paths."""
    return {
        "meta": {"schema_version": "3.5"},
        "weaknesses": {
            "black": black_weaknesses or [],
            "white": white_weaknesses or [],
        },
        "mistake_streaks": {
            "black": black_streaks or [],
            "white": white_streaks or [],
        },
    }


class TestAllStreaksColorFilter:
    def test_both_colours_default(self) -> None:
        karte = _make_karte(
            black_streaks=[{"move_count": 3, "total_loss": 5.0}],
            white_streaks=[{"move_count": 4, "total_loss": 6.0}],
        )
        streaks = _all_streaks(karte)
        assert len(streaks) == 2

    def test_black_only(self) -> None:
        karte = _make_karte(
            black_streaks=[{"move_count": 3, "total_loss": 5.0}],
            white_streaks=[{"move_count": 4, "total_loss": 6.0}],
        )
        streaks = _all_streaks(karte, player_color="black")
        assert len(streaks) == 1
        assert streaks[0]["move_count"] == 3

    def test_white_only(self) -> None:
        karte = _make_karte(
            black_streaks=[{"move_count": 3, "total_loss": 5.0}],
            white_streaks=[{"move_count": 4, "total_loss": 6.0}],
        )
        streaks = _all_streaks(karte, player_color="white")
        assert len(streaks) == 1
        assert streaks[0]["move_count"] == 4

    def test_unknown_color_falls_back_to_both(self) -> None:
        karte = _make_karte(
            black_streaks=[{"move_count": 3, "total_loss": 5.0}],
            white_streaks=[{"move_count": 4, "total_loss": 6.0}],
        )
        streaks = _all_streaks(karte, player_color="nonsense")
        assert len(streaks) == 2


class TestStreakExtractorsAreScoped:
    def test_longest_streak_is_scoped(self) -> None:
        karte = _make_karte(
            black_streaks=[{"move_count": 2, "total_loss": 1.0}],
            white_streaks=[{"move_count": 5, "total_loss": 10.0}],
        )
        assert extract_longest_streak(karte) == 5  # both colours
        assert extract_longest_streak(karte, player_color="black") == 2
        assert extract_longest_streak(karte, player_color="white") == 5

    def test_total_streak_loss_is_scoped(self) -> None:
        karte = _make_karte(
            black_streaks=[{"move_count": 2, "total_loss": 1.0}],
            white_streaks=[{"move_count": 3, "total_loss": 7.0}],
        )
        assert extract_total_streak_loss(karte) == pytest.approx(8.0)
        assert extract_total_streak_loss(karte, player_color="black") == pytest.approx(1.0)
        assert extract_total_streak_loss(karte, player_color="white") == pytest.approx(7.0)

    def test_streak_count_is_scoped(self) -> None:
        karte = _make_karte(
            black_streaks=[
                {"move_count": 2, "total_loss": 1.0},
                {"move_count": 3, "total_loss": 1.0},
            ],
            white_streaks=[{"move_count": 3, "total_loss": 7.0}],
        )
        assert extract_streak_count(karte) == 3
        assert extract_streak_count(karte, player_color="black") == 2
        assert extract_streak_count(karte, player_color="white") == 1

    def test_avg_streak_loss_is_scoped(self) -> None:
        karte = _make_karte(
            black_streaks=[{"move_count": 2, "total_loss": 4.0}],
            white_streaks=[{"move_count": 3, "total_loss": 8.0}],
        )
        # both colours: average of [4.0, 8.0] = 6.0
        assert extract_avg_streak_loss(karte) == pytest.approx(6.0)
        assert extract_avg_streak_loss(karte, player_color="black") == pytest.approx(4.0)
        assert extract_avg_streak_loss(karte, player_color="white") == pytest.approx(8.0)


class TestSymptomContextCarriesScopedStreaks:
    def test_context_has_scoped_streak_fields(self) -> None:
        from katrain.core.coach.karte_symptom_context import (
            build_symptom_context_from_karte,
        )

        karte = _make_karte(
            black_streaks=[{"move_count": 4, "total_loss": 6.0}],
            white_streaks=[{"move_count": 2, "total_loss": 1.0}],
        )
        ctx = build_symptom_context_from_karte(karte, player_color="black")
        assert isinstance(ctx, SymptomContext)
        assert ctx.player_color == "black"
        assert ctx.longest_streak == 4
        assert ctx.total_streak_loss == pytest.approx(6.0)
        assert ctx.streak_count == 1
        assert ctx.avg_streak_loss == pytest.approx(6.0)

    def test_context_default_is_both_colours(self) -> None:
        from katrain.core.coach.karte_symptom_context import (
            build_symptom_context_from_karte,
        )

        karte = _make_karte(
            black_streaks=[{"move_count": 4, "total_loss": 6.0}],
            white_streaks=[{"move_count": 2, "total_loss": 1.0}],
        )
        ctx = build_symptom_context_from_karte(karte)
        assert ctx.player_color is None
        # combined longest = 4, combined total = 7, combined count = 2
        assert ctx.longest_streak == 4
        assert ctx.total_streak_loss == pytest.approx(7.0)
        assert ctx.streak_count == 2
        assert ctx.avg_streak_loss == pytest.approx(3.5)


class TestDetectSymptomsAcceptsPlayerColor:
    def test_detect_still_works_without_filter(self) -> None:
        """No-colour call must remain a no-op backwards-compat path."""
        karte = _make_karte(
            black_streaks=[{"move_count": 5, "total_loss": 12.0}],
        )
        # Should not raise even though SymptomContext is now scoped.
        detect_symptoms_from_karte(karte)

    def test_detect_with_color_runs(self) -> None:
        karte = _make_karte(
            black_streaks=[{"move_count": 5, "total_loss": 12.0}],
        )
        # smoke: should also not raise when a colour is supplied.
        detect_symptoms_from_karte(karte, player_color="black")
