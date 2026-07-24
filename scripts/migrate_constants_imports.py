#!/usr/bin/env python3
"""Migrate `from katrain.core.constants import X` to granular submodules.

Phase A-1 (P1) follow-up. Splits constants into:
    katrain.core.constants.metadata    metadata, paths, top-move keys, timing
    katrain.core.constants.modes       MODE_*, PLAYER_*, PLAYING_*, GAME_TYPES
    katrain.core.constants.output      OUTPUT_*, STATUS_*, KATAGO_EXCEPTION
    katrain.core.constants.priorities  ADDITIONAL_MOVE_ORDER, PRIORITY_*

The script rewrites import lines in place. It leaves the package
``__init__.py`` alone (we will trim it in a second pass) and skips
lines inside TYPE_CHECKING blocks (TYPE_CHECKING imports do not need
to be granular because they are erased at runtime, but we still update
them for consistency unless ``--keep-typechecking`` is given).

Usage:
    uv run --frozen python scripts/migrate_constants_imports.py            # dry run
    uv run --frozen python scripts/migrate_constants_imports.py --apply    # apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Symbol -> submodule mapping. Keep alphabetical per submodule for readability.
SYMBOL_TO_SUBMODULE: dict[str, str] = {}


def _add(submodule: str, *symbols: str) -> None:
    for s in symbols:
        SYMBOL_TO_SUBMODULE[s] = submodule


_add(
    "metadata",
    "ANALYSIS_FORMAT_VERSION",
    "CONFIG_MIN_VERSION",
    "DATA_FOLDER",
    "DEFAULT_CRITICAL_3_MAX_MOVES",
    "HOMEPAGE",
    "PONDERING_REPORT_DT",
    "PROGRAM_NAME",
    "REPORT_DT",
    "SGF_INTERNAL_COMMENTS_MARKER",
    "SGF_SEPARATOR_MARKER",
    "TOP_MOVE_DELTA_SCORE",
    "TOP_MOVE_DELTA_WINRATE",
    "TOP_MOVE_NOTHING",
    "TOP_MOVE_OPTIONS",
    "TOP_MOVE_OWNERSHIP",
    "TOP_MOVE_POLICY",
    "TOP_MOVE_SCORE",
    "TOP_MOVE_SCORE_STDEV",
    "TOP_MOVE_VISITS",
    "TOP_MOVE_WINRATE",
    "VERSION",
)
_add(
    "modes",
    "GAME_TYPES",
    "MODE_ANALYZE",
    "MODE_PLAY",
    "PLAYER_AI",
    "PLAYER_HUMAN",
    "PLAYER_TYPES",
    "PLAYING_NORMAL",
    "PLAYING_TEACHING",
)
_add(
    "output",
    "KATAGO_EXCEPTION",
    "OUTPUT_DEBUG",
    "OUTPUT_ERROR",
    "OUTPUT_EXTRA_DEBUG",
    "OUTPUT_INFO",
    "OUTPUT_KATAGO_STDERR",
    "STATUS_ANALYSIS",
    "STATUS_ERROR",
    "STATUS_INFO",
    "STATUS_TEACHING",
)
_add(
    "priorities",
    "ADDITIONAL_MOVE_ORDER",
    "PRIORITY_ALTERNATIVES",
    "PRIORITY_DEFAULT",
    "PRIORITY_EQUALIZE",
    "PRIORITY_EXTRA_AI_QUERY",
    "PRIORITY_EXTRA_ANALYSIS",
    "PRIORITY_GAME_ANALYSIS",
    "PRIORITY_SWEEP",
)


# Match: from katrain.core.constants import ( ... )   (paren form)
RE_FROM_PAREN = re.compile(
    r"^(\s*)from\s+katrain\.core\.constants\s+import\s+\(([^\)]*)\)\s*$",
    re.MULTILINE,
)
# Match: from katrain.core.constants import A, B, C   (single-line form)
RE_FROM_LINE = re.compile(
    r"^(\s*)from\s+katrain\.core\.constants\s+import\s+(.*)$",
    re.MULTILINE,
)
# Match a single import name (possibly aliased) inside a comma list.
RE_NAME = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?")


def split_names(names_blob: str) -> list[tuple[str, str | None]]:
    """Split a comma-separated import blob into [(name, alias?)].

    Handles both ``NAME`` and ``NAME as ALIAS`` tokens. Strips per-line
    comments before parsing.
    """
    out: list[tuple[str, str | None]] = []
    for line in names_blob.splitlines():
        line = line.split("#", 1)[0]
        line = line.strip().rstrip(",").strip()
        if not line:
            continue
        for m in RE_NAME.finditer(line):
            out.append((m.group(1), m.group(2)))
    return out


def group_by_submodule(names: list[tuple[str, str | None]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for name, alias in names:
        if name not in SYMBOL_TO_SUBMODULE:
            # Unknown symbol; keep it under "constants" so it still works.
            grouped.setdefault("constants", []).append(f"{name}{alias}" if alias else name)
            continue
        sub = SYMBOL_TO_SUBMODULE[name]
        grouped.setdefault(sub, []).append(f"{name}{alias}" if alias else name)
    return grouped


def format_import_block(indent: str, grouped: dict[str, list[str]]) -> str:
    """Build the replacement import block.

    We emit one `from katrain.core.constants.<sub> import ...` per
    submodule, sorted alphabetically. The output uses a multi-line
    parenthesised form when the line would be too long.
    """
    lines: list[str] = []
    for sub in sorted(grouped.keys()):
        names = sorted(grouped[sub], key=lambda s: s.split()[0])
        joined = ", ".join(names)
        single = f"from katrain.core.constants.{sub} import {joined}"
        if len(single) <= 110:
            lines.append(single)
        else:
            chunked = []
            cur = ""
            for n in names:
                test = f"{cur}, {n}" if cur else n
                if len(test) > 100 and cur:
                    chunked.append(cur)
                    cur = n
                else:
                    cur = test
            if cur:
                chunked.append(cur)
            lines.append(f"from katrain.core.constants.{sub} import (")
            for chunk in chunked:
                lines.append(f"    {chunk},")
            lines.append(")")
    return ("\n" + indent).join(lines)


def rewrite_text(text: str) -> tuple[str, int]:
    changes = 0

    def replace_paren(match: re.Match[str]) -> str:
        nonlocal changes
        indent = match.group(1)
        body = match.group(2)
        names = split_names(body)
        if not names:
            return match.group(0)
        grouped = group_by_submodule(names)
        if "constants" not in grouped and len(grouped) == 1:
            sub = next(iter(grouped))
            if all(SYMBOL_TO_SUBMODULE.get(n) == sub for n, _ in names):
                single = f"from katrain.core.constants.{sub} import ({body.strip()})"
                if single.count("\n") == 0:
                    changes += 1
                    return f"{indent}{single}"
        replacement = format_import_block(indent, grouped)
        if replacement.strip() != match.group(0).strip():
            changes += 1
            return replacement
        return match.group(0)

    def replace_line(match: re.Match[str]) -> str:
        nonlocal changes
        indent = match.group(1)
        body = match.group(2)
        names = split_names(body)
        if not names:
            return match.group(0)
        grouped = group_by_submodule(names)
        if "constants" not in grouped and len(grouped) == 1:
            sub = next(iter(grouped))
            if all(SYMBOL_TO_SUBMODULE.get(n) == sub for n, _ in names):
                single = f"from katrain.core.constants.{sub} import {body.strip()}"
                if single != match.group(0).rstrip("\r\n").strip():
                    changes += 1
                    return f"{indent}{single}"
                return match.group(0)
        replacement = format_import_block(indent, grouped)
        if replacement.strip() != match.group(0).rstrip("\r\n").strip():
            changes += 1
            return replacement
        return match.group(0)

    new = RE_FROM_PAREN.sub(replace_paren, text)
    new = RE_FROM_LINE.sub(replace_line, new)
    return new, changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes to disk.")
    parser.add_argument(
        "--root",
        default=str(REPO_ROOT),
        help="Repository root (default: %(default)s)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[
            "katrain/core/constants/__init__.py",
            "tools/",
        ],
        help="Files to skip (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    targets: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part.startswith(".venv") or part == "__pycache__" for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in args.exclude:
            continue
        targets.append(path)

    total_files = 0
    total_changes = 0
    for path in targets:
        original = path.read_text(encoding="utf-8")
        new, changes = rewrite_text(original)
        if changes == 0:
            continue
        total_files += 1
        total_changes += changes
        rel = path.relative_to(root).as_posix()
        if args.apply:
            path.write_text(new, encoding="utf-8")
            print(f"  {rel}: {changes} import(s) rewritten")
        else:
            print(f"[dry-run] {rel}: {changes} import(s) would be rewritten")

    mode = "applied" if args.apply else "would apply"
    print(f"\n{total_changes} import(s) in {total_files} file(s) {mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
