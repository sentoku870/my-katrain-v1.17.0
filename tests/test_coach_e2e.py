"""Phase 213: End-to-end test for the LLM translation pipeline.

This test wires all six coach modules together:

    master_db → tones → symptom_index → lexicon → prompt_builder → validator

A mock LLM (deterministic fixed-string per symptom profile) supplies
the LLM response. The validator is then run against the mock output.

Why a mock LLM:
- The real LLM is offline / external; we can't call it from CI
- Mocking deterministically reproduces the validation behaviour
- The structure of the LLM prompt is the critical part under test

Three end-to-end scenarios:
1. AYAKA / BEGINNER / Atari Blindness detected — short clean response
2. TOMOKO / DAN / Big Point Blindness detected — long structured response
3. EXPERT / TOMOKO_STRICT — expert response with minor validation issues
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
from katrain.core.coach.symptom_index import (
    SymptomContext,
    SymptomId,
    detect_auto_symptoms,
)
from katrain.core.coach.tones import select_voice


# --- Mock LLM factory ---


def _mock_llm(prompt_text: str, profile: str) -> str:
    """Deterministic mock LLM that returns a profile-shaped response.

    Profiles:
    - 'ayaka_beginner': short, casual Kansai, few symptom IDs
    - 'tomoko_dan': medium, structured standard Japanese
    - 'expert_strict': long, formal, direct

    Each profile respects the prompt contract:
    1. Mentions symptom IDs that exist
    2. Cites move numbers in valid range
    3. Ends with ``参照した症状ID: [...]`` line
    """
    if profile == "ayaka_beginner":
        return (
            "ウチが見た感じ、ここはあかんね。\n"
            "着手 30手目 で呼吸点の見落としが出とる。\n"
            "まずアタリを確認することからはじめよか。\n"
            "参照した症状ID: [atari_blindness, capture_race_loss]\n"
        )
    if profile == "tomoko_dan":
        return (
            "主テーマ: 方向感覚のずれと大場の見落とし。\n"
            "副テーマ: 中盤のヨセ精度。\n"
            "着手 100手目 で大場を逃しています。\n"
            "参照した症状ID: [big_point_blindness, territorial_loss, endgame_valuation_error]\n"
        )
    if profile == "expert_strict":
        return (
            "率直に言います。\n"
            "主テーマ: 形勢判断の構造的欠陥。\n"
            "着手 200手目 でビハインド時のリスク調整を誤っています。\n"
            "ウチの解釈（関西弁マーカー）も含めて: 通常なら慎重策。\n"
            "参照した症状ID: [evaluation_errors, risk_miscalibration, fantasy_id]\n"
        )
    raise ValueError(f"unknown profile: {profile}")


# --- Helpers ---


@pytest.fixture
def sample_karte() -> dict:
    """Realistic Karte JSON with 200 moves and known weaknesses."""
    return {
        "schema_version": "3.4",
        "meta": {
            "schema_version": "3.4",
            "game_id": "e2e-test",
            "players": {"black": "Player1", "white": "Player2"},
        },
        "summary": {"total_moves": 200},
        "important_moves": [
            {"meaning_tag_id": "atari_blindness", "points_lost": 1.5},
            {"meaning_tag_id": "capture_race_loss", "points_lost": 2.5},
            {"meaning_tag_id": "big_point_blindness", "points_lost": 3.0},
            {"meaning_tag_id": "territorial_loss", "points_lost": 5.0},
        ],
        "weaknesses": {
            "black": [
                {"category": "atari_blindness"},
                {"category": "big_point_blindness"},
                {"category": "territorial_loss"},
            ],
            "white": [],
        },
        "reason_tags_distribution": {
            "black": {"by_category": {"endgame": 2}},
            "white": {},
        },
    }


# --- Scenario 1: AYAKA / BEGINNER ---


class TestE2EAyakaBeginner:
    def test_pipeline_runs_clean(self, sample_karte):
        # 1. Detection
        ctx = SymptomContext(
            points_lost=2.0,
            move_number=30,
            meaning_tag_ids=(),  # simplified for e2e
        )
        detected = detect_auto_symptoms(ctx)
        # 2. Mode selection (rank "10k" → INTERMEDIATE → AYAKA)
        voice = select_voice("10k")
        # 3. Build prompt
        cfg = PromptConfig(
            voice=voice,
            mode=CoachMode.INTERMEDIATE,
            detected_symptom_ids=tuple(detected) or (SymptomId.ATARI_BLINDNESS,),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        # 4. Mock LLM
        llm_output = _mock_llm(prompt.full_markdown, "ayaka_beginner")
        # 5. Validate
        report = validate_llm_output(llm_output, sample_karte, prompt, config=cfg)

        # The ayaka response mentions atari_blindness + capture_race_loss,
        # both of which are valid in karte. capture_race_loss is in
        # important_moves[].meaning_tag_id, atari_blindness is in config.
        # The response also uses Kansai markers and is short → no tone warning.
        # We expect: unknown_symptom_id for any id not in {karte ids, prompt ids, config ids}.
        bad = [i for i in report.issues if i.kind == "unknown_symptom_id"]
        assert bad == [], f"unexpected bad ids: {[i.context for i in bad]}"

    def test_prompt_contains_required_rubrics(self, sample_karte):
        cfg = PromptConfig(
            voice=ToneVoice.AYAKA,
            mode=CoachMode.BEGINNER,
            detected_symptom_ids=(SymptomId.ATARI_BLINDNESS,),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        # Phase 203 §5.3 contract: required rubrics
        assert "[SYSTEM INSTRUCTION FOR LLM]" in prompt.system_instruction
        assert "[LEXICON INJECTION]" in prompt.lex_injection
        assert "STRICT RULES" in prompt.system_instruction
        assert "DO NOT analyze the board independently" in prompt.system_instruction
        assert "DO NOT invent move numbers" in prompt.system_instruction
        assert "Every symptom_id" in prompt.system_instruction
        assert "参照した症状ID:" in prompt.system_instruction


# --- Scenario 2: TOMOKO / DAN ---


class TestE2ETomokoDan:
    def test_pipeline_runs_clean(self, sample_karte):
        voice = select_voice("4k")  # → DAN → TOMOKO
        cfg = PromptConfig(
            voice=voice,
            mode=CoachMode.DAN,
            detected_symptom_ids=(
                SymptomId.BIG_POINT_BLINDNESS,
                SymptomId.ENDGAME_VALUATION_ERROR,
            ),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        llm_output = _mock_llm(prompt.full_markdown, "tomoko_dan")
        report = validate_llm_output(llm_output, sample_karte, prompt, config=cfg)

        # All 3 IDs in the tomoko response are in the config
        # (big_point_blindness, territorial_loss, slow_move).
        # territorial_loss is in Karte weakness.
        bad = [i for i in report.issues if i.kind == "unknown_symptom_id"]
        assert bad == []

    def test_long_tomoko_text_no_kansai_passes(self, sample_karte):
        voice = select_voice("4k")
        cfg = PromptConfig(
            voice=voice,
            mode=CoachMode.DAN,
            detected_symptom_ids=(SymptomId.BIG_POINT_BLINDNESS,),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        llm_output = _mock_llm(prompt.full_markdown, "tomoko_dan")
        report = validate_llm_output(llm_output, sample_karte, prompt, config=cfg)
        # TOMOKO + no Kansai markers → no tone warning
        tone_issues = [
            i for i in report.issues
            if i.kind in ("tone_inconsistency_ayaka", "tone_inconsistency_tomoko")
        ]
        assert tone_issues == []


# --- Scenario 3: EXPERT / TOMOKO_STRICT ---


class TestE2EExpertStrict:
    def test_tomoko_strict_response_with_validation_issues(self, sample_karte):
        voice = select_voice("7d")  # → EXPERT → TOMOKO_STRICT
        cfg = PromptConfig(
            voice=voice,
            mode=CoachMode.EXPERT,
            detected_symptom_ids=(
                SymptomId.EVALUATION_ERRORS,
                SymptomId.RISK_MISCALIBRATION,
            ),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        llm_output = _mock_llm(prompt.full_markdown, "expert_strict")
        report = validate_llm_output(llm_output, sample_karte, prompt, config=cfg)

        # 'fantasy_id' is in the LLM output but NOT in the karte or config.
        # Should be flagged HIGH.
        bad = [i for i in report.issues if i.kind == "unknown_symptom_id"]
        assert len(bad) >= 1
        bad_ids = {i.context["symptom_id"] for i in bad}
        assert "fantasy_id" in bad_ids

    def test_kansai_marker_in_tomoko_strict_flagged(self, sample_karte):
        voice = select_voice("7d")
        cfg = PromptConfig(
            voice=voice,
            mode=CoachMode.EXPERT,
            detected_symptom_ids=(SymptomId.EVALUATION_ERRORS,),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        llm_output = _mock_llm(prompt.full_markdown, "expert_strict")
        report = validate_llm_output(llm_output, sample_karte, prompt, config=cfg)

        # TOMOKO_STRICT response contains "ウチの解釈（関西弁マーカー）も含めて"
        # → tone_inconsistency_tomoko warning expected.
        tone_issues = [
            i for i in report.issues if i.kind == "tone_inconsistency_tomoko"
        ]
        assert len(tone_issues) == 1

    def test_validation_summary_reflects_issues(self, sample_karte):
        voice = select_voice("7d")
        cfg = PromptConfig(
            voice=voice,
            mode=CoachMode.EXPERT,
            detected_symptom_ids=(
                SymptomId.EVALUATION_ERRORS,
                SymptomId.RISK_MISCALIBRATION,
            ),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        llm_output = _mock_llm(prompt.full_markdown, "expert_strict")
        report = validate_llm_output(llm_output, sample_karte, prompt, config=cfg)

        # Should have ≥1 high (fantasy_id) and ≥1 low (kansai marker)
        assert report.high_count >= 1
        assert report.low_count >= 1

        # summary line should show ⚠️
        assert "⚠️" in report.summary_line()


# --- All modules wire correctly ---


class TestPipelineIntegration:
    def test_all_modules_imported(self):
        # If anything is broken, the imports at the top would fail.
        from katrain.core.coach import (
            CoachMode,
            ToneVoice,
            SymptomId,
            build_translation_prompt,
            validate_llm_output,
            select_voice,
        )
        assert all([
            CoachMode,
            ToneVoice,
            SymptomId,
            build_translation_prompt,
            validate_llm_output,
            select_voice,
        ])

    def test_six_phase_modules_together(self, sample_karte):
        """Run the entire pipeline symbolically in a single test."""
        # Phase 207 (master_db): choose mode
        voice = select_voice("5k")
        from katrain.core.coach.master_db import CoachMode as Mode, get_mode_config
        mode = get_mode_config(Mode.INTERMEDIATE).mode
        # Phase 208 (lexicon): implicit via prompt_builder
        # Phase 209 (symptom_index): detected symptoms
        ctx = SymptomContext(
            points_lost=2.5,
            move_number=80,
            meaning_tag_ids=(),
        )
        detected = tuple(detect_auto_symptoms(ctx)) or (SymptomId.LIFE_DEATH_MISJUDGMENT,)
        # Phase 210 (tones): voice handled
        # Phase 211 (prompt_builder): build prompt
        cfg = PromptConfig(
            voice=voice,
            mode=mode,
            detected_symptom_ids=detected,
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        # Phase 212 (validator): validate
        llm_output = _mock_llm(prompt.full_markdown, "tomoko_dan")
        report = validate_llm_output(llm_output, sample_karte, prompt, config=cfg)
        assert isinstance(report, ValidationReport)
        # Full pipeline completed without crashing.
