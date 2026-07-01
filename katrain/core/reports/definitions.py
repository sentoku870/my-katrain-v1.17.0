"""Centralized definitions for KaTrain JSON Reports (Summary & Karte).

This module consolidates all constants, enums, and mapping dictionaries
used in report generation to ensure consistency across different report types.
"""
from typing import Any, Final

from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.eval_metrics import (
    MistakeCategory,
)
from katrain.core.reports.constants import (
    BAD_MOVE_LOSS_THRESHOLD,
    URGENT_MISS_MIN_CONSECUTIVE,
    URGENT_MISS_THRESHOLD_LOSS,
)

# --- Schema Version ---
# Bump this whenever the JSON structure or definitions change.
REPORT_SCHEMA_VERSION: Final[str] = "3.4"  # Phase 157-C: even/handicapped split + loss_progression dict; Phase 157-D: top-level win_loss_analysis removed; Phase 157-A/B: bug fixes.


# --- Thresholds ---
# MISTAKE_THRESHOLDS are the canonical mistake-classification boundaries used
# by Karte/Summary JSON definitions. These values are pinned (Phase 149 B-3)
# rather than dynamically derived from `get_skill_preset("auto").score_thresholds`
# so that downstream consumers (LLMs, dashboards, golden tests) observe a
# stable contract. If the auto preset is changed in the future, update these
# values intentionally and regenerate any affected golden files.
#
# Source: matches standard preset (1.0/2.5/5.0) as the canonical practical
# classification used throughout the report pipeline.
MISTAKE_THRESHOLDS: Final[dict[str, float]] = {
    "inaccuracy": 1.0,
    "mistake": 2.5,
    "blunder": 5.0,
}

# Thresholds for specific filtering features
FILTERING_THRESHOLDS: Final[dict[str, Any]] = {
    "bad_move_loss": BAD_MOVE_LOSS_THRESHOLD,
    "urgent_miss": {
        "loss": URGENT_MISS_THRESHOLD_LOSS,
        "min_consecutive": URGENT_MISS_MIN_CONSECUTIVE,
    },
    "phase": {
        "opening_max": 50,
        "middle_max": 200,
        "endgame_min": 201,
    }
}

# Combined thresholds for JSON reporting (merges loss thresholds and filtering thresholds)
REPORT_THRESHOLDS: Final[dict[str, Any]] = {
    **FILTERING_THRESHOLDS,
    "loss": MISTAKE_THRESHOLDS,
}


# --- Classifications & Enums ---

MISTAKE_TYPES: Final[list[str]] = [cat.value.lower() for cat in MistakeCategory]

# Fix 2: Sync with MeaningTagId
PRIMARY_TAGS: Final[list[str]] = [tag.value for tag in MeaningTagId]

PHASES: Final[list[str]] = ["opening", "middle", "endgame"]
PHASE_ALIASES: Final[dict[str, str]] = {"yose": "endgame"}


# --- Reasoning & Attributes ---

# Fix 3: Importance Scale Definition
# Thresholds aligned with IMPORTANT_MOVE_SETTINGS_BY_LEVEL (easy=1.0, normal=0.5, strict=0.3).
IMPORTANCE_DEF: Final[dict[str, Any]] = {
    "scale": "0.0 to unbounded (logarithmic)",
    "description": "Combined score of loss and semantic interest",
    "thresholds": {
        "interesting": 0.3,
        "important": 0.5,
        "critical": 1.0
    }
}

REASON_CODE_ALIASES: Final[dict[str, str]] = {
    "low_liberties": "liberties",
    "need_connect": "connection",
    "heavy_loss": "heavy",
    "reading_failure": "reading",
    "shape_mistake": "shape",
    "endgame_slip": "endgame_hint",
    "cut_risk": "cut_risk",
    "thin": "thin",
    "chase_mode": "chase_mode",
    "connection_mistake": "connection", # Map meaning tag to reason code
    "liberties_mistake": "liberties",   # Map meaning tag to reason code
    "joseki_mistake": "joseki",         # New
}

REASON_CODES: Final[list[str]] = [
    "shape", "atari", "clump", "heavy", "overconcentrated", "liberties",
    "endgame_hint", "connection", "urgent", "tenuki", "cut_risk",
    "thin", "chase_mode", "reading", "joseki"
]

CATEGORY_ALIASES: Final[dict[str, str]] = {
    "inaccuracy": "inc",
    "mistake": "bad",
    "blunder": "vbd",
}
