"""Calculation logic for Leela estimated loss.

This module computes estimated loss values for Leela candidates.
The estimated loss is a relative measure showing how much worse
each candidate is compared to the best candidate.
"""

from copy import deepcopy
from typing import Optional

from katrain.core.leela.models import LeelaCandidate, LeelaPositionEval

# Constants for K (loss scale factor)
LEELA_K_DEFAULT = 0.5
LEELA_K_MIN = 0.1
LEELA_K_MAX = 2.0
LEELA_K_RECOMMENDED_MIN = 0.2
LEELA_K_RECOMMENDED_MAX = 1.0

# Maximum estimated loss (clamp value)
LEELA_LOSS_EST_MAX = 50.0


def clamp_k(k: float) -> float:
    """Clamp K value to valid range.

    Args:
        k: Loss scale factor

    Returns:
        Clamped K value in range [LEELA_K_MIN, LEELA_K_MAX]
    """
    return max(LEELA_K_MIN, min(LEELA_K_MAX, k))


def compute_estimated_loss(
    position: LeelaPositionEval,
    k: float = LEELA_K_DEFAULT,
) -> LeelaPositionEval:
    """Compute estimated loss for all candidates.

    Creates a NEW LeelaPositionEval with loss_est values set.
    The original position object is NOT modified (immutable pattern).

    Formula:
    - best_eval = max(eval_pct) across all valid candidates
    - loss_pct = best_eval - candidate.eval_pct
    - loss_est = loss_pct * K, clamped to [0.0, LEELA_LOSS_EST_MAX]

    Args:
        position: LeelaPositionEval with candidates
        k: Loss scale factor (will be clamped to valid range)

    Returns:
        New LeelaPositionEval with loss_est calculated for each candidate
    """
    # Clamp K to valid range
    k = clamp_k(k)

    # Filter valid candidates (visits >= 1)
    valid_candidates = [c for c in position.candidates if c.visits >= 1]

    if not valid_candidates:
        # Return new object with error
        return LeelaPositionEval(
            candidates=[],
            root_visits=0,
            parse_error="No valid candidates for loss calculation",
        )

    # Find best eval_pct
    best_eval = max(c.eval_pct for c in valid_candidates)

    # Create new candidates with loss_est
    new_candidates = []
    for c in valid_candidates:
        loss_pct = best_eval - c.eval_pct
        loss_est = loss_pct * k

        # Apply rounding and clamping
        if loss_est < 0.05:
            loss_est = 0.0
        else:
            loss_est = round(loss_est, 1)

        # Clamp to maximum
        if loss_est > LEELA_LOSS_EST_MAX:
            loss_est = LEELA_LOSS_EST_MAX

        # Create new candidate (don't modify original)
        new_candidate = LeelaCandidate(
            move=c.move,
            winrate=c.winrate,
            visits=c.visits,
            pv=c.pv.copy() if c.pv else [],
            prior=c.prior,
            loss_est=loss_est,
        )
        new_candidates.append(new_candidate)

    return LeelaPositionEval(
        candidates=new_candidates,
        root_visits=position.root_visits,
        parse_error=None,
    )


def format_loss_est(loss: Optional[float]) -> str:
    """Format estimated loss for display.

    Args:
        loss: Estimated loss value, or None if not calculated

    Returns:
        Formatted string:
        - None -> "--"
        - 0.0 -> "0.0"
        - 2.345 -> "2.3"
    """
    if loss is None:
        return "--"
    return f"{loss:.1f}"


def compute_loss_color_ratio(loss_est: float, threshold_large: float = 5.0) -> float:
    """Compute a 0.0-1.0 ratio for coloring based on loss.

    Args:
        loss_est: Estimated loss value
        threshold_large: Loss value considered "large" (returns 1.0)

    Returns:
        Ratio from 0.0 (best) to 1.0 (worst) for color interpolation
    """
    if loss_est <= 0.0:
        return 0.0
    ratio = loss_est / threshold_large
    return min(1.0, ratio)


# =============================================================================
# Phase 16: Resign Hint Logic
# =============================================================================

from dataclasses import dataclass
from typing import List

# Constants for resign hint
RESIGN_WINRATE_THRESHOLD = 0.05       # 5%
RESIGN_CONSECUTIVE_MOVES = 3          # 3 consecutive moves
RESIGN_RELIABILITY_RATIO = 0.8        # 80% of max_visits for "reliable"


@dataclass
class ResignConditionResult:
    """Result of resign condition check."""

    should_show_hint: bool
    consecutive_count: int
    avg_winrate: float           # Internal: 0.0-1.0
    is_reliable: bool

    @property
    def winrate_pct(self) -> float:
        """Display-ready: average winrate as percentage (0-100)."""
        return self.avg_winrate * 100


def check_resign_condition(
    history: List[LeelaPositionEval],
    winrate_threshold: float = RESIGN_WINRATE_THRESHOLD,
    consecutive_moves: int = RESIGN_CONSECUTIVE_MOVES,
    max_visits: int = 1000,
    reliability_ratio: float = RESIGN_RELIABILITY_RATIO,
) -> ResignConditionResult:
    """Check if resign hint should be shown based on recent winrate history.

    v4 change: min_root_visits is dynamically calculated as max_visits * reliability_ratio
    - max_visits=1000 → threshold 800 (root_visits >= 800 is reliable)
    - max_visits=5000 → threshold 4000

    Args:
        history: List of LeelaPositionEval, newest first
        winrate_threshold: Winrate below which to consider resigning (0.0-1.0)
        consecutive_moves: Number of consecutive moves below threshold required
        max_visits: Max visits setting (for dynamic threshold calculation)
        reliability_ratio: Ratio of max_visits for reliability threshold

    Returns:
        ResignConditionResult with should_show_hint, consecutive_count, avg_winrate, is_reliable
    """
    # Calculate dynamic reliability threshold
    min_root_visits = int(max_visits * reliability_ratio)

    # 1. Length check
    if len(history) < consecutive_moves:
        return ResignConditionResult(
            should_show_hint=False,
            consecutive_count=0,
            avg_winrate=0.0,
            is_reliable=False,
        )

    # 2. Check winrate and visits for each position
    winrates = []
    all_reliable = True

    for eval_result in history[:consecutive_moves]:
        if not eval_result.is_valid or eval_result.best_winrate is None:
            return ResignConditionResult(
                should_show_hint=False,
                consecutive_count=0,
                avg_winrate=0.0,
                is_reliable=False,
            )
        winrates.append(eval_result.best_winrate)
        if eval_result.root_visits < min_root_visits:
            all_reliable = False

    # 3. Condition check
    avg_winrate = sum(winrates) / len(winrates)
    all_below = all(w <= winrate_threshold for w in winrates)

    return ResignConditionResult(
        should_show_hint=all_below,
        consecutive_count=consecutive_moves,
        avg_winrate=avg_winrate,
        is_reliable=all_reliable,
    )
