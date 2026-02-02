"""Presentation utilities for Leela estimated loss.

This module provides color calculation and formatting functions
for displaying Leela analysis results.
"""

from __future__ import annotations

from katrain.core.constants import (
    LEELA_COLOR_BEST,
    LEELA_COLOR_SMALL,
    LEELA_COLOR_MEDIUM,
    LEELA_COLOR_LARGE,
    LEELA_LOSS_THRESHOLD_SMALL,
    LEELA_LOSS_THRESHOLD_MEDIUM,
)


def lerp_color(
    c1: tuple[float, float, float, float],
    c2: tuple[float, float, float, float],
    t: float,
) -> tuple[float, float, float, float]:
    """Linear interpolation between two colors.

    Args:
        c1: Start color (RGBA, 0.0-1.0)
        c2: End color (RGBA, 0.0-1.0)
        t: Interpolation factor (0.0 = c1, 1.0 = c2)

    Returns:
        Interpolated color (RGBA, 0.0-1.0)
    """
    t = max(0.0, min(1.0, t))  # Clamp t
    return (
        c1[0] + (c2[0] - c1[0]) * t,
        c1[1] + (c2[1] - c1[1]) * t,
        c1[2] + (c2[2] - c1[2]) * t,
        c1[3] + (c2[3] - c1[3]) * t,
    )


def loss_to_color(loss_est: float) -> tuple[float, float, float, float]:
    """Convert estimated loss to display color.

    Uses color gradient based on loss thresholds:
    - 0.0: Green (best move)
    - 0.1 - 2.0: Green → Yellow (small loss)
    - 2.1 - 5.0: Yellow → Orange (medium loss)
    - > 5.0: Orange → Red (large loss)

    Args:
        loss_est: Estimated loss value

    Returns:
        Color as (R, G, B, A) tuple with values 0.0-1.0
    """
    if loss_est <= 0.0:
        return LEELA_COLOR_BEST

    elif loss_est <= LEELA_LOSS_THRESHOLD_SMALL:
        # 0.1 - 2.0: Green → Yellow
        t = loss_est / LEELA_LOSS_THRESHOLD_SMALL
        return lerp_color(LEELA_COLOR_BEST, LEELA_COLOR_SMALL, t)

    elif loss_est <= LEELA_LOSS_THRESHOLD_MEDIUM:
        # 2.1 - 5.0: Yellow → Orange
        t = (loss_est - LEELA_LOSS_THRESHOLD_SMALL) / (
            LEELA_LOSS_THRESHOLD_MEDIUM - LEELA_LOSS_THRESHOLD_SMALL
        )
        return lerp_color(LEELA_COLOR_SMALL, LEELA_COLOR_MEDIUM, t)

    else:
        # > 5.0: Orange → Red
        t = min(1.0, (loss_est - LEELA_LOSS_THRESHOLD_MEDIUM) / LEELA_LOSS_THRESHOLD_MEDIUM)
        return lerp_color(LEELA_COLOR_MEDIUM, LEELA_COLOR_LARGE, t)


def format_loss_est(loss: float | None) -> str:
    """Format estimated loss for display.

    Args:
        loss: Estimated loss value, or None if not calculated

    Returns:
        Formatted string:
        - None -> "--"
        - 0.0 -> "0.0"
        - 2.345 -> "2.3"
    """
    if loss is None:
        return "--"
    return f"{loss:.1f}"


def format_winrate_pct(winrate: float) -> str:
    """Format winrate as percentage.

    Args:
        winrate: Winrate as 0.0-1.0

    Returns:
        Formatted percentage string (e.g., "52.3%")
    """
    return f"{winrate * 100:.1f}%"


def format_visits(visits: int) -> str:
    """Format visit count for display.

    Args:
        visits: Visit count

    Returns:
        Formatted string with K/M suffix for large numbers
    """
    if visits >= 1_000_000:
        return f"{visits / 1_000_000:.1f}M"
    elif visits >= 1_000:
        return f"{visits / 1_000:.1f}K"
    else:
        return str(visits)
