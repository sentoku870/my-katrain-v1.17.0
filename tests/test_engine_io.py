"""Unit tests for ``katrain.core.engine_io`` (Phase 282-P1B).

The I/O thread helpers run as daemon threads inside the live KataGo
engine; mocking them requires a fully-constructed ``KataGoEngine``
which is not viable in a pure unit test. We focus here on the pure
helper ``_ensure_str`` plus a static structural check that the public
thread functions exist and have the expected signatures.

Coverage targets:
- ``_ensure_str``: bytes / str / None normalization
"""

from __future__ import annotations

import inspect

from katrain.core.engine_io import (
    _ensure_str,
    analysis_read_thread,
    pipe_reader_thread,
    read_stderr_thread,
    write_stdin_thread,
)

# =============================================================================
# _ensure_str
# =============================================================================


class TestEnsureStr:
    def test_none_returns_empty_string(self):
        assert _ensure_str(None) == ""

    def test_str_returned_as_is(self):
        assert _ensure_str("hello") == "hello"

    def test_empty_string_returned(self):
        assert _ensure_str("") == ""

    def test_bytes_decoded_as_utf8(self):
        assert _ensure_str(b"hello") == "hello"

    def test_bytes_with_utf8_chars(self):
        assert _ensure_str("日本語".encode()) == "日本語"

    def test_bytes_with_invalid_utf8_replaced(self):
        """``errors='replace'`` is intentional: thread must not crash on
        arbitrary engine output bytes."""
        invalid = b"bad\xffbyte"
        result = _ensure_str(invalid)
        assert isinstance(result, str)
        assert "bad" in result
        assert "byte" in result

    def test_non_string_types_via_str_fallback(self):
        # ints, floats, etc. are normalized through str()
        assert _ensure_str(42) == "42"
        assert _ensure_str(3.14) == "3.14"


# =============================================================================
# Structural regression checks
# =============================================================================


class TestThreadFunctionSignatures:
    """Lock in the public API of the I/O thread helpers.

    Phase 158+ extracted these from KataGoEngine into standalone
    module-level functions. Subclasses and tests may rely on these
    specific signatures; renaming or changing parameters would break
    them silently without these guards.
    """

    def test_pipe_reader_thread_takes_widget_pipe_queue_name(self):
        sig = inspect.signature(pipe_reader_thread)
        params = list(sig.parameters)
        assert params == ["widget", "pipe", "output_queue", "name"]

    def test_read_stderr_thread_takes_only_widget(self):
        sig = inspect.signature(read_stderr_thread)
        params = list(sig.parameters)
        assert params == ["widget"]

    def test_write_stdin_thread_takes_only_widget(self):
        sig = inspect.signature(write_stdin_thread)
        params = list(sig.parameters)
        assert params == ["widget"]

    def test_analysis_read_thread_takes_only_widget(self):
        sig = inspect.signature(analysis_read_thread)
        params = list(sig.parameters)
        assert params == ["widget"]
