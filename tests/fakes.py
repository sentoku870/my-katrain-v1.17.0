# tests/fakes.py
"""
Fake subprocess classes for testing engine code without real binaries.

Usage:
    from tests.fakes import FakePopen, FakePipe, MinimalKatrain
"""

import queue
import subprocess
import threading
from typing import Optional, Union


class FakePipe:
    """
    Mock pipe for subprocess stdin/stdout/stderr.

    Behavior:
    - readline() returns bytes (for KataGo) or str (for Leela)
    - readline() NEVER returns None - always bytes/str
    - EOF is represented as b"" (bytes mode) or "" (text mode)
    - write() accepts bytes/str and returns length
    - flush() is a no-op
    - close() sets closed=True and signals EOF
    """

    def __init__(self, text_mode: bool = False):
        """
        Args:
            text_mode: If True, use str; if False, use bytes (like real Popen)
        """
        self.text_mode = text_mode
        self.closed = False
        self._buffer: queue.Queue = queue.Queue()
        self._eof = threading.Event()

    def write(self, data: Union[bytes, str]) -> int:
        """Write data to pipe. Raises BrokenPipeError if closed."""
        if self.closed:
            raise BrokenPipeError("Pipe closed")
        return len(data)

    def flush(self) -> None:
        """Flush is a no-op for fake pipes."""
        pass

    def readline(self) -> Union[bytes, str]:
        """
        Return next line or EOF marker.

        NEVER returns None - always returns appropriate empty value for EOF.
        Blocks until data available, EOF signaled, or pipe closed.
        """
        if self._eof.is_set() or self.closed:
            return "" if self.text_mode else b""

        try:
            return self._buffer.get(timeout=0.1)
        except queue.Empty:
            if self._eof.is_set() or self.closed:
                return "" if self.text_mode else b""
            # Return empty to allow loop to check shutdown event
            # Real pipes block, but for testing we use short timeout
            return "" if self.text_mode else b""

    def close(self) -> None:
        """Close the pipe and signal EOF."""
        self.closed = True
        self._eof.set()

    # Test helper methods
    def feed(self, data: Union[bytes, str]) -> None:
        """Test helper: feed data to the pipe for readline() to return."""
        self._buffer.put(data)

    def signal_eof(self) -> None:
        """Test helper: signal end of stream."""
        self._eof.set()


class FakePopen:
    """
    Mock subprocess.Popen for engine testing.

    Simulates process lifecycle without spawning real processes.
    """

    def __init__(self, args, **kwargs):
        self.args = args
        self.returncode: Optional[int] = None
        self._alive = True

        # Determine text mode from kwargs (matches real Popen behavior)
        text_mode = kwargs.get("text", False) or kwargs.get(
            "universal_newlines", False
        )

        # Fake pipes with correct mode
        self.stdin = FakePipe(text_mode=text_mode)
        self.stdout = FakePipe(text_mode=text_mode)
        self.stderr = FakePipe(text_mode=text_mode)

        # Control signals for test coordination
        self._terminate_event = threading.Event()
        self._kill_event = threading.Event()

    def poll(self) -> Optional[int]:
        """Return None if alive, returncode if dead."""
        if self._alive:
            return None
        return self.returncode

    def terminate(self) -> None:
        """Request graceful termination (sets event for wait() to detect)."""
        self._terminate_event.set()

    def kill(self) -> None:
        """Force immediate termination - always succeeds."""
        self._kill_event.set()
        self._alive = False
        self.returncode = -9
        # Signal EOF on pipes
        self.stdout.signal_eof()
        self.stderr.signal_eof()

    def wait(self, timeout: Optional[float] = None) -> int:
        """
        Wait for process to exit.

        Raises TimeoutExpired if terminate_event not set within timeout.
        """
        if not self._alive:
            return self.returncode

        if self._terminate_event.wait(timeout=timeout):
            self._alive = False
            self.returncode = 0
            # Signal EOF on pipes
            self.stdout.signal_eof()
            self.stderr.signal_eof()
            return 0

        if not self._alive:
            return self.returncode

        raise subprocess.TimeoutExpired(self.args, timeout)

    # Test helper methods
    def simulate_graceful_exit(self, exit_code: int = 0) -> None:
        """Test helper: simulate process exiting gracefully."""
        self._terminate_event.set()
        self._alive = False
        self.returncode = exit_code
        self.stdout.signal_eof()
        self.stderr.signal_eof()

    def simulate_crash(self, exit_code: int = 1) -> None:
        """Test helper: simulate process crash."""
        self._alive = False
        self.returncode = exit_code
        self.stdout.signal_eof()
        self.stderr.signal_eof()


class MinimalKatrain:
    """
    Minimal mock katrain object for engine testing.

    Provides config() method that returns values from a predefined dict,
    avoiding MagicMock's fragile single-return-value behavior.
    """

    def __init__(self, overrides: Optional[dict] = None):
        """
        Args:
            overrides: dict of config keys to override (e.g., {"engine/katago": "/path/to/katago"})
        """
        self._configs = {
            "engine/katago": "katago",
            "engine/model": "",
            "engine/config": "",
            "engine/threads": 1,
            "engine/max_visits": 1,
            "engine/max_time": 1.0,
            "engine/wide_root_noise": 0.0,
        }
        if overrides:
            self._configs.update(overrides)

    def log(self, msg, level=None):
        """Suppress logs during test."""
        pass

    def config(self, key, default=None):
        """Return config value for key, or default if not found."""
        return self._configs.get(key, default)
