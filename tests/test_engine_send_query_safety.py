"""Tests for send_query() safety mechanisms."""
import queue
import threading
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def minimal_engine():
    """Create a minimal engine instance for testing send_query safety."""
    from katrain.core.engine import KataGoEngine, MAX_PENDING_QUERIES

    # Use object.__new__ to create instance without __init__
    engine = object.__new__(KataGoEngine)

    # Set up required attributes manually
    engine._pending_query_count = 0
    engine._pending_query_lock = threading.Lock()
    engine.katago_process = MagicMock()
    engine.katago_process.poll.return_value = None  # Process alive
    engine.write_queue = queue.Queue()
    engine.katrain = MagicMock()
    engine.thread_lock = threading.Lock()

    return engine, MAX_PENDING_QUERIES


def mock_schedule_once(callback, delay=0):
    """Mock Clock.schedule_once that executes callback immediately."""
    callback(0)  # Pass 0 as dt argument


class TestSendQuerySafety:
    """Test send_query() safety mechanisms."""

    def test_rejects_when_engine_dead(self, minimal_engine):
        """Query is rejected when engine process is dead."""
        engine, _ = minimal_engine
        engine.katago_process.poll.return_value = 1  # Process exited

        error_received = []

        # Patch sys.modules to make Kivy Clock execute callback immediately
        mock_clock = MagicMock()
        mock_clock.schedule_once = mock_schedule_once
        mock_clock_module = MagicMock()
        mock_clock_module.Clock = mock_clock
        with patch.dict('sys.modules', {'kivy.clock': mock_clock_module}):
            result = engine.send_query(
                {"id": "test"},
                callback=MagicMock(),
                error_callback=lambda e: error_received.append(e)
            )

        assert result is False
        assert len(error_received) == 1
        assert "not alive" in error_received[0]["error"].lower()

    def test_rejects_when_pending_limit_exceeded(self, minimal_engine):
        """Query is rejected when pending limit exceeded."""
        engine, MAX_PENDING = minimal_engine
        engine._pending_query_count = MAX_PENDING

        error_received = []

        # Patch sys.modules to make Kivy Clock execute callback immediately
        mock_clock = MagicMock()
        mock_clock.schedule_once = mock_schedule_once
        mock_clock_module = MagicMock()
        mock_clock_module.Clock = mock_clock
        with patch.dict('sys.modules', {'kivy.clock': mock_clock_module}):
            result = engine.send_query(
                {"id": "overflow"},
                callback=MagicMock(),
                error_callback=lambda e: error_received.append(e)
            )

        assert result is False
        assert len(error_received) == 1
        assert "pending" in error_received[0]["error"].lower()
        # Counter should not increment
        assert engine._pending_query_count == MAX_PENDING

    def test_increments_count_on_success(self, minimal_engine):
        """Pending count increments when query is accepted."""
        engine, _ = minimal_engine
        initial_count = engine._pending_query_count

        result = engine.send_query(
            {"id": "test"},
            callback=MagicMock(),
            error_callback=None
        )

        assert result is True
        assert engine._pending_query_count == initial_count + 1
        # Queue should have item
        assert not engine.write_queue.empty()

    def test_accepts_query_at_limit_minus_one(self, minimal_engine):
        """Query accepted when exactly at limit - 1."""
        engine, MAX_PENDING = minimal_engine
        engine._pending_query_count = MAX_PENDING - 1

        result = engine.send_query(
            {"id": "test"},
            callback=MagicMock(),
            error_callback=None
        )

        assert result is True
        assert engine._pending_query_count == MAX_PENDING


class TestInvokeErrorCallback:
    """Test _invoke_error_callback headless handling (v5: ImportError only fallback)."""

    def test_sync_fallback_when_kivy_not_loaded(self, minimal_engine):
        """Falls back to sync call when Kivy is not loaded in sys.modules."""
        engine, _ = minimal_engine

        callback_received = []

        # Simulate Kivy not loaded by removing it from sys.modules
        import sys
        original_kivy_clock = sys.modules.get('kivy.clock')
        try:
            # Remove kivy.clock from sys.modules if present
            if 'kivy.clock' in sys.modules:
                del sys.modules['kivy.clock']

            engine._invoke_error_callback(
                lambda msg: callback_received.append(msg),
                {"error": "test"}
            )
        finally:
            # Restore original state
            if original_kivy_clock is not None:
                sys.modules['kivy.clock'] = original_kivy_clock

        assert len(callback_received) == 1
        assert callback_received[0]["error"] == "test"

    def test_none_callback_does_nothing(self, minimal_engine):
        """None callback is handled gracefully."""
        engine, _ = minimal_engine

        # Should not raise
        engine._invoke_error_callback(None, {"error": "test"})

    def test_schedules_on_kivy_clock_when_available(self, minimal_engine):
        """When Kivy is available, callback is scheduled via Clock."""
        engine, _ = minimal_engine

        callback_received = []
        mock_clock = MagicMock()
        mock_clock_module = MagicMock()
        mock_clock_module.Clock = mock_clock

        # Patch sys.modules to make it look like Kivy is loaded
        with patch.dict('sys.modules', {'kivy.clock': mock_clock_module}):
            engine._invoke_error_callback(
                lambda msg: callback_received.append(msg),
                {"error": "test"}
            )

        # Should have called schedule_once
        mock_clock.schedule_once.assert_called_once()


class TestDecrementPendingCount:
    """Test _decrement_pending_count method."""

    def test_decrements_count(self, minimal_engine):
        """Decrement reduces count by 1."""
        engine, _ = minimal_engine
        engine._pending_query_count = 5

        engine._decrement_pending_count()

        assert engine._pending_query_count == 4

    def test_does_not_go_negative(self, minimal_engine):
        """Decrement does not go below 0."""
        engine, _ = minimal_engine
        engine._pending_query_count = 0

        engine._decrement_pending_count()

        assert engine._pending_query_count == 0

    def test_thread_safe_decrement(self, minimal_engine):
        """Multiple threads decrementing safely."""
        engine, _ = minimal_engine
        engine._pending_query_count = 100

        threads = []
        for _ in range(50):
            t = threading.Thread(target=engine._decrement_pending_count)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert engine._pending_query_count == 50
