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

Logger Injection (Phase 104):
- Logger is optional: Callable[[str], None] or None
- Caller binds the log level via closure (core layer doesn't know OUTPUT_DEBUG etc.)
- Logger is called once per error with combined message + traceback
- If logger is None or fails, fallback to stderr
"""

import sys
import threading
import traceback
from collections.abc import Callable

from katrain.core.state.events import Event, EventType

# Logger type: level is bound by caller via closure (core layer is level-agnostic)
LoggerType = Callable[[str], None]


class StateNotifier:
    """State change notification system (thread-safe).

    Example:
        >>> notifier = StateNotifier()
        >>> def on_game_changed(event):
        ...     print(f"Game changed: {event.payload}")
        >>> notifier.subscribe(EventType.GAME_CHANGED, on_game_changed)
        >>> notifier.notify(Event.create(EventType.GAME_CHANGED, {"id": 1}))
        Game changed: {'id': 1}

    Logger Injection Example:
        >>> def my_logger(msg: str) -> None:
        ...     print(f"[LOG] {msg}")
        >>> notifier = StateNotifier(logger=my_logger)
    """

    def __init__(self, logger: LoggerType | None = None) -> None:
        """Initialize the notifier with empty subscriber lists.

        Args:
            logger: Optional logger function. If provided, called on callback errors.
                   Signature: Callable[[str], None]. The log level should be
                   bound by the caller via closure (e.g., lambda msg: log(msg, DEBUG)).
                   If None, errors are printed to stderr.
        """
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = {}
        self._lock = threading.RLock()
        self._logger = logger

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
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

    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
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
                self._log_error(event, callback, e)

    def _log_error(self, event: Event, callback: Callable[[Event], None], e: Exception) -> None:
        """Log error when a callback fails (logger injection support, exception-safe).

        The logger is called once with a combined message containing:
        - Callback name, event type, and exception details
        - Full traceback

        This single-call approach improves test determinism.

        If logger is None or fails, falls back to stderr.

        Args:
            event: The event that was being notified
            callback: The callback that failed
            e: The exception that was raised
        """
        cb_name = getattr(callback, "__name__", repr(callback))
        msg = f"[StateNotifier] {event.event_type.value}: {cb_name} failed: {type(e).__name__}: {e!r}"
        tb = traceback.format_exc()
        full_msg = f"{msg}\n{tb}"

        if self._logger:
            try:
                self._logger(full_msg)
            except Exception:
                # Logger failed, fallback to stderr
                print(full_msg, file=sys.stderr)
        else:
            # No logger configured, use stderr
            print(full_msg, file=sys.stderr)

    def clear(self, event_type: EventType | None = None) -> None:
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
