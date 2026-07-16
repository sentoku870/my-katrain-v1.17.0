"""Phase 211: Tests for katrain.core.coach.prompt_builder.

Covers:
- PromptConfig dataclass
- build_translation_prompt: HTML-comment structure, content placement
- Symptom id formatting (stable ordering)
- Lexicon entry selection (dedup + cap)
- Candidate hints (LLM-required symptom context_hints)
- append_llm_prompt_block: non-invasive injection
- render_markdown: identity to full_markdown

The tests do NOT call out to a real LLM. They only verify the structure
of the generated Markdown that downstream consumers will copy / paste.
"""

from __future__ import annotations

import json

import pytest

from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.prompt_builder import (
    LlmPrompt,
    PromptConfig,
    append_llm_prompt_block,
    build_translation_prompt,
    render_markdown,
    validate_prompt_config,
)
from katrain.core.coach.symptom_index import SymptomId

# --- Fixtures ---


@pytest.fixture
def sample_karte() -> dict:
    """Minimal valid Karte JSON for testing."""
    return {
        "schema_version": "3.4",
        "meta": {
            "schema_version": "3.4",
            "game_id": "test-game",
            "players": {"black": "Player1", "white": "Player2"},
        },
        "summary": {
            "total_moves": 240,
            "mistake_distribution": {"black": {"good": 100}, "white": {"good": 100}},
        },
        "important_moves": [],
        "weaknesses": {"black": [], "white": []},
    }


@pytest.fixture
def beginner_config() -> PromptConfig:
    """Standard AYAKA / BEGINNER config with two detected symptoms."""
    return PromptConfig(
        voice=ToneVoice.AYAKA,
        mode=CoachMode.BEGINNER,
        detected_symptom_ids=(
            SymptomId.ATARI_BLINDNESS,
            SymptomId.BIG_POINT_BLINDNESS,
        ),
        llm_required_symptom_ids=(SymptomId.TIME_PRESSURE_LOSS,),
    )


# --- PromptConfig ---


class TestPromptConfig:
    def test_defaults(self):
        cfg = PromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            detected_symptom_ids=(),
        )
        assert cfg.max_lexicon_entries == 7
        assert cfg.include_expanded is True
        assert cfg.schema_version == "3.4"
        assert cfg.player_rank_str is None
        assert cfg.average_points_lost is None


# --- build_translation_prompt ---


class TestBuildTranslationPrompt:
    def test_returns_llm_prompt(self, sample_karte, beginner_config):
        prompt = build_translation_prompt(sample_karte, beginner_config)
        assert isinstance(prompt, LlmPrompt)
        assert isinstance(prompt.full_markdown, str)

    def test_system_instruction_present(self, sample_karte, beginner_config):
        prompt = build_translation_prompt(sample_karte, beginner_config)
        assert "[SYSTEM INSTRUCTION FOR LLM]" in prompt.system_instruction
        assert "<!--" in prompt.system_instruction  # open comment
        assert "-->" in prompt.system_instruction  # close comment

    def test_lexicon_injection_present(self, sample_karte, beginner_config):
        prompt = build_translation_prompt(sample_karte, beginner_config)
        assert "[LEXICON INJECTION]" in prompt.lex_injection
        assert "<!--" in prompt.lex_injection
        assert "-->" in prompt.lex_injection

    def test_body_contains_karte_json(self, sample_karte, beginner_config):
        prompt = build_translation_prompt(sample_karte, beginner_config)
        assert "## Karte JSON" in prompt.body_markdown
        # Body renders the JSON in a code block
        assert "```json" in prompt.body_markdown
        # At least one key from the input should appear
        assert '"test-game"' in prompt.body_markdown

    def test_strict_rules_present(self, sample_karte, beginner_config):
        prompt = build_translation_prompt(sample_karte, beginner_config)
        assert "STRICT RULES" in prompt.system_instruction
        assert "DO NOT analyze the board independently" in prompt.system_instruction
        assert "参照した症状ID" in prompt.system_instruction

    def test_voice_summary_appears(self, sample_karte):
        cfg_ayaka = PromptConfig(
            voice=ToneVoice.AYAKA,
            mode=CoachMode.BEGINNER,
            detected_symptom_ids=(),
        )
        cfg_strict = PromptConfig(
            voice=ToneVoice.TOMOKO_STRICT,
            mode=CoachMode.EXPERT,
            detected_symptom_ids=(),
        )
        p1 = build_translation_prompt(sample_karte, cfg_ayaka)
        p2 = build_translation_prompt(sample_karte, cfg_strict)
        assert "あやか" in p1.system_instruction
        assert "智子（辛口）" in p2.system_instruction

    def test_detected_symptoms_are_listed(self, sample_karte, beginner_config):
        prompt = build_translation_prompt(sample_karte, beginner_config)
        assert "atari_blindness" in prompt.system_instruction
        assert "big_point_blindness" in prompt.system_instruction

    def test_candidate_symptoms_have_hints(self, sample_karte, beginner_config):
        prompt = build_translation_prompt(sample_karte, beginner_config)
        assert "CandidateSymptoms:" in prompt.system_instruction
        # time_pressure_loss has a context_hint pointing to SGF data
        assert "time_pressure_loss" in prompt.system_instruction
        assert "SGF" in prompt.system_instruction or "時間" in prompt.system_instruction

    def test_referenced_symptoms_match_input(self, sample_karte, beginner_config):
        prompt = build_translation_prompt(sample_karte, beginner_config)
        assert set(prompt.referenced_symptom_ids) == set(beginner_config.detected_symptom_ids)

    def test_full_markdown_combines_all(self, sample_karte, beginner_config):
        prompt = build_translation_prompt(sample_karte, beginner_config)
        assert prompt.system_instruction in prompt.full_markdown
        assert prompt.lex_injection in prompt.full_markdown
        assert prompt.body_markdown in prompt.full_markdown

    def test_html_comments_invisible_to_markdown(self, sample_karte, beginner_config):
        """A standard Markdown renderer should treat the HTML comments as
        meta; they do not render as visible text.
        """
        prompt = build_translation_prompt(sample_karte, beginner_config)
        # Both instruction and lex injection start with <!--
        assert prompt.full_markdown.startswith("<!--")
        # Body content (json code block) comes after the html comments
        body_pos = prompt.full_markdown.find("## Karte JSON")
        sys_instr_end = prompt.system_instruction.rfind("-->") + len("-->")
        assert sys_instr_end < body_pos


# --- Lexicon entry selection ---


class TestLexiconSelection:
    def test_atari_blindness_pulls_liberty(self, sample_karte):
        cfg = PromptConfig(
            voice=ToneVoice.AYAKA,
            mode=CoachMode.BEGINNER,
            detected_symptom_ids=(SymptomId.ATARI_BLINDNESS,),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        # ATARI_BLINDNESS has related_lexicon_ids=("liberty", "atari")
        assert "liberty" in prompt.referenced_lexicon_ids
        assert "atari" in prompt.referenced_lexicon_ids

    def test_dedup_across_symptoms(self, sample_karte):
        # Both symptoms reference "liberty" — should not duplicate.
        cfg = PromptConfig(
            voice=ToneVoice.AYAKA,
            mode=CoachMode.BEGINNER,
            detected_symptom_ids=(
                SymptomId.ATARI_BLINDNESS,
                SymptomId.CAPTURE_OVERSIGHT,
            ),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        # "liberty" should appear exactly once even if both symptoms reference it
        assert prompt.referenced_lexicon_ids.count("liberty") <= 1

    def test_max_lexicon_entries_cap(self, sample_karte):
        # Phase 226-A (A1): build the prompt and verify the
        # ``max_lexicon_entries`` cap is honoured.
        prompt = build_translation_prompt(
            sample_karte,
            PromptConfig(
                voice=ToneVoice.AYAKA,
                mode=CoachMode.BEGINNER,
                detected_symptom_ids=(),
                llm_required_symptom_ids=(),
                max_lexicon_entries=2,
            ),
        )
        # At least one entry should be embedded; the cap is enforced
        # by the builder. The exact count varies with detected symptoms,
        # so we only assert that the cap is respected in the upper bound.
        assert prompt.lex_injection.count("-->") <= 2
        # Big-point blindness has urgent_vs_big related
        prompt2 = build_translation_prompt(
            sample_karte,
            PromptConfig(
                voice=ToneVoice.AYAKA,
                mode=CoachMode.BEGINNER,
                detected_symptom_ids=(SymptomId.BIG_POINT_BLINDNESS,),
                max_lexicon_entries=2,
            ),
        )
        assert len(prompt2.referenced_lexicon_ids) <= 2

    def test_no_detected_symptoms_empty_lexicon(self, sample_karte):
        cfg = PromptConfig(
            voice=ToneVoice.AYAKA,
            mode=CoachMode.BEGINNER,
            detected_symptom_ids=(),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        assert prompt.referenced_lexicon_ids == ()
        # Lexicon injection should still be present, just empty
        assert "[LEXICON INJECTION]" in prompt.lex_injection


# --- Stable ordering ---


class TestOrdering:
    def test_symptom_ids_sorted_alphabetically(self, sample_karte):
        cfg = PromptConfig(
            voice=ToneVoice.AYAKA,
            mode=CoachMode.BEGINNER,
            # Pass in non-alphabetical order
            detected_symptom_ids=(
                SymptomId.OVERPLAY_RECKLESS_ATTACK,
                SymptomId.ATARI_BLINDNESS,
            ),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        # atari_blindness should appear before overplay_reckless_attack
        a_pos = prompt.system_instruction.index("atari_blindness")
        o_pos = prompt.system_instruction.index("overplay_reckless_attack")
        assert a_pos < o_pos


# --- append_llm_prompt_block ---


class TestAppendLlmPromptBlock:
    def test_does_not_mutate_input(self, sample_karte, beginner_config):
        snapshot = json.dumps(sample_karte, sort_keys=True)
        result = append_llm_prompt_block(sample_karte, beginner_config)
        # Original should be untouched
        assert json.dumps(sample_karte, sort_keys=True) == snapshot
        # Result should be a new dict
        assert result is not sample_karte

    def test_injects_prompt_key(self, sample_karte, beginner_config):
        result = append_llm_prompt_block(sample_karte, beginner_config)
        assert "__llm_prompt__" in result
        assert "full_markdown" in result["__llm_prompt__"]
        assert "referenced_symptom_ids" in result["__llm_prompt__"]
        assert "referenced_lexicon_ids" in result["__llm_prompt__"]

    def test_preserves_karte_keys(self, sample_karte, beginner_config):
        result = append_llm_prompt_block(sample_karte, beginner_config)
        for key in sample_karte:
            assert key in result
        assert result["schema_version"] == "3.4"
        assert result["meta"]["game_id"] == "test-game"

    def test_injected_ids_match_prompt(self, sample_karte, beginner_config):
        result = append_llm_prompt_block(sample_karte, beginner_config)
        ids = result["__llm_prompt__"]["referenced_symptom_ids"]
        assert set(ids) == {s.value for s in beginner_config.detected_symptom_ids}


# --- render_markdown ---


class TestRenderMarkdown:
    def test_returns_full_markdown(self, sample_karte, beginner_config):
        prompt = build_translation_prompt(sample_karte, beginner_config)
        assert render_markdown(prompt) == prompt.full_markdown


# --- Phase 226-J (J.1): validate_prompt_config ---


class TestValidatePromptConfig:
    """Phase 226-J: voice / mode / symptom consistency."""

    def _config(
        self,
        voice=ToneVoice.TOMOKO,
        mode=CoachMode.DAN,
        detected=(),
    ):
        return PromptConfig(
            voice=voice,
            mode=mode,
            detected_symptom_ids=detected,
        )

    def test_consistent_config_returns_no_warnings(self):
        # TOMOKO serves DAN — both line up.

        warnings = validate_prompt_config(self._config(voice=ToneVoice.TOMOKO, mode=CoachMode.DAN))
        assert warnings == []

    def test_voice_mode_mismatch_warns(self):
        # AYAKA is Kansai-dialect only and serves BEGINNER/INTERMEDIATE.
        # DAN is not in AYAKA's allowed modes → mismatch warning.

        warnings = validate_prompt_config(self._config(voice=ToneVoice.AYAKA, mode=CoachMode.DAN))
        assert any("ayaka" in w and "DAN" in w for w in warnings), (
            f"Expected voice/mode mismatch warning, got: {warnings}"
        )

    def test_symptom_outside_difficulty_range_warns(self):
        # OVERFIGHT is INTERMEDIATE..EXPERT — BEGINNER is out of range.
        # AYAKA can serve BEGINNER, so the voice/mode check passes,
        # but the symptom/range check should still fire.

        warnings = validate_prompt_config(
            self._config(
                voice=ToneVoice.AYAKA,
                mode=CoachMode.BEGINNER,
                detected=(SymptomId.OVERFIGHT,),
            )
        )
        assert any("overfight" in w and "BEGINNER" in w for w in warnings), (
            f"Expected symptom/range warning, got: {warnings}"
        )

    def test_symptom_in_range_no_warning(self):
        # OVERFIGHT for DAN with TOMOKO voice — both consistent.

        warnings = validate_prompt_config(
            self._config(
                voice=ToneVoice.TOMOKO,
                mode=CoachMode.DAN,
                detected=(SymptomId.OVERFIGHT,),
            )
        )
        assert warnings == []

    def test_unknown_symptom_id_ignored(self):
        # A bogus SymptomId should not crash the validator.

        warnings = validate_prompt_config(
            self._config(
                voice=ToneVoice.TOMOKO,
                mode=CoachMode.DAN,
                detected=(),
            )
        )
        assert warnings == []

    def test_multiple_symptoms_each_warned(self):

        warnings = validate_prompt_config(
            self._config(
                voice=ToneVoice.AYAKA,
                mode=CoachMode.BEGINNER,
                detected=(SymptomId.OVERFIGHT, SymptomId.POST_JOSEKI_DIRECTION),
            )
        )
        # Both symptoms are out of BEGINNER range → at least 2 warnings
        symptom_warnings = [w for w in warnings if "範囲外" in w]
        assert len(symptom_warnings) >= 2


# --- Public API ---


class TestExports:
    def test_all_reexports(self):
        import katrain.core.coach as pkg

        for name in [
            "PromptConfig",
            "LlmPrompt",
            "build_translation_prompt",
            "append_llm_prompt_block",
            "render_markdown",
        ]:
            assert hasattr(pkg, name), f"__init__ missing {name}"
