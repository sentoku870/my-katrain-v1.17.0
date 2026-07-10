"""Eval-metrics test subpackage (Phase D-1).

The original ``tests/test_eval_metrics.py`` was 2316 lines and 18 test
classes. It was split into 4 themed submodules for navigability and
faster pytest collection:

- :mod:`tests.eval_metrics.test_loss` - loss calculation, classification,
  perspective consistency (~450 lines, 7 classes)
- :mod:`tests.eval_metrics.test_snapshots` - EvalSnapshot, iteration,
  distribution consistency (~800 lines, 10 classes)
- :mod:`tests.eval_metrics.test_skill` - skill presets, urgent-miss,
  confidence levels (~800 lines, 5 classes)
- :mod:`tests.eval_metrics.test_evidence` - evidence attachments,
  importance ranking (~350 lines, 2 classes)

Pytest discovers all test classes in the submodules automatically; the
parent ``tests/test_eval_metrics.py`` file is kept as a thin
deprecation shim that re-exports nothing (so test collection does not
double-count).
"""
