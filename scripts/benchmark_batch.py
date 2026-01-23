#!/usr/bin/env python
"""
Benchmark script for batch processing performance (Phase 52-B4).

Measures the time to run extract_game_stats() on multiple SGF files.

Usage:
    python scripts/benchmark_batch.py --sgf-dir tests/data --num-games 50 --threshold 5.0 --strict
    python scripts/benchmark_batch.py --help

Options:
    --sgf-dir DIR       Directory containing SGF files (default: tests/data)
    --num-games N       Number of games to process (default: 50)
    --threshold SEC     Time threshold in seconds (default: 5.0)
    --strict            Exit with code 1 if threshold exceeded (default: warning only)
"""

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Minimal Katrain Stub for Benchmarking
# =============================================================================


class MinimalKatrain:
    """Minimal stub for katrain object needed by Game."""

    pondering = False

    def config(self, key: str, default: Any = None) -> Any:
        """Return config value (always return default for stub)."""
        return default


class MinimalEngine:
    """Minimal stub for engine needed by Game."""

    def stop_pondering(self) -> None:
        """No-op for stub."""
        pass

    def request_analysis(self, *args, **kwargs) -> None:
        """No-op for stub."""
        pass


def get_machine_spec() -> Dict[str, Any]:
    """Get machine specification for benchmark context.

    Returns:
        Dictionary with platform, processor, and optionally cpu_count/ram_gb.
    """
    spec: Dict[str, Any] = {
        "platform": platform.platform(),
        "processor": platform.processor(),
    }

    try:
        import psutil

        spec["cpu_count"] = psutil.cpu_count(logical=False)
        spec["ram_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        spec["note"] = "psutil not available"

    return spec


def find_sgf_files(sgf_dir: Path, limit: Optional[int] = None) -> List[Path]:
    """Find SGF files in directory (recursive).

    Args:
        sgf_dir: Directory to search
        limit: Maximum number of files to return

    Returns:
        List of Path objects for SGF files
    """
    files = sorted(sgf_dir.rglob("*.sgf"))
    if limit:
        # Cycle through files if fewer than limit
        while len(files) < limit:
            files = files + files
        files = files[:limit]
    return files


def run_benchmark(
    sgf_dir: Path,
    num_games: int,
    threshold: float,
) -> Dict[str, Any]:
    """Run the benchmark.

    Args:
        sgf_dir: Directory containing SGF files
        num_games: Number of games to process
        threshold: Time threshold in seconds

    Returns:
        Benchmark result dictionary
    """
    # Import here to avoid slow startup
    from katrain.core.game import Game
    from katrain.core.batch.stats import extract_game_stats
    from katrain.core.batch.helpers import parse_sgf_with_fallback

    # Create minimal stubs
    katrain = MinimalKatrain()
    engine = MinimalEngine()

    # Find SGF files
    sgf_files = find_sgf_files(sgf_dir, limit=num_games)
    if not sgf_files:
        return {
            "error": f"No SGF files found in {sgf_dir}",
            "passed": False,
        }

    # Load games first (not part of benchmark)
    games: List[tuple] = []  # (Game, rel_path)
    for sgf_path in sgf_files:
        try:
            # Parse SGF to get move_tree
            move_tree = parse_sgf_with_fallback(sgf_path)
            if move_tree is None:
                continue

            # Create Game with minimal stubs (analyze_fast=True to skip analysis thread)
            game = Game(
                katrain=katrain,
                engine=engine,
                move_tree=move_tree,
                analyze_fast=True,
                sgf_filename=str(sgf_path),
            )
            rel_path = str(sgf_path.relative_to(sgf_dir))
            games.append((game, rel_path))
        except Exception:
            # Skip problematic files
            pass

    if not games:
        return {
            "error": "Could not load any SGF files",
            "passed": False,
        }

    # Run benchmark
    start_time = time.perf_counter()

    successful = 0
    for game, rel_path in games:
        try:
            result = extract_game_stats(game, rel_path)
            if result is not None:
                successful += 1
        except Exception:
            pass

    elapsed = time.perf_counter() - start_time

    # Build result
    result = {
        "elapsed_sec": round(elapsed, 2),
        "games_processed": successful,
        "games_loaded": len(games),
        "avg_ms_per_game": round((elapsed * 1000) / len(games), 1) if games else 0,
        "threshold_sec": threshold,
        "passed": elapsed <= threshold,
        "machine": get_machine_spec(),
    }

    return result


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Benchmark batch processing performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--sgf-dir",
        type=Path,
        default=PROJECT_ROOT / "tests" / "data",
        help="Directory containing SGF files (default: tests/data)",
    )
    parser.add_argument(
        "--num-games",
        type=int,
        default=50,
        help="Number of games to process (default: 50)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=5.0,
        help="Time threshold in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if threshold exceeded (default: warning only)",
    )

    args = parser.parse_args()

    # Verify directory exists
    if not args.sgf_dir.exists():
        print(f"ERROR: SGF directory not found: {args.sgf_dir}", file=sys.stderr)
        sys.exit(1)

    # Run benchmark
    result = run_benchmark(args.sgf_dir, args.num_games, args.threshold)

    # Output JSON result
    print(json.dumps(result, indent=2))

    # Handle exit code
    if "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if not result["passed"]:
        msg = f"{'FAILED' if args.strict else 'WARNING'}: {result['elapsed_sec']:.2f}s > {args.threshold}s"
        if args.strict:
            print(msg, file=sys.stderr)
            sys.exit(1)
        else:
            print(f"{msg} (non-strict)", file=sys.stderr)
            sys.exit(0)
    else:
        print(f"PASSED: {result['elapsed_sec']:.2f}s <= {args.threshold}s")
        sys.exit(0)


if __name__ == "__main__":
    main()
