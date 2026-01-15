"""Architecture validation tests for KaTrain.

PR #114: Phase B1 - Architecture validation tests (v5)

v5改善:
- TYPE_CHECKING検出: `import typing as t; if t.TYPE_CHECKING:` パターン対応
- 相対インポートテスト: 期待される解決結果を明示的にアサート
- 副作用検出: Assign/AnnAssign内の関数呼び出しも検出
"""

import ast
from pathlib import Path
from typing import Set

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
