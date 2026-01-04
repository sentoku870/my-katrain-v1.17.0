#!/usr/bin/env python
"""
Headless batch analyzer for KaTrain SGF files.

This tool processes a folder of SGF files and saves them in the same
"analyzed SGF" format that KaTrain uses (with KT property).

Usage:
    python -m katrain.tools.batch_analyze_sgf --input-dir ./sgf --output-dir ./analyzed
    python -m katrain.tools.batch_analyze_sgf --input-dir ./sgf --visits 500 --skip-if-already-analyzed

Requirements:
    - KataGo engine must be configured in KaTrain settings
    - Uses existing KaTrain config for engine settings
"""

# Disable Kivy's argument parser before importing any Kivy-related modules
import os
os.environ["KIVY_NO_ARGS"] = "1"

import argparse
import hashlib
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple, Union

# KaTrain imports (these may import Kivy indirectly)
from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import KataGoEngine
from katrain.core.game import Game, KaTrainSGF
from katrain.core.constants import OUTPUT_INFO, OUTPUT_ERROR, OUTPUT_DEBUG
from katrain.core.eval_metrics import (
    MistakeCategory,
    PositionDifficulty,
    REASON_TAG_LABELS,
    get_reason_tag_label,
    SKILL_PRESETS,
    DEFAULT_SKILL_PRESET,
    RELIABILITY_VISITS_THRESHOLD,
    get_phase_thresholds,
    AutoConfidence,
    AutoRecommendation,
    PRESET_ORDER,
    _distance_from_range,
    recommend_auto_strictness,
    SKILL_PRESET_LABELS,
    CONFIDENCE_LABELS,
)


# ---------------------------------------------------------------------------
# Variable Visits helpers
# ---------------------------------------------------------------------------

def choose_visits_for_sgf(
    sgf_path: str,
    base_visits: int,
    jitter_pct: float = 0.0,
    deterministic: bool = True,
) -> int:
    """
    Choose visits for an SGF file with optional jitter.

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


# ---------------------------------------------------------------------------
# Points lost helpers (single source of truth for loss aggregation)
# ---------------------------------------------------------------------------

def _get_canonical_loss(points_lost: Optional[float]) -> float:
    """
    Return canonical loss value: max(0, points_lost) or 0 if None.

    Negative points_lost (gains from opponent mistakes) are clamped to 0.
    This matches Karte output semantics for consistency.
    """
    if points_lost is None:
        return 0.0
    return max(0.0, points_lost)


# ---------------------------------------------------------------------------
# Timeout input parsing helper
# ---------------------------------------------------------------------------

# Default timeout in seconds when no timeout is specified
DEFAULT_TIMEOUT_SECONDS: float = 600.0


def parse_timeout_input(
    text: str,
    default: float = DEFAULT_TIMEOUT_SECONDS,
    log_cb: Optional[Callable[[str], None]] = None,
) -> Optional[float]:
    """
    Parse timeout input text from UI into a float or None.

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


# ---------------------------------------------------------------------------
# Safe file write helpers (A3: I/O error handling)
# ---------------------------------------------------------------------------

def _safe_write_file(
    path: str,
    content: str,
    file_kind: str,
    sgf_id: str,
    log_cb: Optional[Callable[[str], None]] = None,
) -> Optional["WriteError"]:
    """
    Safely write content to file with directory creation and error handling.

    Args:
        path: Target file path
        content: Content to write
        file_kind: Type of file ("karte", "summary", "analyzed_sgf")
        sgf_id: Identifier for error reporting (SGF filename or player name)
        log_cb: Optional logging callback

    Returns:
        None on success, WriteError on failure
    """
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

    except Exception as e:
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


# ---------------------------------------------------------------------------
# Encoding fallback: Try multiple encodings for SGF files
# ---------------------------------------------------------------------------

# Common encodings for Go SGF files (Fox/Tygem often use GB18030, Nihon-Kiin uses CP932)
ENCODINGS_TO_TRY = ["utf-8", "utf-8-sig", "gb18030", "cp932", "euc-kr", "latin-1"]


def read_sgf_with_fallback(sgf_path: str, log_cb: Optional[Callable[[str], None]] = None) -> Tuple[Optional[str], str]:
    """
    Read an SGF file with encoding fallback.

    Args:
        sgf_path: Path to the SGF file
        log_cb: Optional callback for logging messages

    Returns:
        Tuple of (content_string, encoding_used) or (None, "") on failure
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)

    # First try to read as bytes
    try:
        with open(sgf_path, "rb") as f:
            raw_bytes = f.read()
    except Exception as e:
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
    sgf_path: str,
    log_cb: Optional[Callable[[str], None]] = None
) -> Optional[any]:
    """
    Parse an SGF file with encoding fallback.

    Args:
        sgf_path: Path to the SGF file
        log_cb: Optional callback for logging messages

    Returns:
        Parsed SGF root node, or None on failure
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)

    content, encoding = read_sgf_with_fallback(sgf_path, log_cb)
    if content is None:
        return None

    try:
        # KaTrainSGF.parse_file reads from file, so we need to use parse() with string
        # Check if KaTrainSGF has a string parse method
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
    except Exception as e:
        log(f"    Parse error: {e}")
        return None


def has_analysis(sgf_path: str) -> bool:
    """
    Check if an SGF file already contains KaTrain analysis (KT property).

    Args:
        sgf_path: Path to the SGF file

    Returns:
        True if the file contains analysis data, False otherwise
    """
    try:
        root = KaTrainSGF.parse_file(sgf_path)
        # Walk through all nodes to check for analysis
        nodes_to_check = [root]
        while nodes_to_check:
            node = nodes_to_check.pop()
            # Check if node has analysis_from_sgf (loaded from KT property)
            if hasattr(node, 'analysis_from_sgf') and node.analysis_from_sgf:
                return True
            nodes_to_check.extend(node.children)
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# File discovery: Recursive search with relative path preservation
# ---------------------------------------------------------------------------

def collect_sgf_files_recursive(
    input_dir: str,
    skip_analyzed: bool = False,
    log_cb: Optional[Callable[[str], None]] = None
) -> List[Tuple[str, str]]:
    """
    Collect all SGF files from the input directory recursively.

    Args:
        input_dir: Directory to search for SGF files
        skip_analyzed: If True, skip files that already have analysis
        log_cb: Optional callback for logging messages

    Returns:
        List of tuples (absolute_path, relative_path) for each file to process
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)

    sgf_files = []
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
    """
    Collect all SGF files from the input directory (non-recursive, for CLI compatibility).

    Args:
        input_dir: Directory to search for SGF files
        skip_analyzed: If True, skip files that already have analysis

    Returns:
        List of SGF file paths to process
    """
    sgf_files = set()  # Use set to avoid duplicates on case-insensitive filesystems
    input_path = Path(input_dir)

    # Collect SGF files (use lowercase glob, Windows is case-insensitive)
    for sgf_file in input_path.glob('*.[sS][gG][fF]'):
        file_path = str(sgf_file)
        if skip_analyzed and has_analysis(file_path):
            print(f"Skipping (already analyzed): {sgf_file.name}")
            continue
        sgf_files.add(file_path)

    # Also check .gib and .ngf formats
    for sgf_file in input_path.glob('*.[gG][iI][bB]'):
        sgf_files.add(str(sgf_file))
    for sgf_file in input_path.glob('*.[nN][gG][fF]'):
        sgf_files.add(str(sgf_file))

    return sorted(sgf_files)


def wait_for_analysis(engine: KataGoEngine, timeout: float = 300.0, poll_interval: float = 0.5) -> bool:
    """
    Wait for the engine to finish all pending analysis queries.

    Args:
        engine: KataGo engine instance
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


# ---------------------------------------------------------------------------
# Single file analysis with detailed error reporting
# ---------------------------------------------------------------------------

def analyze_single_file(
    katrain: KaTrainBase,
    engine: KataGoEngine,
    sgf_path: str,
    output_path: Optional[str] = None,
    visits: Optional[int] = None,
    timeout: float = 600.0,
    cancel_flag: Optional[List[bool]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    save_sgf: bool = True,
    return_game: bool = False,
) -> "Union[bool, Optional[Game]]":
    """
    Analyze a single SGF file and optionally save with analysis data.

    Args:
        katrain: KaTrainBase instance
        engine: KataGo engine instance
        sgf_path: Path to input SGF file
        output_path: Path to save analyzed SGF (required if save_sgf=True)
        visits: Number of visits per move (None = use default)
        timeout: Maximum time to wait for analysis
        cancel_flag: Optional list [bool] - if cancel_flag[0] is True, abort
        log_cb: Optional callback for logging messages
        save_sgf: If True, save the analyzed SGF to output_path
        return_game: If True, return the Game object instead of bool

    Returns:
        If return_game=False: True if successful, False otherwise
        If return_game=True: Game object on success, None on failure
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)

    def fail_result():
        return None if return_game else False

    def success_result(game_obj):
        return game_obj if return_game else True

    try:
        # Check for cancellation
        if cancel_flag and cancel_flag[0]:
            log("    Cancelled before start")
            return fail_result()

        # Determine step count based on options
        total_steps = 3 if not save_sgf else 4

        # Step 1: Parse SGF
        log(f"    [1/{total_steps}] Parsing SGF...")
        move_tree = parse_sgf_with_fallback(sgf_path, log_cb)
        if move_tree is None:
            log(f"    ERROR: Failed to parse SGF file")
            return fail_result()

        # Check for cancellation
        if cancel_flag and cancel_flag[0]:
            log("    Cancelled after parse")
            return fail_result()

        # Step 2: Create Game instance (this triggers analysis of all nodes)
        log(f"    [2/{total_steps}] Creating game and starting analysis...")
        game = Game(
            katrain=katrain,
            engine=engine,
            move_tree=move_tree,
            analyze_fast=False,
            sgf_filename=sgf_path,
        )
        katrain.game = game

        # If custom visits specified, trigger re-analysis with that visit count
        if visits is not None:
            game.analyze_extra("game", visits=visits)

        # Step 3: Wait for analysis to complete (with cancellation check)
        log(f"    [3/{total_steps}] Waiting for analysis to complete...")
        start_time = time.time()
        poll_interval = 0.5
        while not engine.is_idle():
            if cancel_flag and cancel_flag[0]:
                log("    Cancelled during analysis")
                return fail_result()
            if time.time() - start_time > timeout:
                log(f"    ERROR: Analysis timed out after {timeout}s")
                return fail_result()
            time.sleep(poll_interval)

        # Give a moment for final processing
        time.sleep(0.5)

        # Step 4: Save with analysis (KT property) - only if save_sgf is True
        if save_sgf:
            if not output_path:
                log("    ERROR: output_path required when save_sgf=True")
                return fail_result()

            log(f"    [4/{total_steps}] Saving analyzed SGF...")

            # Ensure output directory exists
            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            # Get trainer config and enable analysis saving
            # Note: save_feedback must be a list of bools (one per evaluation class),
            # not a single bool. We use the existing config which already has the correct format.
            trainer_config = katrain.config("trainer", {})
            trainer_config["save_analysis"] = True
            trainer_config["save_marks"] = True
            # Ensure save_feedback is a list (enable all classes if not already set)
            if "save_feedback" not in trainer_config or not isinstance(trainer_config["save_feedback"], list):
                # Default: save feedback for all evaluation classes
                trainer_config["save_feedback"] = [True, True, True, True, True, True]

            game.write_sgf(output_path, trainer_config=trainer_config)

        return success_result(game)

    except Exception as e:
        # Never swallow exceptions silently - log full traceback
        error_tb = traceback.format_exc()
        log(f"    ERROR: {e}")
        log(f"    Traceback:\n{error_tb}")
        return fail_result()


# ---------------------------------------------------------------------------
# GUI API: run_batch - Callable from KaTrain GUI
# ---------------------------------------------------------------------------

@dataclass
class WriteError:
    """Structured error entry for file write failures."""
    file_kind: str  # "karte", "summary", "analyzed_sgf"
    sgf_id: str  # SGF file name or player name
    target_path: str  # Attempted output path
    exception_type: str  # e.g., "PermissionError"
    message: str  # Error message


@dataclass
class BatchResult:
    """Result of batch analysis operation."""
    success_count: int = 0
    fail_count: int = 0
    skip_count: int = 0
    output_dir: str = ""
    cancelled: bool = False
    # Extended output counts
    karte_written: int = 0
    karte_failed: int = 0
    summary_written: bool = False
    summary_error: Optional[str] = None
    analyzed_sgf_written: int = 0
    # Structured write errors (A3)
    write_errors: List[WriteError] = field(default_factory=list)


def run_batch(
    katrain: KaTrainBase,
    engine: KataGoEngine,
    input_dir: str,
    output_dir: Optional[str] = None,
    visits: Optional[int] = None,
    timeout: float = 600.0,
    skip_analyzed: bool = False,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    cancel_flag: Optional[List[bool]] = None,
    # Extended options for karte/summary generation
    save_analyzed_sgf: bool = True,
    generate_karte: bool = False,
    generate_summary: bool = False,
    karte_player_filter: Optional[str] = None,
    min_games_per_player: int = 3,
    skill_preset: str = DEFAULT_SKILL_PRESET,
    # Variable visits options
    variable_visits: bool = False,
    jitter_pct: float = 10.0,
    deterministic: bool = True,
) -> BatchResult:
    """
    Run batch analysis on a folder of SGF files (including subfolders).

    This is the GUI-callable API for batch analysis. It uses an existing
    KaTrain and engine instance (no new engine startup required).

    Args:
        katrain: KaTrainBase instance (can be the running GUI instance)
        engine: KataGoEngine instance (can be the running engine)
        input_dir: Directory containing SGF files to analyze
        output_dir: Directory to save analyzed files (default: same as input_dir)
        visits: Number of visits per move (None = use default)
        timeout: Timeout per file in seconds
        skip_analyzed: Skip files that already have analysis
        progress_cb: Callback(current, total, filename) for progress updates.
            NOTE: Called from background thread. GUI code must use Clock.schedule_once.
        log_cb: Callback(message) for log messages.
            NOTE: Called from background thread. GUI code must use Clock.schedule_once.
        cancel_flag: List[bool] - set cancel_flag[0] = True to cancel
        save_analyzed_sgf: If True, save analyzed SGF files (default: True for backward compat)
        generate_karte: If True, generate karte markdown for each game
        generate_summary: If True, generate a multi-game summary at the end
        karte_player_filter: Filter for karte ("B", "W", or None for both)

    Returns:
        BatchResult with success/fail/skip counts, output counts, and error information
    """
    import re

    result = BatchResult()

    def log(msg: str):
        if log_cb:
            log_cb(msg)

    # Validate input directory
    if not os.path.isdir(input_dir):
        log(f"Error: Input directory does not exist: {input_dir}")
        return result

    # Set output directory
    output_dir = output_dir if output_dir else input_dir
    result.output_dir = output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Create output subdirectories if needed
    if save_analyzed_sgf:
        analyzed_dir = os.path.join(output_dir, "analyzed")
        os.makedirs(analyzed_dir, exist_ok=True)
    if generate_karte:
        karte_dir = os.path.join(output_dir, "reports", "karte")
        os.makedirs(karte_dir, exist_ok=True)
    if generate_summary:
        summary_dir = os.path.join(output_dir, "reports", "summary")
        os.makedirs(summary_dir, exist_ok=True)

    # Log enabled options
    enabled_outputs = []
    if save_analyzed_sgf:
        enabled_outputs.append("Analyzed SGF")
    if generate_karte:
        enabled_outputs.append("Karte")
    if generate_summary:
        enabled_outputs.append("Summary")
    if enabled_outputs:
        log(f"Enabled outputs: {', '.join(enabled_outputs)}")

    # Collect SGF files recursively (with relative path preservation)
    log(f"Scanning for SGF files in: {input_dir}")

    # First pass: count files and check for skips
    all_files = collect_sgf_files_recursive(input_dir, skip_analyzed=False, log_cb=None)
    sgf_files = []
    skip_count = 0

    for abs_path, rel_path in all_files:
        if skip_analyzed and has_analysis(abs_path):
            log(f"Skipping (already analyzed): {rel_path}")
            skip_count += 1
        else:
            sgf_files.append((abs_path, rel_path))

    result.skip_count = skip_count

    if not sgf_files:
        log(f"No SGF files to analyze in {input_dir}")
        return result

    log(f"Found {len(sgf_files)} SGF file(s) to analyze")
    if skip_count > 0:
        log(f"Skipped {skip_count} already-analyzed file(s)")
    total = len(sgf_files)

    # For summary generation, collect game stats
    game_stats_list = [] if generate_summary else None

    # Timestamp for filenames (includes seconds to reduce collision risk)
    batch_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Process each file
    for i, (abs_path, rel_path) in enumerate(sgf_files):
        # Check for cancellation
        if cancel_flag and cancel_flag[0]:
            log("Cancelled by user")
            result.cancelled = True
            break

        # Progress callback
        if progress_cb:
            progress_cb(i + 1, total, rel_path)

        log(f"[{i + 1}/{total}] Analyzing: {rel_path}")

        # Determine base name for output files
        base_name = os.path.splitext(os.path.basename(rel_path))[0]
        # Sanitize filename
        base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)[:50]

        # Determine SGF output path (preserve relative path structure)
        output_rel_path = rel_path
        if output_rel_path.lower().endswith(('.gib', '.ngf')):
            output_rel_path = output_rel_path[:-4] + '.sgf'

        sgf_output_path = None
        if save_analyzed_sgf:
            sgf_output_path = os.path.join(output_dir, "analyzed", output_rel_path)

        # Analyze the file
        # We need the Game object if generating karte or summary
        need_game = generate_karte or generate_summary

        # Calculate effective visits (with optional jitter)
        effective_visits = visits
        if variable_visits and visits is not None:
            effective_visits = choose_visits_for_sgf(
                abs_path,
                visits,
                jitter_pct=jitter_pct,
                deterministic=deterministic,
            )
            if effective_visits != visits:
                log(f"  Variable visits: {visits} -> {effective_visits}")

        game_result = analyze_single_file(
            katrain=katrain,
            engine=engine,
            sgf_path=abs_path,
            output_path=sgf_output_path,
            visits=effective_visits,
            timeout=timeout,
            cancel_flag=cancel_flag,
            log_cb=log_cb,
            save_sgf=save_analyzed_sgf,
            return_game=need_game,
        )

        # Handle result based on return type
        if need_game:
            game = game_result
            success = game is not None
        else:
            success = game_result
            game = None

        if success:
            result.success_count += 1

            if save_analyzed_sgf and sgf_output_path:
                result.analyzed_sgf_written += 1
                log(f"  Saved SGF: {sgf_output_path}")

            # Generate karte if requested
            if generate_karte and game is not None:
                try:
                    karte_text = game.build_karte_report(player_filter=karte_player_filter)
                    # Include path hash to avoid filename collisions for files with same basename
                    path_hash = hashlib.md5(rel_path.encode()).hexdigest()[:6]
                    karte_filename = f"karte_{base_name}_{path_hash}_{batch_timestamp}.md"
                    karte_path = os.path.join(output_dir, "reports", "karte", karte_filename)

                    # Use safe write with error handling (A3)
                    write_error = _safe_write_file(
                        path=karte_path,
                        content=karte_text,
                        file_kind="karte",
                        sgf_id=rel_path,
                        log_cb=log_cb,
                    )
                    if write_error:
                        result.karte_failed += 1
                        result.write_errors.append(write_error)
                    else:
                        result.karte_written += 1
                        log(f"  Saved Karte: {karte_filename}")

                except Exception as e:
                    import traceback
                    result.karte_failed += 1
                    error_details = traceback.format_exc()
                    log(f"  ERROR generating karte: {e}\n{error_details}")
                    # Record as a structured error too
                    result.write_errors.append(WriteError(
                        file_kind="karte",
                        sgf_id=rel_path,
                        target_path="(generation failed)",
                        exception_type=type(e).__name__,
                        message=str(e),
                    ))

            # Collect stats for summary
            if generate_summary and game is not None:
                try:
                    stats = _extract_game_stats(game, rel_path)
                    if stats:
                        game_stats_list.append(stats)
                except Exception as e:
                    log(f"  ERROR extracting stats: {e}")

        else:
            if cancel_flag and cancel_flag[0]:
                log("Cancelled by user")
                result.cancelled = True
                break
            result.fail_count += 1

    # Generate per-player summaries if requested and not cancelled
    if generate_summary and game_stats_list and not result.cancelled:
        try:
            log("Generating per-player summaries...")

            # Extract and group by player
            player_groups = _extract_players_from_stats(game_stats_list, min_games=min_games_per_player)

            if player_groups:
                summary_count = 0
                summary_failed = 0
                for player_name, player_games in player_groups.items():
                    # Sanitize filename
                    safe_name = _sanitize_filename(player_name)
                    base_path = os.path.join(output_dir, "reports", "summary", f"summary_{safe_name}_{batch_timestamp}")
                    summary_path = _get_unique_filename(base_path, ".md")
                    summary_filename = os.path.basename(summary_path)

                    # Build analysis_settings for the summary
                    analysis_settings = {
                        "config_visits": visits,
                        "variable_visits": variable_visits,
                        "jitter_pct": jitter_pct if variable_visits else None,
                        "deterministic": deterministic if variable_visits else None,
                        "timeout": timeout,
                    }
                    summary_text = _build_player_summary(
                        player_name,
                        player_games,
                        skill_preset=skill_preset,
                        analysis_settings=analysis_settings,
                    )

                    # Use safe write with error handling (A3)
                    write_error = _safe_write_file(
                        path=summary_path,
                        content=summary_text,
                        file_kind="summary",
                        sgf_id=player_name,
                        log_cb=log_cb,
                    )
                    if write_error:
                        summary_failed += 1
                        result.write_errors.append(write_error)
                    else:
                        log(f"  [{player_name}] {len(player_games)} games -> {summary_filename}")
                        summary_count += 1

                if summary_count > 0:
                    result.summary_written = True
                    log(f"Generated {summary_count} player summaries")
                if summary_failed > 0:
                    log(f"WARNING: {summary_failed} summary file(s) failed to write")
            else:
                log(f"No players with >= {min_games_per_player} games found")
                result.summary_error = f"No players with >= {min_games_per_player} games"

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            result.summary_error = str(e)
            log(f"ERROR generating summary: {e}\n{error_details}")
    elif generate_summary and not game_stats_list and not result.cancelled:
        # No games were successfully analyzed for summary
        result.summary_error = "No valid game statistics available"
        log("WARNING: Summary generation requested but no valid game statistics available")

    return result


def _extract_game_stats(game: Game, rel_path: str) -> Optional[dict]:
    """Extract statistics from a Game object for summary generation."""
    try:
        from katrain.core import eval_metrics

        snapshot = game.build_eval_snapshot()
        if not snapshot.moves:
            return None

        # Get game metadata
        root = game.root
        player_black = root.get_property("PB", "Black")
        player_white = root.get_property("PW", "White")
        handicap = int(root.get_property("HA", "0") or "0")
        date = root.get_property("DT", None)
        board_size_prop = root.get_property("SZ", "19")
        try:
            board_size = int(board_size_prop)
        except (ValueError, TypeError):
            board_size = 19

        # Calculate stats from snapshot
        stats = {
            "game_name": rel_path,
            "player_black": player_black,
            "player_white": player_white,
            "handicap": handicap,
            "date": date,
            "board_size": (board_size, board_size),
            "total_moves": len(snapshot.moves),
            "total_points_lost": snapshot.total_points_lost,
            "moves_by_player": {"B": 0, "W": 0},
            "loss_by_player": {"B": 0.0, "W": 0.0},
            "mistake_counts": {cat: 0 for cat in eval_metrics.MistakeCategory},
            "mistake_total_loss": {cat: 0.0 for cat in eval_metrics.MistakeCategory},
            "freedom_counts": {diff: 0 for diff in eval_metrics.PositionDifficulty},
            "phase_moves": {"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
            "phase_loss": {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0},
            "phase_mistake_counts": {},
            "phase_mistake_loss": {},
            "worst_moves": [],
            # Per-player stats for player summary
            "mistake_counts_by_player": {
                "B": {cat: 0 for cat in eval_metrics.MistakeCategory},
                "W": {cat: 0 for cat in eval_metrics.MistakeCategory},
            },
            "mistake_total_loss_by_player": {
                "B": {cat: 0.0 for cat in eval_metrics.MistakeCategory},
                "W": {cat: 0.0 for cat in eval_metrics.MistakeCategory},
            },
            "freedom_counts_by_player": {
                "B": {diff: 0 for diff in eval_metrics.PositionDifficulty},
                "W": {diff: 0 for diff in eval_metrics.PositionDifficulty},
            },
            "phase_moves_by_player": {
                "B": {"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
                "W": {"opening": 0, "middle": 0, "yose": 0, "unknown": 0},
            },
            "phase_loss_by_player": {
                "B": {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0},
                "W": {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0},
            },
            "phase_mistake_counts_by_player": {"B": {}, "W": {}},
            "phase_mistake_loss_by_player": {"B": {}, "W": {}},
            # Reason tags for player summary (Issue 2)
            # Tags are computed for important moves only (get_important_move_evals)
            "reason_tags_by_player": {"B": {}, "W": {}},
            # Important moves stats for Reason Tags clarity (PR1-1)
            "important_moves_stats_by_player": {
                "B": {"important_count": 0, "tagged_count": 0, "tag_occurrences": 0},
                "W": {"important_count": 0, "tagged_count": 0, "tag_occurrences": 0},
            },
            # Reliability stats for Data Quality section
            "reliability_by_player": {
                "B": {"total": 0, "reliable": 0, "low_confidence": 0, "total_visits": 0, "with_visits": 0, "max_visits": 0},
                "W": {"total": 0, "reliable": 0, "low_confidence": 0, "total_visits": 0, "with_visits": 0, "max_visits": 0},
            },
        }

        for move in snapshot.moves:
            player = move.player
            canonical_loss = _get_canonical_loss(move.points_lost)
            stats["moves_by_player"][player] = stats["moves_by_player"].get(player, 0) + 1
            stats["loss_by_player"][player] = stats["loss_by_player"].get(player, 0.0) + canonical_loss

            # Phase classification
            phase = eval_metrics.classify_game_phase(move.move_number, board_size=board_size)
            stats["phase_moves"][phase] = stats["phase_moves"].get(phase, 0) + 1
            stats["phase_loss"][phase] = stats["phase_loss"].get(phase, 0.0) + canonical_loss

            # Per-player phase stats
            if player in ("B", "W"):
                stats["phase_moves_by_player"][player][phase] = (
                    stats["phase_moves_by_player"][player].get(phase, 0) + 1
                )
                stats["phase_loss_by_player"][player][phase] = (
                    stats["phase_loss_by_player"][player].get(phase, 0.0) + canonical_loss
                )

            # Mistake category
            if move.mistake_category:
                stats["mistake_counts"][move.mistake_category] = stats["mistake_counts"].get(move.mistake_category, 0) + 1
                stats["mistake_total_loss"][move.mistake_category] = stats["mistake_total_loss"].get(move.mistake_category, 0.0) + canonical_loss

                # Per-player mistake stats
                if player in ("B", "W"):
                    stats["mistake_counts_by_player"][player][move.mistake_category] = (
                        stats["mistake_counts_by_player"][player].get(move.mistake_category, 0) + 1
                    )
                    stats["mistake_total_loss_by_player"][player][move.mistake_category] = (
                        stats["mistake_total_loss_by_player"][player].get(move.mistake_category, 0.0) + canonical_loss
                    )

                # Phase x Mistake
                key = (phase, move.mistake_category.name)
                stats["phase_mistake_counts"][key] = stats["phase_mistake_counts"].get(key, 0) + 1
                stats["phase_mistake_loss"][key] = stats["phase_mistake_loss"].get(key, 0.0) + canonical_loss

                # Per-player Phase x Mistake
                if player in ("B", "W"):
                    stats["phase_mistake_counts_by_player"][player][key] = (
                        stats["phase_mistake_counts_by_player"][player].get(key, 0) + 1
                    )
                    stats["phase_mistake_loss_by_player"][player][key] = (
                        stats["phase_mistake_loss_by_player"][player].get(key, 0.0) + canonical_loss
                    )

            # Freedom/difficulty
            if move.position_difficulty:
                stats["freedom_counts"][move.position_difficulty] = stats["freedom_counts"].get(move.position_difficulty, 0) + 1

                # Per-player freedom stats
                if player in ("B", "W"):
                    stats["freedom_counts_by_player"][player][move.position_difficulty] = (
                        stats["freedom_counts_by_player"][player].get(move.position_difficulty, 0) + 1
                    )

            # NOTE: reason_tags collection moved to after the loop (Issue A fix)
            # Reason tags are computed in get_important_move_evals(), not in build_eval_snapshot()
            # The old code here collected from snapshot.moves which has empty reason_tags

            # Track reliability stats for Data Quality section
            if player in ("B", "W"):
                rel = stats["reliability_by_player"][player]
                rel["total"] += 1
                visits = move.root_visits or 0
                if visits == 0:
                    rel["low_confidence"] += 1
                elif visits >= eval_metrics.RELIABILITY_VISITS_THRESHOLD:
                    rel["reliable"] += 1
                    rel["total_visits"] += visits
                    rel["with_visits"] += 1
                else:
                    rel["low_confidence"] += 1
                    rel["total_visits"] += visits
                    rel["with_visits"] += 1
                # PR1-2: Track max visits
                if visits > rel["max_visits"]:
                    rel["max_visits"] = visits

            # Track worst moves
            if move.points_lost and move.points_lost >= 2.0:
                stats["worst_moves"].append((move.move_number, player, move.gtp, move.points_lost, move.mistake_category))

        # Sort worst moves by loss
        stats["worst_moves"].sort(key=lambda x: x[3], reverse=True)
        stats["worst_moves"] = stats["worst_moves"][:10]  # Keep top 10

        # Issue A fix: Get reason_tags from important moves (not from all moves)
        # Reason tags are computed in get_important_move_evals(), not in build_eval_snapshot()
        # PR1-1: Also track important_moves_count and tagged_moves_count for clarity
        try:
            important_moves = game.get_important_move_evals(compute_reason_tags=True)
            for move in important_moves:
                player = move.player
                if player in ("B", "W"):
                    im_stats = stats["important_moves_stats_by_player"][player]
                    im_stats["important_count"] += 1
                    if move.reason_tags:
                        im_stats["tagged_count"] += 1
                        for tag in move.reason_tags:
                            # Validate tag before counting (A1 requirement)
                            if eval_metrics.validate_reason_tag(tag):
                                stats["reason_tags_by_player"][player][tag] = (
                                    stats["reason_tags_by_player"][player].get(tag, 0) + 1
                                )
                                im_stats["tag_occurrences"] += 1
        except Exception:
            # If important moves extraction fails, reason_tags will be empty but stats still valid
            pass

        return stats
    except Exception:
        return None


def _build_batch_summary(game_stats_list: List[dict], focus_player: Optional[str] = None) -> str:
    """Build a multi-game summary markdown from collected stats."""
    from katrain.core import eval_metrics

    if not game_stats_list:
        return "# Multi-Game Summary\n\nNo games processed."

    lines = ["# Multi-Game Summary\n"]
    lines.append(f"**Games analyzed**: {len(game_stats_list)}\n")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # Aggregate stats
    total_moves = sum(s["total_moves"] for s in game_stats_list)
    total_loss = sum(s["total_points_lost"] for s in game_stats_list)

    lines.append(f"\n## Overview\n")
    lines.append(f"- Total moves: {total_moves}")
    lines.append(f"- Total points lost: {total_loss:.1f}")
    if total_moves > 0:
        lines.append(f"- Average loss per move: {total_loss / total_moves:.2f}")

    # Phase x Mistake breakdown
    lines.append(f"\n## Phase x Mistake Breakdown\n")

    phase_mistake_counts = {}
    phase_mistake_loss = {}
    for stats in game_stats_list:
        for key, count in stats.get("phase_mistake_counts", {}).items():
            phase_mistake_counts[key] = phase_mistake_counts.get(key, 0) + count
        for key, loss in stats.get("phase_mistake_loss", {}).items():
            phase_mistake_loss[key] = phase_mistake_loss.get(key, 0.0) + loss

    if phase_mistake_counts:
        lines.append("| Phase | Mistake | Count | Total Loss |")
        lines.append("|-------|---------|------:|----------:|")
        for key in sorted(phase_mistake_counts.keys(), key=lambda x: phase_mistake_loss.get(x, 0), reverse=True):
            phase, category = key
            count = phase_mistake_counts[key]
            loss = phase_mistake_loss.get(key, 0.0)
            lines.append(f"| {phase} | {category} | {count} | {loss:.1f} |")

    # Worst moves across all games
    lines.append(f"\n## Top 10 Worst Moves (All Games)\n")
    all_worst = []
    for stats in game_stats_list:
        game_name = stats["game_name"]
        for move_num, player, gtp, loss, cat in stats.get("worst_moves", []):
            all_worst.append((game_name, move_num, player, gtp, loss, cat))

    all_worst.sort(key=lambda x: x[4], reverse=True)
    all_worst = all_worst[:10]

    if all_worst:
        lines.append("| Game | Move | Player | Position | Loss | Category |")
        lines.append("|------|-----:|:------:|----------|-----:|----------|")
        for game_name, move_num, player, gtp, loss, cat in all_worst:
            cat_name = cat.name if cat else "—"
            lines.append(f"| {game_name[:30]} | {move_num} | {player} | {gtp} | {loss:.1f} | {cat_name} |")

    # Games list
    lines.append(f"\n## Games Included\n")
    for i, stats in enumerate(game_stats_list, 1):
        game_name = stats["game_name"]
        loss = stats["total_points_lost"]
        moves = stats["total_moves"]
        lines.append(f"{i}. {game_name} — {moves} moves, {loss:.1f} pts lost")

    return "\n".join(lines)


# Windows reserved filenames
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def _sanitize_filename(name: str, max_length: int = 50) -> str:
    """
    Sanitize player name for use in filename.

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
    import re

    if not name:
        return "unknown"

    # Remove/replace invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Normalize whitespace (including full-width spaces)
    safe = re.sub(r'\s+', '_', safe)
    # Remove leading/trailing dots and underscores
    safe = safe.strip('._')

    # Check for Windows reserved names (case-insensitive)
    if safe.upper() in _WINDOWS_RESERVED:
        safe = f"_{safe}_"

    # Truncate to max length
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip('_')

    # Strip trailing dots and spaces again after truncation (Windows requirement)
    safe = safe.rstrip('. ')

    # Final fallback if empty
    if not safe:
        return "unknown"

    return safe


def _get_unique_filename(base_path: str, extension: str = ".md") -> str:
    """
    Generate unique filename by adding suffix if collision exists.

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
            import hashlib
            hash_suffix = hashlib.md5(base_path.encode()).hexdigest()[:6]
            return f"{base_path}_{hash_suffix}{extension}"


# Generic player names to skip
_SKIP_NAMES = {"Black", "White", "黒", "白", "", "?", "Unknown", "不明"}


def _normalize_player_name(name: str) -> str:
    """
    Normalize player name for grouping.

    Uses NFKC normalization and collapses whitespace.
    This is the single source of truth for name normalization.
    """
    import unicodedata

    name = name.strip()
    name = unicodedata.normalize("NFKC", name)
    # Collapse multiple spaces
    name = " ".join(name.split())
    return name


def _extract_players_from_stats(
    game_stats_list: List[dict],
    min_games: int = 3
) -> Dict[str, List[Tuple[dict, str]]]:
    """
    Extract player names and group their games.

    Args:
        game_stats_list: List of game stats dicts
        min_games: Minimum games required per player

    Returns:
        Dict mapping player_display_name -> [(game_stats, role), ...]
        where role is "B" or "W"

    Design Notes:
        - Names are normalized via _normalize_player_name()
        - Original display name (first occurrence) preserved for output
        - Generic names ("Black", "White", "黒", "白", etc.) are skipped
        - Players with < min_games are excluded
    """
    from collections import defaultdict

    # Track: normalized_name -> [(stats, role, original_name), ...]
    player_games: Dict[str, List[Tuple[dict, str, str]]] = defaultdict(list)

    for stats in game_stats_list:
        pb_orig = stats.get("player_black", "").strip()
        pw_orig = stats.get("player_white", "").strip()

        if pb_orig and pb_orig not in _SKIP_NAMES:
            pb_norm = _normalize_player_name(pb_orig)
            player_games[pb_norm].append((stats, "B", pb_orig))

        if pw_orig and pw_orig not in _SKIP_NAMES:
            pw_norm = _normalize_player_name(pw_orig)
            player_games[pw_norm].append((stats, "W", pw_orig))

    # Filter by min_games and convert to output format
    result: Dict[str, List[Tuple[dict, str]]] = {}
    for norm_name, games in player_games.items():
        if len(games) >= min_games:
            # Use first original name as display name
            display_name = games[0][2]
            result[display_name] = [(g[0], g[1]) for g in games]

    return result


def _build_player_summary(
    player_name: str,
    player_games: List[Tuple[dict, str]],
    skill_preset: str = DEFAULT_SKILL_PRESET,
    *,
    analysis_settings: Optional[Dict[str, any]] = None,
) -> str:
    """
    Build summary for a single player across their games.

    Args:
        player_name: Display name of the player
        player_games: List of (game_stats, role) tuples where role is "B" or "W"
        skill_preset: Skill preset for strictness ("auto" or one of SKILL_PRESETS keys)
        analysis_settings: Optional dict with configured analysis settings:
            - config_visits: base visits value
            - variable_visits: bool, whether variable visits is enabled
            - jitter_pct: float, jitter percentage (if variable_visits)
            - deterministic: bool, whether deterministic mode (if variable_visits)
            - timeout: float or None, timeout in seconds

    Returns:
        Markdown summary string
    """
    from datetime import datetime

    lines = [f"# Player Summary: {player_name}\n"]
    lines.append(f"**Games analyzed**: {len(player_games)}\n")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Aggregate only this player's moves across all games
    total_moves = 0
    total_loss = 0.0
    all_worst = []
    games_as_black = 0
    games_as_white = 0

    # Aggregated per-player stats
    mistake_counts: Dict[MistakeCategory, int] = {cat: 0 for cat in MistakeCategory}
    mistake_total_loss: Dict[MistakeCategory, float] = {cat: 0.0 for cat in MistakeCategory}
    freedom_counts: Dict[PositionDifficulty, int] = {diff: 0 for diff in PositionDifficulty}
    phase_moves: Dict[str, int] = {"opening": 0, "middle": 0, "yose": 0, "unknown": 0}
    phase_loss: Dict[str, float] = {"opening": 0.0, "middle": 0.0, "yose": 0.0, "unknown": 0.0}
    phase_mistake_counts: Dict[Tuple[str, str], int] = {}
    phase_mistake_loss: Dict[Tuple[str, str], float] = {}
    reason_tags_counts: Dict[str, int] = {}  # Issue 2: aggregate reason tags
    # PR1-1: Important moves stats for Reason Tags clarity
    important_moves_total = 0
    tagged_moves_total = 0
    tag_occurrences_total = 0

    # Reliability stats for Data Quality section
    reliability_total = 0
    reliability_reliable = 0
    reliability_low_conf = 0
    reliability_total_visits = 0
    reliability_with_visits = 0
    reliability_max_visits = 0  # PR1-2: Track max visits across all games
    board_sizes: set = set()  # Track unique board sizes for Definitions

    for stats, role in player_games:
        if role == "B":
            games_as_black += 1
        else:
            games_as_white += 1

        # Only count this player's moves/loss
        total_moves += stats["moves_by_player"].get(role, 0)
        total_loss += stats["loss_by_player"].get(role, 0.0)

        # Aggregate per-player mistake counts
        if "mistake_counts_by_player" in stats and role in stats["mistake_counts_by_player"]:
            for cat, count in stats["mistake_counts_by_player"][role].items():
                mistake_counts[cat] = mistake_counts.get(cat, 0) + count
        if "mistake_total_loss_by_player" in stats and role in stats["mistake_total_loss_by_player"]:
            for cat, loss in stats["mistake_total_loss_by_player"][role].items():
                mistake_total_loss[cat] = mistake_total_loss.get(cat, 0.0) + loss

        # Aggregate per-player freedom counts
        if "freedom_counts_by_player" in stats and role in stats["freedom_counts_by_player"]:
            for diff, count in stats["freedom_counts_by_player"][role].items():
                freedom_counts[diff] = freedom_counts.get(diff, 0) + count

        # Aggregate per-player phase stats
        if "phase_moves_by_player" in stats and role in stats["phase_moves_by_player"]:
            for phase, count in stats["phase_moves_by_player"][role].items():
                phase_moves[phase] = phase_moves.get(phase, 0) + count
        if "phase_loss_by_player" in stats and role in stats["phase_loss_by_player"]:
            for phase, loss in stats["phase_loss_by_player"][role].items():
                phase_loss[phase] = phase_loss.get(phase, 0.0) + loss

        # Aggregate per-player phase x mistake counts
        if "phase_mistake_counts_by_player" in stats and role in stats["phase_mistake_counts_by_player"]:
            for key, count in stats["phase_mistake_counts_by_player"][role].items():
                phase_mistake_counts[key] = phase_mistake_counts.get(key, 0) + count
        if "phase_mistake_loss_by_player" in stats and role in stats["phase_mistake_loss_by_player"]:
            for key, loss in stats["phase_mistake_loss_by_player"][role].items():
                phase_mistake_loss[key] = phase_mistake_loss.get(key, 0.0) + loss

        # Collect worst moves for this player
        for move_num, player, gtp, loss, cat in stats.get("worst_moves", []):
            if player == role:
                all_worst.append((stats["game_name"], move_num, gtp, loss, cat))

        # Aggregate reason tags (Issue 2)
        if "reason_tags_by_player" in stats and role in stats["reason_tags_by_player"]:
            for tag, count in stats["reason_tags_by_player"][role].items():
                reason_tags_counts[tag] = reason_tags_counts.get(tag, 0) + count

        # PR1-1: Aggregate important moves stats for Reason Tags clarity
        if "important_moves_stats_by_player" in stats and role in stats["important_moves_stats_by_player"]:
            im_stats = stats["important_moves_stats_by_player"][role]
            important_moves_total += im_stats.get("important_count", 0)
            tagged_moves_total += im_stats.get("tagged_count", 0)
            tag_occurrences_total += im_stats.get("tag_occurrences", 0)

        # Aggregate reliability stats for Data Quality
        if "reliability_by_player" in stats and role in stats["reliability_by_player"]:
            rel = stats["reliability_by_player"][role]
            reliability_total += rel.get("total", 0)
            reliability_reliable += rel.get("reliable", 0)
            reliability_low_conf += rel.get("low_confidence", 0)
            reliability_total_visits += rel.get("total_visits", 0)
            reliability_with_visits += rel.get("with_visits", 0)
            # PR1-2: Track max visits across all games
            game_max = rel.get("max_visits", 0)
            if game_max > reliability_max_visits:
                reliability_max_visits = game_max

        # Track board sizes for Definitions section
        if "board_size" in stats:
            board_sizes.add(stats["board_size"][0])  # (x, y) tuple, use x

    # =========================================================================
    # Compute auto recommendation if skill_preset is "auto"
    # =========================================================================
    game_count = len(player_games)
    auto_recommendation: Optional[AutoRecommendation] = None
    effective_preset = skill_preset

    if skill_preset == "auto" and reliability_total > 0:
        # For multi-game summaries, we use aggregated mistake_counts
        # to compute blunder/important counts without re-scanning moves
        rel_pct = 100.0 * reliability_reliable / reliability_total if reliability_total > 0 else 0.0

        # Count blunders and important moves from aggregated stats
        # BLUNDER = MistakeCategory with loss >= t3
        # IMPORTANT = MISTAKE + BLUNDER (loss >= t2)
        # We iterate through presets and use mistake_counts data
        # Since we don't have per-move data, use aggregated stats as proxy
        # Blunders ~ MistakeCategory.BLUNDER count
        # Important ~ MistakeCategory.MISTAKE + MistakeCategory.BLUNDER
        blunder_count = mistake_counts.get(MistakeCategory.BLUNDER, 0)
        important_count = blunder_count + mistake_counts.get(MistakeCategory.MISTAKE, 0)

        # Target ranges scaled by game count
        target_blunder = (3 * game_count, 10 * game_count)
        target_important = (10 * game_count, 30 * game_count)

        # Calculate scores for each preset (simplified: use standard counts as baseline)
        # Since we can't recalculate with different thresholds without moves,
        # we estimate based on "standard" preset counts
        b_score = _distance_from_range(blunder_count, target_blunder) * 2
        i_score = _distance_from_range(important_count, target_important) * 1
        total_score = b_score + i_score

        # Reliability gate
        if rel_pct < 20.0:
            conf = AutoConfidence.LOW
            effective_preset = "standard"
            reason = f"Low reliability ({rel_pct:.1f}%)"
        else:
            # Determine confidence based on score
            if total_score == 0:
                conf = AutoConfidence.HIGH
            elif total_score <= 5:
                conf = AutoConfidence.MEDIUM
            else:
                conf = AutoConfidence.LOW

            # Heuristic: adjust preset based on blunder density
            blunder_per_game = blunder_count / game_count if game_count > 0 else 0
            if blunder_per_game > 10:
                effective_preset = "advanced"  # Too many blunders, use stricter
            elif blunder_per_game < 3:
                effective_preset = "beginner"  # Too few blunders, use looser
            else:
                effective_preset = "standard"
            reason = f"blunder={blunder_count}, important={important_count}"

        auto_recommendation = AutoRecommendation(
            recommended_preset=effective_preset,
            confidence=conf,
            blunder_count=blunder_count,
            important_count=important_count,
            score=total_score,
            reason=reason,
        )

    # =========================================================================
    # Definitions Section (before Overview)
    # =========================================================================
    preset = SKILL_PRESETS.get(effective_preset, SKILL_PRESETS[DEFAULT_SKILL_PRESET])
    t1, t2, t3 = preset.score_thresholds

    # Build strictness info line using JP labels
    effective_label = SKILL_PRESET_LABELS.get(effective_preset, effective_preset)
    if skill_preset == "auto" and auto_recommendation:
        conf_label = CONFIDENCE_LABELS.get(auto_recommendation.confidence.value, auto_recommendation.confidence.value)
        strictness_info = (
            f"自動 → {effective_label} "
            f"(信頼度: {conf_label}, "
            f"大悪手={auto_recommendation.blunder_count}, 重要={auto_recommendation.important_count})"
        )
    else:
        strictness_info = f"{effective_label} (手動)"

    lines.append("\n## Definitions\n")
    lines.append(f"- Strictness: {strictness_info}")

    # Feature 3: Show auto recommendation hint even in manual mode
    if skill_preset != "auto" and game_count > 0:
        # Compute auto recommendation for hint
        blunder_count = mistake_counts.get(MistakeCategory.BLUNDER, 0)
        important_count = blunder_count + mistake_counts.get(MistakeCategory.MISTAKE, 0)
        rel_pct = 100.0 * reliability_reliable / reliability_total if reliability_total > 0 else 0.0

        # Simplified auto recommendation for multi-game context
        target_blunder = (3 * game_count, 10 * game_count)
        target_important = (10 * game_count, 30 * game_count)
        b_score = _distance_from_range(blunder_count, target_blunder) * 2
        i_score = _distance_from_range(important_count, target_important) * 1
        total_score = b_score + i_score

        if rel_pct < 20.0:
            hint_conf = AutoConfidence.LOW
            hint_preset = "standard"
        else:
            if total_score == 0:
                hint_conf = AutoConfidence.HIGH
            elif total_score <= 5:
                hint_conf = AutoConfidence.MEDIUM
            else:
                hint_conf = AutoConfidence.LOW

            blunder_per_game = blunder_count / game_count if game_count > 0 else 0
            if blunder_per_game > 10:
                hint_preset = "advanced"
            elif blunder_per_game < 3:
                hint_preset = "beginner"
            else:
                hint_preset = "standard"

        hint_label = SKILL_PRESET_LABELS.get(hint_preset, hint_preset)
        hint_conf_label = CONFIDENCE_LABELS.get(hint_conf.value, hint_conf.value)
        lines.append(f"- Auto recommended: {hint_label} (信頼度: {hint_conf_label})")

    lines.append("")
    lines.append("| Metric | Definition |")
    lines.append("|--------|------------|")
    lines.append("| Points Lost | Score difference between actual move and best move (clamped to ≥0) |")
    lines.append(f"| Good | Loss < {t1:.1f} pts |")
    lines.append(f"| Inaccuracy | Loss {t1:.1f} - {t2:.1f} pts |")
    lines.append(f"| Mistake | Loss {t2:.1f} - {t3:.1f} pts |")
    lines.append(f"| Blunder | Loss ≥ {t3:.1f} pts |")

    # Phase thresholds - handle mixed board sizes
    if len(board_sizes) == 1:
        board_size = list(board_sizes)[0]
        opening_end, middle_end = get_phase_thresholds(board_size)
        lines.append(f"| Phase ({board_size}x{board_size}) | Opening: <{opening_end}, Middle: {opening_end}-{middle_end-1}, Endgame: ≥{middle_end} |")
    else:
        lines.append("| Phase | Mixed board sizes - thresholds vary |")

    # =========================================================================
    # Analysis Settings Section (configured values)
    # =========================================================================
    if analysis_settings:
        lines.append("\n## Analysis Settings\n")
        # Config visits
        config_visits = analysis_settings.get("config_visits")
        if config_visits is not None:
            lines.append(f"- Config visits: {config_visits:,}")

        # Variable visits settings
        variable_visits = analysis_settings.get("variable_visits", False)
        if variable_visits:
            lines.append("- Variable visits: on")
            jitter_pct = analysis_settings.get("jitter_pct")
            if jitter_pct is not None:
                lines.append(f"- Visits jitter: {jitter_pct}%")
            deterministic = analysis_settings.get("deterministic", False)
            lines.append(f"- Deterministic: {'on' if deterministic else 'off'}")
        else:
            lines.append("- Variable visits: off")

        # Timeout
        timeout = analysis_settings.get("timeout")
        if timeout is not None:
            lines.append(f"- Timeout: {timeout}s")
        else:
            lines.append("- Timeout: None")

        # Reliable threshold (constant)
        lines.append(f"- Reliable threshold: {RELIABILITY_VISITS_THRESHOLD} visits")

    # =========================================================================
    # Data Quality Section (PR1-2: Add max visits and measured note)
    # =========================================================================
    lines.append("\n## Data Quality\n")
    lines.append(f"- Moves analyzed: {reliability_total}")
    if reliability_total > 0:
        rel_pct = 100.0 * reliability_reliable / reliability_total
        low_pct = 100.0 * reliability_low_conf / reliability_total
        lines.append(f"- Reliable (visits ≥ {RELIABILITY_VISITS_THRESHOLD}): {reliability_reliable} ({rel_pct:.1f}%)")
        lines.append(f"- Low-confidence: {reliability_low_conf} ({low_pct:.1f}%)")
        if reliability_with_visits > 0:
            avg_visits = reliability_total_visits / reliability_with_visits
            lines.append(f"- Avg visits: {avg_visits:,.0f}")
            # PR1-2: Add max visits to help users understand the data
            if reliability_max_visits > 0:
                lines.append(f"- Max visits: {reliability_max_visits:,}")
        if rel_pct < 20.0:
            lines.append("")
            lines.append("⚠ Low analysis reliability (<20%). Results may be unstable.")
    # PR1-2: Add note about measured values
    lines.append("")
    lines.append("*Visits are measured from KataGo analysis (root_visits).*")

    # =========================================================================
    # Section 1: Overview
    # =========================================================================
    lines.append(f"\n## Overview\n")
    lines.append(f"- Games as Black: {games_as_black}")
    lines.append(f"- Games as White: {games_as_white}")
    lines.append(f"- Total moves: {total_moves}")
    lines.append(f"- Total points lost: {total_loss:.1f}")
    if total_moves > 0:
        lines.append(f"- Average loss per move: {total_loss / total_moves:.2f}")

    # Per-game metrics
    games_analyzed = len(player_games)
    if games_analyzed > 0:
        points_per_game = total_loss / games_analyzed
        blunders_total = mistake_counts.get(MistakeCategory.BLUNDER, 0)
        mistakes_total = mistake_counts.get(MistakeCategory.MISTAKE, 0)
        important_total = blunders_total + mistakes_total
        blunders_per_game = blunders_total / games_analyzed
        important_per_game = important_total / games_analyzed
        lines.append("")
        lines.append("**Per-game averages:**")
        lines.append(f"- Points lost/game: {points_per_game:.1f}")
        lines.append(f"- Blunders/game: {blunders_per_game:.1f}")
        lines.append(f"- Important mistakes/game: {important_per_game:.1f}")
    else:
        lines.append("")
        lines.append("**Per-game averages:** -")

    # =========================================================================
    # Section 2: Mistake Distribution
    # =========================================================================
    lines.append(f"\n## Mistake Distribution\n")
    lines.append("| Category | Count | Percentage | Avg Loss |")
    lines.append("|----------|------:|------------|----------|")

    category_labels = {
        MistakeCategory.GOOD: "Good",
        MistakeCategory.INACCURACY: "Inaccuracy",
        MistakeCategory.MISTAKE: "Mistake",
        MistakeCategory.BLUNDER: "Blunder",
    }

    total_categorized = sum(mistake_counts.values())
    for cat in [MistakeCategory.GOOD, MistakeCategory.INACCURACY,
                MistakeCategory.MISTAKE, MistakeCategory.BLUNDER]:
        count = mistake_counts.get(cat, 0)
        pct = (count / total_categorized * 100) if total_categorized > 0 else 0.0
        avg_loss = (mistake_total_loss.get(cat, 0.0) / count) if count > 0 else 0.0
        lines.append(f"| {category_labels[cat]} | {count} | {pct:.1f}% | {avg_loss:.2f} |")

    # =========================================================================
    # Section 3: Phase Breakdown
    # =========================================================================
    lines.append(f"\n## Phase Breakdown\n")
    lines.append("| Phase | Moves | Points Lost | Avg Loss |")
    lines.append("|-------|------:|------------:|----------|")

    phase_labels = {
        "opening": "Opening",
        "middle": "Middle game",
        "yose": "Endgame",
        "unknown": "Unknown",
    }

    for phase in ["opening", "middle", "yose", "unknown"]:
        count = phase_moves.get(phase, 0)
        loss = phase_loss.get(phase, 0.0)
        avg_loss = (loss / count) if count > 0 else 0.0
        lines.append(f"| {phase_labels.get(phase, phase)} | {count} | {loss:.1f} | {avg_loss:.2f} |")

    # =========================================================================
    # Section 4: Phase × Mistake Breakdown
    # =========================================================================
    lines.append(f"\n## Phase × Mistake Breakdown\n")
    lines.append("| Phase | Good | Inaccuracy | Mistake | Blunder | Total Loss |")
    lines.append("|-------|------|------------|---------|---------|------------|")

    for phase in ["opening", "middle", "yose"]:
        cells = [phase_labels.get(phase, phase)]

        for cat in [MistakeCategory.GOOD, MistakeCategory.INACCURACY,
                    MistakeCategory.MISTAKE, MistakeCategory.BLUNDER]:
            key = (phase, cat.name)
            count = phase_mistake_counts.get(key, 0)
            loss = phase_mistake_loss.get(key, 0.0)

            if count > 0 and cat != MistakeCategory.GOOD:
                cells.append(f"{count} ({loss:.1f})")
            else:
                cells.append(str(count))

        # Total loss for this phase
        phase_total_loss = phase_loss.get(phase, 0.0)
        cells.append(f"{phase_total_loss:.1f}")

        lines.append("| " + " | ".join(cells) + " |")

    # =========================================================================
    # Section 5: Top 10 Worst Moves
    # =========================================================================
    lines.append(f"\n## Top 10 Worst Moves\n")
    all_worst.sort(key=lambda x: x[3], reverse=True)
    all_worst = all_worst[:10]

    if all_worst:
        lines.append("| Game | Move | Position | Loss | Category |")
        lines.append("|------|-----:|----------|-----:|----------|")
        for game_name, move_num, gtp, loss, cat in all_worst:
            cat_name = cat.name if cat else "—"
            short_game = game_name[:30] + "..." if len(game_name) > 33 else game_name
            lines.append(f"| {short_game} | {move_num} | {gtp} | {loss:.1f} | {cat_name} |")
    else:
        lines.append("- No significant mistakes found.")

    # =========================================================================
    # Section 6: Reason Tags Distribution (Issue 2 + PR1-1 clarity)
    # =========================================================================
    lines.append(f"\n## Reason Tags (Top 10)\n")

    # PR1-1: Add explanatory note about what is counted
    if important_moves_total > 0:
        lines.append(f"*Tags computed for {important_moves_total} important moves "
                     f"(mistakes/blunders with loss ≥ threshold). "
                     f"{tagged_moves_total} moves had ≥1 tag.*\n")

    if reason_tags_counts:
        # Sort by count desc, then by tag name asc for deterministic ordering
        sorted_tags = sorted(
            reason_tags_counts.items(),
            key=lambda x: (-x[1], x[0])
        )[:10]  # Top 10

        # PR1-1: Use tag_occurrences_total as denominator (sum of all tag counts)
        # Percentage = this tag's occurrences / total tag occurrences
        for tag, count in sorted_tags:
            pct = (count / tag_occurrences_total * 100) if tag_occurrences_total > 0 else 0.0
            label = get_reason_tag_label(tag, fallback_to_raw=True)
            lines.append(f"- {label}: {count} ({pct:.1f}%)")
    else:
        lines.append("- No reason tags recorded.")

    # =========================================================================
    # Section 7: Weakness Hypothesis
    # =========================================================================
    lines.append(f"\n## Weakness Hypothesis\n")

    # Determine weaknesses based on cross-tabulation
    weaknesses = []

    # Check phase with highest average loss
    phase_avg = {}
    for phase in ["opening", "middle", "yose"]:
        count = phase_moves.get(phase, 0)
        loss = phase_loss.get(phase, 0.0)
        if count > 0:
            phase_avg[phase] = loss / count

    if phase_avg:
        worst_phase = max(phase_avg.items(), key=lambda x: x[1])
        if worst_phase[1] > 0.5:  # Only if avg loss > 0.5
            weaknesses.append(
                f"**{phase_labels.get(worst_phase[0], worst_phase[0])}** shows highest "
                f"average loss ({worst_phase[1]:.2f} pts/move)"
            )

    # Check for high blunder rate
    total_bad = mistake_counts.get(MistakeCategory.MISTAKE, 0) + mistake_counts.get(MistakeCategory.BLUNDER, 0)
    if total_categorized > 0:
        bad_rate = total_bad / total_categorized * 100
        if bad_rate > 10:
            weaknesses.append(
                f"High mistake/blunder rate: {bad_rate:.1f}% of moves are mistakes or blunders"
            )

    # Check for phase-specific problems
    for phase in ["opening", "middle", "yose"]:
        blunder_key = (phase, MistakeCategory.BLUNDER.name)
        blunder_count = phase_mistake_counts.get(blunder_key, 0)
        blunder_loss = phase_mistake_loss.get(blunder_key, 0.0)
        if blunder_count >= 3 and blunder_loss >= 10:
            weaknesses.append(
                f"{phase_labels.get(phase, phase)}: {blunder_count} blunders "
                f"totaling {blunder_loss:.1f} points lost"
            )

    if weaknesses:
        for w in weaknesses:
            lines.append(f"- {w}")
    else:
        lines.append("- No clear weakness pattern detected. Keep up the good work!")

    # =========================================================================
    # Section 8: Practice Priorities
    # =========================================================================
    lines.append(f"\n## Practice Priorities\n")
    lines.append("Based on the data above, consider focusing on:\n")

    priorities = []

    # Priority 1: Worst phase
    if phase_avg:
        worst_phase = max(phase_avg.items(), key=lambda x: x[1])
        if worst_phase[1] > 0.5:
            phase_name = phase_labels.get(worst_phase[0], worst_phase[0])
            if worst_phase[0] == "opening":
                priorities.append(f"Study **opening principles and joseki** (highest avg loss)")
            elif worst_phase[0] == "middle":
                priorities.append(f"Practice **fighting and reading** (highest avg loss in middle game)")
            else:
                priorities.append(f"Study **endgame techniques** (highest avg loss)")

    # Priority 2: High blunder areas
    for phase in ["opening", "middle", "yose"]:
        blunder_key = (phase, MistakeCategory.BLUNDER.name)
        blunder_count = phase_mistake_counts.get(blunder_key, 0)
        if blunder_count >= 3:
            phase_name = phase_labels.get(phase, phase)
            priorities.append(f"Review {phase_name.lower()} blunders ({blunder_count} occurrences)")

    # Priority 3: Life and death if many blunders
    total_blunders = mistake_counts.get(MistakeCategory.BLUNDER, 0)
    if total_blunders >= 5:
        priorities.append("Practice **life and death problems** to reduce blunders")

    if priorities:
        for i, p in enumerate(priorities[:5], 1):  # Max 5 priorities
            lines.append(f"{i}. {p}")
    else:
        lines.append("- No specific priorities identified. Continue balanced practice!")

    # =========================================================================
    # Section 9: Games Included
    # =========================================================================
    lines.append(f"\n## Games Included\n")
    for i, (stats, role) in enumerate(player_games, 1):
        game_name = stats["game_name"]
        player_loss = stats["loss_by_player"].get(role, 0.0)
        player_moves = stats["moves_by_player"].get(role, 0)
        color = "Black" if role == "B" else "White"
        lines.append(f"{i}. {game_name} ({color}) — {player_moves} moves, {player_loss:.1f} pts lost")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Batch analyze SGF files using KaTrain/KataGo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze all SGF files in a folder
    python -m katrain.tools.batch_analyze_sgf --input-dir ./games --output-dir ./analyzed

    # Analyze with specific visit count
    python -m katrain.tools.batch_analyze_sgf --input-dir ./games --visits 500

    # Skip files that already have analysis
    python -m katrain.tools.batch_analyze_sgf --input-dir ./games --skip-if-already-analyzed

    # In-place analysis (overwrites original files)
    python -m katrain.tools.batch_analyze_sgf --input-dir ./games
""",
    )

    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing SGF files to analyze",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save analyzed files (default: same as input-dir)",
    )
    parser.add_argument(
        "--visits",
        type=int,
        default=None,
        help="Number of visits per move (default: use KaTrain config)",
    )
    parser.add_argument(
        "--skip-if-already-analyzed",
        action="store_true",
        help="Skip files that already contain analysis data (KT property)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="Timeout per file in seconds (default: 600)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output",
    )

    args = parser.parse_args()

    # Validate input directory
    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory does not exist: {args.input_dir}")
        sys.exit(1)

    # Set output directory
    output_dir = args.output_dir if args.output_dir else args.input_dir
    os.makedirs(output_dir, exist_ok=True)

    # Collect SGF files (non-recursive for CLI compatibility)
    sgf_files = collect_sgf_files(args.input_dir, skip_analyzed=args.skip_if_already_analyzed)

    if not sgf_files:
        print(f"No SGF files found in {args.input_dir}")
        sys.exit(0)

    print(f"Found {len(sgf_files)} SGF file(s) to analyze")

    # Initialize KaTrain (headless)
    debug_level = OUTPUT_DEBUG if args.debug else OUTPUT_INFO
    katrain = KaTrainBase(force_package_config=False, debug_level=debug_level)

    # Initialize KataGo engine
    engine_config = katrain.config("engine")
    try:
        engine = KataGoEngine(katrain, engine_config)
    except Exception as e:
        print(f"Error starting KataGo engine: {e}")
        print("Please ensure KataGo is properly configured in KaTrain settings.")
        sys.exit(1)

    # Process each file
    success_count = 0
    fail_count = 0

    def log_print(msg: str):
        print(msg)

    for i, sgf_path in enumerate(sgf_files):
        file_name = os.path.basename(sgf_path)
        print(f"[{i + 1}/{len(sgf_files)}] Analyzing: {file_name}")

        # Determine output path
        output_path = os.path.join(output_dir, file_name)

        # Ensure .sgf extension for converted formats
        if output_path.lower().endswith(('.gib', '.ngf')):
            output_path = output_path[:-4] + '.sgf'

        success = analyze_single_file(
            katrain=katrain,
            engine=engine,
            sgf_path=sgf_path,
            output_path=output_path,
            visits=args.visits,
            timeout=args.timeout,
            log_cb=log_print,
        )

        if success:
            success_count += 1
            print(f"  Saved: {output_path}")
        else:
            fail_count += 1

    # Cleanup
    engine.shutdown(finish=True)

    # Summary
    print()
    print(f"Batch analysis complete!")
    print(f"  Success: {success_count}")
    print(f"  Failed: {fail_count}")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
