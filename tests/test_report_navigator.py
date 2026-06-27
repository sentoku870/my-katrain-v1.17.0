"""Phase 148-D2: Tests for report_navigator.

Ensures Navigator uses .json extension (Phase 148-D1: full migration) and
ignores legacy .md files.
"""
from __future__ import annotations

import time
from pathlib import Path

from katrain.gui.features.report_navigator import (
    REPORT_PATTERNS,
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