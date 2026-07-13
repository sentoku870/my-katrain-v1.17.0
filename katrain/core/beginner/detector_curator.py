"""Phase 186: Curator Weak-Axis Hint Detector

Derives a beginner hint from the Curator profile (the user's aggregated
Mistake / MeaningTag frequencies across analysed games).

Category:
- CURATOR_WEAK_AXIS: when the current node's ``meaning_tag_id`` matches
  one of the user's frequent weakness tags.

Design notes:
- Pure detector: takes a node + the loaded ``CuratorProfile`` and
  returns a BeginnerHint or None.
- Severity is 0 (lowest). Pure context info; never outranks Mistake /
  structural hints.
- "Frequent" is controlled by ``min_occurrences`` (default 3, matching
  the pattern-miner's statistical significance threshold from Phase 86).
- Requires ``node.meaning_tag_id`` to be set, which only happens for
  games analysed by the batch pipeline. For un-analysed nodes (live
  games with no batch profile), the detector simply returns None and
  the user never sees the hint.
- ``CuratorProfile.lookup`` already filters by ``min_occurrences``, so
  we can reuse it as the single gate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from katrain.core.beginner.models import BeginnerHint, HintCategory

if TYPE_CHECKING:
    pass


def detect_curator_weak_axis(
    node: Any,
    user_weak_tags: dict[str, int] | None,
    *,
    min_occurrences: int = 3,
) -> BeginnerHint | None:
    """Detect Curator Weak-Axis summary hint (Phase 186).

    Args:
        node: GameNode to evaluate. Must have a ``meaning_tag_id``
            attribute (typically populated by batch analysis).
        user_weak_tags: ``{meaning_tag_id: occurrence_count}`` loaded from
            the Curator profile. ``None`` or empty dict disables the
            hint.
        min_occurrences: Minimum number of times the tag must appear in
            the user's profile for it to count as a "weak axis". Tags
            below this are silently skipped.

    Returns:
        BeginnerHint with CURATOR_WEAK_AXIS, or None when the node has
        no meaning tag, the tag isn't in the user's weak set, or the
        tag count is below the threshold.
    """
    if not user_weak_tags:
        return None

    tag_id = getattr(node, "meaning_tag_id", None)
    if not tag_id:
        return None

    try:
        raw_count = int(user_weak_tags.get(str(tag_id), 0))
    except (TypeError, ValueError):
        return None
    if raw_count < int(min_occurrences):
        return None

    return BeginnerHint(
        category=HintCategory.CURATOR_WEAK_AXIS,
        coords=None,
        severity=0,
        context={
            "tag_id": str(tag_id),
            "occurrence_count": raw_count,
            "min_occurrences": int(min_occurrences),
        },
    )


__all__ = ["detect_curator_weak_axis"]
