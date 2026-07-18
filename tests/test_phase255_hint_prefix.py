"""Phase 255: [Hint] prefix is an i18n key.

Replaces the hardcoded ``[Hint]`` string in
``ControlsPanel._format_beginner_hint`` with an i18n lookup. The
key is ``beginner-hint:prefix`` (hyphen, not underscore, to avoid
clashing with the category namespace).
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def _format(category, fallback_title, fallback_body, i18n):
    """Replicate the production render function."""
    namespace = category.i18n_namespace
    title = i18n(f"{namespace}:title")
    body = i18n(f"{namespace}:body")
    why = i18n(f"{namespace}:why")

    if title.startswith("beginner_hint:"):
        title = fallback_title
        body = fallback_body
        why = ""

    prefix = i18n("beginner-hint:prefix")
    if prefix.startswith("beginner-hint:"):
        prefix = "[Hint]"

    if why and not why.startswith("beginner_hint:"):
        return f"{prefix} {title}: {body}\n→ {why}"
    return f"{prefix} {title}: {body}"


def _category(value):
    return SimpleNamespace(i18n_namespace=f"beginner_hint:{value}")


class TestHintPrefixI18n:
    """Phase 255: [Hint] prefix is an i18n key, not a hardcoded string."""

    def test_translated_prefix_appears_in_output(self):
        cat = _category("self_atari")
        gettext = lambda key: {  # noqa: E731
            "beginner-hint:prefix": "ヒント",
            "beginner_hint:self_atari:title": "Dangerous Move",
            "beginner_hint:self_atari:body": "Body",
            "beginner_hint:self_atari:why": "Why text",
        }.get(key, key)
        result = _format(cat, "FB", "FB", gettext)
        # The Japanese prefix is used, not "[Hint]".
        assert result.startswith("ヒント ")
        assert "→ Why text" in result

    def test_english_prefix(self):
        cat = _category("self_atari")
        gettext = lambda key: {  # noqa: E731
            "beginner-hint:prefix": "Hint",
            "beginner_hint:self_atari:title": "Dangerous Move",
            "beginner_hint:self_atari:body": "Body",
            "beginner_hint:self_atari:why": "Why text",
        }.get(key, key)
        result = _format(cat, "FB", "FB", gettext)
        # "Hint" (the English msgstr, not the raw key) is used.
        assert result.startswith("Hint ")
        # Must NOT start with "[Hint]" (the legacy hardcoded string).
        assert not result.startswith("[Hint]")

    def test_missing_prefix_key_uses_legacy_default(self):
        """When ``beginner-hint:prefix`` is missing from .po, the
        legacy ``[Hint]`` string is used as a silent fallback."""
        cat = _category("self_atari")
        gettext = lambda key: {  # noqa: E731
            "beginner_hint:self_atari:title": "Dangerous Move",
            "beginner_hint:self_atari:body": "Body",
            "beginner_hint:self_atari:why": "",
            # prefix key absent → gettext returns the raw key
        }.get(key, key)
        result = _format(cat, "FB", "FB", gettext)
        # Legacy [Hint] used as fallback.
        assert result == "[Hint] Dangerous Move: Body"

    def test_no_why_omits_arrow(self):
        """Sanity: the prefix change is independent of the :why logic."""
        cat = _category("self_atari")
        gettext = lambda key: {  # noqa: E731
            "beginner-hint:prefix": "Tipp",
            "beginner_hint:self_atari:title": "T",
            "beginner_hint:self_atari:body": "B",
            "beginner_hint:self_atari:why": "beginner_hint:self_atari:why",  # raw
        }.get(key, key)
        result = _format(cat, "FB", "FB", gettext)
        assert result == "Tipp T: B"
        assert "→" not in result


class TestProductionCodeUsesPrefixKey:
    @pytest.fixture
    def controlspanel_source(self) -> str:
        path = Path(r"D:\github\katrain-1.17.0\katrain\gui\controlspanel.py")
        return path.read_text(encoding="utf-8")

    def test_render_fn_uses_i18n_prefix(self, controlspanel_source):
        tree = ast.parse(controlspanel_source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_format_beginner_hint":
                src = ast.unparse(node)
                assert "beginner-hint:prefix" in src
                return
        pytest.fail("_format_beginner_hint not found")

    def test_legacy_default_in_source(self, controlspanel_source):
        """The literal ``[Hint]`` must still appear as a fallback
        sentinel — if it disappears entirely, the .po-missing
        branch silently breaks."""
        assert "[Hint]" in controlspanel_source
