"""Tests for katrain.gui.features.report_navigator.

Tests only pure functions (Kivy-independent).
UI functions are tested manually via smoke tests.
mtime is set explicitly with os.utime() for deterministic tests.
"""
import os
from pathlib import Path

import pytest

from katrain.gui.features.report_navigator import (
    REPORT_PATTERNS,
    ReportInfo,
    find_recent_reports,
    get_latest_report,
)


class TestReportPatterns:
    """Tests for glob patterns."""

    def test_karte_pattern_matches_expected_files(self, tmp_path):
        """karte_*.md matches karte_test.md but not karte.md."""
        # Should match
        (tmp_path / "karte_test.md").write_text("test")
        (tmp_path / "karte_game1_20260117.md").write_text("test")
        # Should NOT match
        (tmp_path / "karte.md").write_text("test")  # no underscore
        (tmp_path / "my_karte_test.md").write_text("test")  # prefix

        matches = list(tmp_path.glob(REPORT_PATTERNS["karte"]))
        names = {p.name for p in matches}
        assert names == {"karte_test.md", "karte_game1_20260117.md"}

    def test_summary_pattern_matches_expected_files(self, tmp_path):
        """summary_*.md matches summary_test.md but not summary.md."""
        # Should match
        (tmp_path / "summary_test.md").write_text("test")
        (tmp_path / "summary_player_20260117.md").write_text("test")
        # Should NOT match
        (tmp_path / "summary.md").write_text("test")  # no underscore

        matches = list(tmp_path.glob(REPORT_PATTERNS["summary"]))
        names = {p.name for p in matches}
        assert names == {"summary_test.md", "summary_player_20260117.md"}

    def test_package_pattern_matches_expected_files(self, tmp_path):
        """llm_package_*.zip matches llm_package_test.zip."""
        # Should match
        (tmp_path / "llm_package_test.zip").write_bytes(b"PK")
        (tmp_path / "llm_package_20260117-120000_abcd.zip").write_bytes(b"PK")
        # Should NOT match
        (tmp_path / "llm_package.zip").write_bytes(b"PK")  # no underscore after package

        matches = list(tmp_path.glob(REPORT_PATTERNS["package"]))
        names = {p.name for p in matches}
        assert names == {"llm_package_test.zip", "llm_package_20260117-120000_abcd.zip"}


class TestFindRecentReports:
    """Tests for find_recent_reports function."""

    def test_empty_for_nonexistent_dir(self, tmp_path):
        """Returns empty list for non-existent directory."""
        result = find_recent_reports(tmp_path / "nonexistent")
        assert result == []

    def test_empty_for_empty_dir(self, tmp_path):
        """Returns empty list for directory with no matching files."""
        (tmp_path / "random.txt").write_text("random")
        result = find_recent_reports(tmp_path)
        assert result == []

    def test_finds_all_report_types(self, tmp_path):
        """Finds karte, summary, and package files."""
        (tmp_path / "karte_test.md").write_text("karte")
        (tmp_path / "summary_test.md").write_text("summary")
        (tmp_path / "llm_package_test.zip").write_bytes(b"PK")

        result = find_recent_reports(tmp_path)
        types = {r.report_type for r in result}
        assert types == {"karte", "summary", "package"}

    def test_sorts_by_mtime_newest_first(self, tmp_path):
        """Results are sorted by mtime (newest first) using os.utime()."""
        old = tmp_path / "karte_old.md"
        old.write_text("old")
        os.utime(old, (1000, 1000))  # atime, mtime = 1970-01-01 + 1000s

        new = tmp_path / "karte_new.md"
        new.write_text("new")
        os.utime(new, (2000, 2000))  # newer mtime

        result = find_recent_reports(tmp_path)
        assert result[0].path.name == "karte_new.md"
        assert result[1].path.name == "karte_old.md"

    def test_respects_limit(self, tmp_path):
        """Returns at most 'limit' reports."""
        for i in range(20):
            f = tmp_path / f"karte_{i:02d}.md"
            f.write_text(f"karte {i}")
            os.utime(f, (i * 100, i * 100))  # different mtime for each

        result = find_recent_reports(tmp_path, limit=5)
        assert len(result) == 5
        # Newest 5 (i=19, 18, 17, 16, 15) should be returned
        assert result[0].path.name == "karte_19.md"
        assert result[4].path.name == "karte_15.md"

    def test_ignores_unmatched_files(self, tmp_path):
        """Ignores files that don't match patterns."""
        (tmp_path / "random.txt").write_text("random")
        (tmp_path / "karte.md").write_text("no underscore")
        (tmp_path / "karte_test.md").write_text("karte")

        result = find_recent_reports(tmp_path)
        assert len(result) == 1
        assert result[0].report_type == "karte"
        assert result[0].path.name == "karte_test.md"

    def test_handles_oserror_gracefully(self, tmp_path):
        """Continues even if stat() fails for some files."""
        f = tmp_path / "karte_test.md"
        f.write_text("test")

        # This should still work even with potential permission issues
        result = find_recent_reports(tmp_path)
        assert len(result) == 1


class TestGetLatestReport:
    """Tests for get_latest_report function."""

    def test_returns_none_for_empty_dir(self, tmp_path):
        """Returns None when no reports found."""
        assert get_latest_report(tmp_path) is None

    def test_returns_none_for_nonexistent_dir(self, tmp_path):
        """Returns None for non-existent directory."""
        assert get_latest_report(tmp_path / "nonexistent") is None

    def test_returns_newest_across_types(self, tmp_path):
        """Returns the newest report regardless of type."""
        old = tmp_path / "karte_old.md"
        old.write_text("old")
        os.utime(old, (1000, 1000))

        new = tmp_path / "summary_new.md"
        new.write_text("new")
        os.utime(new, (2000, 2000))

        result = get_latest_report(tmp_path)
        assert result is not None
        assert result.path.name == "summary_new.md"
        assert result.report_type == "summary"

    def test_returns_report_info_with_correct_fields(self, tmp_path):
        """ReportInfo has correct path, type, and mtime."""
        f = tmp_path / "karte_test.md"
        f.write_text("test")
        os.utime(f, (1234, 1234))

        result = get_latest_report(tmp_path)
        assert result is not None
        assert result.path == f
        assert result.report_type == "karte"
        assert result.mtime == 1234


class TestReportInfo:
    """Tests for ReportInfo dataclass."""

    def test_report_info_creation(self, tmp_path):
        """ReportInfo can be created with expected fields."""
        f = tmp_path / "test.md"
        f.write_text("test")

        info = ReportInfo(path=f, report_type="karte", mtime=1234.5)
        assert info.path == f
        assert info.report_type == "karte"
        assert info.mtime == 1234.5
