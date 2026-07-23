"""Tests for the beginner-hint ``[Hint]`` prefix rendering (Phase 255, refactored Phase E).

Phase 255 replaced the hard-coded ``[Hint]`` prefix with the
``beginner-hint:prefix`` i18n key so Japanese users see ``ヒント``.
Phase E moved the rendering logic into the Kivy-independent helper
:func:`katrain.core.beginner.format_hint.format_beginner_hint` so
this test can import it directly without copying the function
inline.

This file focuses on the **prefix fallback** branch:

- when ``beginner-hint:prefix`` resolves to a real translation,
  use it;
- when it resolves to the raw key (translation missing), fall back
  to the literal ``[Hint]`` string so legacy users keep their UI.
"""

from __future__ import annotations

from types import SimpleNamespace

from katrain.core.beginner.format_hint import format_beginner_hint


def _category() -> SimpleNamespace:
    return SimpleNamespace(
        i18n_namespace="beginner_hint:self_atari",
        fallback_title="Dangerous Move",
        fallback_body="Body",
    )


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
