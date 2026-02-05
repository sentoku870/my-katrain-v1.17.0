# katrain/core/state/events.py
"""Event types and base Event class for state notification system.

This module defines the event types and base Event dataclass used by StateNotifier.
All events are frozen (immutable) for thread-safety.

Design Notes:
- MappingProxyType provides shallow immutability for payload
- Nested objects in payload are still mutable (shallow copy only)
- For deep immutability, use flat payloads or specialized Event subclasses
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any


class EventType(Enum):
    """Event type enumeration (extensible).

    Each type has a string value for debugging/logging purposes.
    """

    GAME_CHANGED = "game_changed"  # Game state changed
    CONFIG_UPDATED = "config_updated"  # Configuration updated
    ANALYSIS_COMPLETE = "analysis_complete"  # Analysis completed


def _freeze_payload(payload: dict[str, Any] | None) -> Mapping[str, Any] | None:
    """Convert payload to an immutable MappingProxyType (shallow copy).

    Args:
        payload: Optional dictionary to freeze

    Returns:
        None if payload is None, otherwise a MappingProxyType wrapping a copy

    Note:
        This is a shallow copy. Nested objects (dict, list, etc.) remain mutable.
        For deep immutability, flatten the payload or define specialized event types.
    """
    if payload is None:
        return None
    return MappingProxyType(dict(payload))  # Copy then proxy


@dataclass(frozen=True)
class Event:
    """Base event class (immutable).

    Events are frozen dataclasses for thread-safety. The payload is wrapped in
    MappingProxyType to prevent modification at the top level.

    Attributes:
        event_type: The type of event (from EventType enum)
        _payload: Internal storage for the frozen payload

    Example:
        >>> event = Event.create(EventType.GAME_CHANGED, {"game_id": 123})
        >>> event.payload["game_id"]
        123
        >>> event.payload["new_key"] = "value"  # Raises TypeError
    """

    event_type: EventType
    _payload: Mapping[str, Any] | None = field(default=None, repr=False)

    @classmethod
    def create(cls, event_type: EventType, payload: dict[str, Any] | None = None) -> "Event":
        """Factory method to create an Event with frozen payload.

        Args:
            event_type: The type of event
            payload: Optional dictionary (will be shallow-copied and frozen)

        Returns:
            A new Event instance with immutable payload
        """
        return cls(event_type=event_type, _payload=_freeze_payload(payload))

    @property
    def payload(self) -> Mapping[str, Any] | None:
        """Read-only access to the payload.

        Returns:
            The frozen payload (MappingProxyType) or None
        """
        return self._payload
