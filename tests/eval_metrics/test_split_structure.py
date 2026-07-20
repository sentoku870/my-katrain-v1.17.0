"""Regression tests for the Phase E-1 / E-2 test-file splits.

The original ``tests/test_eval_metrics.py`` (2316 lines, Phase D-1)
and ``tests/test_batch_analyzer.py`` (1156 lines, Phase E-2) were both
split into themed subpackages in 2026-07. These tests guard the split
so future additions go to the right file and we don't accidentally
regress to monolithic files.

Phase 280: ``tests/ai_strategies/`` subpackage collapsed back into
``tests/test_ai.py`` when only two AI strategies survived the slim-down.
The corresponding entry in ``SPLIT_FILES`` and the deprecation shim
``tests/test_ai_strategies.py`` were removed at the same time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Files required for each split. The shim must exist and must NOT
# define any test classes (that would cause double-collection).
SPLIT_FILES: dict[str, tuple[str, ...]] = {
    "tests/eval_metrics/": (
        "__init__.py",
        "test_loss.py",
        "test_snapshots.py",
        "test_skill.py",
        "test_evidence.py",
        "test_split_structure.py",
    ),
    "tests/karte/": (
        "__init__.py",
        "test_phase_mistakes.py",
        "test_difficulty.py",
        "test_karte_errors.py",
        "test_skill_integration.py",
    ),
    "tests/batch/": (
        "__init__.py",
        "test_discovery.py",
        "test_analyze.py",
        "test_output.py",
        "test_helpers.py",
    ),
    "tests/cluster_classifier/": (
        "__init__.py",
        "_helpers.py",
        "test_semantics.py",
        "test_stone_reconstruction.py",
        "test_classification.py",
    ),
}

# Original monolithic files that have been replaced by deprecation shims.
DEPRECATION_SHIMS = (
    "tests/test_eval_metrics.py",
    "tests/test_karte_structure.py",
    "tests/test_batch_analyzer.py",
    "tests/test_cluster_classifier.py",
)


class TestSplitFilesExist:
    @pytest.mark.parametrize("subpackage,files", list(SPLIT_FILES.items()))
    def test_all_split_files_exist(self, subpackage: str, files: tuple[str, ...]) -> None:
        repo_root = self._repo_root()
        for f in files:
            path = repo_root / subpackage / f
            assert path.exists(), f"missing {subpackage}{f}"


class TestDeprecationShims:
    @pytest.mark.parametrize("shim", DEPRECATION_SHIMS)
    def test_shim_has_no_test_classes(self, shim: str) -> None:
        """A deprecation shim must not define any test classes, which
        would cause pytest to double-collect the moved test classes."""
        repo_root = self._repo_root()
        text = (repo_root / shim).read_text(encoding="utf-8")
        assert "class Test" not in text, (
            f"{shim} is a deprecation shim; do not add new Test* classes here. "
            f"Add them to the appropriate subpackage instead."
        )

    @pytest.mark.parametrize("shim", DEPRECATION_SHIMS)
    def test_shim_has_no_star_imports(self, shim: str) -> None:
        """A deprecation shim must not use ``import *``; that re-exports
        test classes and triggers double collection."""
        repo_root = self._repo_root()
        text = (repo_root / shim).read_text(encoding="utf-8")
        assert "import *" not in text, (
            f"{shim} must not use wildcard imports; they cause pytest to double-collect the moved test classes."
        )


class TestSplitSize:
    """Each split file stays under 1000 lines so individual files are
    easy to navigate and pytest can collect them quickly."""

    MAX_LINES = 1000

    @pytest.mark.parametrize("subpackage,files", list(SPLIT_FILES.items()))
    def test_file_under_max_lines(self, subpackage: str, files: tuple[str, ...]) -> None:
        repo_root = self._repo_root()
        for f in files:
            if not f.endswith(".py"):
                continue
            line_count = len((repo_root / subpackage / f).read_text(encoding="utf-8").splitlines())
            assert line_count <= self.MAX_LINES, (
                f"{subpackage}{f} has {line_count} lines; max is {self.MAX_LINES}. "
                f"Consider splitting into a new submodule."
            )


def _repo_root() -> Path:
    # __file__ = tests/eval_metrics/test_split_structure.py
    return Path(__file__).resolve().parent.parent.parent


# Module-level alias for the @staticmethod-free class access pattern.
TestSplitFilesExist._repo_root = staticmethod(_repo_root)  # type: ignore[attr-defined]
TestDeprecationShims._repo_root = staticmethod(_repo_root)  # type: ignore[attr-defined]
TestSplitSize._repo_root = staticmethod(_repo_root)  # type: ignore[attr-defined]
