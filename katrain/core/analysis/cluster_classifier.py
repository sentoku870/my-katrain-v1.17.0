# katrain/core/analysis/cluster_classifier.py
"""Phase 82: Cluster classification for Karte Context injection.

Classifies ownership clusters into 3 semantic categories:
- GROUP_DEATH: Actor's stones were captured
- TERRITORY_LOSS: Actor lost territory
- MISSED_KILL: Actor failed to kill opponent's weak stones

This module provides:
- Stone position computation (no side effects, thread-safe)
- Cluster classification logic
- Karte Context injection helpers
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import (
    TYPE_CHECKING,
    cast,
)

from katrain.common.locale_utils import normalize_lang_code
from katrain.core.analysis.board_context import (
    OwnershipContext,
    extract_ownership_context,
)
from katrain.core.analysis.ownership_cluster import (
    ClusterExtractionConfig,
    OwnershipCluster,
    extract_clusters_from_nodes,
)

if TYPE_CHECKING:
    from katrain.core.game import Game
    from katrain.core.game_node import GameNode
    from katrain.core.sgf_parser import SGFNode


# =====================================================================
# Type Aliases
# =====================================================================

StonePosition = tuple[int, int, str]  # (col, row, player)
StoneSet = frozenset[StonePosition]


# =====================================================================
# Enums
# =====================================================================


class ClusterSemantics(str, Enum):
    """Semantic classification of a cluster."""

    GROUP_DEATH = "group_death"  # Actor's stones were captured
    TERRITORY_LOSS = "territory_loss"  # Actor lost territory
    MISSED_KILL = "missed_kill"  # Actor failed to kill opponent's weak stones
    AMBIGUOUS = "ambiguous"  # Cannot determine


# =====================================================================
# Constants
# =====================================================================

# Base confidence by semantics type
BASE_CONFIDENCE: dict[ClusterSemantics, float] = {
    ClusterSemantics.GROUP_DEATH: 0.7,  # Stone capture is concrete
    ClusterSemantics.MISSED_KILL: 0.5,  # Threshold-based
    ClusterSemantics.TERRITORY_LOSS: 0.3,  # Fallback (lower)
    ClusterSemantics.AMBIGUOUS: 0.0,
}

# Injection thresholds by semantics type
INJECTION_THRESHOLD: dict[ClusterSemantics, float] = {
    ClusterSemantics.GROUP_DEATH: 0.3,  # Low (captures are important)
    ClusterSemantics.MISSED_KILL: 0.4,  # Medium
    ClusterSemantics.TERRITORY_LOSS: 0.5,  # High (noise reduction)
    ClusterSemantics.AMBIGUOUS: 1.0,  # Never inject
}

# Territory Loss minimum |sum_delta|
TERRITORY_LOSS_MIN_DELTA = 1.0

# Missed Kill thresholds
WEAK_ADVANTAGE_THRESHOLD = 0.3
SURVIVED_ADVANTAGE_THRESHOLD = 0.3

# Confidence scaling factor
DELTA_SCALING_FACTOR = 0.1

# Semantics labels (localized)
SEMANTICS_LABELS: dict[ClusterSemantics, dict[str, str]] = {
    ClusterSemantics.GROUP_DEATH: {
        "en": "Group captured",
        "jp": "石が取られた",
    },
    ClusterSemantics.TERRITORY_LOSS: {
        "en": "Territory lost",
        "jp": "地を失った",
    },
    ClusterSemantics.MISSED_KILL: {
        "en": "Missed kill",
        "jp": "殺し損ねた",
    },
    ClusterSemantics.AMBIGUOUS: {
        "en": "Unknown",
        "jp": "不明",
    },
}


# =====================================================================
# Data Models
# =====================================================================


@dataclass(frozen=True)
class ClassifiedCluster:
    """A classified cluster with semantic meaning."""

    cluster: OwnershipCluster
    semantics: ClusterSemantics
    confidence: float  # 0.0-1.0
    affected_stones: tuple[StonePosition, ...]  # Stones in cluster
    debug_reason: str  # For testing/logging


@dataclass(frozen=True)
class ClusterClassificationContext:
    """Context needed for cluster classification.

    Note:
        This context is only created when ownership_grid is available
        for both parent and child nodes. If either is missing, this
        context is not created and injection is skipped.
    """

    actor: str  # "B" or "W" - the player who made the mistake
    parent_stones: StoneSet  # Stones before the move
    child_stones: StoneSet  # Stones after the move
    parent_ownership_ctx: OwnershipContext
    child_ownership_ctx: OwnershipContext
    board_size: tuple[int, int]


# =====================================================================
# Stone Reconstruction (Pure Functions)
# =====================================================================


def compute_stones_at_node(
    node: "SGFNode",
    board_size: tuple[int, int],
) -> StoneSet:
    """Compute stone positions at a node by replaying from root.

    Does NOT modify current_node. No side effects. Thread-safe.

    Processing order per node:
    1. placements (AB/AW): Place stones WITHOUT capture logic
    2. moves (B/W): Place stones WITH capture logic
    3. clear_placements (AE): Remove stones

    Args:
        node: Target GameNode
        board_size: (width, height)

    Returns:
        FrozenSet of (col, row, player) tuples

    Coordinate convention:
        (col, row) is 0-indexed
        col: left to right (0 = left edge = A column)
        row: bottom to top (0 = bottom edge)
        Reference: sgf_parser.py Move.from_sgf()
    """
    width, height = board_size
    # board[row][col] = player ("B", "W", or None)
    board: list[list[str | None]] = [[None] * width for _ in range(height)]

    for n in node.nodes_from_root:
        # Step 1: placements (AB/AW) - NO CAPTURE LOGIC
        for move in n.placements:
            if move.is_pass or move.coords is None:
                continue
            col, row = move.coords
            board[row][col] = move.player

        # Step 2: moves (B/W) - WITH CAPTURE LOGIC
        for move in n.moves:
            if move.is_pass or move.coords is None:
                continue
            col, row = move.coords
            player = move.player

            # Place the stone
            board[row][col] = player

            # Capture opponent stones (check adjacent groups)
            opponent = "W" if player == "B" else "B"
            for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nc, nr = col + dc, row + dr
                if 0 <= nc < width and 0 <= nr < height:
                    if board[nr][nc] == opponent:
                        group = _find_group(board, nc, nr, width, height)
                        if not _has_liberty(board, group, width, height):
                            for gc, gr in group:
                                board[gr][gc] = None

            # Suicide check (Rev.6: remove self-group)
            # After capturing opponent, if self has no liberties, remove self.
            # Suicide is illegal in standard rules but may appear in SGF.
            # Handle gracefully without exception.
            own_group = _find_group(board, col, row, width, height)
            if not _has_liberty(board, own_group, width, height):
                for gc, gr in own_group:
                    board[gr][gc] = None

        # Step 3: AE (clear) handling
        for clear_move in n.clear_placements:
            if not clear_move.is_pass and clear_move.coords is not None:
                col, row = clear_move.coords
                board[row][col] = None

    # Convert to StoneSet
    stones: set[StonePosition] = set()
    for row in range(height):
        for col in range(width):
            cell_player = board[row][col]
            if cell_player is not None:
                stones.add((col, row, cell_player))

    return frozenset(stones)


def _find_group(
    board: list[list[str | None]],
    start_col: int,
    start_row: int,
    width: int,
    height: int,
) -> set[tuple[int, int]]:
    """Find connected stones of the same color using BFS (O(1) with deque)."""
    player = board[start_row][start_col]
    if player is None:
        return set()

    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque([(start_col, start_row)])

    while queue:
        col, row = queue.popleft()  # O(1) with deque
        if (col, row) in visited:
            continue
        if not (0 <= col < width and 0 <= row < height):
            continue
        if board[row][col] != player:
            continue

        visited.add((col, row))
        for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            queue.append((col + dc, row + dr))

    return visited


def _has_liberty(
    board: list[list[str | None]],
    group: set[tuple[int, int]],
    width: int,
    height: int,
) -> bool:
    """Check if a group has any liberties."""
    for col, row in group:
        for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nc, nr = col + dc, row + dr
            if 0 <= nc < width and 0 <= nr < height:
                if board[nr][nc] is None:
                    return True
    return False


# =====================================================================
# Stone Cache
# =====================================================================


class StoneCache:
    """Cache for stone positions during Karte generation (one game)."""

    def __init__(self, game: "Game"):
        self._game = game
        self._board_size = game.board_size
        self._cache: dict[int, StoneSet] = {}  # move_number -> stones

    def get_stones_at_move(self, move_number: int) -> StoneSet:
        """Get stones at a move number (cached).

        Args:
            move_number: 1-indexed move number (0=root)

        Returns:
            FrozenSet of (col, row, player) tuples
        """
        if move_number in self._cache:
            return self._cache[move_number]

        node = self._find_node_by_move_number(move_number)
        if node is None:
            return frozenset()

        stones = compute_stones_at_node(node, self._board_size)
        self._cache[move_number] = stones
        return stones

    def _find_node_by_move_number(self, move_number: int) -> "GameNode" | None:
        """Find node by move number on mainline.

        Uses ordered_children[0] for mainline traversal
        (KaTrain convention, game.py:841 pattern).
        """
        node = self._game.root
        for _ in range(move_number):
            if not node.children:
                return None
            # ordered_children[0] = mainline
            node = cast("GameNode", node.ordered_children[0])
        return node


# =====================================================================
# Cluster Classification Helpers
# =====================================================================


def is_opponent_gain(cluster: OwnershipCluster, actor: str) -> bool:
    """Check if a cluster represents opponent's gain from actor's mistake.

    Args:
        cluster: OwnershipCluster to check
        actor: "B" or "W" - the player who made the mistake

    Returns:
        True if the cluster represents opponent gaining (actor losing)
    """
    if actor == "B":
        return cluster.sum_delta < 0  # White gains
    else:
        return cluster.sum_delta > 0  # Black gains


def get_stones_in_cluster(
    cluster: OwnershipCluster,
    stones: StoneSet,
) -> tuple[StonePosition, ...]:
    """Extract stones within a cluster's coordinates.

    Args:
        cluster: OwnershipCluster
        stones: Set of all stones

    Returns:
        Tuple of stones in cluster (sorted for determinism)
    """
    cluster_points: frozenset[tuple[int, int]] = cluster.coords
    stones_in_cluster = [
        (col, row, player)
        for (col, row, player) in stones
        if (col, row) in cluster_points
    ]
    return tuple(sorted(stones_in_cluster))


def compute_cluster_ownership_avg(
    cluster: OwnershipCluster,
    ownership_ctx: OwnershipContext,
) -> float:
    """Compute average ownership within a cluster.

    Uses Phase 81's OwnershipContext.get_ownership_at() for consistent
    coordinate access.

    Args:
        cluster: OwnershipCluster
        ownership_ctx: Phase 81's OwnershipContext

    Returns:
        Average ownership (black perspective: +1 = black, -1 = white)
    """
    if not cluster.coords or ownership_ctx.ownership_grid is None:
        return 0.0

    total = 0.0
    valid_count = 0
    for col, row in cluster.coords:
        val = ownership_ctx.get_ownership_at((col, row))
        if val is not None:
            total += val
            valid_count += 1

    return total / valid_count if valid_count > 0 else 0.0


def _detect_group_death(
    cluster: OwnershipCluster,
    actor: str,
    parent_stones: StoneSet,
    child_stones: StoneSet,
) -> tuple[bool, tuple[StonePosition, ...], str]:
    """Detect if actor's stones were captured in cluster.

    Returns:
        (is_group_death, affected_stones, debug_reason)
    """
    # Get actor's stones in cluster at parent
    parent_actor_stones = get_stones_in_cluster(
        cluster,
        frozenset(s for s in parent_stones if s[2] == actor),
    )

    # Get actor's stones in cluster at child
    child_actor_stones_set = frozenset(
        (s[0], s[1]) for s in child_stones if s[2] == actor
    )

    # Find stones that disappeared
    disappeared = []
    for stone in parent_actor_stones:
        if (stone[0], stone[1]) not in child_actor_stones_set:
            disappeared.append(stone)

    if disappeared:
        return (
            True,
            tuple(disappeared),
            f"Actor {actor} lost {len(disappeared)} stone(s) in cluster",
        )
    return (False, (), "No actor stones captured")


def _detect_territory_loss(
    cluster: OwnershipCluster,
    actor: str,
    parent_stones: StoneSet,
    child_stones: StoneSet,
) -> tuple[bool, str]:
    """Detect if actor lost territory (no stone capture).

    Returns:
        (is_territory_loss, debug_reason)
    """
    # Check minimum delta threshold
    if abs(cluster.sum_delta) < TERRITORY_LOSS_MIN_DELTA:
        return (False, f"sum_delta {cluster.sum_delta:.2f} < {TERRITORY_LOSS_MIN_DELTA}")

    # Get all stones in cluster at parent
    parent_cluster_stones = get_stones_in_cluster(cluster, parent_stones)
    child_cluster_stones = get_stones_in_cluster(cluster, child_stones)

    # Check if any stones were captured (would be GROUP_DEATH)
    parent_coords = frozenset((s[0], s[1]) for s in parent_cluster_stones)
    child_coords = frozenset((s[0], s[1]) for s in child_cluster_stones)
    if parent_coords - child_coords:
        return (False, "Stone capture detected, not territory loss")

    # Check if opponent gained (actor lost)
    if is_opponent_gain(cluster, actor):
        return (
            True,
            f"Territory loss: sum_delta={cluster.sum_delta:.2f} (opponent gain)",
        )

    return (False, "Not opponent gain")


def _detect_missed_kill(
    cluster: OwnershipCluster,
    actor: str,
    parent_ownership_ctx: OwnershipContext,
    child_ownership_ctx: OwnershipContext,
) -> tuple[bool, str]:
    """Detect if actor failed to kill opponent's weak stones.

    Uses ownership averaging to determine if:
    1. Actor had advantage in parent (could have killed)
    2. Opponent now has advantage in child (survived)

    Returns:
        (is_missed_kill, debug_reason)
    """
    parent_avg = compute_cluster_ownership_avg(cluster, parent_ownership_ctx)
    child_avg = compute_cluster_ownership_avg(cluster, child_ownership_ctx)

    # Convert to actor perspective
    if actor == "B":
        actor_adv_parent = parent_avg
        actor_adv_child = child_avg
    else:
        actor_adv_parent = -parent_avg
        actor_adv_child = -child_avg

    # Check thresholds
    actor_was_advantaged = actor_adv_parent >= WEAK_ADVANTAGE_THRESHOLD
    opponent_now_advantaged = actor_adv_child <= -SURVIVED_ADVANTAGE_THRESHOLD

    if actor_was_advantaged and opponent_now_advantaged:
        return (
            True,
            f"Missed kill: actor had {actor_adv_parent:.2f}, opponent now {-actor_adv_child:.2f}",
        )

    return (False, f"Not missed kill: parent={actor_adv_parent:.2f}, child={actor_adv_child:.2f}")


def compute_confidence(
    semantics: ClusterSemantics,
    sum_delta: float,
    affected_stone_count: int,
) -> float:
    """Compute classification confidence (0.0-1.0).

    Formula:
        confidence = base + |sum_delta| * DELTA_SCALING_FACTOR + stone_bonus
        capped to [0.0, 1.0]
    """
    base = BASE_CONFIDENCE.get(semantics, 0.0)
    delta_bonus = abs(sum_delta) * DELTA_SCALING_FACTOR
    stone_bonus = min(0.2, affected_stone_count * 0.05) if affected_stone_count > 0 else 0.0

    confidence = base + delta_bonus + stone_bonus
    return max(0.0, min(1.0, confidence))


def should_inject(classified: ClassifiedCluster) -> bool:
    """Determine if classification should be injected into Karte.

    Returns:
        True if injection should occur
    """
    threshold = INJECTION_THRESHOLD.get(classified.semantics, 1.0)

    # TERRITORY_LOSS has additional requirement
    if classified.semantics == ClusterSemantics.TERRITORY_LOSS:
        if abs(classified.cluster.sum_delta) < TERRITORY_LOSS_MIN_DELTA:
            return False

    return classified.confidence >= threshold


def get_semantics_label(semantics: ClusterSemantics, lang: str | None) -> str:
    """Get localized label for semantics.

    Args:
        lang: Language code (None, "", "jp", "ja", "en", "en_US", etc.)
              None/"" falls back to "en"

    Returns:
        Localized label string
    """
    internal_lang = normalize_lang_code(lang)
    labels = SEMANTICS_LABELS.get(semantics, SEMANTICS_LABELS[ClusterSemantics.AMBIGUOUS])
    return labels.get(internal_lang, labels["en"])


# =====================================================================
# Classification Logic
# =====================================================================


def classify_cluster(
    cluster: OwnershipCluster,
    ctx: ClusterClassificationContext,
) -> ClassifiedCluster:
    """Classify a cluster into 3 semantic categories.

    Classification priority:
    1. GROUP_DEATH: Actor's stones were captured
    2. MISSED_KILL: Actor failed to kill opponent's weak stones
    3. TERRITORY_LOSS: Actor lost territory
    4. AMBIGUOUS: Cannot determine

    Args:
        cluster: OwnershipCluster to classify
        ctx: Classification context

    Returns:
        ClassifiedCluster (always returns, AMBIGUOUS if can't determine)
    """
    try:
        # 1. Check GROUP_DEATH first (most concrete)
        is_death, affected, reason = _detect_group_death(
            cluster,
            ctx.actor,
            ctx.parent_stones,
            ctx.child_stones,
        )
        if is_death:
            return ClassifiedCluster(
                cluster=cluster,
                semantics=ClusterSemantics.GROUP_DEATH,
                confidence=compute_confidence(
                    ClusterSemantics.GROUP_DEATH,
                    cluster.sum_delta,
                    len(affected),
                ),
                affected_stones=affected,
                debug_reason=reason,
            )

        # 2. Check MISSED_KILL
        is_missed, reason = _detect_missed_kill(
            cluster,
            ctx.actor,
            ctx.parent_ownership_ctx,
            ctx.child_ownership_ctx,
        )
        if is_missed:
            return ClassifiedCluster(
                cluster=cluster,
                semantics=ClusterSemantics.MISSED_KILL,
                confidence=compute_confidence(
                    ClusterSemantics.MISSED_KILL,
                    cluster.sum_delta,
                    0,
                ),
                affected_stones=(),
                debug_reason=reason,
            )

        # 3. Check TERRITORY_LOSS
        is_loss, reason = _detect_territory_loss(
            cluster,
            ctx.actor,
            ctx.parent_stones,
            ctx.child_stones,
        )
        if is_loss:
            return ClassifiedCluster(
                cluster=cluster,
                semantics=ClusterSemantics.TERRITORY_LOSS,
                confidence=compute_confidence(
                    ClusterSemantics.TERRITORY_LOSS,
                    cluster.sum_delta,
                    0,
                ),
                affected_stones=(),
                debug_reason=reason,
            )

        # 4. AMBIGUOUS
        return ClassifiedCluster(
            cluster=cluster,
            semantics=ClusterSemantics.AMBIGUOUS,
            confidence=0.0,
            affected_stones=(),
            debug_reason="No classification matched",
        )

    except Exception as e:
        # Catch all exceptions and return AMBIGUOUS
        return ClassifiedCluster(
            cluster=cluster,
            semantics=ClusterSemantics.AMBIGUOUS,
            confidence=0.0,
            affected_stones=(),
            debug_reason=f"Exception: {e}",
        )


# =====================================================================
# Context Building
# =====================================================================


def get_ownership_context_pair(
    parent_node: "GameNode",
    child_node: "GameNode",
) -> tuple[OwnershipContext, OwnershipContext] | None:
    """Get OwnershipContext for both parent and child nodes.

    Returns None if either ownership_grid is None.
    Uses Phase 81's extract_ownership_context() for coordinate consistency.

    Returns:
        (parent_ctx, child_ctx) or None
    """
    parent_ctx = extract_ownership_context(parent_node)
    child_ctx = extract_ownership_context(child_node)

    if parent_ctx.ownership_grid is None or child_ctx.ownership_grid is None:
        return None

    return (parent_ctx, child_ctx)


def build_classification_context(
    actor: str,
    parent_node: "GameNode",
    child_node: "GameNode",
    parent_stones: StoneSet,
    child_stones: StoneSet,
) -> ClusterClassificationContext | None:
    """Build classification context.

    Returns None if ownership is missing for either node.

    Returns:
        ClusterClassificationContext or None
    """
    ownership_pair = get_ownership_context_pair(parent_node, child_node)
    if ownership_pair is None:
        return None

    parent_ctx, child_ctx = ownership_pair
    return ClusterClassificationContext(
        actor=actor,
        parent_stones=parent_stones,
        child_stones=child_stones,
        parent_ownership_ctx=parent_ctx,
        child_ownership_ctx=child_ctx,
        board_size=parent_ctx.board_size,
    )


# =====================================================================
# Karte Integration
# =====================================================================


def _get_cluster_context_for_move(
    game: "Game",
    move_number: int,
    lang: str | None,
    cache: StoneCache | None = None,
) -> str | None:
    """Get cluster context string for a move.

    Args:
        game: Game object
        move_number: 1-indexed move number
        lang: Language code
        cache: Optional stone cache for reuse

    Returns:
        Localized label string, or None if no injection

    Note:
        All exceptions are caught and return None (don't break Karte output).
    """
    try:
        # Guard: move_number must be > 0 (need parent node)
        if move_number <= 0:
            return None

        # Find nodes
        if cache:
            child_node = cache._find_node_by_move_number(move_number)
        else:
            # Direct traversal using mainline
            child_node = _find_mainline_node(game, move_number)

        if child_node is None:
            return None  # Mainline resolution failed

        parent_node_raw = child_node.parent
        if parent_node_raw is None:
            return None  # Root node has no parent
        parent_node = cast("GameNode", parent_node_raw)

        # Get player (actor) from the move
        move = child_node.move
        if move is None or move.player is None:
            return None

        actor = move.player

        # Get stones
        board_size = game.board_size
        if cache:
            parent_stones = cache.get_stones_at_move(move_number - 1)
            child_stones = cache.get_stones_at_move(move_number)
        else:
            parent_stones = compute_stones_at_node(parent_node, board_size)
            child_stones = compute_stones_at_node(child_node, board_size)

        # Build classification context
        classification_ctx = build_classification_context(
            actor,
            parent_node,
            child_node,
            parent_stones,
            child_stones,
        )
        if classification_ctx is None:
            return None  # Ownership missing

        # Extract clusters
        result = extract_clusters_from_nodes(parent_node, child_node)
        if result is None or not result.clusters:
            return None  # No clusters

        # Find clusters representing opponent's gain
        gain_clusters = [c for c in result.clusters if is_opponent_gain(c, actor)]
        if not gain_clusters:
            return None

        # Classify the largest gain cluster
        largest = max(gain_clusters, key=lambda c: abs(c.sum_delta))
        classified = classify_cluster(largest, classification_ctx)

        # Check injection threshold
        if not should_inject(classified):
            return None

        # Return localized label
        return get_semantics_label(classified.semantics, lang)

    except Exception:
        return None  # Catch all, don't break Karte


def _find_mainline_node(game: "Game", move_number: int) -> "GameNode" | None:
    """Find node by move number on mainline.

    Uses ordered_children[0] for mainline traversal.
    """
    node = game.root
    for _ in range(move_number):
        if not node.children:
            return None
        node = cast("GameNode", node.ordered_children[0])
    return node


# =====================================================================
# Module Exports
# =====================================================================

__all__ = [
    # Type aliases
    "StonePosition",
    "StoneSet",
    # Enums
    "ClusterSemantics",
    # Constants
    "BASE_CONFIDENCE",
    "INJECTION_THRESHOLD",
    "TERRITORY_LOSS_MIN_DELTA",
    "WEAK_ADVANTAGE_THRESHOLD",
    "SURVIVED_ADVANTAGE_THRESHOLD",
    "DELTA_SCALING_FACTOR",
    "SEMANTICS_LABELS",
    # Dataclasses
    "ClassifiedCluster",
    "ClusterClassificationContext",
    # Stone reconstruction
    "compute_stones_at_node",
    "StoneCache",
    # Classification helpers
    "is_opponent_gain",
    "get_stones_in_cluster",
    "compute_cluster_ownership_avg",
    "compute_confidence",
    "should_inject",
    "get_semantics_label",
    # Classification
    "classify_cluster",
    # Context building
    "get_ownership_context_pair",
    "build_classification_context",
    # Karte integration
    "_get_cluster_context_for_move",
    # Internal (for testing)
    "_detect_group_death",
    "_detect_territory_loss",
    "_detect_missed_kill",
    "_find_mainline_node",
    "_find_group",
    "_has_liberty",
]
