"""Phase 148-D2: Tests for report_navigator.

Ensures Navigator uses .json extension (Phase 148-D1: full migration) and
ignores legacy .md files.

Phase 227-C: extended with ``find_latest_llm_input`` tests (karte+summary
multi-game support).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from katrain.gui.features.report_navigator import (
    REPORT_PATTERNS,
    find_latest_llm_input,
    find_recent_reports,
    get_latest_report,
)


def test_report_patterns_use_json_extension():
    """Phase 148-D1: karte/summary patterns use .json (not .md)."""
    assert REPORT_PATTERNS["karte"] == "karte_*.json"
    assert REPORT_PATTERNS["summary"] == "summary_*.json"
    assert ".md" not in REPORT_PATTERNS["karte"]
    assert ".md" not in REPORT_PATTERNS["summary"]


def test_find_recent_reports_finds_json(tmp_path: Path):
    """Navigator finds karte/summary .json files."""
    (tmp_path / "karte_001.json").write_text("{}")
    (tmp_path / "summary_black.json").write_text("{}")
    reports = find_recent_reports(tmp_path)
    paths = {r.path.name for r in reports}
    assert "karte_001.json" in paths
    assert "summary_black.json" in paths


def test_find_recent_reports_ignores_legacy_md(tmp_path: Path):
    """Phase 148-D1: legacy .md files are ignored (fully migrated to .json)."""
    (tmp_path / "karte_legacy.md").write_text("# legacy")
    (tmp_path / "summary_old.md").write_text("# legacy")
    (tmp_path / "karte_new.json").write_text("{}")
    reports = find_recent_reports(tmp_path)
    paths = {r.path.name for r in reports}
    assert "karte_new.json" in paths
    assert "karte_legacy.md" not in paths
    assert "summary_old.md" not in paths


def test_get_latest_report_returns_most_recent(tmp_path: Path):
    """get_latest_report returns the newest report."""
    old = tmp_path / "karte_old.json"
    old.write_text("{}")
    time.sleep(0.05)  # ensure mtime diff
    new = tmp_path / "karte_new.json"
    new.write_text("{}")
    latest = get_latest_report(tmp_path)
    assert latest is not None
    assert latest.path.name == "karte_new.json"


def test_find_recent_reports_empty_dir(tmp_path: Path):
    """Empty directory returns empty list."""
    assert find_recent_reports(tmp_path) == []


def test_find_recent_reports_nonexistent_dir(tmp_path: Path):
    """Non-existent directory returns empty list."""
    missing = tmp_path / "does_not_exist"
    assert find_recent_reports(missing) == []


def test_find_recent_reports_recurses_into_subdirectories(tmp_path: Path):
    """2026-07: batch analysis writes reports under ``reports/karte/`` /
    ``reports/summary/``. ``find_recent_reports`` must recurse so the LLM
    Coach popup can auto-fill batch output without a manual selection."""
    sub = tmp_path / "reports" / "karte"
    sub.mkdir(parents=True)
    nested = sub / "karte_batch_20260101-0000.json"
    _touch_with_mtime(nested, 1500)

    # Also a non-JSON peer that must NOT be matched
    (sub / "notes.txt").write_text("ignore me")

    reports = find_recent_reports(tmp_path)
    assert len(reports) == 1
    assert reports[0].path == nested
    assert reports[0].report_type == "karte"


def test_find_latest_llm_input_picks_nested_batch_report(tmp_path: Path):
    """The end-to-end path: nested batch karte is selected over a flat
    (older) summary when the nested file is newer."""
    _touch_with_mtime(tmp_path / "summary_root.json", 1000)
    nested = tmp_path / "reports" / "summary" / "summary_batch.json"
    nested.parent.mkdir(parents=True)
    _touch_with_mtime(nested, 2000)

    result = find_latest_llm_input(tmp_path)
    assert result is not None
    assert result.path == nested
    assert result.report_type == "summary"


# --- find_latest_llm_input (Phase 227-C) ---


def _touch_with_mtime(path: Path, mtime: int) -> None:
    """Write an empty file and set its mtime explicitly."""
    path.write_text("{}")
    os.utime(path, (mtime, mtime))


class TestFindLatestLlmInput:
    def test_only_karte(self, tmp_path: Path):
        _touch_with_mtime(tmp_path / "karte_001.json", 1000)
        result = find_latest_llm_input(tmp_path)
        assert result is not None
        assert result.path.name == "karte_001.json"
        assert result.report_type == "karte"

    def test_only_summary(self, tmp_path: Path):
        _touch_with_mtime(tmp_path / "summary_001.json", 1000)
        result = find_latest_llm_input(tmp_path)
        assert result is not None
        assert result.path.name == "summary_001.json"
        assert result.report_type == "summary"

    def test_mixed_returns_overall_latest(self, tmp_path: Path):
        # Summary is the newest → should win
        _touch_with_mtime(tmp_path / "karte_old.json", 1000)
        _touch_with_mtime(tmp_path / "karte_new.json", 2000)
        _touch_with_mtime(tmp_path / "summary_only.json", 1500)
        _touch_with_mtime(tmp_path / "summary_latest.json", 3000)
        result = find_latest_llm_input(tmp_path)
        assert result is not None
        assert result.path.name == "summary_latest.json"
        assert result.report_type == "summary"

    def test_mixed_karte_newer_wins(self, tmp_path: Path):
        # Karte is the newest → should win
        _touch_with_mtime(tmp_path / "karte_fresh.json", 5000)
        _touch_with_mtime(tmp_path / "summary_old.json", 1000)
        result = find_latest_llm_input(tmp_path)
        assert result is not None
        assert result.path.name == "karte_fresh.json"
        assert result.report_type == "karte"

    def test_empty_dir_returns_none(self, tmp_path: Path):
        # Create empty subdir
        empty = tmp_path / "empty"
        empty.mkdir()
        assert find_latest_llm_input(empty) is None

    def test_nonexistent_dir_returns_none(self, tmp_path: Path):
        missing = tmp_path / "does_not_exist"
        assert find_latest_llm_input(missing) is None

    def test_ignores_zip_packages(self, tmp_path: Path):
        # llm_package_*.zip is a bundle, not raw JSON input
        _touch_with_mtime(tmp_path / "llm_package_2024.zip", 5000)
        _touch_with_mtime(tmp_path / "karte_recent.json", 1000)
        result = find_latest_llm_input(tmp_path)
        assert result is not None
        # karte wins because .zip is excluded
        assert result.path.name == "karte_recent.json"
        assert result.report_type == "karte"

    def test_ignores_md_files(self, tmp_path: Path):
        _touch_with_mtime(tmp_path / "karte_old.md", 9999)
        _touch_with_mtime(tmp_path / "karte_new.json", 1000)
        result = find_latest_llm_input(tmp_path)
        assert result is not None
        assert result.report_type == "karte"

    def test_ignores_non_matching_json(self, tmp_path: Path):
        # random.json doesn't match karte_*.json or summary_*.json
        _touch_with_mtime(tmp_path / "random.json", 9999)
        _touch_with_mtime(tmp_path / "karte_real.json", 1000)
        result = find_latest_llm_input(tmp_path)
        assert result is not None
        assert result.path.name == "karte_real.json"

    def test_only_zip_returns_none(self, tmp_path: Path):
        # Only zip files → no valid LLM input
        _touch_with_mtime(tmp_path / "llm_package_2024.zip", 5000)
        result = find_latest_llm_input(tmp_path)
        assert result is None

    def test_returns_correct_mtime(self, tmp_path: Path):
        _touch_with_mtime(tmp_path / "karte_a.json", 1000)
        _touch_with_mtime(tmp_path / "summary_b.json", 2000)
        result = find_latest_llm_input(tmp_path)
        assert result is not None
        assert result.mtime == 2000
