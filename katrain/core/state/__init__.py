# katrain/core/state/__init__.py
"""State notification system for KaTrain.

This package provides a decoupled state change notification mechanism
that is Kivy-independent and thread-safe.

Public API:
    - EventType: Enum of event types (GAME_CHANGED, CONFIG_UPDATED, etc.)
    - Event: Immutable event dataclass with optional payload
    - StateNotifier: Pub-sub notification system

Example:
    >>> from katrain.core.state import EventType, Event, StateNotifier
    >>>
    >>> notifier = StateNotifier()
    >>>
    >>> def on_config_update(event):
    ...     print(f"Config updated: {event.payload}")
    >>>
    >>> notifier.subscribe(EventType.CONFIG_UPDATED, on_config_update)
    >>> notifier.notify(Event.create(EventType.CONFIG_UPDATED, {"key": "value"}))
    Config updated: {'key': 'value'}
"""
from katrain.core.state.events import Event, EventType
from katrain.core.state.notifier import StateNotifier

__all__ = ["EventType", "Event", "StateNotifier"]
