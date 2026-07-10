"""Deprecation shim for tests/test_ai_strategies.py.

Phase F-1: the 1061-line ``test_ai_strategies.py`` was split into 5
themed submodules under :mod:`tests.ai_strategies` for navigability:

- ``tests.ai_strategies.test_helpers`` - ai_rank_estimation, game_report,
  interpolation helpers, generate_ai_move, request-analysis guards
- ``tests.ai_strategies.test_basic_strategies`` - Default, Handicap,
  Antimirror, Jigo, ScoreLoss
- ``tests.ai_strategies.test_ownership_strategies`` - OwnershipBase,
  SimpleOwnership, SettleStones
- ``tests.ai_strategies.test_select_strategies`` - Policy, Weighted,
  PickBased, Pick, Rank
- ``tests.ai_strategies.test_special_strategies`` - Influence,
  Territory, Local, Tenuki, HumanStyle

The shared ``MockedCn`` / ``ai_test_context`` / ``make_settings``
helpers live in ``tests.ai_strategies._helpers``.

Pytest discovers the submodules automatically. This module remains
as a thin placeholder so that ``import tests.test_ai_strategies``
(if anything ever did that) keeps resolving, and ``git log`` still
shows the refactor commit. The module intentionally exports no
symbols to avoid pytest double-collecting the moved test classes.
"""
