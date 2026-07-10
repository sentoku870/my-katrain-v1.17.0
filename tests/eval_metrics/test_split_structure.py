"""Regression test for the test_eval_metrics subpackage split (Phase D-1).

The 2316-line ``tests/test_eval_metrics.py`` was split into 4 themed
submodules in 2026-07. This test guards the split so future additions
go to the right file and we don't accidentally regress to a single
giant file.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# Anchor: the 4 split files plus the deprecation shim.
EXPECTED_SUBMODULE_FILES = (
    "tests/eval_metrics/__init__.py",
    "tests/eval_metrics/test_loss.py",
    "tests/eval_metrics/test_snapshots.py",
    "tests/eval_metrics/test_skill.py",
    "tests/eval_metrics/test_evidence.py",
    "tests/test_eval_metrics.py",
)


class TestSubpackageStructure:
    @staticmethod
    def _repo_root() -> Path:
        # __file__ = tests/eval_metrics/test_split_structure.py
        # parent.parent.parent = repo root
        return Path(__file__).resolve().parent.parent.parent

    def test_subpackage_files_exist(self) -> None:
        repo_root = self._repo_root()
        for rel in EXPECTED_SUBMODULE_FILES:
            assert (repo_root / rel).exists(), f"missing split file: {rel}"

    def test_shim_has_no_test_classes(self) -> None:
        """The shim must not re-export test classes; that would cause
        pytest to double-collect them."""
        repo_root = self._repo_root()
        shim_text = (repo_root / "tests/test_eval_metrics.py").read_text(encoding="utf-8")
        # The shim is a no-op placeholder; it should not define any
        # `class Test*` (which would re-trigger collection).
        assert "class Test" not in shim_text, (
            "tests/test_eval_metrics.py is a deprecation shim; do not add new "
            "Test* classes here. Add them to tests/eval_metrics/test_*.py instead."
        )

    def test_shim_has_no_star_imports(self) -> None:
        """The shim must not use ``import *``; that re-exports test
        classes and triggers double collection."""
        repo_root = self._repo_root()
        shim_text = (repo_root / "tests/test_eval_metrics.py").read_text(encoding="utf-8")
        assert "import *" not in shim_text, (
            "tests/test_eval_metrics.py must not use wildcard imports; they "
            "cause pytest to double-collect the moved test classes."
        )

    def test_no_double_collection(self) -> None:
        """The 154 eval-metrics tests must only be collected from the
        submodules, not the shim. We exclude this test file itself
        (test_split_structure.py) from the count since it adds 8 new
        structural tests on top of the original 154."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "--collect-only",
                "-q",
                "tests/test_eval_metrics.py",
                "tests/eval_metrics/test_loss.py",
                "tests/eval_metrics/test_snapshots.py",
                "tests/eval_metrics/test_skill.py",
                "tests/eval_metrics/test_evidence.py",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        # Count test occurrences per file path.
        shim_collects = sum(1 for line in result.stdout.splitlines() if "tests/test_eval_metrics.py::" in line)
        submodule_collects = sum(
            1
            for line in result.stdout.splitlines()
            if "tests/eval_metrics/test_loss" in line
            or "tests/eval_metrics/test_snapshots" in line
            or "tests/eval_metrics/test_skill" in line
            or "tests/eval_metrics/test_evidence" in line
        )
        # Total: 154 expected from the original monolithic file.
        assert shim_collects == 0, f"shim collected {shim_collects} tests; expected 0 to avoid double-collection"
        assert submodule_collects == 154, (
            f"submodules collected {submodule_collects}; expected 154 from the original test_eval_metrics.py"
        )


class TestSubpackageSize:
    """Each split file stays under 800 lines so individual files are
    easy to navigate and pytest can collect them quickly."""

    MAX_LINES = 800

    @pytest.mark.parametrize(
        "rel",
        [
            "tests/eval_metrics/test_loss.py",
            "tests/eval_metrics/test_snapshots.py",
            "tests/eval_metrics/test_skill.py",
            "tests/eval_metrics/test_evidence.py",
        ],
    )
    def test_file_under_max_lines(self, rel: str) -> None:
        repo_root = TestSubpackageStructure._repo_root()
        line_count = len((repo_root / rel).read_text(encoding="utf-8").splitlines())
        assert line_count <= self.MAX_LINES, (
            f"{rel} has {line_count} lines; max is {self.MAX_LINES}. Consider splitting into a new submodule."
        )
