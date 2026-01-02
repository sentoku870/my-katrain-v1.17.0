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
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

# KaTrain imports (these may import Kivy indirectly)
from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import KataGoEngine
from katrain.core.game import Game, KaTrainSGF
from katrain.core.constants import OUTPUT_INFO, OUTPUT_ERROR, OUTPUT_DEBUG


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
    output_path: str,
    visits: Optional[int] = None,
    timeout: float = 600.0,
    cancel_flag: Optional[List[bool]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Analyze a single SGF file and save with analysis data.

    Args:
        katrain: KaTrainBase instance
        engine: KataGo engine instance
        sgf_path: Path to input SGF file
        output_path: Path to save analyzed SGF
        visits: Number of visits per move (None = use default)
        timeout: Maximum time to wait for analysis
        cancel_flag: Optional list [bool] - if cancel_flag[0] is True, abort
        log_cb: Optional callback for logging messages

    Returns:
        True if successful, False otherwise
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)

    try:
        # Check for cancellation
        if cancel_flag and cancel_flag[0]:
            log("    Cancelled before start")
            return False

        # Step 1: Parse SGF
        log("    [1/4] Parsing SGF...")
        move_tree = parse_sgf_with_fallback(sgf_path, log_cb)
        if move_tree is None:
            log(f"    ERROR: Failed to parse SGF file")
            return False

        # Check for cancellation
        if cancel_flag and cancel_flag[0]:
            log("    Cancelled after parse")
            return False

        # Step 2: Create Game instance (this triggers analysis of all nodes)
        log("    [2/4] Creating game and starting analysis...")
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
        log("    [3/4] Waiting for analysis to complete...")
        start_time = time.time()
        poll_interval = 0.5
        while not engine.is_idle():
            if cancel_flag and cancel_flag[0]:
                log("    Cancelled during analysis")
                return False
            if time.time() - start_time > timeout:
                log(f"    ERROR: Analysis timed out after {timeout}s")
                return False
            time.sleep(poll_interval)

        # Give a moment for final processing
        time.sleep(0.5)

        # Step 4: Save with analysis (KT property)
        log("    [4/4] Saving analyzed SGF...")

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

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
        return True

    except Exception as e:
        # Never swallow exceptions silently - log full traceback
        error_tb = traceback.format_exc()
        log(f"    ERROR: {e}")
        log(f"    Traceback:\n{error_tb}")
        return False


# ---------------------------------------------------------------------------
# GUI API: run_batch - Callable from KaTrain GUI
# ---------------------------------------------------------------------------

@dataclass
class BatchResult:
    """Result of batch analysis operation."""
    success_count: int = 0
    fail_count: int = 0
    skip_count: int = 0
    output_dir: str = ""
    cancelled: bool = False


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
        progress_cb: Callback(current, total, filename) for progress updates
        log_cb: Callback(message) for log messages
        cancel_flag: List[bool] - set cancel_flag[0] = True to cancel

    Returns:
        BatchResult with success/fail/skip counts and output directory
    """
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

        # Determine output path (preserve relative path structure)
        output_rel_path = rel_path

        # Ensure .sgf extension for converted formats
        if output_rel_path.lower().endswith(('.gib', '.ngf')):
            output_rel_path = output_rel_path[:-4] + '.sgf'

        output_path = os.path.join(output_dir, output_rel_path)

        success = analyze_single_file(
            katrain=katrain,
            engine=engine,
            sgf_path=abs_path,
            output_path=output_path,
            visits=visits,
            timeout=timeout,
            cancel_flag=cancel_flag,
            log_cb=log_cb,
        )

        if success:
            result.success_count += 1
            log(f"  Saved: {output_path}")
        else:
            if cancel_flag and cancel_flag[0]:
                log("Cancelled by user")
                result.cancelled = True
                break
            result.fail_count += 1

    return result


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
