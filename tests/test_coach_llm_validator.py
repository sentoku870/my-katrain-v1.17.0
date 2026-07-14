"""Phase 212: Tests for katrain.core.coach.llm_validator.

Covers:
- Symptom id existence check (against Karte + prompt + config)
- Move number range check
- pointsLost outlier check (within tolerance)
- Tone consistency check (AYAKA vs TOMOKO)
- ValidationReport summary helpers
- Never-raises contract (returns report even on bad input)
"""

from __future__ import annotations

import pytest

from katrain.core.coach.llm_validator import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    validate_llm_output,
)
from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.prompt_builder import (
    PromptConfig,
    build_translation_prompt,
)
from katrain.core.coach.symptom_index import SymptomId


# --- Fixtures ---


@pytest.fixture
def sample_karte() -> dict:
    return {
        "schema_version": "3.4",
        "summary": {"total_moves": 200},
        "important_moves": [
            {"meaning_tag_id": "capture_race_loss", "points_lost": 3.0},
            {"meaning_tag_id": "endgame_slip", "points_lost": 5.0},
        ],
        "weaknesses": {
            "black": [{"category": "blunder"}, {"category": "mistake"}],
            "white": [],
        },
        "reason_tags_distribution": {
            "black": {"by_category": {"heavy": 3}},
            "white": {},
        },
    }


@pytest.fixture
def beginner_config() -> PromptConfig:
    return PromptConfig(
        voice=ToneVoice.AYAKA,
        mode=CoachMode.BEGINNER,
        detected_symptom_ids=(SymptomId.ATARI_BLINDNESS,),
    )


@pytest.fixture
def expert_strict_config() -> PromptConfig:
    return PromptConfig(
        voice=ToneVoice.TOMOKO_STRICT,
        mode=CoachMode.EXPERT,
        detected_symptom_ids=(),
    )


@pytest.fixture
def beginner_prompt(sample_karte, beginner_config):
    return build_translation_prompt(sample_karte, beginner_config)


# --- Symptom id existence ---


class TestSymptomIdCheck:
    def test_unknown_id_flagged(self, sample_karte, beginner_config, beginner_prompt):
        text = (
            "考察:\nあかん、ここは致命的やな。\n"
            "参照した症状ID: [fake_hallucination_id]\n"
        )
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert not report.is_clean
        kinds = [i.kind for i in report.issues]
        assert "unknown_symptom_id" in kinds
        # Context should preserve the unknown id
        issue = next(i for i in report.issues if i.kind == "unknown_symptom_id")
        assert issue.context["symptom_id"] == "fake_hallucination_id"
        assert issue.severity == ValidationSeverity.HIGH

    def test_karte_known_id_accepted(self, sample_karte, beginner_config, beginner_prompt):
        # capture_race_loss is in important_moves[*].meaning_tag_id
        # blunder / mistake are in weaknesses[*].category
        # atari_blindness is in config.detected_symptom_ids
        text = (
            "考察:\n弱点は capture_race_loss, blunder, atari_blindness です。\n"
            "参照した症状ID: [capture_race_loss, blunder, atari_blindness]\n"
        )
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert report.is_clean, f"got issues: {report.issues}"

    def test_no_reference_line_skips_check(self, sample_karte, beginner_config, beginner_prompt):
        text = "短い考察: あかん、ここは難しい。"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        # No "参照した症状ID" line → no symptom validation issues (other checks may run)
        sym_issues = [i for i in report.issues if i.kind == "unknown_symptom_id"]
        assert sym_issues == []

    def test_multiple_unknown_ids_each_flagged(self, sample_karte, beginner_config, beginner_prompt):
        text = (
            "考察:\n"
            "参照した症状ID: [id_a, atari_blindness, id_b, capture_race_loss]\n"
        )
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        kinds = [i for i in report.issues if i.kind == "unknown_symptom_id"]
        # id_a, id_b should be flagged; atari_blindness / capture_race_loss are valid
        bad = sorted(k.context["symptom_id"] for k in kinds)
        assert "id_a" in bad
        assert "id_b" in bad
        assert "atari_blindness" not in bad
        assert "capture_race_loss" not in bad


# --- Move number range ---


class TestMoveNumberCheck:
    def test_in_range_accepted(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: 50手目 が悪い。\n" "参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        move_issues = [i for i in report.issues if i.kind == "move_number_out_of_range"]
        assert move_issues == []

    def test_out_of_range_flagged(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: 999手目 が悪い。\n" "参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        move_issues = [i for i in report.issues if i.kind == "move_number_out_of_range"]
        assert len(move_issues) == 1
        assert move_issues[0].context["move_number"] == 999

    def test_move_zero_flagged(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: 0手目 が悪い。\n" "参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        kinds = [i.kind for i in report.issues]
        assert "move_number_out_of_range" in kinds


# --- pointsLost outlier check ---


class TestPointsLostCheck:
    def test_reasonable_value_not_flagged(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: 3.0目 損しています。\n" "参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        loss_issues = [i for i in report.issues if i.kind == "points_lost_outlier"]
        assert loss_issues == []

    def test_extreme_value_flagged(self, sample_karte, beginner_config, beginner_prompt):
        # max_loss in fixture = 5.0, ceiling = 7.5. 50.0 should trip it.
        text = "考察: 50.0目 損している！？\n" "参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        loss_issues = [i for i in report.issues if i.kind == "points_lost_outlier"]
        assert len(loss_issues) == 1
        assert loss_issues[0].context["value"] == 50.0

    def test_no_summary_skips_check(self, beginner_config, beginner_prompt):
        # Karte JSON without summary.total_moves or important_moves.points_lost
        # should not crash the validator.
        empty_karte = {"schema_version": "3.4"}
        text = "考察: 3.0目 損しています。\n" "参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, empty_karte, beginner_prompt, config=beginner_config)
        # No pointsLost issue should be raised since we can't determine max
        loss_issues = [i for i in report.issues if i.kind == "points_lost_outlier"]
        assert loss_issues == []


# --- Tone consistency ---


class TestToneConsistency:
    def test_ayaka_with_short_text_not_flagged(
        self, sample_karte, beginner_config, beginner_prompt
    ):
        text = "短い考察: ウチが見た。参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        tone_issues = [i for i in report.issues if i.kind == "tone_inconsistency_ayaka"]
        assert tone_issues == []

    def test_ayaka_long_text_no_kansai_flagged(
        self, sample_karte, beginner_config, beginner_prompt
    ):
        # Long formal-style text with no Kansai markers — flagged
        text = "考察:" + "これは標準語で記述された長い考察です。" * 20 + "\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        tone_issues = [i for i in report.issues if i.kind == "tone_inconsistency_ayaka"]
        assert len(tone_issues) == 1

    def test_tomoko_with_kansai_flagged(
        self, sample_karte, expert_strict_config
    ):
        # TOMOKO_STRICT but Kansai markers present
        prompt = build_translation_prompt(sample_karte, expert_strict_config)
        text = "考察:" + "ウチが見た。あかん。" * 5 + "\n参照した症状ID: []\n"
        report = validate_llm_output(text, sample_karte, prompt, config=expert_strict_config)
        tone_issues = [i for i in report.issues if i.kind == "tone_inconsistency_tomoko"]
        assert len(tone_issues) == 1


# --- Summary line ---


class TestSummaryLine:
    def test_clean_summary(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: ウチが見た。あかん、ここは端的に言うと致命的や。\n" "参照した症状ID: [atari_blindness, capture_race_loss]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert report.is_clean
        assert "✅" in report.summary_line()

    def test_warning_summary(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: あかん。\n" "参照した症状ID: [fake_id]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert not report.is_clean
        line = report.summary_line()
        assert "⚠️" in line
        assert "高" in line


# --- Never-raises contract ---


class TestRobustness:
    def test_empty_text(self, sample_karte, beginner_config, beginner_prompt):
        report = validate_llm_output("", sample_karte, beginner_prompt, config=beginner_config)
        assert isinstance(report, ValidationReport)

    def test_empty_karte(self, beginner_config, beginner_prompt):
        report = validate_llm_output(
            "考察: ウチが見た。",
            {},
            beginner_prompt,
            config=beginner_config,
        )
        assert isinstance(report, ValidationReport)

    def test_no_config(self, sample_karte, beginner_prompt):
        text = "考察: あかん。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=None)
        assert isinstance(report, ValidationReport)

    def test_extreme_values(self, sample_karte, beginner_config, beginner_prompt):
        # Move numbers far out of range + extreme values
        text = (
            "考察: 9999手目で 999.9目 損。\n"
            "参照した症状ID: [atari_blindness, fake_id]\n"
        )
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        # Should not raise; may or may not detect issues depending on regex behaviour
        assert isinstance(report, ValidationReport)


# --- Public API ---


class TestExports:
    def test_all_reexports(self):
        import katrain.core.coach as pkg

        for name in [
            "ValidationSeverity",
            "ValidationIssue",
            "ValidationReport",
            "validate_llm_output",
        ]:
            assert hasattr(pkg, name), f"__init__ missing {name}"
