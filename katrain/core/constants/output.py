"""Output level & status constants.

Phase PR1: Extracted from ``katrain.core.constants`` to limit blast
radius. All symbols are re-exported from the package root for
backward compatibility.

Categories:
    OUTPUT_*    Log level thresholds (used by ``log`` and status bar)
    STATUS_*    Status bar priority values (higher = more prominent)
    KATAGO_EXCEPTION  Sentinel for engine internal errors

Usage:
    from katrain.core.constants.output import OUTPUT_DEBUG, STATUS_ERROR
"""

# --- Output (log) levels ---
OUTPUT_ERROR = -1
OUTPUT_KATAGO_STDERR = -0.5
OUTPUT_INFO = 0
OUTPUT_DEBUG = 1
OUTPUT_EXTRA_DEBUG = 2

# --- Status bar priorities ---
# STATUS_ANALYSIS == STATUS_INFO in priority; both are background info.
STATUS_ANALYSIS = 1.0
STATUS_INFO = 1.1
STATUS_TEACHING = 2.0
STATUS_ERROR = 1000.0

# --- Engine sentinel ---
KATAGO_EXCEPTION = "KATAGO-INTERNAL-ERROR"
