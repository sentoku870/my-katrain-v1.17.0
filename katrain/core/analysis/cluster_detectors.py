"""Phase 173: Per-semantics detectors for cluster classification.

Extracted from ``cluster_classifier.py`` so the classifier stays focused on
the classification pipeline.

Detectors
---------

- :func:`_detect_group_death` — was actor captured in this cluster?
- :func:`_detect_territory_loss` — did actor lose territory without capture?
- :func:`_detect_missed_kill` — did actor fail to kill a weak group?

Helpers
-------

- :func:`compute_confidence` (also re-exported as :func:`compute_cluster_confidence`)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.core.analysis.board_context import OwnershipContext
    from katrain.core.analysis.cluster_classifier import ClusterSemantics, StonePosition, StoneSet
    from katrain.core.analysis.ownership_cluster import OwnershipCluster


# =====================================================================
# Detection constants (Phase 82 originals; thresholds preserved verbatim).
# Owned by this module so the dependency between
# ``cluster_detectors`` -> ``cluster_classifier`` stays one-directional.
# ``cluster_classifier`` re-exports these names for backward compatibility.
# =====================================================================

TERRITORY_LOSS_MIN_DELTA = 1.0

# Missed Kill thresholds
WEAK_ADVANTAGE_THRESHOLD = 0.3
SURVIVED_ADVANTAGE_THRESHOLD = 0.3

# Confidence scaling factor
DELTA_SCALING_FACTOR = 0.1


def _get_base_confidence() -> dict[ClusterSemantics, float]:
    """Lazily build & cache ``BASE_CONFIDENCE`` from ``ClusterSemantics``.

    Imported lazily to avoid an import cycle between
    ``cluster_detectors`` and ``cluster_classifier`` (the latter owns
    :class:`ClusterSemantics`).
    """
    cache_key = "_BASE_CONFIDENCE_CACHE"
    cached: dict[ClusterSemantics, float] | None = globals().get(cache_key)  # type: ignore[assignment]
    if cached is not None:
        return cached
    from katrain.core.analysis.cluster_classifier import ClusterSemantics

    cached = {
        ClusterSemantics.GROUP_DEATH: 0.7,  # Stone capture is concrete
        ClusterSemantics.MISSED_KILL: 0.5,  # Threshold-based
        ClusterSemantics.TERRITORY_LOSS: 0.3,  # Fallback (lower)
        ClusterSemantics.AMBIGUOUS: 0.0,
    }
    globals()[cache_key] = cached
    return cached


# =====================================================================
# Detectors
# =====================================================================


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
    from katrain.core.analysis.cluster_classifier import get_stones_in_cluster

    # Get actor's stones in cluster at parent
    parent_actor_stones = get_stones_in_cluster(
        cluster,
        frozenset(s for s in parent_stones if s[2] == actor),
    )

    # Get actor's stones in cluster at child
    child_actor_stones_set = frozenset((s[0], s[1]) for s in child_stones if s[2] == actor)

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
    from katrain.core.analysis.cluster_classifier import get_stones_in_cluster, is_opponent_gain

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

    Returns:
        (is_missed_kill, debug_reason)
    """
    from katrain.core.analysis.cluster_classifier import compute_cluster_ownership_avg

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

    The base value is sourced from ``BASE_CONFIDENCE`` (lazily built from
    ``ClusterSemantics`` so we avoid an import cycle with
    ``cluster_classifier``).
    """
    base = _get_base_confidence().get(semantics, 0.0)
    delta_bonus = abs(sum_delta) * DELTA_SCALING_FACTOR
    stone_bonus = min(0.2, affected_stone_count * 0.05) if affected_stone_count > 0 else 0.0

    confidence = base + delta_bonus + stone_bonus
    return max(0.0, min(1.0, confidence))


# Public alias maintained for backward compatibility with ``analysis/__init__.py``.
compute_cluster_confidence = compute_confidence
