# tests/test_engine_coverage.py
"""Tests for KataGoEngine coverage (Phase 67).

These tests verify engine startup, shutdown, and query management behavior
without requiring real engine binaries by using FakePopen.
"""

import queue
import threading

import pytest
from unittest.mock import patch

from tests.fakes import FakePopen, MinimalKatrain


# Patch target: engine.py uses "import subprocess" then "subprocess.Popen"
POPEN_PATCH_TARGET = "katrain.core.engine.subprocess.Popen"


def make_engine_config():
    """Create a minimal config dict for KataGoEngine."""
    return {
        "katago": "katago",
        "model": "",
        "config": "",
        "altcommand": "echo test",  # Use altcommand to skip finding real binary
        "threads": 1,
        "max_visits": 1,
        "max_time": 1.0,
        "wide_root_noise": 0.0,
        "allow_recovery": False,
    }


class TestEngineStartup:
    """Test KataGoEngine startup behavior."""

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_start_creates_process(self):
        """Engine.start() should create a subprocess."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        engine.start()

        assert engine.katago_process is not None
        # Trigger graceful exit before shutdown
        engine.katago_process.simulate_graceful_exit()
        engine.shutdown()

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_start_creates_threads(self):
        """Engine.start() should create reader/writer threads."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        engine.start()

        assert engine.stdout_reader_thread is not None
        assert engine.stderr_reader_thread is not None
        # Trigger graceful exit before shutdown
        engine.katago_process.simulate_graceful_exit()
        engine.shutdown()

    @patch(POPEN_PATCH_TARGET)
    def test_start_handles_popen_failure(self, mock_popen):
        """Engine.start() should handle Popen exceptions."""
        from katrain.core.engine import KataGoEngine

        mock_popen.side_effect = FileNotFoundError("katago not found")

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        engine.start()

        # Should not crash, process should be None
        assert engine.katago_process is None


class TestEngineShutdown:
    """Test KataGoEngine shutdown behavior."""

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_shutdown_terminates_process(self):
        """shutdown() should terminate the process."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        engine.start()

        # Simulate graceful exit when terminate is called
        def on_terminate():
            engine.katago_process.simulate_graceful_exit()

        engine.katago_process._terminate_event = threading.Event()
        original_terminate = engine.katago_process.terminate

        def patched_terminate():
            original_terminate()
            on_terminate()

        engine.katago_process.terminate = patched_terminate

        engine.shutdown()

        assert engine.katago_process is None

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_shutdown_force_kills_on_timeout(self):
        """shutdown() should force kill if terminate times out."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        engine.start()

        # Don't set terminate_event - process won't exit gracefully
        # FakePopen.wait() will raise TimeoutExpired

        engine.shutdown()

        # Should still complete (force kill)
        assert engine.katago_process is None

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_shutdown_clears_process_reference(self):
        """shutdown() should set katago_process to None."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        engine.start()
        engine.katago_process.simulate_graceful_exit()
        engine.shutdown()

        assert engine.katago_process is None

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_shutdown_without_process(self):
        """shutdown() should handle case where process is None."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        # Don't start - process is None
        engine.shutdown()

        # Should complete without error
        assert engine.katago_process is None


class TestEngineQueryManagement:
    """Test query registration and termination."""

    def test_terminate_query_thread_safe(self):
        """terminate_query() should be thread-safe."""
        # Already covered in test_engine_stability.py
        pass

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_wait_to_finish_returns_true_when_empty(self):
        """wait_to_finish() should return True when no queries."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        engine.start()
        engine.queries = {}  # No queries

        result = engine.wait_to_finish(timeout=0.5)

        assert result is True
        engine.katago_process.simulate_graceful_exit()
        engine.shutdown()


class TestEngineDeadlockPrevention:
    """
    Test deadlock prevention mechanisms.

    Note: These tests verify shutdown completes without blocking.
    Hang detection relies on CI job timeout (typically 10-30 min).
    If a test hangs, it indicates a deadlock bug.
    """

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_shutdown_completes_with_full_queue(self):
        """shutdown() should complete even if write_queue is full."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        engine.start()

        # Fill the queue to simulate blocking scenario
        for _ in range(1000):
            try:
                engine.write_queue.put_nowait("dummy")
            except queue.Full:
                break

        engine.katago_process.simulate_graceful_exit()

        # Should complete without hanging
        # Note: We rely on CI job timeout for hang detection.
        # The test itself should complete quickly if not blocked.
        engine.shutdown()

        # Assert correctness: shutdown completed and cleared reference
        assert engine.katago_process is None

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_shutdown_sets_event_first(self):
        """shutdown() should set _shutdown_event before other operations."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        engine.start()

        assert not engine._shutdown_event.is_set()

        engine.katago_process.simulate_graceful_exit()
        engine.shutdown()

        # Event should be set after shutdown
        assert engine._shutdown_event.is_set()


class TestHelperMethods:
    """Test shutdown helper methods."""

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_safe_queue_put_handles_full_queue(self):
        """_safe_queue_put should handle full queue without blocking indefinitely."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())

        # Create a small bounded queue
        small_queue = queue.Queue(maxsize=1)
        small_queue.put("blocking_item")

        # Should not block indefinitely
        engine._safe_queue_put(small_queue, "test_item", "test context")

        # No assertion needed - test passes if it doesn't hang

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_safe_terminate_handles_oserror(self):
        """_safe_terminate should handle OSError gracefully."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        engine.start()

        # Make terminate raise OSError
        def raise_oserror():
            raise OSError("Permission denied")

        engine.katago_process.terminate = raise_oserror

        # Should not raise
        engine._safe_terminate(engine.katago_process)

        # Cleanup
        engine.katago_process.simulate_graceful_exit()
        engine.katago_process = None

    @patch(POPEN_PATCH_TARGET, FakePopen)
    def test_safe_close_pipes_handles_broken_pipe(self):
        """_safe_close_pipes should handle BrokenPipeError gracefully."""
        from katrain.core.engine import KataGoEngine

        katrain = MinimalKatrain()
        engine = KataGoEngine(katrain, make_engine_config())
        engine.start()

        # Make stdin.close() raise BrokenPipeError
        original_close = engine.katago_process.stdin.close

        def raise_broken_pipe():
            raise BrokenPipeError("Pipe closed")

        engine.katago_process.stdin.close = raise_broken_pipe

        # Should not raise
        engine._safe_close_pipes(engine.katago_process)

        # Cleanup
        engine.katago_process.stdin.close = original_close
        engine.katago_process.simulate_graceful_exit()
        engine.katago_process = None
