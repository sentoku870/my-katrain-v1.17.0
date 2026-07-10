"""AI-strategy test subpackage (Phase F-1).

The original ``tests/test_ai_strategies.py`` was 1061 lines and
contained 22 test classes covering several distinct concerns. It was
split into 5 themed submodules for navigability and faster pytest
collection:

- :mod:`tests.ai_strategies.test_helpers` - cross-cutting helpers
  (``ai_rank_estimation``, ``game_report``, ``interp1d/2d``,
  ``generate_ai_move``, request-analysis guards) (~190 lines, 6 classes)
- :mod:`tests.ai_strategies.test_basic_strategies` - DefaultStrategy,
  HandicapStrategy, AntimirrorStrategy, JigoStrategy, ScoreLossStrategy
  (~200 lines, 5 classes)
- :mod:`tests.ai_strategies.test_ownership_strategies` -
  OwnershipBaseStrategy, SimpleOwnershipStrategy, SettleStonesStrategy
  (~95 lines, 3 classes)
- :mod:`tests.ai_strategies.test_select_strategies` - PolicyStrategy,
  WeightedStrategy, PickBasedStrategy, PickStrategy, RankStrategy
  (~175 lines, 5 classes)
- :mod:`tests.ai_strategies.test_special_strategies` - InfluenceStrategy,
  TerritoryStrategy, LocalStrategy, TenukiStrategy, HumanStyleStrategy
  (~105 lines, 5 classes)

Pytest discovers all test classes in the submodules automatically;
the parent ``tests/test_ai_strategies.py`` file is kept as a thin
deprecation shim that does not define any test classes.

The shared ``MockedCn`` fixture and ``ai_test_context`` /
``make_settings`` helpers live in :mod:`tests.ai_strategies._helpers`.
"""
