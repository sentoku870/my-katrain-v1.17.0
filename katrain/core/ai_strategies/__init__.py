"""AI strategy implementations organized by family.

Phase 158+: This subpackage replaces the monolithic ``katrain.core.ai``
strategy classes. Strategies are split into family modules for better
maintainability:

- ``basic.py``             — DefaultStrategy, HandicapStrategy, AntimirrorStrategy, JigoStrategy
- ``score.py``             — ScoreLossStrategy, OwnershipBaseStrategy, SimpleOwnershipStrategy,
                             SettleStonesStrategy
- ``policy.py``            — PolicyStrategy, WeightedStrategy
- ``pick_base.py``         — PickBasedStrategy (shared base for pick-family)
- ``pick.py``              — PickStrategy (default AI_PICK)
- ``pick_rank.py``         — RankStrategy
- ``pick_influence.py``    — InfluenceStrategy
- ``pick_territory.py``    — TerritoryStrategy
- ``pick_local.py``        — LocalStrategy
- ``pick_tenuki.py``       — TenukiStrategy
- ``human.py``             — HumanStyleStrategy

All strategies use ``@register_strategy(name)`` decorator (from
``katrain.core.ai_strategies_base``) which populates ``STRATEGY_REGISTRY``.
The registry is populated automatically when this package is imported
(e.g. via ``from katrain.core.ai_strategies import *``).

Backward compatibility: ``katrain.core.ai`` re-exports all strategy classes
so existing imports like ``from katrain.core.ai import DefaultStrategy``
continue to work.

Phase 170: LeelaStrategy removed. Leela is now analysis-only; human-vs-Leela
play (Phase 159B) and the related Phase 160/161 workarounds are gone.

Phase 172: Pick-based strategy family split from a single ``pick.py``
(574 lines) into ``pick_base.py`` + ``pick.py`` + five per-strategy modules
to mirror the structure of other families. ``STRATEGY_REGISTRY`` content
is unchanged; only the source layout changed.
"""

from __future__ import annotations

from katrain.core.ai_strategies.basic import (
    AntimirrorStrategy,
    DefaultStrategy,
    HandicapStrategy,
    JigoStrategy,
)
from katrain.core.ai_strategies.human import HumanStyleStrategy
from katrain.core.ai_strategies.pick_base import PickBasedStrategy
from katrain.core.ai_strategies.pick import PickStrategy
from katrain.core.ai_strategies.pick_rank import RankStrategy
from katrain.core.ai_strategies.pick_influence import InfluenceStrategy
from katrain.core.ai_strategies.pick_territory import TerritoryStrategy
from katrain.core.ai_strategies.pick_local import LocalStrategy
from katrain.core.ai_strategies.pick_tenuki import TenukiStrategy
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
    # Pick (base + 6 derived)
    "PickBasedStrategy",
    "PickStrategy",
    "RankStrategy",
    "InfluenceStrategy",
    "TerritoryStrategy",
    "LocalStrategy",
    "TenukiStrategy",
    # Human
    "HumanStyleStrategy",
]
