#!/usr/bin/env python3
"""
Manual Verification Guide for Phase 116 Regression Fix

This script provides a reproducible way to verify the fix works correctly.
User should follow these steps to generate their own screenshot evidence.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from katrain.core.utils import evaluation_class
from katrain.gui.theme import Theme

def show_expected_colors():
    """Show what Top Moves colors SHOULD be for various loss values."""

    print("\n" + "="*80)
    print("EXPECTED COLOR MAPPING FOR KATAGO TOP MOVES")
    print("="*80)

    thresholds = [1.0, 2.0, 5.0, 10.0, 15.0]
    colors = Theme.EVAL_COLORS["theme:normal"]

    # Color palette
    color_names = [
        "Index 0: PURPLE/MAGENTA (worst/bad moves)",
        "Index 1: RED (poor moves)",
        "Index 2: ORANGE (okay moves)",
        "Index 3: YELLOW (decent moves)",
        "Index 4: LIGHT GREEN (good moves)",
        "Index 5: DARK GREEN (excellent moves)",
    ]

    print("\nColor Palette (from worst to best):")
    for name in color_names:
        print(f"  {name}")

    print("\n" + "-"*80)
    print("Loss Value Distribution and Expected Colors:")
    print("-"*80)

    # Test various loss values
    test_losses = [
        (-5.0, "Excellent move (+5 gain on root)"),
        (-2.0, "Good move (+2 gain)"),
        (-0.5, "Minor gain"),
        (0.0, "Equal to root"),
        (0.5, "Minor loss"),
        (1.0, "Small loss (threshold 1)"),
        (2.5, "Medium loss"),
        (5.0, "Large loss (threshold 5)"),
        (10.0, "Very large loss (threshold 10)"),
        (20.0, "Massive loss"),
    ]

    print(f"\nThresholds: {thresholds}\n")
    print("Loss Value | Color Class | RGB Value              | Color Name")
    print("-" * 80)

    for loss, description in test_losses:
        class_idx = evaluation_class(loss, thresholds)
        r, g, b, a = colors[class_idx]

        # Determine color name
        if g > r and b < 0.1:
            color_name = "GREEN"
        elif r > 0.7 and g < 0.2:
            color_name = "RED"
        elif r > 0.3 and g > 0.3:
            color_name = "PURPLE/YELLOW"
        else:
            color_name = "ORANGE/YELLOW"

        print(f"{loss:9.1f}  | Class {class_idx}     | RGB({r:.2f},{g:.2f},{b:.2f}) | {color_name:20s} - {description}")

    print("\n" + "="*80)
    print("WHAT THIS MEANS FOR TOP MOVES DISPLAY")
    print("="*80)
    print("""
When analyzing a position, KataGo will evaluate multiple candidate moves.
Each move gets a "pointsLost" value indicating how much worse it is than the best move.

CORRECT BEHAVIOR (what we fixed):
  - Moves with small pointsLost (like 0.5) = GREEN/YELLOW colors (good moves)
  - Moves with large pointsLost (like 10.0) = RED/PURPLE colors (bad moves)
  - Result: MULTI-COLOR GRADIENT from red (bad) to green (good)

BROKEN BEHAVIOR (Phase 116 before fix):
  - trainer_config["eval_thresholds"] KeyError = crash during initialization
  - Falls back to single color rendering
  - Result: MONOCHROME PURPLE (all same color)

With our fix:
  - Defensive .get() with defaults ensures no crash
  - Logging warns if defaults are used
  - Color gradient is preserved
""")

def show_verification_steps():
    """Show the exact steps to verify the fix."""

    print("\n" + "="*80)
    print("MANUAL VERIFICATION STEPS")
    print("="*80)

    print("""
STEP 1: Start KaTrain with Logging
  Command: python -m katrain 2>&1 | tee katrain_output.log

  Wait for app to fully load (you should see "INFO" messages about Kivy)

STEP 2: Load Test SGF
  Menu: File → Open
  File: tests/data/test_top_moves_color.sgf

  The SGF should load without errors

STEP 3: Navigate to Position with Top Moves
  Method A: Use keyboard arrows to navigate through moves
  Method B: Find a position where KataGo has analyzed

  Look for: Small colored circles/squares on the board (these are Top Moves)

STEP 4: Take Screenshot of Top Moves
  Capture the area showing Top Moves markers

  EXPECTED RESULT:
    - You should see MULTIPLE COLORS:
      * Red/Orange for bad moves (high loss)
      * Yellow for medium moves
      * Green for good moves (low loss)
    - NOT monochrome (all same color)
    - NOT all purple

STEP 5: Check Logs for Regression Detection
  Command: grep "PHASE116-REGRESSION-CHECK" katrain_output.log | wc -l

  EXPECTED RESULT:
    - Count should be 0 or very low
    - If high count: trainer_config initialization issue
    - If any appear: Our logging detected it

STEP 6: Verify No Crashes
  Check katrain_output.log for:
    - No KeyError exceptions
    - No AttributeError exceptions
    - No stderr errors related to trainer_config

  EXPECTED: Clean startup with no errors
""")

def show_comparison():
    """Show what Phase 115 vs Phase 116 should look like."""

    print("\n" + "="*80)
    print("PHASE 115 vs PHASE 116 + FIX COMPARISON")
    print("="*80)

    print("""
+------------------------------------------------------------------+
| PHASE 115 (Baseline - Working by Accident)                       |
+------------------------------------------------------------------+
| - No defensive defaults                                          |
| - Direct dictionary access: trainer_config["key"]                |
| - IF trainer_config incomplete: KeyError → crash/fallback        |
| - Visual: Could show multi-color IF config loads in time        |
| - Fragile: Depends on initialization timing                      |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| PHASE 116 WITHOUT FIX (Regression)                               |
+------------------------------------------------------------------+
| - trainer_config lookup fails during rendering                   |
| - No error handling                                              |
| - Result: Fallback to single color                               |
| - Visual: MONOCHROME PURPLE (all Top Moves same color)          |
| - Problem: Loss of color gradient information                    |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| PHASE 116 WITH FIX (Current - Commits 80a39e2 + 4c8ad90)        |
+------------------------------------------------------------------+
| - Defensive .get() with defaults                                 |
| - Fallback logging: [PHASE116-REGRESSION-CHECK]                  |
| - 10 regression tests ensure behavior                            |
| - Result: Multi-color gradient preserved                         |
| - Visual: MULTI-COLOR GRADIENT (red to green)                    |
| - Robust: Handles incomplete initialization gracefully           |
+------------------------------------------------------------------+
""")

if __name__ == "__main__":
    print("""
================================================================================
                   PHASE 116 REGRESSION FIX
              Manual Verification & Screenshot Guide
================================================================================
""")

    show_expected_colors()
    show_comparison()
    show_verification_steps()

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("""
This script shows what SHOULD happen when you run KaTrain with the fix.

Key Evidence to Look For:
  1. [OK] SGF loads without errors
  2. [OK] Top Moves show MULTIPLE COLORS (not monochrome)
  3. [OK] No [PHASE116-REGRESSION-CHECK] messages (or only during init)
  4. [OK] No KeyError or AttributeError in logs
  5. [OK] Color gradient: Red (bad moves) to Green (good moves)

If all 5 are true = FIX IS WORKING [VERIFIED]

""")
