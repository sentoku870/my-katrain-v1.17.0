"""Phase 207-209: Coach module — Master coaching database + Lexicon + Symptom index.

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
] 