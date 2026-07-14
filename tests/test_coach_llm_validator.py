"""Phase 212 / Phase 226-A: Tests for katrain.core.coach.llm_validator.

Covers:
- Symptom id existence check (against Karte + prompt + config)
- Move number range check
- pointsLost outlier check (within tolerance)
- Tone consistency check (AYAKA vs TOMOKO)
- ValidationReport summary helpers
- Never-raises contract (returns report even on bad input)

Phase 226-A additions:
- A1: Lexicon validation now actually works (English id ↔ ja_term bridge)
- A2: 3-tier fallback for symptom id extraction (trailing line + inline + grep)
- A3: Strict move-number regex (no false positives on 5段 / 30級 / 2026年)
- A4: Extended pointsLost regex (損失 / ロス / points lost)
- A5: player_color integration (opponent's symptom ids → MEDIUM demotion)
- A6: tolerance parameter applied to ceiling comparison
"""

from __future__ import annotations

import pytest

from katrain.core.coach.llm_validator import (
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


# --- Phase 226-A: A1 Lexicon validation ---


class TestLexiconValidation:
    """Phase 226-A A1: Lexicon cross-reference is now functional.

    Previous behaviour: the English-id ↔ Japanese-term bridge was
    broken, so ``_extract_lexicon_mentions`` always returned an empty
    tuple and no warnings were generated. The new code:
    - counts injected ids in ``referenced_lexicon_ids``
    - flags off-injection ja_terms used in 「」 brackets as LOW
    """

    def test_injected_ja_term_counted(self, sample_karte, beginner_config, beginner_prompt):
        # ``liberty`` and ``atari`` are injected; their ja_terms are
        # 「呼吸点」 and 「アタリ」. We only need to check that the
        # referenced_lexicon_ids field surfaces them.
        text = (
            "考察: 「呼吸点」が足りない局面。\n"
            "参照した症状ID: [atari_blindness]\n"
        )
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        # No off-injection warnings (the term was injected).
        off = [i for i in report.issues if i.kind == "lexicon_mention_not_injected"]
        assert off == [], f"unexpected off-injection warnings: {off}"

    def test_off_injection_ja_term_flagged(self, sample_karte, beginner_config, beginner_prompt):
        # Use a term that's unlikely to be in the default injection
        # block. The full lexicon has 116 entries, so we pick one whose
        # ja_term is known to exist.
        from katrain.core.coach.lexicon import load_lexicon

        bundle = load_lexicon()
        all_ja = {e.ja_term for e in bundle.entries}
        # Take the first ja_term that the injection (liberty, atari) does
        # NOT cover, and that is at least 3 characters long so it fits
        # the regex.
        injected_ja = {"呼吸点", "アタリ"}
        candidate = next(
            (ja for ja in sorted(all_ja) if ja not in injected_ja and len(ja) >= 3),
            None,
        )
        if candidate is None:
            pytest.skip("No off-injection candidate available in the bundle")
        text = (
            f"考察: 「{candidate}」が鍵。\n"
            "参照した症状ID: [atari_blindness]\n"
        )
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        off = [i for i in report.issues if i.kind == "lexicon_mention_not_injected"]
        assert len(off) == 1
        assert off[0].context["term"] == candidate
        assert off[0].severity == ValidationSeverity.LOW

    def test_injected_term_does_not_warn(self, sample_karte, beginner_config, beginner_prompt):
        text = (
            "考察: 「呼吸点」「アタリ」が重要。\n"
            "参照した症状ID: [atari_blindness]\n"
        )
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        off = [i for i in report.issues if i.kind == "lexicon_mention_not_injected"]
        assert off == []


# --- Phase 226-A: A2 Symptom id extraction (3-tier fallback) ---


class TestSymptomIdExtractionFallbacks:
    """Phase 226-A A2: 3-tier symptom id extraction."""

    def test_tier1_trailing_line(self, sample_karte, beginner_config, beginner_prompt):
        text = (
            "考察: atari_blindness がひどい。\n"
            "参照した症状ID: [atari_blindness]\n"
        )
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert "atari_blindness" in report.referenced_symptom_ids

    def test_tier2_inline_marker(self, sample_karte, beginner_config, beginner_prompt):
        # Inline marker mid-text (no trailing line).
        text = "考察: 症状: [atari_blindness, capture_race_loss] が鍵。\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert "atari_blindness" in report.referenced_symptom_ids
        assert "capture_race_loss" in report.referenced_symptom_ids

    def test_tier2_english_inline(self, sample_karte, beginner_config, beginner_prompt):
        text = "Consider Symptoms: [atari_blindness, capture_race_loss] here.\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert "atari_blindness" in report.referenced_symptom_ids
        assert "capture_race_loss" in report.referenced_symptom_ids

    def test_tier3_safety_grep(self, sample_karte, beginner_config, beginner_prompt):
        # No marker, but the known id is mentioned in prose.
        text = "考察: atari_blindness が頻発。\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        # Tier 3 should pick it up.
        assert "atari_blindness" in report.referenced_symptom_ids

    def test_tier3_does_not_pick_unknown(self, sample_karte, beginner_config, beginner_prompt):
        # No marker, and the id is unknown — should NOT be picked up
        # by tier 3 because it's not in the known id set.
        text = "考察: fake_hallucination_id がひどい。\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        # Tier 1+2 find nothing; tier 3 only searches known ids.
        assert "fake_hallucination_id" not in report.referenced_symptom_ids


# --- Phase 226-A: A3 Strict move-number regex ---


class TestMoveNumberStrictness:
    """Phase 226-A A3: move-number regex is now strict."""

    def test_hash_prefix_matches(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: #50 が悪い。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        # 50 is in range so no issue
        move_issues = [i for i in report.issues if i.kind == "move_number_out_of_range"]
        assert move_issues == []
        assert 50 in report.referenced_move_numbers

    def test_move_prefix_matches(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: move 50 が悪い。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert 50 in report.referenced_move_numbers

    def test_kanji_suffix_matches(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: 50手目 が悪い。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert 50 in report.referenced_move_numbers

    def test_bare_kanji_matches(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: 50手 で形が悪い。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert 50 in report.referenced_move_numbers

    def test_rank_excluded(self, sample_karte, beginner_config, beginner_prompt):
        # "5段" / "30級" / "2026年" / "7月" should NOT be treated as
        # move numbers.
        text = (
            "考察: 5段の相手に 30級で対局。2026年7月の対局。\n"
            "参照した症状ID: [atari_blindness]\n"
        )
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        # None of the rank/year values should leak in.
        for forbidden in (5, 30, 2026, 7):
            assert forbidden not in report.referenced_move_numbers, (
                f"value {forbidden} leaked into move numbers"
            )

    def test_percentage_excluded(self, sample_karte, beginner_config, beginner_prompt):
        # "勝率50%" should not contribute 50 to move numbers.
        text = "考察: 勝率50%だった。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert 50 not in report.referenced_move_numbers


# --- Phase 226-A: A4 Extended pointsLost patterns ---


class TestPointsLostExtraction:
    """Phase 226-A A4: pointsLost regex accepts more phrasings."""

    def test_kanji_unit(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: 3.0目 損している。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert 3.0 in report.referenced_points_lost

    def test_sonshitsu_keyword(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: 損失 3.0 が大きい。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert 3.0 in report.referenced_points_lost

    def test_rosu_keyword(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: ロス 3.0 が深刻。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert 3.0 in report.referenced_points_lost

    def test_english_phrase(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: 3.0 points lost overall.\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert 3.0 in report.referenced_points_lost

    def test_loss_keyword(self, sample_karte, beginner_config, beginner_prompt):
        text = "考察: loss: 3.0 was significant.\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(text, sample_karte, beginner_prompt, config=beginner_config)
        assert 3.0 in report.referenced_points_lost


# --- Phase 226-A: A5 player-color integration ---


class TestPlayerColorIntegration:
    """Phase 226-A A5: opponent's symptom id → MEDIUM demotion."""

    @pytest.fixture
    def black_view_config(self) -> PromptConfig:
        return PromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            detected_symptom_ids=(SymptomId.ATARI_BLINDNESS,),
            player_color="B",
        )

    @pytest.fixture
    def black_prompt(self, sample_karte, black_view_config):
        return build_translation_prompt(sample_karte, black_view_config)

    def test_opponent_symptom_demoted_to_medium(
        self, sample_karte, black_view_config, black_prompt
    ):
        # Add a white-only symptom to the karte so that under player_color=B
        # (own=black), referencing sente_gote_confusion should demote
        # the issue from HIGH to MEDIUM with a distinct kind.
        sample_karte["weaknesses"]["white"] = [{"category": "sente_gote_confusion"}]
        text = (
            "考察: sente_gote_confusion は白だけ。\n"
            "参照した症状ID: [sente_gote_confusion]\n"
        )
        report = validate_llm_output(
            text, sample_karte, black_prompt, config=black_view_config
        )
        # The symptom is in white's weaknesses but not in black's, so
        # under player_color=B it should be demoted to MEDIUM.
        demoted = [
            i for i in report.issues if i.kind == "symptom_id_belongs_to_opponent"
        ]
        assert len(demoted) == 1
        assert demoted[0].severity == ValidationSeverity.MEDIUM
        assert demoted[0].context["symptom_id"] == "sente_gote_confusion"
        assert demoted[0].context["own_color"] == "black"
        assert demoted[0].context["opp_color"] == "white"

    def test_own_symptom_no_issue(
        self, sample_karte, black_view_config, black_prompt
    ):
        # blunder is in black's weaknesses. Own colour → no demotion.
        text = (
            "考察: blunder が深刻。\n"
            "参照した症状ID: [blunder]\n"
        )
        report = validate_llm_output(
            text, sample_karte, black_prompt, config=black_view_config
        )
        demoted = [
            i for i in report.issues if i.kind == "symptom_id_belongs_to_opponent"
        ]
        assert demoted == []

    def test_no_player_color_keeps_high(
        self, sample_karte, beginner_config, beginner_prompt
    ):
        # No player_color set → no demotion logic kicks in. The symptom
        # still goes through the normal HIGH unknown-id path (which is
        # fine because the id is also not in karte).
        text = (
            "考察: nonsense_id in prose.\n"
            "参照した症状ID: [nonsense_id]\n"
        )
        report = validate_llm_output(
            text, sample_karte, beginner_prompt, config=beginner_config
        )
        high_unknown = [
            i for i in report.issues
            if i.kind == "unknown_symptom_id" and i.severity == ValidationSeverity.HIGH
        ]
        assert len(high_unknown) == 1
        assert high_unknown[0].context["symptom_id"] == "nonsense_id"


# --- Phase 226-A: A6 tolerance parameter ---


class TestToleranceParameter:
    """Phase 226-A A6: tolerance is now applied to the ceiling."""

    def test_at_ceiling_accepted(self, sample_karte, beginner_config, beginner_prompt):
        # max_loss=5.0, ceiling=7.5, boundary=7.55 (default tolerance).
        text = "考察: 7.5目 損した。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(
            text, sample_karte, beginner_prompt, config=beginner_config
        )
        loss_issues = [i for i in report.issues if i.kind == "points_lost_outlier"]
        assert loss_issues == []

    def test_just_above_ceiling_flagged(self, sample_karte, beginner_config, beginner_prompt):
        # 7.6目 > boundary(7.55) → flagged
        text = "考察: 7.6目 損した。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(
            text, sample_karte, beginner_prompt, config=beginner_config
        )
        loss_issues = [i for i in report.issues if i.kind == "points_lost_outlier"]
        assert len(loss_issues) == 1

    def test_well_above_ceiling_flagged(self, sample_karte, beginner_config, beginner_prompt):
        # 50.0目 > boundary(7.55) → flagged
        text = "考察: 50.0目 損した。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(
            text, sample_karte, beginner_prompt, config=beginner_config
        )
        loss_issues = [i for i in report.issues if i.kind == "points_lost_outlier"]
        assert len(loss_issues) == 1

    def test_higher_tolerance_relaxes_check(
        self, sample_karte, beginner_config, beginner_prompt
    ):
        # With tolerance=2.0, boundary becomes 9.5. So 8.0 is now within
        # the boundary.
        text = "考察: 8.0目 損した。\n参照した症状ID: [atari_blindness]\n"
        report = validate_llm_output(
            text,
            sample_karte,
            beginner_prompt,
            config=beginner_config,
            tolerance=2.0,
        )
        loss_issues = [i for i in report.issues if i.kind == "points_lost_outlier"]
        assert loss_issues == []


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
