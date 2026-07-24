#!/usr/bin/env python3
"""Find dead-code candidates in ``katrain/``.

A symbol (top-level function or class) is considered a candidate when:
1. It does not start with ``_`` (i.e., it is public).
2. It is not re-exported via ``__all__``.
3. It is not referenced anywhere except its defining module.

References we look for:
- ``import <module>`` followed by ``<module>.<name>`` accesses
- ``from <module> import <name>`` (with optional alias)
- ``<name>`` used as a bare name in the same file (likely a re-use)

This script does NOT delete anything; it produces a Markdown report.
The human reviewer decides which entries to remove.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def to_module(path: Path) -> str:
    rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    if rel.endswith("/__init__.py"):
        return rel[: -len("/__init__.py")].replace("/", ".")
    if rel.endswith(".py"):
        return rel[:-3].replace("/", ".")
    return ""


def collect_definitions(path: Path) -> dict[str, list[str]]:
    """Return {module_name: [public_symbol_names]} for ``path``."""
    out: dict[str, list[str]] = {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return out
    module = to_module(path)
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            names.append(node.name)
    if names:
        out[module] = names
    return out


def collect_references(path: Path, symbols: set[str]) -> set[str]:
    """Return symbols from ``symbols`` referenced anywhere in ``path``.

    A reference can be:
    - a bare ``Name`` load (same-file re-use)
    - a ``from X import Y`` import
    - an ``Attribute`` access where the value is a known imported alias
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    referenced: set[str] = set()
    # Track imports that introduce aliases for these symbols
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in symbols:
                    referenced.add(alias.name)
                if alias.asname and alias.asname in symbols:
                    referenced.add(alias.asname)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                # aliased imports like ``import katrain.core.foo as foo``
                if alias.asname and alias.asname in symbols:
                    referenced.add(alias.asname)
                # unaliased imports: name is the last segment
                if not alias.asname and alias.name.split(".")[-1] in symbols:
                    referenced.add(alias.name.split(".")[-1])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in symbols:
            referenced.add(node.id)
    return referenced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(REPO_ROOT / "katrain"),
        help="Directory to scan (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "docs" / "dead_code_candidates.md"),
        help="Markdown output path (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    root = Path(args.root)

    # 1. Collect all public definitions per module
    definitions: dict[str, list[str]] = {}
    for path in root.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        if path.name == "__init__.py":
            continue
        definitions.update(collect_definitions(path))

    # 2. Subtract symbols re-exported via __all__
    for path in root.rglob("__init__.py"):
        module = to_module(path)
        if module not in definitions:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, ast.List):
                        names = {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
                        definitions[module] = [n for n in definitions[module] if n not in names]

    # 3. Scan all .py files in repo for references
    all_symbols = {s for names in definitions.values() for s in names}
    referenced: set[str] = set()
    scan_dirs = [REPO_ROOT / "katrain", REPO_ROOT / "tests", REPO_ROOT / "scripts", REPO_ROOT / "tools"]
    for scan_root in scan_dirs:
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            referenced |= collect_references(path, all_symbols)

    # 4. Find candidates: defined but never referenced
    candidates: list[tuple[str, str]] = []
    for module, names in definitions.items():
        for name in names:
            if name not in referenced:
                candidates.append((module, name))
    candidates.sort()

    # 5. Write Markdown report
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Dead Code Candidates")
    lines.append("")
    lines.append(
        f"Generated by `scripts/find_dead_code.py`. "
        f"Found {len(candidates)} public symbol(s) with no cross-module "
        "references."
    )
    lines.append("")
    lines.append(
        "Each entry shows the module path and symbol name. **These are "
        "candidates, not confirmed dead code.** Before removing:"
    )
    lines.append("")
    lines.append("1. Check that the symbol is not referenced via dynamic lookup")
    lines.append("   (e.g., `getattr`, `globals()`, plugin registration).")
    lines.append("2. Check that the symbol is not used in `.kv` files via id binding.")
    lines.append("3. Check `__all__` exports of sub-package init files.")
    lines.append("4. Run a full test pass after removal.")
    lines.append("")
    lines.append("| Module | Symbol |")
    lines.append("|--------|--------|")
    for module, name in candidates:
        lines.append(f"| `katrain/{module.replace('.', '/')}.py` | `{name}` |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {len(candidates)} candidates to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
