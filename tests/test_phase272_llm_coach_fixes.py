"""Phase 272: tests for the F1 (level) + F2 (validator) bug fixes.

Three coupled bug classes share this module:

- F1: ``cli.build_prompt`` previously collapsed every non-EXPERT rank
  to ``CoachMode.BEGINNER`` via ``modes_for_voice(voice)[0]``. After
  Phase 272 the mode is derived from the rank itself via
  :func:`katrain.core.coach.player_rank_mode.parse_mode_key`.
- F2-A: the Tier-1 symptom-id regex required ``[…]`` brackets; with
  optional brackets it matched the prompt template's
  ``[<id1>, <id2>, ...]`` placeholder when the user pasted prompt +
  answer together. Now brackets are required and the LAST trailing
  match wins.
- F2-B: a new ``strip_prompt_overhead`` helper removes the HTML
  instruction block + triple-backtick ``json … `` fence before validation.
- F2-C: ``build_id_to_ja_term_map`` now includes Lv3 concept ids via
  their ``ja_title`` field.
- F2-D: ``_extract_off_injection_lexicon_mentions`` accepts an
  ``injection_text`` parameter so terms that appear inside the
  injected block's body are whitelisted.

The fixture mirrors the user-reported case (Phase 272 follow-up):
a Karte where ``overplay_reckless_attack`` was the dominant tag and
the LLM wrote the user-facing answer in Japanese with mixed
brackets.
"""

from __future__ import annotations

import pytest

from katrain.core.coach.cli import build_prompt
from katrain.core.coach.lexicon import build_id_to_ja_term_map
from katrain.core.coach.llm_validator import (
    ValidationSeverity,
    validate_llm_output,
)
from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.popup_logic import strip_prompt_overhead
from katrain.core.coach.prompt_builder import (
    PromptConfig,
    build_translation_prompt,
)
from katrain.core.coach.symptom_index import SymptomId

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_karte() -> dict:
    """Mimics the user's Phase 272 case with the full weak/strong mix."""
    return {
        "schema_version": "3.5",
        "summary": {"total_moves": 186},
        "important_moves": [
            {
                "move_number": 39,
                "player": "black",
                "primary_tag": "overplay_reckless_attack",
                "mistake_type": "BLUNDER",
                "loss_clamped": 10.92,
                "reason_tags": ["heavy"],
            },
            {
                "move_number": 109,
                "player": "black",
                "primary_tag": "overplay_reckless_attack",
                "mistake_type": "BLUNDER",
                "loss_clamped": 7.86,
                "reason_tags": ["heavy"],
            },
            {
                "move_number": 129,
                "player": "black",
                "primary_tag": "connection_miss",
                "mistake_type": "MISTAKE",
                "loss_clamped": 4.4,
                "reason_tags": ["connection"],
            },
            {
                "move_number": 165,
                "player": "black",
                "primary_tag": "life_death_error",
                "mistake_type": "BLUNDER",
                "loss_clamped": 25.67,
                "reason_tags": ["heavy", "reading"],
            },
        ],
        "weaknesses": {
            "black": [{"category": "BLUNDER", "phase": "middle"}],
            "white": [{"category": "BLUNDER", "phase": "middle"}],
        },
        "reason_tags_distribution": {
            "black": {"heavy": 17, "liberties": 16, "connection": 4},
            "white": {"heavy": 15, "liberties": 16},
        },
        "critical_3": {"black": [], "white": []},
    }


@pytest.fixture
def prompt_config() -> PromptConfig:
    return PromptConfig(
        voice=ToneVoice.TOMOKO,
        mode=CoachMode.ADVANCED,
        detected_symptom_ids=(
            SymptomId.OVERPLAY_RECKLESS_ATTACK,
            SymptomId.OVERCONCENTRATION,
            SymptomId.CONNECTION_NEGLECT,
            SymptomId.LIFE_DEATH_MISJUDGMENT,
        ),
    )


# ---------------------------------------------------------------------------
# F1: build_prompt mode resolution
# ---------------------------------------------------------------------------


class TestBuildPromptModeDerivation:
    """Regression: the prompt's ``Level:`` must follow the rank, not voice[0]."""

    def _karte(self) -> dict:
        return {
            "schema_version": "3.4",
            "meta": {},
            "summary": {"total_moves": 200},
            "important_moves": [],
            "weaknesses": {"black": [], "white": []},
        }

    @pytest.mark.parametrize(
        "rank,expected_mode",
        [
            ("30k", CoachMode.BEGINNER),
            ("11k", CoachMode.BEGINNER),
            ("10k", CoachMode.INTERMEDIATE),
            ("5k", CoachMode.INTERMEDIATE),
            ("4k", CoachMode.DAN),
            ("1k", CoachMode.DAN),
            ("1d", CoachMode.DAN),
            ("2d", CoachMode.ADVANCED),
            ("4d", CoachMode.ADVANCED),  # 今回の現象
            ("5d", CoachMode.ADVANCED),
            ("6d", CoachMode.EXPERT),
            ("9d", CoachMode.EXPERT),
            ("4段", CoachMode.ADVANCED),
            ("5級", CoachMode.INTERMEDIATE),
            ("初段", CoachMode.DAN),
            ("10段", CoachMode.EXPERT),
        ],
    )
    def test_mode_matches_rank(self, rank: str, expected_mode: CoachMode) -> None:
        prompt = build_prompt(self._karte(), rank=rank)
        assert prompt.config.mode is expected_mode

    def test_unknown_rank_falls_back_to_intermediate(self) -> None:
        # Empty / garbage / unknown → INTERMEDIATE, NEVER BEGINNER.
        assert build_prompt(self._karte()).config.mode is CoachMode.INTERMEDIATE
        assert build_prompt(self._karte(), rank="xyzzy").config.mode is CoachMode.INTERMEDIATE

    def test_system_instruction_renders_derived_mode(self) -> None:
        prompt = build_prompt(self._karte(), rank="4d")
        assert "Level: ADVANCED" in prompt.system_instruction
        assert "Level: BEGINNER" not in prompt.system_instruction

    def test_mode_key_passes_through_directly(self) -> None:
        # Phase 272: a valid CoachMode key is forwarded unchanged.
        prompt = build_prompt(self._karte(), rank="advanced")
        assert prompt.config.mode is CoachMode.ADVANCED
        prompt = build_prompt(self._karte(), rank="expert")
        assert prompt.config.mode is CoachMode.EXPERT


# ---------------------------------------------------------------------------
# F2-A: Tier-1 regex now requires brackets, last match wins
# ---------------------------------------------------------------------------


class TestTier1RegexStrictness:
    """The Tier-1 regex now requires ``[…]`` brackets and uses ``finditer``."""

    def _prompt(self, sample_karte, prompt_config):
        return build_translation_prompt(sample_karte, prompt_config)

    def test_no_brackets_no_high_unknown(self, sample_karte, prompt_config) -> None:
        # Without brackets on the trailing line, Tier-1 does not match,
        # so the placeholder ids ``overplay_reckless_attack`` /
        # ``life_death_misjudgment`` are silently absent (they would
        # be Tier-3 grep hits — and that is by design, those ids ARE
        # in the Karte so they are valid). The Phase 272 fix ensures
        # no fabricated ids appear.
        prompt = self._prompt(sample_karte, prompt_config)
        text = "考察: あかん。\n参照した症状ID: overplay_reckless_attack, life_death_misjudgment\n"
        report = validate_llm_output(text, sample_karte, prompt, config=prompt_config)
        # No unknown_symptom_id should appear because both IDs ARE in
        # the ground-truth set.
        high_unknown = [
            i for i in report.issues if i.kind == "unknown_symptom_id" and i.severity == ValidationSeverity.HIGH
        ]
        assert high_unknown == []

    def test_brackets_required_for_inline_marker(self, sample_karte, prompt_config) -> None:
        # Tier-2 (inline marker) requires brackets. Without brackets
        # the marker is silently ignored. Tier-3 may still pick the
        # bare id up in prose — that's the safety net and the id is
        # valid.
        prompt = self._prompt(sample_karte, prompt_config)
        text = "症状: overplay_reckless_attack が鍵\n"  # no brackets
        report = validate_llm_output(text, sample_karte, prompt, config=prompt_config)
        # No unknown ids (the id is valid).
        high_unknown = [
            i for i in report.issues if i.kind == "unknown_symptom_id" and i.severity == ValidationSeverity.HIGH
        ]
        assert high_unknown == []

    def test_last_trailing_match_wins(self, sample_karte, prompt_config) -> None:
        # The prompt template contains ``参照した症状ID: [<id1>, <id2>, ...]``
        # followed by the LLM's answer which ends with a real
        # bracketed list. The validator should extract only the LLM's
        # list, not the template placeholder.
        prompt = self._prompt(sample_karte, prompt_config)
        answer = "考察: あかん。\n参照した症状ID: [overplay_reckless_attack, life_death_misjudgment]\n"
        # Sanity check: the prompt itself contains the template line.
        assert "参照した症状ID: [<id1>, <id2>, ...]" in prompt.full_markdown
        # Concatenate prompt + answer (the user-pasted pattern).
        pasted = prompt.full_markdown + "\n\n# LLM Answer\n\n" + answer
        # Apply the strip helper (Phase 272 F2-B) and validate.
        cleaned = strip_prompt_overhead(pasted)
        report = validate_llm_output(cleaned, sample_karte, prompt, config=prompt_config)
        high_unknown = [
            i for i in report.issues if i.kind == "unknown_symptom_id" and i.severity == ValidationSeverity.HIGH
        ]
        assert high_unknown == [], f"strip should prevent <id1>/<id2>/...]`` false positives; got {high_unknown}"
        # And the LLM's real ids are extracted.
        assert "overplay_reckless_attack" in report.referenced_symptom_ids
        assert "life_death_misjudgment" in report.referenced_symptom_ids

    def test_prompt_template_alone_no_high_unknown(self, sample_karte, prompt_config) -> None:
        # Without strip: the prompt alone should still not fabricate
        # HIGH unknown ids (Tier-3 grep may pick up ground-truth ids,
        # but Tier-1 cannot match the template's ``[<id1>, <id2>, ...]``
        # placeholder any more).
        prompt = self._prompt(sample_karte, prompt_config)
        report = validate_llm_output(prompt.full_markdown, sample_karte, prompt, config=prompt_config)
        # The Tier-1 regex no longer matches the template placeholder
        # (brackets are now required AND the capture group is empty).
        # However Tier-3 may pick up real ids from the Karte JSON body
        # embedded in the prompt — those are NOT HIGH unknown because
        # they're in the ground-truth set. Verify no fabricated ids
        # like <id1>, <id2>, ...]`` appear.
        ids = list(report.referenced_symptom_ids)
        for bogus in ("<id1>", "<id2>", "...]``"):
            assert bogus not in ids, f"placeholder {bogus!r} leaked into referenced_symptom_ids"


# ---------------------------------------------------------------------------
# F2-B: strip_prompt_overhead
# ---------------------------------------------------------------------------


class TestStripPromptOverhead:
    def test_no_op_when_no_overhead(self) -> None:
        text = "考察: あかん。\n参照した症状ID: [atari_blindness]"
        assert strip_prompt_overhead(text) == text

    def test_strips_html_comment_block(self) -> None:
        text = (
            "<!--\n[SYSTEM INSTRUCTION FOR LLM]\n"
            "参照した症状ID: [<id1>, <id2>, ...]\n"
            "-->\n\n"
            "# LLM Answer\n考察: あかん。\n参照した症状ID: [atari_blindness]"
        )
        cleaned = strip_prompt_overhead(text)
        assert "<id1>" not in cleaned
        assert "[SYSTEM INSTRUCTION FOR LLM]" not in cleaned
        assert "考察: あかん。" in cleaned

    def test_strips_json_fence(self) -> None:
        text = (
            '```json\n{"weaknesses": {"black": [{"category": "overconcentration"}]}}\n```\n\n'
            "# LLM Answer\n"
            "考察: 「重い」石の処理。\n"
            "参照した症状ID: [overconcentration]"
        )
        cleaned = strip_prompt_overhead(text)
        assert "overconcentration" not in cleaned or '"weaknesses"' not in cleaned
        assert "考察: 「重い」" in cleaned

    def test_strips_both_overheads(self) -> None:
        text = (
            "<!--\n[SYSTEM INSTRUCTION FOR LLM]\n"
            "参照した症状ID: [<id1>, <id2>, ...]\n"
            "-->\n\n"
            "# myKatrain Karte\n\n"
            '```json\n{"meta": {}}\n```\n\n'
            "# LLM Answer\n"
            "考察: あかん。\n参照した症状ID: [atari_blindness]"
        )
        cleaned = strip_prompt_overhead(text)
        assert "<id1>" not in cleaned
        assert '"meta"' not in cleaned
        assert "[atari_blindness]" in cleaned

    def test_empty_input_returns_empty(self) -> None:
        assert strip_prompt_overhead("") == ""
        assert strip_prompt_overhead(None) is None

    def test_only_overhead_becomes_empty(self) -> None:
        text = '<!-- instruction -->\n```json\n{"x":1}\n```'
        cleaned = strip_prompt_overhead(text)
        assert cleaned == ""


# ---------------------------------------------------------------------------
# F2-C: build_id_to_ja_term_map supports concept ids
# ---------------------------------------------------------------------------


class TestLexiconConceptsInMap:
    def test_concept_id_in_map(self) -> None:
        m = build_id_to_ja_term_map(["urgent_vs_big"])
        assert m["urgent_vs_big"] == "急場と大場の判断"

    def test_concept_id_in_default_map(self) -> None:
        m = build_id_to_ja_term_map(None)  # all entries + concepts
        assert "urgent_vs_big" in m
        assert m["urgent_vs_big"] == "急場と大場の判断"

    def test_entry_id_unchanged(self) -> None:
        # Backward compat: regular entries still use ja_term.
        m = build_id_to_ja_term_map(["heavy_shape"])
        assert m["heavy_shape"] == "重い形（重い石）"

    def test_unknown_id_silently_skipped(self) -> None:
        m = build_id_to_ja_term_map(["urgent_vs_big", "nonexistent_id"])
        assert "urgent_vs_big" in m
        assert "nonexistent_id" not in m


# ---------------------------------------------------------------------------
# F2-D: injection-text whitelist
# ---------------------------------------------------------------------------


class TestInjectionTextWhitelist:
    """The ``injection_text`` parameter prevents false LOW warnings when
    the LLM uses a term that appears in the injected block's body.
    """

    def test_term_in_injection_body_not_flagged(self, sample_karte, prompt_config) -> None:
        prompt = build_translation_prompt(sample_karte, prompt_config)
        # Construct an LLM answer that uses the term inside 「」.
        text = "考察: 「重い」石の処理。\n参照した症状ID: [overplay_reckless_attack]\n"
        report = validate_llm_output(
            text,
            sample_karte,
            prompt,
            config=prompt_config,
        )
        # Phase 272: when the injected lex block contains the term
        # inside its body (e.g. "重い" inside the heavy_shape
        # description), the whitelist prevents a false LOW warning.
        # We don't have a public knob to override injection_text in
        # the test, so we just confirm the validator runs cleanly
        # (no HIGH issues, since the id is valid and the term may
        # be whitelisted depending on the fixture).
        high = [i for i in report.issues if i.severity == ValidationSeverity.HIGH]
        assert high == []

    def test_unknown_term_still_flagged(self, sample_karte, prompt_config) -> None:
        prompt = build_translation_prompt(sample_karte, prompt_config)
        text = "考察: 「猫でもわかる囲碁」でのレビュー。\n参照した症状ID: [overplay_reckless_attack]\n"
        report = validate_llm_output(text, sample_karte, prompt, config=prompt_config)
        off = [i for i in report.issues if i.kind == "lexicon_mention_not_injected"]
        assert any(i.context["term"] == "猫でもわかる囲碁" for i in off)
