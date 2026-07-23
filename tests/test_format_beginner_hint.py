"""Tests for :func:`katrain.core.beginner.format_hint.format_beginner_hint`.

Phase 254 (``→ why`` line) and Phase 255 (``[Hint]`` prefix i18n) were
originally split into two test files. They exercise the same pure
helper, so Phase 3 of the test-suite audit consolidates them here.

Coverage:

- :class:`TestFormatBeginnerHintWhyField` (Phase 254)
  ``→ why`` is appended only when the :why translation resolves to a
  real string; raw-key or empty inputs suppress the arrow line.
- :class:`TestFormatBeginnerHintPrefix` (Phase 255)
  Localised prefix takes precedence; raw key or empty falls back to
  the legacy ``[Hint]`` literal.
- :class:`TestFormatBeginnerHintBodyNewline`
  Body newlines are preserved verbatim.
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


class TestFormatBeginnerHintPrefix:
    """Phase 255 contract: localised prefix takes precedence; missing
    translation falls back to the legacy ``[Hint]`` string."""

    def test_translated_prefix_appears_in_output(self) -> None:
        result = format_beginner_hint(
            category=_category(),
            title="Dangerous Move",
            body="Body text",
            why="Why text",
            prefix="ヒント",
            fallback_title="FB",
            fallback_body="FB",
        )
        assert result.startswith("ヒント ")
        assert "→ Why text" in result

    def test_english_prefix(self) -> None:
        result = format_beginner_hint(
            category=_category(),
            title="Dangerous Move",
            body="Body text",
            why="Why text",
            prefix="Hint",
            fallback_title="FB",
            fallback_body="FB",
        )
        assert result.startswith("Hint ")
        assert "→ Why text" in result

    def test_missing_prefix_key_uses_legacy_default(self) -> None:
        """When ``beginner-hint:prefix`` is missing from .po, the
        legacy ``[Hint]`` string is used as a silent fallback."""
        result = format_beginner_hint(
            category=_category(),
            title="Dangerous Move",
            body="Body",
            why="",
            prefix="beginner-hint:prefix",  # raw key (missing translation)
            fallback_title="FB",
            fallback_body="FB",
        )
        assert result == "[Hint] Dangerous Move: Body"

    def test_no_why_omits_arrow(self) -> None:
        """Sanity: the prefix change is independent of the :why logic."""
        result = format_beginner_hint(
            category=_category(),
            title="T",
            body="B",
            why="",
            prefix="Tipp",
            fallback_title="FB",
            fallback_body="FB",
        )
        assert result == "Tipp T: B"
        assert "→" not in result


class TestFormatBeginnerHintBodyNewline:
    """Body newlines are preserved verbatim in the rendered output."""

    def test_multiline_body_newline_preserved(self) -> None:
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
