"""Markdown/report formatting helpers (Phase 53, enhanced Phase 66)."""

from __future__ import annotations

import os
import re
import urllib.parse
from typing import Literal


def _ensure_balanced_brackets(s: str) -> str:
    """Ensure string has properly nested brackets (not just equal counts).

    "Balance" means:
    - Equal count of '[' and ']'
    - At no prefix does close_count > open_count (rejects "][")

    Algorithm: two-pass scan
    1. Remove unmatched ']' (close without prior open)
    2. Remove unmatched '[' (opens without subsequent close)

    E.g., "[Play..." -> "Play..." (removes orphan '[')
    E.g., "][P1]" -> "[P1]" (removes leading ']')
    """
    # Pass 1: remove unmatched closes (left to right)
    result = []
    open_count = 0
    for ch in s:
        if ch == "[":
            open_count += 1
            result.append(ch)
        elif ch == "]":
            if open_count > 0:
                open_count -= 1
                result.append(ch)
            # else: skip unmatched close
        else:
            result.append(ch)

    # Pass 2: remove unmatched opens (right to left)
    if open_count > 0:
        final = []
        excess_opens = open_count
        for ch in reversed(result):
            if ch == "[" and excess_opens > 0:
                excess_opens -= 1
                # skip this unmatched open
            else:
                final.append(ch)
        result = list(reversed(final))

    return "".join(result)


def _smart_truncate(name: str, max_len: int) -> str:
    """Truncate game name without breaking brackets.

    For "[Player1]vs[Player2]123456.sgf" format:
    - Parse [P1]vs[P2] pattern
    - Preserve both player names if possible
    - Never cut inside brackets [...]
    - Keep recognizable suffix

    For other formats: simple head/tail truncation.

    Args:
        name: Full game name
        max_len: Maximum length (must be >= 10 to produce meaningful output)

    Returns:
        Truncated name, GUARANTEED to:
        - Have balanced brackets in ALL cases
        - len(result) <= max_len in ALL branches
    """
    # Guard: very small max_len
    if max_len < 10:
        max_len = 10  # Minimum to produce meaningful output

    if len(name) <= max_len:
        return name

    def _finalize(s: str) -> str:
        """Apply bracket balancing and enforce max_len."""
        balanced = _ensure_balanced_brackets(s)
        # Final length guard - bracket removal may not be enough
        if len(balanced) > max_len:
            balanced = balanced[: max_len - 3] + "..."
            balanced = _ensure_balanced_brackets(balanced)
        return balanced

    # Try to parse [P1]vs[P2] pattern
    match = re.match(r"^(\[[^\]]+\])vs(\[[^\]]+\])(.*)$", name)
    if match:
        p1, p2, suffix = match.groups()
        players = f"{p1}vs{p2}"

        # Can we fit both players + minimal suffix?
        min_suffix_len = 6  # "...sgf" or similar
        if len(players) + min_suffix_len <= max_len:
            remaining = max_len - len(players) - 3  # 3 for "..."
            if remaining > 0:
                return _finalize(f"{players}...{suffix[-remaining:]}")
            return _finalize(f"{players}...")

        # Cannot fit both players - truncate P2 name
        p2_content = p2[1:-1]  # Remove brackets
        available_for_p2 = max_len - len(p1) - 4 - 6  # "vs[]" + "..."
        if available_for_p2 >= 2:
            truncated_p2 = f"[{p2_content[:available_for_p2]}...]"
            return _finalize(f"{p1}vs{truncated_p2}")

        # Last resort: truncate P1 too
        return _finalize(f"{name[: max_len - 3]}...")

    # Non-standard format: simple truncation preserving tail
    head_len = max(1, max_len - 8)  # Reserve 8 for "..." + 5-char tail
    tail_len = min(5, max_len - head_len - 3)
    raw = f"{name[:head_len]}...{name[-tail_len:]}" if tail_len > 0 else f"{name[: max_len - 3]}..."

    return _finalize(raw)


def format_game_display_label(
    name: str,
    *,
    max_len: int | None = None,
    escape_mode: Literal["table", "plain", "none"] = "none",
) -> str:
    """Generate display label for game name.

    Args:
        name: Full game name (filename or relative path)
        max_len: Maximum length (None = no truncation)
        escape_mode:
            "table" - for markdown table cells (escapes [ ] | and newlines)
            "plain" - for bullet lists (escapes [ ] only)
            "none" - raw output (no escaping)

    Returns:
        Formatted display label with balanced brackets

    Note:
        - Extracts basename if name contains path separators
        - Never produces unbalanced brackets
        - Double-escaping is caller's responsibility to avoid
    """
    # Extract basename if path
    display = os.path.basename(name) if os.sep in name or "/" in name else name

    # Truncate if needed
    if max_len is not None and len(display) > max_len:
        display = _smart_truncate(display, max_len)

    # Apply escaping
    if escape_mode == "table":
        display = escape_markdown_table_cell(display)
    elif escape_mode == "plain":
        display = escape_markdown_brackets(display)

    return display


def format_game_link_target(
    name: str,
    *,
    preserve_path: bool = True,
) -> str:
    """Generate link target from game name.

    Always uses full name (no truncation).

    Args:
        name: Full game name (filename or relative path)
        preserve_path: If True, preserve "/" in paths (for relative links).
                       If False, encode "/" as %2F (for opaque IDs).

    Returns:
        URL-encoded string suitable for markdown links

    Note:
        - This project uses relative paths for karte links, so preserve_path=True
        - safe="/-_." keeps path separators and common filename chars readable
    """
    safe_chars = "/-_." if preserve_path else "-_."
    return urllib.parse.quote(name, safe=safe_chars)


def truncate_game_name(name: str, max_len: int = 35) -> str:
    """Truncate game name preserving head (players) and tail (ID suffix).

    .. deprecated:: Phase 66
        Use :func:`format_game_display_label` instead, which provides
        proper bracket balancing and length guarantees.

    Example: "[ゆうだい03]vs[陈晨59902]1766534654030022615"
           → "[ゆうだい03]vs[陈...22615"

    Args:
        name: Full game name (typically rel_path or filename)
        max_len: Maximum length (default 35)

    Returns:
        Truncated name with "..." in middle if too long

    Warning:
        This function may produce unbalanced brackets. For new code,
        use format_game_display_label() with max_len parameter.
    """
    if len(name) <= max_len:
        return name
    head_len = 18
    tail_len = 5
    ellipsis = "..."
    return f"{name[:head_len]}{ellipsis}{name[-tail_len:]}"


def format_wr_gap(value: float | None) -> str:
    """Format WR Gap with clamping and precision.

    Args:
        value: winrateLost (0.0-1.0 range, can be negative due to search variance)

    Returns:
        Formatted string like "15.0%" or "-" if None
    """
    if value is None:
        return "-"
    # Clamp to [0, 1] - negative values occur when candidate has higher winrate
    # than root due to search variance; we display as 0.0%
    clamped = max(0.0, min(1.0, value))
    return f"{clamped * 100:.1f}%"


def make_markdown_link_target(from_dir: str, to_file: str) -> str:
    """Create markdown-compatible relative link target.

    - Computes relative path (with fallback for cross-drive on Windows)
    - Converts backslashes to forward slashes (Windows)
    - URL-encodes problematic characters (brackets, spaces, multibyte)

    Internally uses format_game_link_target() for consistent URL encoding.

    Args:
        from_dir: Directory containing the source markdown file
        to_file: Absolute path to the target file

    Returns:
        URL-encoded relative path suitable for markdown links,
        or just the filename if relpath fails (cross-drive)
    """
    try:
        rel = os.path.relpath(to_file, from_dir)
    except ValueError:
        # Cross-drive on Windows (e.g., D:\foo vs C:\bar)
        # Fallback to just the filename
        rel = os.path.basename(to_file)

    # Convert Windows backslashes to forward slashes
    rel = rel.replace("\\", "/")
    # Use unified format_game_link_target for URL encoding
    return format_game_link_target(rel, preserve_path=True)


def escape_markdown_brackets(text: str) -> str:
    """Escape brackets for markdown table cells.

    Prevents broken markdown when game names contain brackets like
    "[ゆうだい03]vs[陈晨...]" which would be interpreted as link syntax.

    Args:
        text: Text to escape (typically a truncated game name)

    Returns:
        Text with [ and ] escaped as \\[ and \\]

    Note:
        For full table cell safety, use escape_markdown_table_cell() instead.
    """
    return text.replace("[", "\\[").replace("]", "\\]")


def escape_markdown_table_cell(text: str | None) -> str:
    """Escape text for safe use in markdown table cells.

    Handles:
    - None → "-" (safe placeholder)
    - Brackets [ ] → \\[ \\] (prevents link syntax)
    - Pipes | → \\| (prevents column breaks)
    - Newlines → space (prevents row breaks)

    Args:
        text: Plain text to escape, or None

    Returns:
        Escaped text safe for markdown table cells

    Note:
        Do NOT use on text that intentionally contains markdown links.
        Use escape_markdown_brackets() for bracket-only escaping.
    """
    if text is None:
        return "-"
    result = text.replace("[", "\\[").replace("]", "\\]")
    result = result.replace("|", "\\|")
    result = result.replace("\n", " ").replace("\r", "")
    return result
