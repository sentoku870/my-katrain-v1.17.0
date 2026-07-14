"""Phase 207: Coach module — Master coaching database (mode/tone).

This subpackage hosts the LLM "translation" pipeline data and helpers
documented in `docs/archive/specs-planned/phase203-llm-translator.md`.

Layout (planned):
- master_db.py   (Phase 207): §0 / §1 — mode classification + tone config
- lexicon.py     (Phase 208): go_lexicon YAML loader
- symptom_index.py (Phase 209): §2-0 symptom → KataGo metric mapping
- tones.py       (Phase 210): tone selector helpers (delegates to master_db)
- prompt_builder.py (Phase 211): HTML-comment-style SystemInstruction generator
- llm_validator.py (Phase 212): post-hoc output validation

All modules are core-layer (Kivy-free).
"""

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

__all__ = [
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
]