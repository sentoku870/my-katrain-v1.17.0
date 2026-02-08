"""Centralized definitions for KaTrain JSON Reports (Summary & Karte).

This module consolidates all constants, enums, and mapping dictionaries
used in report generation to ensure consistency across different report types.
"""
from typing import Final, Dict, List, Any

from katrain.core.eval_metrics import (
    MistakeCategory,
    PositionDifficulty,
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
REPORT_SCHEMA_VERSION: Final[str] = "2.1"


# --- Thresholds ---
# Derived from 'auto' preset for consistency with practical classification
_auto_preset = get_skill_preset("auto")
_score_thresholds = _auto_preset.score_thresholds

MISTAKE_THRESHOLDS: Final[Dict[str, float]] = {
    "inaccuracy": _score_thresholds[0], # ~0.5
    "mistake": _score_thresholds[1],    # ~2.0
    "blunder": _score_thresholds[2],    # ~5.0
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

# Fix 5: Clarify Difficulty Definitions
DIFFICULTY_LEVELS: Final[Dict[str, str]] = {
    "simple": "One clear best move / Obvious",
    "normal": "Standard complexity",
    "hard": "Complex pattern / Many candidates",
    "only": "Forced move / Single valid candidate",
    "unknown": "Difficulty could not be determined"
}

# Fix 2: Sync with MeaningTagId
PRIMARY_TAGS: Final[List[str]] = [tag.value for tag in MeaningTagId]

PHASES: Final[List[str]] = ["opening", "middle", "endgame"]
PHASE_ALIASES: Final[Dict[str, str]] = {"yose": "endgame"}


# --- Reasoning & Attributes ---

# Fix 3: Importance Scale Definition
IMPORTANCE_DEF: Final[Dict[str, Any]] = {
    "scale": "0.0 to unbounded (logarithmic)",
    "description": "Combined score of loss and semantic interest",
    "thresholds": {
        "interesting": 1.0,
        "important": 3.0,
        "critical": 6.0
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
