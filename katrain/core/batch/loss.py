"""Canonical loss aggregation (single source of truth for loss values)."""

from __future__ import annotations


def get_canonical_loss(points_lost: float | None) -> float:
    """Return canonical loss value: max(0, points_lost) or 0 if None.

    Negative points_lost (gains from opponent mistakes) are clamped to 0.
    This matches Karte output semantics for consistency.

    Args:
        points_lost: Raw points lost value (may be None or negative)

    Returns:
        Canonical loss value >= 0.0
    """
    if points_lost is None:
        return 0.0
    return max(0.0, points_lost)


# Alias for backward compatibility with private name
_get_canonical_loss = get_canonical_loss
