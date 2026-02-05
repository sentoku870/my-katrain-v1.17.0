"""Batch analysis helper functions.

All functions are pure or take injected dependencies (no module-level imports
of heavy core modules like engine/game). This module is Kivy-independent.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine

# =============================================================================
# Constants
# =============================================================================

# Default timeout in seconds when no timeout is specified
DEFAULT_TIMEOUT_SECONDS: float = 600.0

# Common encodings for Go SGF files (Fox/Tygem often use GB18030, Nihon-Kiin uses CP932)
ENCODINGS_TO_TRY: tuple[str, ...] = (
    "utf-8",
    "utf-8-sig",
    "gb18030",
    "cp932",
    "euc-kr",
    "latin-1",
)

# Windows reserved filenames
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

# Generic player names to skip
_SKIP_NAMES = {"Black", "White", "黒", "白", "", "?", "Unknown", "不明"}


# =============================================================================
# Variable Visits helpers
# =============================================================================


def choose_visits_for_sgf(
    sgf_path: str,
    base_visits: int,
    jitter_pct: float = 0.0,
    deterministic: bool = True,
) -> int:
    """Choose visits for an SGF file with optional jitter.

    Args:
        sgf_path: Path to the SGF file (used for deterministic hashing)
        base_visits: Base visits count
        jitter_pct: Jitter percentage (0-25%), clamped for safety
        deterministic: If True, use path-based hash for reproducibility

    Returns:
        Visits count with jitter applied

    Examples:
        >>> choose_visits_for_sgf("game1.sgf", 500, jitter_pct=10, deterministic=True)
        475  # or similar, deterministic based on path
        >>> choose_visits_for_sgf("game1.sgf", 500, jitter_pct=0)
        500  # No jitter
    """
    if jitter_pct <= 0 or base_visits <= 0:
        return base_visits

    # Clamp jitter to max 25% for safety
    jitter_pct = min(jitter_pct, 25.0)

    # Calculate jitter range
    max_jitter = base_visits * (jitter_pct / 100.0)

    if deterministic:
        # Use md5 hash of normalized path for reproducibility
        # Normalize path: resolve, convert to forward slashes, lowercase
        normalized = os.path.normpath(os.path.abspath(sgf_path))
        normalized = normalized.replace("\\", "/").lower()
        hash_bytes = hashlib.md5(normalized.encode("utf-8")).digest()
        # Use first 4 bytes as unsigned int
        hash_val = int.from_bytes(hash_bytes[:4], byteorder="big")
        # Map to [-max_jitter, +max_jitter]
        jitter = (hash_val / 0xFFFFFFFF) * 2 * max_jitter - max_jitter
    else:
        import random

        jitter = random.uniform(-max_jitter, max_jitter)

    result = int(base_visits + jitter)
    # Ensure at least 1 visit
    return max(1, result)


# =============================================================================
# Points lost helpers (single source of truth for loss aggregation)
# =============================================================================


def get_canonical_loss(points_lost: float | None) -> float:
    """Return canonical loss value: max(0, points_lost) or 0 if None.

    Negative points_lost (gains from opponent mistakes) are clamped to 0.
    This matches Karte output semantics for consistency.

    Args:
        points_lost: Raw points lost value (may be None or negative)

    Returns:
        Canonical loss value >= 0.0
    """
    if points_lost is None:
        return 0.0
    return max(0.0, points_lost)


# Alias for backward compatibility with private name
_get_canonical_loss = get_canonical_loss


# =============================================================================
# Timeout input parsing helper
# =============================================================================


def parse_timeout_input(
    text: str,
    default: float = DEFAULT_TIMEOUT_SECONDS,
    log_cb: Callable[[str], None] | None = None,
) -> float | None:
    """Parse timeout input text from UI into a float or None.

    Args:
        text: Raw text from the timeout input field
        default: Default value when input is empty (default: 600.0)
        log_cb: Optional callback for logging warnings

    Returns:
        - None if text is "none" (case-insensitive, stripped)
        - default if text is empty
        - Parsed float value if valid number
        - default if parsing fails (with warning logged)

    Examples:
        >>> parse_timeout_input("")
        600.0
        >>> parse_timeout_input("None")
        None
        >>> parse_timeout_input("  NONE  ")
        None
        >>> parse_timeout_input("300")
        300.0
        >>> parse_timeout_input("abc")  # Returns default with warning
        600.0
    """
    stripped = text.strip()

    # Empty string -> default
    if not stripped:
        return default

    # "None" (case-insensitive) -> no timeout
    if stripped.lower() == "none":
        return None

    # Try to parse as float
    try:
        return float(stripped)
    except ValueError:
        if log_cb:
            log_cb(f"[WARNING] Invalid timeout value '{text}', using default {default}s")
        return default


# =============================================================================
# Safe file write helpers (A3: I/O error handling)
# =============================================================================


def safe_write_file(
    path: str,
    content: str,
    file_kind: str,
    sgf_id: str,
    log_cb: Callable[[str], None] | None = None,
) -> Any | None:
    """Safely write content to file with directory creation and error handling.

    Args:
        path: Target file path
        content: Content to write
        file_kind: Type of file ("karte", "summary", "analyzed_sgf")
        sgf_id: Identifier for error reporting (SGF filename or player name)
        log_cb: Optional logging callback

    Returns:
        None on success, WriteError on failure

    Note:
        Returns WriteError from models module. Import is deferred to avoid
        circular imports at module load time.
    """
    from katrain.core.batch.models import WriteError

    def log(msg: str) -> None:
        if log_cb:
            log_cb(msg)

    try:
        # Ensure parent directory exists (pathlib handles Windows paths correctly)
        parent = Path(path).parent
        parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return None  # Success

    except (OSError, PermissionError, UnicodeEncodeError) as e:
        error = WriteError(
            file_kind=file_kind,
            sgf_id=sgf_id,
            target_path=path,
            exception_type=type(e).__name__,
            message=str(e),
        )
        log(f"  ERROR writing {file_kind}: {e}")
        return error

    except Exception as e:  # noqa: BLE001
        # Catch-all for unexpected errors
        error = WriteError(
            file_kind=file_kind,
            sgf_id=sgf_id,
            target_path=path,
            exception_type=type(e).__name__,
            message=str(e),
        )
        log(f"  ERROR writing {file_kind} (unexpected): {e}")
        return error


# Alias for backward compatibility with private name
_safe_write_file = safe_write_file


# =============================================================================
# Encoding fallback: Try multiple encodings for SGF files
# =============================================================================


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


# =============================================================================
# File discovery: Recursive search with relative path preservation
# =============================================================================


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


# =============================================================================
# Engine polling helper
# =============================================================================


def wait_for_analysis(engine: KataGoEngine, timeout: float = 300.0, poll_interval: float = 0.5) -> bool:
    """Wait for the engine to finish all pending analysis queries.

    Args:
        engine: KataGo engine instance (or any engine with is_idle() method)
        timeout: Maximum time to wait in seconds
        poll_interval: Time between checks in seconds

    Returns:
        True if analysis completed, False if timeout
    """
    start_time = time.time()
    while not engine.is_idle():
        if time.time() - start_time > timeout:
            return False
        time.sleep(poll_interval)
    return True


# =============================================================================
# Filename sanitization helpers
# =============================================================================


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """Sanitize player name for use in filename.

    Handles:
        - Invalid characters (<>:"/\\|?*)
        - Whitespace normalization
        - Windows reserved names (CON, PRN, NUL, etc.)
        - Empty result fallback
        - Length truncation

    Args:
        name: Original player name
        max_length: Maximum filename length (default 50)

    Returns:
        Safe filename string
    """
    if not name:
        return "unknown"

    # Remove/replace invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', "_", name)
    # Normalize whitespace (including full-width spaces)
    safe = re.sub(r"\s+", "_", safe)
    # Remove leading/trailing dots and underscores
    safe = safe.strip("._")

    # Check for Windows reserved names (case-insensitive)
    if safe.upper() in _WINDOWS_RESERVED:
        safe = f"_{safe}_"

    # Truncate to max length
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip("_")

    # Strip trailing dots and spaces again after truncation (Windows requirement)
    safe = safe.rstrip(". ")

    # Final fallback if empty
    if not safe:
        return "unknown"

    return safe


# Alias for backward compatibility with private name
_sanitize_filename = sanitize_filename


def get_unique_filename(base_path: str, extension: str = ".md") -> str:
    """Generate unique filename by adding suffix if collision exists.

    Args:
        base_path: Full path without extension
        extension: File extension including dot

    Returns:
        Unique file path
    """
    path = base_path + extension
    if not os.path.exists(path):
        return path

    counter = 1
    while True:
        path = f"{base_path}_{counter}{extension}"
        if not os.path.exists(path):
            return path
        counter += 1
        if counter > 100:  # Safety limit
            hash_suffix = hashlib.md5(base_path.encode()).hexdigest()[:6]
            return f"{base_path}_{hash_suffix}{extension}"


# Alias for backward compatibility with private name
_get_unique_filename = get_unique_filename


def normalize_player_name(name: str) -> str:
    """Normalize player name for grouping.

    Uses NFKC normalization and collapses whitespace.
    This is the single source of truth for name normalization.

    Args:
        name: Original player name

    Returns:
        Normalized player name
    """
    name = name.strip()
    name = unicodedata.normalize("NFKC", name)
    # Collapse multiple spaces
    name = " ".join(name.split())
    return name


# Alias for backward compatibility with private name
_normalize_player_name = normalize_player_name


# =============================================================================
# UI validation helpers (moved from batch_core.py)
# =============================================================================


def safe_int(text: str, default: int | None = None) -> int | None:
    """Parse integer safely, returning default on invalid input.

    Note: Does not log warnings to avoid noise from frequent UI validation.

    Args:
        text: Text to parse
        default: Value to return if parsing fails

    Returns:
        Parsed integer or default value
    """
    text = text.strip() if text else ""
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


# Alias for backward compatibility with private name
_safe_int = safe_int


def needs_leela_karte_warning(analysis_engine: str, generate_karte: bool) -> bool:
    """Check if Leela+karte warning should be displayed.

    Phase 36 MVP restriction: Leela batch analysis does not fully support
    karte generation. This function determines if a warning should be shown
    to the user when they select Leela with karte generation enabled.

    Args:
        analysis_engine: Selected analysis engine ("katago" or "leela")
        generate_karte: Whether karte generation is enabled

    Returns:
        True if warning should be displayed (Leela + karte enabled)
        False otherwise

    Example:
        >>> needs_leela_karte_warning("leela", generate_karte=True)
        True
        >>> needs_leela_karte_warning("leela", generate_karte=False)
        False
        >>> needs_leela_karte_warning("katago", generate_karte=True)
        False
    """
    return analysis_engine == "leela" and generate_karte


# =============================================================================
# Markdown/Report Formatting Helpers (Phase 53, enhanced Phase 66)
# =============================================================================

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
