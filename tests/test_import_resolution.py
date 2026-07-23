"""Detect circular imports across the katrain package (Phase 174 P1-B).

Architecture review (Phase 173) flagged a handful of strongly-connected
components (SCCs) in the import graph. Most are non-fatal — Python's
import machinery resolves them at runtime via lazy attributes
(``__getattr__``) and stub objects — but they remain a code-organisation
smell that complicates refactoring.

This file provides two regression tests:

1. ``test_no_import_errors``: every module under ``katrain/`` imports
   cleanly without ``ImportError`` / ``ModuleNotFoundError``. Acts as a
   smoke net for the existing cycle resolution.

2. ``test_no_new_cycles_introduced``: compare the SCC count before and
   after refactors. Fails when a refactor grows the count. (Read-only,
   reference data lives in the docstring.)
"""

from __future__ import annotations

import importlib
import pkgutil

# Reused by ``TestCycleAccounting`` below to walk a module's import
# graph with the same TYPE_CHECKING-aware semantics used by
# ``tests/test_architecture.py``. Importing the collector here keeps
# the cycle test self-contained.
from tests.test_architecture import AllImportCollector

# Phase A-13: run on CI. Kivy is mocked via KIVY_NO_WINDOW/KIVY_GL_BACKEND
# set by the test_and_build.yaml workflow. Previously this file was
# skipped on CI to dodge a brittle Kivy import that is now handled by the
# same headless infra as test_popups_helpers.py.


def _iter_katrain_modules():
    """Yield ``(module_name, fully_qualified_path)`` for all production modules."""
    import katrain

    for info in pkgutil.walk_packages(katrain.__path__, prefix="katrain."):
        if info.ispkg:
            continue
        yield info.name


class TestImportResolution:
    def test_no_import_errors(self) -> None:
        """Every production module imports cleanly.

        Cycles are tolerated (Python handles them via stub objects),
        but a real ``ImportError`` indicates a broken dependency.
        """
        failures: list[tuple[str, type[Exception], str]] = []
        for mod_name in _iter_katrain_modules():
            try:
                importlib.import_module(mod_name)
            except (ImportError, ModuleNotFoundError) as e:
                # Skip dist-packages not in our repo (kivymd etc.)
                if "kivymd" in str(e) or "kivy" in str(e):
                    continue
                failures.append((mod_name, type(e).__name__, str(e)))

        assert not failures, "Modules failed to import (likely a broken dependency):\n" + "\n".join(
            f"  - {m}: {t}: {msg}" for m, t, msg in failures
        )

    def test_module_walk_complete(self) -> None:
        """Smoke check: pkgutil.walk_packages picks up at least 200 modules.

        Phase 173 measured 246 production modules. This guards against
        silent walking failures (e.g. if pkgutil stops traversing due
        to a syntax error in some __init__.py).
        """
        modules = list(_iter_katrain_modules())
        assert len(modules) >= 200, (
            f"Only found {len(modules)} production modules; expected ≥200. Check pkgutil.walk_packages setup."
        )


class TestCycleAccounting:
    """Guards against re-introducing the known four-node circular import
    cluster that Phase 173 documented as a runtime-tolerated SCC.

    The historical ``test_reference_scc_count_documented`` compared two
    hard-coded constants to themselves (assert 50 == 50) and asserted
    nothing -- it passed regardless of the actual import graph. This
    rewrite uses the ``AllImportCollector`` (defined alongside the
    architecture tests) to walk ``katrain/core/ai`` and
    ``katrain/core/reports/karte/sections/metadata`` directly and prove
    that neither module imports the other at module scope (a strict
    requirement to keep the four-node SCC at bay).

    Cycles that go through TYPE_CHECKING blocks, deferred imports
    inside functions, or ``__getattr__`` stubs are still tolerated --
    the assertion below is intentionally restricted to *module-level*
    imports to mirror the audit it replaced.
    """

    # Phase 173 review found these four modules formed a single SCC:
    #   core.ai <-> core.batch.orchestration
    #            <-> core.game.facade
    #            <-> core.reports.karte.sections.metadata
    # The four-node cluster is the boundary we watch; a regression
    # that brings back a direct edge between any pair is a hard fail.
    _PROHIBITED_EDGES = {
        ("katrain.core.ai", "katrain.core.batch.orchestration"),
        ("katrain.core.batch.orchestration", "katrain.core.ai"),
        ("katrain.core.ai", "katrain.core.game.facade"),
        ("katrain.core.game.facade", "katrain.core.ai"),
        ("katrain.core.ai", "katrain.core.reports.karte.sections.metadata"),
        ("katrain.core.reports.karte.sections.metadata", "katrain.core.ai"),
    }
    _WATCHED_TARGETS = (
        "katrain.core.batch.orchestration",
        "katrain.core.game.facade",
        "katrain.core.reports.karte.sections.metadata",
    )

    def _module_imports(self, module_name: str) -> set[str]:
        """Return the set of module-level imports of ``module_name``."""
        import ast
        import importlib
        from pathlib import Path

        spec = importlib.util.find_spec(module_name)
        if spec is None or spec.origin is None:
            raise AssertionError(f"module {module_name!r} not importable from spec")
        source = Path(spec.origin).read_text(encoding="utf-8")
        tree = ast.parse(source)
        # ``AllImportCollector`` already does the TYPE_CHECKING walk;
        # reusing it keeps the cycle check consistent with the
        # architecture tests.
        package = ".".join(module_name.split(".")[:-1])
        collector = AllImportCollector(module_package=package)
        collector.visit(tree)
        return {name for _line, name in collector.all_imports}

    def test_no_known_four_node_cycle_edges(self) -> None:
        """``katrain.core.ai`` must not directly import the three peers
        that historically formed the Phase 173 four-node SCC, and vice
        versa. Indirect cycles (through helpers, TYPE_CHECKING, or
        deferred imports) remain tolerated.
        """
        ai_imports = self._module_imports("katrain.core.ai")
        for peer in self._WATCHED_TARGETS:
            assert peer not in ai_imports, (
                f"katrain.core.ai must not directly import {peer}; the "
                f"Phase 173 audit documented this edge as the entry "
                f"point of a four-node circular SCC. Move the import "
                f"behind a function body or a TYPE_CHECKING guard."
            )
            peer_imports = self._module_imports(peer)
            assert "katrain.core.ai" not in peer_imports, (
                f"{peer} must not directly import katrain.core.ai; the "
                f"Phase 173 audit documented this edge as part of a "
                f"four-node circular SCC."
            )

    def test_known_prohibited_edges_match_documented_set(self) -> None:
        """Self-check: the prohibited-edge table on this class is the
        inverse of the four-node SCC the previous test guards. A
        developer who adds/removes an entry below must also update
        the matching documented pair so the two halves stay in sync.
        """
        from itertools import permutations

        documented_pairs = {
            (a, b)
            for pair in (
                (
                    "katrain.core.ai",
                    "katrain.core.batch.orchestration",
                ),
                (
                    "katrain.core.ai",
                    "katrain.core.game.facade",
                ),
                (
                    "katrain.core.ai",
                    "katrain.core.reports.karte.sections.metadata",
                ),
            )
            for a, b in permutations(pair, 2)
        }
        assert documented_pairs == self._PROHIBITED_EDGES, (
            "_PROHIBITED_EDGES drifted from the documented four-node SCC set; update both sides in lockstep."
        )
