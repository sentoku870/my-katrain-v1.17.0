"""AI strategy implementations (Phase 280 slim-down).

Phase 280: Reduced to two survivors. Module structure:
- ``basic.py`` — ``DefaultStrategy`` (ai:default) and ``HandicapStrategy``
  (ai:handicap).

All strategies use ``@register_strategy(name)`` decorator (from
``katrain.core.ai_strategies_base``) which populates ``STRATEGY_REGISTRY``.
The registry is populated automatically when this package is imported
(e.g. via ``from katrain.core.ai_strategies import *``).

Backward compatibility: ``katrain.core.ai`` re-exports the strategy classes
so existing imports like ``from katrain.core.ai import DefaultStrategy``
continue to work.
"""

from __future__ import annotations

from katrain.core.ai_strategies.basic import (
    DefaultStrategy,
    HandicapStrategy,
)

__all__ = [
    "DefaultStrategy",
    "HandicapStrategy",
]
