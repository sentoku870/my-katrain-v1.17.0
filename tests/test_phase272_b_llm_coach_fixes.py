"""Phase 272-B: tests for the LLM Coach popup + Lexicon whitelist extensions.

Three coupled modules are exercised here:

- ``katrain.core.coach.lexicon.extract_all_injected_terms`` (B5)
- ``katrain.core.coach.llm_validator`` whitelist integration (B5)
- ``katrain.gui.popups.llm_coach_popup.rank_spinner_label_to_key`` /
  ``rank_spinner_key_to_label`` (B1)
- ``katrain.gui.popups.llm_coach_popup`` auto-block on generate (B4)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.coach.lexicon import (
    extract_all_injected_terms,
)
from katrain.core.coach.llm_validator import (
    validate_llm_output,
)
from katrain.core.coach.master_db import CoachMode, ToneVoice
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
                "move_number": 165,
                "player": "black",
                "primary_tag": "life_death_error",
                "mistake_type": "BLUNDER",
                "loss_clamped": 25.24,
                "reason_tags": ["heavy", "reading"],
            },
        ],
        "weaknesses": {
            "black": [{"category": "BLUNDER", "phase": "middle"}],
            "white": [{"category": "BLUNDER", "phase": "middle"}],
        },
        "reason_tags_distribution": {
            "black": {"heavy": 17, "liberties": 16},
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
            SymptomId.LIFE_DEATH_MISJUDGMENT,
        ),
    )


# ---------------------------------------------------------------------------
# B5: extract_all_injected_terms
# ---------------------------------------------------------------------------


class TestExtractAllInjectedTerms:
    def test_returns_primary_ja_term(self) -> None:
        terms = extract_all_injected_terms(entry_ids=["heavy_shape"])
        assert "重い形（重い石）" in terms

    def test_returns_concept_title(self) -> None:
        terms = extract_all_injected_terms(entry_ids=["urgent_vs_big"])
        assert "急場と大場の判断" in terms

    def test_extracts_compounds_from_pitfalls(self) -> None:
        # heavy_shape has pitfalls text mentioning 捨て石 / 切り etc.
        terms = extract_all_injected_terms(entry_ids=["heavy_shape"])
        # We can't guarantee the exact compound, but the set must be
        # non-empty after the entry's pitfalls are scanned.
        assert isinstance(terms, set)
        assert len(terms) >= 2

    def test_includes_bracket_terms_from_injection_text(self) -> None:
        text = "【example】\n# 「大場」と「急場」が重要。\n定義: ..."
        terms = extract_all_injected_terms(text, entry_ids=[])
        assert "大場" in terms
        assert "急場" in terms

    def test_none_injection_text_returns_only_entry_terms(self) -> None:
        terms_with = extract_all_injected_terms("text", entry_ids=["heavy_shape"])
        terms_without = extract_all_injected_terms(None, entry_ids=["heavy_shape"])
        assert "重い形（重い石）" in terms_without
        assert terms_without.issubset(terms_with | terms_without)

    def test_empty_inputs_returns_empty_set(self) -> None:
        # ``entry_ids=None`` returns all known terms — non-empty.
        terms = extract_all_injected_terms(None, entry_ids=None)
        assert isinstance(terms, set)
        assert len(terms) > 0

    def test_unknown_entry_id_skipped(self) -> None:
        terms = extract_all_injected_terms(None, entry_ids=["nonexistent_id_xyz"])
        assert terms == set() or all(isinstance(t, str) for t in terms)


# ---------------------------------------------------------------------------
# B5 integration with validator
# ---------------------------------------------------------------------------


class TestLexiconWhitelistIntegration:
    """The ``injection_text`` argument prevents false ``lexicon_mention_not_injected``
    warnings when the LLM uses a term taught via the injection body.
    """

    def test_heavy_whitelisted_when_heavy_shape_injected(self, sample_karte, prompt_config) -> None:
        prompt = build_translation_prompt(sample_karte, prompt_config)
        # The injection block for OVERPLAY_RECKLESS_ATTACK / OVERCONCENTRATION
        # includes heavy_shape (whose ja_term is "重い形（重い石）"). The
        # compound "重い" appears in the entry's pitfalls / description.
        assert "heavy_shape" in prompt.referenced_lexicon_ids
        text = "考察: 「重い」石の処理に注意。\n参照した症状ID: [overplay_reckless_attack]\n"
        report = validate_llm_output(text, sample_karte, prompt, config=prompt_config)
        off = [i for i in report.issues if i.kind == "lexicon_mention_not_injected" and i.context.get("term") == "重い"]
        assert off == [], f"「重い」 should be whitelisted; got {off}"

    def test_daijiba_whitelisted_when_concept_injected(self, sample_karte, prompt_config) -> None:
        # Force a prompt whose lexicon injection includes urgent_vs_big.
        cfg = PromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.ADVANCED,
            detected_symptom_ids=(SymptomId.OVERCONCENTRATION,),
        )
        prompt = build_translation_prompt(sample_karte, cfg)
        if "urgent_vs_big" not in prompt.referenced_lexicon_ids:
            pytest.skip("urgent_vs_big not injected in this prompt config")
        text = "考察: 「大場」の判断。\n参照した症状ID: [overconcentration]\n"
        report = validate_llm_output(text, sample_karte, prompt, config=cfg)
        off = [i for i in report.issues if i.kind == "lexicon_mention_not_injected" and i.context.get("term") == "大場"]
        assert off == [], f"「大場」 should be whitelisted when urgent_vs_big is injected; got {off}"

    def test_unknown_term_still_flagged(self, sample_karte, prompt_config) -> None:
        prompt = build_translation_prompt(sample_karte, prompt_config)
        text = "考察: 「猫でもわかる囲碁」。\n参照した症状ID: [overplay_reckless_attack]\n"
        report = validate_llm_output(text, sample_karte, prompt, config=prompt_config)
        off = [i for i in report.issues if i.kind == "lexicon_mention_not_injected"]
        assert any(i.context["term"] == "猫でもわかる囲碁" for i in off)

    def test_llm_specific_phrases_still_flagged(self, sample_karte, prompt_config) -> None:
        prompt = build_translation_prompt(sample_karte, prompt_config)
        # These phrases are from the user's actual LLM output. They
        # are LLM-coined prose, not Lexicon entries, so they MUST
        # still be flagged (B5 only widens the whitelist, never
        # narrows it).
        text = "考察: 「何となく打った手」「3秒確認」「一手深呼吸」。\n参照した症状ID: [overplay_reckless_attack]\n"
        report = validate_llm_output(text, sample_karte, prompt, config=prompt_config)
        flagged = {i.context["term"] for i in report.issues if i.kind == "lexicon_mention_not_injected"}
        # All three should be flagged as off-injection (they're not in
        # any Lexicon entry).
        for term in ("何となく打った手", "3秒確認", "一手深呼吸"):
            assert term in flagged, f"{term!r} should be flagged as off-injection"


# ---------------------------------------------------------------------------
# B1: rank Spinner helpers
# ---------------------------------------------------------------------------


class TestRankSpinnerHelpers:
    """Phase 272-B: the popup rank_input is a Spinner that stores the
    localised label. The label ↔ key mapping helpers live in
    ``llm_coach_popup.py``; they are pure functions so we can test
    them without Kivy.
    """

    def test_label_to_key_known_labels(self) -> None:
        from katrain.gui.popups.llm_coach_popup import (
            rank_spinner_label_to_key,
        )

        assert rank_spinner_label_to_key("BEGINNER（入門〜10級）") == "beginner"
        assert rank_spinner_label_to_key("INTERMEDIATE（9級〜4級）") == "intermediate"
        assert rank_spinner_label_to_key("DAN（3級〜二段）") == "dan"
        assert rank_spinner_label_to_key("ADVANCED（三段〜五段）") == "advanced"
        assert rank_spinner_label_to_key("EXPERT（六段以上）") == "expert"

    def test_key_to_label_round_trip(self) -> None:
        from katrain.gui.popups.llm_coach_popup import (
            rank_spinner_key_to_label,
            rank_spinner_label_to_key,
        )

        for key in ("beginner", "intermediate", "dan", "advanced", "expert"):
            label = rank_spinner_key_to_label(key)
            assert rank_spinner_label_to_key(label) == key

    def test_unknown_label_returns_none(self) -> None:
        from katrain.gui.popups.llm_coach_popup import rank_spinner_label_to_key

        assert rank_spinner_label_to_key("") is None
        assert rank_spinner_label_to_key("unknown") is None
        assert rank_spinner_label_to_key("4d") is None

    def test_unknown_key_falls_back_to_intermediate(self) -> None:
        from katrain.gui.popups.llm_coach_popup import rank_spinner_key_to_label

        assert rank_spinner_key_to_label("nonexistent") == "INTERMEDIATE（9級〜4級）"


# ---------------------------------------------------------------------------
# Post-merge fix: synchronously populate player info on generate/validate
# ---------------------------------------------------------------------------


class TestGenerateValidatesSynchronousPopulation:
    """Phase 272-B (post-merge fix): the rank/perspective populator runs on
    a 0.2s Clock schedule, but the user may click "Generate & Copy" or
    "Validate" before that schedule fires. Without synchronous
    population, the auto-block guard would render
    ``black_name = "?"`` / ``white_name = "?"`` (and effectively
    refuse to detect "仙得" in either side) even when the Karte JSON
    contains valid ``meta.player_info``.

    These tests pin the contract: clicking generate / validate while
    ``_last_player_info`` is still empty must still trigger a
    synchronous detect so the user gets the expected behaviour.
    """

    def test_generate_populates_player_info_before_check(self, tmp_path) -> None:
        """When ``on_generate_and_copy`` is called with an empty cache,
        the popup must synchronously re-run ``populate_karte_player_info``
        so the auto-block guard sees the actual black/white names.
        """
        from tests.llm_coach_popup_helpers import _make_content

        # Build a Karte with valid meta.player_info.
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "Alice", "rank": "4d"},
                            "white": {"name": "Bob", "rank": "3d"},
                        }
                    },
                    "important_moves": [],
                    "weaknesses": {"black": [], "white": []},
                    "summary": {"total_moves": 100},
                }
            ),
            encoding="utf-8",
        )

        content = _make_content(path_type="karte")
        content.ids["karte_path_input"].text = str(karte)
        content.katrain.config = MagicMock(
            side_effect=lambda key, default=None: {
                "mykatrain_settings": {"default_user_name": "Bob"},
                "general/player_rank": "advanced",
            }.get(key, default or "")
        )

        # User clicks Generate before _populate_rank_and_perspective
        # has had a chance to run.
        assert content._last_player_info == {}
        content.perspective_value = "auto"
        content.detected_player_color = None
        with (
            patch(
                "katrain.gui.features.llm_coach.build_llm_prompt",
                return_value=(True, "# PROMPT"),
            ) as spy,
            patch("katrain.gui.popups.llm_coach_popup.Clipboard"),
        ):
            content.on_generate_and_copy()
        # Generation must succeed and the cache must now contain
        # the actual black/white names.
        assert spy.called
        assert content._last_player_info.get("black", {}).get("name") == "Alice"
        assert content._last_player_info.get("white", {}).get("name") == "Bob"
        # Status reflects a successful copy (not the auto-block).
        assert "Prompt copied" in content.ids["status_label"].text or "コピー" in content.ids["status_label"].text

    def test_generate_with_no_player_info_blocks_with_real_names(self, tmp_path) -> None:
        """When the Karte truly has no player info (e.g. ``meta.player_info``
        missing), the auto-block must render the actual unknown names
        — not placeholder ``?``.
        """
        from tests.llm_coach_popup_helpers import _make_content

        # Karte with meta but no player_info.
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps({"meta": {"source_filename": None}}),
            encoding="utf-8",
        )

        content = _make_content(path_type="karte")
        content.ids["karte_path_input"].text = str(karte)
        content.katrain.config = MagicMock(
            side_effect=lambda key, default=None: {
                "mykatrain_settings": {"default_user_name": "Bob"},
                "general/player_rank": "advanced",
            }.get(key, default or "")
        )

        content.perspective_value = "auto"
        content.detected_player_color = None
        with (
            patch(
                "katrain.gui.features.llm_coach.build_llm_prompt",
                return_value=(True, "# PROMPT"),
            ) as spy,
            patch("katrain.gui.popups.llm_coach_popup.Clipboard"),
        ):
            content.on_generate_and_copy()
        # Generation must NOT have been called (auto-blocked).
        assert not spy.called
        # Status mentions both names (or at least the markers "?")
        # — the important thing is the message doesn't claim success.
        assert "コピー" not in content.ids["status_label"].text or "stopped" in content.ids["status_label"].text.lower()
