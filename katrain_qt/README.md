# KaTrain Qt Shell

A Qt (PySide6) frontend for KaTrain, providing Go game review with KataGo analysis.

## Status: M5.0 - Qt Default Runtime

Qt is now the **default** frontend. Kivy is optional.

## Installation

### Standard Install (Qt frontend - recommended)

```bash
pip install .
```

This installs PySide6 and the Qt frontend. **Kivy is NOT installed.**

### Legacy Kivy App (optional)

```bash
pip install .[kivy]
```

### Both Frontends

```bash
pip install .[kivy]
# PySide6 is already included in default dependencies
```

## Quick Start

```bash
# Run from repository root
python -m katrain_qt
```

## KataGo Setup (Manual)

KataGo is **NOT bundled**. You need to install it separately.

### 1. Download KataGo

Get the latest release from: https://github.com/lightvector/KataGo/releases

- Windows: Download `katago-vX.XX.X-windows-x64.zip`
- Extract to a folder (e.g., `C:\KataGo\`)

### 2. Download a Model

From the same releases page, download a neural network model:
- Recommended: `kata1-b18c384nbt-s9.1b.bin.gz` (strong, ~350MB)
- Smaller option: `kata1-b6c96-s175395328.bin.gz` (~25MB)

### 3. Create Analysis Config

Create `analysis.cfg` in your KataGo folder with:

```
# analysis.cfg - minimal configuration for analysis
logSearchInfo = false
logToStderr = false
```

### 4. Configure in KaTrain Qt

1. Launch: `python -m katrain_qt`
2. On first launch, click "Open Settings" in the dialog
3. Set the paths:
   - **Executable**: `C:\KataGo\katago.exe`
   - **Config**: `C:\KataGo\analysis.cfg`
   - **Model**: `C:\KataGo\kata1-b18c384nbt-s9.1b.bin.gz`
4. Click OK

### Alternative: Environment Variables

```powershell
# Windows PowerShell
$env:KATAGO_EXE = "C:\KataGo\katago.exe"
$env:KATAGO_CONFIG = "C:\KataGo\analysis.cfg"
$env:KATAGO_MODEL = "C:\KataGo\model.bin.gz"
python -m katrain_qt
```

## Building Windows Executable

### Prerequisites

```bash
pip install pyinstaller
```

### Build

```powershell
.\tools\build_windows.ps1
```

Or manually:

```bash
pyinstaller --name KaTrainQt --windowed --clean --noconfirm --collect-all PySide6 --exclude-module kivy --exclude-module kivymd katrain_qt/__main__.py
```

### Output

```
dist\KaTrainQt\KaTrainQt.exe
```

### Distribution

The `dist\KaTrainQt\` folder contains everything needed to run. Copy it to any Windows machine.

**Note**: KataGo is NOT included. Users must install it separately (see KataGo Setup above).

## Features

- **SGF file loading and saving** with Save/Save As workflow
- **Unsaved changes prompt** when closing, opening, or starting new games
- **Navigation**: First/Prev/Next/Last moves
- **Click-to-play**: Place stones with mouse (captures and ko handled automatically)
- **Pass**: P key or toolbar button
- **KataGo analysis**: Space to toggle analysis on/off
- **Score graph**: Visual score progression with click-to-navigate
- **Analysis panel**: Winrate, score lead, candidate moves with principal variation
- **Settings persistence**: Window geometry, dock layout, KataGo paths

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| New Game | Ctrl+N |
| Open SGF | Ctrl+O |
| Save | Ctrl+S |
| Save As | Ctrl+Shift+S |
| Previous Move | Left Arrow |
| Next Move | Right Arrow |
| First Move | Home |
| Last Move | End |
| Pass | P |
| Toggle Analysis | Space |
| Settings | Ctrl+, (platform-specific) |

## Settings

### File Locations

- **JSON settings**: `katrain_qt/katrain_qt_settings.json`
  - KataGo paths (exe, config, model)
  - Analysis parameters (max visits, max candidates)
  - Game defaults (komi, rules)
  - Last SGF directory

- **Window geometry**: Platform-specific QSettings
  - Windows: Registry under `HKCU\Software\KaTrain\KaTrain-Qt`
  - macOS: `~/Library/Preferences/com.katrain.KaTrain-Qt.plist`
  - Linux: `~/.config/KaTrain/KaTrain-Qt.conf`

### Environment Variable Overrides

Environment variables take precedence over saved settings:

| Variable | Purpose |
|----------|---------|
| `KATAGO_EXE` | Path to KataGo executable |
| `KATAGO_CONFIG` | Path to analysis config file |
| `KATAGO_MODEL` | Path to neural network model |
| `KATRAIN_QT_LOGLEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) |

Example:
```bash
# Windows PowerShell
$env:KATAGO_EXE = "C:\KataGo\katago.exe"
$env:KATAGO_CONFIG = "C:\KataGo\analysis.cfg"
$env:KATAGO_MODEL = "C:\KataGo\model.bin.gz"
python -m katrain_qt.app_qt

# Linux/macOS
export KATAGO_EXE=/path/to/katago
export KATAGO_CONFIG=/path/to/analysis.cfg
export KATAGO_MODEL=/path/to/model.bin.gz
python -m katrain_qt.app_qt
```

## File Workflow

### Opening Files
- File → Open SGF (Ctrl+O)
- Prompts to save unsaved changes before opening

### Saving Files
- **Save (Ctrl+S)**: Saves to current file path (or shows Save As if new game)
- **Save As (Ctrl+Shift+S)**: Always shows file dialog
- `.sgf` extension added automatically if not specified
- UTF-8 encoding used for all saves

### Dirty State
- Window title shows `*` when there are unsaved changes
- Prompt appears on close/open/new if there are unsaved changes
- Dirty state set when: playing moves, passing
- Dirty state cleared when: saving, loading, starting new game

## Architecture

### Source of Truth

KaTrain core (`katrain/core/`) is the **source of truth** for:
- SGF parsing and game tree
- Board state (stone positions)
- Move validation, captures, ko

The Qt layer is **rendering only**:
- Reads stones from `GameAdapter.get_stones()`
- Sends navigation requests to adapter
- Never computes captures or validates moves itself

### Coordinate Systems

Three coordinate systems are used:

| System | Row Origin | Used By |
|--------|------------|---------|
| **KaTrain Core** | row=0 at BOTTOM | `katrain.core`, `Move.coords` |
| **Qt Rendering** | row=0 at TOP | `board_widget.py`, UI layer |
| **GTP String** | 1-indexed from bottom | KataGo JSON, display labels |

## Development

### Running Tests

```bash
# From repository root
$env:PYTHONUTF8 = "1"  # Windows only
uv run pytest tests/katrain_qt/ -v
```

### Project Structure

```
katrain_qt/
├── __init__.py          # Package init, install_shims()
├── __main__.py          # python -m katrain_qt entry point
├── app_qt.py            # Main application window
├── core_adapter.py      # Wrapper around KaTrain core
├── settings.py          # Settings manager (JSON + QSettings)
├── compat/
│   └── kivy_shim.py     # Mocks for Kivy dependencies
├── analysis/
│   ├── models.py        # Data classes (PositionSnapshot, CandidateMove, etc.)
│   └── katago_engine.py # QProcess-based KataGo manager
├── widgets/
│   ├── board_widget.py      # Go board rendering
│   ├── candidates_panel.py  # Candidate moves list
│   ├── score_graph.py       # Score progression graph
│   └── analysis_panel.py    # Analysis details
└── dialogs/
    ├── __init__.py
    └── settings_dialog.py   # Settings configuration dialog
```

### Files NOT to Modify

- `katrain/` - Original KaTrain code (Kivy app)
- `katrain/core/` - Shared game logic (read-only for Qt dev)

## Known Limitations

Compared to the original Kivy-based KaTrain:

- **Board sizes**: Analysis limited to 19x19 (display supports 9x9, 13x13, 19x19)
- **Features not implemented**:
  - AI vs AI play
  - Timer
  - Themes
  - i18n/translations
  - Teaching/training modes
  - Territory overlay
  - SGF variations editing
  - Move comments editing

## Troubleshooting

### KataGo fails to start

1. Check that paths are correct in Edit → Settings
2. Verify files exist and are readable
3. Try running KataGo directly from command line:
   ```bash
   katago analysis -config analysis.cfg -model model.bin.gz
   ```

### Analysis not showing

1. Press Space to start analysis (or use Analysis menu)
2. Check status bar for error messages
3. Enable debug logging: `KATRAIN_QT_LOGLEVEL=DEBUG`

### Window layout issues

Reset to defaults:
1. Edit → Settings → Reset to Defaults
2. Or delete QSettings manually (see File Locations above)

## Milestone History

- **M3.0-M3.4**: Core functionality, Kivy shims, KataGo integration
- **M4.1**: Score graph
- **M4.2**: Analysis panel with PV display
- **M4.3**: Settings dialog with persistence
- **M4.4**: SGF save with round-trip support
- **M4.5**: MVR complete (dirty state, Save/Save As, documentation)
- **M5.0**: Qt-default runtime (PySide6 default, Kivy optional)
- **M5.0b**: Windows distribution skeleton (PyInstaller baseline)

## License

Same as KaTrain - see main repository LICENSE file.
