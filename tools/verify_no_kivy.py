#!/usr/bin/env python3
"""
Verify Qt app works without Kivy installed.

This script:
1. Creates a temporary venv
2. Installs the project with `pip install -e .`
3. Verifies Kivy is NOT installed
4. Runs: `pytest tests/katrain_qt/ -v`
5. Reports pass/fail

Usage:
    python tools/verify_no_kivy.py

Requirements:
    - Python 3.13+
    - Must be run from repository root
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run_cmd(cmd: list, cwd: str = None, env: dict = None) -> tuple:
    """Run a command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def main():
    # Determine repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Verify we're in the right place
    if not (repo_root / "pyproject.toml").exists():
        print("ERROR: Must run from repository root")
        print(f"  Expected pyproject.toml at: {repo_root / 'pyproject.toml'}")
        return 1

    if not (repo_root / "katrain_qt").is_dir():
        print("ERROR: katrain_qt directory not found")
        return 1

    print("=" * 60)
    print("Verify Qt App Without Kivy")
    print("=" * 60)
    print(f"Repository root: {repo_root}")
    print()

    # Create temporary venv
    venv_dir = tempfile.mkdtemp(prefix="katrain_qt_test_")
    print(f"Creating temp venv: {venv_dir}")

    try:
        # Determine Python executable
        python_exe = sys.executable

        # Create venv
        print("\n[1/5] Creating virtual environment...")
        rc, out, err = run_cmd([python_exe, "-m", "venv", venv_dir])
        if rc != 0:
            print(f"ERROR: Failed to create venv: {err}")
            return 1

        # Determine venv Python/pip paths
        if sys.platform == "win32":
            venv_python = Path(venv_dir) / "Scripts" / "python.exe"
            venv_pip = Path(venv_dir) / "Scripts" / "pip.exe"
        else:
            venv_python = Path(venv_dir) / "bin" / "python"
            venv_pip = Path(venv_dir) / "bin" / "pip"

        # Upgrade pip
        print("\n[2/5] Upgrading pip...")
        rc, out, err = run_cmd([str(venv_pip), "install", "--upgrade", "pip"])
        if rc != 0:
            print(f"WARNING: pip upgrade failed: {err}")

        # Install project (editable)
        print("\n[3/5] Installing project (pip install -e .)...")
        rc, out, err = run_cmd(
            [str(venv_pip), "install", "-e", "."],
            cwd=str(repo_root),
        )
        if rc != 0:
            print(f"ERROR: pip install failed:")
            print(err)
            return 1
        print("  Install successful")

        # Verify Kivy is NOT installed
        print("\n[4/5] Verifying Kivy is NOT installed...")
        rc, out, err = run_cmd([str(venv_pip), "list"])
        installed_packages = out.lower()

        if "kivy" in installed_packages:
            print("FAIL: Kivy is installed (should NOT be)")
            print("  Installed packages containing 'kivy':")
            for line in out.split("\n"):
                if "kivy" in line.lower():
                    print(f"    {line}")
            return 1
        print("  OK: Kivy is NOT installed")

        # Verify PySide6 IS installed
        if "pyside6" not in installed_packages:
            print("FAIL: PySide6 is NOT installed (should be)")
            return 1
        print("  OK: PySide6 IS installed")

        # Run Qt tests
        print("\n[5/5] Running Qt tests...")
        # Install pytest in the venv
        rc, out, err = run_cmd([str(venv_pip), "install", "pytest"])
        if rc != 0:
            print(f"WARNING: pytest install issue: {err}")

        # Set UTF-8 environment for Windows
        test_env = os.environ.copy()
        test_env["PYTHONUTF8"] = "1"

        rc, out, err = run_cmd(
            [str(venv_python), "-m", "pytest", "tests/katrain_qt/", "-v"],
            cwd=str(repo_root),
            env=test_env,
        )

        print(out)
        if err:
            print(err)

        if rc != 0:
            print("\nFAIL: Tests failed")
            return 1

        print("\n" + "=" * 60)
        print("SUCCESS: All checks passed!")
        print("  - Kivy is NOT installed")
        print("  - PySide6 IS installed")
        print("  - Qt tests pass")
        print("=" * 60)
        return 0

    finally:
        # Cleanup
        print(f"\nCleaning up: {venv_dir}")
        try:
            shutil.rmtree(venv_dir)
        except Exception as e:
            print(f"WARNING: Failed to cleanup: {e}")


if __name__ == "__main__":
    sys.exit(main())
