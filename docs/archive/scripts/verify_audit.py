#!/usr/bin/env python3
"""Verify audit document completeness and correctness.

Fails on:
- Any cell containing "TODO"
- Any cell containing "?"
- Any enum value not in the allowed lists
- Count mismatch between JSON and document
- Skipped files in JSON
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Allowed enum values (must match plan exactly)
ALLOWED_CATEGORY = {
    "thread-exception",
    "shutdown-cleanup",
    "callback-protection",
    "file-io-fallback",
    "silent-default",
    "partial-failure",
    "traceback-format",
    "ui-state-restore",
    "external-lib",
    "other",
}

ALLOWED_BEHAVIOR = {
    "log-and-continue",
    "log-and-exit",
    "silent-ignore",
    "fallback-value",
    "re-raise",
    "user-notify",
}

ALLOWED_RISK = {"low", "medium", "high"}

ALLOWED_INTENT = {"intentional", "improve"}

ALLOWED_ACTION = {
    "none",
    "add-specific-catch",
    "add-logging",
    "add-user-notify",
    "refactor",
    "investigate",
}


def parse_table_rows(doc: str) -> list[dict[str, str]]:
    """Parse Markdown table rows into list of dicts."""
    rows = []
    lines = doc.splitlines()

    # Find table header
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("| id |"):
            header_idx = i
            break

    if header_idx is None:
        return rows

    # Parse header
    header_line = lines[header_idx]
    headers = [h.strip() for h in header_line.split("|")[1:-1]]

    # Skip separator line
    data_start = header_idx + 2

    # Parse data rows
    for line in lines[data_start:]:
        line = line.strip()
        if not line.startswith("|"):
            break
        if not re.match(r"^\| \d+ \|", line):
            continue

        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))

    return rows


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    # Load AST analysis result
    json_path = Path("audit_raw.json")
    if not json_path.exists():
        print("Error: audit_raw.json not found")
        return 1

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # DoD #1: No skipped files
    if data["skipped_files"]:
        errors.append(f"Skipped files: {len(data['skipped_files'])}")
        for sf in data["skipped_files"]:
            print(f"  - {sf['file']}: {sf['reason']}")
    else:
        print("✓ No skipped files")

    # Load document
    doc_path = Path("docs/archive/error-handling-audit.md")
    if not doc_path.exists():
        errors.append("Document not found: docs/archive/error-handling-audit.md")
        print("\nErrors:")
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    doc = doc_path.read_text(encoding="utf-8")
    rows = parse_table_rows(doc)

    # DoD #2: Count match
    if data["total"] == len(rows):
        print(f"✓ Counts match: {data['total']}")
    else:
        errors.append(f"Count mismatch: JSON={data['total']}, Doc={len(rows)}")

    # DoD #3 & #4: Validate each row
    todo_count = 0
    question_count = 0
    enum_errors: list[str] = []

    for i, row in enumerate(rows, start=1):
        row_id = row.get("id", str(i))

        # Check for TODO
        for col, val in row.items():
            if "TODO" in val:
                todo_count += 1
                if todo_count <= 5:  # Show first 5 examples
                    warnings.append(f"Row {row_id}: TODO in '{col}'")

        # Check for ?
        for col, val in row.items():
            if "?" in val and col not in ("notes",):  # Allow ? in notes
                question_count += 1
                if question_count <= 5:
                    warnings.append(f"Row {row_id}: '?' in '{col}'")

        # Validate enums
        category = row.get("category", "")
        if category and category not in ALLOWED_CATEGORY:
            enum_errors.append(f"Row {row_id}: invalid category '{category}'")

        behavior = row.get("behavior", "")
        if behavior and behavior not in ALLOWED_BEHAVIOR:
            enum_errors.append(f"Row {row_id}: invalid behavior '{behavior}'")

        risk = row.get("risk", "")
        if risk and risk not in ALLOWED_RISK:
            enum_errors.append(f"Row {row_id}: invalid risk '{risk}'")

        intent = row.get("intent", "")
        if intent and intent not in ALLOWED_INTENT:
            enum_errors.append(f"Row {row_id}: invalid intent '{intent}'")

        action = row.get("action", "")
        if action and action not in ALLOWED_ACTION:
            enum_errors.append(f"Row {row_id}: invalid action '{action}'")

    # Report TODO/? counts
    if todo_count == 0:
        print("✓ No TODO entries")
    else:
        errors.append(f"TODO entries remain: {todo_count}")

    if question_count == 0:
        print("✓ No '?' entries (except notes)")
    else:
        errors.append(f"'?' entries remain: {question_count}")

    # Report enum errors
    if enum_errors:
        errors.append(f"Invalid enum values: {len(enum_errors)}")
        for ee in enum_errors[:10]:  # Show first 10
            print(f"  - {ee}")
    else:
        print("✓ All enum values valid")

    # Print warnings
    if warnings:
        print("\nWarnings (first 5 of each type):")
        for w in warnings[:10]:
            print(f"  ⚠ {w}")

    # Final result
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    print("\n✓ All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
