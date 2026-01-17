"""Thread-safe log buffer for diagnostics export.

Phase 29: Diagnostics + Bug Report Bundle.

This module provides a LogBuffer class that captures log messages
for inclusion in diagnostic exports. It is intentionally minimal
to avoid circular import issues.
"""

from collections import deque
from threading import Lock
from typing import Callable, Optional

from katrain.core.constants import OUTPUT_ERROR


def _default_timestamp() -> str:
    """Get current timestamp in ISO format (testable via injection)."""
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


class LogBuffer:
    """Thread-safe circular buffer for log messages.

    Stores formatted log entries with timestamps and levels.
    Designed to be embedded in BaseKaTrain for diagnostics export.
    """

    MAX_LINES = 500
    MAX_CHARS_PER_LINE = 2000

    def __init__(self, timestamp_fn: Optional[Callable[[], str]] = None) -> None:
        """Initialize LogBuffer.

        Args:
            timestamp_fn: Optional function returning timestamp string.
                          Defaults to ISO format datetime. Inject for testing.
        """
        self._buffer: deque[str] = deque(maxlen=self.MAX_LINES)
        self._lock = Lock()
        self._timestamp_fn = timestamp_fn or _default_timestamp

    def append(self, message: str, level: int) -> None:
        """Add a log entry to the buffer.

        Args:
            message: Log message text.
            level: Log level (OUTPUT_INFO, OUTPUT_ERROR, etc.).
        """
        timestamp = self._timestamp_fn()
        level_str = "ERROR" if level == OUTPUT_ERROR else "INFO"

        # Truncate overly long messages
        if len(message) > self.MAX_CHARS_PER_LINE:
            message = message[: self.MAX_CHARS_PER_LINE] + "...[truncated]"

        entry = f"[{timestamp}] [{level_str}] {message}"
        with self._lock:
            self._buffer.append(entry)

    def get_lines(self) -> list[str]:
        """Get all buffered log lines.

        Returns:
            List of formatted log entries (oldest first).
        """
        with self._lock:
            return list(self._buffer)

    def clear(self) -> None:
        """Clear all buffered log lines."""
        with self._lock:
            self._buffer.clear()
