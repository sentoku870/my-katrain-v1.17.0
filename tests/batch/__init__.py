"""Batch test subpackage (Phase E-2).

The original ``tests/test_batch_analyzer.py`` was 1156 lines and
contained 24 test classes covering several distinct concerns. It was
split into 4 themed submodules for navigability and faster pytest
collection:

- :mod:`tests.batch.test_discovery` - SGF file collection, encoding
  fallback, basic KaTrainSGF parsing (~250 lines, 5 classes)
- :mod:`tests.batch.test_analyze` - batch analyzer CLI, single-file
  analysis, run-batch helpers (~220 lines, 5 classes)
- :mod:`tests.batch.test_output` - output directory structure, error
  handling, player extraction, filename sanitisation (~340 lines, 5
  classes)
- :mod:`tests.batch.test_helpers` - entropy normalisation, --min-games,
  canonical-loss helper, atomic write, WriteError dataclass
  (~330 lines, 7 classes)

Pytest discovers all test classes in the submodules automatically;
the parent ``tests/test_batch_analyzer.py`` file is kept as a thin
deprecation shim that does not define any test classes.
"""
