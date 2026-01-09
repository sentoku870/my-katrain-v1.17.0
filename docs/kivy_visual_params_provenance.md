# Kivy Visual Parameters Provenance

> **Created**: 2026-01-10
> **Purpose**: Document the source of all visual parameters in the Qt implementation
> **Single Source of Truth**: `katrain_qt/common/eval_constants.py`

---

## 1. Overview

This document traces each visual parameter in the Qt KaTrain implementation back to its
original source in the Kivy KaTrain codebase. This ensures that the Qt version matches
the Kivy version ("本家") in visual appearance.

**Note**: The original Kivy GUI files (`katrain/gui/`) were removed as part of the Qt
migration. The parameters documented here were extracted from the original Kivy source
before removal and are preserved in `katrain_qt/common/eval_constants.py`.

---

## 2. Parameter Categories

### 2.1 Evaluation Thresholds

| Parameter | Qt Value | Original Kivy Source | Notes |
|-----------|----------|---------------------|-------|
| `EVAL_THRESHOLDS_DESC` | `[12.0, 6.0, 3.0, 1.5, 0.5, 0.0]` | `katrain/config.json` trainer/default | Descending order for board overlay |
| `EVAL_THRESHOLDS_ASC` | `[0.2, 0.5, 2.0, 5.0, 8.0]` | Derived from DESC | Ascending order for table rows |
| `LOW_VISITS_THRESHOLD` | `25` | `katrain/config.json` trainer/low_visits | Moves below this shown with lower alpha |
| `OWNERSHIP_THRESHOLD` | `0.1` | `katrain/gui/badukpan.py` | Hide weak territory hints |

### 2.2 Evaluation Colors (Board Overlay)

6-stage color system from worst (index 0) to best (index 5).

| Index | Qt RGB | Original Kivy RGBA | Meaning |
|-------|--------|-------------------|---------|
| 0 | `(114, 33, 107)` | `[0.45, 0.13, 0.42, 1.0]` | Purple - loss >= 12 |
| 1 | `(204, 0, 0)` | `[0.8, 0.0, 0.0, 1.0]` | Red - 6 <= loss < 12 |
| 2 | `(230, 102, 26)` | `[0.9, 0.4, 0.1, 1.0]` | Orange - 3 <= loss < 6 |
| 3 | `(242, 242, 0)` | `[0.95, 0.95, 0.0, 1.0]` | Yellow - 1.5 <= loss < 3 |
| 4 | `(171, 230, 46)` | `[0.67, 0.9, 0.18, 1.0]` | Yellow-green - 0.5 <= loss < 1.5 |
| 5 | `(30, 150, 0)` | `[0.12, 0.59, 0.0, 1.0]` | Green - loss < 0.5 |

**Source**: `katrain/gui/theme.py` `EVAL_COLORS["theme:normal"]`

### 2.3 Evaluation Colors (Table Row Background)

Lighter pastel versions for table rows. Note: Index order is REVERSED from board overlay
(index 0 = best).

| Index | Qt RGB | Meaning |
|-------|--------|---------|
| 0 | `(200, 255, 200)` | Light green - loss <= 0.2 |
| 1 | `(230, 255, 200)` | Light yellow-green - 0.2 < loss <= 0.5 |
| 2 | `(255, 255, 200)` | Light yellow - 0.5 < loss <= 2.0 |
| 3 | `(255, 230, 200)` | Light orange - 2.0 < loss <= 5.0 |
| 4 | `(255, 200, 200)` | Light red - 5.0 < loss <= 8.0 |
| 5 | `(255, 200, 230)` | Light purple - loss > 8.0 |

### 2.4 Special Colors

| Parameter | Qt Value | Original Kivy Value | Source |
|-----------|----------|---------------------|--------|
| `TOP_MOVE_BORDER_COLOR` | `RGB(10, 200, 250)` | `[10/255, 200/255, 250/255]` | `theme.py` TOP_MOVE_BORDER_COLOR |
| `APPROX_BOARD_COLOR` | `RGB(242, 191, 120)` | `[0.95, 0.75, 0.47]` | `theme.py` APPROX_BOARD_COLOR |
| `OWNERSHIP_BLACK_COLOR` | `RGB(0, 0, 26)` | `[0.0, 0.0, 0.10, 0.75]` | `theme.py` OWNERSHIP_COLORS["B"] |
| `OWNERSHIP_WHITE_COLOR` | `RGB(235, 235, 255)` | `[0.92, 0.92, 1.0, 0.80]` | `theme.py` OWNERSHIP_COLORS["W"] |

### 2.5 Alpha and Scale Values

| Parameter | Value | Source |
|-----------|-------|--------|
| `HINT_SCALE` | `0.98` | `theme.py` HINT_SCALE |
| `UNCERTAIN_HINT_SCALE` | `0.7` | `theme.py` UNCERTAIN_HINT_SCALE |
| `HINTS_ALPHA` | `0.8` | `theme.py` HINTS_ALPHA |
| `HINTS_LO_ALPHA` | `0.6` | `theme.py` HINTS_LO_ALPHA |
| `OWNERSHIP_BLACK_ALPHA` | `191` (0.75 * 255) | Derived from OWNERSHIP_COLORS |
| `OWNERSHIP_WHITE_ALPHA` | `204` (0.80 * 255) | Derived from OWNERSHIP_COLORS |
| `MARK_SIZE` | `0.42` | `theme.py` MARK_SIZE |

### 2.6 Mistake Ring Colors

| Classification | Qt RGB | Description |
|----------------|--------|-------------|
| `good` | None | No ring |
| `inaccuracy` | `(242, 242, 0)` | Yellow (matches eval color index 3) |
| `mistake` | `(230, 102, 25)` | Orange (matches eval color index 2) |
| `blunder` | `(204, 0, 0)` | Red (matches eval color index 1) |
| `terrible` | `(114, 33, 107)` | Purple (matches eval color index 0) |

---

## 3. RGBA to RGB Conversion

Kivy uses RGBA values in range [0.0, 1.0]. Qt uses RGB integers [0, 255].

Conversion formula:
```
Qt_value = int(Kivy_value * 255)
```

Example for Purple `[0.45, 0.13, 0.42, 1.0]`:
- R: 0.45 * 255 = 114.75 -> 114
- G: 0.13 * 255 = 33.15 -> 33
- B: 0.42 * 255 = 107.1 -> 107

---

## 4. Threshold Indexing

### Board Overlay (Descending)

The board overlay uses descending thresholds to find the FIRST threshold where
`points_lost >= threshold`:

```python
EVAL_THRESHOLDS_DESC = [12.0, 6.0, 3.0, 1.5, 0.5, 0.0]

i = 0
while i < len(thresholds) - 1 and points_lost < thresholds[i]:
    i += 1
# Result: i is the color index (0=worst, 5=best)
```

### Table Rows (Ascending)

The table row coloring uses ascending thresholds to find the FIRST threshold where
`points_lost > threshold`:

```python
EVAL_THRESHOLDS_ASC = [0.2, 0.5, 2.0, 5.0, 8.0]

color_idx = 0
for j, threshold in enumerate(thresholds):
    if points_lost > threshold:
        color_idx = j + 1
# Result: color_idx is the color index (0=best, 5=worst)
```

---

## 5. Consistency Verification

Run the drift checker to ensure all widgets use the shared constants:

```bash
python scripts/check_threshold_consistency.py
```

This script:
1. Checks that no files have hardcoded threshold/color definitions
2. Verifies that files using eval terms import from the shared module
3. Returns exit code 0 on success, 1 on violations

---

## 6. Files Using Shared Constants

| File | Imports |
|------|---------|
| `katrain_qt/widgets/board_widget.py` | All evaluation constants |
| `katrain_qt/widgets/analysis_panel.py` | `EVAL_ROW_COLORS`, `EVAL_THRESHOLDS_ASC` |
| `katrain_qt/widgets/candidates_panel.py` | Row colors, thresholds, LOW_VISITS |

---

## 7. Changelog

| Date | Change |
|------|--------|
| 2026-01-10 | Initial creation from Phase 0 parameter extraction |
