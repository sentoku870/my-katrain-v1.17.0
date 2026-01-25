"""Tests for batch helper functions (Phase 53)."""
import os
import pytest
from katrain.core.batch.helpers import (
    truncate_game_name,
    format_wr_gap,
    make_markdown_link_target,
)


class TestTruncateGameName:
    """Tests for truncate_game_name function."""

    def test_short_unchanged(self):
        """Short names should remain unchanged."""
        assert truncate_game_name("Short") == "Short"

    def test_exactly_max_len_unchanged(self):
        """Names at exactly max length should remain unchanged."""
        name = "a" * 35
        assert truncate_game_name(name) == name

    def test_preserves_tail(self):
        """Truncated names should preserve the tail (ID suffix)."""
        name = "[ゆうだい03]vs[陈晨59902]1766534654030022615"
        result = truncate_game_name(name)
        assert result.endswith("22615")
        assert "..." in result
        assert len(result) <= 35

    def test_multibyte_safe(self):
        """Multibyte characters should be handled correctly."""
        name = "[日本語名前]vs[中文名字]1234567890123456"
        result = truncate_game_name(name)
        # len() counts codepoints, not bytes
        assert len(result) <= 35

    def test_custom_max_len(self):
        """Custom max_len should be respected (min 26 due to head+tail+ellipsis)."""
        # Note: function uses head_len=18, tail_len=5, ellipsis=3, so min is 26
        name = "a" * 50  # Long enough name
        result = truncate_game_name(name, max_len=30)
        assert len(result) <= 30
        assert "..." in result


class TestFormatWRGap:
    """Tests for format_wr_gap function."""

    def test_normal(self):
        """Normal values should format correctly."""
        assert format_wr_gap(0.15) == "15.0%"
        assert format_wr_gap(0.456) == "45.6%"

    def test_clamps_negative(self):
        """Negative values should clamp to 0.0%."""
        # Negative values can occur due to search variance
        assert format_wr_gap(-0.01) == "0.0%"
        assert format_wr_gap(-0.05) == "0.0%"

    def test_clamps_over_one(self):
        """Values over 1.0 should clamp to 100.0%."""
        assert format_wr_gap(1.05) == "100.0%"

    def test_small_positive(self):
        """Small positive values should show 1 decimal precision."""
        # Should show 1 decimal, not round to 0%
        assert format_wr_gap(0.003) == "0.3%"
        assert format_wr_gap(0.001) == "0.1%"

    def test_none(self):
        """None should return '-'."""
        assert format_wr_gap(None) == "-"

    def test_zero(self):
        """Zero should format as 0.0%."""
        assert format_wr_gap(0.0) == "0.0%"


class TestMakeMarkdownLinkTarget:
    """Tests for make_markdown_link_target function."""

    def test_sibling_folder(self):
        """Links to sibling folders should work."""
        result = make_markdown_link_target(
            "/reports/summary",
            "/reports/karte/file.md"
        )
        assert result == "../karte/file.md"

    def test_encodes_brackets(self):
        """Brackets should be URL-encoded."""
        result = make_markdown_link_target(
            "/reports/summary",
            "/reports/karte/karte_[player]vs[player].md"
        )
        assert "%5B" in result  # [ encoded
        assert "%5D" in result  # ] encoded
        assert "[" not in result
        assert "]" not in result

    def test_encodes_spaces(self):
        """Spaces should be URL-encoded."""
        result = make_markdown_link_target(
            "/reports/summary",
            "/reports/karte/karte_player name.md"
        )
        assert "%20" in result  # space encoded
        assert " " not in result

    def test_keeps_safe_chars(self):
        """Safe path characters should not be encoded."""
        result = make_markdown_link_target(
            "/reports/summary",
            "/reports/karte/karte_test-file_v1.0.md"
        )
        # Hyphens, underscores, dots, slashes should not be encoded
        assert "-" in result
        assert "_" in result
        assert "." in result
        assert "/" in result

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_windows_backslash(self):
        """On Windows, backslashes should become forward slashes."""
        result = make_markdown_link_target(
            "C:\\reports\\summary",
            "C:\\reports\\karte\\file.md"
        )
        assert "\\" not in result
        assert "../karte/file.md" == result

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_cross_drive_fallback(self):
        """Cross-drive paths on Windows should fallback to basename."""
        result = make_markdown_link_target(
            "C:\\reports\\summary",
            "D:\\other\\karte\\file.md"
        )
        # Should fallback to just filename
        assert "file.md" in result

    def test_multibyte_filename(self):
        """Multibyte characters should be URL-encoded."""
        result = make_markdown_link_target(
            "/reports/summary",
            "/reports/karte/karte_日本語.md"
        )
        # Should URL-encode multibyte chars
        assert ".md" in result
        # Japanese chars should be percent-encoded
        assert "%" in result or "日本語" not in result

    def test_same_directory(self):
        """Links in the same directory should work."""
        result = make_markdown_link_target(
            "/reports/karte",
            "/reports/karte/file.md"
        )
        assert result == "file.md"
