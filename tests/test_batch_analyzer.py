"""Deprecation shim for tests/test_batch_analyzer.py.

Phase E-2: the 1156-line ``test_batch_analyzer.py`` was split into 4
themed submodules under :mod:`tests.batch` for navigability:

- ``tests.batch.test_discovery`` - SGF file collection, encoding
  fallback, basic KaTrainSGF parsing
- ``tests.batch.test_analyze`` - batch analyzer CLI, single-file
  analysis, run-batch helpers
- ``tests.batch.test_output`` - output directory structure, error
  handling, player extraction, filename sanitisation
- ``tests.batch.test_helpers`` - entropy normalisation, --min-games,
  canonical-loss helper, atomic write, WriteError dataclass

Pytest discovers the submodules automatically. This module remains
as a thin placeholder so that ``import tests.test_batch_analyzer``
(if anything ever did that) keeps resolving, and ``git log`` still
shows the refactor commit. The module intentionally exports no
symbols to avoid pytest double-collecting the moved test classes.
"""
