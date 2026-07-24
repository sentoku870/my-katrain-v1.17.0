"""AI strategy base classes and registry (Phase 280 slim-down).

After Phase 280 the AI strategy family is reduced to two survivors:
``ai:default`` (DefaultStrategy) and ``ai:handicap`` (HandicapStrategy).
This module retains only what those strategies actually need:
- ``AIStrategy``: ABC base class with the engine-helper contract
  (``wait_for_analysis`` / ``request_analysis``).
- ``STRATEGY_REGISTRY``: strategy_id -> strategy_class.
- ``register_strategy``: decorator used by strategy subclasses.

Removed during Phase 280 (no surviving caller):
- ``interp1d`` / ``interp2d`` / ``interp_ix`` interpolation helpers.
- ``fmt_moves`` / ``should_play_top_move``.
- ``generate_influence_territory_weights`` / ``generate_local_tenuki_weights``.
"""

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from katrain.core.constants.output import OUTPUT_DEBUG, OUTPUT_ERROR
from katrain.core.constants.priorities import PRIORITY_EXTRA_AI_QUERY
from katrain.core.game import Game, Move

# =============================================================================
# Strategy Registry
# =============================================================================

STRATEGY_REGISTRY: dict[str, type] = {}


def register_strategy(strategy_name: str) -> Callable[[type["AIStrategy"]], type["AIStrategy"]]:
    """Decorator to register a strategy class in the registry."""

    def decorator(strategy_class: type["AIStrategy"]) -> type["AIStrategy"]:
        STRATEGY_REGISTRY[strategy_name] = strategy_class
        return strategy_class

    return decorator


# =============================================================================
# AIStrategy Base Class
# =============================================================================


class AIStrategy(ABC):
    """Base strategy class for AI move generation.

    All AI strategies inherit from this class and implement generate_move().
    """

    def __init__(self, game: Game, ai_settings: dict[str, Any]) -> None:
        """Initialize the strategy.

        Args:
            game: The current game instance
            ai_settings: Strategy-specific settings dictionary
        """
        self.game = game
        self.settings = ai_settings
        self.cn = game.current_node
        self.strategy_name = self.__class__.__name__
        self.game.katrain.log(
            f"Initializing {self.strategy_name} with settings: {self.settings}",
            OUTPUT_DEBUG,
        )

    @abstractmethod
    def generate_move(self) -> tuple[Move, str]:
        """Generate a move and explanation.

        Returns:
            Tuple of (Move, ai_thoughts string)
        """
        pass

    def request_analysis(self, extra_settings: dict[str, Any]) -> dict[str, Any] | None:
        """Helper to request additional analysis with custom settings.

        Args:
            extra_settings: Additional KataGo analysis settings

        Returns:
            Analysis result dictionary, or None on error
        """
        self.game.katrain.log(
            f"[{self.strategy_name}] Requesting analysis with settings: {extra_settings}",
            OUTPUT_DEBUG,
        )
        error = False
        analysis: dict[str, Any] | None = None

        def set_analysis(a: dict[str, Any], partial_result: bool) -> None:
            nonlocal analysis
            if not partial_result:
                analysis = a
                self.game.katrain.log(f"[{self.strategy_name}] Analysis received", OUTPUT_DEBUG)

        def set_error(a: Any) -> None:
            nonlocal error
            self.game.katrain.log(
                f"[{self.strategy_name}] Error in additional analysis query: {a}",
                OUTPUT_ERROR,
            )
            error = True

        engine = self.game.engines[self.cn.player]
        engine.request_analysis(
            self.cn,
            callback=set_analysis,
            error_callback=set_error,
            priority=PRIORITY_EXTRA_AI_QUERY,
            ownership=False,
            extra_settings=extra_settings,
        )
        self.game.katrain.log(f"[{self.strategy_name}] Waiting for analysis to complete...", OUTPUT_DEBUG)
        # Phase 165: Add timeout to prevent infinite loop if the engine
        # silently dies or the writer thread is stuck (e.g. deadlocked
        # by terminate_queries() before the Phase 159 RLock fix).
        _wait_timeout_s = 120.0
        _wait_start = time.time()
        try:
            while not (error or analysis):
                if time.time() - _wait_start > _wait_timeout_s:
                    raise TimeoutError(
                        f"[{self.strategy_name}] Timed out after {_wait_timeout_s}s waiting for analysis"
                    )
                time.sleep(0.01)
                try:
                    engine.check_alive(exception_if_dead=True)
                except Exception:
                    self.game.katrain.log(
                        f"[{self.strategy_name}] Engine died while waiting for analysis",
                        OUTPUT_ERROR,
                    )
                    return None
        except TimeoutError:
            self.game.katrain.log(
                f"[{self.strategy_name}] Analysis wait timed out after {_wait_timeout_s}s",
                OUTPUT_ERROR,
            )
            raise

        if analysis:
            self.game.katrain.log(f"[{self.strategy_name}] Analysis completed successfully", OUTPUT_DEBUG)
        return analysis

    def wait_for_analysis(self) -> None:
        """Wait for the analysis to complete."""
        self.game.katrain.log(
            f"[{self.strategy_name}] Waiting for regular analysis to complete...",
            OUTPUT_DEBUG,
        )
        while not self.cn.analysis_complete:
            time.sleep(0.01)
            self.game.engines[self.cn.next_player].check_alive(exception_if_dead=True)
        self.game.katrain.log(f"[{self.strategy_name}] Regular analysis completed", OUTPUT_DEBUG)


__all__ = [
    "STRATEGY_REGISTRY",
    "register_strategy",
    "AIStrategy",
]
