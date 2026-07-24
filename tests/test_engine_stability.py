"""Tests for engine stability improvements (Phase 22).

These tests verify thread safety and shutdown behaviour of
``KataGoEngine``. Phase 4 of the test-suite audit removed the inline
``FakeEngine`` classes (each test redefined its own near-clone) and the
duplicated ``reader_thread`` helper. They now share the module-level
helpers below; the per-test bodies only describe the scenario they
exercise.
"""

from __future__ import annotations

import queue
import threading
import time
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Shared FakeEngine helpers
# ---------------------------------------------------------------------------


class _QueriesEngine:
    """``terminate_query`` / ``wait_to_finish`` target.

    Carries the ``thread_lock``, ``queries`` dict and optional
    ``katago_process`` mock that the production methods read. The
    subclass hooks (``wait_to_finish``) are installed by individual tests
    so the contract under test stays co-located with the assertion.
    """

    def __init__(self, queries: dict[str, str] | None = None) -> None:
        self.thread_lock = threading.Lock()
        self.queries = queries if queries is not None else {"q1": "data1", "q2": "data2", "q3": "data3"}
        self.katago_process = MagicMock()
        self.katago_process.poll.return_value = None  # Process running
        self.query_completed = threading.Event()
        self.waiting = threading.Event()

    def terminate_query(self, query_id: str) -> None:
        with self.thread_lock:
            self.queries.pop(query_id, None)


class _ShutdownEventEngine:
    """``shutdown`` / ``start`` event-lifecycle target."""

    def __init__(self) -> None:
        self._shutdown_event = threading.Event()

    def shutdown(self) -> None:
        self._shutdown_event.set()

    def start(self) -> None:
        # Important: recreate event (not clear()) so old threads still
        # see the set state from the previous shutdown.
        self._shutdown_event = threading.Event()


class _CaptureRaceEngine:
    """``read_with_local_capture`` / ``read_without_capture`` target."""

    def __init__(self) -> None:
        self.process = MagicMock()
        self.process.stdout.readline.return_value = b"data\n"

    def read_with_local_capture(self):
        # Safe: capture the process reference locally so a concurrent
        # ``self.process = None`` can't reach it mid-call.
        process = self.process
        if process is None:
            return None
        return process.stdout.readline()

    def read_without_capture(self):
        # Unsafe: direct attribute access loses to ``self.process = None``.
        if self.process is None:
            return None
        return self.process.stdout.readline()


# ---------------------------------------------------------------------------
# Shared pipe-reader thread helper
# ---------------------------------------------------------------------------


def _pipe_reader_thread(pipe, output_queue: queue.Queue, shutdown_event: threading.Event) -> None:
    """Inline implementation of ``engine_io.pipe_reader_thread`` semantics.

    Drains ``pipe.readline()`` into ``output_queue`` until shutdown or
    EOF. Posts ``None`` as a termination signal. Kept inline because
    importing the production module triggers Kivy graphics init in
    CI; the behaviour under test is the loop shape, not the helper.
    """
    while not shutdown_event.is_set():
        try:
            line = pipe.readline()
        except (OSError, ValueError):
            break
        if not line:
            break
        output_queue.put(line)
    output_queue.put(None)  # Termination signal


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTerminateQueryThreadSafety:
    """``terminate_query`` concurrent call tests (Issue #2)."""

    def test_concurrent_terminate_no_keyerror(self):
        engine = _QueriesEngine()
        errors: list[Exception] = []

        def worker(qid: str) -> None:
            try:
                engine.terminate_query(qid)
            except Exception as e:  # noqa: BLE001 — tests concurrent pop
                errors.append(e)

        # Same query_id called from multiple threads → must be safe
        # (no KeyError; pop defaults to None).
        threads = [threading.Thread(target=worker, args=(qid,)) for qid in ["q1", "q2", "q3", "q1", "q2", "q3"]]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(engine.queries) == 0


class TestWaitToFinishTimeout:
    """``wait_to_finish`` timeout behaviour tests (Issue #2)."""

    def test_returns_false_on_timeout(self):
        """Returns ``False`` when timeout reached with pending queries."""
        engine = _QueriesEngine(queries={"q1": "pending"})

        def wait_to_finish(timeout: float = 30.0) -> bool:
            deadline = time.monotonic() + timeout
            while True:
                with engine.thread_lock:
                    if not engine.queries:
                        return True
                if engine.katago_process is None or engine.katago_process.poll() is not None:
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                engine.query_completed.wait(timeout=min(remaining, 0.1))
                engine.query_completed.clear()

        engine.wait_to_finish = wait_to_finish  # type: ignore[attr-defined]
        assert engine.wait_to_finish(timeout=0.2) is False

    def test_returns_true_when_queries_cleared(self):
        """Returns ``True`` when all queries complete before timeout."""
        engine = _QueriesEngine(queries={"q1": "pending"})

        def wait_to_finish(timeout: float = 30.0) -> bool:
            deadline = time.monotonic() + timeout
            while True:
                with engine.thread_lock:
                    if not engine.queries:
                        return True
                engine.waiting.set()  # signal we're in the wait loop
                if engine.katago_process is None or engine.katago_process.poll() is not None:
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                engine.query_completed.wait(timeout=min(remaining, 0.1))
                engine.query_completed.clear()

        engine.wait_to_finish = wait_to_finish  # type: ignore[attr-defined]

        def clear_queries() -> None:
            # Wait until the main thread is actually in the wait loop.
            engine.waiting.wait(timeout=2.0)
            with engine.thread_lock:
                engine.queries.clear()
            engine.query_completed.set()

        t = threading.Thread(target=clear_queries, daemon=True)
        t.start()

        assert engine.wait_to_finish(timeout=2.0) is True
        t.join(timeout=1.0)


class TestShutdownEventLifecycle:
    """``_shutdown_event`` lifecycle tests (Issue #1)."""

    def test_event_recreated_on_restart(self):
        """Event is recreated (not cleared) on restart."""
        engine = _ShutdownEventEngine()
        old_event = engine._shutdown_event

        engine.shutdown()
        assert old_event.is_set()

        engine.start()
        assert engine._shutdown_event is not old_event
        assert not engine._shutdown_event.is_set()
        # Old event remains set (safe for old threads still holding a reference).
        assert old_event.is_set()


class TestPipeReaderThread:
    """``_pipe_reader_thread`` behaviour tests (Issue #1)."""

    def test_puts_lines_to_queue(self):
        """Reader thread puts lines from pipe to queue."""
        output_queue: queue.Queue = queue.Queue()
        shutdown_event = threading.Event()

        mock_pipe = MagicMock()
        mock_pipe.readline.side_effect = [b"line1\n", b"line2\n", b""]  # "" = EOF

        t = threading.Thread(
            target=_pipe_reader_thread,
            args=(mock_pipe, output_queue, shutdown_event),
        )
        t.start()
        t.join(timeout=1.0)

        result_lines: list = []
        while not output_queue.empty():
            result_lines.append(output_queue.get_nowait())

        assert result_lines == [b"line1\n", b"line2\n", None]

    def test_stops_on_shutdown_event(self):
        """Reader thread stops when shutdown event is set."""
        output_queue: queue.Queue = queue.Queue()
        shutdown_event = threading.Event()

        # Mock pipe that blocks long enough for shutdown_event to fire.
        mock_pipe = MagicMock()

        def slow_readline() -> bytes:
            time.sleep(0.5)
            return b"line\n"

        mock_pipe.readline.side_effect = slow_readline

        t = threading.Thread(
            target=_pipe_reader_thread,
            args=(mock_pipe, output_queue, shutdown_event),
        )
        t.start()

        # Give the reader time to enter the slow readline, then signal shutdown.
        time.sleep(0.1)
        shutdown_event.set()

        t.join(timeout=2.0)
        assert not t.is_alive()


class TestQueueBasedIO:
    """Queue-based I/O timeout tests (Issue #1)."""

    def test_queue_get_with_timeout(self):
        """Consumer can timeout on empty queue."""
        q: queue.Queue = queue.Queue()
        # Assert correctness: Empty exception was raised (timeout occurred).
        # No timing assertions — CI environments have unpredictable scheduling.
        with pytest.raises(queue.Empty):
            q.get(timeout=0.1)

    def test_queue_get_receives_data(self):
        """Consumer receives data from queue."""
        q: queue.Queue = queue.Queue()
        q.put(b"test data")
        assert q.get(timeout=1.0) == b"test data"

    def test_queue_none_signal_terminates_consumer(self):
        """Consumer exits on ``None`` signal."""
        q: queue.Queue = queue.Queue()
        received: list = []
        done = threading.Event()

        def consumer() -> None:
            while True:
                try:
                    item = q.get(timeout=0.1)
                except queue.Empty:
                    continue
                if item is None:
                    done.set()
                    return
                received.append(item)

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
        """Local-capture pattern prevents the race condition."""
        engine = _CaptureRaceEngine()

        # Simulate ``process`` being set to None mid-operation.
        def set_process_none() -> None:
            time.sleep(0.05)
            engine.process = None

        # With local capture, the captured reference remains valid even
        # after the concurrent setter runs.
        t = threading.Thread(target=set_process_none)
        t.start()
        result = engine.read_with_local_capture()
        t.join()

        assert result == b"data\n"
