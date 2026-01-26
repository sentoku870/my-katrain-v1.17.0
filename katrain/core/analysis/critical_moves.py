# -*- coding: utf-8 -*-
"""Critical 3 Focused Review Mode.

This module provides functionality to select the top 3 most critical mistakes
from a game for focused review. Each critical move includes structured context
suitable for Karte output and LLM prompt generation.

Part of Phase 50: Critical 3 Focused Review Mode.

Key Features:
- Deterministic selection (same game -> same 3 moves)
- MeaningTag-weighted scoring
- Diversity penalty for tag variety
- Non-mutating classification (no side effects on MoveEval)

Public API:
- CriticalMove: Frozen dataclass for structured move data
- select_critical_moves(): Main selection function
- MEANING_TAG_WEIGHTS: Weight dictionary for tag-based scoring
- DEFAULT_MEANING_TAG_WEIGHT: Fallback weight for unknown tags

Example:
    >>> from katrain.core.analysis import select_critical_moves
    >>> critical = select_critical_moves(game, max_moves=3, lang="ja")
    >>> for cm in critical:
    ...     print(f"Move #{cm.move_number}: {cm.meaning_tag_label}")
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from katrain.core.game import Game
    from katrain.core.game_node import GameNode

# =============================================================================
# Constants
# =============================================================================

# Learning-value-based weights (life-death/reading > strategic > minor)
MEANING_TAG_WEIGHTS: Dict[str, float] = {
    # High priority - fundamental reading errors
    "life_death_error": 1.5,
    "capture_race_loss": 1.4,
    "reading_failure": 1.3,
    "connection_miss": 1.2,
    # Medium priority - strategic errors
    "direction_error": 1.1,
    "missed_tesuji": 1.1,
    "overplay": 1.0,
    "territorial_loss": 1.0,
    # Low priority - minor/ambiguous errors
    "shape_mistake": 0.9,
    "slow_move": 0.8,
    "endgame_slip": 0.8,
    "uncertain": 0.5,  # Fallback for unclassifiable
}

DEFAULT_MEANING_TAG_WEIGHT = 0.7  # Fallback for unknown tags (future-proofing)

DIVERSITY_PENALTY_FACTOR = 0.5  # Multiplier for repeated tags

CRITICAL_SCORE_PRECISION = 4  # Decimal places for deterministic rounding


# =============================================================================
# Data Model
# =============================================================================


@dataclass(frozen=True)
class CriticalMove:
    """LLM prompt generation-ready structured Critical Move.

    All fields are populated (only score_stdev may be None).
    frozen=True ensures immutability for thread-safety and hashability.

    Attributes:
        move_number: 1-indexed move number (same as MoveEval.move_number)
        player: "B" or "W"
        gtp_coord: GTP coordinate (e.g., "D4", "pass")

        score_loss: Loss from get_canonical_loss_from_move(), >= 0, side-to-move perspective
        delta_winrate: MoveEval.delta_winrate, black perspective

        meaning_tag_id: MeaningTagId.value (e.g., "overplay")
        meaning_tag_label: Localized label from get_tag_label()
        position_difficulty: PositionDifficulty.value ("easy"/"normal"/"hard"/"only"/"unknown")
        reason_tags: Immutable tuple of reason tags

        score_stdev: KataGo analysis["root"]["scoreStdev"] (None for Leela/unanalyzed)
        game_phase: classify_game_phase() result ("opening"/"middle"/"yose")

        importance_score: MoveEval.importance_score (after pick_important_moves)
        critical_score: Final score (rounded, with weight and diversity penalty)
    """

    # Identification
    move_number: int
    player: str
    gtp_coord: str

    # Loss metrics
    score_loss: float
    delta_winrate: float

    # Classification
    meaning_tag_id: str
    meaning_tag_label: str
    position_difficulty: str
    reason_tags: Tuple[str, ...]

    # Context
    score_stdev: Optional[float]
    game_phase: str

    # Scoring
    importance_score: float
    critical_score: float


# =============================================================================
# Scoring Functions
# =============================================================================


def _get_meaning_tag_weight(tag_id: Optional[str]) -> float:
    """Get weight for a MeaningTag (handles None/unknown).

    Args:
        tag_id: meaning_tag_id (None allowed)

    Returns:
        - None -> DEFAULT_MEANING_TAG_WEIGHT (0.7)
        - "uncertain" -> 0.5 (from MEANING_TAG_WEIGHTS)
        - Known tag -> corresponding weight
        - Unknown tag -> DEFAULT_MEANING_TAG_WEIGHT (0.7)
    """
    if tag_id is None:
        return DEFAULT_MEANING_TAG_WEIGHT
    return MEANING_TAG_WEIGHTS.get(tag_id, DEFAULT_MEANING_TAG_WEIGHT)


def _compute_diversity_penalty(
    tag_id: Optional[str],
    selected_tag_ids: Tuple[str, ...],
) -> float:
    """Compute penalty for tag overlap with already-selected tags.

    Args:
        tag_id: Current move's meaning_tag_id (None allowed)
        selected_tag_ids: Tuple of already-selected tag IDs

    Returns:
        1.0: Tag is unique, "uncertain", or None (no penalty for ambiguous)
        DIVERSITY_PENALTY_FACTOR^n: For n overlaps
    """
    if tag_id is None or tag_id == "uncertain":
        return 1.0  # No penalty for ambiguous classification

    count = selected_tag_ids.count(tag_id)
    return DIVERSITY_PENALTY_FACTOR**count


def _compute_critical_score(
    importance: float,
    tag_id: Optional[str],
    selected_tag_ids: Tuple[str, ...],
) -> float:
    """Compute critical score with deterministic rounding.

    Formula: importance * meaning_tag_weight * diversity_penalty

    Uses Decimal ROUND_HALF_UP to eliminate floating-point variance.

    Args:
        importance: MoveEval.importance_score
        tag_id: meaning_tag_id (None allowed)
        selected_tag_ids: Already-selected tag IDs for diversity penalty

    Returns:
        Critical score rounded to CRITICAL_SCORE_PRECISION decimal places
    """
    weight = _get_meaning_tag_weight(tag_id)
    penalty = _compute_diversity_penalty(tag_id, selected_tag_ids)

    raw_score = importance * weight * penalty

    # Deterministic rounding (Python's round() uses banker's rounding)
    quantized = Decimal(str(raw_score)).quantize(
        Decimal(10) ** -CRITICAL_SCORE_PRECISION,
        rounding=ROUND_HALF_UP,
    )
    return float(quantized)


def _sort_key(move_number: int, score: float) -> Tuple[float, int]:
    """Deterministic sort key for candidate selection.

    Primary: critical_score descending (negated for ascending sort)
    Secondary: move_number ascending (earlier moves prioritized)
    """
    return (-score, move_number)


# =============================================================================
# Node Map & Score Stdev Helpers
# =============================================================================


def _build_node_map(game: "Game") -> Dict[int, "GameNode"]:
    """Build move_number -> GameNode mapping for main branch.

    Note:
    - iter_main_branch_nodes() yields only nodes with moves (root excluded)
    - Uses node.depth (SGFNode cached property, root=0)
    - Result: node_map[1] = first move's node (root=0 not included)

    Index correspondence:
    - MoveEval.move_number=1 -> node_map[1] OK
    - MoveEval.move_number=N -> node_map[N] OK

    Rationale: Same pattern used in engine_compare.py:379
    """
    from katrain.core.analysis import iter_main_branch_nodes

    node_map: Dict[int, Any] = {}
    for node in iter_main_branch_nodes(game):
        node_map[node.depth] = node
    return node_map


def _get_score_stdev_from_node(node: "GameNode") -> Optional[float]:
    """Safely extract scoreStdev from a GameNode.

    KataGo: node.analysis["root"]["scoreStdev"]
    Leela Zero: No scoreStdev field -> None
    Unanalyzed: analysis_exists=False -> None

    Returns:
        float: scoreStdev value
        None: No analysis, Leela, or missing field (no error raised)
    """
    # Safe check via analysis_exists property (game_node.py:307)
    if not getattr(node, "analysis_exists", False):
        return None

    analysis = getattr(node, "analysis", None)
    if analysis is None:
        return None

    # KaTrain internally always uses "root" key (normalized at game_node.py:286)
    root_info = analysis.get("root")
    if root_info is None:
        return None

    return root_info.get("scoreStdev")


def _get_score_stdev_for_move(
    node_map: Dict[int, "GameNode"],
    move_number: int,
) -> Optional[float]:
    """Get scoreStdev for a move number.

    Args:
        node_map: Result from _build_node_map()
        move_number: Target move number (1-indexed)

    Returns:
        scoreStdev or None
    """
    node = node_map.get(move_number)
    if node is None:
        return None
    return _get_score_stdev_from_node(node)


# =============================================================================
# MeaningTag Classification (Non-Mutating)
# =============================================================================


def _classify_meaning_tags(
    moves: List[Any],  # List[MoveEval]
    snapshot: Any,  # EvalSnapshot
) -> Dict[int, str]:
    """Build local meaning_tag_id mapping (non-mutating).

    If move already has meaning_tag_id set, uses that.
    Otherwise classifies via classify_meaning_tag().

    Returns:
        {move_number: meaning_tag_id} mapping
    """
    from katrain.core.analysis.meaning_tags import (
        ClassificationContext,
        classify_meaning_tag,
    )

    total_moves = len(snapshot.moves)
    ctx = ClassificationContext(total_moves=total_moves)
    result: Dict[int, str] = {}

    for move in moves:
        if move.meaning_tag_id is not None:
            result[move.move_number] = move.meaning_tag_id
        else:
            tag = classify_meaning_tag(move, context=ctx)
            result[move.move_number] = tag.id.value

    return result


# =============================================================================
# Main Selection Function
# =============================================================================


def select_critical_moves(
    game: "Game",
    *,
    max_moves: int = 3,
    lang: str = "ja",
    level: str = "normal",
) -> List[CriticalMove]:
    """Select top critical moves for focused review.

    Determinism guarantee:
    - Same game -> Same result
    - Sort key: (critical_score DESC, move_number ASC)
    - Floating-point rounding eliminates variance

    Args:
        game: Game object
        max_moves: Maximum moves to select (default: 3)
        lang: Label language ("ja" or "en")
        level: Important move level ("easy"/"normal"/"strict")

    Returns:
        List[CriticalMove] - Up to max_moves items, sorted by critical_score descending
    """
    from katrain.core.analysis import (
        snapshot_from_game,
        classify_game_phase,
        get_canonical_loss_from_move,
        pick_important_moves,
    )
    from katrain.core.analysis.meaning_tags import MeaningTagId, get_tag_label

    # Step 1: Build snapshot and get important moves
    snapshot = snapshot_from_game(game)
    important_moves = pick_important_moves(snapshot, level=level, recompute=True)

    if not important_moves:
        return []

    # Step 2: Classify meaning tags (non-mutating)
    meaning_tag_map = _classify_meaning_tags(important_moves, snapshot)

    # Step 3: Build node map for scoreStdev lookup
    node_map = _build_node_map(game)

    # Step 4: Get board size for game phase classification
    board_size = 19
    root = getattr(game, "root", None)
    if root is not None:
        board_size_tuple = getattr(root, "board_size", (19, 19))
        if isinstance(board_size_tuple, (list, tuple)) and len(board_size_tuple) >= 1:
            board_size = board_size_tuple[0]

    # Step 5: Greedy selection with diversity penalty
    candidates = list(important_moves)
    selected: List[CriticalMove] = []
    selected_tag_ids: Tuple[str, ...] = ()

    for _ in range(max_moves):
        if not candidates:
            break

        # Compute critical scores for all candidates
        scores: Dict[int, float] = {}
        for move in candidates:
            tag_id = meaning_tag_map.get(move.move_number)
            importance = move.importance_score or 0.0
            scores[move.move_number] = _compute_critical_score(
                importance, tag_id, selected_tag_ids
            )

        # Sort by (critical_score DESC, move_number ASC)
        candidates.sort(key=lambda m: _sort_key(m.move_number, scores[m.move_number]))

        # Select best candidate
        best = candidates.pop(0)
        best_tag_id = meaning_tag_map.get(best.move_number, "uncertain")

        # Build CriticalMove
        try:
            tag_enum = MeaningTagId(best_tag_id)
            tag_label = get_tag_label(tag_enum, lang=lang)
        except ValueError:
            # Unknown tag - use raw ID as label
            tag_label = best_tag_id

        critical_move = CriticalMove(
            move_number=best.move_number,
            player=best.player or "?",
            gtp_coord=best.gtp or "?",
            score_loss=get_canonical_loss_from_move(best),
            delta_winrate=best.delta_winrate or 0.0,
            meaning_tag_id=best_tag_id,
            meaning_tag_label=tag_label,
            position_difficulty=(
                best.position_difficulty.value
                if best.position_difficulty is not None
                else "unknown"
            ),
            reason_tags=tuple(best.reason_tags) if best.reason_tags else (),
            score_stdev=_get_score_stdev_for_move(node_map, best.move_number),
            game_phase=classify_game_phase(best.move_number, board_size),
            importance_score=best.importance_score or 0.0,
            critical_score=scores[best.move_number],
        )

        selected.append(critical_move)
        selected_tag_ids = (*selected_tag_ids, best_tag_id)

    return selected


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Data Model
    "CriticalMove",
    # Main Function
    "select_critical_moves",
    # Constants (for testing)
    "MEANING_TAG_WEIGHTS",
    "DEFAULT_MEANING_TAG_WEIGHT",
    "DIVERSITY_PENALTY_FACTOR",
    "CRITICAL_SCORE_PRECISION",
    # Internal functions (exported for testing)
    "_get_meaning_tag_weight",
    "_compute_diversity_penalty",
    "_compute_critical_score",
    "_build_node_map",
    "_get_score_stdev_from_node",
    "_get_score_stdev_for_move",
    "_classify_meaning_tags",
]
