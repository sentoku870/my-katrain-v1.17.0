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


class TestBoardKvNavButtonCaptions:
    """Phase 287-F: the KV file must declare captions for every nav button."""

    def test_every_nav_button_has_caption_and_tooltip(self):
        src = Path("katrain/gui/kv/board.kv").read_text(encoding="utf-8")
        # Each of the 9 nav buttons must declare caption_text + tooltip_text.
        # The KIF "SGF", "パス", "黒優先", "白優先" buttons in the left half
        # already have text labels, so they are not subject to this rule.
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
        # Captions are shorter, so we just check that 9 NavIconButtonWithCaption
        # blocks appear (one per nav button).
        assert src.count("NavIconButtonWithCaption:") >= 9, "Expected >= 9 NavIconButtonWithCaption entries"

    def test_caption_text_and_tooltip_text_used(self):
        """Phase 287-F: the two new properties must be referenced."""
        src = Path("katrain/gui/kv/board.kv").read_text(encoding="utf-8")
        assert "caption_text:" in src
        assert "tooltip_text:" in src

    def test_naviconbutton_template_mixes_tooltipmixin(self):
        """Phase 287-F fix: <NavIconButton@...> must include TooltipMixin so
        the tooltip_text property actually triggers long-press tooltips."""
        src = Path("katrain/gui/kv/board.kv").read_text(encoding="utf-8")
        assert "TooltipMixin" in src, (
            "NavIconButton template must mix in TooltipMixin; otherwise tooltip_text silently does nothing."
        )

    def test_naviconbuttonwithcaption_uses_python_class(self):
        """Phase 287-F fix: <NavIconButtonWithCaption> must reference the
        Python class (not @BoxLayout) so Kivy properties resolve."""
        src = Path("katrain/gui/kv/board.kv").read_text(encoding="utf-8")
        # Old form was <NavIconButtonWithCaption@BoxLayout>: which made
        # root.caption_text fail with AttributeError. The fix replaces
        # it with <NavIconButtonWithCaption>: (Python class).
        assert "<NavIconButtonWithCaption@BoxLayout>:" not in src
        assert "<NavIconButtonWithCaption>:" in src

    def test_naviconbuttonwithcaption_class_declares_properties(self):
        """Phase 287-F fix: the Python class must declare caption_text,
        tooltip_text, icon, color as Kivy properties."""
        import ast
        from pathlib import Path

        src = Path("katrain/gui/widgets/nav_icon_caption.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        # Look for class NavIconButtonWithCaption with the 4 properties.
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "NavIconButtonWithCaption":
                prop_names: set[str] = set()
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name) and isinstance(stmt.value, ast.Call):
                                prop_names.add(target.id)
                assert {"caption_text", "tooltip_text", "icon", "color"} <= prop_names, (
                    f"NavIconButtonWithCaption must declare caption_text/tooltip_text/icon/color "
                    f"as Kivy properties; got {prop_names}"
                )
                return
        raise AssertionError("NavIconButtonWithCaption class not found")
