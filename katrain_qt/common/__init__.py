# katrain_qt/common/__init__.py
"""Common utilities and constants shared across katrain_qt modules."""

from katrain_qt.common.eval_constants import (
    # Thresholds
    EVAL_THRESHOLDS_DESC,
    EVAL_THRESHOLDS_ASC,
    LOW_VISITS_THRESHOLD,
    OWNERSHIP_THRESHOLD,
    # Colors
    EVAL_COLORS,
    EVAL_ROW_COLORS,
    TOP_MOVE_BORDER_COLOR,
    APPROX_BOARD_COLOR,
    OWNERSHIP_BLACK_COLOR,
    OWNERSHIP_WHITE_COLOR,
    OWNERSHIP_BLACK_ALPHA,
    OWNERSHIP_WHITE_ALPHA,
    MISTAKE_RING_COLORS,
    MISTAKE_RING_WIDTH,
    # Scales and alphas
    HINT_SCALE,
    UNCERTAIN_HINT_SCALE,
    HINTS_ALPHA,
    HINTS_LO_ALPHA,
    MARK_SIZE,
    # Helper functions
    get_eval_color_for_loss,
    get_row_color_for_loss,
    # Formatting functions
    format_visits,
    format_score,
)

__all__ = [
    # Thresholds
    "EVAL_THRESHOLDS_DESC",
    "EVAL_THRESHOLDS_ASC",
    "LOW_VISITS_THRESHOLD",
    "OWNERSHIP_THRESHOLD",
    # Colors
    "EVAL_COLORS",
    "EVAL_ROW_COLORS",
    "TOP_MOVE_BORDER_COLOR",
    "APPROX_BOARD_COLOR",
    "OWNERSHIP_BLACK_COLOR",
    "OWNERSHIP_WHITE_COLOR",
    "OWNERSHIP_BLACK_ALPHA",
    "OWNERSHIP_WHITE_ALPHA",
    "MISTAKE_RING_COLORS",
    "MISTAKE_RING_WIDTH",
    # Scales and alphas
    "HINT_SCALE",
    "UNCERTAIN_HINT_SCALE",
    "HINTS_ALPHA",
    "HINTS_LO_ALPHA",
    "MARK_SIZE",
    # Helper functions
    "get_eval_color_for_loss",
    "get_row_color_for_loss",
    # Formatting functions
    "format_visits",
    "format_score",
]
