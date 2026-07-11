"""Phase 172/173: Tests for the command DISPATCH_TABLE.

These tests guarantee:
1. Every ``do_*`` function exported from ``katrain.gui.features.commands.*``
   is registered in ``DISPATCH_TABLE``.
2. Every key in ``DISPATCH_TABLE`` resolves to a callable.
3. ``dispatch`` routes a message to the right function (smoke test via
   mocks so we don't need a live KaTrainGui).
4. ``-`` and ``_`` separators are normalised.
5. Unknown messages raise ``KeyError``.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

from katrain.gui.features.commands import (
    DISPATCH_TABLE,
    analyze_commands,
    dispatch,
    export_commands,
    game_commands,
    popup_commands,
)


def _all_command_modules():
    return (analyze_commands, export_commands, game_commands, popup_commands)


def _func_is_registered(func_name: str) -> bool:
    """True if a ``do_<foo>`` function is reachable through dispatch.

    Covers two cases:
    * Direct: ``do_undo`` → key ``undo`` is in ``_DISPATCH_KEYS``.
    * Override: ``do_start_selfplay`` → key ``selfplay_setup`` via
      ``_KEY_TO_FUNC_NAME``.
    """
    from katrain.gui.features.commands import (  # noqa: PLC0415
        _DISPATCH_KEYS,
        _KEY_TO_FUNC_NAME,
    )

    if not func_name.startswith("do_"):
        return False
    key = func_name[len("do_") :]
    if key in _DISPATCH_KEYS:
        return True
    return func_name in _KEY_TO_FUNC_NAME.values()


def _all_do_funcs():
    """Yield (module, name) for every public ``do_*`` callable."""
    for mod in _all_command_modules():
        for name in dir(mod):
            if name.startswith("do_") and callable(getattr(mod, name, None)):
                yield mod, name


class TestDispatchTableCoverage:
    def test_all_do_functions_registered(self) -> None:
        """Every ``do_*`` function in commands/ is reachable via DISPATCH_TABLE."""
        missing = []
        for mod, name in _all_do_funcs():
            if not _func_is_registered(name):
                missing.append(f"{mod.__name__}.{name}")
        assert missing == [], f"Unregistered commands: {missing}"

    def test_all_keys_resolve_to_callables(self) -> None:
        for key, fn in DISPATCH_TABLE.items():
            assert callable(fn), f"DISPATCH_TABLE[{key!r}] is not callable"

    def test_keys_are_unique(self) -> None:
        keys = list(DISPATCH_TABLE.keys())
        assert len(keys) == len(set(keys)), "Duplicate keys in DISPATCH_TABLE"

    def test_table_size_is_stable(self) -> None:
        """Guards against accidental deletion of registered commands.

        If you intentionally remove a command, update both this number
        and the command's tests/usage together.
        """
        assert len(DISPATCH_TABLE) >= 35, f"DISPATCH_TABLE shrank unexpectedly: {len(DISPATCH_TABLE)} entries"


class TestDispatchFunction:
    def test_dash_normalised_to_underscore(self, monkeypatch: pytest.MonkeyPatch) -> None:
        spy = MagicMock()
        monkeypatch.setattr(analyze_commands, "do_analyze_extra", spy)
        ctx = MagicMock()
        # The dash form must resolve the same as the underscore form.
        dispatch(ctx, "analyze-extra", "game")
        spy.assert_called_once_with(ctx, "game")

    def test_underscore_form_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        spy = MagicMock()
        monkeypatch.setattr(analyze_commands, "do_redo", spy)
        ctx = MagicMock()
        dispatch(ctx, "redo", 3)
        spy.assert_called_once_with(ctx, 3)

    def test_extra_args_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        spy = MagicMock()
        monkeypatch.setattr(popup_commands, "do_new_game_popup", spy)
        ctx = MagicMock()
        dispatch(ctx, "new-game-popup")  # popup action (no extra args)
        spy.assert_called_once_with(ctx)

    def test_extra_kwargs_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        spy = MagicMock()
        monkeypatch.setattr(analyze_commands, "do_analyze_extra", spy)
        ctx = MagicMock()
        dispatch(ctx, "analyze-extra", "sweep", visits=100, mistakes_only=True)
        spy.assert_called_once_with(ctx, "sweep", visits=100, mistakes_only=True)

    def test_unknown_message_raises_keyerror(self) -> None:
        ctx = MagicMock()
        with pytest.raises(KeyError):
            dispatch(ctx, "this-action-does-not-exist")


class TestMessageWireFormats:
    """Sanity-check that the message names match the legacy menu/KV strings.

    These come from real call sites (Kivy menu, keyboard shortcuts, KV
    bindings, message_loop_manager). If a name is renamed, this catches
    it before runtime.
    """

    EXPECTED_KEYS = {
        # menu.kv, board.kv (root.katrain("...") form, normalised internally)
        "open_recent_sgf",  # sent as "open-recent-sgf"
        "new_game_popup",  # sent as "new-game-popup"
        "save_game_as_popup",
        "analyze_sgf_popup",
        "timer_popup",
        "teacher_popup",
        "ai_popup",
        "config_popup",
        "mykatrain_settings_popup",  # sent as "mykatrain-settings-popup"
        "batch_analyze_popup",
        "diagnostics_popup",
        # board.kv (underscore form already)
        "undo",
        "redo",
        "find_mistake",  # sent as "find-mistake"
        "rotate",
        "insert_mode",
        "reset_analysis",
        "resign",
        "prev_important",
        "next_important",
        "ai_move",
        "play",
        "switch_branch",
        "selfplay_setup",
        "select_box",
        "tsumego_frame",
        "analyze_extra",
        # engine recovery popup (handled by PopupManager, not via menu)
        "engine_recovery_popup",
        # shortcuts (keyboard_manager.py)
        "save_game",
        "open_latest_report",
        "open_output_folder",
        "export_karte",
        "export_summary",
        "export_summary_ui",
    }

    def test_expected_message_keys_present(self) -> None:
        for key in self.EXPECTED_KEYS:
            assert key in DISPATCH_TABLE, f"Missing key: {key}"

    def test_dispatch_keys_use_underscore_form(self) -> None:
        """No key in DISPATCH_TABLE should contain a dash; they must be normalised."""
        for key in DISPATCH_TABLE:
            assert "-" not in key, f"DISPATCH_TABLE key {key!r} should be dash-free"

    def test_signatures_take_ctx_as_first_arg(self) -> None:
        """All registered callables must be ``do_*(ctx, ...)`` so dispatch
        forwards the GUI correctly.
        """
        bad = []
        for key, fn in DISPATCH_TABLE.items():
            try:
                params = list(inspect.signature(fn).parameters)
            except (TypeError, ValueError):
                # C-objects / builtins without signatures; skip
                continue
            if not params:
                bad.append(key)
        assert bad == [], f"Functions with no positional args: {bad}"


class TestRemovedWrappers:
    """The 34 ``_do_*`` wrapper methods that used to live on KaTrainGui
    must NOT exist anymore. We verify this without instantiating the GUI
    (it pulls in Kivy) by parsing the source.
    """

    # 33 message names reachable through the message queue + "switch_branch"
    # flows through the same dispatcher. _do_mykatrain_settings_popup,
    # _do_export_karte etc. have been replaced by ``commands.DISPATCH_TABLE``
    # entries. These are the names that used to exist as wrappers and must
    # be gone from the GUI class body.
    EXPECTED_ABSENT_WRAPPERS = {
        "_do_new_game",
        "_do_insert_mode",
        "_do_ai_move",
        "_do_undo",
        "_do_reset_analysis",
        "_do_resign",
        "_do_redo",
        "_do_rotate",
        "_do_find_mistake",
        "_do_prev_important",
        "_do_next_important",
        "_do_switch_branch",
        "_do_play",
        "_do_analyze_extra",
        "_do_selfplay_setup",
        "_do_select_box",
        "_do_new_game_popup",
        "_do_timer_popup",
        "_do_teacher_popup",
        "_do_config_popup",
        "_do_ai_popup",
        "_do_engine_recovery_popup",
        "_do_tsumego_frame",
        "_do_analyze_sgf_popup",
        "_do_open_recent_sgf",
        "_do_save_game",
        "_do_save_game_as_popup",
        "_do_export_karte",
        "_do_open_latest_report",
        "_do_open_output_folder",
        "_do_export_summary",
        "_do_export_summary_ui",
        "_do_mykatrain_settings_popup",
        "_do_batch_analyze_popup",
        "_do_diagnostics_popup",
    }

    def test_were_removed_from_kstraingui(self) -> None:
        """AST scan of __main__.py: no method body for any _do_* wrapper."""
        import ast
        from pathlib import Path

        from katrain import __file__ as _init

        main_path = Path(_init).parent / "__main__.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"))

        found_in_class = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == "KaTrainGui":
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        found_in_class.add(item.name)

        survivors = self.EXPECTED_ABSENT_WRAPPERS & found_in_class
        assert not survivors, f"_do_* wrappers still present in KaTrainGui: {sorted(survivors)}"

    def test_do_update_state_is_kept(self) -> None:
        """``_do_update_state`` is intentionally retained (called by
        message_loop_manager directly to avoid re-queueing)."""
        import ast
        from pathlib import Path

        from katrain import __file__ as _init

        main_path = Path(_init).parent / "__main__.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"))

        has_do_update = False
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == "KaTrainGui":
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "_do_update_state":
                        has_do_update = True
        assert has_do_update, "_do_update_state was removed but message_loop_manager still needs it"


class TestCommandsDoNotImportKivyAtLoad:
    """Phase 173: regression test for CI exit-102.

    The CI runner image's ``/home/runner/.kivy`` directory is created
    the first time Kivy's ``__init__.py`` runs, and reused on
    subsequent jobs. When pytest-xdist (or any other sequential
    layer, including the smoke-test-then-full-run workflow)
    triggers two simultaneous imports of ``katrain.gui.features.commands``
    in different processes, the second one hits ``FileExistsError``
    on ``os.mkdir('/home/runner/.kivy')`` and pytest's controller
    surfaces that as exit code 102 mid-collection.

    Root cause was ``from kivy.clock import Clock`` at module level
    inside ``katrain/gui/features/commands/game_commands.py``. Every
    command-dispatching path (``__call__``, ``message_loop_manager``,
    xdist workers, test collection that imports commands for
    refactoring assertions) loads this module, which in turn loaded
    Kivy.

    These tests assert that ``commands`` package modules can be
    imported without Kivy's lazy ``os.mkdir`` of user dirs firing.
    Kivy can still be imported lazily inside individual ``do_*``
    functions where needed.
    """

    def _import_commands_with_mkdir_prohibited(self) -> None:
        import os

        real_mkdir = os.mkdir

        def fake_mkdir(*args, **kwargs):
            path = args[0] if args else kwargs.get("name")
            if isinstance(path, str) and "/.kivy" in path:
                raise AssertionError(f"Kivy mkdir fired during commands import: {path!r}")
            return real_mkdir(*args, **kwargs)

        os.mkdir = fake_mkdir
        try:
            from katrain.gui.features.commands import (  # noqa: F401
                DISPATCH_TABLE,
                analyze_commands,
                export_commands,
                game_commands,
                popup_commands,
            )
        finally:
            os.mkdir = real_mkdir

    def test_game_commands_module_does_not_import_kivy(self) -> None:
        """Phase 173 root-cause fix: ``game_commands`` previously did
        ``from kivy.clock import Clock`` at module level. Verify the
        import statement has been moved out of module scope so pytest
        collection does not pull in Kivy as a side effect.
        """
        import ast
        from pathlib import Path

        gc_path = Path(game_commands.__file__)
        source = gc_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        module_level_kivy_imports: list[str] = []
        for stmt in tree.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    if alias.name.startswith("kivy"):
                        module_level_kivy_imports.append(alias.name)
            elif isinstance(stmt, ast.ImportFrom) and stmt.module and stmt.module.startswith("kivy"):
                module_level_kivy_imports.append(stmt.module)
        assert module_level_kivy_imports == [], (
            f"game_commands.py imports Kivy at module level: "
            f"{module_level_kivy_imports}; this triggers mkdir('~/.kivy') "
            f"as a side effect and causes exit 102 in CI when the second "
            f"job hits a runner with ~/.kivy already populated."
        )

    def test_commands_modules_import_without_kivy_mkdir(self) -> None:
        """End-to-end: importing the four command submodules plus the
        DISPATCH_TABLE itself must not trigger Kivy's lazy mkdir of
        ``~/.kivy/mods``. Without this fix pytest collection dies with
        ``FileExistsError`` on the GitHub Actions Ubuntu-24.04 runner.
        """
        # The fixture monkey-patches os.mkdir to raise if Kivy fires.
        self._import_commands_with_mkdir_prohibited()
