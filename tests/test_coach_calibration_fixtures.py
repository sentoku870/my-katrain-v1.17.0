"""Phase 218 + 227-E: Tests for calibration fixtures.

Each GoldenFixture is run through ``detect_symptoms_from_karte`` and
compared against ``expected_symptom_ids``. These tests document detector
behaviour and pin thresholds against regressions.

Phase 227-E: extended with summary fixtures that pin the Phase 227-A
``extract_summary_weakness_patterns`` output and the Phase 227-B
``validate_summary_llm_output`` behaviour.
"""

from __future__ import annotations

import pytest

from katrain.core.coach.calibration_fixtures import (
    ALL_FIXTURES,
    GoldenFixture,
    get_fixture,
    list_fixture_names,
)
from katrain.core.coach.json_type import (
    extract_summary_weakness_patterns,
    is_summary,
)
from katrain.core.coach.karte_detector import detect_symptoms_from_karte
from katrain.core.coach.symptom_index import SymptomId

# --- Sanity: fixtures themselves ---


class TestFixturesSanity:
    def test_count(self):
        # Phase 227-E: 8 karte fixtures + 4 summary fixtures = 12
        assert len(ALL_FIXTURES) == 12

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
        # 8 karte + 4 summary
        assert len(names) == 12

    def test_summary_fixtures_detected_as_summary(self):
        """Phase 227-E: the 4 summary fixtures should be detected as
        ``"summary"`` by ``is_summary`` (this is the marker that tells
        the popup to switch to summary mode)."""
        for name in (
            "summary_clean",
            "summary_blunder_dominant",
            "summary_empty_weaknesses",
            "summary_handicapped_mix",
        ):
            fix = ALL_FIXTURES[name]
            assert is_summary(fix.karte), f"{name} should be detected as summary"

    def test_karte_fixtures_detected_as_not_summary(self):
        """Phase 227-E: the 8 karte fixtures should NOT be detected as
        summary (they have weaknesses + important_moves, which is the
        karte marker)."""
        for name in (
            "perfect_game",
            "single_atari_mistake",
            "reckless_overplay",
            "long_mistake_streak",
            "many_small_streaks",
            "tilt_chain_disaster",
            "tilt_discouragement",
            "strong_correlation",
        ):
            fix = ALL_FIXTURES[name]
            assert not is_summary(fix.karte), f"{name} should NOT be detected as summary"


# --- Each fixture produces the documented symptoms ---


@pytest.mark.parametrize(
    "fixture_name,expected_ids",
    [
        ("perfect_game", set()),
        ("single_atari_mistake", {SymptomId.ATARI_BLINDNESS}),
        ("reckless_overplay", {SymptomId.OVERPLAY_RECKLESS_ATTACK, SymptomId.OVERCONCENTRATION}),
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


# --- Phase 227-E: Summary fixture content checks ---


class TestSummaryFixturesPatterns:
    """Pin the Phase 227-A pattern extractor output for each summary
    fixture. This is the regression safety net for multi-game
    coaching — if someone changes the sort order, frequency formula,
    or colour aggregation logic, these tests catch it."""

    def test_summary_clean_yields_two_patterns(self):
        # 1 black + 1 white weakness entry
        patterns = extract_summary_weakness_patterns(
            ALL_FIXTURES["summary_clean"].karte
        )
        assert len(patterns) == 2

    def test_summary_clean_frequency_ratio(self):
        # games_analyzed = 3, black has count=2, white has count=1
        # → black freq=2/3, white freq=1/3
        patterns = extract_summary_weakness_patterns(
            ALL_FIXTURES["summary_clean"].karte
        )
        # Sort by color for stable assertion
        by_color = {p["color"]: p for p in patterns}
        assert abs(by_color["black"]["frequency_ratio"] - (2 / 3)) < 1e-9
        assert abs(by_color["white"]["frequency_ratio"] - (1 / 3)) < 1e-9

    def test_summary_blunder_dominant_top_pattern(self):
        # Top pattern by total_loss is black/middle/blunder (50.0)
        patterns = extract_summary_weakness_patterns(
            ALL_FIXTURES["summary_blunder_dominant"].karte
        )
        assert len(patterns) == 4  # 3 black + 1 white
        top = patterns[0]
        assert top["color"] == "black"
        assert top["category"] == "blunder"
        assert top["total_loss"] == 50.0
        # 5/5 games = 100%
        assert top["frequency_ratio"] == 1.0

    def test_summary_empty_weaknesses_yields_no_patterns(self):
        patterns = extract_summary_weakness_patterns(
            ALL_FIXTURES["summary_empty_weaknesses"].karte
        )
        assert patterns == []

    def test_summary_handicapped_mix_pattern_count(self):
        # 2 black + 1 white = 3 patterns
        patterns = extract_summary_weakness_patterns(
            ALL_FIXTURES["summary_handicapped_mix"].karte
        )
        assert len(patterns) == 3
        # Top is black/middle/blunder at 100% (6/6 games)
        top = patterns[0]
        assert top["color"] == "black"
        assert top["category"] == "blunder"
        assert top["frequency_ratio"] == 1.0


class TestSummaryFixturesPromptRendering:
    """Phase 227-E: pin the Phase 227-A prompt rendering for each
    summary fixture. We verify that the build_summary_weakness_prompt
    output contains the expected sections."""

    def test_summary_clean_renders_two_pattern_lines(self):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )

        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(
            ALL_FIXTURES["summary_clean"].karte, cfg
        )
        # Pattern block has exactly 2 numbered lines (count=2/1)
        patterns_block_marker = "### Weakness Patterns (pre-computed, top 2)\n"
        if patterns_block_marker in prompt.body_markdown:
            block = prompt.body_markdown.split(patterns_block_marker, 1)[1]
            # Block continues to the next section
            block = block.split("### Phase × Mistake Buckets", 1)[0]
            numbered = [
                line for line in block.splitlines() if line.startswith(("1. **", "2. **", "3. **"))
            ]
            assert len(numbered) == 2
        # referenced_patterns is a tuple
        assert len(prompt.referenced_patterns) == 2

    def test_summary_blunder_dominant_renders_four_pattern_lines(self):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )

        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=5,
        )
        prompt = build_summary_weakness_prompt(
            ALL_FIXTURES["summary_blunder_dominant"].karte, cfg
        )
        assert len(prompt.referenced_patterns) == 4

    def test_summary_empty_weaknesses_renders_placeholder(self):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )

        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=1,
        )
        prompt = build_summary_weakness_prompt(
            ALL_FIXTURES["summary_empty_weaknesses"].karte, cfg
        )
        # Placeholder text is shown in the patterns block
        assert "weakness データが見つかりません" in prompt.body_markdown
        # No patterns injected
        assert len(prompt.referenced_patterns) == 0


class TestSummaryFixturesValidator:
    """Phase 227-E: pin the Phase 227-B validator behaviour for each
    summary fixture. We feed a clean response and verify the
    validator's pattern/phases/issue extraction works."""

    def _build_prompt(self, fix_name: str):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )

        fix = ALL_FIXTURES[fix_name]
        # Pull games_analyzed from the fixture's meta
        games = fix.karte.get("meta", {}).get("games_analyzed", 5)
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=games,
        )
        return fix, build_summary_weakness_prompt(fix.karte, cfg)

    def test_summary_clean_clean_response(self):
        from katrain.core.coach.summary_validator import (
            validate_summary_llm_output,
        )

        fix, prompt = self._build_prompt("summary_clean")
        response = (
            "考察: 中盤の mistakes が多いです。\n"
            "抽出した弱点パターン: [mistake]\n"
            "参照したphase: [middle]\n"
        )
        report = validate_summary_llm_output(response, fix.karte, prompt)
        # Both colors have "mistake" category → no unknown
        assert report.is_clean
        # Pattern was extracted
        assert "mistake" in report.referenced_categories

    def test_summary_blunder_dominant_clean_response(self):
        from katrain.core.coach.summary_validator import (
            validate_summary_llm_output,
        )

        fix, prompt = self._build_prompt("summary_blunder_dominant")
        response = (
            "考察: 中盤の blunders が多いです。\n"
            "抽出した弱点パターン: [blunder, mistake, endgame_slip]\n"
            "参照したphase: [middle, opening, endgame]\n"
        )
        report = validate_summary_llm_output(response, fix.karte, prompt)
        assert report.is_clean

    def test_summary_blunder_dominant_flags_unknown_category(self):
        from katrain.core.coach.summary_validator import (
            validate_summary_llm_output,
        )

        fix, prompt = self._build_prompt("summary_blunder_dominant")
        response = (
            "考察: ...\n"
            "抽出した弱点パターン: [blunder, fantasy_category]\n"
        )
        report = validate_summary_llm_output(response, fix.karte, prompt)
        assert not report.is_clean
        kinds = [i.kind for i in report.issues]
        assert "unknown_pattern_category" in kinds

    def test_summary_blunder_dominant_flags_move_number(self):
        from katrain.core.coach.summary_validator import (
            validate_summary_llm_output,
        )

        fix, prompt = self._build_prompt("summary_blunder_dominant")
        # 第50手 is forbidden in summary mode
        response = (
            "考察: 第50手でのミスが顕著でした。\n"
            "抽出した弱点パターン: [blunder]\n"
        )
        report = validate_summary_llm_output(response, fix.karte, prompt)
        kinds = [i.kind for i in report.issues]
        assert "forbidden_move_number" in kinds
