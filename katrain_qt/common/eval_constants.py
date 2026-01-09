# katrain_qt/common/eval_constants.py
"""
Shared evaluation constants for KaTrain Qt.

This module is the SINGLE SOURCE OF TRUTH for all evaluation-related
visual constants. All widgets (board_widget, analysis_panel, candidates_panel)
MUST import from here to ensure consistency.

## Provenance

All constants are extracted from original Kivy KaTrain source code:
- katrain/gui/theme.py (EVAL_COLORS, thresholds, alpha values)
- katrain/gui/badukpan.py (rendering logic, scale factors)
- katrain/config.json (default trainer settings)

See docs/kivy_visual_params_provenance.md for detailed line-by-line references.

## Threshold Conventions

Two orderings exist for thresholds:
- EVAL_THRESHOLDS_DESC: [12, 6, 3, 1.5, 0.5, 0] - Descending, for board overlay
  Used in board_widget.py to find first threshold where loss >= threshold
- EVAL_THRESHOLDS_ASC: [0.2, 0.5, 2.0, 5.0, 8.0] - Ascending, for table rows
  Used in analysis_panel.py/candidates_panel.py to find first threshold where loss > threshold

Both represent the same 6-stage evaluation system, just indexed differently.
"""

from PySide6.QtGui import QColor


# =============================================================================
# Evaluation Thresholds
# =============================================================================

# Descending order thresholds (for board overlay - find first where loss >= threshold)
# Source: katrain/gui/theme.py, config.json trainer/default
# Index 0 = worst (loss >= 12), Index 5 = best (loss < 0.5)
EVAL_THRESHOLDS_DESC = [12.0, 6.0, 3.0, 1.5, 0.5, 0.0]

# Ascending order thresholds (for table row coloring - find first where loss > threshold)
# These are the same breakpoints, just ordered for ascending iteration
# Index 0 = best (loss <= 0.2), Index 5 = worst (loss > 8.0)
EVAL_THRESHOLDS_ASC = [0.2, 0.5, 2.0, 5.0, 8.0]

# Low visits threshold - moves with fewer visits are shown with lower alpha
# Source: katrain/config.json trainer/low_visits = 25
LOW_VISITS_THRESHOLD = 25

# Ownership display threshold - hide territory hints below this value
# Source: katrain/gui/badukpan.py ownership rendering logic
OWNERSHIP_THRESHOLD = 0.1


# =============================================================================
# Evaluation Colors (Board Overlay)
# =============================================================================

# 6-stage evaluation colors for board overlay circles
# Source: katrain/gui/theme.py EVAL_COLORS["theme:normal"]
# Index order: worst (purple) to best (green)
#
# Original Kivy RGBA values:
#   [0.45, 0.13, 0.42, 1.0]  -> RGB(114, 33, 107) - Purple
#   [0.8, 0.0, 0.0, 1.0]     -> RGB(204, 0, 0)    - Red
#   [0.9, 0.4, 0.1, 1.0]     -> RGB(230, 102, 26) - Orange
#   [0.95, 0.95, 0.0, 1.0]   -> RGB(242, 242, 0)  - Yellow
#   [0.67, 0.9, 0.18, 1.0]   -> RGB(171, 230, 46) - Yellow-green
#   [0.12, 0.59, 0.0, 1.0]   -> RGB(30, 150, 0)   - Green
EVAL_COLORS = [
    QColor(114, 33, 107),   # Index 0: Purple (worst: loss >= 12)
    QColor(204, 0, 0),      # Index 1: Red (6 <= loss < 12)
    QColor(230, 102, 26),   # Index 2: Orange (3 <= loss < 6)
    QColor(242, 242, 0),    # Index 3: Yellow (1.5 <= loss < 3)
    QColor(171, 230, 46),   # Index 4: Yellow-green (0.5 <= loss < 1.5)
    QColor(30, 150, 0),     # Index 5: Green (best: loss < 0.5)
]


# =============================================================================
# Evaluation Colors (Table Row Background)
# =============================================================================

# Lighter versions of EVAL_COLORS for table row backgrounds
# These are pastel versions to not overwhelm the text
# Index order: best (green) to worst (purple) - OPPOSITE of EVAL_COLORS!
# This matches ascending threshold iteration in table coloring
EVAL_ROW_COLORS = [
    QColor(200, 255, 200),    # Index 0: Light green (best: loss <= 0.2)
    QColor(230, 255, 200),    # Index 1: Light yellow-green (0.2 < loss <= 0.5)
    QColor(255, 255, 200),    # Index 2: Light yellow (0.5 < loss <= 2.0)
    QColor(255, 230, 200),    # Index 3: Light orange (2.0 < loss <= 5.0)
    QColor(255, 200, 200),    # Index 4: Light red (5.0 < loss <= 8.0)
    QColor(255, 200, 230),    # Index 5: Light purple (worst: loss > 8.0)
]

# Gray for low visits (insufficient confidence)
LOW_VISITS_ROW_BG = QColor(230, 230, 230)


# =============================================================================
# Special Colors
# =============================================================================

# Top move border color (cyan highlight)
# Source: katrain/gui/theme.py TOP_MOVE_BORDER_COLOR
# Original: [10/255, 200/255, 250/255] -> RGB(10, 200, 250)
TOP_MOVE_BORDER_COLOR = QColor(10, 200, 250)

# Board background color (for clearing behind circles)
# Source: katrain/gui/theme.py APPROX_BOARD_COLOR
# Original: [0.95, 0.75, 0.47] -> RGB(242, 191, 120)
APPROX_BOARD_COLOR = QColor(242, 191, 120)

# Ownership territory colors
# Source: katrain/gui/theme.py OWNERSHIP_COLORS
# Black: [0.0, 0.0, 0.10, 0.75] -> RGB(0, 0, 26), alpha=191
# White: [0.92, 0.92, 1.0, 0.80] -> RGB(235, 235, 255), alpha=204
OWNERSHIP_BLACK_COLOR = QColor(0, 0, 26)
OWNERSHIP_WHITE_COLOR = QColor(235, 235, 255)
OWNERSHIP_BLACK_ALPHA = 191  # 0.75 * 255
OWNERSHIP_WHITE_ALPHA = 204  # 0.80 * 255

# Mistake classification ring colors (for last move stone)
# These match the 6-stage eval colors for visual consistency
MISTAKE_RING_COLORS = {
    "good": None,                         # No ring for good moves
    "inaccuracy": QColor(242, 242, 0),    # Yellow
    "mistake": QColor(230, 102, 25),      # Orange
    "blunder": QColor(204, 0, 0),         # Red
    "terrible": QColor(114, 33, 107),     # Purple (worst)
}
MISTAKE_RING_WIDTH = 3.0


# =============================================================================
# Scale and Alpha Values
# =============================================================================

# Hint circle scale relative to stone size
# Source: katrain/gui/theme.py HINT_SCALE = 0.98
HINT_SCALE = 0.98

# Uncertain hint scale (for low-confidence moves)
# Source: katrain/gui/theme.py UNCERTAIN_HINT_SCALE = 0.7
UNCERTAIN_HINT_SCALE = 0.7

# Alpha values for hint circles
# Source: katrain/gui/theme.py
HINTS_ALPHA = 0.8       # Normal visits
HINTS_LO_ALPHA = 0.6    # Low visits (< LOW_VISITS_THRESHOLD)

# Mark size for stone markers (triangle, square, circle)
# Source: katrain/gui/theme.py MARK_SIZE = 0.42
MARK_SIZE = 0.42


# =============================================================================
# Helper Functions
# =============================================================================

def get_eval_color_for_loss(points_lost: float) -> QColor:
    """
    Get evaluation color for board overlay given loss amount.

    Uses descending threshold iteration (EVAL_THRESHOLDS_DESC).

    Args:
        points_lost: Loss in points (0 = best move)

    Returns:
        QColor for the evaluation circle
    """
    i = 0
    while i < len(EVAL_THRESHOLDS_DESC) - 1 and points_lost < EVAL_THRESHOLDS_DESC[i]:
        i += 1
    return QColor(EVAL_COLORS[i])


def get_row_color_for_loss(points_lost: float, is_low_visits: bool = False) -> QColor:
    """
    Get row background color for table given loss amount.

    Uses ascending threshold iteration (EVAL_THRESHOLDS_ASC).

    Args:
        points_lost: Loss in points (0 = best move)
        is_low_visits: If True, return gray for low-confidence move

    Returns:
        QColor for the table row background
    """
    if is_low_visits:
        return QColor(LOW_VISITS_ROW_BG)

    color_idx = 0
    for j, threshold in enumerate(EVAL_THRESHOLDS_ASC):
        if points_lost > threshold:
            color_idx = j + 1
    color_idx = min(color_idx, len(EVAL_ROW_COLORS) - 1)
    return QColor(EVAL_ROW_COLORS[color_idx])


# =============================================================================
# Formatting Functions
# =============================================================================

def format_visits(visits: int) -> str:
    """
    Format visit count with K suffix for readability.

    Examples:
        123 -> "123"
        1234 -> "1.2k"
        12345 -> "12.3k"
        123456 -> "123k"

    Args:
        visits: Raw visit count

    Returns:
        Formatted string with K suffix if >= 1000
    """
    if visits >= 1000:
        return f"{visits / 1000:.1f}k"
    return str(visits)


def format_score(score: float) -> str:
    """
    Format score with explicit sign prefix.

    Examples:
        2.3 -> "+2.3"
        -0.5 -> "-0.5"
        0.0 -> "0.0"

    Args:
        score: Score value (positive = good for current player)

    Returns:
        Formatted string with sign prefix
    """
    if score == 0:
        return "0.0"
    return f"{score:+.1f}"
