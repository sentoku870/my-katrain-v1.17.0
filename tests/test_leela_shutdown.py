# tests/test_leela_shutdown.py
"""Tests for Leela engine shutdown (Issues 3 & 4)."""

import logging
import subprocess
from unittest.mock import MagicMock, Mock, patch

from katrain.core.leela.engine import LeelaEngine


def test_shutdown_handles_kill_timeout():
    """Verify shutdown completes even if kill doesn't terminate process."""
    with patch.object(LeelaEngine, "__init__", lambda self, *args: None):
        engine = LeelaEngine(None, None)

    engine._shutdown_event = Mock()
    engine._analysis_thread = None
    engine._lock = MagicMock()
    engine._current_request_id = None

    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.wait.side_effect = [
        subprocess.TimeoutExpired("cmd", 5),  # First wait times out
        subprocess.TimeoutExpired("cmd", 2),  # Wait after kill also times out
    ]
    engine.process = mock_proc

    result = engine.shutdown()  # Should not raise

    assert result is False
    mock_proc.kill.assert_called_once()


def test_shutdown_graceful_success():
    """Verify graceful shutdown returns True."""
    with patch.object(LeelaEngine, "__init__", lambda self, *args: None):
        engine = LeelaEngine(None, None)

    engine._shutdown_event = Mock()
    engine._analysis_thread = None
    engine._lock = MagicMock()
    engine._current_request_id = None

    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.wait.return_value = None  # Exits immediately
    engine.process = mock_proc

    result = engine.shutdown()

    assert result is True
    mock_proc.kill.assert_not_called()


def test_shutdown_joins_thread_after_process_termination():
    """Verify thread join happens after process wait."""
    with patch.object(LeelaEngine, "__init__", lambda self, *args: None):
        engine = LeelaEngine(None, None)

    call_order = []

    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()

    def record_wait(*args, **kwargs):
        call_order.append("proc.wait")

    mock_proc.wait.side_effect = record_wait

    mock_thread = MagicMock()

    def record_join(*args, **kwargs):
        call_order.append("thread.join")

    mock_thread.join.side_effect = record_join
    mock_thread.is_alive.return_value = True

    engine._shutdown_event = Mock()
    engine._analysis_thread = mock_thread
    engine._lock = MagicMock()
    engine._current_request_id = None
    engine.process = mock_proc

    engine.shutdown()

    assert call_order == ["proc.wait", "thread.join"]


def test_shutdown_clears_thread_reference():
    """Verify thread reference is cleared after shutdown."""
    with patch.object(LeelaEngine, "__init__", lambda self, *args: None):
        engine = LeelaEngine(None, None)

    engine._shutdown_event = Mock()
    engine._analysis_thread = MagicMock()
    engine._analysis_thread.is_alive.return_value = False
    engine._lock = MagicMock()
    engine._current_request_id = None
    engine.process = None

    engine.shutdown()

    assert engine._analysis_thread is None


def test_shutdown_logs_if_thread_timeout(caplog):
    """Verify warning logged if thread doesn't stop."""
    with patch.object(LeelaEngine, "__init__", lambda self, *args: None):
        engine = LeelaEngine(None, None)

    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = True  # Still alive after join

    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.wait.return_value = None  # Process exits immediately

    engine._shutdown_event = Mock()
    engine._analysis_thread = mock_thread
    engine._lock = MagicMock()
    engine._current_request_id = None
    engine.process = mock_proc  # Must have process to reach thread join code

    with caplog.at_level(logging.WARNING, logger="katrain.core.leela.engine"):
        engine.shutdown()

    assert "did not stop" in caplog.text
