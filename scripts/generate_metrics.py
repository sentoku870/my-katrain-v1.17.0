#!/usr/bin/env python
"""Module metrics auto-generation script.

PR #134: Phase B6 - Metrics auto-generation

This script generates metrics about the KaTrain codebase:
- Line counts per module
- Test counts
- Module structure overview

Usage:
    python scripts/generate_metrics.py
    python scripts/generate_metrics.py --json
    python scripts/generate_metrics.py --markdown
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


# Calculate project root from script location
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
KATRAIN_DIR = PROJECT_ROOT / "katrain"
TESTS_DIR = PROJECT_ROOT / "tests"


def count_lines(path: Path) -> int:
    """Count non-empty lines in a file."""
    try:
        with open(path, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def get_python_files(directory: Path) -> List[Path]:
    """Get all Python files in a directory recursively."""
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.py"))


def collect_module_metrics(base_dir: Path) -> Dict[str, Dict]:
    """Collect metrics for all modules under a base directory."""
    metrics = {}

    for py_file in get_python_files(base_dir):
        if "__pycache__" in str(py_file):
            continue

        rel_path = py_file.relative_to(PROJECT_ROOT)
        lines = count_lines(py_file)

        # Group by top-level module
        parts = rel_path.parts
        if len(parts) >= 2:
            module = parts[1]  # e.g., "core", "gui"
        else:
            module = "root"

        if module not in metrics:
            metrics[module] = {"files": {}, "total_lines": 0}

        metrics[module]["files"][str(rel_path)] = lines
        metrics[module]["total_lines"] += lines

    return metrics


def count_tests() -> Tuple[int, int]:
    """Count number of test files and test functions.

    Returns:
        (test_file_count, test_function_count)
    """
    test_files = list(get_python_files(TESTS_DIR))
    test_file_count = len([f for f in test_files if f.name.startswith("test_")])

    # Try to get test count from pytest
    # Try multiple commands: uv run pytest, python -m pytest
    commands_to_try = [
        ["uv", "run", "pytest", "--collect-only", "-q", str(TESTS_DIR)],
        [sys.executable, "-m", "pytest", "--collect-only", "-q", str(TESTS_DIR)],
    ]

    for cmd in commands_to_try:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(PROJECT_ROOT),
                timeout=60,
            )
            # Count lines with "::" which indicate test items
            test_count = len([
                line for line in result.stdout.split("\n")
                if "::" in line and not line.startswith("=")
            ])
            if test_count > 0:
                return test_file_count, test_count
        except Exception:
            continue

    return test_file_count, 0


def get_key_modules() -> Dict[str, int]:
    """Get line counts for key modules (Phase B4/B5 targets)."""
    key_files = [
        "katrain/core/game.py",
        "katrain/core/ai.py",
        "katrain/core/ai_strategies_base.py",
        "katrain/core/engine.py",
        "katrain/core/analysis/logic.py",
        "katrain/core/analysis/logic_loss.py",
        "katrain/core/analysis/logic_importance.py",
        "katrain/core/analysis/logic_quiz.py",
        "katrain/core/analysis/models.py",
        "katrain/core/analysis/presentation.py",
        "katrain/__main__.py",
    ]

    result = {}
    for file_path in key_files:
        full_path = PROJECT_ROOT / file_path
        if full_path.exists():
            result[file_path] = count_lines(full_path)

    return result


def generate_metrics() -> Dict:
    """Generate all metrics."""
    module_metrics = collect_module_metrics(KATRAIN_DIR)
    test_file_count, test_count = count_tests()
    key_modules = get_key_modules()

    # Calculate totals
    total_lines = sum(m["total_lines"] for m in module_metrics.values())
    total_files = sum(len(m["files"]) for m in module_metrics.values())

    return {
        "summary": {
            "total_lines": total_lines,
            "total_files": total_files,
            "test_files": test_file_count,
            "test_count": test_count,
        },
        "key_modules": key_modules,
        "by_module": {
            name: {"total_lines": data["total_lines"], "file_count": len(data["files"])}
            for name, data in sorted(module_metrics.items())
        },
        "detailed": module_metrics,
    }


def format_markdown(metrics: Dict) -> str:
    """Format metrics as Markdown."""
    lines = []
    lines.append("# KaTrain Code Metrics")
    lines.append("")

    # Summary
    s = metrics["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Lines**: {s['total_lines']:,}")
    lines.append(f"- **Total Files**: {s['total_files']}")
    lines.append(f"- **Test Files**: {s['test_files']}")
    lines.append(f"- **Test Count**: {s['test_count']}")
    lines.append("")

    # Key modules
    lines.append("## Key Modules (Phase B4/B5 Targets)")
    lines.append("")
    lines.append("| Module | Lines |")
    lines.append("|--------|------:|")
    for path, line_count in metrics["key_modules"].items():
        lines.append(f"| `{path}` | {line_count:,} |")
    lines.append("")

    # By module
    lines.append("## Lines by Module")
    lines.append("")
    lines.append("| Module | Files | Lines |")
    lines.append("|--------|------:|------:|")
    for name, data in metrics["by_module"].items():
        lines.append(f"| {name} | {data['file_count']} | {data['total_lines']:,} |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate KaTrain code metrics")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--markdown", action="store_true", help="Output as Markdown")
    parser.add_argument("--detailed", action="store_true", help="Include detailed file list")
    args = parser.parse_args()

    metrics = generate_metrics()

    if not args.detailed:
        # Remove detailed section for cleaner output
        del metrics["detailed"]

    if args.json:
        print(json.dumps(metrics, indent=2))
    elif args.markdown:
        print(format_markdown(metrics))
    else:
        # Default: human-readable summary
        s = metrics["summary"]
        print(f"KaTrain Code Metrics")
        print(f"====================")
        print(f"Total Lines:  {s['total_lines']:,}")
        print(f"Total Files:  {s['total_files']}")
        print(f"Test Files:   {s['test_files']}")
        print(f"Test Count:   {s['test_count']}")
        print()
        print("Key Modules:")
        for path, line_count in metrics["key_modules"].items():
            print(f"  {path}: {line_count:,} lines")
        print()
        print("Use --json or --markdown for detailed output.")


if __name__ == "__main__":
    main()
