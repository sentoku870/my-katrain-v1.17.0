# katrain/gui/features/commands/analyze_commands.py
from __future__ import annotations

"""Analysis-related command handlers extracted from KaTrainGui (Phase 41-B).

These functions handle analysis mode changes and related operations.
The ctx parameter is expected to be a KaTrainGui instance (satisfies FeatureContext).
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui
    from katrain.core.analysis.modes import AnalysisMode


def do_analyze_extra(ctx: KaTrainGui, mode: str | AnalysisMode, **kwargs: Any) -> None:
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


# ---------------------------------------------------------------------------
# Phase 173: Additional game-state dispatchers.
#
# These methods live on ``__main__.KaTrainGui._game_state_manager`` but
# the GUI / Kv bindings and the message-queue dispatcher call them through
# the ``_do_*`` shim on KaTrainGui. Routing them through commands/ keeps
# the command surface uniform.
# ---------------------------------------------------------------------------


def do_insert_mode(ctx: KaTrainGui, mode: str = "toggle") -> None:
    """Toggle or set insert mode (delegated to GameStateManager)."""
    ctx._game_state_manager.do_insert_mode(mode)


def do_reset_analysis(ctx: KaTrainGui) -> None:
    """Reset the analysis cache for the current game."""
    ctx._game_state_manager.do_reset_analysis()


def do_resign(ctx: KaTrainGui) -> None:
    """Resign the current game (delegated to GameStateManager)."""
    ctx._game_state_manager.do_resign()


def do_redo(ctx: KaTrainGui, n_times: int = 1) -> None:
    """Redo N moves in the current game (delegated to GameStateManager)."""
    ctx._game_state_manager.do_redo(n_times)


def do_prev_important(ctx: KaTrainGui) -> None:
    """Navigate to the previous important (mistake / key) move."""
    ctx._game_state_manager.do_prev_important()


def do_next_important(ctx: KaTrainGui) -> None:
    """Navigate to the next important (mistake / key) move."""
    ctx._game_state_manager.do_next_important()
