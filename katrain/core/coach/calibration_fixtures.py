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

from dataclasses import dataclass
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
        "should fire via per-move SymptomContext detector. Phase 226-F "
        "(F-A) added ``current_phase`` so OVERCONCENTRATION also fires "
        "(middle phase + overplay tag)."
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
    expected_symptom_ids=(
        SymptomId.OVERPLAY_RECKLESS_ATTACK,
        SymptomId.OVERCONCENTRATION,
    ),
    tolerance_notes=(
        "OVERPLAY + score_stdev > 1.5 triggers per-move detector. "
        "OVERPLAY in middle phase also triggers OVERCONCENTRATION "
        "(Phase 226-F F-A)."
    ),
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


# --- Phase 227-E: Summary fixtures ---
#
# Summary JSONs don't have per-move data, so the per-game detectors
# (Phases 215-217) don't apply. Instead, these fixtures pin:
# - ``extract_summary_weakness_patterns`` output (Phase 227-A)
# - ``validate_summary_llm_output`` behaviour (Phase 227-B)
# - ``build_summary_weakness_prompt`` rendering (Phase 227-A)
#
# The ``karte`` field here holds a multi-game Summary JSON (the field
# name is preserved for backward compatibility — historically
# fixtures were Karte-shaped).


_SUMMARY_CLEAN = GoldenFixture(
    name="summary_clean",
    description=(
        "Multi-game summary with 2 players and minimal weaknesses. "
        "No symptoms should fire — validates that summary detection "
        "doesn't false-positive on minimal input. The pattern extractor "
        "should return exactly 2 patterns (one per color)."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {
            "games_analyzed": 3,
            "games_by_type": {"even": 3, "handicapped": 0, "unknown": 0},
            "date_range": ["2026-07-10", "2026-07-12"],
        },
        "summary": {"total_games": 3, "win_rate": 0.5, "total_moves": 600},
        "phase_x_mistake": {
            "middle:mistake": 2,
        },
        "weaknesses": {
            "black": [
                {"phase": "middle", "category": "mistake", "count": 2, "total_loss": 4.0},
            ],
            "white": [
                {"phase": "middle", "category": "mistake", "count": 1, "total_loss": 2.0},
            ],
        },
        "mistake_streaks": {"black": [], "white": []},
        "loss_progression": {"all": [{"mistake_count": 0}] * 3},
        "games": [{"game_id": "g1"}, {"game_id": "g2"}, {"game_id": "g3"}],
        "players": {"sentoku870": {"rank": "4d", "win_rate": 0.5}, "Opponent1": {"rank": "3d", "win_rate": 0.5}},
    },
    expected_symptom_ids=(),
    tolerance_notes=(
        "Both colors have only 1 weakness entry each. "
        "Pattern extractor should return 2 patterns (one per color). "
        "Symptom detectors that need per-move data won't fire."
    ),
)


_SUMMARY_BLUNDER_DOMINANT = GoldenFixture(
    name="summary_blunder_dominant",
    description=(
        "Summary where one player (black) has 100% blunder rate across "
        "all games. Validates that summary prompts render the "
        "weakness patterns correctly and that the validator flags "
        "an LLM response that references nonexistent categories."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {
            "games_analyzed": 5,
            "games_by_type": {"even": 5, "handicapped": 0, "unknown": 0},
        },
        "summary": {"total_games": 5, "win_rate": 0.2, "total_moves": 1000},
        "phase_x_mistake": {
            "middle:blunder": 25,
            "opening:mistake": 8,
            "endgame:mistake": 3,
        },
        "weaknesses": {
            "black": [
                {"phase": "middle", "category": "blunder", "count": 5, "total_loss": 50.0},
                {"phase": "opening", "category": "mistake", "count": 4, "total_loss": 12.0},
                {"phase": "endgame", "category": "endgame_slip", "count": 2, "total_loss": 6.0},
            ],
            "white": [
                {"phase": "middle", "category": "mistake", "count": 3, "total_loss": 9.0},
            ],
        },
        "mistake_streaks": {"black": [{"move_count": 3, "total_loss": 20.0}], "white": []},
        "loss_progression": {"all": [{"mistake_count": 3}, {"mistake_count": 5}, {"mistake_count": 4}, {"mistake_count": 6}, {"mistake_count": 3}]},
        "players": {"sentoku870": {"rank": "4d", "win_rate": 0.2}, "Opponent1": {"rank": "3d", "win_rate": 0.8}},
    },
    expected_symptom_ids=(),
    tolerance_notes=(
        "Blunder dominates (50.0 total_loss vs 12+6+9 for others). "
        "Top pattern is 'blunder' at 100% frequency (5/5 games). "
        "Loss progression shows non-zero mistake counts in every game."
    ),
)


_SUMMARY_EMPTY_WEAKNESSES = GoldenFixture(
    name="summary_empty_weaknesses",
    description=(
        "Summary with 0 weaknesses entries. The pattern extractor "
        "should return an empty list, and the prompt body should "
        "show the placeholder text. Validates the empty-weaknesses "
        "branch of build_summary_weakness_prompt."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {
            "games_analyzed": 1,
            "games_by_type": {"even": 1, "handicapped": 0, "unknown": 0},
        },
        "summary": {"total_games": 1, "win_rate": 1.0, "total_moves": 200},
        "phase_x_mistake": {},
        "weaknesses": {"black": [], "white": []},
        "mistake_streaks": {"black": [], "white": []},
        "loss_progression": {"all": [{"mistake_count": 0}]},
        "players": {"sentoku870": {"rank": "5k", "win_rate": 1.0}},
    },
    expected_symptom_ids=(),
    tolerance_notes=(
        "No weaknesses data — pattern extractor returns []. "
        "Prompt body shows the (weakness データが見つかりません) placeholder."
    ),
)


_SUMMARY_HANDICAPPED = GoldenFixture(
    name="summary_handicapped_mix",
    description=(
        "Mixed-regime summary (even + handicapped games). Validates "
        "that the pattern extractor handles both regimes when both "
        "are present in games_by_type. The popup doesn't show "
        "per-regime stats in the prompt (Phase 227-A renders only "
        "the 'all' aggregate), but the per-game counts should still "
        "sum to games_analyzed."
    ),
    karte={
        "schema_version": "3.4",
        "meta": {
            "games_analyzed": 6,
            "games_by_type": {"even": 4, "handicapped": 2, "unknown": 0},
        },
        "summary": {"total_games": 6, "win_rate": 0.5, "total_moves": 1500},
        "phase_x_mistake": {
            "opening:mistake": 6,
            "middle:blunder": 12,
        },
        "weaknesses": {
            "black": [
                {"phase": "middle", "category": "blunder", "count": 6, "total_loss": 36.0},
                {"phase": "opening", "category": "mistake", "count": 4, "total_loss": 12.0},
            ],
            "white": [
                {"phase": "middle", "category": "blunder", "count": 3, "total_loss": 18.0},
            ],
        },
        "mistake_streaks": {"black": [], "white": []},
        "loss_progression": {"all": [{"mistake_count": 3}] * 6},
        "players": {"sentoku870": {"rank": "4d", "win_rate": 0.5}, "Opponent1": {"rank": "4d", "win_rate": 0.5}},
    },
    expected_symptom_ids=(),
    tolerance_notes=(
        "Mixed regime (4 even + 2 handicapped). "
        "Total pattern count = 3 (2 black + 1 white). "
        "Top pattern: black/middle/blunder at 100% (6/6 games)."
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
        # Phase 227-E: Summary fixtures
        _SUMMARY_CLEAN,
        _SUMMARY_BLUNDER_DOMINANT,
        _SUMMARY_EMPTY_WEAKNESSES,
        _SUMMARY_HANDICAPPED,
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
