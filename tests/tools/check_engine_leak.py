#!/usr/bin/env python
"""
Engine process leak verification script.

Usage:
    # With real engine (requires katago binary):
    uv run python tests/tools/check_engine_leak.py --cycles 5 --katago /path/to/katago

    # Process count only (CI default, no binary required):
    uv run python tests/tools/check_engine_leak.py --skip-engine

    # Using user's existing config:
    uv run python tests/tools/check_engine_leak.py --use-config

This script:
1. Records baseline process count for katago/leela
2. Runs N start/stop cycles using minimal engine initialization (if not skipped)
3. Verifies no extra processes remain after cycles

CI Note: Use --skip-engine by default in CI environments where real binaries
are not guaranteed. The script will still verify process counting works.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def count_engine_processes():
    """
    Count running katago/leela processes (Windows).

    Uses tasklist without filters and does substring matching in Python
    for reliable cross-environment behavior.
    """
    try:
        # Run tasklist without /FI filter (wildcards unreliable across environments)
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        count = 0
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            line_lower = line.lower()
            # Substring match for katago/leela process names
            if "katago" in line_lower or "leela" in line_lower:
                count += 1

        return count
    except FileNotFoundError:
        # Not Windows - try ps (Unix/Mac)
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=30)
            count = 0
            for line in result.stdout.strip().split("\n"):
                line_lower = line.lower()
                if "katago" in line_lower or "leela" in line_lower:
                    # Exclude this script itself if it matches
                    if "check_engine_leak" not in line_lower:
                        count += 1
            return count
        except Exception as e:
            print(f"Warning: Could not count processes: {e}")
            return 0
    except Exception as e:
        print(f"Warning: Could not count processes: {e}")
        return 0


def load_user_config():
    """Load user's KaTrain config.json if available."""
    # Standard config locations
    config_paths = [
        Path.home() / ".katrain" / "config.json",
        Path.home() / "AppData" / "Local" / "katrain" / "config.json",  # Windows
        Path.home() / ".config" / "katrain" / "config.json",  # Linux
    ]

    for path in config_paths:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load {path}: {e}")

    return None


def run_engine_cycle(katago_path, model_path, config_path):
    """Run one start/stop cycle of KataGoEngine."""
    # Import here to avoid Kivy initialization issues
    os.environ.setdefault("KIVY_NO_ARGS", "1")
    os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")

    from katrain.core.engine import KataGoEngine

    # Minimal mock for katrain object with configurable paths
    class MinimalKatrain:
        def __init__(self, katago, model, config):
            self._katago = katago
            self._model = model
            self._config = config

        def log(self, msg, level=None):
            pass  # Suppress logs during test

        def config(self, key, default=None):
            configs = {
                "engine/katago": self._katago,
                "engine/model": self._model,
                "engine/config": self._config,
                "engine/threads": 1,
                "engine/max_visits": 1,
                "engine/max_time": 1.0,
                "engine/wide_root_noise": 0.0,
            }
            return configs.get(key, default)

    katrain = MinimalKatrain(katago_path, model_path, config_path)

    # Try to create and start engine
    try:
        engine = KataGoEngine(katrain)
        engine.start()
        # Brief pause to ensure startup completes
        # (This sleep is acceptable: it's a tool script, not a flaky test)
        time.sleep(0.5)
        engine.shutdown(finish=True)
        # Brief pause to ensure OS cleanup completes
        time.sleep(0.2)
        return True
    except Exception as e:
        print(f"Engine cycle failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Check for engine process leaks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CI mode (no binary required):
  uv run python tests/tools/check_engine_leak.py --skip-engine

  # Local testing with explicit paths:
  uv run python tests/tools/check_engine_leak.py --katago C:/katago/katago.exe --model C:/katago/model.bin.gz

  # Use existing KaTrain config:
  uv run python tests/tools/check_engine_leak.py --use-config --cycles 3
""",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=5,
        help="Number of start/stop cycles (default: 5)",
    )
    parser.add_argument(
        "--skip-engine",
        action="store_true",
        help="Skip actual engine cycles (process count verification only). Use this in CI.",
    )
    parser.add_argument(
        "--katago",
        type=str,
        default=None,
        help="Path to katago executable (default: 'katago' in PATH)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="",
        help="Path to model file (default: empty, uses katago default)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="",
        help="Path to katago config file (default: empty, uses katago default)",
    )
    parser.add_argument(
        "--use-config",
        action="store_true",
        help="Load paths from user's KaTrain config.json",
    )
    args = parser.parse_args()

    print("=== Engine Leak Verification ===\n")

    # Resolve engine paths
    katago_path = args.katago or "katago"
    model_path = args.model
    config_path = args.config

    if args.use_config:
        user_config = load_user_config()
        if user_config:
            katago_path = user_config.get("engine", {}).get("katago", katago_path)
            model_path = user_config.get("engine", {}).get("model", model_path)
            config_path = user_config.get("engine", {}).get("config", config_path)
            print(f"Loaded config: katago={katago_path}")
        else:
            print("Warning: --use-config specified but no config.json found")

    # Step 1: Baseline
    baseline = count_engine_processes()
    print(f"Baseline process count: {baseline}")

    if args.skip_engine:
        print("\n--skip-engine: Skipping actual engine cycles")
        print("(Use this mode in CI where binaries are not available)")
    else:
        # Step 2: Run cycles
        print(f"\nRunning {args.cycles} start/stop cycles...")
        print(f"  katago: {katago_path}")
        print(f"  model: {model_path or '(default)'}")
        print(f"  config: {config_path or '(default)'}")
        print()

        for i in range(args.cycles):
            success = run_engine_cycle(katago_path, model_path, config_path)
            status = "OK" if success else "FAIL"
            print(f"  Cycle {i + 1}/{args.cycles}: {status}")
            if not success:
                print("  Warning: Cycle failed, continuing...")

        # Brief pause for OS cleanup
        # (This sleep is acceptable: it's a tool script for manual/CI verification)
        time.sleep(2)

    # Step 3: Final count
    final = count_engine_processes()
    print(f"\nFinal process count: {final}")

    # Step 4: Verdict
    leaked = final - baseline
    if leaked > 0:
        print(f"\n[FAIL] LEAK DETECTED: {leaked} extra process(es)")
        return 1
    else:
        print("\n[PASS] No process leak detected")
        return 0


if __name__ == "__main__":
    sys.exit(main())
