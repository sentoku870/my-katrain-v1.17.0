"""Forward-reference aggregator for the engine subsystem (Phase B1).

The engine subsystem is split across multiple modules to keep each one
focussed:

- ``katrain.core.engine`` — ``BaseEngine`` / ``KataGoEngine`` class
  definitions.
- ``katrain.core.engine_io`` — pipe-reader thread implementations.
- ``katrain.core.engine_query`` — query builders / lifecycle helpers.
- ``katrain.core.engine_cmd`` — analysis-command dispatch.

Each helper module needs to reference ``KataGoEngine`` and ``GameNode``
in function signatures but cannot import them at module level without
triggering a runtime cycle (engine.py pulls engine_query back in via
delayed imports). The historical workaround was a ``TYPE_CHECKING``
guard in each module::

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from katrain.core.engine import KataGoEngine
        from katrain.core.game_node import GameNode

That worked but duplicated the same TYPE_CHECKING block in four
places and made the cycle relationship implicit. Phase B1 centralises
those imports here so each helper imports from a single place.

This module performs **only** ``TYPE_CHECKING`` imports — it has no
runtime symbols, no module-level work, and no impact on production
import order. The forward references flow through this single
file, so a developer who needs to follow the dependency graph can
read it in one place instead of opening every helper module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine
    from katrain.core.game_node import GameNode

__all__ = ["KataGoEngine", "GameNode"]
