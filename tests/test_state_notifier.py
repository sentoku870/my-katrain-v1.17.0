# tests/test_state_notifier.py
"""Unit tests for StateNotifier, Event, and EventType.

Test categories:
- Basic functionality (subscribe, notify, unsubscribe)
- Safety (exception handling, defensive copy, duplicates)
- Thread safety (concurrent subscribe/notify)
- Snapshot semantics (unsubscribe during notify)
- Event immutability (frozen dataclass, MappingProxyType)
"""

import subprocess
import sys
import threading
from types import MappingProxyType

import pytest

from katrain.core.state import Event, EventType, StateNotifier


class TestStateNotifier:
    """StateNotifier unit tests."""

    def test_subscribe_and_notify(self) -> None:
        """Basic subscribe and notify flow."""
        notifier = StateNotifier()
        received: list[Event] = []

        def callback(event: Event) -> None:
            received.append(event)

        notifier.subscribe(EventType.GAME_CHANGED, callback)
        event = Event.create(EventType.GAME_CHANGED, {"game_id": 42})
        notifier.notify(event)

        assert len(received) == 1
        assert received[0].event_type == EventType.GAME_CHANGED
        assert received[0].payload is not None
        assert received[0].payload["game_id"] == 42

    def test_unsubscribe(self) -> None:
        """Unsubscribe prevents future notifications."""
        notifier = StateNotifier()
        received: list[Event] = []

        def callback(event: Event) -> None:
            received.append(event)

        notifier.subscribe(EventType.GAME_CHANGED, callback)
        notifier.unsubscribe(EventType.GAME_CHANGED, callback)

        notifier.notify(Event.create(EventType.GAME_CHANGED))

        assert len(received) == 0

    def test_notify_no_subscribers(self) -> None:
        """Notify with no subscribers is a no-op (no error)."""
        notifier = StateNotifier()
        event = Event.create(EventType.GAME_CHANGED)

        # Should not raise
        notifier.notify(event)

    def test_multiple_subscribers_same_type(self) -> None:
        """Multiple subscribers for the same event type all receive events."""
        notifier = StateNotifier()
        results: list[str] = []

        def callback_a(event: Event) -> None:
            results.append("A")

        def callback_b(event: Event) -> None:
            results.append("B")

        notifier.subscribe(EventType.CONFIG_UPDATED, callback_a)
        notifier.subscribe(EventType.CONFIG_UPDATED, callback_b)

        notifier.notify(Event.create(EventType.CONFIG_UPDATED))

        assert "A" in results
        assert "B" in results
        assert len(results) == 2

    def test_multiple_event_types(self) -> None:
        """Subscribers to different event types only receive their events."""
        notifier = StateNotifier()
        game_count = 0
        config_count = 0

        def on_game(event: Event) -> None:
            nonlocal game_count
            game_count += 1

        def on_config(event: Event) -> None:
            nonlocal config_count
            config_count += 1

        notifier.subscribe(EventType.GAME_CHANGED, on_game)
        notifier.subscribe(EventType.CONFIG_UPDATED, on_config)

        notifier.notify(Event.create(EventType.GAME_CHANGED))
        notifier.notify(Event.create(EventType.GAME_CHANGED))
        notifier.notify(Event.create(EventType.CONFIG_UPDATED))

        assert game_count == 2
        assert config_count == 1

    def test_callback_exception_does_not_affect_others(self, capsys: pytest.CaptureFixture) -> None:
        """One callback's exception doesn't prevent other callbacks."""
        notifier = StateNotifier()
        results: list[str] = []

        def bad_callback(event: Event) -> None:
            raise ValueError("Intentional error")

        def good_callback(event: Event) -> None:
            results.append("good")

        notifier.subscribe(EventType.GAME_CHANGED, bad_callback)
        notifier.subscribe(EventType.GAME_CHANGED, good_callback)

        notifier.notify(Event.create(EventType.GAME_CHANGED))

        # Good callback should still be called
        assert results == ["good"]

        # Error should be logged to stderr
        captured = capsys.readouterr()
        assert "bad_callback failed" in captured.err
        assert "ValueError" in captured.err

    def test_defensive_copy_during_notify(self) -> None:
        """Adding a subscriber during notify doesn't affect current notification."""
        notifier = StateNotifier()
        call_order: list[str] = []

        def late_callback(event: Event) -> None:
            call_order.append("late")

        def first_callback(event: Event) -> None:
            call_order.append("first")
            # Try to add new subscriber during notification
            notifier.subscribe(EventType.GAME_CHANGED, late_callback)

        notifier.subscribe(EventType.GAME_CHANGED, first_callback)
        notifier.notify(Event.create(EventType.GAME_CHANGED))

        # Only first_callback was called in this round
        assert call_order == ["first"]

        # Next notification should call both
        call_order.clear()
        notifier.notify(Event.create(EventType.GAME_CHANGED))
        assert "first" in call_order
        assert "late" in call_order

    def test_duplicate_subscribe_ignored(self) -> None:
        """Subscribing the same callback twice is a no-op."""
        notifier = StateNotifier()
        count = 0

        def callback(event: Event) -> None:
            nonlocal count
            count += 1

        notifier.subscribe(EventType.GAME_CHANGED, callback)
        notifier.subscribe(EventType.GAME_CHANGED, callback)  # Duplicate

        notifier.notify(Event.create(EventType.GAME_CHANGED))

        assert count == 1  # Called only once

    def test_unsubscribe_nonexistent_noop(self) -> None:
        """Unsubscribing a non-existent callback is a no-op."""
        notifier = StateNotifier()

        def callback(event: Event) -> None:
            pass

        # Should not raise
        notifier.unsubscribe(EventType.GAME_CHANGED, callback)
        notifier.unsubscribe(EventType.CONFIG_UPDATED, callback)

    def test_concurrent_subscribe(self) -> None:
        """Concurrent subscribe calls don't cause exceptions."""
        notifier = StateNotifier()
        threads: list[threading.Thread] = []
        errors: list[Exception] = []

        def subscribe_many() -> None:
            try:
                for i in range(100):
                    notifier.subscribe(EventType.GAME_CHANGED, lambda e, n=i: None)
            except Exception as e:
                errors.append(e)

        for _ in range(5):
            t = threading.Thread(target=subscribe_many)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        # Notifier should still be usable
        notifier.notify(Event.create(EventType.GAME_CHANGED))

    def test_concurrent_notify(self) -> None:
        """Concurrent notify calls don't cause exceptions."""
        notifier = StateNotifier()
        call_count = 0
        lock = threading.Lock()

        def callback(event: Event) -> None:
            nonlocal call_count
            with lock:
                call_count += 1

        notifier.subscribe(EventType.GAME_CHANGED, callback)

        threads: list[threading.Thread] = []
        errors: list[Exception] = []

        def notify_many() -> None:
            try:
                for _ in range(50):
                    notifier.notify(Event.create(EventType.GAME_CHANGED))
            except Exception as e:
                errors.append(e)

        for _ in range(5):
            t = threading.Thread(target=notify_many)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        # 5 threads * 50 notifications = 250
        assert call_count == 250

    def test_unsubscribe_during_notify_still_receives_current(self) -> None:
        """Unsubscribing during notify still receives the current event."""
        notifier = StateNotifier()
        received: list[str] = []

        def self_unsubscribing_callback(event: Event) -> None:
            received.append("self")
            notifier.unsubscribe(EventType.GAME_CHANGED, self_unsubscribing_callback)

        def other_callback(event: Event) -> None:
            received.append("other")

        notifier.subscribe(EventType.GAME_CHANGED, self_unsubscribing_callback)
        notifier.subscribe(EventType.GAME_CHANGED, other_callback)

        # First notify: both receive
        notifier.notify(Event.create(EventType.GAME_CHANGED))
        assert "self" in received
        assert "other" in received

        # Second notify: only other receives (self unsubscribed)
        received.clear()
        notifier.notify(Event.create(EventType.GAME_CHANGED))
        assert received == ["other"]

    def test_clear_all(self) -> None:
        """Clear all subscribers."""
        notifier = StateNotifier()
        count = 0

        def callback(event: Event) -> None:
            nonlocal count
            count += 1

        notifier.subscribe(EventType.GAME_CHANGED, callback)
        notifier.subscribe(EventType.CONFIG_UPDATED, callback)

        notifier.clear()

        notifier.notify(Event.create(EventType.GAME_CHANGED))
        notifier.notify(Event.create(EventType.CONFIG_UPDATED))

        assert count == 0

    def test_clear_specific_type(self) -> None:
        """Clear subscribers for a specific event type only."""
        notifier = StateNotifier()
        game_count = 0
        config_count = 0

        def on_game(event: Event) -> None:
            nonlocal game_count
            game_count += 1

        def on_config(event: Event) -> None:
            nonlocal config_count
            config_count += 1

        notifier.subscribe(EventType.GAME_CHANGED, on_game)
        notifier.subscribe(EventType.CONFIG_UPDATED, on_config)

        notifier.clear(EventType.GAME_CHANGED)

        notifier.notify(Event.create(EventType.GAME_CHANGED))
        notifier.notify(Event.create(EventType.CONFIG_UPDATED))

        assert game_count == 0
        assert config_count == 1


class TestEvent:
    """Event dataclass tests."""

    def test_frozen(self) -> None:
        """Event is a frozen dataclass."""
        event = Event.create(EventType.GAME_CHANGED)
        with pytest.raises(AttributeError):
            event.event_type = EventType.CONFIG_UPDATED  # type: ignore[misc]

    def test_payload_optional(self) -> None:
        """Event can be created without payload."""
        event = Event.create(EventType.GAME_CHANGED)
        assert event.payload is None

    def test_payload_with_data(self) -> None:
        """Event can be created with payload."""
        event = Event.create(EventType.GAME_CHANGED, {"key": "value"})
        assert event.payload is not None
        assert event.payload["key"] == "value"

    def test_equality(self) -> None:
        """Events with same type and payload are equal."""
        event1 = Event(EventType.GAME_CHANGED, MappingProxyType({"a": 1}))
        event2 = Event(EventType.GAME_CHANGED, MappingProxyType({"a": 1}))
        assert event1 == event2

    def test_payload_is_immutable(self) -> None:
        """Payload is a MappingProxyType (immutable at top level)."""
        event = Event.create(EventType.GAME_CHANGED, {"key": "value"})
        assert event.payload is not None
        assert isinstance(event.payload, MappingProxyType)

    def test_create_factory_freezes_payload(self) -> None:
        """Event.create() converts payload to MappingProxyType."""
        payload = {"key": "value"}
        event = Event.create(EventType.GAME_CHANGED, payload)
        assert event.payload is not None
        assert isinstance(event.payload, MappingProxyType)

    def test_payload_mutation_raises_typeerror(self) -> None:
        """Attempting to mutate payload raises TypeError."""
        event = Event.create(EventType.GAME_CHANGED, {"key": "value"})
        assert event.payload is not None
        with pytest.raises(TypeError):
            event.payload["new_key"] = "new_value"  # type: ignore[index]

    def test_payload_not_aliased_to_original(self) -> None:
        """Payload is not aliased to the original dict."""
        original = {"key": "original"}
        event = Event.create(EventType.GAME_CHANGED, original)

        # Modify original dict
        original["key"] = "modified"
        original["new_key"] = "new_value"

        # Event payload should be unchanged
        assert event.payload is not None
        assert event.payload["key"] == "original"
        assert "new_key" not in event.payload

    def test_nested_payload_is_mutable(self) -> None:
        """Nested objects in payload are still mutable (shallow immutability)."""
        nested = {"inner_key": "inner_value"}
        event = Event.create(EventType.GAME_CHANGED, {"nested": nested})

        assert event.payload is not None
        # Nested dict is still mutable (shallow immutability limitation)
        event.payload["nested"]["inner_key"] = "modified"
        assert event.payload["nested"]["inner_key"] == "modified"


class TestEventType:
    """EventType enum tests."""

    def test_all_types_have_string_values(self) -> None:
        """All EventType members have string values."""
        for event_type in EventType:
            assert isinstance(event_type.value, str)
            assert len(event_type.value) > 0

    def test_at_least_three_types(self) -> None:
        """At least three event types are defined."""
        assert len(EventType) >= 3

    def test_expected_types_exist(self) -> None:
        """Expected event types are defined."""
        assert EventType.GAME_CHANGED.value == "game_changed"
        assert EventType.CONFIG_UPDATED.value == "config_updated"
        assert EventType.ANALYSIS_COMPLETE.value == "analysis_complete"


class TestKivyIsolation:
    """Verify state module doesn't import Kivy."""

    def test_state_module_does_not_import_kivy(self) -> None:
        """core/state module doesn't import Kivy (clean subprocess)."""
        # Single-line code to avoid IndentationError
        code = (
            "import sys; "
            "import katrain.core.state as s; "
            "kivy = [m for m in sys.modules if m.startswith('kivy')]; "
            "sys.exit(1) if kivy else print('OK')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Kivy imported:\nreturncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )


class TestStateNotifierLogger:
    """Logger injection tests (Phase 104)."""

    def test_logger_injection_called_on_error(self) -> None:
        """Logger is called once with combined msg+traceback on callback error."""
        logs: list[str] = []
        notifier = StateNotifier(logger=logs.append)

        def bad_callback(event: Event) -> None:
            raise ValueError("intentional")

        notifier.subscribe(EventType.GAME_CHANGED, bad_callback)
        notifier.notify(Event.create(EventType.GAME_CHANGED))

        # Logger called exactly once (combined message)
        assert len(logs) == 1
        combined_msg = logs[0]
        assert "bad_callback failed" in combined_msg
        assert "ValueError" in combined_msg
        assert "Traceback" in combined_msg

    def test_logger_none_fallback_to_stderr(self, capsys: pytest.CaptureFixture) -> None:
        """Logger=None falls back to stderr."""
        notifier = StateNotifier(logger=None)

        def bad_callback(event: Event) -> None:
            raise RuntimeError("test error")

        notifier.subscribe(EventType.GAME_CHANGED, bad_callback)
        notifier.notify(Event.create(EventType.GAME_CHANGED))

        captured = capsys.readouterr()
        assert "bad_callback failed" in captured.err
        assert "RuntimeError" in captured.err
        assert "Traceback" in captured.err

    def test_logger_optional_parameter_backward_compatible(self) -> None:
        """Logger parameter is optional (backward compatible)."""
        notifier = StateNotifier()  # No logger argument
        assert notifier is not None

        # Normal operation still works
        received: list[Event] = []
        notifier.subscribe(EventType.GAME_CHANGED, received.append)
        notifier.notify(Event.create(EventType.GAME_CHANGED))
        assert len(received) == 1

    def test_logger_failure_falls_back_to_stderr(self, capsys: pytest.CaptureFixture) -> None:
        """If logger raises, falls back to stderr (exception-safe)."""

        def crashing_logger(msg: str) -> None:
            raise RuntimeError("logger crashed")

        notifier = StateNotifier(logger=crashing_logger)

        def bad_callback(event: Event) -> None:
            raise ValueError("callback error")

        notifier.subscribe(EventType.GAME_CHANGED, bad_callback)
        # notify() should not raise (exception-safe)
        notifier.notify(Event.create(EventType.GAME_CHANGED))

        # Fallback to stderr
        captured = capsys.readouterr()
        assert "bad_callback failed" in captured.err
        assert "ValueError" in captured.err
