# -*- coding: utf-8 -*-
"""Risk Context Analyzer.

This module provides risk analysis logic for evaluating whether a player's
moves align with appropriate strategy based on game situation.

Key functions:
- analyze_risk(): Main entry point for risk analysis
- to_player_perspective(): Convert Black-perspective values to side-to-move
- determine_judgment(): Classify game situation
- determine_behavior_from_stdev(): Classify behavior from stdev change
- determine_behavior_from_volatility(): Classify behavior from volatility
- check_strategy_mismatch(): Detect strategy alignment issues

Part of Phase 61: Risk Context Core.
"""

import math
from typing import Any, Iterator, List, Literal, Optional, Tuple

from katrain.core.analysis.logic import iter_main_branch_nodes

from .models import (
    PlayerRiskStats,
    RiskAnalysisConfig,
    RiskAnalysisResult,
    RiskBehavior,
    RiskContext,
    RiskJudgmentType,
)


# Type alias for GameNode (to avoid importing from katrain.core.game_node)
GameNode = Any


# =============================================================================
# Perspective Conversion
# =============================================================================


def to_player_perspective(
    winrate_black: float,
    score_lead_black: float,
    player: str,
) -> Tuple[float, float]:
    """Convert Black-perspective values to side-to-move perspective.

    KataGo/KaTrain returns values from Black's perspective.
    This function converts them to the perspective of the player to move.

    Args:
        winrate_black: Winrate from Black's perspective (0.0-1.0)
        score_lead_black: Score lead from Black's perspective (positive=Black ahead)
        player: "B" or "W"

    Returns:
        (winrate_player, score_lead_player): Values from side-to-move perspective
    """
    if player == "B":
        return winrate_black, score_lead_black
    else:  # player == "W"
        return 1.0 - winrate_black, -score_lead_black


# =============================================================================
# Node Data Extraction (Hardened Dict Access)
# =============================================================================


def _get_winrate_from_node(node: GameNode) -> Optional[float]:
    """Safely extract winrate from a node.

    Contract:
        - analysis_exists=False or analysis=None → None
        - analysis["root"] does not exist → None
        - analysis["root"]["winrate"] does not exist → None
        - Never raises KeyError/TypeError (returns None instead)
    """
    if not getattr(node, "analysis_exists", False):
        return None
    analysis = getattr(node, "analysis", None)
    if analysis is None:
        return None
    root_info = analysis.get("root")
    if root_info is None:
        return None
    return root_info.get("winrate")


def _get_score_lead_from_node(node: GameNode) -> Optional[float]:
    """Safely extract scoreLead from a node.

    Contract:
        Same as _get_winrate_from_node.
    """
    if not getattr(node, "analysis_exists", False):
        return None
    analysis = getattr(node, "analysis", None)
    if analysis is None:
        return None
    root_info = analysis.get("root")
    if root_info is None:
        return None
    return root_info.get("scoreLead")


def _get_score_stdev_from_node(node: GameNode) -> Optional[float]:
    """Safely extract scoreStdev from a node.

    Contract:
        Same as _get_winrate_from_node.
    """
    if not getattr(node, "analysis_exists", False):
        return None
    analysis = getattr(node, "analysis", None)
    if analysis is None:
        return None
    root_info = analysis.get("root")
    if root_info is None:
        return None
    return root_info.get("scoreStdev")


def _get_player_from_node(node: GameNode) -> Optional[Literal["B", "W"]]:
    """Extract and normalize player from a node.

    Contract:
        - node.move is None → None
        - node.move.player is "B" or "W" → return as-is
        - Other values → ValueError (unexpected state)

    Note:
        KaTrain defines Move.PLAYERS = "BW", so "B"/"W" are the only valid values.
        ValueError provides early detection of unexpected state.
    """
    move = getattr(node, "move", None)
    if move is None:
        return None
    player = getattr(move, "player", None)
    if player not in ("B", "W"):
        raise ValueError(f"Unexpected player value: {player!r}")
    return player


# =============================================================================
# Volatility Fallback
# =============================================================================


def _get_volatility_window_values(
    score_history: List[Optional[float]],
    current_index: int,
    window_size: int,
) -> List[float]:
    """Get scoreLead values for volatility calculation.

    Args:
        score_history: All moves' scoreLead history
            (index 0 = move 1's pre = Node(0)'s scoreLead)
        current_index: Current move index (0-based, move N → N-1)
        window_size: Window size for volatility

    Returns:
        List of valid scoreLead values (None excluded)

    Note:
        Uses only values up to current_index (inclusive).
        For move N, score_history[current_index] is move N's pre = Node(N-1).
        Thus only "before playing move N" information is used.
    """
    start = max(0, current_index - window_size + 1)
    end = current_index + 1  # inclusive
    window = score_history[start:end]
    return [v for v in window if v is not None]


def _compute_volatility(values: List[float]) -> Optional[float]:
    """Compute volatility (population standard deviation).

    Args:
        values: List of valid scoreLead values (None already excluded)

    Returns:
        Standard deviation, or None if sample count < 2

    Note:
        Uses population standard deviation (/n), not sample (/n-1).
        Thresholds (volatility_complicating_threshold=5.0 etc.) are set accordingly.
    """
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)  # /n (population)
    return math.sqrt(variance)


# =============================================================================
# Judgment and Behavior Classification
# =============================================================================


def determine_judgment(
    winrate_player: float,
    score_lead_player: float,
    config: RiskAnalysisConfig,
) -> RiskJudgmentType:
    """Determine game situation from side-to-move perspective.

    Args:
        winrate_player: Winrate from side-to-move perspective (0.0-1.0)
        score_lead_player: Score lead from side-to-move perspective (positive=ahead)
        config: Threshold configuration

    Returns:
        RiskJudgmentType (WINNING, LOSING, or CLOSE)

    Note:
        Thresholds are inclusive (>= and <=):
        - WR >= 0.85 AND Score >= 10.0 → WINNING
        - WR <= 0.15 AND Score <= -10.0 → LOSING
        - Otherwise → CLOSE
    """
    # WINNING requires both conditions
    if (
        winrate_player >= config.winning_winrate_threshold
        and score_lead_player >= config.winning_score_threshold
    ):
        return RiskJudgmentType.WINNING

    # LOSING requires both conditions
    if (
        winrate_player <= config.losing_winrate_threshold
        and score_lead_player <= config.losing_score_threshold
    ):
        return RiskJudgmentType.LOSING

    # Otherwise CLOSE
    return RiskJudgmentType.CLOSE


def determine_behavior_from_stdev(
    delta_stdev: float,
    config: RiskAnalysisConfig,
) -> RiskBehavior:
    """Classify behavior from delta_stdev.

    Args:
        delta_stdev: post_stdev - pre_stdev
        config: Threshold configuration

    Returns:
        RiskBehavior (COMPLICATING, SOLID, or NEUTRAL)

    Note:
        Thresholds are inclusive:
        - delta >= complicating_threshold → COMPLICATING
        - delta <= solid_threshold → SOLID
        - Otherwise → NEUTRAL
    """
    if delta_stdev >= config.complicating_stdev_delta:
        return RiskBehavior.COMPLICATING
    if delta_stdev <= config.solid_stdev_delta:
        return RiskBehavior.SOLID
    return RiskBehavior.NEUTRAL


def determine_behavior_from_volatility(
    volatility: Optional[float],
    config: RiskAnalysisConfig,
) -> RiskBehavior:
    """Classify behavior from volatility.

    Args:
        volatility: Past N moves scoreLead standard deviation, or None
        config: Threshold configuration

    Returns:
        RiskBehavior (COMPLICATING, SOLID, or NEUTRAL)

    Note:
        Thresholds are inclusive:
        - volatility >= complicating_threshold → COMPLICATING
        - volatility <= solid_threshold → SOLID
        - Otherwise or None → NEUTRAL
    """
    if volatility is None:
        return RiskBehavior.NEUTRAL
    if volatility >= config.volatility_complicating_threshold:
        return RiskBehavior.COMPLICATING
    if volatility <= config.volatility_solid_threshold:
        return RiskBehavior.SOLID
    return RiskBehavior.NEUTRAL


# =============================================================================
# Strategy Mismatch Detection
# =============================================================================


def check_strategy_mismatch(
    judgment: RiskJudgmentType,
    behavior: RiskBehavior,
) -> Tuple[bool, Optional[str]]:
    """Check if behavior contradicts optimal strategy for the situation.

    Mismatch rules:
        - WINNING + COMPLICATING → Mismatch ("unnecessary_risk_when_winning")
        - LOSING + SOLID → Mismatch ("passive_when_losing")
        - All other combinations → OK

    Args:
        judgment: Game situation judgment
        behavior: Move behavior classification

    Returns:
        (is_mismatch, reason): Tuple of mismatch flag and reason string
    """
    if judgment == RiskJudgmentType.WINNING and behavior == RiskBehavior.COMPLICATING:
        return True, "unnecessary_risk_when_winning"
    if judgment == RiskJudgmentType.LOSING and behavior == RiskBehavior.SOLID:
        return True, "passive_when_losing"
    return False, None


# =============================================================================
# Node Iterator
# =============================================================================


def _iter_move_nodes(game: Any) -> Iterator[GameNode]:
    """Iterate over main branch move nodes (excluding root).

    Yields:
        GameNode objects for each move on the main branch.

    Note:
        Root detection uses `node.parent is None` (not `move is None`).
        PASS is represented as Move(coords=None, player="B"/"W").
        This implementation is PASS-representation-independent.
    """
    for node in iter_main_branch_nodes(game):
        # Root detection: use parent=None (not move=None)
        if node.parent is not None:
            yield node


# =============================================================================
# Main Analysis Function
# =============================================================================


def analyze_risk(
    game: Any,
    config: Optional[RiskAnalysisConfig] = None,
) -> RiskAnalysisResult:
    """Analyze risk-taking behavior throughout a game.

    Args:
        game: KaTrain Game instance
        config: Analysis configuration (uses defaults if None)

    Returns:
        RiskAnalysisResult containing all contexts and statistics

    Note:
        - Uses enumerate for move_number (not node.depth)
        - score_history maintains 1:1 correspondence with moves (even on skip)
        - Skips only when pre_node lacks winrate/scoreLead
        - Uses volatility fallback when scoreStdev unavailable
    """
    if config is None:
        config = RiskAnalysisConfig()

    # score_history[i] = move (i+1)'s pre_node's scoreLead
    # current_index = move_number - 1
    score_history: List[Optional[float]] = []
    contexts: List[RiskContext] = []

    # Track statistics
    any_stdev_used = False
    any_fallback_used = False

    # Use enumerate for move_number (not node.depth)
    for move_number, node in enumerate(_iter_move_nodes(game), start=1):
        # node = state after playing move_number
        pre_node = node.parent  # state before playing move_number
        post_node = node  # state after playing move_number

        # Always append pre_node's scoreLead to history (Contract)
        pre_score = _get_score_lead_from_node(pre_node)
        score_history.append(pre_score)

        current_index = move_number - 1  # = len(score_history) - 1

        # Skip check: pre_node must have winrate and scoreLead
        pre_wr = _get_winrate_from_node(pre_node)
        if pre_wr is None or pre_score is None:
            continue  # SKIP (score_history already appended)

        # Get player
        player = _get_player_from_node(node)
        if player is None:
            continue  # Should not happen, but defensive

        # Convert to player perspective
        wr_player, score_player = to_player_perspective(pre_wr, pre_score, player)

        # Determine judgment
        judgment = determine_judgment(wr_player, score_player, config)

        # Calculate delta_stdev or use fallback
        pre_stdev = _get_score_stdev_from_node(pre_node)
        post_stdev = _get_score_stdev_from_node(post_node)

        if pre_stdev is not None and post_stdev is not None:
            # Use scoreStdev
            delta_stdev = post_stdev - pre_stdev
            behavior = determine_behavior_from_stdev(delta_stdev, config)
            has_stdev = True
            volatility = None
            any_stdev_used = True
        else:
            # Fallback: volatility from score_history
            values = _get_volatility_window_values(
                score_history, current_index, config.volatility_window
            )
            volatility = _compute_volatility(values)
            behavior = determine_behavior_from_volatility(volatility, config)
            has_stdev = False
            delta_stdev = None
            any_fallback_used = True

        # Check strategy mismatch
        is_mismatch, mismatch_reason = check_strategy_mismatch(judgment, behavior)

        # Create RiskContext
        ctx = RiskContext(
            move_number=move_number,
            player=player,
            judgment_type=judgment,
            winrate_before=wr_player,
            score_lead_before=score_player,
            risk_behavior=behavior,
            delta_stdev=delta_stdev,
            volatility_metric=volatility,
            is_strategy_mismatch=is_mismatch,
            mismatch_reason=mismatch_reason,
            has_stdev_data=has_stdev,
        )
        contexts.append(ctx)

    # Compute statistics
    contexts_tuple = tuple(contexts)
    black_contexts = [c for c in contexts if c.player == "B"]
    white_contexts = [c for c in contexts if c.player == "W"]

    def make_stats(ctxs: List[RiskContext]) -> PlayerRiskStats:
        return PlayerRiskStats(
            total_contexts=len(ctxs),
            winning_count=sum(1 for c in ctxs if c.judgment_type == RiskJudgmentType.WINNING),
            losing_count=sum(1 for c in ctxs if c.judgment_type == RiskJudgmentType.LOSING),
            close_count=sum(1 for c in ctxs if c.judgment_type == RiskJudgmentType.CLOSE),
            mismatch_count=sum(1 for c in ctxs if c.is_strategy_mismatch),
            contexts_with_stdev=sum(1 for c in ctxs if c.has_stdev_data),
            contexts_with_fallback=sum(1 for c in ctxs if not c.has_stdev_data),
        )

    return RiskAnalysisResult(
        contexts=contexts_tuple,
        has_stdev_data=any_stdev_used,
        fallback_used=any_fallback_used,
        strategy_mismatch_count=sum(1 for c in contexts if c.is_strategy_mismatch),
        winning_contexts=sum(1 for c in contexts if c.judgment_type == RiskJudgmentType.WINNING),
        losing_contexts=sum(1 for c in contexts if c.judgment_type == RiskJudgmentType.LOSING),
        black_stats=make_stats(black_contexts),
        white_stats=make_stats(white_contexts),
    )
