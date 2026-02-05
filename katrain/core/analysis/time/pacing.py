"""Pacing & Tilt Analysis.

This module analyzes the correlation between time consumption and loss
to detect impulsive moves (blitz mistakes) and tilt episodes.

Part of Phase 59: Pacing & Tilt Core.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from katrain.core.analysis.models import MoveEval, get_canonical_loss_from_move

from .models import GameTimeData

_logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Pacing thresholds (multipliers relative to median)
BLITZ_MULTIPLIER = 0.3
LONG_THINK_MULTIPLIER = 3.0

# Tilt detection
TILT_WINDOW_MOVES = 5
EPISODE_CONTINUATION_RATIO = 0.5
MIN_POSITIVE_LOSSES_FOR_P90 = 2

# Severity thresholds (score points)
SEVERE_MOVE_COUNT = 4
SEVERE_LOSS_THRESHOLD = 15.0  # > 15.0 for SEVERE
MODERATE_MOVE_COUNT = 3
MODERATE_LOSS_THRESHOLD = 5.0  # >= 5.0 for MODERATE

# Analysis requirements
MIN_MOVES_FOR_STATS = 10


# =============================================================================
# Enums
# =============================================================================


class LossSource(StrEnum):
    """Source of canonical loss values."""

    SCORE = "score"  # KataGo score_loss
    LEELA = "leela"  # Leela leela_loss_est
    POINTS = "points"  # Legacy points_lost
    NONE = "none"  # No loss data


class TiltSeverity(StrEnum):
    """Severity classification for tilt episodes.

    Precedence order (checked first to last):
    1. SEVERE: move_count >= 4 AND cumulative_loss > 15.0
    2. MODERATE: move_count >= 3 OR cumulative_loss >= 5.0
    3. MILD: otherwise (move_count == 2, cumulative_loss < 5.0)
    """

    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass(frozen=True)
class PacingConfig:
    """Configuration for pacing analysis."""

    blitz_multiplier: float = BLITZ_MULTIPLIER
    long_think_multiplier: float = LONG_THINK_MULTIPLIER
    tilt_window_moves: int = TILT_WINDOW_MOVES
    episode_continuation_ratio: float = EPISODE_CONTINUATION_RATIO
    min_moves_for_stats: int = MIN_MOVES_FOR_STATS
    min_positive_losses_for_p90: int = MIN_POSITIVE_LOSSES_FOR_P90


@dataclass(frozen=True)
class GamePacingStats:
    """Computed game-level statistics for pacing analysis.

    Contains thresholds used for classification and diagnostic counters.
    """

    # Per-player time thresholds
    time_median_black: float | None
    time_median_white: float | None
    blitz_threshold_black: float | None
    blitz_threshold_white: float | None
    long_think_threshold_black: float | None
    long_think_threshold_white: float | None

    # Loss thresholds
    loss_p90: float
    episode_continuation_threshold: float

    # Coverage diagnostics
    total_moves_analyzed: int
    expected_move_count: int
    missing_move_eval_count: int
    has_coverage_gaps: bool
    moves_with_time_data: int
    moves_with_loss_data: int

    # Engine source tracking
    loss_source: LossSource
    has_mixed_sources: bool

    # Feature flags
    tilt_detection_enabled: bool


@dataclass(frozen=True)
class PacingMetrics:
    """Per-move pacing classification.

    Attributes:
        move_number: 1-indexed move number
        player: 'B' or 'W'
        time_spent_sec: Time consumed (None if no time data)
        canonical_loss: Loss from get_canonical_loss_from_move() (>= 0.0)
        is_blitz: time < player_median * 0.3
        is_long_think: time > player_median * 3.0
        is_impulsive: is_blitz AND loss > p90
        is_overthinking: is_long_think AND loss > p90
    """

    move_number: int
    player: str
    time_spent_sec: float | None
    canonical_loss: float
    is_blitz: bool
    is_long_think: bool
    is_impulsive: bool
    is_overthinking: bool


@dataclass(frozen=True)
class TiltEpisode:
    """A detected tilt episode (cascade of mistakes after a trigger).

    Guarantees:
        - move_numbers is tuple[int, ...] in ascending order, unique values
        - move_count == len(move_numbers) >= 2
        - trigger_move == start_move == move_numbers[0]
        - end_move == move_numbers[-1]
    """

    player: str
    trigger_move: int
    start_move: int
    end_move: int
    move_count: int
    cumulative_loss: float
    severity: TiltSeverity
    move_numbers: tuple[int, ...]


@dataclass(frozen=True)
class PacingAnalysisResult:
    """Complete result of pacing/tilt analysis.

    Guarantees:
        - pacing_metrics in ascending move_number order
        - game_stats always populated (never None)
        - tilt_episodes empty if tilt_detection_enabled == False
    """

    pacing_metrics: tuple[PacingMetrics, ...]
    tilt_episodes: tuple[TiltEpisode, ...]
    has_time_data: bool
    game_stats: GamePacingStats


# =============================================================================
# Helper Functions
# =============================================================================


def _compute_median(values: list[float]) -> float:
    """Compute median of a list of values.

    Returns 0.0 if list is empty.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
    return sorted_vals[mid]


def _compute_percentile_90(values: list[float]) -> float:
    """Compute 90th percentile using nearest-rank method.

    Algorithm:
        rank = ceil(0.9 * n)
        return sorted_values[rank - 1]

    Returns 0.0 if list is empty.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    rank = math.ceil(0.9 * n)
    return sorted_vals[rank - 1]


def _detect_coverage_gaps(
    time_data: GameTimeData,
    moves: list[MoveEval],
) -> tuple[set[int], int]:
    """Detect missing MoveEval entries.

    Returns:
        (missing_move_numbers, expected_max_move)

    Algorithm:
        1. Determine expected_max_move from TimeMetrics (if available)
           or from max MoveEval move_number
        2. Compute expected range: 1..expected_max_move
        3. Find missing: expected - actual
    """
    move_eval_numbers = {m.move_number for m in moves if m.player is not None}

    # Determine expected max from TimeMetrics (authoritative for mainline length)
    if time_data.metrics:
        expected_max_move = max(m.move_number for m in time_data.metrics)
    elif move_eval_numbers:
        expected_max_move = max(move_eval_numbers)
    else:
        return set(), 0

    expected = set(range(1, expected_max_move + 1))
    missing = expected - move_eval_numbers

    return missing, expected_max_move


def _detect_loss_sources(moves: list[MoveEval]) -> tuple[LossSource, bool]:
    """Detect which loss sources are used in the moves.

    Returns:
        (primary_source, has_mixed_sources)
    """
    sources_used: set[LossSource] = set()

    for m in moves:
        if m.player is None:
            continue
        if m.score_loss is not None:
            sources_used.add(LossSource.SCORE)
        elif m.leela_loss_est is not None:
            sources_used.add(LossSource.LEELA)
        elif m.points_lost is not None:
            sources_used.add(LossSource.POINTS)

    if not sources_used:
        return LossSource.NONE, False

    if len(sources_used) == 1:
        return sources_used.pop(), False

    # Mixed sources - SCORE takes priority
    if LossSource.SCORE in sources_used:
        return LossSource.SCORE, True
    if LossSource.LEELA in sources_used:
        return LossSource.LEELA, True
    return LossSource.POINTS, True


def _compute_severity(move_count: int, cumulative_loss: float) -> TiltSeverity:
    """Compute tilt severity with strict precedence.

    Order: SEVERE > MODERATE > MILD.
    """
    # 1. SEVERE: both conditions (AND)
    if move_count >= SEVERE_MOVE_COUNT and cumulative_loss > SEVERE_LOSS_THRESHOLD:
        return TiltSeverity.SEVERE

    # 2. MODERATE: either condition (OR)
    if move_count >= MODERATE_MOVE_COUNT or cumulative_loss >= MODERATE_LOSS_THRESHOLD:
        return TiltSeverity.MODERATE

    # 3. MILD: default
    return TiltSeverity.MILD


# =============================================================================
# Stats Computation
# =============================================================================


def _compute_game_stats(
    time_data: GameTimeData,
    moves: list[MoveEval],
    config: PacingConfig,
    missing_moves: set[int],
    expected_max_move: int,
) -> GamePacingStats:
    """Compute game-level statistics for pacing analysis."""
    # Filter valid moves (player is not None)
    valid_moves = [m for m in moves if m.player is not None]

    # Build time map from TimeMetrics
    time_map: dict[int, float | None] = {}
    for tm in time_data.metrics:
        time_map[tm.move_number] = tm.time_spent_sec

    # Collect per-player times
    black_times: list[float] = []
    white_times: list[float] = []
    moves_with_time = 0

    for m in valid_moves:
        time_spent = time_map.get(m.move_number)
        if time_spent is not None:
            moves_with_time += 1
            if m.player == "B":
                black_times.append(time_spent)
            elif m.player == "W":
                white_times.append(time_spent)

    # Compute medians
    time_median_black = _compute_median(black_times) if black_times else None
    time_median_white = _compute_median(white_times) if white_times else None

    # Compute thresholds
    blitz_threshold_black = time_median_black * config.blitz_multiplier if time_median_black is not None else None
    blitz_threshold_white = time_median_white * config.blitz_multiplier if time_median_white is not None else None
    long_think_threshold_black = (
        time_median_black * config.long_think_multiplier if time_median_black is not None else None
    )
    long_think_threshold_white = (
        time_median_white * config.long_think_multiplier if time_median_white is not None else None
    )

    # Collect positive losses for p90
    positive_losses: list[float] = []
    for m in valid_moves:
        loss = get_canonical_loss_from_move(m)
        if loss > 0.0:
            positive_losses.append(loss)

    # Compute p90
    if len(positive_losses) >= config.min_positive_losses_for_p90:
        loss_p90 = _compute_percentile_90(positive_losses)
    else:
        loss_p90 = 0.0

    continuation_threshold = loss_p90 * config.episode_continuation_ratio

    # Detect loss sources
    loss_source, has_mixed_sources = _detect_loss_sources(valid_moves)

    if has_mixed_sources:
        _logger.warning("Mixed loss sources detected (KataGo + Leela); severity thresholds may be less accurate.")

    return GamePacingStats(
        time_median_black=time_median_black,
        time_median_white=time_median_white,
        blitz_threshold_black=blitz_threshold_black,
        blitz_threshold_white=blitz_threshold_white,
        long_think_threshold_black=long_think_threshold_black,
        long_think_threshold_white=long_think_threshold_white,
        loss_p90=loss_p90,
        episode_continuation_threshold=continuation_threshold,
        total_moves_analyzed=len(valid_moves),
        expected_move_count=expected_max_move,
        missing_move_eval_count=len(missing_moves),
        has_coverage_gaps=len(missing_moves) > 0,
        moves_with_time_data=moves_with_time,
        moves_with_loss_data=len(positive_losses),
        loss_source=loss_source,
        has_mixed_sources=has_mixed_sources,
        tilt_detection_enabled=loss_p90 > 0.0,
    )


# =============================================================================
# Classification
# =============================================================================


def _classify_pacing(
    moves: list[MoveEval],
    time_data: GameTimeData,
    game_stats: GamePacingStats,
) -> list[PacingMetrics]:
    """Classify each move's pacing based on game statistics."""
    # Build time map
    time_map: dict[int, float | None] = {}
    for tm in time_data.metrics:
        time_map[tm.move_number] = tm.time_spent_sec

    result: list[PacingMetrics] = []

    for m in moves:
        if m.player is None:
            continue

        time_spent = time_map.get(m.move_number)
        canonical_loss = get_canonical_loss_from_move(m)

        # Determine thresholds based on player
        if m.player == "B":
            blitz_threshold = game_stats.blitz_threshold_black
            long_think_threshold = game_stats.long_think_threshold_black
        else:
            blitz_threshold = game_stats.blitz_threshold_white
            long_think_threshold = game_stats.long_think_threshold_white

        # Compute flags
        is_blitz = False
        is_long_think = False

        if time_spent is not None:
            if blitz_threshold is not None and time_spent < blitz_threshold:
                is_blitz = True
            if long_think_threshold is not None and time_spent > long_think_threshold:
                is_long_think = True

        # Impulsive/overthinking require tilt detection enabled
        is_impulsive = False
        is_overthinking = False

        if game_stats.tilt_detection_enabled:
            if is_blitz and canonical_loss > game_stats.loss_p90:
                is_impulsive = True
            if is_long_think and canonical_loss > game_stats.loss_p90:
                is_overthinking = True

        result.append(
            PacingMetrics(
                move_number=m.move_number,
                player=m.player,
                time_spent_sec=time_spent,
                canonical_loss=canonical_loss,
                is_blitz=is_blitz,
                is_long_think=is_long_think,
                is_impulsive=is_impulsive,
                is_overthinking=is_overthinking,
            )
        )

    # Sort by move_number (ascending)
    result.sort(key=lambda x: x.move_number)
    return result


# =============================================================================
# Tilt Detection
# =============================================================================


def _detect_tilt_episodes(
    pacing_metrics: list[PacingMetrics],
    game_stats: GamePacingStats,
    config: PacingConfig,
) -> list[TiltEpisode]:
    """Detect tilt episodes from pacing-classified moves.

    Algorithm:
        1. For each player, find triggers (loss > p90)
        2. For each trigger, scan window for continuations (loss >= threshold)
        3. If 2+ moves, create episode
        4. Claimed moves cannot be reused
    """
    if not game_stats.tilt_detection_enabled:
        return []

    episodes: list[TiltEpisode] = []

    for player in ["B", "W"]:
        # Filter player's moves (already sorted by move_number)
        player_moves = [m for m in pacing_metrics if m.player == player]

        if not player_moves:
            continue

        claimed: set[int] = set()

        for trigger in player_moves:
            if trigger.move_number in claimed:
                continue

            # Check if this is a trigger (loss > p90, strict)
            if trigger.canonical_loss <= game_stats.loss_p90:
                continue

            # Start episode with trigger
            episode_moves = [trigger]
            window_end = trigger.move_number + config.tilt_window_moves

            # Scan for continuations within window
            for cont in player_moves:
                if cont.move_number <= trigger.move_number:
                    continue
                if cont.move_number > window_end:
                    break  # Past window (relies on sorted order)
                if cont.move_number in claimed:
                    continue
                # Continuation threshold (>= not >)
                if cont.canonical_loss >= game_stats.episode_continuation_threshold:
                    episode_moves.append(cont)

            # Need at least 2 moves for an episode
            if len(episode_moves) >= 2:
                move_numbers = tuple(m.move_number for m in episode_moves)
                cumulative_loss = sum(m.canonical_loss for m in episode_moves)
                severity = _compute_severity(len(episode_moves), cumulative_loss)

                episodes.append(
                    TiltEpisode(
                        player=player,
                        trigger_move=episode_moves[0].move_number,
                        start_move=episode_moves[0].move_number,
                        end_move=episode_moves[-1].move_number,
                        move_count=len(episode_moves),
                        cumulative_loss=cumulative_loss,
                        severity=severity,
                        move_numbers=move_numbers,
                    )
                )

                # Mark as claimed
                claimed.update(move_numbers)

    return episodes


# =============================================================================
# Main Entry Point
# =============================================================================


def analyze_pacing(
    time_data: GameTimeData,
    moves: list[MoveEval],
    config: PacingConfig | None = None,
) -> PacingAnalysisResult:
    """Analyze game for pacing patterns and tilt episodes.

    Args:
        time_data: From parse_time_data(game.root)
        moves: List of MoveEval, typically from snapshot_from_game(game).moves

    Returns:
        PacingAnalysisResult (never None, never raises for incomplete data)

    Coverage handling (best-effort):
        If `moves` is missing entries for some mainline move_numbers:
        - Warning is logged with details of missing moves
        - Those move_numbers are skipped (no PacingMetrics)
        - game_stats.has_coverage_gaps is set to True
        - game_stats.missing_move_eval_count contains the count
        Processing continues with available data.

    Guarantees:
        - pacing_metrics in ascending move_number order
        - game_stats always populated
        - tilt_episodes empty if tilt_detection_enabled=False
    """
    if config is None:
        config = PacingConfig()

    # Detect coverage gaps
    missing_moves, expected_max_move = _detect_coverage_gaps(time_data, moves)

    if missing_moves:
        missing_sample = sorted(missing_moves)[:5]
        _logger.warning(
            "MoveEval coverage incomplete: missing %d/%d moves (first few: %s). Pacing analysis will skip these moves.",
            len(missing_moves),
            expected_max_move,
            missing_sample,
        )

    # Compute game stats
    game_stats = _compute_game_stats(time_data, moves, config, missing_moves, expected_max_move)

    # Check minimum moves
    if game_stats.total_moves_analyzed < config.min_moves_for_stats:
        # Not enough data for meaningful analysis
        return PacingAnalysisResult(
            pacing_metrics=(),
            tilt_episodes=(),
            has_time_data=game_stats.moves_with_time_data > 0,
            game_stats=game_stats,
        )

    # Classify pacing
    pacing_metrics = _classify_pacing(moves, time_data, game_stats)

    # Detect tilt episodes
    tilt_episodes = _detect_tilt_episodes(pacing_metrics, game_stats, config)

    return PacingAnalysisResult(
        pacing_metrics=tuple(pacing_metrics),
        tilt_episodes=tuple(tilt_episodes),
        has_time_data=game_stats.moves_with_time_data > 0,
        game_stats=game_stats,
    )


# =============================================================================
# Helper Functions for Report Integration (Phase 60)
# =============================================================================


def get_pacing_icon(metrics: PacingMetrics | None) -> str:
    """Convert PacingMetrics to a display icon.

    Priority order: 🔥 > 💭 > 🐇 > 🐢

    Args:
        metrics: PacingMetrics for a move, or None

    Returns:
        Icon string: "🔥" (impulsive), "💭" (overthinking),
                     "🐇" (blitz), "🐢" (long_think), or "-" (normal/none)
    """
    if metrics is None:
        return "-"
    if metrics.is_impulsive:
        return "🔥"
    if metrics.is_overthinking:
        return "💭"
    if metrics.is_blitz:
        return "🐇"
    if metrics.is_long_think:
        return "🐢"
    return "-"


def extract_pacing_stats_for_summary(result: PacingAnalysisResult) -> dict[str, Any]:
    """Convert PacingAnalysisResult to a dict for stats_dict storage.

    Phase 59 guarantees:
        is_impulsive=True  => is_blitz=True
        is_overthinking=True => is_long_think=True
    Therefore:
        blitz_mistake_count <= blitz_count
        long_think_mistake_count <= long_think_count

    Args:
        result: PacingAnalysisResult from analyze_pacing()

    Returns:
        Serializable dict for summary stats aggregation
    """
    if not result.has_time_data:
        return {"has_time_data": False}

    player_stats = {}
    for player in ["B", "W"]:
        player_metrics = [m for m in result.pacing_metrics if m.player == player]
        player_stats[player] = {
            "blitz_count": sum(1 for m in player_metrics if m.is_blitz),
            "blitz_mistake_count": sum(1 for m in player_metrics if m.is_impulsive),
            "long_think_count": sum(1 for m in player_metrics if m.is_long_think),
            "long_think_mistake_count": sum(1 for m in player_metrics if m.is_overthinking),
        }

    tilt_episodes = [
        {
            "player": ep.player,
            "start_move": ep.start_move,
            "end_move": ep.end_move,
            "severity": ep.severity.value,
            "cumulative_loss": ep.cumulative_loss,
        }
        for ep in result.tilt_episodes
    ]

    return {
        "has_time_data": True,
        "player_stats": player_stats,
        "tilt_episodes": tilt_episodes,
    }
