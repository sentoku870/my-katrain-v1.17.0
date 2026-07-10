"""Deprecation shim for tests/test_karte_structure.py.

Phase E-1: the 1426-line ``test_karte_structure.py`` was split into 4
themed submodules under :mod:`tests.karte` for navigability:

- ``tests.karte.test_phase_mistakes`` - phase aggregation, streak
  detection, MoveEval defaults (~660 lines, 8 classes)
- ``tests.karte.test_difficulty`` - difficulty assessment, EvalSnapshot
  difficulty stats (~340 lines, 3 classes)
- ``tests.karte.test_karte_errors`` - KarteGenerationError lifecycle,
  build_karte_report error paths, streak edge cases (~280 lines, 3 classes)
- ``tests.karte.test_skill_integration`` - urgent-miss configs,
  weakness hypothesis, label/threshold consistency (~180 lines, 3 classes)

Pytest discovers the submodules automatically. This module remains
as a thin placeholder so that ``import tests.test_karte_structure``
(if anything ever did that) keeps resolving, and ``git log`` still
shows the refactor commit. The module intentionally exports no
symbols to avoid pytest double-collecting the moved test classes.
"""
