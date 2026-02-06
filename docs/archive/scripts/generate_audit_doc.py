#!/usr/bin/env python3
"""Generate the complete audit document from audit_raw.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def classify(entry: dict) -> tuple[str, str, str, str, str]:
    """Classify an exception handler entry.

    Returns (category, behavior, risk, intent, action).
    """
    ctx = entry["context"].lower()
    file = entry["file"].lower()

    # Already has noqa - use existing reason to infer
    if entry["has_noqa"]:
        reason = entry["noqa_reason"].lower()
        if "thread" in reason:
            return "thread-exception", "log-and-exit", "low", "intentional", "none"
        elif "shutdown" in reason or "cleanup" in reason:
            return "shutdown-cleanup", "log-and-continue", "low", "intentional", "none"
        elif "callback" in reason:
            return "callback-protection", "log-and-continue", "low", "intentional", "none"
        elif "config" in reason or "fail" in reason:
            return "file-io-fallback", "fallback-value", "low", "intentional", "none"
        else:
            return "file-io-fallback", "log-and-continue", "low", "intentional", "none"

    # Thread-related
    if "thread" in ctx or "_thread" in ctx:
        return "thread-exception", "user-notify", "low", "intentional", "none"

    # Error handler internals
    if "error_handler" in file:
        return "traceback-format", "silent-ignore", "low", "intentional", "none"

    # file_opener.py - all are external lib calls (subprocess/os)
    if "file_opener" in file:
        return "external-lib", "log-and-continue", "low", "intentional", "none"

    # lang.py / lang_bridge.py - external lib / callback
    if "lang" in file and ("callback" in ctx or "notify" in ctx):
        return "callback-protection", "silent-ignore", "low", "intentional", "none"
    if "lang" in file:
        return "file-io-fallback", "fallback-value", "low", "improve", "add-specific-catch"

    # sound.py - external lib
    if "sound" in file:
        return "external-lib", "silent-ignore", "low", "intentional", "none"

    # Batch processing
    if "/batch/" in file or "batch" in ctx:
        return "partial-failure", "log-and-continue", "medium", "improve", "add-specific-catch"

    # Leela engine - similar to KataGo engine
    if "leela" in file:
        if "shutdown" in ctx:
            return "shutdown-cleanup", "log-and-continue", "low", "intentional", "none"
        return "thread-exception", "log-and-continue", "low", "intentional", "none"

    # diagnostics.py
    if "diagnostics" in file:
        return "external-lib", "fallback-value", "low", "improve", "add-specific-catch"

    # game.py
    if "game.py" in file:
        return "file-io-fallback", "fallback-value", "low", "improve", "add-specific-catch"

    # controlspanel.py
    if "controlspanel" in file:
        return "ui-state-restore", "fallback-value", "low", "improve", "add-specific-catch"

    # smart_kifu
    if "smart_kifu" in file:
        return "file-io-fallback", "log-and-continue", "medium", "improve", "add-specific-catch"

    # radar_chart / skill_radar
    if "radar" in file:
        return "ui-state-restore", "fallback-value", "low", "improve", "add-specific-catch"

    # settings_popup
    if "settings" in file:
        if "import" in ctx or "export" in ctx:
            return "file-io-fallback", "user-notify", "medium", "improve", "add-specific-catch"
        return "ui-state-restore", "user-notify", "medium", "improve", "add-specific-catch"

    # SGF operations
    if "sgf" in file:
        return "file-io-fallback", "user-notify", "medium", "improve", "add-specific-catch"

    # Reports
    if "/reports/" in file or "karte" in file:
        return "partial-failure", "log-and-continue", "medium", "improve", "add-specific-catch"

    # Curator
    if "curator" in file:
        return "partial-failure", "log-and-continue", "medium", "improve", "add-specific-catch"

    # Summary operations
    if "summary" in file:
        return "partial-failure", "log-and-continue", "medium", "improve", "add-specific-catch"

    # Popups - usually file operations or network
    if "popup" in file:
        if "download" in ctx or "check_model" in ctx:
            return "external-lib", "log-and-continue", "medium", "improve", "add-specific-catch"
        return "file-io-fallback", "user-notify", "medium", "improve", "add-specific-catch"

    # package_export
    if "package_export" in file:
        return "file-io-fallback", "user-notify", "medium", "improve", "add-specific-catch"

    # engine_compare
    if "engine_compare" in file:
        return "partial-failure", "log-and-continue", "medium", "improve", "add-specific-catch"

    # __main__.py specific patterns
    if "__main__" in file:
        if "toggle" in ctx or "mode" in ctx:
            return "ui-state-restore", "log-and-continue", "low", "improve", "add-specific-catch"
        if "start" in ctx:
            return "ui-state-restore", "silent-ignore", "low", "intentional", "none"
        if "position" in ctx or "build" in ctx:
            return "ui-state-restore", "fallback-value", "low", "intentional", "none"
        return "ui-state-restore", "log-and-continue", "medium", "improve", "add-specific-catch"

    # leela_manager
    if "leela_manager" in file:
        return "thread-exception", "log-and-continue", "low", "improve", "add-specific-catch"

    # Default: needs investigation
    return "other", "log-and-continue", "medium", "improve", "investigate"


def main() -> int:
    json_path = Path("audit_raw.json")
    if not json_path.exists():
        print("Error: audit_raw.json not found", file=sys.stderr)
        return 1

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # Count by category
    categories: dict[str, int] = {}
    intents = {"intentional": 0, "improve": 0}
    patterns: dict[str, int] = {}

    for entry in data["entries"]:
        cat, beh, risk, intent, action = classify(entry)
        categories[cat] = categories.get(cat, 0) + 1
        intents[intent] = intents.get(intent, 0) + 1
        pat = entry["pattern"]
        patterns[pat] = patterns.get(pat, 0) + 1

    # Generate document
    print("# Error Handling Audit - Phase 77")
    print()
    print("## Summary")
    print()
    print("| Metric | Count |")
    print("|--------|-------|")
    print(f"| Total handlers | {data['total']} |")
    print(f"| Intentional (noqa or justified) | {intents['intentional']} |")
    print(f"| Improvement targets | {intents['improve']} |")
    for pat, cnt in sorted(patterns.items(), key=lambda x: -x[1]):
        print(f"| By pattern: {pat} | {cnt} |")

    print()
    print("## Audit Table")
    print()
    print("| id | file | line | context | pattern | category | behavior | risk | intent | action | notes |")
    print("|----|------|------|---------|---------|----------|----------|------|--------|--------|-------|")

    for i, entry in enumerate(data["entries"], start=1):
        cat, beh, risk, intent, action = classify(entry)
        notes = entry["noqa_reason"] if entry["has_noqa"] else ""
        # Escape pipes
        file_path = entry["file"].replace("|", "\\|")
        context = entry["context"].replace("|", "\\|")
        pattern = entry["pattern"].replace("|", "\\|")
        notes = notes.replace("|", "\\|")
        print(f"| {i} | {file_path} | {entry['line']} | {context} | {pattern} | {cat} | {beh} | {risk} | {intent} | {action} | {notes} |")

    print()
    print("## Category Summary")

    category_descriptions = {
        "thread-exception": "Exception handlers in thread contexts. Most are intentional to prevent thread crashes.",
        "shutdown-cleanup": "Exception handlers during shutdown/cleanup. Intentional to ensure cleanup completes.",
        "callback-protection": "Exception handlers protecting callback callers. Intentional to prevent crash propagation.",
        "file-io-fallback": "Exception handlers for file I/O operations. Mix of intentional (config) and improvement targets.",
        "partial-failure": "Exception handlers in batch processing. Allow partial success when processing multiple items.",
        "traceback-format": "Exception handlers in error handler itself. Must not throw to prevent cascading failures.",
        "ui-state-restore": "Exception handlers for UI state restoration. Safe to fail with fallback values.",
        "external-lib": "Exception handlers for external library calls. Protect against external failures.",
        "other": "Handlers needing further investigation to determine proper categorization.",
    }

    for cat, cnt in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"\n### {cat} ({cnt} entries)")
        print(category_descriptions.get(cat, ""))

    print("""
## Phase 78/79 Recommendations

### High Priority (Phase 78) - User-facing paths
- File I/O operations that notify users should use specific exceptions (FileNotFoundError, PermissionError)
- SGF parsing errors should catch specific sgf_parser exceptions
- Settings import/export should validate data before processing

### Medium Priority (Phase 79) - Background paths
- Batch processing should differentiate between recoverable and fatal errors
- Report generation should use specific exceptions for different failure modes
- Curator operations should have clearer error categories
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
