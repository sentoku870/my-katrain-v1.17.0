"""Constants package.

Split into four cohesive sub-modules so changes have a narrower blast
radius:

    katrain.core.constants.metadata    PROGRAM_NAME, VERSION, paths, timings
    katrain.core.constants.modes       MODE_*, PLAYER_*, PLAYING_*, GAME_TYPES
    katrain.core.constants.output      OUTPUT_*, STATUS_*, KATAGO_EXCEPTION
    katrain.core.constants.priorities  ADDITIONAL_MOVE_ORDER, PRIORITY_*

New code should import directly from the granular sub-module
(``from katrain.core.constants.output import OUTPUT_DEBUG``).

The package root intentionally no longer re-exports the symbols.
``from katrain.core.constants import X`` is no longer supported and is
caught by ``tests/test_architecture.py::test_constants_uses_granular_imports``.
"""

from __future__ import annotations
