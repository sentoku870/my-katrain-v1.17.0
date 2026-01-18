"""Phase 38: Batch input validation tests.

Tests for _safe_int() helper function in batch_core.py.
CI-safe (no real engines, no Kivy UI).
"""
import pytest


class TestSafeInt:
    """Test _safe_int() helper function."""

    def test_valid_integer(self):
        """Valid integer string parses correctly."""
        from katrain.gui.features.batch_core import _safe_int

        assert _safe_int("123") == 123
        assert _safe_int("0") == 0
        assert _safe_int("-5") == -5

    def test_empty_string_returns_default(self):
        """Empty string returns default value."""
        from katrain.gui.features.batch_core import _safe_int

        assert _safe_int("") is None
        assert _safe_int("", default=10) == 10

    def test_whitespace_only_returns_default(self):
        """Whitespace-only string returns default value."""
        from katrain.gui.features.batch_core import _safe_int

        assert _safe_int("   ") is None
        assert _safe_int("   ", default=5) == 5

    def test_invalid_string_returns_default(self):
        """Invalid string (non-numeric) returns default value."""
        from katrain.gui.features.batch_core import _safe_int

        assert _safe_int("abc") is None
        assert _safe_int("abc", default=42) == 42

    def test_float_string_returns_default(self):
        """Float string returns default (int parsing only)."""
        from katrain.gui.features.batch_core import _safe_int

        assert _safe_int("3.14") is None
        assert _safe_int("3.14", default=3) == 3

    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace is trimmed."""
        from katrain.gui.features.batch_core import _safe_int

        assert _safe_int("  42  ") == 42
        assert _safe_int("\t100\n") == 100

    def test_none_input_returns_default(self):
        """None-like input (empty) returns default."""
        from katrain.gui.features.batch_core import _safe_int

        # Note: _safe_int expects str, but handles falsy input gracefully
        assert _safe_int("", default=99) == 99

    def test_mixed_content_returns_default(self):
        """Mixed alphanumeric content returns default."""
        from katrain.gui.features.batch_core import _safe_int

        assert _safe_int("12abc") is None
        assert _safe_int("abc12", default=0) == 0
        assert _safe_int("1.0.0", default=1) == 1
