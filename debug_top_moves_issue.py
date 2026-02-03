#!/usr/bin/env python3
"""
Debug script to investigate Top Moves color issue.

Tests evaluation_class() logic with various loss values to understand
why all Top Moves appear purple (index 0).
"""

from katrain.core.utils import evaluation_class
from katrain.gui.theme import Theme

# Test parameters (from badukpan.py defaults)
eval_thresholds = [1.0, 2.0, 5.0, 10.0, 15.0]
colors = Theme.EVAL_COLORS["theme:normal"]

print("\n" + "="*80)
print("DEBUG: TOP MOVES COLOR ISSUE INVESTIGATION")
print("="*80)

print("\nColor Palette:")
color_names = [
    "Index 0: PURPLE [0.447, 0.129, 0.42]",
    "Index 1: RED [0.8, 0, 0]",
    "Index 2: ORANGE [0.9, 0.4, 0.1]",
    "Index 3: YELLOW [0.95, 0.95, 0]",
    "Index 4: LIGHT GREEN [0.67, 0.9, 0.18]",
    "Index 5: DARK GREEN [0.117, 0.588, 0]",
]
for name in color_names:
    print(f"  {name}")

print("\nThresholds:", eval_thresholds)

print("\n" + "-"*80)
print("Test: Loss Values and Their Color Indices")
print("-"*80)

test_cases = [
    (-5.0, "Excellent move (KataGo gain)"),
    (-2.0, "Good move (KataGo gain)"),
    (-0.5, "Small gain (KataGo gain)"),
    (0.0, "Equal to best move"),
    (0.5, "Small loss"),
    (1.0, "At threshold 1.0"),
    (1.5, "Between thresholds"),
    (2.0, "At threshold 2.0"),
    (3.0, "Between 2.0 and 5.0"),
    (5.0, "At threshold 5.0"),
    (7.0, "Between 5.0 and 10.0"),
    (10.0, "At threshold 10.0"),
    (12.0, "Between 10.0 and 15.0"),
    (15.0, "At threshold 15.0"),
    (20.0, "Beyond all thresholds"),
]

print(f"\n{'Loss':<8} | {'Index':<6} | {'Color Name':<20} | {'Description':<35}")
print("-"*80)

for loss, description in test_cases:
    idx = evaluation_class(loss, eval_thresholds)
    color = colors[idx]

    # Color name detection
    if idx == 0:
        color_name = "PURPLE"
    elif idx == 1:
        color_name = "RED"
    elif idx == 2:
        color_name = "ORANGE"
    elif idx == 3:
        color_name = "YELLOW"
    elif idx == 4:
        color_name = "LIGHT GREEN"
    elif idx == 5:
        color_name = "DARK GREEN"
    else:
        color_name = f"UNKNOWN({idx})"

    print(f"{loss:<8.1f} | {idx:<6} | {color_name:<20} | {description:<35}")

print("\n" + "="*80)
print("ANALYSIS")
print("="*80)

# Check if all indices are 0
all_indices = [evaluation_class(loss, eval_thresholds) for loss, _ in test_cases]
all_zero = all(idx == 0 for idx in all_indices)

if all_zero:
    print("\n[PROBLEM] All indices are 0 (all purple)!")
    print("This matches the user's report of monochrome purple Top Moves.")
    print("\nPossible causes:")
    print("1. evaluation_class() logic is inverted")
    print("2. KataGo pointsLost values are always negative (gains)")
    print("3. evaluation_class() not being called correctly")
else:
    indices_set = set(all_indices)
    print(f"\n[OK] Multiple indices detected: {sorted(indices_set)}")
    print("This suggests the color gradient should work.")

print("\n" + "="*80)
print("evaluation_class() LOGIC TEST")
print("="*80)

print("\nFunction logic:")
print("  i = 0")
print("  while i < len(eval_thresholds) - 1:")
print("    if points_lost < eval_thresholds[i]:")
print("      break")
print("    i += 1")
print("  return i")

print("\nStep-by-step for loss=0.5 (should be GREEN/YELLOW):")
loss = 0.5
i = 0
print(f"  Start: loss={loss}, i={i}")
while i < len(eval_thresholds) - 1:
    threshold = eval_thresholds[i]
    print(f"  Step: i={i}, threshold={threshold}, loss < threshold = {loss < threshold}")
    if loss < threshold:
        print(f"  -> Break at i={i}")
        break
    i += 1
    if i >= len(eval_thresholds):
        print(f"  -> Reached end, final i={i}")
        break
print(f"  Final: i={i} (color: {color_names[i]})")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

if all_zero:
    print("""
The logic appears to be INVERTED:
- All loss values return index 0 (purple)
- This is the opposite of what we want

Possible fixes:
1. Invert the logic: if points_lost >= threshold instead of <
2. Check if KataGo values are always negative (gains)
3. Verify the loss value sign/direction

The "double inversion" mentioned in Phase 116 notes:
- evaluation_class() logic is inverted
- KataGo pointsLost calculation is also inverted
- They cancel out in Phase 115 by accident
- Phase 116 changes may have broken this balance
""")
else:
    print("The logic appears to be working correctly.")

print("\n" + "="*80)
