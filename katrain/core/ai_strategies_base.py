"""AI strategy base classes and utilities.

PR #130: Phase B5 - ai_strategies_base.py作成

ai.pyから抽出された基底クラスとユーティリティ関数。
- AIStrategy: 全AI戦略の基底クラス
- STRATEGY_REGISTRY: 戦略レジストリ
- register_strategy: 戦略登録デコレータ
- ユーティリティ関数（補間、重み生成など）
"""

from abc import ABC, abstractmethod
import math
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from katrain.core.constants import (
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    PRIORITY_EXTRA_AI_QUERY,
)
from katrain.core.game import Game, GameNode, Move


# =============================================================================
# Strategy Registry
# =============================================================================

STRATEGY_REGISTRY: Dict[str, type] = {}


def register_strategy(strategy_name: str) -> Callable[[Type["AIStrategy"]], Type["AIStrategy"]]:
    """Decorator to register a strategy class in the registry."""
    def decorator(strategy_class: Type["AIStrategy"]) -> Type["AIStrategy"]:
        STRATEGY_REGISTRY[strategy_name] = strategy_class
        return strategy_class
    return decorator


# =============================================================================
# Interpolation Utilities
# =============================================================================

def interp_ix(lst: List[float] | Tuple[float, ...], x: float) -> Tuple[int, float]:
    """Find interpolation index and fraction."""
    i = 0
    while i + 1 < len(lst) - 1 and lst[i + 1] < x:
        i += 1
    t = max(0.0, min(1.0, (x - lst[i]) / (lst[i + 1] - lst[i])))
    return i, t


def interp1d(lst: List[Tuple[float, float]], x: float) -> float:
    """1D linear interpolation."""
    xs, ys = zip(*lst)
    i, t = interp_ix(xs, x)
    result: float = (1 - t) * ys[i] + t * ys[i + 1]
    return result


def interp2d(gridspec: Tuple[List[float], List[float], List[List[float]]], x: float, y: float) -> float:
    """2D bilinear interpolation."""
    xs, ys, matrix = gridspec
    i, t = interp_ix(xs, x)
    j, s = interp_ix(ys, y)
    result: float = (
        matrix[j][i] * (1 - t) * (1 - s)
        + matrix[j][i + 1] * t * (1 - s)
        + matrix[j + 1][i] * (1 - t) * s
        + matrix[j + 1][i + 1] * t * s
    )
    return result


# =============================================================================
# Move Generation Utilities
# =============================================================================

def fmt_moves(moves: List[Tuple[float, Move]]) -> str:
    """Format move list for display."""
    return ", ".join(f"{mv.gtp()} ({p:.2%})" for p, mv in moves)


def policy_weighted_move(
    policy_moves: List[Tuple[float, Move]],
    lower_bound: float,
    weaken_fac: float,
) -> Tuple[Move, str]:
    """Select a move weighted by policy, with weakening factor."""
    from katrain.core.utils import weighted_selection_without_replacement

    lower_bound, weaken_fac = max(0, lower_bound), max(0.01, weaken_fac)
    weighted_coords = [
        (pv, pv ** (1 / weaken_fac), move)
        for pv, move in policy_moves
        if pv > lower_bound and not move.is_pass
    ]
    if weighted_coords:
        top = weighted_selection_without_replacement(weighted_coords, 1)[0]
        move = top[2]
        ai_thoughts = (
            f"Playing policy-weighted random move {move.gtp()} ({top[0]:.1%}) "
            f"from {len(weighted_coords)} moves above lower_bound of {lower_bound:.1%}."
        )
    else:
        move = policy_moves[0][1]
        ai_thoughts = (
            f"Playing top policy move because no non-pass move > "
            f"above lower_bound of {lower_bound:.1%}."
        )
    return move, ai_thoughts


def generate_influence_territory_weights(
    ai_mode: str,
    ai_settings: Dict[str, Any],
    policy_grid: List[List[float | None]],
    size: Tuple[int, int],
) -> Tuple[List[Tuple[float, float, int, int]], str]:
    """Generate position weights for influence/territory strategies."""
    from katrain.core.constants import AI_INFLUENCE

    thr_line = ai_settings["threshold"] - 1  # zero-based
    if ai_mode == AI_INFLUENCE:
        def weight(x: int, y: int) -> float:
            return float((1 / ai_settings["line_weight"]) ** (
                max(0, thr_line - min(size[0] - 1 - x, x))
                + max(0, thr_line - min(size[1] - 1 - y, y))
            ))
    else:
        def weight(x: int, y: int) -> float:
            return float((1 / ai_settings["line_weight"]) ** (
                max(0, min(size[0] - 1 - x, x, size[1] - 1 - y, y) - thr_line)
            ))

    weighted_coords: List[Tuple[float, float, int, int]] = []
    for x in range(size[0]):
        for y in range(size[1]):
            pval = policy_grid[y][x]
            if pval is not None and pval > 0:
                weighted_coords.append((pval * weight(x, y), weight(x, y), x, y))
    ai_thoughts = (
        f"Generated weights for {ai_mode} according to weight factor "
        f"{ai_settings['line_weight']} and distance from {thr_line + 1}th line. "
    )
    return weighted_coords, ai_thoughts


def generate_local_tenuki_weights(
    ai_mode: str,
    ai_settings: Dict[str, Any],
    policy_grid: List[List[float | None]],
    cn: GameNode,
    size: Tuple[int, int],
) -> Tuple[List[Tuple[float, float, int, int]], str]:
    """Generate position weights for local/tenuki strategies."""
    from katrain.core.constants import AI_TENUKI

    var = ai_settings["stddev"] ** 2
    assert cn.move is not None and cn.move.coords is not None
    mx, my = cn.move.coords
    weighted_coords: List[Tuple[float, float, int, int]] = []
    for x in range(size[0]):
        for y in range(size[1]):
            pval = policy_grid[y][x]
            if pval is not None and pval > 0:
                weighted_coords.append((pval, math.exp(-0.5 * ((x - mx) ** 2 + (y - my) ** 2) / var), x, y))
    ai_thoughts = (
        f"Generated weights based on one minus gaussian with variance {var} "
        f"around coordinates {mx},{my}. "
    )
    if ai_mode == AI_TENUKI:
        weighted_coords = [(p, 1 - w, x, y) for p, w, x, y in weighted_coords]
        ai_thoughts = (
            f"Generated weights based on one minus gaussian with variance {var} "
            f"around coordinates {mx},{my}. "
        )
    return weighted_coords, ai_thoughts


# =============================================================================
# AIStrategy Base Class
# =============================================================================

class AIStrategy(ABC):
    """Base strategy class for AI move generation.

    All AI strategies inherit from this class and implement generate_move().
    """

    def __init__(self, game: Game, ai_settings: Dict[str, Any]) -> None:
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
    def generate_move(self) -> Tuple[Move, str]:
        """Generate a move and explanation.

        Returns:
            Tuple of (Move, ai_thoughts string)
        """
        pass

    def request_analysis(self, extra_settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
        analysis: Optional[Dict[str, Any]] = None

        def set_analysis(a: Dict[str, Any], partial_result: bool) -> None:
            nonlocal analysis
            if not partial_result:
                analysis = a
                self.game.katrain.log(
                    f"[{self.strategy_name}] Analysis received", OUTPUT_DEBUG
                )

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
        self.game.katrain.log(
            f"[{self.strategy_name}] Waiting for analysis to complete...", OUTPUT_DEBUG
        )
        while not (error or analysis):
            time.sleep(0.01)
            engine.check_alive(exception_if_dead=True)

        if analysis:
            self.game.katrain.log(
                f"[{self.strategy_name}] Analysis completed successfully", OUTPUT_DEBUG
            )
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
        self.game.katrain.log(
            f"[{self.strategy_name}] Regular analysis completed", OUTPUT_DEBUG
        )

    def should_play_top_move(
        self,
        policy_moves: List[Tuple[float, Move | None]],
        top_5_pass: bool,
        override: float = 0.0,
        overridetwo: float = 1.0,
    ) -> Tuple[Optional[Move], str]:
        """Check if we should play the top policy move, regardless of strategy.

        Args:
            policy_moves: List of (probability, Move) tuples
            top_5_pass: Whether pass is in top 5 moves
            override: Single move override threshold
            overridetwo: Combined top-2 override threshold

        Returns:
            Tuple of (Move or None, explanation)
        """
        top_policy_move_opt = policy_moves[0][1]
        top_policy_move = top_policy_move_opt if top_policy_move_opt is not None else Move(None)
        self.game.katrain.log(
            f"[{self.strategy_name}] Checking if should play top move. "
            f"Top move: {top_policy_move.gtp()} ({policy_moves[0][0]:.2%})",
            OUTPUT_DEBUG,
        )
        self.game.katrain.log(
            f"[{self.strategy_name}] Override thresholds: single={override:.2%}, "
            f"combined={overridetwo:.2%}",
            OUTPUT_DEBUG,
        )
        self.game.katrain.log(
            f"[{self.strategy_name}] Top 5 pass: {top_5_pass}", OUTPUT_DEBUG
        )

        if top_5_pass:
            self.game.katrain.log(
                f"[{self.strategy_name}] Playing top move because pass is in top 5",
                OUTPUT_DEBUG,
            )
            return top_policy_move, "Playing top one because one of them is pass."

        if policy_moves[0][0] > override:
            self.game.katrain.log(
                f"[{self.strategy_name}] Playing top move because weight "
                f"{policy_moves[0][0]:.2%} > override {override:.2%}",
                OUTPUT_DEBUG,
            )
            return (
                top_policy_move,
                f"Top policy move has weight > {override:.1%}, so overriding other strategies.",
            )

        if policy_moves[0][0] + policy_moves[1][0] > overridetwo:
            combined = policy_moves[0][0] + policy_moves[1][0]
            self.game.katrain.log(
                f"[{self.strategy_name}] Playing top move because combined weight "
                f"{combined:.2%} > overridetwo {overridetwo:.2%}",
                OUTPUT_DEBUG,
            )
            return (
                top_policy_move,
                f"Top two policy moves have cumulative weight > {overridetwo:.1%}, "
                "so overriding other strategies.",
            )

        self.game.katrain.log(
            f"[{self.strategy_name}] No override condition met, continuing with strategy",
            OUTPUT_DEBUG,
        )
        return None, ""
