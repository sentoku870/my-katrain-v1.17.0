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
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple

if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine

# =============================================================================
# Constants
# =============================================================================

# Default timeout in seconds when no timeout is specified
DEFAULT_TIMEOUT_SECONDS: float = 600.0

# Common encodings for Go SGF files (Fox/Tygem often use GB18030, Nihon-Kiin uses CP932)
ENCODINGS_TO_TRY: Tuple[str, ...] = (
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


def get_canonical_loss(points_lost: Optional[float]) -> float:
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
    log_cb: Optional[Callable[[str], None]] = None,
) -> Optional[float]:
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
    log_cb: Optional[Callable[[str], None]] = None,
) -> Optional[Any]:
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


def read_sgf_with_fallback(
    sgf_path: str, log_cb: Optional[Callable[[str], None]] = None
) -> Tuple[Optional[str], str]:
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


def parse_sgf_with_fallback(
    sgf_path: str, log_cb: Optional[Callable[[str], None]] = None
) -> Optional[Any]:
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

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".sgf", delete=False, encoding="utf-8"
            ) as tmp:
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
    log_cb: Optional[Callable[[str], None]] = None,
) -> List[Tuple[str, str]]:
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

    sgf_files: List[Tuple[str, str]] = []
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


def collect_sgf_files(input_dir: str, skip_analyzed: bool = False) -> List[str]:
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


def wait_for_analysis(
    engine: KataGoEngine, timeout: float = 300.0, poll_interval: float = 0.5
) -> bool:
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
        safe = safe[: max_length].rstrip("_")

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


def safe_int(text: str, default: Optional[int] = None) -> Optional[int]:
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
