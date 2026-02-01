# katrain/gui/features/commands/analyze_commands.py
from __future__ import annotations

"""Analysis-related command handlers extracted from KaTrainGui (Phase 41-B).

These functions handle analysis mode changes and related operations.
The ctx parameter is expected to be a KaTrainGui instance (satisfies FeatureContext).
"""

from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui
    from katrain.core.constants import AnalysisMode


def do_analyze_extra(ctx: "KaTrainGui", mode: Union[str, "AnalysisMode"], **kwargs: Any) -> None:
    """Perform extra analysis in the specified mode.

    Args:
        ctx: KaTrainGui instance
        mode: Analysis mode (string or AnalysisMode enum)
        **kwargs: Additional arguments passed to game.analyze_extra
    """
    from katrain.core.constants import parse_analysis_mode

    # Normalize mode at entry point (game.analyze_extra also normalizes, but explicit here for clarity)
    mode = parse_analysis_mode(mode)
    if ctx.game:
        ctx.game.analyze_extra(mode, **kwargs)
