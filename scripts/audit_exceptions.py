#!/usr/bin/env python3
"""Audit broad exception handlers using AST analysis.

Detects:
- except Exception / except BaseException
- except builtins.Exception (ast.Attribute)
- bare except:
- Tuples containing any of the above

Output paths use forward slashes (POSIX style) for cross-platform consistency.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


# Broad exception names to detect
BROAD_EXCEPTIONS = frozenset({"Exception", "BaseException"})

# Regex for noqa detection (case-insensitive, flexible spacing)
NOQA_PATTERN = re.compile(r"noqa\s*:\s*ble001", re.IGNORECASE)


@dataclass
class BroadExceptEntry:
    """Single broad exception handler entry."""

    file: str
    line: int
    context: str  # e.g., "ClassName.method_name" or "<module>"
    pattern: str  # e.g., "except Exception", "bare except"
    has_noqa: bool
    noqa_reason: str


@dataclass
class SkippedFile:
    """File that could not be parsed."""

    file: str
    reason: str  # "SyntaxError" or "UnicodeDecodeError"
    detail: str  # Error message


@dataclass
class AuditResult:
    """Complete audit output."""

    scanned_files: int
    skipped_files: list[SkippedFile] = field(default_factory=list)
    total: int = 0
    with_noqa: int = 0
    without_noqa: int = 0
    entries: list[BroadExceptEntry] = field(default_factory=list)


def is_broad_exception_name(node: ast.expr) -> tuple[bool, str]:
    """Check if an AST node represents a broad exception type.

    Returns (is_broad, name_string).
    Handles both ast.Name and ast.Attribute (e.g., builtins.Exception).
    """
    if isinstance(node, ast.Name):
        if node.id in BROAD_EXCEPTIONS:
            return True, node.id
    elif isinstance(node, ast.Attribute):
        # Handle qualified names like builtins.Exception, exceptions.Exception
        if node.attr in BROAD_EXCEPTIONS:
            # Reconstruct the full qualified name
            parts = [node.attr]
            current = node.value
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return True, ".".join(reversed(parts))
    return False, ""


def get_exception_pattern(handler: ast.ExceptHandler) -> tuple[bool, str]:
    """Determine if handler catches broad exceptions and return pattern string."""
    if handler.type is None:
        return True, "bare except"

    if isinstance(handler.type, (ast.Name, ast.Attribute)):
        is_broad, name = is_broad_exception_name(handler.type)
        if is_broad:
            return True, f"except {name}"

    elif isinstance(handler.type, ast.Tuple):
        # Check each element in the tuple
        names = []
        has_broad = False
        for elt in handler.type.elts:
            is_broad, name = is_broad_exception_name(elt)
            if is_broad:
                has_broad = True
            if isinstance(elt, ast.Name):
                names.append(elt.id)
            elif isinstance(elt, ast.Attribute):
                # Reconstruct qualified name
                parts = [elt.attr]
                current = elt.value
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                names.append(".".join(reversed(parts)))
            else:
                names.append("?")
        if has_broad:
            return True, f"except ({', '.join(names)})"

    return False, ""


def extract_noqa_reason(line_text: str) -> str:
    """Extract the reason from a noqa comment, handling edge cases safely.

    Expected format: # noqa: BLE001 - reason text here
    Also handles: # noqa:BLE001 - reason, # NOQA: ble001 - reason, etc.
    """
    # Find the noqa marker position
    match = NOQA_PATTERN.search(line_text.lower())
    if not match:
        return ""

    # Get everything after the match
    after_noqa = line_text[match.end() :]

    # Look for " - " separator
    if " - " not in after_noqa:
        return ""

    reason_part = after_noqa.split(" - ", 1)[1]

    # Clean up: remove trailing comments and whitespace
    # Stop at any new # that might indicate another comment
    if " #" in reason_part:
        reason_part = reason_part.split(" #")[0]

    return reason_part.strip()


class ExceptVisitor(ast.NodeVisitor):
    """AST visitor that finds broad exception handlers with full context."""

    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self.context_stack: list[str] = []
        self.results: list[BroadExceptEntry] = []
        self.file_path: str = ""

    def get_context(self) -> str:
        """Return fully qualified context string."""
        if not self.context_stack:
            return "<module>"
        return ".".join(self.context_stack)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.context_stack.append(node.name)
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.context_stack.append(node.name)
        self.generic_visit(node)
        self.context_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        is_broad, pattern = get_exception_pattern(node)

        if is_broad:
            line_text = ""
            if 0 < node.lineno <= len(self.source_lines):
                line_text = self.source_lines[node.lineno - 1]

            # Check for noqa comment (case-insensitive)
            has_noqa = bool(NOQA_PATTERN.search(line_text.lower()))
            noqa_reason = extract_noqa_reason(line_text) if has_noqa else ""

            self.results.append(
                BroadExceptEntry(
                    file=self.file_path,
                    line=node.lineno,
                    context=self.get_context(),
                    pattern=pattern,
                    has_noqa=has_noqa,
                    noqa_reason=noqa_reason,
                )
            )

        self.generic_visit(node)


def analyze_file(
    path: Path, base_dir: Path
) -> tuple[list[BroadExceptEntry], SkippedFile | None]:
    """Analyze a single Python file for broad exception handlers.

    Returns (entries, skipped_info). skipped_info is None if parsing succeeded.
    """
    # Use POSIX-style paths (forward slashes) for cross-platform consistency
    relative_path = path.relative_to(base_dir).as_posix()

    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        return [], SkippedFile(
            file=relative_path,
            reason="UnicodeDecodeError",
            detail=str(e),
        )

    try:
        tree = ast.parse(source, filename=relative_path)
    except SyntaxError as e:
        return [], SkippedFile(
            file=relative_path,
            reason="SyntaxError",
            detail=f"line {e.lineno}: {e.msg}",
        )

    lines = source.splitlines()
    visitor = ExceptVisitor(lines)
    visitor.file_path = relative_path
    visitor.visit(tree)

    return visitor.results, None


def main() -> int:
    base_dir = Path.cwd()
    katrain_dir = base_dir / "katrain"

    if not katrain_dir.exists():
        print("Error: katrain/ directory not found", file=sys.stderr)
        return 1

    result = AuditResult(scanned_files=0)
    py_files = sorted(katrain_dir.rglob("*.py"))

    for py_file in py_files:
        entries, skipped = analyze_file(py_file, base_dir)
        result.scanned_files += 1

        if skipped:
            result.skipped_files.append(skipped)
            print(
                f"WARNING: Skipped {skipped.file}: {skipped.reason} - {skipped.detail}",
                file=sys.stderr,
            )
        else:
            result.entries.extend(entries)

    result.total = len(result.entries)
    result.with_noqa = sum(1 for e in result.entries if e.has_noqa)
    result.without_noqa = result.total - result.with_noqa

    # Convert to JSON-serializable format
    output = {
        "scanned_files": result.scanned_files,
        "skipped_files": [asdict(s) for s in result.skipped_files],
        "total": result.total,
        "with_noqa": result.with_noqa,
        "without_noqa": result.without_noqa,
        "entries": [asdict(e) for e in result.entries],
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))

    # Exit with error if any files were skipped
    if result.skipped_files:
        print(
            f"\nERROR: {len(result.skipped_files)} file(s) skipped - fix before proceeding",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
