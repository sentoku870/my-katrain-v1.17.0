"""Karte test subpackage (Phase E-1).

The original ``tests/test_karte_structure.py`` was 1426 lines and
contained 17 test classes covering several distinct concerns. It was
split into 4 themed submodules for navigability and faster pytest
collection:

- :mod:`tests.karte.test_phase_mistakes` - phase aggregation, streak
  detection, MoveEval reason_tags defaults (~660 lines, 8 classes)
- :mod:`tests.karte.test_difficulty` - difficulty assessment, EvalSnapshot
  difficulty stats (~340 lines, 3 classes)
- :mod:`tests.karte.test_karte_errors` - KarteGenerationError lifecycle,
  build_karte_json_string error paths, streak edge cases (~280 lines, 3 classes)
  (Phase 232: was ``build_karte_report`` until Phase 231)
- :mod:`tests.karte.test_skill_integration` - urgent-miss configs,
  weakness hypothesis, label/threshold consistency (~180 lines, 3 classes)

Pytest discovers all test classes in the submodules automatically;
the parent ``tests/test_karte_structure.py`` file is kept as a thin
deprecation shim that does not define any test classes.
"""
