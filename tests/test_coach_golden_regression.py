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

        Fox karte: critical_3 black=2, white=1; reason_tags black={heavy:1},
        white={heavy:1} (``unknown`` placeholders are dropped since 3.5)
        -> total 3 + 2 = 5.
        """
        karte = _load_karte("karte_sgf_fox.golden")
        assert extract_critical_move_count(karte) == 5


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

    def test_capture_oversight_fires_on_capture_race_loss(self):
        """2026-07: capture_race_loss tags must map to HintCategory.MISSED_CAPTURE
        so the CAPTURE_OVERSIGHT detector (tag + avg points > 1.0) fires.

        Real golden kartes don't carry capture_race_loss today, so we
        assemble a minimal karte with one capture_race_loss move to pin
        the wiring end-to-end.
        """
        karte = {
            "important_moves": [
                {
                    "move_number": 12,
                    "player": "black",
                    "primary_tag": MeaningTagId.CAPTURE_RACE_LOSS.value,
                    "mistake_type": "blunder",
                    "loss_clamped": 4.0,
                    "reason_codes": ["heavy"],
                }
            ],
            "summary": {"total_moves": 50},
            "mistake_streaks": {"black": [], "white": []},
        }
        ctx = build_symptom_context_from_karte(karte)
        # The remap is now in effect.
        assert HintCategory.MISSED_CAPTURE in ctx.hint_categories
        # And the detector fires.
        detected = detect_symptoms_from_karte(karte)
        assert SymptomId.CAPTURE_OVERSIGHT in detected

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


# --- Schema 3.5 sections against the real shape ---


class TestSchema35Sections:
    def test_meta_score_perspective(self):
        karte = _load_karte("karte_sgf_fox.golden")
        assert karte["meta"]["score_perspective"] == "black"

    def test_important_moves_coaching_fields(self):
        """Schema 3.5 coaching-context fields exist on every important move."""
        karte = _load_karte("karte_sgf_fox.golden")
        for mv in karte["important_moves"]:
            for key in ("winrate_lost", "score_before", "score_after", "score_stdev", "difficulty_score"):
                assert key in mv, f"missing coaching field: {key}"

    def test_important_moves_drop_game_ref(self):
        """Single-game karte omits game_name / game_id (they repeat meta)."""
        karte = _load_karte("karte_sgf_fox.golden")
        for mv in karte["important_moves"]:
            assert "game_name" not in mv
            assert "game_id" not in mv

    def test_critical_3_has_best_move(self):
        karte = _load_karte("karte_sgf_fox.golden")
        # Move 17 (R8): the mock analysis names T6 as the best move.
        assert karte["critical_3"]["black"][0]["best_move"] == "T6"

    def test_weaknesses_by_tag_structure(self):
        """Fox karte: black's territorial_loss bucket = 2 moves / 8.5 points."""
        karte = _load_karte("karte_sgf_fox.golden")
        by_tag = karte["weaknesses_by_tag"]
        assert set(by_tag.keys()) == {"black", "white"}
        black_top = by_tag["black"][0]
        assert black_top["tag"] == "territorial_loss"
        assert black_top["count"] == 2
        assert black_top["total_loss"] == pytest.approx(8.5)
        assert black_top["evidence"][0]["move_number"] == 17

    def test_score_trajectory_sampling(self):
        """Sampled every 10 moves plus the final move (92)."""
        karte = _load_karte("karte_sgf_fox.golden")
        traj = karte["score_trajectory"]
        sampled = [p["move"] for p in traj]
        assert sampled == [10, 20, 30, 40, 50, 60, 70, 80, 90, 92]
        for p in traj:
            assert isinstance(p["score"], (int, float))

    def test_opponent_correlation_is_null_on_single_game(self):
        karte = _load_karte("karte_sgf_fox.golden")
        assert karte["opponent_strength_loss_correlation"] is None

    def test_reason_codes_unknown_dropped(self):
        """The ``unknown`` placeholder never reaches any section."""
        karte = _load_karte("karte_sgf_fox.golden")
        for mv in karte["important_moves"]:
            assert "unknown" not in mv["reason_codes"]
        for color in ("black", "white"):
            assert "unknown" not in karte["reason_tags_distribution"][color]
            for c3 in karte["critical_3"][color]:
                assert "unknown" not in c3["reason_tags"]
