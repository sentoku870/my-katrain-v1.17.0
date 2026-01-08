# Build KaTrain Qt for Windows using PyInstaller
# Usage: .\tools\build_windows.ps1
#
# Prerequisites:
#   pip install pyinstaller
#
# Output:
#   dist\KaTrainQt\KaTrainQt.exe

$ErrorActionPreference = "Stop"

# Get script directory and repo root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Building KaTrain Qt for Windows" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Repository root: $repoRoot"
Write-Host ""

# Change to repo root
Push-Location $repoRoot

try {
    # Check PyInstaller is installed (use uv run for venv compatibility)
    Write-Host "[1/3] Checking PyInstaller..." -ForegroundColor Yellow
    $pyinstallerCheck = & uv run python -c "import PyInstaller; print(PyInstaller.__version__)" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: PyInstaller not found. Install with: uv pip install pyinstaller" -ForegroundColor Red
        exit 1
    }
    Write-Host "  PyInstaller version: $pyinstallerCheck"

    # Build with PyInstaller
    Write-Host ""
    Write-Host "[2/3] Running PyInstaller..." -ForegroundColor Yellow
    Write-Host "  Entry point: katrain_qt/__main__.py"
    Write-Host "  This may take several minutes..."
    Write-Host ""

    # Simple approach: --collect-all for PySide6, exclude Kivy
    # --clean: Clean build cache
    # --noconfirm: Overwrite without asking
    & uv run pyinstaller `
        --name KaTrainQt `
        --windowed `
        --clean `
        --noconfirm `
        --collect-all PySide6 `
        --exclude-module kivy `
        --exclude-module kivymd `
        --exclude-module ffpyplayer `
        katrain_qt/__main__.py

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: PyInstaller failed" -ForegroundColor Red
        exit 1
    }

    # Check output
    Write-Host ""
    Write-Host "[3/3] Verifying output..." -ForegroundColor Yellow
    $exePath = Join-Path $repoRoot "dist\KaTrainQt\KaTrainQt.exe"
    if (Test-Path $exePath) {
        $exeSize = (Get-Item $exePath).Length / 1MB
        Write-Host "  Output: $exePath"
        Write-Host "  Size: $([math]::Round($exeSize, 2)) MB"

        # Check dist folder size
        $distSize = (Get-ChildItem -Path (Join-Path $repoRoot "dist\KaTrainQt") -Recurse |
                     Measure-Object -Property Length -Sum).Sum / 1MB
        Write-Host "  Total dist size: $([math]::Round($distSize, 2)) MB"
    } else {
        Write-Host "ERROR: Output not found at $exePath" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "BUILD SUCCESS" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "To test:"
    Write-Host "  .\dist\KaTrainQt\KaTrainQt.exe"
    Write-Host ""
    Write-Host "Note: KataGo is NOT bundled."
    Write-Host "Configure KataGo paths in Edit -> Settings after first launch."
    Write-Host ""

} finally {
    Pop-Location
}
