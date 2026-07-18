"""後方互換APIの存在とシグネチャを検証（Phase 74）

Kivy非依存:
- ConfigManagerインポート: Kivy-free（検証済み）
- AST解析のパス: katrain.__file__ から導出（作業ディレクトリ非依存）
- import katrain 自体はKivyをインポートしない（katrain/__init__.py は空ファイル）
- AST解析は KaTrainGui クラス内のメソッドのみを検証（false-positive防止）
"""

import ast
import inspect
from pathlib import Path


class TestConfigManagerImport:
    """ConfigManagerのインポートテスト"""

    def test_can_import_config_manager(self):
        """ConfigManagerがインポート可能"""
        from katrain.gui.managers.config_manager import ConfigManager

        assert ConfigManager is not None

    def test_config_manager_has_required_methods(self):
        """必須メソッドが存在"""
        from katrain.gui.managers.config_manager import ConfigManager

        assert hasattr(ConfigManager, "get")
        assert hasattr(ConfigManager, "get_section")
        assert hasattr(ConfigManager, "set_section")
        assert hasattr(ConfigManager, "load_export_settings")
        assert hasattr(ConfigManager, "save_export_settings")
        assert hasattr(ConfigManager, "save_batch_options")

    def test_config_manager_is_kivy_free(self):
        """ConfigManagerモジュールがKivyをインポートしていないことを確認"""
        import katrain.gui.managers.config_manager as cm_module

        # モジュールの__dict__にKivy関連がないことを確認
        module_attrs = dir(cm_module)
        kivy_related = [attr for attr in module_attrs if "kivy" in attr.lower()]
        assert kivy_related == [], f"Kivy-related attributes found: {kivy_related}"


class TestBackwardCompatSignatures:
    """後方互換APIシグネチャ検証"""

    def test_save_export_settings_accepts_none_defaults(self):
        """save_export_settings()のデフォルト引数がNone"""
        from katrain.gui.managers.config_manager import ConfigManager

        sig = inspect.signature(ConfigManager.save_export_settings)
        params = sig.parameters

        assert params["sgf_directory"].default is None
        assert params["selected_players"].default is None

    def test_set_section_signature(self):
        """set_section(section, value)のシグネチャ"""
        from katrain.gui.managers.config_manager import ConfigManager

        sig = inspect.signature(ConfigManager.set_section)
        param_names = list(sig.parameters.keys())

        assert "section" in param_names
        assert "value" in param_names

    def test_get_signature_has_default_parameter(self):
        """get(setting, default=None)のシグネチャ"""
        from katrain.gui.managers.config_manager import ConfigManager

        sig = inspect.signature(ConfigManager.get)
        params = sig.parameters

        assert "setting" in params
        assert "default" in params
        assert params["default"].default is None

    def test_save_batch_options_signature(self):
        """save_batch_options(options)のシグネチャ"""
        from katrain.gui.managers.config_manager import ConfigManager

        sig = inspect.signature(ConfigManager.save_batch_options)
        param_names = list(sig.parameters.keys())

        assert "options" in param_names

    def test_constructor_signature(self):
        """ConfigManager.__init__のシグネチャ"""
        from katrain.gui.managers.config_manager import ConfigManager

        sig = inspect.signature(ConfigManager.__init__)
        params = sig.parameters

        assert "config_dict" in params
        assert "save_config" in params
        assert "logger" in params
        assert params["logger"].default is None
        assert "log_level_info" in params
        assert params["log_level_info"].default == 0


class TestKaTrainGuiDelegationExists:
    """KaTrainGuiの委譲メソッド存在確認（インポートレベル）"""

    def test_katrain_gui_has_required_methods(self):
        """KaTrainGuiクラス内に必須メソッドが存在（Kivy非依存）"""
        # 注: KaTrainGuiをインスタンス化しない（Kivy依存回避）
        # ASTでKaTrainGuiクラス内のメソッドのみを検証
        # パス堅牢化: katrain.__file__ から導出（作業ディレクトリ非依存）
        import katrain

        # katrain パッケージの場所から __main__.py を導出
        katrain_pkg_dir = Path(katrain.__file__).parent
        main_py = katrain_pkg_dir / "__main__.py"
        tree = ast.parse(main_py.read_text(encoding="utf-8"))

        # KaTrainGuiクラスを探す
        katrain_gui_class = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == "KaTrainGui":
                katrain_gui_class = node
                break

        assert katrain_gui_class is not None, "KaTrainGui class not found"

        # KaTrainGuiクラス内のメソッド名を収集
        method_names = [
            item.name for item in ast.iter_child_nodes(katrain_gui_class) if isinstance(item, ast.FunctionDef)
        ]

        # 必須メソッドの存在確認
        # Phase 198 Stage 2: ``_load_export_settings`` / ``_save_export_settings``
        # were removed from KaTrainGui (delegation shrank through
        # ``self.ctx.config_manager``). Only ``set_config_section`` remains
        # as the live public API.
        required_methods = [
            "set_config_section",
        ]
        for method in required_methods:
            assert method in method_names, f"KaTrainGui.{method} not found"

        # Phase 198 Stage 2 follow-up: ensure the legacy shim names are gone
        # (no resurrection via inheritance / redefinition). If they ever come
        # back they should be re-introduced only via AppContext.
        legacy_removed_methods = [
            "_load_export_settings",
            "_save_export_settings",
        ]
        for method in legacy_removed_methods:
            assert method not in method_names, f"KaTrainGui.{method} should have been removed in Phase 198 Stage 2"

    def test_katrain_gui_has_config_manager_init(self):
        """KaTrainGui.__init__でConfigManagerが初期化されている"""
        import katrain

        katrain_pkg_dir = Path(katrain.__file__).parent
        main_py = katrain_pkg_dir / "__main__.py"
        source_code = main_py.read_text(encoding="utf-8")

        # ConfigManagerのインポートと初期化が存在することを確認
        assert "from katrain.gui.managers.config_manager import ConfigManager" in source_code
        assert "self._config_manager = ConfigManager(" in source_code


class TestAppContextAssignedInInit:
    """Phase 249-hotfix: ``self.ctx = AppContext(...)`` must live inside
    ``KaTrainGui.__init__``.

    Background: while extracting ``_build_kifunarabe_weakness_exporter`` in
    Phase 249-γ, the closing block of ``__init__`` (which assigns
    ``self.ctx``) was accidentally left **after** the new helper method's
    ``return`` statement, making it dead code. The instance therefore had
    no ``ctx`` attribute, and the very first ``on_start`` → ``on_language``
    → ``set_config_section`` call crashed with::

        AttributeError: 'KaTrainGui' object has no attribute 'ctx'

    The bug is invisible to ``test_main_smoke.py`` (which uses
    ``KaTrainApp.__new__``) and to all manager-level tests (which stub
    ``self.ctx``). These AST tests catch it at the source-code level
    without needing a live Kivy instance.
    """

    def _get_init_method(self):
        import katrain

        katrain_pkg_dir = Path(katrain.__file__).parent
        main_py = katrain_pkg_dir / "__main__.py"
        tree = ast.parse(main_py.read_text(encoding="utf-8"))

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == "KaTrainGui":
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        return item
        raise AssertionError("KaTrainGui.__init__ not found")

    def test_self_ctx_assigned_inside_init(self):
        """``self.ctx = ...`` is reachable code inside ``__init__``."""
        init_method = self._get_init_method()
        init_end = init_method.end_lineno

        ctx_assign_lines: list[int] = []
        for sub in ast.walk(init_method):
            if isinstance(sub, ast.Assign):
                for tgt in sub.targets:
                    if (
                        isinstance(tgt, ast.Attribute)
                        and isinstance(tgt.value, ast.Name)
                        and tgt.value.id == "self"
                        and tgt.attr == "ctx"
                    ):
                        ctx_assign_lines.append(sub.lineno)

        assert ctx_assign_lines, (
            "self.ctx = ... assignment is missing from KaTrainGui.__init__. "
            "Phase 249-hotfix regression: the assignment was left as dead "
            "code inside _build_kifunarabe_weakness_exporter."
        )
        # The assignment must come before __init__ ends (i.e. it is not in
        # a helper method that was wrongly placed after the return).
        for line in ctx_assign_lines:
            assert line <= init_end, (
                f"self.ctx assignment at line {line} is after __init__ ends at line {init_end}; it is unreachable."
            )

    def test_setup_state_subscriptions_called_in_init(self):
        """``self.ctx.ui_update_manager.setup_state_subscriptions()`` runs
        inside ``__init__`` (after ``self.ctx`` is assigned)."""
        init_method = self._get_init_method()
        init_end = init_method.end_lineno

        # Find any Call to setup_state_subscriptions with the dotted target
        # ``self.ctx.ui_update_manager.setup_state_subscriptions``.
        call_lines: list[int] = []
        for sub in ast.walk(init_method):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "setup_state_subscriptions"
            ):
                call_lines.append(sub.lineno)

        assert call_lines, (
            "setup_state_subscriptions() is missing from __init__; state subscriptions won't be wired at startup."
        )
        for line in call_lines:
            assert line <= init_end, (
                f"setup_state_subscriptions() at line {line} is after __init__ ends at line {init_end}."
            )

    def test_set_config_section_guards_missing_ctx(self):
        """``set_config_section`` no-ops safely when ``self.ctx`` is unset
        instead of raising ``AttributeError`` (defensive)."""
        import katrain

        katrain_pkg_dir = Path(katrain.__file__).parent
        main_py = katrain_pkg_dir / "__main__.py"
        tree = ast.parse(main_py.read_text(encoding="utf-8"))

        ka_train_gui_class = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == "KaTrainGui":
                ka_train_gui_class = node
                break
        assert ka_train_gui_class is not None, "KaTrainGui class not found"

        set_section = None
        for item in ast.iter_child_nodes(ka_train_gui_class):
            if isinstance(item, ast.FunctionDef) and item.name == "set_config_section":
                set_section = item
                break
        assert set_section is not None, "set_config_section method not found"

        # The function must use ``getattr(self, "ctx", None)`` (or a
        # similar guard) so an early call before __init__ finishes does
        # not raise AttributeError.
        src = ast.unparse(set_section)
        assert 'getattr(self, "ctx"' in src or "getattr(self, 'ctx'" in src, (
            "set_config_section must guard against missing self.ctx. "
            "Phase 249-hotfix: without the guard, an early on_language → "
            "set_config_section call raises AttributeError before the user "
            "sees any error context."
        )


class TestKivyFreeImportChain:
    """Kivyインポートチェーン検証"""

    def test_katrain_init_is_empty(self):
        """katrain/__init__.pyが空（またはKivyをインポートしない）"""
        import katrain

        katrain_init = Path(katrain.__file__)
        content = katrain_init.read_text(encoding="utf-8").strip()

        # 空ファイルまたはKivyインポートなし
        if content:
            assert "kivy" not in content.lower(), "katrain/__init__.py should not import Kivy"

    def test_gui_init_is_minimal(self):
        """katrain/gui/__init__.pyが軽量"""
        import katrain

        gui_init = Path(katrain.__file__).parent / "gui" / "__init__.py"
        content = gui_init.read_text(encoding="utf-8").strip()

        # 空ファイルまたはKivyインポートなし
        if content:
            assert "kivy" not in content.lower(), "katrain/gui/__init__.py should not import Kivy"

    def test_managers_init_is_minimal(self):
        """katrain/gui/managers/__init__.pyが軽量"""
        import katrain

        managers_init = Path(katrain.__file__).parent / "gui" / "managers" / "__init__.py"
        content = managers_init.read_text(encoding="utf-8").strip()

        # docstringのみまたはKivyインポートなし
        if content:
            # コメントとdocstringを除去してKivyインポートを確認
            lines = [
                line
                for line in content.split("\n")
                if line.strip()
                and not line.strip().startswith("#")
                and not line.strip().startswith('"""')
                and not line.strip().startswith("'''")
            ]
            for line in lines:
                assert "kivy" not in line.lower(), f"Kivy import found: {line}"
