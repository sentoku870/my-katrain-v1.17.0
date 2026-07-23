"""Beginner-hint rendering helper (Kivy-independent core).

Phase 91-92 introduced the BeginnerHint formatting inside
``katrain.gui.controlspanel.ControlsPanel._format_beginner_hint``;
Phase 179.1 replaced the legacy hard-coded key table with the
``HintCategory.i18n_namespace`` property; Phase 254 added the
``→ why`` 2nd line; Phase 255 replaced the hard-coded ``[Hint]``
prefix with an i18n key. All of that logic was buried inside a GUI
class method, which forced headless tests to copy it inline
(`tests/test_phase254_why_field.py` and `test_phase255_hint_prefix.py`
each defined a private ``_format`` replica that silently drifted
from the production implementation).

This module hosts the **rendering logic** as a pure function so
the GUI wrapper can delegate to it and the test suite can call it
directly without importing Kivy.

The function is *not* generic: it accepts the small data shape that
matches the production call site (a category stub exposing
``i18n_namespace`` / ``fallback_title`` / ``fallback_body`` and an
i18n callable). A real :class:`HintCategory` satisfies this duck
type.
"""

from __future__ import annotations

from typing import Protocol


class _HintCategoryLike(Protocol):
    """Minimal duck-typed surface the renderer needs.

    Both the production :class:`katrain.core.beginner.models.HintCategory`
    and the test stub in ``tests/test_phase254_why_field.py``
    satisfy this protocol.
    """

    i18n_namespace: str
    fallback_title: str
    fallback_body: str


def format_beginner_hint(
    category: _HintCategoryLike,
    title: str,
    body: str,
    why: str,
    prefix: str,
    fallback_title: str,
    fallback_body: str,
) -> str:
    """Build the display string for a single beginner hint.

    Args:
        category: The category stub (kept for future attribute access).
        title: Resolved title string from i18n (raw key on miss).
        body: Resolved body string from i18n (raw key on miss).
        why: Resolved ``:why`` string from i18n (raw key on miss; may be empty).
        prefix: Resolved ``beginner-hint:prefix`` string from i18n.
        fallback_title: English fallback applied when ``title`` is the raw key.
        fallback_body: English fallback applied when ``body`` is the raw key.

    Returns:
        Formatted two-line display string. The second line
        (``→ why``) is appended only when the :why i18n key
        resolved to a non-raw, non-empty string.
    """
    # If i18n key is not found (returns the raw key), use English
    # fallback. The same sentinel check works for all three keys
    # because they share a common prefix.
    if title.startswith("beginner_hint:"):
        title = fallback_title
        body = fallback_body
        # The :why key has no programmatic fallback (it lives in
        # the .po files). Leave it empty so the second line is
        # not rendered for users whose .po is missing the key.
        why = ""

    # Phase 254: only append the "why" line when the i18n key
    # resolved to a non-empty, non-raw-key string. Falls back
    # silently for languages whose .po is missing the :why key.
    # Phase 255: the [Hint] prefix is now an i18n key so jp users
    # see "ヒント" instead of the English word. Falls back to the
    # raw "[Hint]" string when the .po is missing the key.
    if prefix.startswith("beginner-hint:"):
        prefix = "[Hint]"

    if why and not why.startswith("beginner_hint:"):
        return f"{prefix} {title}: {body}\n→ {why}"
    return f"{prefix} {title}: {body}"
