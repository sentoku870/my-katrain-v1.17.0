"""SGF I/O with encoding fallback and analysis detection."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

# Common encodings for Go SGF files (Fox/Tygem often use GB18030, Nihon-Kiin uses CP932)
ENCODINGS_TO_TRY: tuple[str, ...] = (
    "utf-8",
    "utf-8-sig",
    "gb18030",
    "cp932",
    "euc-kr",
    "latin-1",
)


def read_sgf_with_fallback(sgf_path: str, log_cb: Callable[[str], None] | None = None) -> tuple[str | None, str]:
    """Read an SGF file with encoding fallback.

    Args:
        sgf_path: Path to the SGF file
        log_cb: Optional callback for logging messages

    Returns:
        Tuple of (content_string, encoding_used) or (None, "") on failure
    """

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    # First try to read as bytes
    try:
        with open(sgf_path, "rb") as f:
            raw_bytes = f.read()
    except Exception as e:  # noqa: BLE001
        log(f"    Error reading file: {e}")
        return None, ""

    # Try each encoding
    for encoding in ENCODINGS_TO_TRY:
        try:
            content = raw_bytes.decode(encoding)
            # Basic sanity check: SGF should contain parentheses
            if "(" in content and ")" in content:
                if encoding != "utf-8":
                    log(f"    Using encoding: {encoding}")
                return content, encoding
        except (UnicodeDecodeError, LookupError):
            continue

    log(f"    Failed to decode with any encoding: {ENCODINGS_TO_TRY}")
    return None, ""


def parse_sgf_with_fallback(sgf_path: str, log_cb: Callable[[str], None] | None = None) -> Any | None:
    """Parse an SGF file with encoding fallback.

    Args:
        sgf_path: Path to the SGF file
        log_cb: Optional callback for logging messages

    Returns:
        Parsed SGF root node, or None on failure

    Note:
        This function imports KaTrainSGF at call time to avoid module-level
        dependencies on heavy core modules.
    """
    from katrain.core.game import KaTrainSGF

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    content, encoding = read_sgf_with_fallback(sgf_path, log_cb)
    if content is None:
        return None

    try:
        # KaTrainSGF.parse_file reads from file, so we need to use parse() with string
        if hasattr(KaTrainSGF, "parse"):
            return KaTrainSGF.parse(content)
        else:
            # Fallback: write to temp file if only parse_file is available
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".sgf", delete=False, encoding="utf-8") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                return KaTrainSGF.parse_file(tmp_path)
            finally:
                os.unlink(tmp_path)
    except Exception as e:  # noqa: BLE001
        log(f"    Parse error: {e}")
        return None


def has_analysis(sgf_path: str) -> bool:
    """Check if an SGF file already contains KaTrain analysis (KT property).

    Args:
        sgf_path: Path to the SGF file

    Returns:
        True if the file contains analysis data, False otherwise
    """
    from katrain.core.game import KaTrainSGF

    try:
        root = KaTrainSGF.parse_file(sgf_path)
        # Walk through all nodes to check for analysis
        nodes_to_check = [root]
        while nodes_to_check:
            node = nodes_to_check.pop()
            # Check if node has analysis_from_sgf (loaded from KT property)
            if hasattr(node, "analysis_from_sgf") and node.analysis_from_sgf:
                return True
            nodes_to_check.extend(node.children)
        return False
    except Exception:  # noqa: BLE001
        return False
