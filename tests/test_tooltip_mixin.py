"""Static checks for the TooltipMixin contract (Phase 287-F).

The TooltipMixin lives in ``katrain.gui.kivyutils.mixins`` and uses
Kivy's Clock + touch system at runtime, which our headless CI cannot
exercise. We instead verify the API contract via AST inspection so a
future refactor that breaks the contract (e.g. renames
``tooltip_text``) is caught.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _load_mixins_tree() -> ast.Module:
    return ast.parse(Path("katrain/gui/kivyutils/mixins.py").read_text(encoding="utf-8"))


class TestTooltipMixinContract:
    """Phase 287-F: TooltipMixin public surface."""

    def test_class_exists(self):
        tree = _load_mixins_tree()
        names = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
        assert "TooltipMixin" in names

    def test_required_methods_present(self):
        tree = _load_mixins_tree()
        for cls in tree.body:
            if isinstance(cls, ast.ClassDef) and cls.name == "TooltipMixin":
                methods = {m.name for m in cls.body if isinstance(m, ast.FunctionDef)}
                assert methods >= {
                    "__init__",
                    "on_touch_down",
                    "on_touch_up",
                    "_cancel_tooltip",
                    "_show_tooltip",
                    "_dismiss_tooltip",
                }, f"Missing methods: {methods}"
                return
        raise AssertionError("TooltipMixin not found")

    def test_tooltip_text_and_delay_are_string_and_numeric_properties(self):
        tree = _load_mixins_tree()
        for cls in tree.body:
            if isinstance(cls, ast.ClassDef) and cls.name == "TooltipMixin":
                # Kivy properties are declared as class-level assignments
                # of the form ``name = PropertyType(...)``. Collect those.
                properties: dict[str, ast.Call] = {}
                for stmt in cls.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name) and isinstance(stmt.value, ast.Call):
                                properties[target.id] = stmt.value
                assert "tooltip_text" in properties, "tooltip_text property missing"
                assert "tooltip_delay" in properties, "tooltip_delay property missing"
                text_fn = ast.unparse(properties["tooltip_text"].func)
                delay_fn = ast.unparse(properties["tooltip_delay"].func)
                assert "StringProperty" in text_fn, f"tooltip_text must use StringProperty, got {text_fn}"
                assert "NumericProperty" in delay_fn, f"tooltip_delay must use NumericProperty, got {delay_fn}"
                return
        raise AssertionError("TooltipMixin not found")

    def test_on_touch_down_schedules_timer_when_text_set(self):
        """The implementation must guard scheduling on tooltip_text."""
        tree = _load_mixins_tree()
        for cls in tree.body:
            if isinstance(cls, ast.ClassDef) and cls.name == "TooltipMixin":
                for stmt in cls.body:
                    if isinstance(stmt, ast.FunctionDef) and stmt.name == "on_touch_down":
                        src = ast.unparse(stmt)
                        assert "tooltip_text" in src, "on_touch_down must check tooltip_text"
                        assert "Clock.schedule_once" in src, "on_touch_down must schedule the tooltip"
                        return
        raise AssertionError("on_touch_down not found")

    def test_on_touch_up_cancels_timer(self):
        tree = _load_mixins_tree()
        for cls in tree.body:
            if isinstance(cls, ast.ClassDef) and cls.name == "TooltipMixin":
                for stmt in cls.body:
                    if isinstance(stmt, ast.FunctionDef) and stmt.name == "on_touch_up":
                        src = ast.unparse(stmt)
                        assert "_cancel_tooltip" in src, "on_touch_up must call _cancel_tooltip"
                        assert "_dismiss_tooltip" in src, "on_touch_up must call _dismiss_tooltip"
                        return
        raise AssertionError("on_touch_up not found")


class TestBoardKvNavButtons:
    """Phase 287-H (revert): the KV file uses bare NavIconButton for every
    bottom-bar nav button. Captions live only as i18n tooltip strings,
    surfaced by the TooltipMixin long-press handler.
    """

    def test_every_nav_button_has_tooltip(self):
        src = Path("katrain/gui/kv/board.kv").read_text(encoding="utf-8")
        nav_buttons = [
            "prev-mistake",
            "first-move",
            "prev-10",
            "prev-1",
            "next-1",
            "next-10",
            "last-move",
            "next-mistake",
            "rotate",
        ]
        for key in nav_buttons:
            assert f"ui:tooltip:{key}" in src, f"Missing tooltip key ui:tooltip:{key}"

    def test_tooltip_text_used_by_nav_buttons(self):
        """Phase 287-H (revert): caption_text is gone; tooltip_text remains."""
        src = Path("katrain/gui/kv/board.kv").read_text(encoding="utf-8")
        assert "tooltip_text:" in src
        # caption_text is no longer wired into the bottom-bar nav buttons
        # (reverted in Phase 287-H). We tolerate the key being absent or
        # only referenced from translated strings.
        assert "NavIconButtonWithCaption" not in src, (
            "NavIconButtonWithCaption was reverted in Phase 287-H; the bare "
            "NavIconButton (icon + tooltip only) is used instead."
        )

    def test_naviconbutton_template_mixes_tooltipmixin(self):
        """Phase 287-F: <NavIconButton@...> must include TooltipMixin so
        the tooltip_text property actually triggers long-press tooltips."""
        src = Path("katrain/gui/kv/board.kv").read_text(encoding="utf-8")
        assert "TooltipMixin" in src, (
            "NavIconButton template must mix in TooltipMixin; otherwise tooltip_text silently does nothing."
        )
