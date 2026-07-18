"""Phase 254: beginner-hint :why field is rendered in the GUI.

Before Phase 254, the i18n keys ``beginner_hint:*:why`` were translated
in jp + en but had no consumer — the GUI's ``_format_beginner_hint``
only emitted ``title`` + ``body``. This test locks the new behaviour:
the formatted text contains a second line with the localized :why
text, prefixed by a `→` arrow so it's clearly secondary information.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

# ---------------------------------------------------------------------------
# Replica of the render function (kept in sync with controlspanel.py)
# ---------------------------------------------------------------------------


def _format(category, fallback_title, fallback_body, i18n):
    """Replicate ControlsPanel._format_beginner_hint logic without Kivy.

    Args:
        category: stub with .i18n_namespace property
        fallback_title: English fallback when i18n misses
        fallback_body: same
        i18n: a gettext-like callable that takes a key and returns
            the translation (or the raw key when missing)
    """
    namespace = category.i18n_namespace
    title = i18n(f"{namespace}:title")
    body = i18n(f"{namespace}:body")
    why = i18n(f"{namespace}:why")

    if title.startswith("beginner_hint:"):
        title = fallback_title
        body = fallback_body
        why = ""

    if why and not why.startswith("beginner_hint:"):
        return f"[Hint] {title}: {body}\n→ {why}"
    return f"[Hint] {title}: {body}"


def _category(value: str):
    """Simple stub with .i18n_namespace == 'beginner_hint:<value>'."""
    return SimpleNamespace(i18n_namespace=f"beginner_hint:{value}")


# ---------------------------------------------------------------------------
# Behavioural tests
# ---------------------------------------------------------------------------


class TestFormatHintWithWhy:
    """Phase 254: :why is rendered as a 2nd line with a `→` prefix."""

    def test_all_three_keys_translated_appends_why(self):
        cat = _category("self_atari")
        gettext = lambda key: {  # noqa: E731
            "beginner_hint:self_atari:title": "Dangerous Move",
            "beginner_hint:self_atari:body": "Playing here puts your group in atari.",
            "beginner_hint:self_atari:why": "A move that puts your own stones in atari can be captured next.",
        }.get(key, key)
        result = _format(cat, "FB Title", "FB Body", gettext)
        # Three components visible: title, body, why.
        assert "[Hint] Dangerous Move: Playing here puts your group in atari." in result
        assert "→ A move that puts your own stones in atari can be captured next." in result
        # Two lines: title/body on line 1, why on line 2.
        assert result.count("\n") == 1

    def test_why_key_missing_omits_why_line(self):
        """When :why is missing from .po, only the title:body line is rendered."""
        cat = _category("self_atari")
        gettext = lambda key: {  # noqa: E731
            "beginner_hint:self_atari:title": "Dangerous Move",
            "beginner_hint:self_atari:body": "Body",
            # :why is absent → raw key returned
        }.get(key, key)
        result = _format(cat, "FB Title", "FB Body", gettext)
        # Only one line, no arrow.
        assert result == "[Hint] Dangerous Move: Body"
        assert "→" not in result

    def test_why_key_returns_raw_key_omits_why_line(self):
        """If :why key returns the raw key (missing from .po), it must
        not leak into the rendered text."""
        cat = _category("self_atari")
        gettext = lambda key: {  # noqa: E731
            "beginner_hint:self_atari:title": "Dangerous Move",
            "beginner_hint:self_atari:body": "Body",
            "beginner_hint:self_atari:why": "beginner_hint:self_atari:why",  # raw key
        }.get(key, key)
        result = _format(cat, "FB Title", "FB Body", gettext)
        assert result == "[Hint] Dangerous Move: Body"
        assert "beginner_hint:self_atari:why" not in result

    def test_title_missing_uses_english_fallback(self):
        """When title is missing, the :why key is not consulted (it
        lives in the .po files; no programmatic fallback)."""
        cat = _category("self_atari")
        gettext = lambda key: {  # noqa: E731
            "beginner_hint:self_atari:title": "beginner_hint:self_atari:title",  # raw
            "beginner_hint:self_atari:body": "beginner_hint:self_atari:body",
            "beginner_hint:self_atari:why": "An explanatory sentence",
        }.get(key, key)
        result = _format(cat, "FB Title", "FB Body", gettext)
        # Fallback title/body, no :why (intentionally blanked out).
        assert result == "[Hint] FB Title: FB Body"
        assert "→" not in result

    def test_why_empty_string_omits_why_line(self):
        """An explicit empty :why (e.g. .po has ``msgstr ""``) is
        treated as missing — no second line."""
        cat = _category("self_atari")
        gettext = lambda key: {  # noqa: E731
            "beginner_hint:self_atari:title": "Title",
            "beginner_hint:self_atari:body": "Body",
            "beginner_hint:self_atari:why": "",
        }.get(key, key)
        result = _format(cat, "FB Title", "FB Body", gettext)
        assert result == "[Hint] Title: Body"
        assert "→" not in result

    @pytest.mark.parametrize(
        "category_value",
        [
            "self_atari",
            "cut_risk",
            "low_liberties",
            "self_capture_like",
            "mistake_blunder",
            "curator_weak_axis",
        ],
    )
    def test_all_categories_support_why(self, category_value):
        """Every hint category should support the :why field uniformly."""
        cat = _category(category_value)
        gettext = lambda key: "Why text" if key.endswith(":why") else "T" if key.endswith(":title") else "B"  # noqa: E731
        result = _format(cat, "FB", "FB", gettext)
        assert "→ Why text" in result


# ---------------------------------------------------------------------------
# AST guard: production code must reference :why
# ---------------------------------------------------------------------------


class TestProductionCodeUsesWhy:
    """Locks the production contract so a future refactor cannot
    silently drop the :why rendering."""

    @pytest.fixture
    def controlspanel_source(self) -> str:
        path = Path(__file__).parent.parent / "katrain" / "gui" / "controlspanel.py"
        return path.read_text(encoding="utf-8")

    def test_format_function_references_why_key(self, controlspanel_source):
        """_format_beginner_hint must construct an i18n key ending in
        ``:why`` and include the resulting text in the output."""
        tree = ast.parse(controlspanel_source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_format_beginner_hint":
                src = ast.unparse(node)
                assert ":why" in src, "production render fn must read :why key"
                assert "→" in src, "production render fn must include the arrow prefix"
                return
        pytest.fail("_format_beginner_hint not found")

    def test_no_why_key_does_not_leak_raw_key(self, controlspanel_source):
        """When the :why key is missing, the render fn must not embed
        the raw ``beginner_hint:...:why`` key in the output text."""
        tree = ast.parse(controlspanel_source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_format_beginner_hint":
                src = ast.unparse(node)
                # The check is `not why.startswith("beginner_hint:")`
                # — the raw-key sentinel.
                assert "startswith('beginner_hint:')" in src
                return
        pytest.fail("_format_beginner_hint not found")
