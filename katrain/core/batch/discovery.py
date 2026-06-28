"""SGF file discovery (recursive + non-recursive)."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from katrain.core.batch.sgf_io import has_analysis


def collect_sgf_files_recursive(
    input_dir: str,
    skip_analyzed: bool = False,
    log_cb: Callable[[str], None] | None = None,
) -> list[tuple[str, str]]:
    """Collect all SGF files from the input directory recursively.

    Args:
        input_dir: Directory to search for SGF files
        skip_analyzed: If True, skip files that already have analysis
        log_cb: Optional callback for logging messages

    Returns:
        List of tuples (absolute_path, relative_path) for each file to process
    """

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    sgf_files: list[tuple[str, str]] = []
    input_path = Path(input_dir).resolve()

    # Extensions to look for (case-insensitive)
    extensions = {".sgf", ".gib", ".ngf"}

    # Walk through all subdirectories
    for root, _dirs, files in os.walk(input_path):
        root_path = Path(root)
        for file_name in files:
            file_path = root_path / file_name
            ext = file_path.suffix.lower()

            if ext not in extensions:
                continue

            abs_path = str(file_path)
            rel_path = str(file_path.relative_to(input_path))

            if skip_analyzed and has_analysis(abs_path):
                log(f"Skipping (already analyzed): {rel_path}")
                continue

            sgf_files.append((abs_path, rel_path))

    # Sort by relative path for consistent ordering
    sgf_files.sort(key=lambda x: x[1])
    return sgf_files


def collect_sgf_files(input_dir: str, skip_analyzed: bool = False) -> list[str]:
    """Collect all SGF files from the input directory (non-recursive, for CLI compatibility).

    Args:
        input_dir: Directory to search for SGF files
        skip_analyzed: If True, skip files that already have analysis

    Returns:
        List of SGF file paths to process
    """
    sgf_files = set()  # Use set to avoid duplicates on case-insensitive filesystems
    input_path = Path(input_dir)

    # Collect SGF files (use lowercase glob, Windows is case-insensitive)
    for sgf_file in input_path.glob("*.[sS][gG][fF]"):
        file_path = str(sgf_file)
        if skip_analyzed and has_analysis(file_path):
            print(f"Skipping (already analyzed): {sgf_file.name}")
            continue
        sgf_files.add(file_path)

    # Also check .gib and .ngf formats
    for sgf_file in input_path.glob("*.[gG][iI][bB]"):
        sgf_files.add(str(sgf_file))
    for sgf_file in input_path.glob("*.[nN][gG][fF]"):
        sgf_files.add(str(sgf_file))

    return sorted(sgf_files)
