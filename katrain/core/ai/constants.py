"""AI strategy constants (Phase 203: extracted from core/constants.py).
Phase 280: Slimmed down to only the two survivor strategies
(`ai:default` and `ai:handicap`).

All identifiers, strategy lists, strength map, statistics constants,
option values, and key properties used by the AI subsystem live here.
"""

# Strategy identifiers (string keys like "ai:default")
AI_DEFAULT = "ai:default"
AI_HANDICAP = "ai:handicap"

AI_CONFIG_DEFAULT = AI_HANDICAP

# Strategy aggregations (kept minimal: only the two survivors)
AI_STRATEGIES = [AI_DEFAULT, AI_HANDICAP]
AI_STRATEGIES_RECOMMENDED_ORDER = [AI_DEFAULT, AI_HANDICAP]

AI_STRENGTH = {  # dan ranks, backup if model is missing.
    AI_DEFAULT: 9,
    AI_HANDICAP: 9,
}

# --- AI Statistics Constants ---

# Accuracy decay base: accuracy = 100 * base ** weighted_loss
# Loss 1 point → 75%, 2 points → 56%, 3 points → 42%
AI_ACCURACY_DECAY_BASE: float = 0.75

# Pass loss threshold: skip pass moves with loss greater than this (in points)
AI_PASS_LOSS_THRESHOLD: float = 0.75

# Endgame fill ratio: board fill ratio to consider endgame (settings default)
AI_ENDGAME_FILL_RATIO_DEFAULT: float = 0.75

# Option values only used by the two surviving strategies (DefaultStrategy uses none).
AI_OPTION_VALUES = {
    "automatic": "bool",
    "pda": [(x / 10, f"{'W' if x < 0 else 'B'}+{abs(x / 10):.1f}") for x in range(-30, 31)],
}

AI_KEY_PROPERTIES = {
    "automatic",
}


__all__ = [
    # Strategy identifiers
    "AI_DEFAULT",
    "AI_HANDICAP",
    # Aggregations
    "AI_CONFIG_DEFAULT",
    "AI_STRATEGIES",
    "AI_STRATEGIES_RECOMMENDED_ORDER",
    "AI_STRENGTH",
    # Statistics
    "AI_ACCURACY_DECAY_BASE",
    "AI_PASS_LOSS_THRESHOLD",
    "AI_ENDGAME_FILL_RATIO_DEFAULT",
    # Options
    "AI_OPTION_VALUES",
    "AI_KEY_PROPERTIES",
]
