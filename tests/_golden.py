"""Helpers used by the golden-test snapshot comparison layer.

Not prefixed with ``test_`` so pytest does not try to collect this
module. Imported by ``tests/conftest.py`` (via ``pytest_addoption``)
and by individual test files that need to load or update golden
snapshots.
"""

from __future__ import annotations

import re
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"


def normalize_output(text: str) -> str:
    """
    Normalize Karte/Summary output for golden test comparison.

    Normalizes:
    1. Line endings → LF only (handles CRLF and CR)
    2. Timestamps → [TIMESTAMP]
    3. Absolute paths → [PATH]
    4. Floating point numbers → 1 decimal place
    5. Trailing newlines → single trailing newline

    Does NOT normalize:
    - Order of sections (fixed by code)
    - Order of moves (deterministic tiebreaks in code)
    - Evidence order (deterministic tiebreaks in code)
    """
    # 1. Normalize line endings first (before other processing)
    # Order matters: \r\n first, then remaining \r
    result = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Normalize timestamps (various formats)
    # ISO format: 2025-01-05T12:34:56
    result = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "[TIMESTAMP]", result)
    # Date format: 2025-01-05
    result = re.sub(r"\d{4}-\d{2}-\d{2}", "[DATE]", result)
    # Time format: 12:34:56 (colon-separated)
    result = re.sub(r"\d{2}:\d{2}:\d{2}", "[TIME]", result)
    # Time format: 12 34 56 (space-separated, as in game_id from filename)
    result = re.sub(r"\d{2} \d{2} \d{2}", "[TIME]", result)
    # Run ID: run_<unix_timestamp>_<8 hex chars> — varies every run
    result = re.sub(r'"run_id":\s*"run_\d+_[0-9a-f]{8}"', '"run_id": "[RUN_ID]"', result)

    # 3. Normalize absolute paths (Windows and Unix)
    # Windows: D:\github\... or C:\Users\...
    result = re.sub(r"[A-Z]:\\[^\s\]]+", "[PATH]", result)
    # Unix: /home/... or /tmp/...
    result = re.sub(r"/(?:home|tmp|var|usr)[^\s\]]*", "[PATH]", result)

    # 4. Normalize floating point numbers to 1 decimal place
    # Match numbers like 3.14159 or -12.345 (but not integers)
    def round_float(match):
        num = float(match.group(0))
        # Keep sign, round to 1 decimal
        return f"{num:.1f}"

    # Match floats that have decimal points with 2+ digits after
    result = re.sub(r"-?\d+\.\d{2,}", round_float, result)

    # 5. Normalize trailing newlines (single trailing newline)
    result = result.rstrip("\n") + "\n"

    return result


def load_golden(name: str) -> str:
    """Load golden file content."""
    golden_path = GOLDEN_DIR / name
    if not golden_path.exists():
        raise FileNotFoundError(f"Golden file not found: {golden_path}")
    return golden_path.read_text(encoding="utf-8")


def save_golden(name: str, content: str) -> None:
    """Save content to golden file."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden_path = GOLDEN_DIR / name
    golden_path.write_text(content, encoding="utf-8")


def update_golden_if_requested(name: str, content: str, request) -> None:
    """Update golden file if --update-goldens flag is passed."""
    if request.config.getoption("--update-goldens", default=False):
        save_golden(name, content)
