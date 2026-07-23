"""Phase 227-B: Tests for katrain.core.coach.summary_validator.

Covers:
- Pattern category existence (HIGH)
- Per-move number reference detection (HIGH)
- Pattern count > MAX_PATTERNS (MEDIUM)
- Phase label cross-check (MEDIUM)
- Specific game ID reference detection (LOW)
- Tone consistency (LOW)
- SummaryValidationReport fields + properties
- Extractors: _extract_pattern_categories, _extract_referenced_phases,
  _extract_move_numbers, _extract_game_id_references,
  _extract_phases_from_prose
"""

from __future__ import annotations

import pytest

from katrain.core.coach.llm_validator import ValidationSeverity
from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.summary_prompt_builder import (
    SummaryPromptConfig,
    build_summary_weakness_prompt,
)
from katrain.core.coach.summary_validator import (
    SummaryValidationReport,
    _extract_game_id_references,
    _extract_move_numbers,
    _extract_pattern_categories,
    _extract_phases_from_prose,
    _extract_referenced_phases,
    _summary_available_categories,
    _summary_available_phases,
    validate_summary_llm_output,
)

# --- Fixtures ---


@pytest.fixture
def sample_summary() -> dict:
    return {
        "schema_version": "3.4",
        "meta": {"games_analyzed": 5},
        "phase_x_mistake": {
            "opening:mistake": 5,
            "middle:blunder": 8,
            "endgame:mistake": 2,
        },
        "weaknesses": {
            "black": [
                {"phase": "middle", "category": "blunder", "count": 5, "total_loss": 30.0},
                {"phase": "opening", "category": "mistake", "count": 4, "total_loss": 12.0},
            ],
            "white": [
                {"phase": "endgame", "category": "endgame_slip", "count": 2, "total_loss": 4.0},
            ],
        },
        "players": {"sentoku870": {}},
    }


@pytest.fixture
def tomoko_config() -> SummaryPromptConfig:
    return SummaryPromptConfig(
        voice=ToneVoice.TOMOKO,
        mode=CoachMode.DAN,
        games_analyzed=5,
        player_name="sentoku870",
    )


@pytest.fixture
def beginner_tomoko_config() -> SummaryPromptConfig:
    # Phase 269: BEGINNER voice is TOMOKO (AYAKA removed).
    return SummaryPromptConfig(
        voice=ToneVoice.TOMOKO,
        mode=CoachMode.BEGINNER,
        games_analyzed=5,
    )


# --- Ground truth extractors ---


class TestSummaryAvailableFields:
    def test_categories_across_colors(self, sample_summary):
        cats = _summary_available_categories(sample_summary)
        assert cats == {"blunder", "mistake", "endgame_slip"}

    def test_categories_no_weaknesses(self):
        assert _summary_available_categories({}) == set()

    def test_categories_non_dict_weaknesses(self):
        assert _summary_available_categories({"weaknesses": "bad"}) == set()

    def test_phases_across_colors(self, sample_summary):
        phases = _summary_available_phases(sample_summary)
        assert phases == {"middle", "opening", "endgame"}

    def test_phases_no_weaknesses(self):
        assert _summary_available_phases({}) == set()


# --- Phase 228-C: Shape B (players.<name>.mistakes / phases) ---


class TestSummaryAvailableFieldsShapeB:
    """Phase 228-C: ``_summary_available_categories`` and
    ``_summary_available_phases`` accept the standard 4 mistake
    categories and 3 phase labels when the summary uses the real
    ``summary_json_export.py`` shape."""

    def test_shape_b_categories_includes_4_standard(self, real_shape_summary):
        data = real_shape_summary
        cats = _summary_available_categories(data)
        # The 4 standard categories must be present
        for cat in ("blunder", "mistake", "inaccuracy", "good"):
            assert cat in cats

    def test_shape_b_phases_includes_3_standard(self, real_shape_summary):
        data = real_shape_summary
        phases = _summary_available_phases(data)
        for ph in ("opening", "middle", "endgame"):
            assert ph in phases

    def test_shape_b_categories_includes_explicit_only(self):
        # When a player has only some of the standard categories
        # (e.g. opponent1 only has good and blunder), the missing
        # ones should still appear in the valid set because the
        # mistakes block exists.
        data = {
            "players": {
                "alice": {
                    "mistakes": {
                        "good": {"count": 1, "pct": 50.0, "denominator": 2, "avg_loss": 0.1},
                        "blunder": {"count": 1, "pct": 50.0, "denominator": 2, "avg_loss": 5.0},
                    }
                }
            }
        }
        cats = _summary_available_categories(data)
        # Both standard categories included via Shape B
        assert "good" in cats
        assert "blunder" in cats
        # The 4 standard set is added when any mistakes block exists
        for cat in ("blunder", "mistake", "inaccuracy", "good"):
            assert cat in cats

    def test_no_mistakes_block_no_standard_categories(self):
        # Players exist but no ``mistakes`` sub-block — standard
        # categories should NOT be auto-added.
        data = {
            "players": {
                "alice": {
                    "phases": {
                        "middle": {"moves": 100, "total_loss": 50.0, "avg_loss": 0.5},
                    }
                }
            }
        }
        cats = _summary_available_categories(data)
        # 4 standard categories NOT included
        assert "blunder" not in cats
        assert "good" not in cats

    def test_empty_mistakes_block_treated_as_missing(self):
        # A mistakes block that exists but is empty should not
        # trigger Shape B mode.
        data = {
            "players": {
                "alice": {
                    "mistakes": {},
                }
            }
        }
        cats = _summary_available_categories(data)
        assert "blunder" not in cats

    def test_explicit_custom_categories_added(self):
        # A player with a custom category (e.g. "endgame_slip") in
        # their mistakes block should add that to the valid set.
        data = {
            "players": {
                "alice": {
                    "mistakes": {
                        "good": {"count": 1, "pct": 50.0, "denominator": 2, "avg_loss": 0.1},
                        "endgame_slip": {"count": 1, "pct": 50.0, "denominator": 2, "avg_loss": 5.0},
                    }
                }
            }
        }
        cats = _summary_available_categories(data)
        assert "endgame_slip" in cats
        # Standard categories also present (Shape B)
        assert "blunder" in cats

    def test_phases_includes_3_standard_when_shape_b(self):
        # Phase 228-C: when at least one player has a phases block,
        # all 3 standard phase labels are accepted (the LLM is
        # justified in citing any of them because the Player Phase
        # Loss Distribution block always uses these labels).
        data = {
            "players": {
                "alice": {
                    "phases": {
                        "middle": {"moves": 100, "total_loss": 50.0, "avg_loss": 0.5},
                    }
                }
            }
        }
        phases = _summary_available_phases(data)
        for ph in ("opening", "middle", "endgame"):
            assert ph in phases

    def test_phases_union_across_players(self):
        # Phases are unioned across all players.
        data = {
            "players": {
                "alice": {
                    "phases": {
                        "middle": {"moves": 100, "total_loss": 50.0, "avg_loss": 0.5},
                    }
                },
                "bob": {
                    "phases": {
                        "opening": {"moves": 50, "total_loss": 10.0, "avg_loss": 0.2},
                        "endgame": {"moves": 80, "total_loss": 15.0, "avg_loss": 0.19},
                    }
                },
            }
        }
        phases = _summary_available_phases(data)
        assert phases == {"middle", "opening", "endgame"}

    def test_shape_a_still_works(self):
        # Phase 227-A legacy shape: top-level weaknesses still work
        data = {
            "weaknesses": {
                "black": [
                    {"phase": "middle", "category": "blunder", "count": 5, "total_loss": 30.0},
                ],
            },
        }
        cats = _summary_available_categories(data)
        assert cats == {"blunder"}
        # No Shape B, so standard categories NOT added
        assert "good" not in cats
        assert "inaccuracy" not in cats

    def test_both_shapes_present_both_included(self):
        # When both shapes exist, categories from Shape A AND the
        # 4 standard Shape B categories are all accepted. The
        # validator treats Shape A's explicit categories as additive
        # (not exclusive) — both schema sets can co-exist.
        data = {
            "weaknesses": {
                "black": [
                    {"phase": "middle", "category": "weird_old_category", "count": 1, "total_loss": 1.0},
                ],
            },
            "players": {
                "alice": {
                    "mistakes": {
                        "good": {"count": 1, "pct": 50.0, "denominator": 2, "avg_loss": 0.1},
                    }
                }
            },
        }
        cats = _summary_available_categories(data)
        # Shape A category present
        assert "weird_old_category" in cats
        # Shape B standard categories also present
        for cat in ("blunder", "mistake", "inaccuracy", "good"):
            assert cat in cats

    def test_non_dict_players_block_ignored(self):
        data = {"players": "not a dict"}
        assert _summary_available_categories(data) == set()
        assert _summary_available_phases(data) == set()

    def test_non_dict_player_block_skipped(self):
        data = {"players": {"alice": "bad"}}
        assert _summary_available_categories(data) == set()
        assert _summary_available_phases(data) == set()

    def test_non_dict_mistakes_block_skipped(self):
        data = {"players": {"alice": {"mistakes": "bad"}}}
        assert _summary_available_categories(data) == set()

    def test_non_dict_phases_block_skipped(self):
        data = {"players": {"alice": {"phases": "bad"}}}
        assert _summary_available_phases(data) == set()

    def test_partial_shape_b_only_one_player_has_data(self):
        # One player has mistakes + phases, another doesn't.
        # Should still add the standard categories.
        data = {
            "players": {
                "alice": {
                    "mistakes": {
                        "blunder": {"count": 1, "pct": 50.0, "denominator": 2, "avg_loss": 5.0},
                    },
                    "phases": {
                        "middle": {"moves": 50, "total_loss": 25.0, "avg_loss": 0.5},
                    },
                },
                "bob": {},  # no mistakes, no phases
            }
        }
        cats = _summary_available_categories(data)
        for cat in ("blunder", "mistake", "inaccuracy", "good"):
            assert cat in cats
        phases = _summary_available_phases(data)
        assert "middle" in phases


class TestValidatorAcceptsShapeBCategories:
    """Phase 228-C: end-to-end test that the validator returns clean
    when LLM cites the standard 4 mistake categories from a
    Shape B summary."""

    def test_blunder_mistake_inaccuracy_good_all_clean(self, real_shape_summary):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )

        data = real_shape_summary
        response = (
            "考察: 中盤の blunder が最多です。\n"
            "抽出した弱点パターン: [blunder, mistake, inaccuracy]\n"
            "参照したphase: [middle, opening]\n"
        )
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(data, cfg)
        report = validate_summary_llm_output(response, data, prompt)
        assert report.is_clean
        assert report.high_count == 0
        assert report.medium_count == 0
        assert report.low_count == 0
        assert "blunder" in report.referenced_categories
        assert "mistake" in report.referenced_categories
        assert "inaccuracy" in report.referenced_categories
        assert "middle" in report.referenced_phases
        assert "opening" in report.referenced_phases

    def test_fantasy_category_still_flagged_for_shape_b(self, real_shape_summary):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )

        data = real_shape_summary
        # Cite a real category plus a hallucinated one
        response = "考察: ...\n抽出した弱点パターン: [blunder, fantasy_category]\n参照したphase: [middle]\n"
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(data, cfg)
        report = validate_summary_llm_output(response, data, prompt)
        # fantasy_category is NOT a standard mistake category and
        # not in the summary — should be flagged HIGH.
        assert not report.is_clean
        assert report.high_count == 1
        kinds = [i.kind for i in report.issues]
        assert "unknown_pattern_category" in kinds

    def test_standard_phases_accepted_for_shape_b(self):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )

        # Summary with only "middle" in phases block — but the
        # 3 standard phase labels are still accepted because the
        # Player Phase Loss Distribution block always uses them.
        data = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "players": {
                "alice": {
                    "mistakes": {
                        "blunder": {"count": 1, "pct": 100.0, "denominator": 1, "avg_loss": 5.0},
                    },
                    "phases": {
                        "middle": {"moves": 50, "total_loss": 25.0, "avg_loss": 0.5},
                    },
                }
            },
        }
        response = (
            "考察: ...\n"
            "抽出した弱点パターン: [blunder]\n"
            "参照したphase: [middle, opening, endgame]\n"  # all 3 accepted
        )
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(data, cfg)
        report = validate_summary_llm_output(response, data, prompt)
        # All 3 standard phases accepted, no warnings
        phase_kinds = [i.kind for i in report.issues if i.kind == "phase_label_out_of_set"]
        assert phase_kinds == []

    def test_good_category_citation_clean(self, real_shape_summary):
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPromptConfig,
            build_summary_weakness_prompt,
        )

        data = real_shape_summary
        # LLM might mention "good" as a positive observation
        response = "考察: 良い手も 79.9% あります。\n抽出した弱点パターン: [blunder, good]\n参照したphase: [middle]\n"
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(data, cfg)
        report = validate_summary_llm_output(response, data, prompt)
        # "good" is a valid Shape B standard category — no HIGH warning
        high_kinds = [i.kind for i in report.issues if i.severity.value == "high"]
        assert "unknown_pattern_category" not in high_kinds


# --- LLM text extractors ---


class TestPatternListExtractor:
    def test_ja_contract(self):
        text = "考察: ...\n抽出した弱点パターン: [blunder, mistake]"
        assert _extract_pattern_categories(text) == ("blunder", "mistake")

    def test_ja_contract_with_fullwidth_colon(self):
        text = "考察: ...\n抽出した弱点パターン：[blunder, mistake]"
        assert _extract_pattern_categories(text) == ("blunder", "mistake")

    def test_en_contract(self):
        text = "WeaknessPatterns: [blunder, mistake]"
        assert _extract_pattern_categories(text) == ("blunder", "mistake")

    def test_short_ja_contract(self):
        text = "弱点パターン: [blunder, mistake]"
        assert _extract_pattern_categories(text) == ("blunder", "mistake")

    def test_missing_line(self):
        text = "考察: 弱点があります。"
        assert _extract_pattern_categories(text) == ()

    def test_works_with_trailing_newline(self):
        text = "考察...\n抽出した弱点パターン: [blunder]\n"
        assert _extract_pattern_categories(text) == ("blunder",)

    def test_works_with_followup_lines(self):
        text = "考察...\n抽出した弱点パターン: [blunder, mistake]\n参照したphase: [middle, opening]\n"
        assert _extract_pattern_categories(text) == ("blunder", "mistake")


class TestPhaseListExtractor:
    def test_ja_contract(self):
        text = "考察...\n参照したphase: [middle, opening]"
        assert _extract_referenced_phases(text) == ("middle", "opening")

    def test_en_contract(self):
        text = "考察...\nPhases: [middle, opening]"
        assert _extract_referenced_phases(text) == ("middle", "opening")

    def test_missing(self):
        assert _extract_referenced_phases("考察のみ") == ()


class TestMoveNumberExtractor:
    def test_50手目(self):
        assert _extract_move_numbers("第50手目でミス") == (50,)

    def test_move_50(self):
        assert _extract_move_numbers("move 50 で失敗") == (50,)

    def test_hash_50(self):
        assert _extract_move_numbers("#50 が悪い") == (50,)

    def test_着手_50(self):
        assert _extract_move_numbers("着手 50 が悪い") == (50,)

    def test_5段_not_match(self):
        # 5段 should NOT match (段 is excluded unit)
        assert _extract_move_numbers("4段プレイヤー") == ()

    def test_30級_not_match(self):
        assert _extract_move_numbers("30級") == ()

    def test_2026年_not_match(self):
        assert _extract_move_numbers("2026年") == ()

    def test_zero_excluded(self):
        # 0 is excluded (must be >0)
        assert _extract_move_numbers("着手 0") == ()

    def test_empty(self):
        assert _extract_move_numbers("") == ()

    # --- Phase 229: count patterns must NOT be flagged ---
    # The previous regex matched bare "X手" which produced false
    # positives on every statistical phrase like "全388手中51手（13.1%）".
    # The summary validator now drops the bare alternative; these tests
    # pin that behaviour.

    def test_count_in_全N手中M手_not_flagged(self):
        # "全388手中51手" — 51 is the COUNT of moves, not a move number
        assert _extract_move_numbers("全388手中51手（13.1%）") == ()

    def test_count_in_X手_N_percent_not_flagged(self):
        # "22手（5.7%）" at the start of a bullet (no preceding context)
        assert _extract_move_numbers("22手（5.7%）が mistake です") == ()

    def test_count_in_X手_N_percent_no_preceding_text(self):
        # Pure statistical phrase
        assert _extract_move_numbers("5手（1.3%）") == ()

    def test_count_patterns_combined_realistic_llm_output(self):
        # Verbatim copy of the LLM prose section that triggered the
        # original false positive report.
        text = (
            "### 1. inaccuracy（軽度の判断ミス）\n"
            "- 全388手中51手（13.1%）\n"
            "### 2. mistake（明らかなミス）\n"
            "- 22手（5.7%）\n"
            "### 3. blunder（大失着）\n"
            "- 5手（1.3%）\n"
        )
        assert _extract_move_numbers(text) == ()

    def test_5段_not_flagged_in_summary_mode(self):
        # Sanity check: rank suffixes remain excluded (covered by
        # the karte regex too — making sure the summary regex is at
        # least as strict).
        assert _extract_move_numbers("4段プレイヤー、30級、2026年") == ()

    def test_real_move_refs_still_flagged_after_phase229(self):
        # All unambiguous move references must still be detected.
        assert _extract_move_numbers("第50手でのミス") == (50,)
        assert _extract_move_numbers("#50 が悪い") == (50,)
        assert _extract_move_numbers("move 50 で失敗") == (50,)
        assert _extract_move_numbers("着手 50 が悪い") == (50,)
        assert _extract_move_numbers("50手目で失敗") == (50,)
        assert _extract_move_numbers("50番") == (50,)


class TestGameIdExtractor:
    def test_g1(self):
        assert _extract_game_id_references("g1 で起きた") == ("g1",)

    def test_game_5(self):
        assert _extract_game_id_references("game_5 の結果") == ("game_5",)

    def test_game5_no_underscore(self):
        assert _extract_game_id_references("game5 でした") == ("game5",)

    def test_no_match(self):
        assert _extract_game_id_references("特に問題ない") == ()

    def test_dedup(self):
        result = _extract_game_id_references("g1 と g1 は同じ")
        assert result == ("g1",)

    def test_multiple_distinct(self):
        result = _extract_game_id_references("g1, g2, g3")
        assert result == ("g1", "g2", "g3")


class TestPhasesFromProse:
    def test_single_phase(self):
        assert _extract_phases_from_prose("序盤 (opening) が悪い") == ("opening",)

    def test_multiple_phases(self):
        assert _extract_phases_from_prose("opening と middle が問題") == (
            "opening",
            "middle",
        )

    def test_no_phases(self):
        assert _extract_phases_from_prose("特に問題ない") == ()

    def test_word_boundary_substring_not_match(self):
        # 'open' should not match 'opening' as a separate word
        assert _extract_phases_from_prose("opening") == ("opening",)
        # Phase 227-B: plural forms are also accepted (lenient matching
        # mirrors the karte validator's tone-extractor philosophy)
        result = _extract_phases_from_prose("multiple openings")
        assert "opening" in result

    def test_case_insensitive(self):
        assert _extract_phases_from_prose("OPENING was bad") == ("opening",)

    def test_empty(self):
        assert _extract_phases_from_prose("") == ()


# --- validate_summary_llm_output ---


class TestValidationClean:
    def test_clean_response(self, sample_summary, tomoko_config):
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        text = (
            "考察: 中盤の blunders が多いです。\n"
            "抽出した弱点パターン: [blunder, mistake]\n"
            "参照したphase: [middle, opening]\n"
        )
        report = validate_summary_llm_output(text, sample_summary, prompt)
        assert report.is_clean
        assert report.high_count == 0
        assert report.medium_count == 0
        assert report.low_count == 0
        assert report.referenced_categories == ("blunder", "mistake")
        assert "middle" in report.referenced_phases
        assert "opening" in report.referenced_phases

    def test_clean_response_long_no_tone_issue(self, sample_summary, tomoko_config):
        # TOMOKO config + long text without Kansai markers = clean
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        long_text = "考察: " + "abc " * 100 + "\n抽出した弱点パターン: [blunder]\n"
        report = validate_summary_llm_output(long_text, sample_summary, prompt)
        assert not any(i.kind.startswith("tone") for i in report.issues)


class TestValidationPatternCategory:
    def test_unknown_category_high(self, sample_summary, tomoko_config):
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        text = "考察: ...\n抽出した弱点パターン: [blunder, fantasy_category]"
        report = validate_summary_llm_output(text, sample_summary, prompt)
        kinds = [i.kind for i in report.issues]
        assert "unknown_pattern_category" in kinds
        high_kinds = [i.kind for i in report.issues if i.severity == ValidationSeverity.HIGH]
        assert "unknown_pattern_category" in high_kinds

    def test_known_categories_no_issue(self, sample_summary, tomoko_config):
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        text = "考察: ...\n抽出した弱点パターン: [blunder, mistake, endgame_slip]"
        report = validate_summary_llm_output(text, sample_summary, prompt)
        assert not any(i.kind == "unknown_pattern_category" for i in report.issues)


class TestValidationMoveNumber:
    def test_forbidden_move_number_high(self, sample_summary, tomoko_config):
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        text = "考察: 第50手でのミスが顕著でした。\n抽出した弱点パターン: [blunder]\n"
        report = validate_summary_llm_output(text, sample_summary, prompt)
        kinds = [i.kind for i in report.issues]
        assert "forbidden_move_number" in kinds
        high_kinds = [i.kind for i in report.issues if i.severity == ValidationSeverity.HIGH]
        assert "forbidden_move_number" in high_kinds
        assert report.referenced_move_numbers == (50,)

    def test_no_move_number_no_issue(self, sample_summary, tomoko_config):
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        text = "考察: 全体的に傾向があります。\n抽出した弱点パターン: [blunder]\n"
        report = validate_summary_llm_output(text, sample_summary, prompt)
        assert not any(i.kind == "forbidden_move_number" for i in report.issues)

    # --- Phase 229: statistical count patterns must NOT trigger
    # forbidden_move_number at the validation-report level ---
    def test_count_patterns_not_flagged_at_report_level(self, sample_summary, tomoko_config):
        # Verbatim copy of the LLM output that triggered the original
        # bug report (3 false-positive HIGH findings on counts 51/22/5).
        # Categories are chosen to match the sample_summary fixture
        # (mistake/blunder/endgame_slip) so we isolate the count-pattern
        # behaviour from category validation.
        text = (
            "## 抽出した弱点パターン（深刻度順）\n"
            "### 1. **endgame_slip（軽度の判断ミス）**\n"
            "- 全388手中51手（13.1%）\n"
            "### 2. **mistake（明らかなミス）**\n"
            "- 22手（5.7%）\n"
            "### 3. **blunder（大失着）**\n"
            "- 5手（1.3%）\n"
            "抽出した弱点パターン: [endgame_slip, mistake, blunder]\n"
            "参照したphase: [middle]\n"
        )
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        report = validate_summary_llm_output(text, sample_summary, prompt)
        # No HIGH forbidden_move_number issues — counts are legitimate
        # in summary mode.
        forbidden = [i for i in report.issues if i.kind == "forbidden_move_number"]
        assert forbidden == [], (
            f"Expected no false-positive forbidden_move_number issues, got: {[i.message for i in forbidden]}"
        )
        # The report's referenced_move_numbers must be empty.
        assert report.referenced_move_numbers == ()
        # No HIGH issues at all for this clean response.
        assert report.high_count == 0


class TestValidationPatternCount:
    def test_too_many_patterns_medium(self, sample_summary, tomoko_config):
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        # 4 patterns > MAX_PATTERNS=3
        text = "考察...\n抽出した弱点パターン: [a, b, c, d]"
        report = validate_summary_llm_output(text, sample_summary, prompt)
        kinds = [i.kind for i in report.issues]
        assert "too_many_patterns" in kinds
        medium_kinds = [i.kind for i in report.issues if i.severity == ValidationSeverity.MEDIUM]
        assert "too_many_patterns" in medium_kinds

    def test_exactly_max_no_issue(self, sample_summary, tomoko_config):
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        text = "考察...\n抽出した弱点パターン: [a, b, c]"
        report = validate_summary_llm_output(text, sample_summary, prompt)
        assert not any(i.kind == "too_many_patterns" for i in report.issues)

    def test_no_patterns_no_count_issue(self, sample_summary, tomoko_config):
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        text = "考察のみ。パターン抽出なし。"
        report = validate_summary_llm_output(text, sample_summary, prompt)
        # No pattern line at all → no count issue (count = 0, not > MAX)
        assert not any(i.kind == "too_many_patterns" for i in report.issues)


class TestValidationPhase:
    def test_known_label_not_in_summary_medium(self, sample_summary, tomoko_config):
        # sample_summary has 'middle' / 'opening' / 'endgame' but the
        # validator flags 'endgame' because the assistant says "中盤"
        # which the LLM might or might not know. We use a fixture
        # without 'endgame' to verify the out-of-set check.
        from tests.test_coach_summary_validator import _summary_available_phases

        summary_no_endgame = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 5},
            "weaknesses": {
                "black": [
                    {"phase": "middle", "category": "blunder", "count": 5, "total_loss": 30.0},
                ],
                "white": [],
            },
        }
        assert "endgame" not in _summary_available_phases(summary_no_endgame)
        prompt = build_summary_weakness_prompt(summary_no_endgame, tomoko_config)
        text = "考察: endgame が問題です。\n抽出した弱点パターン: [blunder]\n"
        report = validate_summary_llm_output(text, summary_no_endgame, prompt)
        kinds = [i.kind for i in report.issues]
        assert "phase_label_out_of_set" in kinds

    def test_unknown_label_ignored(self, sample_summary, tomoko_config):
        # 'fuseki' / 'yose' are not in _VALID_PHASES so they're not
        # checked against the summary. The validator only flags
        # *known* phase labels that are *not* in the summary.
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        text = "考察: fuseki と yose が問題です。\n抽出した弱点パターン: [blunder]\n"
        report = validate_summary_llm_output(text, sample_summary, prompt)
        assert not any(i.kind == "phase_label_out_of_set" for i in report.issues)

    def test_known_phases_no_issue(self, sample_summary, tomoko_config):
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        text = "考察: opening と middle が問題。\n抽出した弱点パターン: [blunder]\n"
        report = validate_summary_llm_output(text, sample_summary, prompt)
        assert not any(i.kind == "phase_label_out_of_set" for i in report.issues)


class TestValidationGameId:
    def test_specific_game_id_low(self, sample_summary, tomoko_config):
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        text = "考察: g3 で大きなミスがありました。\n抽出した弱点パターン: [blunder]\n"
        report = validate_summary_llm_output(text, sample_summary, prompt)
        kinds = [i.kind for i in report.issues]
        assert "specific_game_id_referenced" in kinds
        low_kinds = [i.kind for i in report.issues if i.severity == ValidationSeverity.LOW]
        assert "specific_game_id_referenced" in low_kinds
        assert "g3" in report.referenced_game_ids


# --- Report properties ---


class TestSummaryValidationReport:
    def test_clean_summary_line(self):
        report = SummaryValidationReport(llm_text="ok")
        assert report.is_clean
        assert "検証クリア" in report.summary_line()

    def test_dirty_summary_line(self):
        from katrain.core.coach.llm_validator import ValidationIssue

        issues = (
            ValidationIssue(
                severity=ValidationSeverity.HIGH,
                kind="test",
                message="test",
            ),
        )
        report = SummaryValidationReport(llm_text="bad", issues=issues)
        assert not report.is_clean
        assert "高" in report.summary_line()

    def test_count_properties(self):
        from katrain.core.coach.llm_validator import ValidationIssue

        issues = (
            ValidationIssue(severity=ValidationSeverity.HIGH, kind="a", message="m"),
            ValidationIssue(severity=ValidationSeverity.MEDIUM, kind="b", message="m"),
            ValidationIssue(severity=ValidationSeverity.MEDIUM, kind="c", message="m"),
            ValidationIssue(severity=ValidationSeverity.LOW, kind="d", message="m"),
            ValidationIssue(severity=ValidationSeverity.LOW, kind="e", message="m"),
            ValidationIssue(severity=ValidationSeverity.LOW, kind="f", message="m"),
        )
        report = SummaryValidationReport(llm_text="x", issues=issues)
        assert report.high_count == 1
        assert report.medium_count == 2
        assert report.low_count == 3

    def test_frozen(self):
        from dataclasses import FrozenInstanceError

        report = SummaryValidationReport(llm_text="ok")
        with pytest.raises(FrozenInstanceError):
            report.llm_text = "new"  # type: ignore[misc]


# --- Multiple issues ---


class TestMultipleIssues:
    def test_combined_violations(self, tomoko_config):
        # Use a summary without 'endgame' so we can flag the LLM
        # for using an out-of-set phase label.
        summary_no_endgame = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 5},
            "weaknesses": {
                "black": [
                    {"phase": "middle", "category": "blunder", "count": 5, "total_loss": 30.0},
                ],
                "white": [],
            },
        }
        prompt = build_summary_weakness_prompt(summary_no_endgame, tomoko_config)
        # Combine: unknown category + move number + game id + too many
        # + out-of-set phase (endgame not in this summary)
        text = (
            "考察: 第50手でのミスが顕著で、g3 が最悪でした。\n"
            "endgame と middle も問題です。\n"
            "抽出した弱点パターン: [blunder, fantasy, error, extra, more]\n"
        )
        report = validate_summary_llm_output(text, summary_no_endgame, prompt)
        kinds = {i.kind for i in report.issues}
        assert "unknown_pattern_category" in kinds
        assert "forbidden_move_number" in kinds
        assert "specific_game_id_referenced" in kinds
        assert "too_many_patterns" in kinds
        assert "phase_label_out_of_set" in kinds

    def test_never_raises(self, sample_summary, tomoko_config):
        prompt = build_summary_weakness_prompt(sample_summary, tomoko_config)
        # Garbage text should not raise
        report = validate_summary_llm_output("", sample_summary, prompt)
        assert report.referenced_categories == ()
        assert report.referenced_move_numbers == ()
        assert report.referenced_game_ids == ()
