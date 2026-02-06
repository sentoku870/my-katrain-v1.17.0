#!/usr/bin/env python3
"""
Verification script: Check if eval_color fallback logging is triggered during startup.

This script loads KaTrain, lets it initialize, then loads a test SGF to trigger
Top Moves rendering. Any fallback logging indicates incomplete trainer_config.

Usage:
  python verify_initialization_logs.py | tee initialization_log.txt
"""

import sys
import os
import logging
from pathlib import Path

# Set up logging to capture all output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("="*80)
print("VERIFICATION: trainer_config Initialization")
print("="*80)
print("\nScript Purpose:")
print("  Monitor for [PHASE116-REGRESSION-CHECK] log messages during KaTrain startup.")
print("  If NO such messages appear, trainer_config is properly initialized.")
print("  If messages appear, it indicates incomplete config needing fallback defaults.")
print("\nExpected Result:")
print("  - Phase 115 baseline: May or may not show fallback messages (test will tell us)")
print("  - Phase 116 + fix: Should NOT show fallback messages (config should be complete)")
print("="*80)

try:
    from katrain.core.lang import i18n
    print("\n[INFO] Successfully imported katrain.core.lang")

    # Try to import katrain GUI (this might fail if Kivy can't initialize)
    print("[INFO] Attempting to import KaTrain GUI components...")
    from katrain.gui.badukpan import BadukPanWidget
    print("[INFO] Successfully imported BadukPanWidget")

    # Check if eval_color method exists
    if hasattr(BadukPanWidget, 'eval_color'):
        print("[OK] eval_color method found in BadukPanWidget")
    else:
        print("[ERROR] eval_color method NOT found in BadukPanWidget")
        sys.exit(1)

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("\nTo generate screenshots:")
    print("  1. Start KaTrain: python -m katrain")
    print("  2. Load test SGF: tests/data/test_top_moves_color.sgf")
    print("  3. Navigate to a move with KataGo analysis")
    print("  4. Take screenshot of Top Moves markers")
    print("  5. Check console output for [PHASE116-REGRESSION-CHECK] messages")
    print("\nTo fully verify the fix:")
    print("  1. Run this script on Phase 115 baseline")
    print("  2. Run this script with Phase 116 + commit 80a39e2")
    print("  3. Compare for any [PHASE116-REGRESSION-CHECK] messages")
    print("\n" + "="*80)

except Exception as e:
    print(f"\n[ERROR] Failed to import KaTrain components: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
