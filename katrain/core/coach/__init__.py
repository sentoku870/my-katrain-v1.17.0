"""Phase 207-212: Coach module — Master coaching database + Lexicon + Symptom index + Tones + Prompt builder + Validator.

This subpackage hosts the LLM "translation" pipeline data and helpers
documented in `docs/archive/specs-planned/phase203-llm-translator.md`.

Layout:
- master_db.py     (Phase 207): §0 / §1 — mode classification + tone config
- lexicon.py       (Phase 208): go_lexicon YAML loader
- symptom_index.py (Phase 209): §2-0 symptom → KataGo metric mapping
- tones.py         (Phase 210): tone selector helpers (delegates to master_db)
- prompt_builder.py (Phase 211): HTML-comment-style SystemInstruction generator
- llm_validator.py (Phase 212): post-hoc output validation

All modules are core-layer (Kivy-free).
"""

from katrain.core.coach.calibration_fixtures import (
    ALL_FIXTURES,
    GoldenFixture,
    get_fixture,
    list_fixture_names,
)
from katrain.core.coach.json_type import (
    JsonType,
    detect_json_type,
    extract_summary_game_count,
    extract_summary_mistake_buckets,
    extract_summary_total_loss,
    is_karte,
    is_summary,
    normalize_summary_to_karte_shape,
)
from katrain.core.coach.karte_detector import (
    build_symptom_context_from_karte,
    detect_symptoms_from_karte,
    extract_avg_points_lost,
    extract_avg_streak_loss,
    extract_avg_winrate_lost,
    extract_consecutive_loss_run,
    extract_critical_move_count,
    extract_game_count,
    extract_good_move_count,
    extract_longest_streak,
    extract_max_overall_difficulty,
    extract_max_score_stdev,
    extract_max_winrate_drop,
    extract_streak_count,
    extract_total_streak_loss,
    extract_weakness_concentration,
    extract_winrate_scorelead_correlation,
    extract_winrate_scorelead_pairs,
)
from katrain.core.coach.lexicon import (
    DEFAULT_LEXICON_PATH,
    LexiconBundle,
    LexiconConcept,
    LexiconEntry,
    all_ids,
    entries_by_category,
    entries_by_level,
    get_concept,
    get_entry,
    inject_lexicon_for_prompt,
    load_lexicon,
    validate_references,
)
from katrain.core.coach.llm_validator import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    validate_llm_output,
)
from katrain.core.coach.master_db import (
    CoachMode,
    ModeConfig,
    RankRange,
    ToneConfig,
    ToneVoice,
    all_modes,
    all_tones,
    estimate_mode_from_loss,
    estimate_mode_from_rank,
    get_mode_config,
    get_tone_config,
)
from katrain.core.coach.prompt_builder import (
    LlmPrompt,
    PromptConfig,
    append_llm_prompt_block,
    build_translation_prompt,
    render_markdown,
    validate_prompt_config,
)
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
from katrain.core.coach.tones import (
    apply_kansai_normalisation,
    check_prohibited,
    greeting_for_mode,
    greeting_for_voice,
    has_kansai_markers,
    modes_for_voice,
    select_voice,
    voice_summary,
)

__all__ = [
    # master_db (Phase 207)
    "CoachMode",
    "ToneVoice",
    "RankRange",
    "ModeConfig",
    "ToneConfig",
    "get_mode_config",
    "get_tone_config",
    "all_modes",
    "all_tones",
    "estimate_mode_from_rank",
    "estimate_mode_from_loss",
    # lexicon (Phase 208)
    "LexiconEntry",
    "LexiconConcept",
    "LexiconBundle",
    "DEFAULT_LEXICON_PATH",
    "load_lexicon",
    "get_entry",
    "get_concept",
    "entries_by_level",
    "entries_by_category",
    "validate_references",
    "inject_lexicon_for_prompt",
    "all_ids",
    # symptom_index (Phase 209)
    "SymptomId",
    "SymptomContext",
    "Symptom",
    "list_all_symptoms",
    "lookup_symptom",
    "list_auto_detected_symptoms",
    "list_llm_required_symptoms",
    "detect_auto_symptoms",
    # tones (Phase 210)
    "select_voice",
    "greeting_for_mode",
    "greeting_for_voice",
    "has_kansai_markers",
    "apply_kansai_normalisation",
    "check_prohibited",
    "voice_summary",
    "modes_for_voice",
    # prompt_builder (Phase 211)
    "PromptConfig",
    "LlmPrompt",
    "build_translation_prompt",
    "append_llm_prompt_block",
    "render_markdown",
    "validate_prompt_config",  # Phase 226-J
    # llm_validator (Phase 212)
    "ValidationSeverity",
    "ValidationIssue",
    "ValidationReport",
    "validate_llm_output",
    # karte_detector (Phase 215)
    "build_symptom_context_from_karte",
    "detect_symptoms_from_karte",
    "extract_avg_points_lost",
    "extract_avg_winrate_lost",
    "extract_avg_streak_loss",
    "extract_consecutive_loss_run",
    "extract_critical_move_count",
    "extract_game_count",
    "extract_good_move_count",
    "extract_longest_streak",
    "extract_max_overall_difficulty",
    "extract_max_score_stdev",
    "extract_max_winrate_drop",
    "extract_streak_count",
    "extract_total_streak_loss",
    "extract_weakness_concentration",
    "extract_winrate_scorelead_correlation",
    "extract_winrate_scorelead_pairs",
    # calibration_fixtures (Phase 218)
    "GoldenFixture",
    "ALL_FIXTURES",
    "get_fixture",
    "list_fixture_names",
    # json_type (Phase 221)
    "JsonType",
    "detect_json_type",
    "is_karte",
    "is_summary",
    "normalize_summary_to_karte_shape",
    "extract_summary_game_count",
    "extract_summary_total_loss",
    "extract_summary_mistake_buckets",
]
