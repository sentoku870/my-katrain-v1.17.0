"""Settings popup search-filter predicates (Kivy-independent core).

Phase 287-G (UI/UX fixes, Wave C commit 8) introduced the search-bar
filter on the settings popup. The previous implementation lived
inline in ``katrain.gui.features.settings_popup`` and manipulated
``widget.opacity`` / ``widget.disabled`` / ``widget.height`` directly,
which made the logic impossible to test without a full Kivy Popup
hierarchy.

This module hosts the **predicate half** of the filter -- the part
that decides which rows match and which do not -- as a pure-Python
function that returns the matching indices. The GUI layer keeps the
widget-mutation half and calls :func:`compute_matching_indices`
first, then applies the side effects to the ``widgets[i]``
elements. Headless tests can call :func:`compute_matching_indices`
without importing Kivy.
"""

from __future__ import annotations


def compute_matching_indices(
    label_texts: list[str],
    query: str,
) -> tuple[list[int], int]:
    """Return ``(matching_indices, total_rows)`` for ``query`` over ``label_texts``.

    The query is whitespace-trimmed and case-folded. An empty query
    matches every row. Rows whose label does not contain the (folded)
    query are excluded from ``matching_indices``.

    Args:
        label_texts: Row labels in display order.
        query: Raw search string (already validated to be a ``str``).

    Returns:
        ``(matching_indices, total_rows)`` tuple. ``total_rows`` is
        the number of non-``None`` entries (consistent with the GUI
        helper's behaviour of skipping widgets that are not present).
    """
    q = (query or "").strip().lower()
    matching: list[int] = []
    total = 0
    for idx, raw_label in enumerate(label_texts):
        label = (raw_label or "").lower()
        total += 1
        if not q or q in label:
            matching.append(idx)
    return matching, total
