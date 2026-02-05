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
        required_methods = [
            "set_config_section",
            "_load_export_settings",
            "_save_export_settings",
            "_save_batch_options",
        ]
        for method in required_methods:
            assert method in method_names, f"KaTrainGui.{method} not found"

    def test_katrain_gui_has_config_manager_init(self):
        """KaTrainGui.__init__でConfigManagerが初期化されている"""
        import katrain

        katrain_pkg_dir = Path(katrain.__file__).parent
        main_py = katrain_pkg_dir / "__main__.py"
        source_code = main_py.read_text(encoding="utf-8")

        # ConfigManagerのインポートと初期化が存在することを確認
        assert "from katrain.gui.managers.config_manager import ConfigManager" in source_code
        assert "self._config_manager = ConfigManager(" in source_code


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
