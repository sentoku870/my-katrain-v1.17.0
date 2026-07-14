"""Phase 218: Tests for calibration fixtures.

Each GoldenFixture is run through ``detect_symptoms_from_karte`` and
compared against ``expected_symptom_ids``. These tests document detector
behaviour and pin thresholds against regressions.
"""

from __future__ import annotations

import pytest

from katrain.core.coach.calibration_fixtures import (
    ALL_FIXTURES,
    GoldenFixture,
    get_fixture,
    list_fixture_names,
)
from katrain.core.coach.karte_detector import detect_symptoms_from_karte
from katrain.core.coach.symptom_index import SymptomId


# --- Sanity: fixtures themselves ---


class TestFixturesSanity:
    def test_count(self):
        assert len(ALL_FIXTURES) == 8

    def test_all_names_unique(self):
        names = list(ALL_FIXTURES.keys())
        assert len(names) == len(set(names))

    def test_all_fixtures_are_dataclass(self):
        for fix in ALL_FIXTURES.values():
            assert isinstance(fix, GoldenFixture)

    @pytest.mark.parametrize("name", list_fixture_names())
    def test_each_fixture_has_expected(self, name):
        fix = ALL_FIXTURES[name]
        assert fix.expected_symptom_ids is not None
        assert isinstance(fix.expected_symptom_ids, tuple)
        # All expected ids must be valid SymptomId values
        for sid in fix.expected_symptom_ids:
            assert isinstance(sid, SymptomId)

    def test_get_fixture_returns_none_for_missing(self):
        assert get_fixture("this_does_not_exist_xyz") is None

    def test_get_fixture_returns_for_known(self):
        fix = get_fixture("perfect_game")
        assert fix is not None
        assert fix.name == "perfect_game"

    def test_list_fixture_names_returns_tuple(self):
        names = list_fixture_names()
        assert isinstance(names, tuple)
        assert len(names) == 8


# --- Each fixture produces the documented symptoms ---


@pytest.mark.parametrize(
    "fixture_name,expected_ids",
    [
        ("perfect_game", set()),
        ("single_atari_mistake", {SymptomId.ATARI_BLINDNESS}),
        ("reckless_overplay", {SymptomId.OVERPLAY_RECKLESS_ATTACK}),
        ("long_mistake_streak", {SymptomId.OVERFIGHT}),
        ("many_small_streaks", {SymptomId.SMALL_MOVE_ADDICTION}),
        ("tilt_chain_disaster", {SymptomId.TILT_CHAIN}),
        ("tilt_discouragement", {SymptomId.TILT_DISCOURAGEMENT}),
        ("strong_correlation", set()),
    ],
)
def test_fixture_detects_expected(fixture_name, expected_ids):
    fix = ALL_FIXTURES[fixture_name]
    fired = set(detect_symptoms_from_karte(fix.karte))
    assert fired == expected_ids, (
        f"Fixture '{fixture_name}': expected {expected_ids}, got {fired}"
    )


class TestFixtureDocumentation:
    """Verify that each fixture's description matches its content."""

    @pytest.mark.parametrize("name", list_fixture_names())
    def test_fixture_has_description(self, name):
        fix = ALL_FIXTURES[name]
        assert fix.description
        assert len(fix.description) > 20

    @pytest.mark.parametrize("name", list_fixture_names())
    def test_fixture_has_karte_json(self, name):
        fix = ALL_FIXTURES[name]
        assert fix.karte
        assert "schema_version" in fix.karte

    def test_perfect_game_no_symptoms(self):
        fix = ALL_FIXTURES["perfect_game"]
        fired = detect_symptoms_from_karte(fix.karte)
        assert fired == ()