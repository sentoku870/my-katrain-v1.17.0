# katrain/core/state/notifier.py
"""State notification system (thread-safe, Kivy-independent).

StateNotifier implements a pub-sub pattern for state change notifications.
It is designed to work in both GUI and headless environments.

Design Principles:
- Kivy-independent (core layer)
- Exception-safe (one listener failure doesn't affect others)
- Defensive copy (safe from modifications during notification)
- Thread-safe (RLock for re-entrancy)

Snapshot Semantics:
- notify() takes a snapshot of the listener list before notification
- Listeners unsubscribed during notify() still receive the current event
- Next notify() will not call unsubscribed listeners
"""
import sys
import threading
import traceback
from typing import Callable, Optional

from katrain.core.state.events import Event, EventType


class StateNotifier:
    """State change notification system (thread-safe).

    Example:
        >>> notifier = StateNotifier()
        >>> def on_game_changed(event):
        ...     print(f"Game changed: {event.payload}")
        >>> notifier.subscribe(EventType.GAME_CHANGED, on_game_changed)
        >>> notifier.notify(Event.create(EventType.GAME_CHANGED, {"id": 1}))
        Game changed: {'id': 1}
    """

    def __init__(self) -> None:
        """Initialize the notifier with empty subscriber lists."""
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = {}
        self._lock = threading.RLock()

    def subscribe(
        self, event_type: EventType, callback: Callable[[Event], None]
    ) -> None:
        """Subscribe a callback to an event type.

        Duplicate subscriptions are ignored (same callback won't be called twice).

        Args:
            event_type: The type of event to subscribe to
            callback: Function to call when event is notified
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)

    def unsubscribe(
        self, event_type: EventType, callback: Callable[[Event], None]
    ) -> None:
        """Unsubscribe a callback from an event type.

        Unsubscribing a non-existent callback is a no-op.

        Args:
            event_type: The type of event to unsubscribe from
            callback: The callback to remove
        """
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                except ValueError:
                    pass  # Callback not found, ignore

    def notify(self, event: Event) -> None:
        """Notify all subscribers of an event.

        Takes a snapshot of the subscriber list before notification, so
        modifications during notification don't affect the current round.

        Each callback is wrapped in try/except to ensure one failure
        doesn't prevent other callbacks from being called.

        Args:
            event: The event to notify subscribers about
        """
        with self._lock:
            # Defensive copy: snapshot of current subscribers
            callbacks = self._subscribers.get(event.event_type, [])[:]

        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                # Log error but continue with other callbacks
                # Phase 104 will inject a proper logger
                cb_name = getattr(callback, "__name__", repr(callback))
                print(
                    f"[StateNotifier] {event.event_type.value}: "
                    f"{cb_name} failed: {type(e).__name__}: {e!r}",
                    file=sys.stderr,
                )
                traceback.print_exc(file=sys.stderr)

    def clear(self, event_type: Optional[EventType] = None) -> None:
        """Clear subscribers (primarily for testing).

        Args:
            event_type: If provided, clear only that type's subscribers.
                       If None, clear all subscribers.
        """
        with self._lock:
            if event_type is None:
                self._subscribers.clear()
            elif event_type in self._subscribers:
                self._subscribers[event_type].clear()
