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

Phase 265: ``apply_curator_weak_axis_label`` adds Curator metadata to
an *already* computed beginner hint. This is the real-time play path
where ``node.meaning_tag_id`` is unavailable, but the hint category
(e.g. ``MISTAKE_BLUNDER``) maps to a MeaningTag group (e.g.
``life_death_error``) that may be in the user's weak set.
"""

from __future__ import annotations

from dataclasses import replace
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


def apply_curator_weak_axis_label(
    hint: BeginnerHint | None,
    user_weak_tags: dict[str, int] | None,
    *,
    min_occurrences: int = 3,
) -> BeginnerHint | None:
    """Phase 265: re-label an existing beginner hint with curator-weak-axis metadata.

    Used for the real-time play path where ``node.meaning_tag_id`` is
    unavailable. We look at the hint's category, find related
    ``MeaningTagId`` values, and if any of them is in the user's weak
    set, we add a ``curator_weak_axis`` entry to the hint's context.

    The original hint (category, severity, coords, message) is
    preserved — the curator metadata is supplementary. UI code can
    then optionally display "あなたの弱点: X (N 回)" alongside the
    main beginner hint.

    Args:
        hint: Already-computed BeginnerHint (from priority chain), or None.
        user_weak_tags: ``{meaning_tag_id: occurrence_count}`` from the
            Curator profile. ``None`` / empty disables the re-label.
        min_occurrences: Minimum tag count to count as a "weak axis".

    Returns:
        The same ``BeginnerHint`` (frozen dataclass replacement) with
        context extended, or the original if no weak-axis match.
    """
    if hint is None or not user_weak_tags:
        return hint

    related = HintCategory.related_meaning_tag_ids(hint.category)
    if not related:
        return hint

    # Find the first related tag in the user's weak set, above threshold.
    # The mapping order in ``related_meaning_tag_ids`` reflects priority
    # (most specific first), so the first match is the most relevant.
    matched_tag: str | None = None
    matched_count: int = 0
    for tag_id in related:
        try:
            count = int(user_weak_tags.get(str(tag_id), 0))
        except (TypeError, ValueError):
            continue
        if count >= int(min_occurrences):
            matched_tag = str(tag_id)
            matched_count = count
            break

    if matched_tag is None:
        return hint

    # Frozen dataclass — use ``replace`` to keep immutability
    new_context = dict(hint.context or {})
    new_context["curator_weak_axis"] = {
        "tag_id": matched_tag,
        "occurrence_count": matched_count,
        "min_occurrences": int(min_occurrences),
    }
    return replace(hint, context=new_context)


__all__ = ["detect_curator_weak_axis", "apply_curator_weak_axis_label"]
