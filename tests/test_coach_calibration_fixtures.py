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
        # Phase 228-D: 8 karte + 4 Shape A summary + 3 Shape B
        # Phase 245: +1 (position_evaluation_distorted) → 16 fixtures
        assert len(ALL_FIXTURES) == 16

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
        # 8 karte + 7 summary (4 Shape A + 3 Shape B)
        assert len(names) == 16

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
    assert fired == expected_ids, f"Fixture '{fixture_name}': expected {expected_ids}, got {fired}"


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
        patterns = extract_summary_weakness_patterns(ALL_FIXTURES["summary_clean"].karte)
        assert len(patterns) == 2

    def test_summary_clean_frequency_ratio(self):
        # games_analyzed = 3, black has count=2, white has count=1
        # → black freq=2/3, white freq=1/3
        patterns = extract_summary_weakness_patterns(ALL_FIXTURES["summary_clean"].karte)
        # Sort by color for stable assertion
        by_color = {p["color"]: p for p in patterns}
        assert abs(by_color["black"]["frequency_ratio"] - (2 / 3)) < 1e-9
        assert abs(by_color["white"]["frequency_ratio"] - (1 / 3)) < 1e-9

    def test_summary_blunder_dominant_top_pattern(self):
        # Top pattern by total_loss is black/middle/blunder (50.0)
        patterns = extract_summary_weakness_patterns(ALL_FIXTURES["summary_blunder_dominant"].karte)
        assert len(patterns) == 4  # 3 black + 1 white
        top = patterns[0]
        assert top["color"] == "black"
        assert top["category"] == "blunder"
        assert top["total_loss"] == 50.0
        # 5/5 games = 100%
        assert top["frequency_ratio"] == 1.0

    def test_summary_empty_weaknesses_yields_no_patterns(self):
        patterns = extract_summary_weakness_patterns(ALL_FIXTURES["summary_empty_weaknesses"].karte)
        assert patterns == []

    def test_summary_handicapped_mix_pattern_count(self):
        # 2 black + 1 white = 3 patterns
        patterns = extract_summary_weakness_patterns(ALL_FIXTURES["summary_handicapped_mix"].karte)
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
        prompt = build_summary_weakness_prompt(ALL_FIXTURES["summary_clean"].karte, cfg)
        # Pattern block has exactly 2 numbered lines (count=2/1)
        patterns_block_marker = "### Weakness Patterns (pre-computed, top 2)\n"
        if patterns_block_marker in prompt.body_markdown:
            block = prompt.body_markdown.split(patterns_block_marker, 1)[1]
            # Block continues to the next section
            block = block.split("### Phase × Mistake Buckets", 1)[0]
            numbered = [line for line in block.splitlines() if line.startswith(("1. **", "2. **", "3. **"))]
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
        prompt = build_summary_weakness_prompt(ALL_FIXTURES["summary_blunder_dominant"].karte, cfg)
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
        prompt = build_summary_weakness_prompt(ALL_FIXTURES["summary_empty_weaknesses"].karte, cfg)
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
        response = "考察: 中盤の mistakes が多いです。\n抽出した弱点パターン: [mistake]\n参照したphase: [middle]\n"
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
        response = "考察: ...\n抽出した弱点パターン: [blunder, fantasy_category]\n"
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
        response = "考察: 第50手でのミスが顕著でした。\n抽出した弱点パターン: [blunder]\n"
        report = validate_summary_llm_output(response, fix.karte, prompt)
        kinds = [i.kind for i in report.issues]
        assert "forbidden_move_number" in kinds


# --- Phase 228-D: Real-shape (Shape B) summary fixtures ---


class TestRealShapeFixtureSanity:
    """Phase 228-D: pin the structural properties of the 3 new
    real-shape summary fixtures."""

    def test_count_3_real_shape_fixtures(self):
        names = [n for n in list_fixture_names() if n.startswith("real_summary_")]
        assert len(names) == 3

    def test_all_real_shape_fixtures_detected_as_summary(self):
        # Each real-shape fixture should be detected as "summary" by
        # the JSON type detector (no top-level weaknesses block).
        from katrain.core.coach.json_type import is_summary

        for name in (
            "real_summary_blunder_focused",
            "real_summary_good_player",
            "real_summary_multi_player",
        ):
            fix = ALL_FIXTURES[name]
            assert is_summary(fix.karte), f"{name} should be detected as summary"

    def test_all_real_shape_fixtures_have_players_block(self):
        for name in (
            "real_summary_blunder_focused",
            "real_summary_good_player",
            "real_summary_multi_player",
        ):
            fix = ALL_FIXTURES[name]
            assert "players" in fix.karte
            assert isinstance(fix.karte["players"], dict)
            assert len(fix.karte["players"]) >= 1

    def test_all_real_shape_fixtures_have_standard_mistake_keys(self):
        # Every player's mistakes block has the 4 standard keys.
        for name in (
            "real_summary_blunder_focused",
            "real_summary_good_player",
            "real_summary_multi_player",
        ):
            fix = ALL_FIXTURES[name]
            players = fix.karte["players"]
            for player_name, block in players.items():
                mistakes = block.get("mistakes", {})
                assert "good" in mistakes, f"{name}.{player_name} missing 'good'"
                assert "inaccuracy" in mistakes, f"{name}.{player_name} missing 'inaccuracy'"
                assert "mistake" in mistakes, f"{name}.{player_name} missing 'mistake'"
                assert "blunder" in mistakes, f"{name}.{player_name} missing 'blunder'"

    def test_all_real_shape_fixtures_have_phases_block(self):
        for name in (
            "real_summary_blunder_focused",
            "real_summary_good_player",
            "real_summary_multi_player",
        ):
            fix = ALL_FIXTURES[name]
            for player_name, block in fix.karte["players"].items():
                phases = block.get("phases", {})
                assert "opening" in phases, f"{name}.{player_name} missing 'opening'"
                assert "middle" in phases, f"{name}.{player_name} missing 'middle'"
                assert "endgame" in phases, f"{name}.{player_name} missing 'endgame'"


class TestRealShapeFixturePatterns:
    """Phase 228-D: pin the pattern extractor output for the new
    real-shape fixtures."""

    def test_blunder_focused_has_4_patterns(self):
        from katrain.core.coach.json_type import (
            extract_summary_weakness_patterns,
        )

        patterns = extract_summary_weakness_patterns(ALL_FIXTURES["real_summary_blunder_focused"].karte)
        # Phase 241-A: "good" is filtered out (not a weakness).
        # 3 weakness categories × 1 player = 3 patterns.
        assert len(patterns) == 3
        categories = {p["category"] for p in patterns}
        assert categories == {"inaccuracy", "mistake", "blunder"}

    def test_good_player_patterns_sorted_by_total_loss(self):
        from katrain.core.coach.json_type import (
            extract_summary_weakness_patterns,
        )

        patterns = extract_summary_weakness_patterns(ALL_FIXTURES["real_summary_good_player"].karte)
        losses = [p["total_loss"] for p in patterns]
        assert losses == sorted(losses, reverse=True)
        # Phase 241-A: "good" is excluded. Sorted by total_loss:
        # inaccuracy=22*2.8=61.6, mistake=5*5.2=26.0, blunder=1*12.0=12.0.
        assert patterns[0]["category"] == "inaccuracy"
        assert patterns[1]["category"] == "mistake"
        assert patterns[2]["category"] == "blunder"

    def test_multi_player_has_8_patterns(self):
        from katrain.core.coach.json_type import (
            extract_summary_weakness_patterns,
        )

        patterns = extract_summary_weakness_patterns(ALL_FIXTURES["real_summary_multi_player"].karte)
        # Phase 241-A: 3 weakness categories × 2 players = 6 patterns.
        assert len(patterns) == 6
        players = {p["player"] for p in patterns}
        assert players == {"strong_player", "weak_player"}
        # Sanity: no "good" category leaks through.
        assert all(p["category"] != "good" for p in patterns)


class TestRealShapeFixturePromptRendering:
    """Phase 228-D: end-to-end prompt rendering for the new
    real-shape fixtures. Verifies the Phase 228-B prompt body
    sections are populated."""

    def _build_prompt(self, fixture_name, **cfg_kwargs):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )

        fix = ALL_FIXTURES[fixture_name]
        games = fix.karte.get("meta", {}).get("games_analyzed", 3)
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=games,
            **cfg_kwargs,
        )
        return fix, build_summary_weakness_prompt(fix.karte, cfg)

    def test_blunder_focused_player_mistakes_section_populated(self):
        fix, prompt = self._build_prompt("real_summary_blunder_focused", player_name="sentoku870")
        # Section header includes the player name
        assert "### Player Mistake Distribution (sentoku870)" in prompt.body_markdown
        # All 4 categories rendered with their values
        assert "**blunder**: 5/388 (1.3%) - avg_loss 19.04" in prompt.body_markdown
        assert "**mistake**: 22/388 (5.7%) - avg_loss 5.69" in prompt.body_markdown
        assert "**inaccuracy**: 51/388 (13.1%) - avg_loss 3.11" in prompt.body_markdown
        assert "**good**: 310/388 (79.9%) - avg_loss 0.28" in prompt.body_markdown

    def test_blunder_focused_player_phases_section_populated(self):
        fix, prompt = self._build_prompt("real_summary_blunder_focused", player_name="sentoku870")
        assert "### Player Phase Loss Distribution (sentoku870)" in prompt.body_markdown
        # Middle phase should be first (highest total_loss = 370.78)
        body = prompt.body_markdown
        phase_section_start = body.find("### Player Phase Loss Distribution")
        next_section_start = body.find("### Weakness Patterns")
        phase_block = body[phase_section_start:next_section_start]
        middle_pos = phase_block.find("**middle**")
        endgame_pos = phase_block.find("**endgame**")
        opening_pos = phase_block.find("**opening**")
        assert middle_pos < endgame_pos < opening_pos
        # Values present
        assert "173手" in phase_block
        assert "370.78" in phase_block

    def test_blunder_focused_weakness_patterns_uses_pct(self):
        fix, prompt = self._build_prompt("real_summary_blunder_focused", player_name="sentoku870")
        # Shape B patterns use 全体に占める割合 not 頻度
        assert "全体に占める割合" in prompt.body_markdown
        assert "13.1%" in prompt.body_markdown  # inaccuracy pct
        # Should NOT have misleading frequency like "1700.0%"
        assert "1700.0%" not in prompt.body_markdown

    def test_good_player_player_name_section_label(self):
        fix, prompt = self._build_prompt("real_summary_good_player", player_name="strong_player")
        assert "### Player Mistake Distribution (strong_player)" in prompt.body_markdown
        assert "### Player Phase Loss Distribution (strong_player)" in prompt.body_markdown

    def test_multi_player_birdseye_shows_overview(self):
        fix, prompt = self._build_prompt("real_summary_multi_player")
        # Birdseye: section headers say 全体俯瞰
        assert "### Player Mistake Distribution (全体俯瞰)" in prompt.body_markdown
        assert "### Player Phase Loss Distribution (全体俯瞰)" in prompt.body_markdown
        # Both player names appear in the per-player overview
        assert "**strong_player**" in prompt.body_markdown
        assert "**weak_player**" in prompt.body_markdown
        # Birdseye line uses 'worst phase' format
        assert "worst phase" in prompt.body_markdown


class TestRealShapeFixtureValidatorE2E:
    """Phase 228-D: end-to-end validator test using the new
    real-shape fixtures + a clean LLM response. The validator
    should return clean because the standard 4 categories are
    now valid (Phase 228-C)."""

    def test_blunder_focused_clean_response(self):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )

        fix = ALL_FIXTURES["real_summary_blunder_focused"]
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
            player_name="sentoku870",
        )
        prompt = build_summary_weakness_prompt(fix.karte, cfg)

        # A clean LLM response citing the standard categories
        response = (
            "考察: 中盤の blunder が最も深刻です。\n"
            "抽出した弱点パターン: [blunder, mistake, inaccuracy]\n"
            "参照したphase: [middle, opening]\n"
        )
        from katrain.core.coach.summary_validator import (
            validate_summary_llm_output,
        )

        report = validate_summary_llm_output(response, fix.karte, prompt)
        # All 4 standard categories accepted (Phase 228-C)
        # No move numbers, no game IDs, no hallucinated categories
        assert report.is_clean
        assert report.high_count == 0
        assert report.medium_count == 0
        assert report.low_count == 0
        # Patterns extracted
        assert "blunder" in report.referenced_categories
        assert "mistake" in report.referenced_categories
        assert "inaccuracy" in report.referenced_categories
        assert "middle" in report.referenced_phases

    def test_multi_player_focused_strong_response(self):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )
        from katrain.core.coach.summary_validator import (
            validate_summary_llm_output,
        )

        fix = ALL_FIXTURES["real_summary_multi_player"]
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=4,
            player_name="strong_player",
        )
        prompt = build_summary_weakness_prompt(fix.karte, cfg)
        response = (
            "考察: good が多いです。\n抽出した弱点パターン: [good, inaccuracy]\n参照したphase: [middle, opening]\n"
        )
        report = validate_summary_llm_output(response, fix.karte, prompt)
        assert report.is_clean
        assert "good" in report.referenced_categories
        assert "inaccuracy" in report.referenced_categories

    def test_hallucinated_category_still_flagged(self):
        # The validator should still flag categories that aren't in
        # the standard 4 AND aren't in the summary.
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )
        from katrain.core.coach.summary_validator import (
            validate_summary_llm_output,
        )

        fix = ALL_FIXTURES["real_summary_blunder_focused"]
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
            player_name="sentoku870",
        )
        prompt = build_summary_weakness_prompt(fix.karte, cfg)
        response = "考察: ...\n抽出した弱点パターン: [blunder, fantasy_category]\n参照したphase: [middle]\n"
        report = validate_summary_llm_output(response, fix.karte, prompt)
        assert not report.is_clean
        kinds = [i.kind for i in report.issues]
        assert "unknown_pattern_category" in kinds

    def test_forbidden_move_number_still_flagged(self):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )
        from katrain.core.coach.summary_validator import (
            validate_summary_llm_output,
        )

        fix = ALL_FIXTURES["real_summary_blunder_focused"]
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
            player_name="sentoku870",
        )
        prompt = build_summary_weakness_prompt(fix.karte, cfg)
        response = "考察: 第50手でのミスが顕著でした。\n抽出した弱点パターン: [blunder]\n参照したphase: [middle]\n"
        report = validate_summary_llm_output(response, fix.karte, prompt)
        kinds = [i.kind for i in report.issues]
        assert "forbidden_move_number" in kinds
