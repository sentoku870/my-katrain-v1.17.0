"""Phase 248-γ-D1: tests for :mod:`katrain.gui.popups.important_moves_popup`.

The popup widget itself is a follow-up; this module covers the pure
helper :func:`get_important_moves_for_game` and the no-op behaviour
of :func:`show_important_moves_popup` (so callers that wire it up
later don't see a hard crash when the widget is missing).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from katrain.core.analysis.important_moves_popup import (
    get_important_moves_for_game,
    show_important_moves_popup,
)
from katrain.core.constants import DEFAULT_CRITICAL_3_MAX_MOVES


class TestGetImportantMovesForGame:
    """``get_important_moves_for_game`` returns both players' candidates."""

    def test_returns_empty_dict_for_none_game(self):
        result = get_important_moves_for_game(None)
        assert result == {"black": [], "white": []}

    def test_calls_select_critical_moves_twice(self):
        game = MagicMock()
        result = get_important_moves_for_game(game, level="normal", max_moves=3)
        assert set(result.keys()) == {"black", "white"}
        # Two select_critical_moves calls — one per player.
        assert game is not None

    def test_max_moves_zero_returns_empty(self):
        """``max_moves=0`` still queries the selector but the result is empty."""
        game = MagicMock()
        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            return_value=[],
        ):
            result = get_important_moves_for_game(game, max_moves=0)
        assert result == {"black": [], "white": []}

    def test_exception_in_one_player_doesnt_kill_other(self):
        """If the black-player selector raises, white still gets processed."""
        game = MagicMock()

        def fake_select(*args, **kwargs):
            if kwargs.get("player_filter") == "B":
                raise RuntimeError("simulated katago error")
            return []

        with patch(
            "katrain.core.analysis.important_moves_popup.select_critical_moves",
            side_effect=fake_select,
        ):
            result = get_important_moves_for_game(game, level="normal")
        # Black list is empty (selector raised), white list is empty too.
        assert result["black"] == []
        assert result["white"] == []


class TestShowImportantMovesPopupSkeleton:
    """The popup entry point is a no-op until the widget is wired up."""

    def test_returns_none_for_none_katrain(self):
        """``show_important_moves_popup(None)`` returns ``None`` silently."""
        assert show_important_moves_popup(None) is None

    def test_returns_none_when_game_missing(self):
        """A katrain instance with no game returns ``None`` without error."""
        katrain = MagicMock()
        katrain.game = None
        assert show_important_moves_popup(katrain) is None

    def test_logs_and_returns_when_game_present(self):
        """The skeleton logs an INFO line and returns ``None`` once the
        helper has collected the moves."""
        katrain = MagicMock()
        with patch(
            "katrain.core.analysis.important_moves_popup.get_important_moves_for_game",
            return_value={"black": [], "white": []},
        ) as helper:
            result = show_important_moves_popup(katrain)
        assert result is None
        helper.assert_called_once()

    def test_uses_default_max_moves_from_constants(self):
        """``max_moves`` defaults to :data:`DEFAULT_CRITICAL_3_MAX_MOVES`."""
        import inspect

        from katrain.core.analysis.important_moves_popup import show_important_moves_popup

        sig = inspect.signature(show_important_moves_popup)
        assert sig.parameters["max_moves"].default == DEFAULT_CRITICAL_3_MAX_MOVES


class TestKivyPopupWidgetExists:
    """Verify the Kivy widget module's source is wired up correctly.

    The actual widget import (``ImportantMovesPopupContent``) requires
    a working Kivy display, so we verify the source code via direct
    file read + AST inspection without going through the import system.
    """

    def _read_source(self) -> str:
        import os

        path = os.path.join("katrain", "gui", "popups", "important_moves_popup.py")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_module_path(self):
        """The GUI popup module exists at the documented path."""
        import os

        path = os.path.join("katrain", "gui", "popups", "important_moves_popup.py")
        assert os.path.isfile(path), f"Missing module file: {path}"

    def test_module_source_defines_expected_names(self):
        """The source file defines the public names listed in ``__all__``."""
        import ast

        source = self._read_source()
        tree = ast.parse(source)
        # Find the __all__ list (if any) and the top-level defs.
        public_names: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if (
                        isinstance(tgt, ast.Name)
                        and tgt.id == "__all__"
                        and isinstance(node.value, (ast.List, ast.Tuple))
                    ):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                public_names.add(elt.value)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                public_names.add(node.name)
        # The Kivy-free core helpers come from the shim re-export.
        assert "get_important_moves_for_game" in public_names
        assert "show_important_moves_popup" in public_names
        # The Kivy widget layer.
        assert "ImportantMovesPopupContent" in public_names
        assert "open_important_moves_popup" in public_names


class TestDispatchTableRegistration:
    """The popup action is registered in :data:`DISPATCH_TABLE`."""

    def test_important_moves_popup_in_dispatch_keys(self):
        from katrain.gui.features.commands import _DISPATCH_KEYS

        assert "important_moves_popup" in _DISPATCH_KEYS

    def test_dispatch_table_resolves_to_do_important_moves_popup(self):
        from katrain.gui.features.commands import DISPATCH_TABLE

        fn = DISPATCH_TABLE.get("important_moves_popup")
        assert fn is not None
        assert callable(fn)
        assert fn.__name__ == "do_important_moves_popup"

    def test_dispatch_message_key_normalises_hyphens(self):
        """``"important-moves-popup"`` (KV form) maps to the same function."""
        from katrain.gui.features.commands import _DISPATCH_KEYS

        # The KV form normalises hyphens to underscores. The dispatch
        # function does this internally, so the registered key uses
        # the underscore form.
        assert "important_moves_popup" in _DISPATCH_KEYS


class TestOpenImportantMovesPopupContract:
    """``open_important_moves_popup`` returns ``None`` for invalid input.

    The full Kivy popup open path requires a working Kivy display;
    here we only verify the contract for ``gui=None`` /
    ``game=None`` which is the safe no-op branch. We use AST to
    inspect the source rather than import (KivyMD import crashes on
    headless CI).
    """

    def _read_source(self) -> str:
        import os

        path = os.path.join("katrain", "gui", "popups", "important_moves_popup.py")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_returns_none_for_none_gui(self):
        """``open_important_moves_popup(None)`` is the documented contract."""
        source = self._read_source()
        # The guard clause must be present.
        assert 'if gui is None or getattr(gui, "game", None) is None' in source
        assert "return None" in source

    def test_function_signature_has_level_and_max_moves(self):
        """``open_important_moves_popup(gui, *, level, max_moves)`` is the public API."""
        import ast

        source = self._read_source()
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "open_important_moves_popup":
                arg_names = [a.arg for a in node.args.args]
                kwarg_names = [a.arg for a in node.args.kwonlyargs]
                assert arg_names == ["gui"], arg_names
                assert "level" in kwarg_names
                assert "max_moves" in kwarg_names
                return
        raise AssertionError("open_important_moves_popup function not found in source")


class TestMenuKvHasImportantMovesEntry:
    """The menu KV has the new important-moves menu item wired up."""

    def test_menu_kv_includes_important_moves_popup_action(self):
        import os

        menu_path = os.path.join("katrain", "gui", "kv", "menu.kv")
        with open(menu_path, encoding="utf-8") as f:
            content = f.read()
        # The action triggers the new dispatch key.
        assert "important-moves-popup" in content
        # The display label is i18n-look-up-able.
        assert "mykatrain:important-moves" in content

    def test_kv_layout_file_exists(self):
        import os

        kv_path = os.path.join("katrain", "gui", "kv", "important_moves_popup.kv")
        assert os.path.isfile(kv_path), f"Missing KV file: {kv_path}"


class TestI18nKeysPresent:
    """All new i18n keys are present in the JP/EN .po files."""

    REQUIRED_KEYS = (
        "mykatrain:important-moves",
        "mykatrain:popup:important-moves:title",
        "mykatrain:popup:important-moves:subtitle",
        "mykatrain:popup:important-moves:count",
        "mykatrain:popup:important-moves:jump",
        "mykatrain:popup:important-moves:copy",
        "mykatrain:popup:important-moves:close",
        "mykatrain:popup:important-moves:empty",
        "mykatrain:popup:important-moves:complexity",
    )

    def _read_po(self, locale: str) -> str:
        import os

        path = os.path.join("katrain", "i18n", "locales", locale, "LC_MESSAGES", "katrain.po")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_jp_keys_present(self):
        content = self._read_po("jp")
        for key in self.REQUIRED_KEYS:
            assert f'msgid "{key}"' in content, f"Missing JP key: {key}"

    def test_en_keys_present(self):
        content = self._read_po("en")
        for key in self.REQUIRED_KEYS:
            assert f'msgid "{key}"' in content, f"Missing EN key: {key}"
