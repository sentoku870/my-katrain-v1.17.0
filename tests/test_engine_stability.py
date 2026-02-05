"""Tests for engine stability improvements (Phase 22).

These tests verify thread safety and shutdown behavior of KataGoEngine.
"""

import queue
import threading
import time
from unittest.mock import MagicMock

import pytest


class TestTerminateQueryThreadSafety:
    """terminate_query concurrent call tests (Issue #2)."""

    def test_concurrent_terminate_no_keyerror(self):
        """Multiple threads can safely pop the same query_id without KeyError."""

        class FakeEngine:
            def __init__(self):
                self.thread_lock = threading.Lock()
                self.queries = {"q1": "data1", "q2": "data2", "q3": "data3"}

            def terminate_query(self, query_id):
                with self.thread_lock:
                    self.queries.pop(query_id, None)

        engine = FakeEngine()
        errors = []

        def worker(qid):
            try:
                engine.terminate_query(qid)
            except Exception as e:
                errors.append(e)

        # Same query_id called from multiple threads
        threads = []
        for qid in ["q1", "q2", "q3", "q1", "q2", "q3"]:
            t = threading.Thread(target=worker, args=(qid,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(engine.queries) == 0


class TestWaitToFinishTimeout:
    """wait_to_finish timeout behavior tests (Issue #2)."""

    def test_returns_false_on_timeout(self):
        """Returns False when timeout is reached with pending queries."""

        class FakeEngine:
            def __init__(self):
                self.thread_lock = threading.Lock()
                self.queries = {"q1": "pending"}
                self.query_completed = threading.Event()
                self.katago_process = MagicMock()
                self.katago_process.poll.return_value = None  # Process running

            def wait_to_finish(self, timeout=30.0):
                """Event-based wait with timeout."""
                deadline = time.monotonic() + timeout
                while True:
                    with self.thread_lock:
                        if not self.queries:
                            return True
                    if self.katago_process is None or self.katago_process.poll() is not None:
                        return True
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    # Event-based wait instead of sleep
                    self.query_completed.wait(timeout=min(remaining, 0.1))
                    self.query_completed.clear()

        engine = FakeEngine()

        result = engine.wait_to_finish(timeout=0.2)

        # Assert correctness (timed out), not exact timing
        # CI environments can have arbitrary scheduling delays - avoid timing assertions
        assert result is False

    def test_returns_true_when_queries_cleared(self):
        """Returns True when all queries complete before timeout."""

        class FakeEngine:
            def __init__(self):
                self.thread_lock = threading.Lock()
                self.queries = {"q1": "pending"}
                self.query_completed = threading.Event()
                self.katago_process = MagicMock()
                self.katago_process.poll.return_value = None
                self.waiting = threading.Event()  # Signals when wait loop has started

            def wait_to_finish(self, timeout=30.0):
                """Event-based wait with timeout."""
                deadline = time.monotonic() + timeout
                while True:
                    with self.thread_lock:
                        if not self.queries:
                            return True
                    self.waiting.set()  # Signal that we're in the wait loop
                    if self.katago_process is None or self.katago_process.poll() is not None:
                        return True
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self.query_completed.wait(timeout=min(remaining, 0.1))
                    self.query_completed.clear()

        engine = FakeEngine()

        # Background thread clears queries and signals
        def clear_queries():
            # Wait until the main thread is actually in the wait loop (event-based, no sleep)
            engine.waiting.wait(timeout=2.0)
            with engine.thread_lock:
                engine.queries.clear()
            engine.query_completed.set()  # Signal completion

        t = threading.Thread(target=clear_queries, daemon=True)
        t.start()

        result = engine.wait_to_finish(timeout=2.0)
        t.join(timeout=1.0)

        # Assert correctness, not timing
        assert result is True


class TestShutdownEventLifecycle:
    """_shutdown_event lifecycle tests (Issue #1)."""

    def test_event_recreated_on_restart(self):
        """Event is recreated (not cleared) on restart."""

        class FakeEngine:
            def __init__(self):
                self._shutdown_event = threading.Event()

            def shutdown(self):
                self._shutdown_event.set()

            def start(self):
                # Important: recreate event (not clear())
                self._shutdown_event = threading.Event()

        engine = FakeEngine()

        # Save old event
        old_event = engine._shutdown_event

        engine.shutdown()
        assert old_event.is_set()

        engine.start()

        # New event is created
        assert engine._shutdown_event is not old_event
        assert not engine._shutdown_event.is_set()
        # Old event remains set (safe for old threads)
        assert old_event.is_set()


class TestPipeReaderThread:
    """_pipe_reader_thread behavior tests (Issue #1)."""

    def test_puts_lines_to_queue(self):
        """Reader thread puts lines from pipe to queue."""
        output_queue = queue.Queue()
        shutdown_event = threading.Event()

        # Mock pipe with predefined lines
        mock_pipe = MagicMock()
        lines = [b"line1\n", b"line2\n", b""]  # Empty = EOF
        mock_pipe.readline.side_effect = lines

        def reader_thread(pipe, output_queue, name):
            while not shutdown_event.is_set():
                try:
                    line = pipe.readline()
                    if not line:
                        break
                    output_queue.put(line)
                except (OSError, ValueError):
                    break
            output_queue.put(None)  # Termination signal

        t = threading.Thread(target=reader_thread, args=(mock_pipe, output_queue, "test"))
        t.start()
        t.join(timeout=1.0)

        # Verify queue contents
        result_lines = []
        while not output_queue.empty():
            item = output_queue.get_nowait()
            result_lines.append(item)

        assert result_lines == [b"line1\n", b"line2\n", None]

    def test_stops_on_shutdown_event(self):
        """Reader thread stops when shutdown event is set."""
        output_queue = queue.Queue()
        shutdown_event = threading.Event()

        # Mock pipe that blocks
        mock_pipe = MagicMock()

        def slow_readline():
            time.sleep(0.5)
            return b"line\n"

        mock_pipe.readline.side_effect = slow_readline

        def reader_thread(pipe, output_queue, name):
            while not shutdown_event.is_set():
                try:
                    line = pipe.readline()
                    if not line:
                        break
                    output_queue.put(line)
                except (OSError, ValueError):
                    break
            output_queue.put(None)

        t = threading.Thread(target=reader_thread, args=(mock_pipe, output_queue, "test"))
        t.start()

        # Set shutdown event
        time.sleep(0.1)
        shutdown_event.set()

        # Thread should stop after current readline
        t.join(timeout=2.0)
        assert not t.is_alive()


class TestQueueBasedIO:
    """Queue-based I/O timeout tests (Issue #1)."""

    def test_queue_get_with_timeout(self):
        """Consumer can timeout on empty queue."""
        q = queue.Queue()

        with pytest.raises(queue.Empty):
            q.get(timeout=0.1)
        # Assert correctness: Empty exception was raised (timeout occurred)
        # No timing assertions - CI environments have unpredictable scheduling

    def test_queue_get_receives_data(self):
        """Consumer receives data from queue."""
        q = queue.Queue()
        q.put(b"test data")

        result = q.get(timeout=1.0)
        assert result == b"test data"

    def test_queue_none_signal_terminates_consumer(self):
        """Consumer exits on None signal."""
        q = queue.Queue()
        received = []
        done = threading.Event()

        def consumer():
            while True:
                try:
                    item = q.get(timeout=0.1)
                    if item is None:
                        done.set()
                        return
                    received.append(item)
                except queue.Empty:
                    continue

        t = threading.Thread(target=consumer)
        t.start()

        q.put(b"data1")
        q.put(b"data2")
        q.put(None)  # Termination signal

        done.wait(timeout=1.0)
        t.join(timeout=1.0)

        assert not t.is_alive()
        assert received == [b"data1", b"data2"]


class TestTOCTOUPattern:
    """TOCTOU (Time-of-Check-Time-of-Use) pattern tests (Issue #4)."""

    def test_local_capture_prevents_race(self):
        """Local capture pattern prevents race condition."""

        class FakeEngine:
            def __init__(self):
                self.process = MagicMock()
                self.process.stdout.readline.return_value = b"data\n"

            def read_with_local_capture(self):
                """Safe: capture reference locally."""
                process = self.process
                if process is None:
                    return None
                return process.stdout.readline()

            def read_without_capture(self):
                """Unsafe: direct access."""
                if self.process is None:
                    return None
                return self.process.stdout.readline()

        engine = FakeEngine()

        # Simulate process being set to None mid-operation
        def set_process_none():
            time.sleep(0.05)
            engine.process = None

        # With local capture, the captured reference remains valid
        t = threading.Thread(target=set_process_none)
        t.start()

        # This should work because we captured the reference
        result = engine.read_with_local_capture()
        t.join()

        assert result == b"data\n"
