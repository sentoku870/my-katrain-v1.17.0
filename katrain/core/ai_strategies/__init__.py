"""AI strategy implementations organized by family.

Phase 158+: This subpackage replaces the monolithic ``katrain.core.ai``
strategy classes. Strategies are split into family modules for better
maintainability:

- ``basic.py``   — DefaultStrategy, HandicapStrategy, AntimirrorStrategy, JigoStrategy
- ``score.py``   — ScoreLossStrategy, OwnershipBaseStrategy, SimpleOwnershipStrategy,
                   SettleStonesStrategy
- ``policy.py``  — PolicyStrategy, WeightedStrategy
- ``pick.py``    — PickBasedStrategy (base) + PickStrategy, RankStrategy,
                   InfluenceStrategy, TerritoryStrategy, LocalStrategy, TenukiStrategy
- ``human.py``   — HumanStyleStrategy

All strategies use ``@register_strategy(name)`` decorator (from
``katrain.core.ai_strategies_base``) which populates ``STRATEGY_REGISTRY``.
The registry is populated automatically when this package is imported
(e.g. via ``from katrain.core.ai_strategies import *``).

Backward compatibility: ``katrain.core.ai`` re-exports all strategy classes
so existing imports like ``from katrain.core.ai import DefaultStrategy``
continue to work.
"""

from __future__ import annotations

from katrain.core.ai_strategies.basic import (
    AntimirrorStrategy,
    DefaultStrategy,
    HandicapStrategy,
    JigoStrategy,
)
from katrain.core.ai_strategies.human import HumanStyleStrategy
from katrain.core.ai_strategies.pick import (
    InfluenceStrategy,
    LocalStrategy,
    PickBasedStrategy,
    PickStrategy,
    RankStrategy,
    TenukiStrategy,
    TerritoryStrategy,
)
from katrain.core.ai_strategies.policy import (
    PolicyStrategy,
    WeightedStrategy,
)
from katrain.core.ai_strategies.score import (
    OwnershipBaseStrategy,
    ScoreLossStrategy,
    SettleStonesStrategy,
    SimpleOwnershipStrategy,
)

__all__ = [
    # Basic
    "AntimirrorStrategy",
    "DefaultStrategy",
    "HandicapStrategy",
    "JigoStrategy",
    # Score
    "OwnershipBaseStrategy",
    "ScoreLossStrategy",
    "SettleStonesStrategy",
    "SimpleOwnershipStrategy",
    # Policy
    "PolicyStrategy",
    "WeightedStrategy",
    # Pick
    "InfluenceStrategy",
    "LocalStrategy",
    "PickBasedStrategy",
    "PickStrategy",
    "RankStrategy",
    "TenukiStrategy",
    "TerritoryStrategy",
    # Human
    "HumanStyleStrategy",
]
