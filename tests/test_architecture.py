"""Architecture validation tests for KaTrain.

PR #114: Phase B1 - Architecture validation tests (v5)

v5改善:
- TYPE_CHECKING検出: `import typing as t; if t.TYPE_CHECKING:` パターン対応
- 相対インポートテスト: 期待される解決結果を明示的にアサート
- 副作用検出: Assign/AnnAssign内の関数呼び出しも検出
"""

import ast
from pathlib import Path
from typing import List, Set, Tuple
import json

import pytest


# テストファイルからプロジェクトルートを計算（cwdに依存しない）
_TEST_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TEST_DIR.parent  # katrain-1.17.0/


class RuntimeImportCollector(ast.NodeVisitor):
    """Collects module-level runtime imports, skipping TYPE_CHECKING blocks.

    v5改善:
    - typingモジュールのエイリアス追跡（`import typing as t`対応）
    - TYPE_CHECKINGのインポート元を追跡
    - 相対インポートを適切に処理
    - 関数/メソッド内の遅延インポートはスキップ（モジュールレベルのみ検出）
    """

    def __init__(self, module_package: str = ""):
        self.runtime_imports: list[str] = []
        self._module_package = module_package  # 相対インポート解決用
        # TYPE_CHECKINGとしてインポートされた名前を追跡
        self._type_checking_names: Set[str] = set()
        # typingモジュールのエイリアスを追跡（v5追加）
        self._typing_aliases: Set[str] = {"typing"}  # デフォルトで"typing"を含む
        # 関数/クラス内にいるかどうかのカウンタ
        self._function_depth: int = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """関数定義に入る"""
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """非同期関数定義に入る"""
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """from ... import文を収集（モジュールレベルのみ）"""
        # typing.TYPE_CHECKINGのインポートを追跡（常に実行）
        if node.module == "typing":
            for alias in node.names:
                if alias.name == "TYPE_CHECKING":
                    imported_name = alias.asname or alias.name
                    self._type_checking_names.add(imported_name)

        # 関数内の遅延インポートはスキップ
        if self._function_depth > 0:
            return

        # ランタイムインポートを収集
        if node.module:
            # 相対インポートの場合、パッケージを解決
            if node.level > 0 and self._module_package:
                resolved = self._resolve_relative_import(node.module, node.level)
                if resolved:
                    self.runtime_imports.append(resolved)
            else:
                # 絶対インポート
                self.runtime_imports.append(node.module)

    def _resolve_relative_import(self, module: str, level: int) -> str:
        """相対インポートを絶対パスに解決

        Args:
            module: インポート対象モジュール（例: "models"）
            level: ドットの数（1 = ".", 2 = ".."）

        Returns:
            解決された絶対パス（例: "katrain.core.analysis.models"）
        """
        parts = self._module_package.split(".")
        if level > len(parts):
            return ""  # 親パッケージを超える相対インポートは解決不可

        # level=1: 同じパッケージ、level=2: 親パッケージ
        base_parts = parts[: -level + 1] if level > 1 else parts
        base = ".".join(base_parts)
        return f"{base}.{module}" if module else base

    def visit_Import(self, node: ast.Import) -> None:
        """import文を収集（モジュールレベルのみ）"""
        for alias in node.names:
            # typingモジュールのエイリアスを追跡（常に実行）
            if alias.name == "typing":
                imported_name = alias.asname or alias.name
                self._typing_aliases.add(imported_name)
            # 関数内の遅延インポートはスキップ
            if self._function_depth == 0:
                self.runtime_imports.append(alias.name)

    def visit_If(self, node: ast.If) -> None:
        """TYPE_CHECKING条件を検出し、そのブロック内はスキップ"""
        if self._is_type_checking_guard(node):
            # TYPE_CHECKINGブロック: bodyをvisitしない
            # elseブロックは通常コード（ランタイム）なのでvisit
            for child in node.orelse:
                self.visit(child)
            return  # bodyはスキップ

        # 通常のif文: 全てvisit
        self.generic_visit(node)

    def _is_type_checking_guard(self, node: ast.If) -> bool:
        """TYPE_CHECKING条件かどうか判定（v5: エイリアス対応強化）"""
        test = node.test

        # パターン1: if TYPE_CHECKING: (直接インポート)
        if isinstance(test, ast.Name):
            return test.id in self._type_checking_names or test.id == "TYPE_CHECKING"

        # パターン2: if typing.TYPE_CHECKING: または if t.TYPE_CHECKING: (v5対応)
        if isinstance(test, ast.Attribute):
            if isinstance(test.value, ast.Name):
                # typing/t/T 等のエイリアスを全てチェック
                return (
                    test.value.id in self._typing_aliases
                    and test.attr == "TYPE_CHECKING"
                )

        return False


def _collect_runtime_imports(source: str, module_package: str = "") -> list[str]:
    """ソースコードからランタイムインポートを収集"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    collector = RuntimeImportCollector(module_package)
    collector.visit(tree)
    return collector.runtime_imports


def _get_module_package(file_path: Path, root: Path) -> str:
    """ファイルパスからモジュールパッケージを計算

    例: katrain/core/game.py → katrain.core
    """
    try:
        rel = file_path.relative_to(root)
        parts = list(rel.parts[:-1])  # ディレクトリ部分のみ
        return ".".join(parts)
    except ValueError:
        return ""


def _has_call_in_node(node: ast.AST) -> bool:
    """ノード内に関数呼び出しがあるかチェック（v5追加: B対応）

    Assign/AnnAssignの右辺に関数呼び出しがあるかを検出
    例: DEFAULT = os.getenv("X") → True
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            return True
    return False


class TestLayerBoundaries:
    """レイヤー境界のテスト"""

    # 許可リスト（将来の例外用、現在は空）
    ALLOWED_CORE_GUI_IMPORTS: Set[str] = set()

    def test_no_core_imports_gui(self):
        """core層がgui層をランタイムインポートしていないことを検証"""
        violations = []
        core_dir = _PROJECT_ROOT / "katrain" / "core"

        for py_file in core_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            rel_path = py_file.relative_to(_PROJECT_ROOT / "katrain")
            module_pkg = _get_module_package(py_file, _PROJECT_ROOT)
            source = py_file.read_text(encoding="utf-8")
            runtime_imports = _collect_runtime_imports(source, module_pkg)

            for module in runtime_imports:
                if module.startswith("katrain.gui"):
                    if str(rel_path) not in self.ALLOWED_CORE_GUI_IMPORTS:
                        violations.append(f"{rel_path}: imports {module}")

        assert not violations, (
            f"Core→GUI runtime import violations:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_common_has_no_core_or_gui_imports(self):
        """common/がcore/やgui/をインポートしていないことを検証"""
        violations = []
        common_dir = _PROJECT_ROOT / "katrain" / "common"

        if not common_dir.exists():
            pytest.skip("common/ directory not found")

        for py_file in common_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            rel_path = py_file.relative_to(_PROJECT_ROOT / "katrain")
            module_pkg = _get_module_package(py_file, _PROJECT_ROOT)
            source = py_file.read_text(encoding="utf-8")
            runtime_imports = _collect_runtime_imports(source, module_pkg)

            for module in runtime_imports:
                if module.startswith(("katrain.core", "katrain.gui")):
                    violations.append(f"{rel_path}: imports {module}")

        assert not violations, (
            f"common/ should not import core/ or gui/:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_common_no_side_effects(self):
        """common/に副作用コードがないことを検証（v5強化: B対応）

        検査項目:
        - トップレベルExpr（関数呼び出し単体）を禁止
        - Assign/AnnAssign内の関数呼び出しも禁止（os.getenv()等）
        - docstringは許可
        """
        common_dir = _PROJECT_ROOT / "katrain" / "common"

        if not common_dir.exists():
            pytest.skip("common/ directory not found")

        violations = []
        for py_file in common_dir.rglob("*.py"):
            if "__pycache__" in str(py_file) or py_file.name == "__init__.py":
                continue

            source = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.iter_child_nodes(tree):
                # 禁止1: トップレベルExpr（docstring以外）
                if isinstance(node, ast.Expr):
                    if isinstance(node.value, ast.Constant) and isinstance(
                        node.value.value, str
                    ):
                        continue  # docstringは許可
                    violations.append(
                        f"{py_file.name}: side-effect expression at line {node.lineno}"
                    )

                # 禁止2: Assign/AnnAssign内の関数呼び出し（v5追加）
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    value = node.value
                    if value and _has_call_in_node(value):
                        violations.append(
                            f"{py_file.name}: function call in assignment at line {node.lineno}"
                        )

        assert not violations, (
            f"common/ should have no side effects:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestTypeCheckingSkip:
    """TYPE_CHECKINGスキップの単体テスト（v5強化）"""

    def test_skips_type_checking_block(self):
        """TYPE_CHECKINGブロック内のインポートはスキップされる"""
        source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.gui.theme import Theme  # should be skipped

from katrain.core.game import Game  # runtime import
"""
        imports = _collect_runtime_imports(source)
        assert "katrain.gui.theme" not in imports
        assert "katrain.core.game" in imports

    def test_skips_typing_type_checking(self):
        """typing.TYPE_CHECKING形式もスキップされる"""
        source = """
import typing

if typing.TYPE_CHECKING:
    from katrain.gui.popups import I18NPopup  # should be skipped

from katrain.core.constants import OUTPUT_INFO  # runtime
"""
        imports = _collect_runtime_imports(source)
        assert "katrain.gui.popups" not in imports
        assert "katrain.core.constants" in imports

    def test_else_block_is_runtime(self):
        """TYPE_CHECKINGのelseブロックはランタイム"""
        source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.gui.theme import Theme
else:
    from katrain.core.game import Game  # runtime
"""
        imports = _collect_runtime_imports(source)
        assert "katrain.gui.theme" not in imports
        assert "katrain.core.game" in imports

    def test_aliased_type_checking(self):
        """TYPE_CHECKINGがエイリアスされた場合"""
        source = """
from typing import TYPE_CHECKING as TC

if TC:
    from katrain.gui.theme import Theme  # should be skipped
"""
        imports = _collect_runtime_imports(source)
        assert "katrain.gui.theme" not in imports

    def test_typing_module_alias(self):
        """typingモジュールがエイリアスされた場合（v5追加: A対応）

        パターン: import typing as t; if t.TYPE_CHECKING:
        """
        source = """
import typing as t

if t.TYPE_CHECKING:
    from katrain.gui.theme import Theme  # should be skipped

from katrain.core.game import Game  # runtime
"""
        imports = _collect_runtime_imports(source)
        assert "katrain.gui.theme" not in imports
        assert "katrain.core.game" in imports

    def test_relative_import_resolution_explicit(self):
        """相対インポートの解決（v5追加: 明示的アサート）

        from .models → katrain.core.analysis.models
        from ..game → katrain.core.game
        """
        source = """
from .models import EvalSnapshot
from ..game import Game
"""
        imports = _collect_runtime_imports(source, "katrain.core.analysis")
        # 期待される解決結果を明示的にアサート
        assert "katrain.core.analysis.models" in imports
        assert "katrain.core.game" in imports


class TestSideEffectDetection:
    """副作用検出の単体テスト（v5追加）"""

    def test_detects_call_in_assign(self):
        """Assign内の関数呼び出しを検出"""
        node = ast.parse("DEFAULT = os.getenv('X')").body[0]
        assert _has_call_in_node(node)

    def test_detects_call_in_annassign(self):
        """AnnAssign内の関数呼び出しを検出"""
        node = ast.parse("DEFAULT: str = os.getenv('X')").body[0]
        assert _has_call_in_node(node)

    def test_allows_literal_assign(self):
        """リテラル代入は許可"""
        node = ast.parse("DEFAULT = 'value'").body[0]
        assert not _has_call_in_node(node)

    def test_allows_tuple_literal(self):
        """タプルリテラルは許可"""
        node = ast.parse("COLOR = (1.0, 0.5, 0.0)").body[0]
        assert not _has_call_in_node(node)


class TestLazyImportSkip:
    """遅延インポートスキップの単体テスト"""

    def test_skips_import_inside_function(self):
        """関数内のインポートはスキップされる"""
        source = """
from katrain.core.game import Game  # module-level

def my_function():
    from katrain.gui.theme import Theme  # lazy import, should be skipped
    return Theme
"""
        imports = _collect_runtime_imports(source)
        assert "katrain.core.game" in imports
        assert "katrain.gui.theme" not in imports

    def test_skips_import_inside_try_except(self):
        """try/except内の関数内インポートもスキップ"""
        source = """
class Lang:
    def switch_lang(self, lang):
        try:
            from katrain.gui.kivyutils import clear_texture_caches
            clear_texture_caches()
        except ImportError:
            pass
"""
        imports = _collect_runtime_imports(source)
        assert "katrain.gui.kivyutils" not in imports

    def test_module_level_import_collected(self):
        """モジュールレベルのインポートは収集される"""
        source = """
from katrain.core.utils import find_package_resource
import os
"""
        imports = _collect_runtime_imports(source)
        assert "katrain.core.utils" in imports
        assert "os" in imports


class TestModuleStructure:
    """Phase B4/B5 で追加されたモジュール構造の検証"""

    def test_analysis_submodules_exist(self):
        """analysis/ サブモジュールが存在する"""
        analysis_dir = _PROJECT_ROOT / "katrain" / "core" / "analysis"

        expected_files = [
            "logic.py",
            "logic_loss.py",
            "logic_importance.py",
            "logic_quiz.py",
            "models.py",
            "presentation.py",
        ]

        for filename in expected_files:
            filepath = analysis_dir / filename
            assert filepath.exists(), f"Expected {filename} in analysis/"

    def test_ai_strategies_base_exists(self):
        """ai_strategies_base.py が存在する"""
        filepath = _PROJECT_ROOT / "katrain" / "core" / "ai_strategies_base.py"
        assert filepath.exists(), "ai_strategies_base.py should exist"

    def test_reports_submodules_exist(self):
        """reports/ サブモジュールが存在する"""
        reports_dir = _PROJECT_ROOT / "katrain" / "core" / "reports"

        expected_files = [
            "__init__.py",
            "types.py",
            "summary_report.py",
            "quiz_report.py",
            "karte_report.py",
            "important_moves_report.py",
        ]

        for filename in expected_files:
            filepath = reports_dir / filename
            assert filepath.exists(), f"Expected {filename} in reports/"

    def test_gui_managers_exist(self):
        """gui/ マネージャーが存在する"""
        gui_dir = _PROJECT_ROOT / "katrain" / "gui"

        expected_files = [
            "leela_manager.py",
            "sgf_manager.py",
        ]

        for filename in expected_files:
            filepath = gui_dir / filename
            assert filepath.exists(), f"Expected {filename} in gui/"


class TestDependencyDirection:
    """依存方向の検証（Phase B6追加）

    許可される依存方向:
    - gui → core: OK
    - core → gui: NG（TYPE_CHECKING除く）
    - reports → game: OK（reports はcore層）
    - analysis サブモジュール → models: OK
    """

    def test_reports_does_not_import_gui(self):
        """reports/ が gui/ をインポートしていないことを検証"""
        violations = []
        reports_dir = _PROJECT_ROOT / "katrain" / "core" / "reports"

        if not reports_dir.exists():
            pytest.skip("reports/ directory not found")

        for py_file in reports_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            rel_path = py_file.relative_to(_PROJECT_ROOT / "katrain")
            module_pkg = _get_module_package(py_file, _PROJECT_ROOT)
            source = py_file.read_text(encoding="utf-8")
            runtime_imports = _collect_runtime_imports(source, module_pkg)

            for module in runtime_imports:
                if module.startswith("katrain.gui"):
                    violations.append(f"{rel_path}: imports {module}")

        assert not violations, (
            f"reports/ should not import gui/:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_analysis_submodules_do_not_import_gui(self):
        """analysis/ サブモジュールが gui/ をインポートしていないことを検証"""
        violations = []
        analysis_dir = _PROJECT_ROOT / "katrain" / "core" / "analysis"

        for py_file in analysis_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            rel_path = py_file.relative_to(_PROJECT_ROOT / "katrain")
            module_pkg = _get_module_package(py_file, _PROJECT_ROOT)
            source = py_file.read_text(encoding="utf-8")
            runtime_imports = _collect_runtime_imports(source, module_pkg)

            for module in runtime_imports:
                if module.startswith("katrain.gui"):
                    violations.append(f"{rel_path}: imports {module}")

        assert not violations, (
            f"analysis/ should not import gui/:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_ai_strategies_base_does_not_import_gui(self):
        """ai_strategies_base.py が gui/ をインポートしていないことを検証"""
        filepath = _PROJECT_ROOT / "katrain" / "core" / "ai_strategies_base.py"

        if not filepath.exists():
            pytest.skip("ai_strategies_base.py not found")

        source = filepath.read_text(encoding="utf-8")
        runtime_imports = _collect_runtime_imports(source, "katrain.core")

        gui_imports = [m for m in runtime_imports if m.startswith("katrain.gui")]
        assert not gui_imports, (
            f"ai_strategies_base.py should not import gui/: {gui_imports}"
        )

    def test_batch_does_not_import_kivy(self):
        """core/batch/ must not import kivy* or katrain.gui* (Phase 42-A).

        Forbidden imports (from AllImportCollector.FORBIDDEN_PREFIXES):
        - kivy, kivy.*, kivymd, kivy_garden.*
        - katrain.gui, katrain.gui.*

        Note: TYPE_CHECKING imports are allowed (AllImportCollector skips them).
        This is verified by test_skips_type_checking_block().
        """
        violations = []
        batch_dir = _PROJECT_ROOT / "katrain" / "core" / "batch"

        if not batch_dir.exists():
            pytest.skip("batch/ directory not found")

        for py_file in batch_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            rel_path = py_file.relative_to(_PROJECT_ROOT / "katrain")
            module_pkg = _get_module_package(py_file, _PROJECT_ROOT)
            source = py_file.read_text(encoding="utf-8")

            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            collector = AllImportCollector(module_pkg)
            collector.visit(tree)

            forbidden = collector.get_forbidden_imports()
            for lineno, module in forbidden:
                violations.append(f"{rel_path}:{lineno}: imports {module}")

        assert not violations, (
            f"core/batch/ must not import kivy/gui:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nNote: TYPE_CHECKING imports are allowed and not flagged."
        )


# ===========================================================================
# Phase 20 (PR #136): Kivy/GUI isolation tests
# ===========================================================================


class AllImportCollector(ast.NodeVisitor):
    """全てのインポートを収集（関数内の遅延インポート含む）

    RuntimeImportCollectorとは異なり、_function_depthをチェックしない。
    TYPE_CHECKINGガードのみスキップ。

    用途: core層がKivy/GUIに依存していないかの完全検査
    """

    # 禁止プレフィックス（startswithでチェック）
    FORBIDDEN_PREFIXES = ("kivy", "kivymd", "kivy_garden", "katrain.gui")

    def __init__(self, module_package: str = ""):
        self.all_imports: List[Tuple[int, str]] = []  # (line_no, module_name)
        self._module_package = module_package
        self._type_checking_names: Set[str] = set()
        self._typing_aliases: Set[str] = {"typing"}
        self._in_type_checking_block = False

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        # TYPE_CHECKING名の追跡
        if node.module == "typing":
            for alias in node.names:
                if alias.name == "TYPE_CHECKING":
                    self._type_checking_names.add(alias.asname or alias.name)

        if self._in_type_checking_block:
            self.generic_visit(node)
            return

        if node.module:
            if node.level > 0 and self._module_package:
                resolved = self._resolve_relative_import(node.module, node.level)
                if resolved:
                    self.all_imports.append((node.lineno, resolved))
            else:
                self.all_imports.append((node.lineno, node.module))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "typing":
                self._typing_aliases.add(alias.asname or alias.name)

        if self._in_type_checking_block:
            self.generic_visit(node)
            return

        for alias in node.names:
            self.all_imports.append((node.lineno, alias.name))
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        if self._is_type_checking_guard(node):
            old_state = self._in_type_checking_block
            self._in_type_checking_block = True
            for child in node.body:
                self.visit(child)
            self._in_type_checking_block = old_state
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def _is_type_checking_guard(self, node: ast.If) -> bool:
        test = node.test
        if isinstance(test, ast.Name):
            return test.id in self._type_checking_names or test.id == "TYPE_CHECKING"
        if isinstance(test, ast.Attribute):
            if isinstance(test.value, ast.Name):
                return test.value.id in self._typing_aliases and test.attr == "TYPE_CHECKING"
        return False

    def _resolve_relative_import(self, module: str, level: int) -> str:
        """相対インポートを絶対パスに解決

        例:
        - level=1, module="models" in "katrain.core.analysis" → "katrain.core.analysis.models"
        - level=2, module="game" in "katrain.core.analysis" → "katrain.core.game"
        """
        parts = self._module_package.split(".")
        if level > len(parts):
            return ""

        # level=1: 現在のパッケージ（全パーツを保持）
        # level=2: 1つ上のパッケージ（最後の1つを削除）
        # level=N: N-1個上のパッケージ
        if level == 1:
            base_parts = parts  # 同じパッケージ
        else:
            base_parts = parts[:-(level - 1)]  # level-1個削除
        base = ".".join(base_parts)
        return f"{base}.{module}" if module else base

    def is_forbidden(self, module: str) -> bool:
        """モジュールが禁止リストに該当するか判定"""
        return module.startswith(self.FORBIDDEN_PREFIXES)

    def get_forbidden_imports(self) -> List[Tuple[int, str]]:
        """禁止モジュールのインポートを返す"""
        return [(lineno, module) for lineno, module in self.all_imports
                if self.is_forbidden(module)]


class TestAllImportCollectorUnit:
    """AllImportCollectorの単体テスト"""

    def test_resolve_relative_import_level1(self):
        """level=1の相対インポート解決"""
        collector = AllImportCollector("katrain.core.analysis")
        assert collector._resolve_relative_import("models", 1) == "katrain.core.analysis.models"

    def test_resolve_relative_import_level2(self):
        """level=2の相対インポート解決"""
        collector = AllImportCollector("katrain.core.analysis")
        assert collector._resolve_relative_import("game", 2) == "katrain.core.game"

    def test_resolve_relative_import_empty_module(self):
        """moduleが空の場合"""
        collector = AllImportCollector("katrain.core.analysis")
        assert collector._resolve_relative_import("", 1) == "katrain.core.analysis"

    def test_is_forbidden_kivy(self):
        """kivy系モジュールは禁止"""
        collector = AllImportCollector()
        assert collector.is_forbidden("kivy")
        assert collector.is_forbidden("kivy.utils")
        assert collector.is_forbidden("kivymd")
        assert collector.is_forbidden("kivy_garden.flower")

    def test_is_forbidden_katrain_gui(self):
        """katrain.guiは禁止"""
        collector = AllImportCollector()
        assert collector.is_forbidden("katrain.gui")
        assert collector.is_forbidden("katrain.gui.widgets")

    def test_is_allowed_katrain_core(self):
        """katrain.coreは許可"""
        collector = AllImportCollector()
        assert not collector.is_forbidden("katrain.core")
        assert not collector.is_forbidden("katrain.common")

    def test_detects_lazy_import(self):
        """関数内の遅延インポートを検出"""
        source = '''
def my_function():
    from katrain.gui.theme import Theme
    return Theme
'''
        tree = ast.parse(source)
        collector = AllImportCollector()
        collector.visit(tree)

        forbidden = collector.get_forbidden_imports()
        assert len(forbidden) == 1
        assert forbidden[0][1] == "katrain.gui.theme"

    def test_skips_type_checking_block(self):
        """TYPE_CHECKINGブロックはスキップ"""
        source = '''
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from katrain.gui.theme import Theme  # should be skipped

from kivy.utils import platform  # should be detected
'''
        tree = ast.parse(source)
        collector = AllImportCollector()
        collector.visit(tree)

        forbidden = collector.get_forbidden_imports()
        modules = [m for _, m in forbidden]
        assert "kivy.utils" in modules
        assert "katrain.gui.theme" not in modules


# 許可リストの既知エントリ（削除のみ許可、追加禁止）
KNOWN_ALLOWLIST_ENTRIES = frozenset({
    "core/base_katrain.py|kivy",
})


def _check_import_exists_in_file(file_path: Path, import_prefix: str) -> bool:
    """ファイル内に指定プレフィックスで始まるインポートがあるか確認"""
    source = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    collector = AllImportCollector()
    collector.visit(tree)

    for _, module in collector.all_imports:
        if module == import_prefix or module.startswith(f"{import_prefix}."):
            return True
    return False


class TestKivyIsolation:
    """core層がKivy/GUIに依存しないことを検証（Phase 20 PR #136）"""

    @pytest.fixture
    def allowlist(self) -> dict:
        fixture_path = _TEST_DIR / "fixtures" / "kivy_import_allowlist.json"
        if not fixture_path.exists():
            return {"entries": {}}
        with open(fixture_path, encoding="utf-8") as f:
            return json.load(f)

    def test_allowlist_is_delete_only(self, allowlist):
        """許可リストは削除のみ許可（ハードコードセットで強制）"""
        entries = set(allowlist.get("entries", {}).keys())
        new_entries = entries - KNOWN_ALLOWLIST_ENTRIES

        assert not new_entries, (
            f"New allowlist entries detected (DELETE-ONLY policy):\n"
            + "\n".join(f"  - {e}" for e in new_entries)
            + "\n\nTo fix: Remove the violating import instead of adding to allowlist.\n"
            "The allowlist is DELETE-ONLY. Contact maintainer to discuss exceptions."
        )

    def test_no_forbidden_imports_in_core(self, allowlist):
        """core層がKivy/KivyMD/katrain.guiをインポートしていないことを検証

        遅延インポート（関数内）も検出する。
        """
        violations = []
        allowed_entries = allowlist.get("entries", {})
        core_dir = _PROJECT_ROOT / "katrain" / "core"

        for py_file in core_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            rel_path = str(py_file.relative_to(_PROJECT_ROOT / "katrain")).replace("\\", "/")
            source = py_file.read_text(encoding="utf-8")

            try:
                tree = ast.parse(source)
            except SyntaxError as e:
                pytest.fail(f"SyntaxError in {rel_path}:{e.lineno}: {e.msg}")

            module_pkg = _get_module_package(py_file, _PROJECT_ROOT)
            collector = AllImportCollector(module_pkg)
            collector.visit(tree)

            for lineno, module in collector.get_forbidden_imports():
                # 許可リストのマッチング
                # 1. 完全一致: "core/lang.py|kivy._event"
                # 2. プレフィックス一致: "core/lang.py|katrain.gui" → katrain.gui.* にマッチ
                is_allowed = False
                for allowlist_key in allowed_entries.keys():
                    if "|" not in allowlist_key:
                        continue
                    key_file, key_module = allowlist_key.split("|", 1)
                    if key_file == rel_path:
                        if module == key_module or module.startswith(f"{key_module}."):
                            is_allowed = True
                            break

                if not is_allowed:
                    violations.append(f"{rel_path}:{lineno}: imports {module}")

        assert not violations, (
            f"Forbidden imports found in core layer:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nTo fix: Remove the import. Adding to allowlist is NOT permitted."
        )

    def test_allowlist_entries_still_exist(self, allowlist):
        """許可リストのエントリがまだ存在することを確認（stale検出）"""
        entries = allowlist.get("entries", {})
        stale_entries = []

        for key, info in entries.items():
            if "|" not in key:
                continue

            file_rel, import_prefix = key.split("|", 1)
            full_path = _PROJECT_ROOT / "katrain" / file_rel

            if not full_path.exists():
                stale_entries.append(f"{key}: file no longer exists")
                continue

            if not _check_import_exists_in_file(full_path, import_prefix):
                stale_entries.append(f"{key}: import no longer exists in file")

        assert not stale_entries, (
            f"Stale allowlist entries (imports already removed):\n"
            + "\n".join(f"  - {e}" for e in stale_entries)
            + "\n\nPlease remove these entries from kivy_import_allowlist.json"
        )
