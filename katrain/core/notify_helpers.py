# katrain/core/notify_helpers.py
"""Notification helper functions (Kivy-independent).

These helpers encapsulate the notify() call pattern with defensive access.
They can be safely imported in tests without Kivy dependencies.

Phase 105: Initial implementation
"""
from typing import Any, Optional

from katrain.core.state import Event, EventType


def notify_game_changed(ctx: Any, *, source: str) -> bool:
    """Notify GAME_CHANGED if notifier is available.

    Args:
        ctx: Context with optional state_notifier attribute
        source: Event source identifier (e.g., "new_game", "load_sgf")

    Returns:
        True if notification was sent, False otherwise
    """
    notifier = getattr(ctx, "state_notifier", None)
    if notifier is None:
        return False

    notifier.notify(Event.create(EventType.GAME_CHANGED, {"source": source}))
    return True


def maybe_notify_analysis_complete(
    katrain: Any,
    *,
    partial_result: bool,
    results_exist: bool,
    query_id: Optional[str],
) -> bool:
    """Notify ANALYSIS_COMPLETE if conditions are met.

    Conditions for notification:
    - partial_result is False (not during-search result)
    - results_exist is True (analysis has actual results)
    - katrain has state_notifier attribute
    - query_id is not None

    Args:
        katrain: KaTrainBase or KaTrainGui instance
        partial_result: True if this is a partial (during-search) result
        results_exist: True if analysis has results (not noResults)
        query_id: Query identifier for payload (may be None)

    Returns:
        True if notification was sent, False otherwise
    """
    if partial_result or not results_exist or query_id is None:
        return False

    notifier = getattr(katrain, "state_notifier", None)
    if notifier is None:
        return False

    notifier.notify(Event.create(EventType.ANALYSIS_COMPLETE, {"query_id": query_id}))
    return True
