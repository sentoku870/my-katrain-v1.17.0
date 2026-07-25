"""Regression tests: the coach layer must read the REAL Karte JSON shape.

Background (2026-07 schema-alignment fix): the coach extractors /
symptom-context builders / validators used to read field names that
never existed in real Karte output (``points_lost``, ``winrate_lost``,
``meaning_tag_id``, ``mistake_category``, ``critical_3[color]["moves"]``
...). As a result, symptom detection and parts of LLM-output validation
silently never fired on real kartes, while tests kept passing because
fixtures were written in that fictional shape.

These tests run the detection / validation chain against the REAL golden
kartes (tests/fixtures/golden/karte_sgf_*.golden) to prevent recurrence.
"""

from __future__ import annotations

import json

import pytest

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.beginner.models import HintCategory
from katrain.core.coach.karte_detector import detect_symptoms_from_karte
from katrain.core.coach.karte_extractors import (
    extract_avg_points_lost,
    extract_critical_move_count,
)
from katrain.core.coach.karte_symptom_context import build_symptom_context_from_karte
from katrain.core.coach.llm_validator import (
    ValidationSeverity,
    _karte_max_points_lost,
    validate_llm_output,
)
from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.prompt_builder import PromptConfig, build_translation_prompt
from katrain.core.coach.symptom_index import SymptomId
from tests.conftest import load_golden

GOLDEN_KARTES = [
    "karte_sgf_fox.golden",
    "karte_sgf_alphago.golden",
    "karte_sgf_panda.golden",
]


def _load_karte(name: str) -> dict:
    return json.loads(load_golden(name))


def _config() -> PromptConfig:
    return PromptConfig(
        voice=ToneVoice.TOMOKO,
        mode=CoachMode.INTERMEDIATE,
        detected_symptom_ids=(),
    )


# --- Extractors against the real shape ---


class TestExtractorsOnRealKarte:
    def test_avg_points_lost_reads_loss_clamped(self):
        """Fox karte: loss_clamped = 2.5 / 6.0 / 12.0 -> avg = 20.5/3."""
        karte = _load_karte("karte_sgf_fox.golden")
        avg = extract_avg_points_lost(karte)
        assert avg is not None
        assert avg == pytest.approx(20.5 / 3, abs=1e-6)

    @pytest.mark.parametrize("golden", GOLDEN_KARTES)
    def test_avg_points_lost_not_none_on_all_goldens(self, golden):
        karte = _load_karte(golden)
        assert extract_avg_points_lost(karte) is not None

    def test_critical_move_count_handles_list_shape(self):
        """critical_3[color] is a plain list; reason_tags are flat counts.

        Fox karte: critical_3 black=2, white=1; reason_tags black={unknown:1,
        heavy:1}, white={heavy:1} -> total 3 + 3 = 6.
        """
        karte = _load_karte("karte_sgf_fox.golden")
        assert extract_critical_move_count(karte) == 6


# --- Symptom context / detection against the real shape ---


class TestSymptomDetectionOnRealKarte:
    def test_meaning_tags_collected_from_primary_tag(self):
        karte = _load_karte("karte_sgf_fox.golden")
        ctx = build_symptom_context_from_karte(karte)
        assert MeaningTagId.TERRITORIAL_LOSS in ctx.meaning_tag_ids

    def test_hint_categories_collected_from_mistake_type(self):
        karte = _load_karte("karte_sgf_fox.golden")
        ctx = build_symptom_context_from_karte(karte)
        # Fox karte has mistake_type "mistake" and "blunder" entries.
        assert HintCategory.MISTAKE_BLUNDER in ctx.hint_categories
        assert HintCategory.MISTAKE_MISTAKE in ctx.hint_categories

    @pytest.mark.parametrize("golden", GOLDEN_KARTES)
    def test_meaning_tags_not_empty_on_all_goldens(self, golden):
        ctx = build_symptom_context_from_karte(_load_karte(golden))
        assert len(ctx.meaning_tag_ids) > 0

    def test_detection_fires_on_real_karte(self):
        """Fox karte: avg loss ~6.83 in an opening-dominant context must
        fire FIRST_MOVE_CONFUSION (opening + avg points lost > 5.0)."""
        karte = _load_karte("karte_sgf_fox.golden")
        detected = detect_symptoms_from_karte(karte)
        assert SymptomId.FIRST_MOVE_CONFUSION in detected

    @pytest.mark.parametrize("golden", GOLDEN_KARTES)
    def test_detection_returns_valid_symptom_ids(self, golden):
        detected = detect_symptoms_from_karte(_load_karte(golden))
        assert isinstance(detected, tuple)
        for sid in detected:
            assert isinstance(sid, SymptomId)


# --- Validator against the real shape ---


class TestValidatorOnRealKarte:
    def test_max_points_lost_reads_loss_clamped(self):
        karte = _load_karte("karte_sgf_fox.golden")
        assert _karte_max_points_lost(karte) == pytest.approx(12.0)

    def test_points_lost_outlier_fires_on_real_karte(self):
        """Fox karte ceiling = 12.0 * 1.5 + 0.05 = 18.05; citing 25.0目
        must trigger points_lost_outlier (this check was dead before the
        2026-07 fix because ``points_lost`` does not exist in real kartes).
        """
        karte = _load_karte("karte_sgf_fox.golden")
        config = _config()
        prompt = build_translation_prompt(karte, config)
        text = "第34手で25.0目の損失が出ました。\n参照した症状ID: [territorial_loss]\n"
        report = validate_llm_output(text, karte, prompt, config=config)
        kinds = [i.kind for i in report.issues]
        assert "points_lost_outlier" in kinds

    def test_real_tag_reference_accepted(self):
        """Referencing a tag present in the real karte must not be flagged."""
        karte = _load_karte("karte_sgf_fox.golden")
        config = _config()
        prompt = build_translation_prompt(karte, config)
        text = "地の損失が主題です。\n参照した症状ID: [territorial_loss]\n"
        report = validate_llm_output(text, karte, prompt, config=config)
        unknown = [i for i in report.issues if i.kind == "unknown_symptom_id" and i.severity == ValidationSeverity.HIGH]
        assert unknown == []
