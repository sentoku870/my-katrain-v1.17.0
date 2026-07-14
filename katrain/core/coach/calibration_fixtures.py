"""Phase 218: Golden test fixtures for coach pipeline regression testing.

Each fixture is a small Karte JSON with a documented symptom profile.
``expected_symptom_ids`` lists the SymptomIds that should fire when
``detect_symptoms_from_karte`` runs against the fixture.

These fixtures:
1. Document detector behaviour (which symptoms fire on which patterns)
2. Pin thresholds so accidental regressions are caught immediately
3. Provide a basis for future threshold tuning (Phase 219)

Usage::

    from katrain.core.coach.calibration_fixtures import ALL_FIXTURES
    for name, fixture in ALL_FIXTURES.items():
        fired = detect_symptoms_from_karte(fixture.karte)
        assert set(fired) == set(fixture.expected_symptom_ids)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from katrain.core.coach.symptom_index import SymptomId


@dataclass(frozen=True)
class GoldenFixture:
    """A Karte JSON with documented expected detector output.

    Attributes:
        name: Short identifier (e.g. "perfect_game", "tilt_disaster").
        description: Human-readable explanation of what the fixture tests.
        karte: A Karte JSON-shaped dict.
        expected_symptom_ids: Tuple of SymptomIds expected to fire.
        tolerance_notes: Phase 219+ notes on which thresholds to tune.
    """

    name: str
    description: str
    karte: dict[str, Any]
    expected_symptom_ids: tuple[SymptomId, ...]
    tolerance_notes: str = ""


# --- Fixture 1: Perfect game --


_PERFECT_GAME = GoldenFixture(
    name="perfect_game",
    description=(
        "Clean game with no mistakes. No symptoms should fire. "
        "Validates that detectors don't false-positive on ideal input."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {"board_size": 19, "game_count": 1, "players": {"black": "P1", "white": "P2"}},
        "summary": {"total_moves": 200, "total_points_lost": {"black": 0.0, "white": 0.0}},
        "important_moves": [],
        "weaknesses": {"black": [], "white": []},
        "mistake_streaks": {"black": [], "white": []},
        "loss_progression": [{"mistake_count": 0} for _ in range(20)],
    },
    expected_symptom_ids=(),
    tolerance_notes="Empty weaknesses / streaks / loss_progression.",
)


# --- Fixture 2: Atari blindness only --


_ATARI_FIXTURE = GoldenFixture(
    name="single_atari_mistake",
    description=(
        "Weakness category 'atari_blindness' only — no important_moves, "
        "no streaks. Should fire ONLY ATARI_BLINDNESS via weakness category "
        "mapping (Phase 215)."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {"board_size": 19, "game_count": 1},
        "summary": {"total_moves": 50},
        "important_moves": [],
        "weaknesses": {
            "black": [{"category": "atari_blindness", "total_loss": 1.5}],
            "white": [],
        },
        "mistake_streaks": {"black": [], "white": []},
        "loss_progression": [
            {"mistake_count": 0}, {"mistake_count": 0}, {"mistake_count": 0},
        ],
    },
    expected_symptom_ids=(SymptomId.ATARI_BLINDNESS,),
    tolerance_notes="Pure weakness category test; no per-move signals.",
)


# --- Fixture 3: Big overplay with high scoreStdev --


_OVERPLAY_FIXTURE = GoldenFixture(
    name="reckless_overplay",
    description=(
        "OVERPLAY tag + score_stdev > 1.5 → OVERPLAY_RECKLESS_ATTACK "
        "should fire via per-move SymptomContext detector."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {"board_size": 19, "game_count": 1},
        "summary": {"total_moves": 100},
        "important_moves": [
            {
                "meaning_tag_id": "overplay",
                "points_lost": 4.0,
                "winrate_lost": 0.10,
                "move_number": 80,
                "score_stdev": 2.0,
            }
        ],
        "weaknesses": {
            "black": [{"category": "overplay_reckless_attack", "total_loss": 4.0}],
            "white": [],
        },
        "mistake_streaks": {"black": [], "white": []},
        "loss_progression": [{"mistake_count": 1}, {"mistake_count": 0}],
    },
    expected_symptom_ids=(SymptomId.OVERPLAY_RECKLESS_ATTACK,),
    tolerance_notes="OVERPLAY + score_stdev > 1.5 triggers per-move detector.",
)


# --- Fixture 4: Long streak (overfight) --


_OVERFIGHT_FIXTURE = GoldenFixture(
    name="long_mistake_streak",
    description=(
        "Consecutive mistake streak of 4 moves. No other symptoms "
        "should fire — isolated streak detector test (Phase 216)."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {"board_size": 19, "game_count": 1},
        "summary": {"total_moves": 100},
        "important_moves": [],
        "weaknesses": {"black": [], "white": []},
        "mistake_streaks": {
            "black": [
                {
                    "start_move": 50,
                    "end_move": 54,
                    "move_count": 4,
                    "total_loss": 12.0,
                    "avg_loss": 3.0,
                    "moves": [],
                }
            ],
            "white": [],
        },
        "loss_progression": [
            {"mistake_count": 0}, {"mistake_count": 0}, {"mistake_count": 0},
        ],
    },
    expected_symptom_ids=(SymptomId.OVERFIGHT,),
    tolerance_notes="longest_streak >= 3 triggers OVERFIGHT (Phase 216).",
)


# --- Fixture 5: Many small streaks (small_move_addiction) --


_SMALL_MOVE_ADDICTION_FIXTURE = GoldenFixture(
    name="many_small_streaks",
    description=(
        "Five small mistake streaks, isolated from loss_run and "
        "total_streak_loss thresholds. Should fire ONLY "
        "SMALL_MOVE_ADDICTION (Phase 216)."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {"board_size": 19, "game_count": 1},
        "summary": {"total_moves": 200},
        "important_moves": [],
        "weaknesses": {"black": [], "white": []},
        "mistake_streaks": {
            "black": [
                # 5 small streaks; total_loss is small enough that TILT_*
                # won't fire.
                {"move_count": 2, "total_loss": 1.0},
                {"move_count": 2, "total_loss": 1.0},
                {"move_count": 2, "total_loss": 1.0},
                {"move_count": 2, "total_loss": 1.0},
                {"move_count": 2, "total_loss": 1.0},
            ],
            "white": [],
        },
        "loss_progression": [
            {"mistake_count": 0}, {"mistake_count": 0}, {"mistake_count": 0},
            {"mistake_count": 0}, {"mistake_count": 0},
        ],
    },
    expected_symptom_ids=(SymptomId.SMALL_MOVE_ADDICTION,),
    tolerance_notes=(
        "streak_count >= 5 → SMALL_MOVE_ADDICTION. "
        "TILT_* disabled by low total_streak_loss and zero loss_run."
    ),
)


# --- Fixture 6: Tilt chain --


_TILT_CHAIN_FIXTURE = GoldenFixture(
    name="tilt_chain_disaster",
    description=(
        "Many consecutive loss buckets + large total streak loss. "
        "TILT_CHAIN should fire (Phase 216)."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {"board_size": 19, "game_count": 1},
        "summary": {"total_moves": 200},
        "important_moves": [],
        "weaknesses": {"black": [], "white": []},
        "mistake_streaks": {
            "black": [
                # streak_count=1, longest_streak=2 to avoid OVERFIGHT/SMALL_MOVE_ADDICTION
                {"move_count": 2, "total_loss": 8.0},
                {"move_count": 2, "total_loss": 8.0},
            ],
            "white": [],
        },
        "loss_progression": [
            # 4 consecutive loss buckets → loss_run = 4
            {"mistake_count": 2}, {"mistake_count": 1}, {"mistake_count": 3},
            {"mistake_count": 2}, {"mistake_count": 0}, {"mistake_count": 0},
        ],
    },
    expected_symptom_ids=(SymptomId.TILT_CHAIN,),
    tolerance_notes="total_streak_loss >= 15 + loss_run >= 4.",
)


# --- Fixture 7: Tilt discouragement --


_TILT_DISCOURAGEMENT_FIXTURE = GoldenFixture(
    name="tilt_discouragement",
    description=(
        "Long consecutive loss run + high avg streak loss. "
        "TILT_DISCOURAGEMENT should fire (Phase 216)."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {"board_size": 19, "game_count": 1},
        "summary": {"total_moves": 200},
        "important_moves": [],
        "weaknesses": {"black": [], "white": []},
        "mistake_streaks": {
            "black": [
                # 1 streak of 2 moves with total_loss=8.0 → avg_streak_loss=8.0
                # total_streak_loss=8.0 < 15 → TILT_CHAIN doesn't fire
                # move_count=2 < 3 → OVERFIGHT doesn't fire
                {"move_count": 2, "total_loss": 8.0},
            ],
            "white": [],
        },
        "loss_progression": [
            # 5 consecutive loss buckets → loss_run = 5
            {"mistake_count": 2}, {"mistake_count": 1}, {"mistake_count": 3},
            {"mistake_count": 2}, {"mistake_count": 1},
        ],
    },
    expected_symptom_ids=(SymptomId.TILT_DISCOURAGEMENT,),
    tolerance_notes="loss_run >= 5 + avg_streak_loss >= 3.",
)


# --- Fixture 8: Winrate/scoreLead correlation test (Phase 217) --


_CORRELATION_FIXTURE = GoldenFixture(
    name="strong_correlation",
    description=(
        "Strong Pearson correlation between winrate_lost and points_lost. "
        "No aggregate-pattern symptom should fire (POSITION_EVALUATION "
        "remains placeholder for Phase 219 calibration)."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {"board_size": 19, "game_count": 1},
        "summary": {"total_moves": 200},
        "important_moves": [
            {"winrate_lost": 0.05, "points_lost": 1.5},
            {"winrate_lost": 0.10, "points_lost": 3.0},
            {"winrate_lost": 0.20, "points_lost": 6.0},
            {"winrate_lost": 0.30, "points_lost": 9.0},
        ],
        "weaknesses": {"black": [], "white": []},
        "mistake_streaks": {"black": [], "white": []},
        "loss_progression": [{"mistake_count": 0} for _ in range(20)],
    },
    expected_symptom_ids=(),
    tolerance_notes=(
        "Strong positive correlation → no POSITION_EVALUATION. "
        "Used to validate Phase 217 placeholder stays quiet."
    ),
)


# --- Public API ---


ALL_FIXTURES: dict[str, GoldenFixture] = {
    fixture.name: fixture
    for fixture in (
        _PERFECT_GAME,
        _ATARI_FIXTURE,
        _OVERPLAY_FIXTURE,
        _OVERFIGHT_FIXTURE,
        _SMALL_MOVE_ADDICTION_FIXTURE,
        _TILT_CHAIN_FIXTURE,
        _TILT_DISCOURAGEMENT_FIXTURE,
        _CORRELATION_FIXTURE,
    )
}


def get_fixture(name: str) -> GoldenFixture | None:
    """Return a single GoldenFixture by name, or None if missing."""
    return ALL_FIXTURES.get(name)


def list_fixture_names() -> tuple[str, ...]:
    """Return all fixture names in stable order."""
    return tuple(ALL_FIXTURES.keys())


__all__ = [
    "GoldenFixture",
    "ALL_FIXTURES",
    "get_fixture",
    "list_fixture_names",
] 