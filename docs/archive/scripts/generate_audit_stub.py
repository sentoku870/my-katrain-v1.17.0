#!/usr/bin/env python3
"""Generate Markdown table stub from audit_raw.json.

Pre-fills: id, file, line, context, pattern
Manual fill: category, behavior, risk, intent, action, notes

NOTE: File paths and context are output in full (no truncation) to maintain
traceability for Phase 78/79. Long values may wrap in the Markdown table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    json_path = Path("audit_raw.json")
    if not json_path.exists():
        print(
            "Error: audit_raw.json not found. Run audit_exceptions.py first.",
            file=sys.stderr,
        )
        return 1

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    if data.get("skipped_files"):
        print(
            "Error: skipped_files is not empty. Fix parsing errors first.",
            file=sys.stderr,
        )
        return 1

    # Generate header
    print(
        "| id | file | line | context | pattern | category | behavior | risk | intent | action | notes |"
    )
    print(
        "|----|------|------|---------|---------|----------|----------|------|--------|--------|-------|"
    )

    # Generate rows with placeholders for manual columns
    # NO TRUNCATION - output full paths and contexts for traceability
    for i, entry in enumerate(data["entries"], start=1):
        file_path = entry["file"]
        context = entry["context"]
        pattern = entry["pattern"]

        # Pre-suggest category based on context keywords
        suggested_cat = "TODO"
        ctx_lower = entry["context"].lower()
        file_lower = entry["file"].lower()

        if "thread" in ctx_lower or "_thread" in ctx_lower:
            suggested_cat = "TODO(thread-exception?)"
        elif (
            "shutdown" in ctx_lower
            or "cleanup" in ctx_lower
            or "terminate" in ctx_lower
        ):
            suggested_cat = "TODO(shutdown-cleanup?)"
        elif "callback" in ctx_lower:
            suggested_cat = "TODO(callback-protection?)"
        elif "error_handler" in file_lower:
            suggested_cat = "TODO(traceback-format?)"

        # Pre-suggest intent based on noqa
        if entry["has_noqa"]:
            suggested_intent = "intentional"
            suggested_action = "none"
        else:
            suggested_intent = "TODO"
            suggested_action = "TODO"

        notes = entry.get("noqa_reason", "")

        # Escape pipe characters in values to avoid breaking Markdown table
        file_path = file_path.replace("|", "\\|")
        context = context.replace("|", "\\|")
        pattern = pattern.replace("|", "\\|")
        notes = notes.replace("|", "\\|")

        print(
            f"| {i} | {file_path} | {entry['line']} | {context} | {pattern} | {suggested_cat} | TODO | TODO | {suggested_intent} | {suggested_action} | {notes} |"
        )

    # Summary to stderr (not part of output file)
    print(f"\n<!-- Generated stub: {data['total']} entries -->", file=sys.stderr)
    print(
        f"<!-- With noqa: {data['with_noqa']}, Without noqa: {data['without_noqa']} -->",
        file=sys.stderr,
    )
    print("<!-- Replace all TODO values before finalizing -->", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
