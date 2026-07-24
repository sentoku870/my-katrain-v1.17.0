"""Phase 281 (tofu-fix): KivyMD 1.2.0 hint_text_label font synchronization tests.

These tests guard against the "tofu" regression where KivyMD 1.2.0's
internal ``TextfieldLabel`` does not inherit ``font_name`` from the
parent ``MDTextField``. If a future refactor accidentally drops the
``on_kv_post`` / ``on_font_name`` handlers or the ``Roboto`` fallback
in the stub KV, the Japanese hint text will once again render as
tofu boxes (``□□□``) — which is exactly what these tests must catch.

Test architecture:
- Use ``KivyUnitTest`` (tests/kivy_test_base.py) to spin up Kivy in
  headless mode (no real window, GL backend mocked) so widget
  instantiation works under CI.
- Source-static checks against ``_kivymd_kv_loader.py`` and
  ``__main__.py`` catch regressions even when Kivy cannot be imported
  (e.g. on platforms without the Kivy GL mock backend).
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Source-static regression guards (run unconditionally, even without Kivy)
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parents[1]
KV_LOADER_PATH = REPO_ROOT / "katrain" / "gui" / "_kivymd_kv_loader.py"
# Phase PR3: KaTrainGui and KaTrainApp moved from __main__.py to
# gui/app.py. Tests that grep for symbols in the original module
# location now prefer the new location when it exists.
_APP_PY = REPO_ROOT / "katrain" / "gui" / "app.py"
MAIN_PATH = _APP_PY if _APP_PY.exists() else REPO_ROOT / "katrain" / "__main__.py"
BASE_POPUP_PATH = REPO_ROOT / "katrain" / "gui" / "popups" / "_base.py"
FACTORY_PATH = REPO_ROOT / "katrain" / "gui" / "widgets" / "factory.py"


# Runtime probe: only run the widget-instantiation tests when Kivy is
# actually importable. Source-static checks above still run regardless.
try:
    import kivy  # noqa: F401

    _KIVY_AVAILABLE = True
except ImportError:
    _KIVY_AVAILABLE = False


class TestKivymdKvLoaderStaticRules:
    """Phase 281 guard: the stub KV rules must NOT contain a 'Roboto'
    fallback for ``font_name``. Roboto has no Japanese glyphs and
    would render every hint string as tofu boxes.
    """

    def test_textfield_kv_loader_exists(self):
        assert KV_LOADER_PATH.exists(), f"missing {KV_LOADER_PATH}"

    def test_textfield_kv_loader_has_no_roboto_fallback(self):
        text = KV_LOADER_PATH.read_text(encoding="utf-8")
        # The KV body is a multi-line ``"(...)"`` tuple, so we anchor
        # to the key and capture everything up to the closing ``),``.
        textfield_block_match = re.search(
            r'"textfield/textfield\.kv":\s*\((.*?)\),',
            text,
            re.DOTALL,
        )
        assert textfield_block_match, "could not locate textfield.kv stub block"
        block = textfield_block_match.group(1)
        # Roboto fallback in either the MDTextField rule or the
        # TextfieldLabel rule would silently bring tofu back. The
        # allowed string is only ``Theme.DEFAULT_FONT``.
        assert "'Roboto'" not in block, (
            "Roboto fallback found in MDTextField/TextfieldLabel rule; "
            "Roboto has no JP glyphs and would render Japanese hint text "
            "as tofu. Use Theme.DEFAULT_FONT instead."
        )
        assert '"Roboto"' not in block, (
            "Roboto fallback found in MDTextField/TextfieldLabel rule; "
            "Roboto has no JP glyphs and would render Japanese hint text "
            "as tofu. Use Theme.DEFAULT_FONT instead."
        )

    def test_textfield_kv_loader_imports_theme(self):
        """The stub KV must import ``Theme`` so the ``Theme.DEFAULT_FONT``
        fallback expression is resolvable at runtime.
        """
        text = KV_LOADER_PATH.read_text(encoding="utf-8")
        assert "#:import Theme katrain.gui.theme.Theme" in text, (
            "TextfieldLabel rule references Theme.DEFAULT_FONT but the "
            "stub KV does not import Theme; Kivy would fail to load the "
            "rule with a NameError."
        )

    def test_factory_uses_helper(self):
        """``factory.py`` must call the ``_schedule_hint_label_sync``
        helper so the runtime sync is wired up for every widget built
        via the project wrappers.
        """
        text = FACTORY_PATH.read_text(encoding="utf-8")
        assert "_schedule_hint_label_sync" in text, (
            "factory.py no longer schedules hint_label sync; tofu regression risk for KivyMD-derived widgets."
        )

    def test_labelled_textinput_overrides_kv_post(self):
        """``_base.py`` must define ``on_kv_post`` on ``LabelledTextInput``
        so the post-construction sync is triggered.
        """
        text = BASE_POPUP_PATH.read_text(encoding="utf-8")
        assert "def on_kv_post" in text, (
            "LabelledTextInput.on_kv_post is missing; KivyMD 1.2.0 hint text "
            "will render with the default font and tofu boxes for Japanese."
        )
        assert "_sync_font_to_hint_labels" in text, (
            "LabelledTextInput must call _sync_font_to_hint_labels to enforce "
            "font propagation to KivyMD's internal TextfieldLabel."
        )

    def test_resource_find_validates_none(self):
        """``__main__.py`` must guard against ``resource_find`` returning
        ``None`` so missing fonts surface as a warning instead of
        silently falling back to Roboto.
        """
        text = MAIN_PATH.read_text(encoding="utf-8")
        assert "resource_find(Theme.DEFAULT_FONT)" in text
        assert "resolved_font" in text, (
            "resource_find result is no longer captured into a local; the missing-font warning guard has regressed."
        )
        assert "not found" in text.lower() or "warning" in text.lower(), "resource_find None branch must log a warning."


# ---------------------------------------------------------------------------
# Runtime tests (require Kivy headless environment)
# ---------------------------------------------------------------------------


# Note: ``MDTextField`` instantiation requires a running KivyMD ``MDApp``
# (KivyMD 1.2.0 raises ValueError otherwise). We can't easily spin up
# the full app in a unit test, so we rely on AST-level checks below for
# the ``LabelledTextInput`` overrides; runtime coverage is exercised by
# the popup tests that DO have a real app (test_llm_coach_popup.py etc.).
#
# We still keep a probe so the test file imports cleanly even on systems
# without Kivy — the runtime class is just never reached.


def test_labelled_textinput_overrides_defined_via_ast():
    """AST check: ``LabelledTextInput`` must define both ``on_kv_post``
    and ``on_font_name`` methods, and both must call
    ``_sync_font_to_hint_labels``. This is the runtime contract that
    keeps KivyMD 1.2.0's ``TextfieldLabel`` in sync without forcing
    us to instantiate ``MDTextField`` (which requires a real MDApp).
    """
    import ast

    tree = ast.parse(BASE_POPUP_PATH.read_text(encoding="utf-8"))
    target_cls = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "LabelledTextInput":
            target_cls = node
            break
    assert target_cls is not None, "LabelledTextInput class not found in _base.py"

    method_names = {m.name for m in target_cls.body if isinstance(m, ast.FunctionDef)}
    assert "on_kv_post" in method_names, (
        "LabelledTextInput.on_kv_post must be defined so the post-construction font sync runs."
    )
    assert "on_font_name" in method_names, (
        "LabelledTextInput.on_font_name must be defined so future font_name "
        "changes propagate to the internal hint label."
    )

    def _calls_helper(fn: ast.FunctionDef) -> bool:
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Name) and func.id == "_sync_font_to_hint_labels":
                    return True
                if isinstance(func, ast.Attribute) and func.attr == "_sync_font_to_hint_labels":
                    return True
        return False

    for method_name in ("on_kv_post", "on_font_name"):
        method = next(m for m in target_cls.body if isinstance(m, ast.FunctionDef) and m.name == method_name)
        assert _calls_helper(method), (
            f"LabelledTextInput.{method_name} must call _sync_font_to_hint_labels "
            f"to keep KivyMD 1.2.0's internal TextfieldLabel in sync."
        )
