"""Query priority constants.

Phase PR1: Extracted from ``katrain.core.constants`` to limit blast
radius. All symbols are re-exported from the package root for
backward compatibility.

Lower value = higher priority. New moves (PRIORITY_DEFAULT) sit at
1000, while interactive extras (PRIORITY_ALTERNATIVES / EQUALIZE /
EXTRA_ANALYSIS) sit at 100 so the user feels no latency.
"""

# --- Move ordering sentinel ---
ADDITIONAL_MOVE_ORDER = 999

# --- Query priorities (lower = higher priority) ---
PRIORITY_GAME_ANALYSIS = -100
PRIORITY_SWEEP = -10
PRIORITY_ALTERNATIVES = 100
PRIORITY_EQUALIZE = 100
PRIORITY_EXTRA_ANALYSIS = 100
PRIORITY_DEFAULT = 1000
PRIORITY_EXTRA_AI_QUERY = 10_000
