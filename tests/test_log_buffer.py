"""Tests for katrain.core.log_buffer module.

Phase 29: Diagnostics + Bug Report Bundle.
"""

from concurrent.futures import ThreadPoolExecutor

from katrain.core.constants import OUTPUT_ERROR, OUTPUT_INFO
from katrain.core.log_buffer import LogBuffer


class TestLogBuffer:
    """Tests for LogBuffer class."""

    def test_append_and_get(self) -> None:
        """Basic append and retrieval works."""
        buffer = LogBuffer(timestamp_fn=lambda: "2026-01-17T12:00:00")
        buffer.append("test message", OUTPUT_INFO)
        lines = buffer.get_lines()

        assert len(lines) == 1
        assert lines[0] == "[2026-01-17T12:00:00] [INFO] test message"

    def test_error_level_formatting(self) -> None:
        """ERROR level is correctly formatted."""
        buffer = LogBuffer(timestamp_fn=lambda: "2026-01-17T12:00:00")
        buffer.append("error message", OUTPUT_ERROR)
        lines = buffer.get_lines()

        assert len(lines) == 1
        assert "[ERROR]" in lines[0]
        assert "error message" in lines[0]

    def test_info_level_formatting(self) -> None:
        """INFO level is correctly formatted."""
        buffer = LogBuffer(timestamp_fn=lambda: "2026-01-17T12:00:00")
        buffer.append("info message", OUTPUT_INFO)
        lines = buffer.get_lines()

        assert "[INFO]" in lines[0]

    def test_max_lines_enforced(self) -> None:
        """Buffer respects MAX_LINES limit."""
        buffer = LogBuffer(timestamp_fn=lambda: "2026-01-17T12:00:00")

        # Add more than MAX_LINES entries
        for i in range(LogBuffer.MAX_LINES + 100):
            buffer.append(f"message {i}", OUTPUT_INFO)

        lines = buffer.get_lines()
        assert len(lines) == LogBuffer.MAX_LINES

        # Should contain the latest messages (FIFO behavior with max size)
        assert "message 100" in lines[0]
        assert f"message {LogBuffer.MAX_LINES + 99}" in lines[-1]

    def test_long_line_truncation(self) -> None:
        """Lines exceeding MAX_CHARS_PER_LINE are truncated."""
        buffer = LogBuffer(timestamp_fn=lambda: "2026-01-17T12:00:00")
        long_message = "x" * (LogBuffer.MAX_CHARS_PER_LINE + 500)
        buffer.append(long_message, OUTPUT_INFO)

        lines = buffer.get_lines()
        assert len(lines) == 1
        assert "...[truncated]" in lines[0]
        # The message part should be truncated to MAX_CHARS_PER_LINE
        # Total line includes timestamp and level prefix

    def test_timestamp_injection(self) -> None:
        """Timestamp function can be injected for deterministic testing."""
        fixed_time = "2026-01-17T14:30:00"
        buffer = LogBuffer(timestamp_fn=lambda: fixed_time)
        buffer.append("test", OUTPUT_INFO)

        lines = buffer.get_lines()
        assert fixed_time in lines[0]

    def test_thread_safety(self) -> None:
        """Concurrent appends don't cause data corruption."""
        buffer = LogBuffer(timestamp_fn=lambda: "2026-01-17T12:00:00")
        num_threads = 10
        messages_per_thread = 50

        def append_messages(thread_id: int) -> None:
            for i in range(messages_per_thread):
                buffer.append(f"thread {thread_id} message {i}", OUTPUT_INFO)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(append_messages, i) for i in range(num_threads)]
            for f in futures:
                f.result()

        lines = buffer.get_lines()
        # All messages should be captured (within MAX_LINES limit)
        expected = min(num_threads * messages_per_thread, LogBuffer.MAX_LINES)
        assert len(lines) == expected

    def test_clear(self) -> None:
        """Clear removes all entries."""
        buffer = LogBuffer(timestamp_fn=lambda: "2026-01-17T12:00:00")
        buffer.append("message 1", OUTPUT_INFO)
        buffer.append("message 2", OUTPUT_INFO)

        assert len(buffer.get_lines()) == 2

        buffer.clear()
        assert len(buffer.get_lines()) == 0

    def test_empty_buffer(self) -> None:
        """Empty buffer returns empty list."""
        buffer = LogBuffer()
        assert buffer.get_lines() == []

    def test_unicode_preserved(self) -> None:
        """Unicode messages are handled correctly."""
        buffer = LogBuffer(timestamp_fn=lambda: "2026-01-17T12:00:00")
        buffer.append("囲碁の解析が完了しました", OUTPUT_INFO)

        lines = buffer.get_lines()
        assert "囲碁の解析が完了しました" in lines[0]

    def test_multiple_levels(self) -> None:
        """Multiple log levels are correctly formatted."""
        buffer = LogBuffer(timestamp_fn=lambda: "2026-01-17T12:00:00")
        buffer.append("info", OUTPUT_INFO)
        buffer.append("error", OUTPUT_ERROR)
        buffer.append("info again", OUTPUT_INFO)

        lines = buffer.get_lines()
        assert len(lines) == 3
        assert "[INFO]" in lines[0]
        assert "[ERROR]" in lines[1]
        assert "[INFO]" in lines[2]


class TestLogBufferConstants:
    """Verify LogBuffer constants are reasonable."""

    def test_max_lines_reasonable(self) -> None:
        """MAX_LINES is within expected range."""
        assert 100 <= LogBuffer.MAX_LINES <= 1000

    def test_max_chars_reasonable(self) -> None:
        """MAX_CHARS_PER_LINE is within expected range."""
        assert 500 <= LogBuffer.MAX_CHARS_PER_LINE <= 5000
