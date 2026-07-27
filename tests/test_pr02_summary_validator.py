"""PR-02 regression tests for summary-side validator hardening.

PR-02 (S1): ``_extract_pattern_categories`` / ``_extract_referenced_phases``
in ``summary_validator`` previously used ``.search()`` (first match),
so a user pasting the prompt + LLM answer together got the prompt's
template row (``<category1>``, ``<category2>``) validated instead of
the LLM's actual answer. The fix mirrors the karte-side Phase 272
strategy: ``finditer`` + take the LAST match, plus tighter regexes
that exclude angle-bracket placeholders.

PR-02 (S4): ``_POINTS_LOST_RE`` in ``llm_validator`` previously
matched bare ``N目`` (e.g. ``15目リード``, ``コミ 6.5 目``, ``3目得``)
as a pointsLost reference. The fix requires a loss-flavoured
context word or anchor label.

PR-02 (S6): both validators emit a LOW ``missing_contract_line``
warning when the LLM response omits the contract rows AND does not
mention any ids in prose form.
"""

from __future__ import annotations

from typing import Any

from katrain.core.coach.llm_validator import ValidationSeverity, validate_llm_output
from katrain.core.coach.summary_validator import (
    _extract_pattern_categories,
    _extract_referenced_phases,
    validate_summary_llm_output,
)

# A minimal Summary JSON shape that the summary validator accepts.
# ``available_categories`` is what ``_summary_available_categories``
# extracts; we only need a token shape that exposes one valid
# category so the validator's reference checks can run.
SUMMARY_JSON: dict[str, Any] = {
    "meta": {"schema_version": "3.5"},
    "weaknesses": [
        {"phase": "middle", "category": "mistake", "count": 2, "total_loss": 4.0},
        {"phase": "endgame", "category": "endgame_slip", "count": 1, "total_loss": 2.0},
    ],
    "games": [{"game_id": "g1"}],
}


class TestSummaryExtractPatternLastMatch:
    def test_picks_last_match_over_template(self) -> None:
        """S1: when prompt + answer are pasted together, the answer's
        contract line wins over the template's placeholder row."""
        prompt_template = (
            "## 最終出力形式\n"
            "```\n"
            "抽出した弱点パターン: [<category1>, <category2>, ...]\n"
            "参照したphase: [opening, middle, ...]\n"
            "```\n"
        )
        answer = "...実際のLLM回答...\n抽出した弱点パターン: [mistake]\n参照したphase: [middle]\n"
        text = prompt_template + answer
        assert _extract_pattern_categories(text) == ("mistake",), (
            "_extract_pattern_categories must prefer the LLM answer's "
            "contract line over the prompt's template placeholders."
        )
        assert _extract_referenced_phases(text) == ("middle",)

    def test_template_alone_returns_empty(self) -> None:
        """S1 (defensive): even if only the template is present, the
        angle-bracket exclusion means we get an empty tuple rather
        than ``('<category1>', '<category2>')``."""
        prompt_template = "抽出した弱点パターン: [<category1>, <category2>, ...]\n"
        assert _extract_pattern_categories(prompt_template) == ()

    def test_solo_answer_unchanged(self) -> None:
        """S1 backwards compat: a bare contract line is still parsed."""
        assert _extract_pattern_categories("抽出した弱点パターン: [atari_blindness, endgame_slip]") == (
            "atari_blindness",
            "endgame_slip",
        )


class TestSummaryMissingContractWarning:
    def test_no_contract_lines_emits_low_warning(self) -> None:
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPrompt,
            SummaryPromptConfig,
        )

        prompt = SummaryPrompt(
            system_instruction="<!-- empty -->",
            body_markdown="{summary}",
            full_markdown="{summary}",
            config=SummaryPromptConfig(
                voice=ToneVoice.TOMOKO,
                mode=CoachMode.INTERMEDIATE,
                games_analyzed=1,
            ),
        )
        report = validate_summary_llm_output(
            llm_text="これは契約行を含まない散文だけのテキストです。",
            summary_json=SUMMARY_JSON,
            prompt=prompt,
        )
        severities = [(i.severity, i.kind) for i in report.issues]
        assert (ValidationSeverity.LOW, "missing_contract_line") in severities, (
            "Summary validator must emit LOW/missing_contract_line when neither contract row is present."
        )

    def test_contract_line_present_skips_warning(self) -> None:
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.summary_prompt_builder import (
            SummaryPrompt,
            SummaryPromptConfig,
        )

        prompt = SummaryPrompt(
            system_instruction="<!-- empty -->",
            body_markdown="{summary}",
            full_markdown="{summary}",
            config=SummaryPromptConfig(
                voice=ToneVoice.TOMOKO,
                mode=CoachMode.INTERMEDIATE,
                games_analyzed=1,
            ),
        )
        report = validate_summary_llm_output(
            llm_text=("弱点: ...\n抽出した弱点パターン: [mistake]\n"),
            summary_json=SUMMARY_JSON,
            prompt=prompt,
        )
        kinds = [i.kind for i in report.issues]
        assert "missing_contract_line" not in kinds


class TestKarteMissingContractWarning:
    def test_no_symptom_id_emits_low_warning(self) -> None:
        """S6: karte validator must warn when the contract line AND
        prose-level symptom id mentions are both absent."""
        karte_json: dict[str, Any] = {
            "meta": {"schema_version": "3.5"},
            "weaknesses": {"black": [], "white": []},
            "important_moves": [],
        }
        # Minimal valid LlmPrompt — see prompt_builder for fields.
        # The simplest way to exercise the validator is via the
        # contract helper: feed it text with no contract and no ids.
        from katrain.core.coach.master_db import CoachMode, ToneVoice
        from katrain.core.coach.prompt_builder import LlmPrompt, PromptConfig

        prompt = LlmPrompt(
            system_instruction="<!-- empty -->",
            lex_injection="<!-- empty -->",
            body_markdown="{karte}",
            full_markdown="{karte}",
            config=PromptConfig(
                voice=ToneVoice.TOMOKO,
                mode=CoachMode.INTERMEDIATE,
                detected_symptom_ids=(),
                llm_required_symptom_ids=(),
                player_color=None,
            ),
            referenced_symptom_ids=(),
            referenced_lexicon_ids=(),
        )
        report = validate_llm_output(
            llm_text="契約なしの散文テキスト。症状 ID の言及なし。",
            karte_json=karte_json,
            prompt=prompt,
            config=None,
        )
        kinds = [i.kind for i in report.issues]
        assert "missing_contract_line" in kinds, (
            "Karte validator must emit LOW/missing_contract_line when the contract row is absent."
        )


class TestPointsLostFalsePositives:
    def test_bare_lead_in_me_is_not_a_loss(self) -> None:
        """S4: 'N目リード' is a score lead, not a loss — must not match."""
        from katrain.core.coach.llm_validator import _POINTS_LOST_RE

        text = "終盤のリードは15目です。"
        assert _POINTS_LOST_RE.search(text) is None, (
            "'15目リード' must NOT match pointsLost — it is a score lead, not a loss value."
        )

    def test_bare_komi_in_me_is_not_a_loss(self) -> None:
        text = "コミ6.5目を考慮すると、白が有利です。"
        from katrain.core.coach.llm_validator import _POINTS_LOST_RE

        assert _POINTS_LOST_RE.search(text) is None, "'コミ 6.5目' is a komi value, not a loss."

    def test_bare_gain_in_me_is_not_a_loss(self) -> None:
        text = "この手で3目得しました。"
        from katrain.core.coach.llm_validator import _POINTS_LOST_RE

        assert _POINTS_LOST_RE.search(text) is None, "'3目得' is a gain, not a loss."

    def test_explicit_loss_word_is_still_a_loss(self) -> None:
        """S4: explicit loss wording must continue to match."""
        from katrain.core.coach.llm_validator import _POINTS_LOST_RE

        # 損失の直後に目
        assert _POINTS_LOST_RE.search("損失 3.5目") is not None
        # ラベル先行
        assert _POINTS_LOST_RE.search("ロス：4.2") is not None
        # 英語ラベル
        assert _POINTS_LOST_RE.search("3.0 points lost") is not None
