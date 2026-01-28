# PySide6 Go Board PoC

Minimal proof-of-concept for a 19x19 Go board UI using PySide6 (Qt).

## Purpose

Validate feasibility of moving KaTrain's board UI from Kivy to Qt (PySide6).
This is a standalone PoC - it does **not** modify any existing KaTrain/Kivy code.

## Features

- 19x19 grid with 9 star points (hoshi)
- Left-click to place stones (alternating Black/White)
- Right-click to remove stones
- Last move marker (contrasting ring)
- Hover ghost showing next stone position
- Status bar with coordinates and validity
- Proper resize handling (board stays square)

## Requirements

- Python 3.13+
- PySide6

## Installation & Running (Windows PowerShell)

```powershell
# Navigate to repo root
cd D:\github\katrain-1.17.0

# (Optional) Set execution policy for current process if script activation is blocked
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Create virtual environment (first time only)
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r tools\pyside_board_poc\requirements.txt

# Run the PoC
python tools\pyside_board_poc\board_poc.py
```

## Usage

| Action | Effect |
|--------|--------|
| **Left-click** | Place stone at nearest intersection (Black first, then alternating) |
| **Right-click** | Remove stone at nearest intersection |
| **Mouse hover** | Shows ghost of next stone; status bar updates with position |

## Design Notes

### Tunable Parameters (in `board_poc.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MARGIN_RATIO` | 0.05 | Margin as ratio of widget size |
| `MARGIN_MIN` | 20 | Minimum margin in pixels |
| `STONE_RADIUS_RATIO` | 0.45 | Stone radius as ratio of grid spacing |
| `HOSHI_RADIUS_RATIO` | 0.12 | Star point radius as ratio of grid spacing |
| `HIT_THRESHOLD_RATIO` | 0.45 | Click valid if within this ratio of spacing from intersection |

### Architecture

- `GoBoardWidget(QWidget)`: Handles rendering and mouse events
- `MainWindow(QMainWindow)`: Contains board + status bar
- Signal/slot pattern for loose coupling between board and status bar
- Uses `QRectF`/`QPointF` (float geometry) to reduce drift on resize/HiDPI

### Move History Rules

- `stones` dict tracks current board state: `{(i, j): "B" or "W"}`
- `move_history` list tracks placement order: `[(i, j, color), ...]`
- Next color derived from history length: `"B" if len(history) % 2 == 0 else "W"`
- On right-click removal: removes from both `stones` and `move_history` (scans from end)

---

# PySide6 Go Board PoC+ (Extended)

Extended proof-of-concept adding SGF loading, move navigation, and KataGo integration.

## Purpose

Validate feasibility of:
- SGF file loading and move navigation (19x19 only)
- Overlay drawing (candidate moves with rank/value/visits)
- KataGo integration for real analysis (with dummy fallback)

## Running PoC+

```powershell
# Navigate to repo root
cd D:\github\katrain-1.17.0

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run the extended PoC
python tools\pyside_board_poc\board_poc_plus.py
```

## PoC+ Features

### SGF Loading
- **File → Open SGF (Ctrl+O)**: Load any SGF file
- **File → Open Sample SGF**: Load built-in sample game (36 moves)
- Supports main sequence only (variations are ignored)
- Parses B[], W[], AB[], AW[] properties

### Move Navigation

| Action | Effect |
|--------|--------|
| **← (Left Arrow)** | Previous move |
| **→ (Right Arrow)** | Next move |
| **Home** | Go to initial position |
| **End** | Go to final position |
| **Toolbar buttons** | First / Prev / Next / Last |

### Analysis Overlay

| Action | Effect |
|--------|--------|
| **Space** | Toggle analysis start/stop |
| **View → Show Overlay** | Toggle overlay visibility |
| **Analysis → Start/Stop** | Start or stop analysis |
| **Analysis → Configure KataGo** | Configure KataGo paths |

- Displays up to 5 candidate moves as blue circles
- Each candidate shows rank (1-5) and value (±points)
- With KataGo: shows score lead and visit count
- **Fallback**: Without KataGo configured, uses dummy analysis (random but deterministic)

### KataGo Configuration

To enable real analysis, configure KataGo via **Analysis → Configure KataGo**:

1. **KataGo Executable**: Path to `katago.exe`
2. **Analysis Config**: Path to `analysis_config.cfg` (can use KaTrain's config at `katrain/KataGo/analysis_config.cfg`)
3. **Model File**: Path to neural network model (`.bin.gz`)

Settings are saved to `poc_settings.json` in the PoC directory.

**Environment Variables** (optional, override file settings):
- `KATAGO_EXE`: Path to KataGo executable
- `KATAGO_CONFIG`: Path to analysis config
- `KATAGO_MODEL`: Path to model file

Example (PowerShell):
```powershell
$env:KATAGO_EXE = "C:\path\to\katago.exe"
$env:KATAGO_CONFIG = "D:\github\katrain-1.17.0\katrain\KataGo\analysis_config.cfg"
$env:KATAGO_MODEL = "C:\path\to\model.bin.gz"
python tools\pyside_board_poc\board_poc_plus.py
```

### Edit Mode

| Action | Effect |
|--------|--------|
| **Edit → Edit Mode** | Toggle edit mode |
| **Left-click (edit mode)** | Place stone |
| **Right-click (edit mode)** | Remove stone |

- Edits apply to current position only
- Navigation resets edits (they are not saved to SGF)

### Candidates Panel (Right Dock)

- Shows candidate list as text
  - KataGo: `1. D16: +3.20 (1500 visits)`
  - Dummy: `1. D16: +0.25`
- Updates in sync with overlay

## Coordinate System

- **Internal**: `(col, row)` where col=0..18 (left to right), row=0..18 (top to bottom)
- **SGF**: `"aa"` = top-left = `(col=0, row=0)`
- **Display**: `"A1"` style (letter + number), **without 'I' skip** (simplified for PoC)
  - `col=0` → `'A'`, `col=8` → `'I'` (not skipped)
  - `row=0` → `19`, `row=18` → `1`

## Architecture (PoC+)

### Files

| File | Description |
|------|-------------|
| `board_poc_plus.py` | Main application (~1000 lines) |
| `models.py` | BoardModel + AnalysisModel + GTP utils (~470 lines) |
| `katago_engine.py` | KataGo process management (~490 lines) |
| `poc_settings.json` | KataGo path settings (auto-generated) |
| `sample.sgf` | Test SGF file (36 moves) |

### Architecture Modes

**KataGo Mode (default if configured):**
```
MainWindowPlus (GUI Thread)
  ├─ BoardModel ───────────────→ get_position_snapshot()
  │                                       │
  ├─ KataGoEngine ←──────────── PositionSnapshot
  │   ├─ QProcess (async I/O)
  │   │   ├─ stdin ← JSON query
  │   │   └─ stdout → JSON response (buffered)
  │   └─ _read_buffer (newline-delimited)
  │                                       │
  ├─ AnalysisModel ←─────────── [CandidateMove, ...]
  │                                       │
  ├─ BoardWidgetPlus ────────── overlay drawing
  └─ CandidatesPanel ────────── list display
```

**Dummy Fallback Mode (when KataGo not configured):**
```
Main Thread                     Worker Thread
─────────────────────────────────────────────────
MainWindowPlus                  AnalysisWorker
  ├─ BoardWidgetPlus              ├─ QTimer (created in start())
  ├─ CandidatesPanel              └─ _generate_candidates()
  └─ BoardModel, AnalysisModel
```

**Key Design Points**:
- **KataGo Mode**: All in GUI thread, QProcess handles async I/O
- **Dummy Mode**: Worker thread with QTimer for periodic updates
- 200ms debounce for KataGo queries on rapid position changes
- Query ID management for stale response filtering
- Newline-delimited JSON buffering for robust parsing
- `initialStones` approach for position representation (works with edit mode)

### Tunable Parameters (in `board_poc_plus.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OVERLAY_RADIUS_RATIO` | 0.38 | Overlay circle radius as ratio of spacing |
| `OVERLAY_ALPHA` | 120 | Overlay transparency (0-255) |
| `OVERLAY_COLOR` | `#0064FF` | Overlay color (blue) |
| `ANALYSIS_INTERVAL_MS` | 500 | Dummy analysis update interval (ms) |
| `MAX_CANDIDATES` | 5 | Maximum candidates to show |
| `LABEL_FONT_RATIO` | 0.28 | Label font size as ratio of spacing |
| `DEBOUNCE_MS` | 200 | KataGo query debounce delay (ms) |

### KataGo Settings (in `katago_engine.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DEFAULT_MAX_VISITS` | 1000 | Maximum search visits per query |
| `DEFAULT_KOMI` | 6.5 | Default komi value |
| `DEFAULT_RULES` | "japanese" | Default rules |
| `MAX_CANDIDATES` | 5 | Max candidates parsed from response |
