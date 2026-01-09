#!/usr/bin/env python3
"""
check_threshold_consistency.py - Verify all eval constants use the shared module.

This script checks that:
1. No files define their own EVAL_THRESHOLDS, EVAL_COLORS, etc.
2. All files properly import from katrain_qt.common.eval_constants

Usage:
    python scripts/check_threshold_consistency.py

Exit codes:
    0 - All checks pass
    1 - Violations found (hardcoded constants or missing imports)
"""

import re
import sys
from pathlib import Path


# Patterns that indicate hardcoded constants (violations)
VIOLATION_PATTERNS = [
    # Hardcoded threshold arrays
    r"^\s*EVAL_THRESHOLDS\s*=\s*\[",
    r"^\s*EVAL_THRESHOLDS_KIVY\s*=\s*\[",
    r"^\s*ROW_BG_THRESHOLDS\s*=\s*\[",
    # Hardcoded color arrays
    r"^\s*EVAL_COLORS\s*=\s*\[",
    r"^\s*EVAL_COLORS_KIVY\s*=\s*\[",
    r"^\s*EVAL_ROW_COLORS\s*=\s*\[",
    r"^\s*ROW_BG_COLORS\s*=\s*\[",
    # Hardcoded alpha values (with QColor constructor, not imports)
    r"^\s*LOW_VISITS_THRESHOLD\s*=\s*\d",
    r"^\s*HINTS_ALPHA\s*=\s*0\.\d",
    r"^\s*HINTS_LO_ALPHA\s*=\s*0\.\d",
]

# Files to check (relative to project root)
FILES_TO_CHECK = [
    "katrain_qt/widgets/board_widget.py",
    "katrain_qt/widgets/analysis_panel.py",
    "katrain_qt/widgets/candidates_panel.py",
    "katrain_qt/widgets/stats_panel.py",
    "katrain_qt/widgets/score_graph.py",
]

# Files that are ALLOWED to define constants (the source of truth)
ALLOWED_DEFINITION_FILES = [
    "katrain_qt/common/eval_constants.py",
]

# Expected import pattern
EXPECTED_IMPORT = r"from\s+katrain_qt\.common\.eval_constants\s+import"


def check_file(filepath: Path, project_root: Path) -> list:
    """
    Check a single file for violations.

    Returns list of (line_number, violation_description) tuples.
    """
    violations = []
    relative_path = str(filepath.relative_to(project_root))

    # Skip allowed definition files
    if relative_path.replace("\\", "/") in ALLOWED_DEFINITION_FILES:
        return []

    if not filepath.exists():
        return [(0, f"File not found: {relative_path}")]

    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Check for hardcoded patterns
    for i, line in enumerate(lines, 1):
        for pattern in VIOLATION_PATTERNS:
            if re.match(pattern, line):
                violations.append((i, f"Hardcoded constant: {line.strip()[:50]}..."))

    return violations


def check_imports(filepath: Path, project_root: Path) -> bool:
    """
    Check if file imports from shared module (when it should).

    Returns True if file has proper imports or doesn't need them.
    """
    relative_path = str(filepath.relative_to(project_root))

    # Skip allowed definition files
    if relative_path.replace("\\", "/") in ALLOWED_DEFINITION_FILES:
        return True

    if not filepath.exists():
        return True  # Skip non-existent files (checked elsewhere)

    content = filepath.read_text(encoding="utf-8")

    # Check if file uses any eval-related terms
    uses_eval_terms = any(term in content for term in [
        "EVAL_THRESHOLDS",
        "EVAL_COLORS",
        "ROW_BG_COLORS",
        "ROW_BG_THRESHOLDS",
        "LOW_VISITS_THRESHOLD",
        "HINTS_ALPHA",
    ])

    # If file uses eval terms, it should import from shared module
    if uses_eval_terms:
        return bool(re.search(EXPECTED_IMPORT, content))

    return True


def main():
    """Run all consistency checks."""
    project_root = Path(__file__).parent.parent

    print("=" * 60)
    print("Threshold Consistency Checker")
    print("=" * 60)
    print()

    all_violations = []
    import_issues = []

    for rel_path in FILES_TO_CHECK:
        filepath = project_root / rel_path

        # Check for hardcoded constants
        violations = check_file(filepath, project_root)
        if violations:
            all_violations.extend([(rel_path, ln, desc) for ln, desc in violations])

        # Check for proper imports
        if not check_imports(filepath, project_root):
            import_issues.append(rel_path)

    # Report results
    if all_violations:
        print("VIOLATIONS FOUND (hardcoded constants):")
        print("-" * 40)
        for file, line, desc in all_violations:
            print(f"  {file}:{line}: {desc}")
        print()

    if import_issues:
        print("MISSING IMPORTS:")
        print("-" * 40)
        for file in import_issues:
            print(f"  {file}: Should import from katrain_qt.common.eval_constants")
        print()

    # Also check that the shared module exists
    shared_module = project_root / "katrain_qt" / "common" / "eval_constants.py"
    if not shared_module.exists():
        print("ERROR: Shared module not found!")
        print(f"  Expected: {shared_module}")
        return 1
    else:
        print(f"Shared module exists: katrain_qt/common/eval_constants.py")

    print()

    if all_violations or import_issues:
        print("RESULT: FAIL")
        print(f"  {len(all_violations)} hardcoded constant(s)")
        print(f"  {len(import_issues)} missing import(s)")
        return 1
    else:
        print("RESULT: PASS")
        print("  All files use shared constants module")
        return 0


if __name__ == "__main__":
    sys.exit(main())
