"""Deprecation shim for tests/test_eval_metrics.py.

Phase D-1: the 2316-line ``test_eval_metrics.py`` was split into 4
themed submodules under :mod:`tests.eval_metrics` for navigability:

- ``tests.eval_metrics.test_loss`` - loss calculation, classification,
  perspective consistency
- ``tests.eval_metrics.test_snapshots`` - EvalSnapshot, iteration,
  distribution consistency
- ``tests.eval_metrics.test_skill`` - skill presets, urgent-miss,
  confidence levels
- ``tests.eval_metrics.test_evidence`` - evidence attachments,
  importance ranking

Pytest discovers the submodules automatically. This module remains
as a thin placeholder so that ``import tests.test_eval_metrics`` (if
anything ever did that) keeps resolving, and ``git log`` still shows
the refactor commit. The module intentionally exports no symbols to
avoid pytest double-collecting the moved test classes.
"""
