"""Centralized definitions for KaTrain JSON Reports (Summary & Karte).

This module consolidates all constants, enums, and mapping dictionaries
used in report generation to ensure consistency across different report types.
"""
from typing import Final, Dict, List, Any

from katrain.core.eval_metrics import (
    MistakeCategory,
    get_skill_preset,
)
from katrain.core.analysis.meaning_tags import MeaningTagId
from katrain.core.reports.constants import (
    BAD_MOVE_LOSS_THRESHOLD,
    URGENT_MISS_THRESHOLD_LOSS,
    URGENT_MISS_MIN_CONSECUTIVE,
)

# --- Schema Version ---
# Bump this whenever the JSON structure or definitions change.
REPORT_SCHEMA_VERSION: Final[str] = "3.1"  # Phase 153-A: difficulty 削除


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
MISTAKE_THRESHOLDS: Final[Dict[str, float]] = {
    "inaccuracy": 1.0,
    "mistake": 2.5,
    "blunder": 5.0,
}

# Thresholds for specific filtering features
FILTERING_THRESHOLDS: Final[Dict[str, Any]] = {
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
REPORT_THRESHOLDS: Final[Dict[str, Any]] = {
    **FILTERING_THRESHOLDS,
    "loss": MISTAKE_THRESHOLDS,
}


# --- Classifications & Enums ---

MISTAKE_TYPES: Final[List[str]] = [cat.value.lower() for cat in MistakeCategory]

# Fix 2: Sync with MeaningTagId
PRIMARY_TAGS: Final[List[str]] = [tag.value for tag in MeaningTagId]

PHASES: Final[List[str]] = ["opening", "middle", "endgame"]
PHASE_ALIASES: Final[Dict[str, str]] = {"yose": "endgame"}


# --- Reasoning & Attributes ---

# Fix 3: Importance Scale Definition
# Thresholds aligned with IMPORTANT_MOVE_SETTINGS_BY_LEVEL (easy=1.0, normal=0.5, strict=0.3).
IMPORTANCE_DEF: Final[Dict[str, Any]] = {
    "scale": "0.0 to unbounded (logarithmic)",
    "description": "Combined score of loss and semantic interest",
    "thresholds": {
        "interesting": 0.3,
        "important": 0.5,
        "critical": 1.0
    }
}

REASON_CODE_ALIASES: Final[Dict[str, str]] = {
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

REASON_CODES: Final[List[str]] = [
    "shape", "atari", "clump", "heavy", "overconcentrated", "liberties",
    "endgame_hint", "connection", "urgent", "tenuki", "cut_risk",
    "thin", "chase_mode", "reading", "joseki"
]

CATEGORY_ALIASES: Final[Dict[str, str]] = {
    "inaccuracy": "inc",
    "mistake": "bad",
    "blunder": "vbd",
}
