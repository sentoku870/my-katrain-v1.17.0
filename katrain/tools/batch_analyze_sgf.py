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

Note:
    Phase 42-B: All batch processing logic has been moved to katrain.core.batch.
    This module now re-exports from core.batch for backward compatibility
    and provides a CLI entry point.
"""

# Disable Kivy's argument parser before importing any Kivy-related modules
import os
os.environ["KIVY_NO_ARGS"] = "1"

import argparse
import sys
from typing import Callable, Dict, List, Optional, Tuple, Union

# KaTrain imports for CLI entry point
from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import KataGoEngine
from katrain.core.constants import OUTPUT_INFO, OUTPUT_ERROR, OUTPUT_DEBUG

# =============================================================================
# Phase 42-B: Backward compatibility re-exports from katrain.core.batch
# =============================================================================
# All batch processing logic is now in katrain.core.batch.
# Re-export everything here so existing code continues to work.

from katrain.core.batch import (
    # === Models ===
    WriteError,
    BatchResult,
    # === Constants ===
    DEFAULT_TIMEOUT_SECONDS,
    ENCODINGS_TO_TRY,
    # === Helper functions ===
    # Variable visits
    choose_visits_for_sgf,
    # Loss calculation
    get_canonical_loss,
    # Timeout parsing
    parse_timeout_input,
    # File I/O
    safe_write_file,
    read_sgf_with_fallback,
    parse_sgf_with_fallback,
    has_analysis,
    # File discovery
    collect_sgf_files_recursive,
    collect_sgf_files,
    # Engine polling
    wait_for_analysis,
    # Filename sanitization
    sanitize_filename,
    get_unique_filename,
    normalize_player_name,
    # UI validation
    safe_int,
    needs_leela_karte_warning,
    # === Analysis functions (lazy imports) ===
    analyze_single_file,
    analyze_single_file_leela,
    # === Orchestration (lazy imports) ===
    run_batch,
    # === Stats functions (lazy imports) ===
    extract_game_stats,
    build_batch_summary,
    extract_players_from_stats,
    build_player_summary,
)

# Private name aliases (unchanged API for backward compatibility)
from katrain.core.batch.helpers import (
    get_canonical_loss as _get_canonical_loss,
    safe_write_file as _safe_write_file,
    sanitize_filename as _sanitize_filename,
    get_unique_filename as _get_unique_filename,
    normalize_player_name as _normalize_player_name,
)

# Stats function private aliases
from katrain.core.batch.stats import (
    extract_game_stats as _extract_game_stats,
    build_batch_summary as _build_batch_summary,
    extract_players_from_stats as _extract_players_from_stats,
    build_player_summary as _build_player_summary,
)

# =============================================================================
# Additional backward-compat re-exports for Leela support
# =============================================================================
# These were previously imported directly in this module and used by tests.

from katrain.core.leela.engine import LeelaEngine
from katrain.core.leela.conversion import leela_position_to_move_eval
from katrain.core.leela.models import LeelaPositionEval
from katrain.core.analysis.models import EvalSnapshot, MoveEval


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
    print("Batch analysis complete!")
    print(f"  Success: {success_count}")
    print(f"  Failed: {fail_count}")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
