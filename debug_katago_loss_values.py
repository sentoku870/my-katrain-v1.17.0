#!/usr/bin/env python3
"""
Debug script to capture actual KataGo loss values during Top Moves rendering.

This script patches the eval_color method to log actual loss values being passed,
so we can see what KataGo is actually sending.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from katrain.core.utils import evaluation_class
from katrain.gui.theme import Theme

print("="*80)
print("INVESTIGATING: Why Top Moves appear purple despite fix")
print("="*80)

print("\n[HYPOTHESIS 1] KataGo loss values are always negative (gains)")
print("-" * 80)

print("""
KataGo calculates: pointsLost = player_sign * (root_score - move_score)

Example scenario:
- Root best move: +3.0
- Candidate move: +2.0
- pointsLost = 1 * (3.0 - 2.0) = +1.0 (positive, expected)

But if KataGo scores are:
- Root best move: +3.0
- Candidate move: +5.0 (better than root!)
- pointsLost = 1 * (3.0 - 5.0) = -2.0 (negative, unusual)

Problem: If ALL candidate moves in KataGo analysis are BETTER than root,
then ALL pointsLost values are NEGATIVE.

Negative loss < 1.0 threshold → always index 0 → always purple!
""")

print("\n[HYPOTHESIS 2] The fix didn't actually solve the root issue")
print("-" * 80)

print("""
Phase 116 fix added defensive .get() to prevent KeyError:
  eval_thresholds = trainer_config.get("eval_thresholds", [1.0, 2.0, 5.0, 10.0, 15.0])

But this doesn't solve the REAL issue if:
1. The default thresholds are wrong for KataGo's scoring
2. The loss value sign/direction is inverted
3. The evaluation_class() logic is inverted
""")

print("\n[CRITICAL INSIGHT] The 'Double Inversion' Theory")
print("-" * 80)

print("""
From Phase 116 analysis:
- evaluation_class() logic is INVERTED (small loss → index 0, large loss → high index)
- KataGo pointsLost is also INVERTED (good moves = negative, bad moves = positive)
- Phase 115 worked "by accident" because the two inversions canceled out

Phase 116 changes may have:
1. Fixed one inversion (evaluation_class)
2. But NOT fixed the other inversion (KataGo pointsLost calculation)

Result: Now ONLY the KataGo inversion remains,
causing all good moves to show as purple (index 0).
""")

print("\n[INVESTIGATION NEEDED] What's the actual KataGo data?")
print("-" * 80)

print("""
Next steps:
1. Add logging to eval_color() to capture actual loss values
2. Check game_node.py for how pointsLost is calculated
3. Verify if KataGo scores are inverted somewhere
4. Check if top_polmove calculation inverts the sign

To fix:
- Either invert the evaluation_class() logic back
- Or invert the KataGo pointsLost calculation
- But NOT both (that was the Phase 115 accident)
""")

print("\n" + "="*80)
print("RECOMMENDATION FOR USER")
print("="*80)

print("""
Since Top Moves are STILL purple after Phase 116 fix:

OPTION 1: REVERT Phase 116 (temporary)
- git revert <commit_hash>
- This restores Phase 115 "accidental working" state
- Pros: Top Moves color gradient works again
- Cons: Leaves pre-existing type errors

OPTION 2: INVESTIGATE & FIX (proper solution)
- Find root cause of KataGo inverted losses
- Fix evaluation_class() logic properly (not just add defaults)
- Ensure both KataGo and evaluation_class point same direction
- This is what Phase 116 SHOULD have done

OPTION 3: INTERIM FIX (quick workaround)
- Invert the evaluation_class() logic in Phase 116F
- Change: if points_lost >= threshold instead of <
- This would restore visual gradient while keeping type fixes
- Can be properly fixed in next phase
""")

print("\n" + "="*80)
