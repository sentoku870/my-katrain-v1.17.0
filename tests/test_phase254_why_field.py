"""Tests for the beginner-hint ``:why`` rendering (Phase 254, refactored Phase E).

Phase 254 added the second ``→ why`` line to beginner hints. Phase E
moved the rendering logic into the Kivy-independent helper
:func:`katrain.core.beginner.format_hint.format_beginner_hint`,
which both the GUI wrapper and this test import directly. The
previous version of this file inlined a private ``_format`` copy
that had already drifted from the production code; the AST guard
in ``tests/test_phase256_kifunarabe_summary_suppression.py`` is the
appropriate place to verify the production wiring.

This file focuses on the **rendering contract** of the pure helper:

- raw ``beginner_hint:*`` i18n keys fall back to English fallbacks;
- ``[Hint]`` prefix fallback applies when ``beginner-hint:prefix``
  i18n key is missing;
- the ``→ why`` line is appended only when the :why key resolved
  to a non-empty, non-raw string.
"""

from __future__ import annotations

from types import SimpleNamespace

from katrain.core.beginner.format_hint import format_beginner_hint


def _category(
    i18n_namespace: str = "beginner_hint:self_atari", *, title: str = "Dangerous Move", body: str = "Body text"
) -> SimpleNamespace:
    return SimpleNamespace(
        i18n_namespace=i18n_namespace,
        fallback_title=title,
        fallback_body=body,
    )


class TestFormatBeginnerHintWhyField:
    """Phase 254 contract: ``→ why`` line is appended when :why resolves."""

    def test_all_three_keys_translated_appends_why(self) -> None:
        """All three keys resolve to real strings → both lines rendered."""
        result = format_beginner_hint(
            category=_category(),
            title="Dangerous Move",
            body="Playing here puts your group in atari.",
            why="A move that puts your own stones in atari can be captured next.",
            prefix="[Hint]",
            fallback_title="FB Title",
            fallback_body="FB Body",
        )
        assert "[Hint] Dangerous Move: Playing here puts your group in atari." in result
        assert "→ A move that puts your own stones in atari can be captured next." in result
        assert result.count("\n") == 1

    def test_why_key_missing_omits_why_line(self) -> None:
        """When :why is missing from .po (returns raw key or empty), no
        second line is rendered."""
        result = format_beginner_hint(
            category=_category(),
            title="Dangerous Move",
            body="Body",
            why="beginner_hint:self_atari:why",  # raw key (missing translation)
            prefix="[Hint]",
            fallback_title="FB Title",
            fallback_body="FB Body",
        )
        assert result == "[Hint] Dangerous Move: Body"
        assert "→" not in result

    def test_title_key_missing_uses_fallbacks(self) -> None:
        """When title resolves to the raw key, the English fallback is used.

        The :why line is suppressed when the master gate fires (title
        raw key) because the :why translation has no programmatic
        fallback (it only lives in .po files).
        """
        result = format_beginner_hint(
            category=_category(title="FB Title", body="FB Body"),
            title="beginner_hint:self_atari:title",  # raw key
            body="beginner_hint:self_atari:body",  # raw key
            why="A reason",
            prefix="[Hint]",
            fallback_title="FB Title",
            fallback_body="FB Body",
        )
        # Both fallbacks applied; :why suppressed by design.
        assert "[Hint] FB Title: FB Body" in result
        assert "→ A reason" not in result

    def test_empty_why_omits_arrow_line(self) -> None:
        """Empty :why produces a single-line output."""
        result = format_beginner_hint(
            category=_category(),
            title="Dangerous Move",
            body="Body",
            why="",
            prefix="[Hint]",
            fallback_title="FB Title",
            fallback_body="FB Body",
        )
        assert result == "[Hint] Dangerous Move: Body"
        assert "→" not in result

    def test_multiline_body_newline_preserved(self) -> None:
        """Body newlines are preserved verbatim in the rendered output."""
        result = format_beginner_hint(
            category=_category(),
            title="T",
            body="line1\nline2",
            why="reason",
            prefix="[Hint]",
            fallback_title="FB",
            fallback_body="FB",
        )
        assert result == "[Hint] T: line1\nline2\n→ reason"
