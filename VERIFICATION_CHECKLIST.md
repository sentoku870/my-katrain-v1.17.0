# Phase 116 Regression Fix - Verification Checklist

## Quick Start

Run this command to see expected color mappings:

```powershell
python manual_verification_guide.py
```

## Manual Verification (5-10 minutes)

Follow these exact steps to generate visual proof that the fix works:

### Step 1: Start KaTrain with Logging
```powershell
$env:PYTHONUTF8 = "1"
python -m katrain 2>&1 | Tee-Object -FilePath katrain_verification.log
```

**Wait for**: KaTrain main window to fully load (you'll see various "INFO" messages from Kivy)

### Step 2: Load Test SGF
1. Menu: `File → Open`
2. Navigate to: `tests/data/test_top_moves_color.sgf`
3. Click `Open`

**Expected**: SGF loads without errors

### Step 3: Navigate to a Move with Top Moves
1. Use keyboard arrow keys (← → ↑ ↓) to navigate through moves
2. Look for small colored circles/squares on the board (these are Top Moves indicators)
3. Navigate to move 8-10 to see clear Top Moves colors

**Expected**: You should see colored dots on the board representing candidate moves

### Step 4: Screenshot Evidence
Take a screenshot showing:
- The board with Top Moves colored dots/squares visible
- Multiple colors visible (NOT all the same color/monochrome)
- Colors should range from:
  - **Red/Orange** for bad moves (high loss value)
  - **Yellow** for medium moves
  - **Green** for good moves (low loss value)

**NOT acceptable**: All dots the same color (purple monochrome)

### Step 5: Check Logs for Regression Detection
In the PowerShell window where KaTrain is running:

```powershell
# Stop KaTrain (Alt+F4 or Ctrl+C in PowerShell)
# Check the logs:

Select-String -Path katrain_verification.log -Pattern "PHASE116-REGRESSION-CHECK"
```

**Expected Result**:
- No output (trainer_config was properly initialized)
- OR a few messages during startup only (normal, indicates initialization was catching up)

**Not acceptable**: Many [PHASE116-REGRESSION-CHECK] messages throughout the session

### Step 6: Verify No Errors in Log
```powershell
# Check for Python errors
Select-String -Path katrain_verification.log -Pattern "(KeyError|AttributeError|Traceback)" -Context 2
```

**Expected**: No error output (or at most unrelated GUI warnings)

---

## Verification Checklist

Print this out or use it to verify the fix:

- [ ] **Step 1 PASSED**: KaTrain started and loaded without crashing
- [ ] **Step 2 PASSED**: test_top_moves_color.sgf loaded successfully
- [ ] **Step 3 PASSED**: Top Moves (colored dots) are visible on the board
- [ ] **Step 4 PASSED**: Screenshot shows MULTIPLE colors in Top Moves (red → green gradient)
- [ ] **Step 5 PASSED**: No [PHASE116-REGRESSION-CHECK] messages in logs (or only during init)
- [ ] **Step 6 PASSED**: No KeyError/AttributeError/Traceback in logs

### If all 6 checkboxes are PASSED:
**✓ THE FIX IS WORKING**

### If any checkbox is FAILED:
- Take note of which step failed
- Save the katrain_verification.log file
- Note any error messages
- Report which step(s) failed

---

## Expected Color Mapping

When the fix is working correctly, you should see:

| Loss Value | Expected Color | Example Move Quality |
|-----------|-----------------|----------------------|
| -5.0 | Dark Green | Excellent move (+5 win) |
| -2.0 | Light Green | Good move (+2 win) |
| 0.0 | Yellow | Neutral move |
| 1.0 | Orange | Small loss (-1 point) |
| 5.0 | Red | Large loss (-5 points) |
| 10.0 | Purple/Red | Very bad loss (-10 points) |

**The key**: Colors should gradually shift from RED (bad) → PURPLE (worst) as loss increases, and YELLOW/GREEN as moves get better.

**NOT monochrome purple** (all the same color)

---

## Advanced Verification (for developers)

### Test the eval_color() logic directly
```powershell
uv run pytest tests/test_eval_color_regression.py -v
```

Expected output: **10/10 tests PASSED**

### Run full test suite
```powershell
uv run pytest tests
```

Expected output: **All tests pass** (no regressions introduced)

### Check mypy types
```powershell
uv run mypy katrain
```

Expected output: **Success: no issues found in 205 source files**

---

## Summary

**This checklist verifies that Phase 116 fixes the Top Moves color regression.**

The fix adds defensive `.get()` with defaults to `eval_color()` method in `badukpan.py`, preventing crashes when `trainer_config` is incomplete during initialization.

**Before the fix**: Top Moves would display as monochrome purple (all same color)
**After the fix**: Top Moves display with color gradient (red bad → green good)

---

## Notes

- This is a **visual/behavioral** regression test, not a unit test
- The fix is **backward compatible** (no breaking changes)
- The fix adds **minimal logging** to help detect initialization issues
- No changes to actual color computation logic (only error handling)

For detailed technical analysis, see: `PHASE116_REGRESSION_VERIFICATION.md`
