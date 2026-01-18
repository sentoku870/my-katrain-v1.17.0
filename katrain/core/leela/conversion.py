"""Conversion module: Leela → MoveEval/EvalSnapshot.

This module converts Leela Zero analysis results (LeelaPositionEval)
to the standard MoveEval/EvalSnapshot pipeline used by Karte/Summary.

Phase 31: Leela→MoveEval変換

Design principles:
- Single-engine reports (no KataGo/Leela mixing)
- Reuse existing pipeline types (EvalSnapshot/MoveEval)
- Clear loss semantics: score_loss (points) vs leela_loss_est (estimated from winrate gap)
"""

import logging
from typing import List, Optional, Tuple

from katrain.core.analysis.models import (
    EvalSnapshot,
    MistakeCategory,
    MoveEval,
)
from katrain.core.analysis.logic_loss import classify_mistake
from katrain.core.leela.models import LeelaPositionEval
from katrain.core.leela.logic import (
    LEELA_K_DEFAULT,
    LEELA_LOSS_EST_MAX,
)

logger = logging.getLogger(__name__)

# Epsilon threshold for rounding (matches logic.py:81)
LEELA_LOSS_EST_EPSILON = 0.05


def _normalize_move(move: str) -> Optional[str]:
    """Normalize a GTP coordinate string.

    Args:
        move: Input coordinate string

    Returns:
        Normalized coordinate, or None for invalid input

    Rules:
    - Strip whitespace
    - Convert to uppercase: "d4" → "D4"
    - Unify pass variants: "Pass", "PASS", "pass" → "PASS"
    - Empty string "" → None (don't hide potential bugs)
    """
    move = move.strip().upper()
    if move == "":
        return None  # Empty string is likely a bug
    if move == "PASS":
        return "PASS"
    return move


def _round_loss_est(loss_est: float) -> float:
    """Round and clamp leela_loss_est.

    Follows the same rules as logic.py:81-88 (order preserved):
    1. epsilon check: < 0.05 → 0.0 (noise removal)
    2. round: to 1 decimal place
    3. clamp: > 50.0 → 50.0 (maximum clamp)

    Args:
        loss_est: Raw loss estimate value

    Returns:
        Rounded and clamped loss estimate
    """
    # Step 1: epsilon threshold
    if loss_est < LEELA_LOSS_EST_EPSILON:
        return 0.0
    # Step 2: round to 1 decimal
    loss_est = round(loss_est, 1)
    # Step 3: clamp to max
    if loss_est > LEELA_LOSS_EST_MAX:
        return LEELA_LOSS_EST_MAX
    return loss_est


def _convert_to_black_perspective(
    parent_best_wr: Optional[float],
    current_best_wr: Optional[float],
    player: str,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Convert Leela winrate (side-to-move) to black perspective.

    Leela's winrate is from the perspective of the player to move (side-to-move).
    MoveEval uses black perspective for consistency.

    Args:
        parent_best_wr: Best winrate at parent position (0.0-1.0, side-to-move)
        current_best_wr: Best winrate at current position (0.0-1.0, side-to-move)
        player: Player who made this move ("B" or "W")

    Returns:
        Tuple of (winrate_before, winrate_after, delta_winrate), all black perspective.
        Returns (None, None, None) if either input is None.
    """
    if parent_best_wr is None or current_best_wr is None:
        return None, None, None

    if player == "B":
        # Black played: parent is black-to-move, current is white-to-move
        winrate_before = parent_best_wr           # Black's winrate (parent: B to move)
        winrate_after = 1.0 - current_best_wr     # Black's winrate (current: W to move)
    else:  # player == "W"
        # White played: parent is white-to-move, current is black-to-move
        winrate_before = 1.0 - parent_best_wr     # Black's winrate (parent: W to move)
        winrate_after = current_best_wr           # Black's winrate (current: B to move)

    delta_winrate = winrate_after - winrate_before  # Black perspective change
    return winrate_before, winrate_after, delta_winrate


def _compute_winrate_loss(delta_winrate: Optional[float], player: str) -> Optional[float]:
    """Compute winrate loss from the perspective of the player who moved.

    Args:
        delta_winrate: Black-perspective winrate change (positive=black improved)
        player: Player who made this move ("B" or "W")

    Returns:
        winrate_loss: Loss from the mover's perspective (always >= 0, None if not calculable)

    Logic:
        - Black's move: black worsening (delta < 0) → loss = -delta
        - White's move: white worsening (black improvement, delta > 0) → loss = delta
    """
    if delta_winrate is None:
        return None

    if player == "B":
        # Black: negative delta (black worsening) is loss
        return max(0.0, -delta_winrate)
    else:
        # White: positive delta (black improvement = white worsening) is loss
        return max(0.0, delta_winrate)


def _compute_leela_loss_for_played_move(
    parent_eval: Optional[LeelaPositionEval],
    played_move: str,
    k: float,
) -> Optional[float]:
    """Compute estimated loss for the played move.

    Algorithm:
    1. If parent is None (first move) → return None
    2. Normalize played_move
    3. Find played_move in parent's candidates
       - Found: loss_est = (best_wr - played_wr) * K * 100
       - Not found: return None
    4. Round and clamp the result

    Args:
        parent_eval: Parent position evaluation (None for first move)
        played_move: GTP coordinate of the played move (e.g., "D4", "pass")
        k: Loss scale factor

    Returns:
        Estimated loss, or None if not calculable
    """
    if parent_eval is None:
        return None

    if not parent_eval.is_valid:
        return None

    # Normalize the played move
    normalized_move = _normalize_move(played_move)
    if normalized_move is None:
        return None  # Empty string or invalid

    # Find the played move in parent's candidates
    played_candidate = None
    for candidate in parent_eval.candidates:
        if candidate.move.upper() == normalized_move:
            played_candidate = candidate
            break

    if played_candidate is None:
        # Move not in candidates (low visits, pass, or analysis interrupted)
        return None

    # Get best candidate's winrate
    best = parent_eval.best_candidate
    if best is None:
        return None

    # Calculate loss estimate
    # Both winrates are from side-to-move perspective, so no conversion needed
    loss_pct = (best.eval_pct - played_candidate.eval_pct)  # Difference in percentage (0-100 scale)
    loss_est = loss_pct * k

    # Round and clamp
    return _round_loss_est(loss_est)


def leela_position_to_move_eval(
    parent_eval: Optional[LeelaPositionEval],
    current_eval: LeelaPositionEval,
    move_number: int,
    player: str,
    played_move: str,
    k: float = LEELA_K_DEFAULT,
) -> MoveEval:
    """Convert Leela parent/current evaluations to a MoveEval.

    Args:
        parent_eval: Parent position evaluation (None for first move)
        current_eval: Current position evaluation
        move_number: Move number (1-indexed)
        player: Player who made this move ("B" or "W")
        played_move: GTP coordinate of the played move (e.g., "D4", "pass")
        k: Loss scale factor (default: LEELA_K_DEFAULT = 0.5)

    Returns:
        MoveEval with Leela-specific fields populated:
        - score_* fields: None (Leela doesn't provide scoreLead)
        - winrate_* fields: Converted to black perspective
        - points_lost: None (KataGo-specific)
        - leela_loss_est: Estimated loss from candidate winrate gap
        - mistake_category: Classified by winrate_loss (score_loss=None fallback)
    """
    # Get best winrates
    parent_best_wr = parent_eval.best_winrate if parent_eval else None
    current_best_wr = current_eval.best_winrate

    # Convert to black perspective
    winrate_before, winrate_after, delta_winrate = _convert_to_black_perspective(
        parent_best_wr, current_best_wr, player
    )

    # Compute winrate loss (for mistake classification)
    winrate_loss = _compute_winrate_loss(delta_winrate, player)

    # Compute leela_loss_est from parent candidates
    leela_loss_est = _compute_leela_loss_for_played_move(parent_eval, played_move, k)

    # Classify mistake using winrate_loss (score_loss is None for Leela)
    mistake_category = classify_mistake(
        score_loss=None,
        winrate_loss=winrate_loss,
    )

    return MoveEval(
        move_number=move_number,
        player=player,
        gtp=played_move,
        # Score fields: None (Leela doesn't provide scoreLead)
        score_before=None,
        score_after=None,
        delta_score=None,
        # Winrate fields: converted to black perspective
        winrate_before=winrate_before,
        winrate_after=winrate_after,
        delta_winrate=delta_winrate,
        # KataGo-specific fields: None
        points_lost=None,
        realized_points_lost=None,
        # Root visits from current evaluation
        root_visits=current_eval.root_visits,
        # Loss fields
        score_loss=None,
        winrate_loss=winrate_loss,
        # Mistake classification (by winrate_loss since score_loss=None)
        mistake_category=mistake_category,
        # Leela-specific field
        leela_loss_est=leela_loss_est,
    )


def leela_sequence_to_eval_snapshot(
    evals: List[LeelaPositionEval],
    moves_info: List[Tuple[int, str, str]],
    k: float = LEELA_K_DEFAULT,
) -> EvalSnapshot:
    """Convert a sequence of Leela evaluations to an EvalSnapshot.

    Caller Contract:
    - Input must be a single linear sequence (main line only)
    - Branching SGF must be split by caller before calling this function
    - move_numbers must be monotonically increasing

    Args:
        evals: List of LeelaPositionEval, one per move
        moves_info: List of (move_number, player, gtp) tuples
        k: Loss scale factor (default: LEELA_K_DEFAULT = 0.5)

    Returns:
        EvalSnapshot containing MoveEval for each move

    Raises:
        ValueError: Length mismatch, non-monotonic move_number, or move_number < 1
    """
    # Validation: length match
    if len(evals) != len(moves_info):
        raise ValueError(
            f"Length mismatch: evals={len(evals)}, moves_info={len(moves_info)}"
        )

    # Validation: move_number monotonic and >= 1
    for i, (move_num, player, gtp) in enumerate(moves_info):
        if move_num < 1:
            raise ValueError(f"Invalid move_number={move_num} at index {i}")
        if i > 0 and move_num <= moves_info[i - 1][0]:
            raise ValueError(
                f"Non-monotonic move_number: {moves_info[i - 1][0]} -> {move_num}"
            )

    # Warning: player alternation (not an error, just log)
    for i in range(1, len(moves_info)):
        prev_player = moves_info[i - 1][1]
        curr_player = moves_info[i][1]
        if prev_player == curr_player:
            logger.warning(
                f"Non-alternating players at move {moves_info[i][0]}: "
                f"{prev_player} -> {curr_player}"
            )

    # Convert each evaluation
    move_evals: List[MoveEval] = []
    for i, (move_num, player, gtp) in enumerate(moves_info):
        parent_eval = evals[i - 1] if i > 0 else None
        current_eval = evals[i]

        move_eval = leela_position_to_move_eval(
            parent_eval=parent_eval,
            current_eval=current_eval,
            move_number=move_num,
            player=player,
            played_move=gtp,
            k=k,
        )
        move_evals.append(move_eval)

    return EvalSnapshot(moves=move_evals)
