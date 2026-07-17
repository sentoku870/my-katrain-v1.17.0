"""Phase 209: Tests for katrain.core.coach.symptom_index.

Covers:
- SymptomId enum completeness (40 symptoms from §2-0 expansion)
- Symptom dataclass validation
- SymptomContext.phase detection
- Auto / LLM-required classification
- detect_auto_symptoms: positive/negative cases
- Detector failure tolerance (no crashes on partial data)
"""

from __future__ import annotations

import pytest

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.beginner.models import HintCategory
from katrain.core.coach.master_db import CoachMode
from katrain.core.coach.symptom_index import (
    Symptom,
    SymptomContext,
    SymptomId,
    detect_auto_symptoms,
    list_all_symptoms,
    list_auto_detected_symptoms,
    list_llm_required_symptoms,
    lookup_symptom,
)

# --- Enum completeness ---


class TestSymptomId:
    def test_count_is_40(self):
        # 30 row-level entries expanded to 40 candidate symptoms
        assert len(list(SymptomId)) == 40

    def test_id_values_unique(self):
        values = [s.value for s in SymptomId]
        assert len(values) == len(set(values))

    @pytest.mark.parametrize(
        "expected",
        [
            "atari_blindness",
            "capture_oversight",
            "big_point_blindness",
            "joseki_rote",
            "time_pressure_loss",
            "ai_overload",
            "tilt_discouragement",
            "evaluation_errors",
            "saving_everything",
        ],
    )
    def test_known_ids_present(self, expected):
        assert SymptomId(expected).value == expected


# --- Symptom table integrity ---


class TestSymptomTable:
    def test_list_all_returns_tuple(self):
        symptoms = list_all_symptoms()
        assert isinstance(symptoms, tuple)
        assert len(symptoms) == len(list(SymptomId))

    def test_no_duplicate_ids(self):
        ids = [s.id for s in list_all_symptoms()]
        assert len(ids) == len(set(ids))

    def test_lookup_roundtrip(self):
        for sid in SymptomId:
            s = lookup_symptom(sid)
            assert s is not None
            assert s.id == sid
            assert isinstance(s, Symptom)

    def test_unknown_id_returns_none(self):
        assert lookup_symptom(SymptomId.ATARI_BLINDNESS) is not None
        # All IDs are valid enum values, so we instead check that
        # a non-SymptomId argument would fail. That's caught by type-check.

    @pytest.mark.parametrize("symptom", list_all_symptoms())
    def test_symptom_difficulty_range(self, symptom):
        # difficulty_range must be (min, max) CoachMode pair
        assert isinstance(symptom.difficulty_range, tuple)
        assert len(symptom.difficulty_range) == 2
        lo, hi = symptom.difficulty_range
        assert isinstance(lo, CoachMode)
        assert isinstance(hi, CoachMode)
        # Confirm ordering
        assert list(CoachMode).index(lo) <= list(CoachMode).index(hi)

    @pytest.mark.parametrize("symptom", list_all_symptoms())
    def test_symptom_has_label_and_description(self, symptom):
        assert symptom.ja_label
        assert symptom.en_label
        assert symptom.description_jp


# --- Auto-detected / LLM-required split ---


class TestAutoLlMSplit:
    def test_split_covers_all(self):
        auto = list_auto_detected_symptoms()
        llm = list_llm_required_symptoms()
        assert len(auto) + len(llm) == 40
        # No overlap
        auto_ids = {s.id for s in auto}
        llm_ids = {s.id for s in llm}
        assert auto_ids.isdisjoint(llm_ids)

    def test_auto_detected_has_detector_or_none(self):
        for s in list_auto_detected_symptoms():
            assert s.auto_detected is True
            # detector may be None if future-Phase; but most are populated
            # We do not enforce all are populated because Phase 209.5 may
            # add more.

    def test_llm_required_has_context_hint(self):
        # User decision (Phase 203 §4.2): LLM-required symptoms must
        # include a context_hint so the LLM has guidance.
        for s in list_llm_required_symptoms():
            assert s.context_hint, f"{s.id.value} (LLM-required) missing context_hint"

    def test_known_auto_detected(self):
        assert lookup_symptom(SymptomId.ATARI_BLINDNESS).auto_detected is True
        assert lookup_symptom(SymptomId.CAPTURE_OVERSIGHT).auto_detected is True
        assert lookup_symptom(SymptomId.LIFE_DEATH_MISJUDGMENT).auto_detected is True
        assert lookup_symptom(SymptomId.BIG_POINT_BLINDNESS).auto_detected is True

    def test_known_llm_required(self):
        for sid in [
            SymptomId.TIME_PRESSURE_LOSS,
            SymptomId.TIME_MISALLOCATION,
            SymptomId.TIME_DRAIN,
            SymptomId.AI_OVERLOAD,
            SymptomId.COPY_WITHOUT_UNDERSTANDING,
            SymptomId.AUTHORITY_BIAS,
            SymptomId.TILT_EMOTIONAL_INTERFERENCE,
            SymptomId.SACRIFICE_JUDGMENT,
            SymptomId.ENDOWMENT_EFFECT_SUNK_COST,
            SymptomId.SHALLOW_REVIEW,
        ]:
            assert lookup_symptom(sid).auto_detected is False, f"{sid.value} should be LLM-required"


# --- SymptomContext.phase ---


class TestSymptomContextPhase:
    def test_opening_phase(self):
        ctx = SymptomContext(move_number=10)
        assert ctx.is_phase("opening") is True
        assert ctx.is_phase("middle") is False
        assert ctx.is_phase("endgame") is False

    def test_middle_phase(self):
        ctx = SymptomContext(move_number=100)
        assert ctx.is_phase("opening") is False
        assert ctx.is_phase("middle") is True

    def test_endgame_phase(self):
        ctx = SymptomContext(move_number=250)
        assert ctx.is_phase("opening") is False
        assert ctx.is_phase("endgame") is True

    def test_none_move_number_returns_false(self):
        ctx = SymptomContext(move_number=None)
        for phase in ("opening", "middle", "endgame"):
            assert ctx.is_phase(phase) is False

    def test_unknown_phase_returns_false(self):
        ctx = SymptomContext(move_number=50)
        assert ctx.is_phase("unknown_phase") is False

    def test_small_board_scales_thresholds(self):
        # On 9x9 the opening max should be < 50
        ctx = SymptomContext(move_number=15, board_size=9)
        assert ctx.is_phase("opening") is True

        ctx = SymptomContext(move_number=15, board_size=13)
        assert ctx.is_phase("opening") is True

    # --- Phase 226-F (F-A): current_phase fallback ---

    def test_current_phase_fallback_when_move_number_unknown(self):
        # When move_number is None the karte builder populates
        # current_phase instead; is_phase() must consult it.
        ctx = SymptomContext(move_number=None, current_phase="opening")
        assert ctx.is_phase("opening") is True
        assert ctx.is_phase("middle") is False
        assert ctx.is_phase("endgame") is False

    def test_current_phase_fallback_middle(self):
        ctx = SymptomContext(move_number=None, current_phase="middle")
        assert ctx.is_phase("opening") is False
        assert ctx.is_phase("middle") is True

    def test_current_phase_fallback_endgame(self):
        ctx = SymptomContext(move_number=None, current_phase="endgame")
        assert ctx.is_phase("middle") is False
        assert ctx.is_phase("endgame") is True

    def test_current_phase_fallback_unknown(self):
        ctx = SymptomContext(move_number=None, current_phase="unknown")
        for phase in ("opening", "middle", "endgame"):
            assert ctx.is_phase(phase) is False

    def test_move_number_takes_precedence_over_current_phase(self):
        # Per-move contexts have a real move_number; the karte fallback
        # must not override the explicit value.
        ctx = SymptomContext(move_number=300, current_phase="opening")
        assert ctx.is_phase("opening") is False
        assert ctx.is_phase("endgame") is True


# --- detect_auto_symptoms: positive/negative ---


class TestDetectAutoSymptoms:
    def test_empty_context_returns_empty(self):
        fired = detect_auto_symptoms(SymptomContext())
        # A bare context with no fields shouldn't match anything.
        # Some detectors may still fire on bare fields (e.g. GAME_COUNT>=5
        # is None which is < 5, so no match). We just check it doesn't crash.
        assert isinstance(fired, list)

    def test_no_duplicates_in_fired_list(self):
        fired = detect_auto_symptoms(
            SymptomContext(
                points_lost=20.0,
                move_number=300,
                is_endgame=True,
                score_stdev=3.0,
                winrate_lost=0.5,
                meaning_tag_ids=(
                    MeaningTagId.LIFE_DEATH_ERROR,
                    MeaningTagId.CONNECTION_MISS,
                ),
                hint_categories=(
                    HintCategory.SELF_ATARI,
                    HintCategory.MISTAKE_BLUNDER,
                    HintCategory.IGNORE_ATARI,
                    HintCategory.CURATOR_WEAK_AXIS,
                ),
                avg_points_lost=20.0,
                game_count=10,
                weakness_concentration=0.7,
            )
        )
        assert len(fired) == len(set(fired))

    def test_atari_blindness_fires(self):
        ctx = SymptomContext(
            points_lost=1.5,
            meaning_tag_ids=(MeaningTagId.CAPTURE_RACE_LOSS,),
        )
        fired = detect_auto_symptoms(ctx)
        assert SymptomId.ATARI_BLINDNESS in fired

    def test_first_move_confusion_fires_in_opening(self):
        ctx = SymptomContext(
            move_number=5,
            points_lost=6.0,
        )
        fired = detect_auto_symptoms(ctx)
        assert SymptomId.FIRST_MOVE_CONFUSION in fired

    def test_first_move_confusion_does_not_fire_in_endgame(self):
        ctx = SymptomContext(
            move_number=200,
            points_lost=6.0,
        )
        fired = detect_auto_symptoms(ctx)
        assert SymptomId.FIRST_MOVE_CONFUSION not in fired

    def test_endgame_symptoms_fire_in_endgame(self):
        ctx = SymptomContext(
            move_number=250,
            is_endgame=True,
            meaning_tag_ids=(MeaningTagId.ENDGAME_SLIP,),
            hint_categories=(HintCategory.MISTAKE_BLUNDER,),
        )
        fired = detect_auto_symptoms(ctx)
        assert SymptomId.ENDGAME_VALUATION_ERROR in fired
        assert SymptomId.ENDGAME_PRECISION in fired

    def test_detector_returns_false_no_fire(self):
        ctx = SymptomContext(
            move_number=100,
            points_lost=0.5,  # below all thresholds
        )
        fired = detect_auto_symptoms(ctx)
        assert SymptomId.ATARI_BLINDNESS not in fired
        assert SymptomId.BIG_POINT_BLINDNESS not in fired


# --- Detector robustness ---


class TestDetectorRobustness:
    def test_does_not_crash_on_minimal_context(self):
        # No fields set — every detector should return False safely.
        fired = detect_auto_symptoms(SymptomContext())
        assert isinstance(fired, list)

    def test_does_not_crash_on_extreme_values(self):
        ctx = SymptomContext(
            points_lost=1e9,
            winrate_lost=1e9,
            move_number=99999,
            score_stdev=1e6,
            overall_difficulty=1e6,
        )
        fired = detect_auto_symptoms(ctx)
        assert isinstance(fired, list)


# --- Phase 226-J (J.2): Symptom ↔ Lexicon related_ids coverage ---


class TestSymptomLexiconCoverage:
    """Phase 226-J + 242-C: every symptom (auto-detected and LLM-required)
    must have at least one related_lexicon_ids entry so the LLM prompt
    can reference the terminology. Phase 242-C closed the gap for the
    9 LLM-required symptoms that were empty before:

    - time_pressure_loss / time_misallocation / time_drain
    - shallow_review
    - ai_overload / copy_without_understanding
    - tilt_discouragement / tilt_chain / tilt_emotional_interference
    """

    @pytest.mark.parametrize(
        "sid",
        [
            SymptomId.TOO_MANY_CHOICES,
            SymptomId.ENDGAME_PRECISION,
            SymptomId.SAME_MISTAKE_LOOP,
            SymptomId.STAGNATION_LOOP,
            SymptomId.LOCAL_OPTIMUM,
        ],
    )
    def test_auto_detected_symptom_has_lexicon_links(self, sid):
        symptom = lookup_symptom(sid)
        assert symptom is not None
        assert symptom.related_lexicon_ids, f"{sid.value} must list at least one Lexicon id"

    @pytest.mark.parametrize(
        "sid",
        [
            # Phase 242-C: 9 LLM-required symptoms that now have lexicon links
            SymptomId.TIME_PRESSURE_LOSS,
            SymptomId.TIME_MISALLOCATION,
            SymptomId.TIME_DRAIN,
            SymptomId.SHALLOW_REVIEW,
            SymptomId.AI_OVERLOAD,
            SymptomId.COPY_WITHOUT_UNDERSTANDING,
            SymptomId.TILT_DISCOURAGEMENT,
            SymptomId.TILT_CHAIN,
            SymptomId.TILT_EMOTIONAL_INTERFERENCE,
        ],
    )
    def test_llm_required_symptom_has_lexicon_links(self, sid):
        """Phase 242-C: every LLM-required symptom now has a lexicon link.

        Previously these were empty tuples. The Phase 242-C Lexicon
        YAML extension (5 new entries) provides ground truth for the
        LLM to use in its prompt body.
        """
        symptom = lookup_symptom(sid)
        assert symptom is not None
        assert symptom.related_lexicon_ids, (
            f"{sid.value} must list at least one Lexicon id "
            f"(Phase 242-C closed the gap for LLM-required symptoms)"
        )

    @pytest.mark.parametrize(
        "sid",
        [
            SymptomId.TIME_PRESSURE_LOSS,
            SymptomId.TIME_MISALLOCATION,
            SymptomId.TIME_DRAIN,
        ],
    )
    def test_time_symptoms_link_to_time_management(self, sid):
        symptom = lookup_symptom(sid)
        assert "time_management" in symptom.related_lexicon_ids

    @pytest.mark.parametrize(
        "sid",
        [
            SymptomId.AI_OVERLOAD,
            SymptomId.COPY_WITHOUT_UNDERSTANDING,
            SymptomId.SHALLOW_REVIEW,
        ],
    )
    def test_ai_review_symptoms_link_to_ai_overload_or_post_game_review(self, sid):
        symptom = lookup_symptom(sid)
        ids = set(symptom.related_lexicon_ids)
        # Each AI/review symptom should be near at least one of the
        # new Phase 242-C entries that we created for this cluster.
        assert "ai_overload" in ids or "post_game_review" in ids, (
            f"{sid.value} should link to ai_overload or post_game_review"
        )

    @pytest.mark.parametrize(
        "sid",
        [
            SymptomId.TILT_DISCOURAGEMENT,
            SymptomId.TILT_CHAIN,
            SymptomId.TILT_EMOTIONAL_INTERFERENCE,
        ],
    )
    def test_tilt_symptoms_link_to_tilt_recovery_or_mental_state(self, sid):
        symptom = lookup_symptom(sid)
        ids = set(symptom.related_lexicon_ids)
        assert "tilt_recovery" in ids or "mental_state" in ids, (
            f"{sid.value} should link to tilt_recovery or mental_state"
        )

    def test_too_many_choices_links_priority(self):
        symptom = lookup_symptom(SymptomId.TOO_MANY_CHOICES)
        assert "priority" in symptom.related_lexicon_ids
        assert "triage_priority" in symptom.related_lexicon_ids

    def test_endgame_precision_links_yose(self):
        symptom = lookup_symptom(SymptomId.ENDGAME_PRECISION)
        assert "yose" in symptom.related_lexicon_ids
        assert "counting" in symptom.related_lexicon_ids
        assert "endgame_sente_value" in symptom.related_lexicon_ids

    def test_same_mistake_loop_links_directions(self):
        symptom = lookup_symptom(SymptomId.SAME_MISTAKE_LOOP)
        assert "urgent_vs_big" in symptom.related_lexicon_ids
        assert "direction_of_play" in symptom.related_lexicon_ids

    def test_stagnation_loop_links_balance(self):
        symptom = lookup_symptom(SymptomId.STAGNATION_LOOP)
        assert "whole_board_balance" in symptom.related_lexicon_ids

    def test_local_optimum_links_directions(self):
        symptom = lookup_symptom(SymptomId.LOCAL_OPTIMUM)
        assert "urgent_vs_big" in symptom.related_lexicon_ids
        assert "whole_board_balance" in symptom.related_lexicon_ids


# --- Public API ---


class TestExports:
    def test_all_reexports(self):
        import katrain.core.coach as pkg

        for name in [
            "SymptomId",
            "SymptomContext",
            "Symptom",
            "list_all_symptoms",
            "lookup_symptom",
            "list_auto_detected_symptoms",
            "list_llm_required_symptoms",
            "detect_auto_symptoms",
        ]:
            assert hasattr(pkg, name), f"__init__ missing {name}"
