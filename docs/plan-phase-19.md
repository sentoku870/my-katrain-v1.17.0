# Phase 19: 大規模リファクタリング計画（改訂版 v5）

> **作成日**: 2026-01-15
> **改訂日**: 2026-01-16（v8: Phase 19クローズ）
> **ステータス**: ✅ 完了（主要リファクタリング完了、一部項目は効果薄/リスク高のためスキップ）
> **修正レベル**: Lv5（根本的アーキテクチャ改善）
> **前提**: Phase 18完了（879テストパス）

---

## 完了サマリー（v8）

### 実施済み
| Phase | 内容 | PR |
|-------|------|-----|
| **B1** | 循環依存解消（common/theme_constants.py） | ✅ |
| **B2** | game.py → reports/パッケージ抽出（5モジュール） | ✅ |
| **B3** | KaTrainGui分割（leela_manager, sgf_manager） | ✅ 部分完了 |
| **B4** | analysis/logic.py分割（loss, importance, quiz） | ✅ |
| **B5** | ai.py分割（ai_strategies_base.py） | ✅ 部分完了 |
| **B6** | アーキテクチャテスト・ドキュメント | ✅ |

### スキップ（理由）
| 項目 | 理由 |
|------|------|
| dialog_coordinator.py | 規模大・リスク高・手動テスト必須 |
| keyboard_controller.py | リスク高・全ショートカット手動テスト必須 |
| ai_strategies_advanced.py | 効果薄（既にai_strategies_base.pyで十分分割済み）|

### 成果
- **テスト数**: 879パス（増加）
- **ai.py**: 1,459行 → 1,061行（-27%）
- **analysis/**: logic.pyをサブモジュール化（再利用性向上）
- **reports/**: game.pyからレポート生成ロジックを分離
- **gui/**: leela_manager, sgf_managerを依存注入パターンで抽出

---

## v5 改訂サマリー

| 項目 | v4計画 | v5改訂 |
|------|--------|--------|
| **A) ASTテスト強化** | `typing.TYPE_CHECKING`のみ検出 | **`import typing as t`等のエイリアス対応 + 相対インポートテスト強化** |
| **B) common/副作用テスト** | トップレベル`Expr`のみ検出 | **Assign/AnnAssign内の`ast.Call`も検出** |
| **C) ConfigReader確認** | `__call__(key, default)`を仮定 | **既存FeatureContext.configと一致確認済み → 再利用** |
| **D) Protocol型確認** | `board_size: int`を仮定 | **実際は`Tuple[int,int]` → 型定義を修正** |

### v4からの継続項目（変更なし）
| 項目 | 内容 |
|------|------|
| カルテテスト | CI=構造テスト、手動=正規化diff |
| 循環依存解消 | common/theme_constants.py活用 |
| game.py分割 | reports/サブパッケージ |
| KaTrainGui抽出 | 明示的依存のみ（依存注入パターン） |
| 並行実行 | 単独開発者向け順次実行推奨 |

---

## 1. Architecture Snapshot（現状分析）

### 1.1 モジュール構成と行数

#### Core Layer (`katrain/core/`) - 11,300 LOC
| ファイル | 行数 | 責務 | 結合度リスク |
|----------|------|------|--------------|
| **game.py** | **2,883** | ゲーム状態 + レポート生成 + 解析オーケストレーション | **🔴 VERY HIGH** |
| **ai.py** | **1,459** | 15+ AI戦略クラス | 🟡 HIGH |
| engine.py | 563 | KataGoプロセス管理 | 🔴 HIGH |
| sgf_parser.py | 743 | SGFパース/生成 | ⭐ LOW |
| game_node.py | 489 | ノード状態・解析データ | 🟡 MEDIUM |
| board_analysis.py | 484 | 戦術分析 | ⭐ LOW |
| constants.py | 323 | 定数定義 | ⭐ NONE |
| lang.py | 97 | 国際化 | 🟡 MEDIUM (⚠️ gui依存) |

#### 検出された循環依存
```
core/lang.py (Line 8)
    └─→ from katrain.gui.theme import Theme  ⚠️ VIOLATION
        └─→ Theme.DEFAULT_FONT (Line 56)
```

**実際に必要なもの**: フォント名文字列 `"NotoSansJP-Regular.otf"` のみ

### 1.2 game.py 責務分析（詳細）

| 責務カテゴリ | 行数 | 状態変更 | 抽出可能性 |
|-------------|------|----------|------------|
| BaseGame（盤面状態） | ~150 | ✅ YES | ❌ コア維持 |
| Game初期化・操作 | ~600 | ✅ YES | ❌ コア維持 |
| 解析オーケストレーション | ~300 | ✅ YES | ❌ コア維持 |
| **カルテレポート** | ~800 | ❌ READ-ONLY | ✅ 抽出可能 |
| **サマリーレポート** | ~400 | ❌ READ-ONLY | ✅ 抽出可能（staticmethod） |
| **クイズ生成** | ~100 | ❌ READ-ONLY | ✅ 抽出可能 |
| **重要局面表示** | ~200 | ⚠️ 一部変更 | ✅ 部分抽出可能 |
| ナビゲーション | ~100 | ✅ YES | ❌ UI統合維持 |

**重要発見**: レポート生成メソッドは**純粋に読み取り専用**（`get_important_move_evals()`の`reason_tags`変更を除く）

### 1.3 依存関係グラフ

```
                    ┌─────────────────────────────────────┐
                    │  Foundation Layer (No dependencies)  │
                    │  constants.py, errors.py, utils.py   │
                    │  sgf_parser.py                       │
                    └────────────────┬────────────────────┘
                                     │
                    ┌────────────────▼────────────────────┐
                    │  Shared Layer                        │
                    │  common/theme_constants.py ← NEW     │
                    └────────────────┬────────────────────┘
                                     │
                    ┌────────────────▼────────────────────┐
                    │  Data Layer                          │
                    │  analysis/models.py, game_node.py    │
                    │  lang.py (now imports from common)   │
                    └────────────────┬────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
    ┌─────────▼─────────┐  ┌────────▼────────┐  ┌─────────▼─────────┐
    │ analysis/logic.py │  │   engine.py     │  │ board_analysis.py │
    └─────────┬─────────┘  └────────┬────────┘  └───────────────────┘
              │                     │
              └─────────┬───────────┘
                        │
               ┌────────▼────────┐
               │    game.py      │  ← REDUCED (~800 lines)
               │  (State + Orch) │
               └────────┬────────┘
                        │
           ┌────────────┼────────────┐
           │            │            │
    ┌──────▼──────┐ ┌──▼──┐ ┌───────▼───────┐
    │ reports/    │ │ ai  │ │ leela/tsumego │
    │ (NEW pkg)   │ └─────┘ └───────────────┘
    └─────────────┘
```

### 1.4 非交渉事項（Invariants）

| 項目 | 説明 | 検証方法 |
|------|------|----------|
| **カルテ出力形式** | Markdown形式、アンカー必須 | 出力テスト |
| **FeatureContext Protocol** | 機能モジュールのインターフェース | 型チェック |
| **KataGo JSONプロトコル** | 解析リクエスト/レスポンス形式 | 既存テスト |
| **SGFフォーマット** | 標準SGF + KaTrain拡張 | パーステスト |
| **テスト通過** | 843テスト全パス維持 | CI |

---

## 2. リファクタリング選択肢

### 推奨: Option B（中程度のリファクタリング）

**変更内容**:
1. **Phase B1**: 循環依存解消（common活用）
2. **Phase B2**: game.py → reports/サブパッケージ抽出
3. **Phase B3**: KaTrainGui分割（明示的依存）
4. **Phase B4**: analysis/logic.py分割
5. **Phase B5**: ai.py戦略分離
6. **Phase B6**: アーキテクチャテスト・ドキュメント

---

## 3. Epic PR Series（改訂版）

### Phase B1: 循環依存解消（PR #113-114）

#### PR #113: DEFAULT_FONTをcommonに移動
- **ファイル**:
  - `katrain/common/theme_constants.py`（追加）
  - `katrain/common/__init__.py`（更新）
  - `katrain/core/lang.py`（インポート変更）
  - `katrain/gui/theme.py`（インポート変更、任意）
- **内容**:
  ```python
  # katrain/common/theme_constants.py
  # 既存: INFO_PV_COLOR
  DEFAULT_FONT = "NotoSansJP-Regular.otf"  # 追加

  # katrain/core/lang.py (Line 8)
  # Before: from katrain.gui.theme import Theme
  # After:  from katrain.common import DEFAULT_FONT

  # Line 56:
  # Before: self.font_name = self.FONTS.get(lang) or Theme.DEFAULT_FONT
  # After:  self.font_name = self.FONTS.get(lang) or DEFAULT_FONT
  ```
- **リスク**: LOW
- **受入条件**:
  - `grep "katrain.gui" katrain/core/lang.py` → 結果なし
  - `python -c "from katrain.core.lang import Lang"` → 成功
  - 全テストパス
- **ロールバック**: git revert

#### PR #114: アーキテクチャ検証テスト（基礎）
- **ファイル**: `tests/test_architecture.py`（新規）
- **v5改善**:
  - **A-1**: `import typing as t`等のエイリアスに対応（typingモジュールエイリアス追跡）
  - **A-2**: 相対インポートテストで期待値を明示的にアサート
  - **B-1**: Assign/AnnAssign内の`ast.Call`を検出（`os.getenv()`等の副作用防止）
- **内容**:
  ```python
  """Architecture validation tests for KaTrain.

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
      """Collects runtime imports, skipping TYPE_CHECKING blocks.

      v5改善:
      - typingモジュールのエイリアス追跡（`import typing as t`対応）
      - TYPE_CHECKINGのインポート元を追跡
      - 相対インポートを適切に処理
      """

      def __init__(self, module_package: str = ""):
          self.runtime_imports: list[str] = []
          self._module_package = module_package  # 相対インポート解決用
          # TYPE_CHECKINGとしてインポートされた名前を追跡
          self._type_checking_names: Set[str] = set()
          # typingモジュールのエイリアスを追跡（v5追加）
          self._typing_aliases: Set[str] = {"typing"}  # デフォルトで"typing"を含む

      def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
          """from ... import文を収集"""
          # typing.TYPE_CHECKINGのインポートを追跡
          if node.module == "typing":
              for alias in node.names:
                  if alias.name == "TYPE_CHECKING":
                      imported_name = alias.asname or alias.name
                      self._type_checking_names.add(imported_name)

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
          base_parts = parts[:-level + 1] if level > 1 else parts
          base = ".".join(base_parts)
          return f"{base}.{module}" if module else base

      def visit_Import(self, node: ast.Import) -> None:
          """import文を収集"""
          for alias in node.names:
              # typingモジュールのエイリアスを追跡（v5追加）
              if alias.name == "typing":
                  imported_name = alias.asname or alias.name
                  self._typing_aliases.add(imported_name)
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
                  return test.value.id in self._typing_aliases and test.attr == "TYPE_CHECKING"

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
                      if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                          continue  # docstringは許可
                      violations.append(f"{py_file.name}: side-effect expression at line {node.lineno}")

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
          source = '''
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from katrain.gui.theme import Theme  # should be skipped

  from katrain.core.game import Game  # runtime import
  '''
          imports = _collect_runtime_imports(source)
          assert "katrain.gui.theme" not in imports
          assert "katrain.core.game" in imports

      def test_skips_typing_type_checking(self):
          """typing.TYPE_CHECKING形式もスキップされる"""
          source = '''
  import typing

  if typing.TYPE_CHECKING:
      from katrain.gui.popups import I18NPopup  # should be skipped

  from katrain.core.constants import OUTPUT_INFO  # runtime
  '''
          imports = _collect_runtime_imports(source)
          assert "katrain.gui.popups" not in imports
          assert "katrain.core.constants" in imports

      def test_else_block_is_runtime(self):
          """TYPE_CHECKINGのelseブロックはランタイム"""
          source = '''
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from katrain.gui.theme import Theme
  else:
      from katrain.core.game import Game  # runtime
  '''
          imports = _collect_runtime_imports(source)
          assert "katrain.gui.theme" not in imports
          assert "katrain.core.game" in imports

      def test_aliased_type_checking(self):
          """TYPE_CHECKINGがエイリアスされた場合"""
          source = '''
  from typing import TYPE_CHECKING as TC

  if TC:
      from katrain.gui.theme import Theme  # should be skipped
  '''
          imports = _collect_runtime_imports(source)
          assert "katrain.gui.theme" not in imports

      def test_typing_module_alias(self):
          """typingモジュールがエイリアスされた場合（v5追加: A対応）

          パターン: import typing as t; if t.TYPE_CHECKING:
          """
          source = '''
  import typing as t

  if t.TYPE_CHECKING:
      from katrain.gui.theme import Theme  # should be skipped

  from katrain.core.game import Game  # runtime
  '''
          imports = _collect_runtime_imports(source)
          assert "katrain.gui.theme" not in imports
          assert "katrain.core.game" in imports

      def test_relative_import_resolution_explicit(self):
          """相対インポートの解決（v5追加: 明示的アサート）

          from .models → katrain.core.analysis.models
          from ..game → katrain.core.game
          """
          source = '''
  from .models import EvalSnapshot
  from ..game import Game
  '''
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
  ```
- **リスク**: LOW
- **受入条件**:
  - テストパス（循環依存解消後）
  - TYPE_CHECKINGスキップの全単体テスト（エイリアス含む）がパス
  - 副作用検出テストがパス
  - pytest を任意のディレクトリから実行しても動作

---

### Phase B2: game.py → reports/パッケージ（PR #115-120）

#### PR #115: reports/パッケージ骨格作成
- **ファイル**:
  - `katrain/core/reports/__init__.py`（新規）
  - `katrain/core/reports/types.py`（新規）
  - `tests/test_reports_types.py`（新規）
- **v5改善**:
  - **C-1**: 既存fixture（`sample_game`）を使用
  - **C-2**: 属性存在テストで検証（より堅牢）
  - **C-3**: 既存の`FeatureContext.config`と一致するため、新規Protocolは不要 → 再利用
  - **D-1**: `board_size`の型を`Tuple[int, int]`に修正（実際のGame.board_sizeの型）
  - **D-2**: 型テストを実際の戻り値型に合わせて修正
- **内容**:
  ```python
  # katrain/core/reports/types.py
  """Type definitions for report generation.

  v5設計方針:
  - Protocol は最小限から始める
  - 各PRで必要なメソッドのみ追加
  - runtime_checkableは使わない（属性テストで検証）
  - ConfigReaderは既存のFeatureContext.configと同じシグネチャ
  - 型は実際のGame/SGFNode実装に合わせる
  """
  from typing import Protocol, Optional, Any, Tuple


  class GameMetadataProvider(Protocol):
      """最小限のゲームメタデータ（PR #116 summary_report用）

      v5: 実際のGame/SGFNodeの型に合わせた定義
      """
      @property
      def board_size(self) -> Tuple[int, int]:
          """盤面サイズ（x, y）。非正方形盤面対応のためタプル。"""
          ...

      @property
      def komi(self) -> float: ...

      @property
      def rules(self) -> str: ...

      @property
      def sgf_filename(self) -> Optional[str]: ...

      def get_root_property(self, key: str) -> Optional[str]: ...


  class ConfigReader(Protocol):
      """設定値を読み取るためのProtocol

      v5確認済み: 既存のFeatureContext.configおよびBaseKatrain.configと同じシグネチャ
      - FeatureContext.config(setting: str, default: Any = None) -> Any
      - BaseKatrain.config(setting, default=None)

      用途: karte_report等でconfig値を取得する際の型安全なインターフェース

      実装例:
      - KaTrainGui.config (実際の使用)
      - FeatureContext.config (既存Protocol)
      - テスト用のdictラッパー
      """
      def __call__(self, key: str, default: Any = None) -> Any:
          """設定値を取得

          Args:
              key: 設定キー（例: "karte/show_variation_pv"）
              default: キーが存在しない場合のデフォルト値

          Returns:
              設定値、またはdefault
          """
          ...


  # PR #119 で追加予定
  # class GameAnalysisProvider(GameMetadataProvider, Protocol):
  #     """解析データを含むプロバイダ（karte_report用）"""
  #     def build_eval_snapshot(self) -> "EvalSnapshot": ...
  #     @property
  #     def current_node(self) -> "GameNode": ...
  #     @property
  #     def root(self) -> "GameNode": ...


  # Protocol が要求する属性リスト（テスト用）
  GAME_METADATA_REQUIRED_ATTRS = [
      "board_size",
      "komi",
      "rules",
      "sgf_filename",
      "get_root_property",
  ]

  CONFIG_READER_REQUIRED_ATTRS = [
      "__call__",
  ]
  ```

  ```python
  # tests/test_reports_types.py (PR #115に含める)
  """Protocol互換性テスト（v5: 型を実際の実装に合わせて検証）

  v5改善:
  - 属性存在テスト
  - 既存fixture (sample_game) を活用
  - 実際の戻り値型を検証（board_size: Tuple[int, int]等）
  - FeatureContext.configとConfigReaderの互換性を確認
  """
  import pytest
  from katrain.core.reports.types import (
      GAME_METADATA_REQUIRED_ATTRS,
      CONFIG_READER_REQUIRED_ATTRS,
  )


  class TestGameMetadataProviderCompatibility:
      """GameクラスがGameMetadataProviderを満たすことを検証"""

      def test_game_has_required_attributes(self, sample_game):
          """Game が必須属性を持っている"""
          for attr in GAME_METADATA_REQUIRED_ATTRS:
              assert hasattr(sample_game, attr), (
                  f"Game must have '{attr}' attribute/method. "
                  f"GameMetadataProvider protocol requires: {GAME_METADATA_REQUIRED_ATTRS}"
              )

      def test_game_attributes_types(self, sample_game):
          """属性の型が正しい（v5: 実際の型を検証）"""
          # board_size は Tuple[int, int]（非正方形盤面対応）
          board_size = sample_game.board_size
          assert isinstance(board_size, tuple), f"board_size should be tuple, got {type(board_size)}"
          assert len(board_size) == 2, f"board_size should be (x, y), got {board_size}"
          assert all(isinstance(d, int) for d in board_size), f"board_size elements should be int"

          # komi は float
          assert isinstance(sample_game.komi, (int, float))

          # rules は str
          assert isinstance(sample_game.rules, str)

          # sgf_filename は None または str
          assert sample_game.sgf_filename is None or isinstance(sample_game.sgf_filename, str)

          # メソッド
          assert callable(sample_game.get_root_property)


  class TestConfigReaderCompatibility:
      """ConfigReader Protocol の検証"""

      def test_dict_wrapper_satisfies_protocol(self):
          """dictをラップしたConfigReaderの例"""
          class DictConfigReader:
              def __init__(self, data: dict):
                  self._data = data

              def __call__(self, key: str, default=None):
                  # スラッシュ区切りのキーをサポート（実際のconfig互換）
                  if "/" in key:
                      cat, k = key.split("/", 1)
                      return self._data.get(cat, {}).get(k, default)
                  return self._data.get(key, default)

          config = DictConfigReader({"karte": {"show_variation_pv": True}})

          # Protocol要件を満たす
          for attr in CONFIG_READER_REQUIRED_ATTRS:
              assert hasattr(config, attr)

          # 動作確認（スラッシュ区切りキー）
          assert config("karte/show_variation_pv") is True
          assert config("nonexistent", "default") == "default"

      def test_feature_context_config_signature(self):
          """FeatureContext.configのシグネチャがConfigReaderと互換（v5: 確認済み）

          FeatureContext.config(setting: str, default: Any = None) -> Any
          ConfigReader.__call__(key: str, default: Any = None) -> Any
          """
          from katrain.gui.features.context import FeatureContext
          import inspect

          # FeatureContext.config のシグネチャを取得
          sig = inspect.signature(FeatureContext.config)
          params = list(sig.parameters.keys())

          # 期待するパラメータ: self, setting, default
          assert "setting" in params or len(params) >= 2
          # default パラメータが存在
          assert "default" in params


  class TestProtocolDefinitions:
      """Protocol定義自体のテスト"""

      def test_required_attrs_lists_exist(self):
          """必須属性リストが定義されている"""
          assert len(GAME_METADATA_REQUIRED_ATTRS) >= 5
          assert len(CONFIG_READER_REQUIRED_ATTRS) >= 1

      def test_protocol_import_succeeds(self):
          """Protocol定義がインポート可能"""
          from katrain.core.reports.types import (
              GameMetadataProvider,
              ConfigReader,
          )
          # 型ヒントとして使用可能か確認
          def example_func(game: GameMetadataProvider, config: ConfigReader) -> str:
              return ""
  ```
- **リスク**: LOW
- **受入条件**:
  - インポート成功
  - `sample_game` fixture を使った属性・型テストがパス
  - ConfigReader Protocol が FeatureContext.config と互換
  - `katrain/core/reports/` が `katrain.gui` をインポートしていない

#### PR #116: summary_report.py抽出（最も簡単）
- **ファイル**:
  - `katrain/core/reports/summary_report.py`（新規）
  - `katrain/core/game.py`（委譲メソッド追加）
- **内容**:
  - `build_summary_report()` を移動（既にstaticmethod）
  - `_aggregate_player_stats()` を移動
  - 全`_format_*()` フォーマッタを移動
- **抽出行数**: ~600行
- **リスク**: LOW（全てstaticmethod）
- **受入条件**:
  - サマリーエクスポート機能が正常動作
  - 全テストパス
- **後方互換**:
  ```python
  # game.py に委譲メソッドを残す
  @staticmethod
  def build_summary_report(game_data_list, focus_player):
      """Deprecated: use reports.summary_report.build_summary_report()"""
      from katrain.core.reports import summary_report
      return summary_report.build_summary_report(game_data_list, focus_player)
  ```

#### PR #117: quiz_report.py抽出
- **ファイル**:
  - `katrain/core/reports/quiz_report.py`（新規）
  - `katrain/core/game.py`（委譲）
- **内容**:
  - `get_quiz_items()` → 純関数化
  - `build_quiz_questions()` → 純関数化
- **抽出行数**: ~100行
- **リスク**: LOW
- **受入条件**: クイズ生成が正常動作

#### PR #118: formatters.py抽出（共通フォーマッタ）
- **ファイル**:
  - `katrain/core/reports/formatters.py`（新規）
- **内容**:
  - `_convert_sgf_to_gtp_coord()`
  - `_detect_urgent_miss_sequences()`
  - Karte内部フォーマッタ（`fmt_val`, `fmt_float`, 等）
- **抽出行数**: ~300行
- **リスク**: LOW
- **受入条件**: 全テストパス

#### PR #119: karte_report.py抽出（最大）
- **ファイル**:
  - `katrain/core/reports/karte_report.py`（新規）
  - `katrain/core/game.py`（委譲）
  - `tests/test_karte_output.py`（新規/更新）
- **内容**:
  - `build_karte_report()` → 純関数化
  - `_build_karte_report_impl()` → 純関数化
  - `_build_error_karte()` → 純関数化
- **抽出行数**: ~800行
- **v4改善**:
  - **A-1**: カルテテスト戦略を統一（CI=構造、手動=正規化diff）
  - **D-2**: `ConfigReader` Protocol を使用（`Callable[[str], Any]`ではない）
- **シグネチャ変更**:
  ```python
  # 新しいAPI（v4: ConfigReader Protocol使用）
  from katrain.core.reports.types import GameMetadataProvider, ConfigReader

  def build_karte_report(
      game: GameMetadataProvider,  # Protocolで型付け
      level: int,
      player_filter: Optional[str],
      skill_preset: SkillPreset,
      config: ConfigReader,  # v4: 明示的Protocol
  ) -> str:
      """カルテレポートを生成

      Args:
          game: ゲームデータプロバイダ
          level: 詳細レベル（1-3）
          player_filter: 対象プレイヤー（"B", "W", None=両方）
          skill_preset: スキルプリセット
          config: 設定リーダー（ConfigReader Protocol）

      Returns:
          Markdown形式のカルテレポート

      Note:
          この関数は katrain.gui をインポートしない（core層のみ）
      """
  ```
- **リスク**: MEDIUM（最大の抽出）
- **受入条件（v4統一: A対応）**:
  - **CI検証（自動）**:
    - 必須セクション存在テスト（「# カルテ」「## 重要局面」等）
    - アンカー形式テスト（手数/座標/損失パターン）
    - テンプレートプレースホルダ未残存テスト
    - `katrain/core/reports/` が `katrain.gui` をインポートしていないこと
  - **手動検証（PR作成時のみ）**:
    - リファクタリング前の出力を保存
    - 正規化diff（`_normalize_karte_for_comparison()`）で比較
    - 差分がないことを確認
  - 全テストパス

#### PR #120: important_moves_report.py抽出
- **ファイル**:
  - `katrain/core/reports/important_moves_report.py`（新規）
  - `katrain/core/game.py`（委譲）
- **内容**:
  - `build_important_moves_report()` を移動
  - `_iter_main_branch_nodes()` をユーティリティ化
  - `_compute_important_moves()` をユーティリティ化
- **重要**: `get_important_move_evals()`の`reason_tags`変更はGameに残す
- **抽出行数**: ~200行
- **リスク**: LOW-MEDIUM
- **受入条件**: 重要局面表示が正常動作

---

### Phase B3: KaTrainGui分割（PR #121-125）

#### 設計原則（v2改善）

**問題**: Managerが`self.katrain`を受け取ると「分散God Object」になる

**解決**: 各Managerに**明示的な依存のみ**を渡す

```python
# ❌ 悪い例（分散God Object）
class LeelaManager:
    def __init__(self, katrain: KaTrainGui):
        self.katrain = katrain  # 全てにアクセス可能

    def request_analysis(self):
        self.katrain.game.current_node  # 直接アクセス

# ✅ 良い例（明示的依存）
class LeelaManager:
    def __init__(
        self,
        config_getter: Callable[[str], Any],
        logger: Callable[[str, int], None],
        schedule_once: Callable[[Callable, float], None],
    ):
        self._config = config_getter
        self._log = logger
        self._schedule = schedule_once

    def request_analysis(self, node: GameNode, callback: Callable):
        # 必要なデータは引数で受け取る
```

#### PR #121: LeelaManager抽出
- **ファイル**:
  - `katrain/gui/leela_manager.py`（新規）
  - `katrain/__main__.py`（委譲）
- **内容**:
  - `start_leela_engine()`, `shutdown_leela_engine()`
  - `request_leela_analysis()`, `_set_leela_analysis()`
  - `_check_and_show_resign_hint()`
- **依存注入**:
  ```python
  class LeelaManager:
      def __init__(
          self,
          config_getter: Callable[[str], Any],
          logger: Callable[[str, int], None],
          schedule_once: Callable,
          show_resign_popup: Callable[[GameNode, float], None],
      ):
          ...

  # KaTrainGui.__init__で初期化
  self.leela_manager = LeelaManager(
      config_getter=self.config,
      logger=self.log,
      schedule_once=Clock.schedule_once,
      show_resign_popup=self._show_resign_hint_popup,
  )
  ```
- **リスク**: LOW-MEDIUM
- **受入条件**: Leela解析が正常動作

#### PR #122: SGFManager抽出
- **ファイル**:
  - `katrain/gui/sgf_manager.py`（新規）
  - `katrain/__main__.py`（委譲）
- **内容**:
  - `load_sgf_file()`, `_do_save_game()`
  - `load_sgf_from_clipboard()`
  - `_do_open_recent_sgf()`, `_show_recent_sgf_dropdown()`
- **依存注入**:
  ```python
  class SGFManager:
      def __init__(
          self,
          config_getter: Callable[[str], Any],
          config_setter: Callable[[str, Any], None],
          logger: Callable[[str, int], None],
          game_loader: Callable[[Game], None],  # ゲームをUIに設定
      ):
  ```
- **リスク**: LOW-MEDIUM
- **受入条件**: SGF読み書きが正常動作

#### PR #123: DialogCoordinator抽出
- **ファイル**:
  - `katrain/gui/dialog_coordinator.py`（新規）
  - `katrain/__main__.py`（委譲）
- **内容**:
  - `_do_*_popup` メソッド群（12メソッド）
- **依存注入**:
  ```python
  class DialogCoordinator:
      def __init__(
          self,
          config_getter: Callable[[str], Any],
          game_getter: Callable[[], Optional[Game]],
          engine_getter: Callable[[], Optional[KataGoEngine]],
          popup_callback: Callable[[Popup], None],  # ポップアップ表示
      ):
  ```
- **リスク**: MEDIUM
- **受入条件**: 全ダイアログが正常動作

#### PR #124: KeyboardController抽出
- **ファイル**:
  - `katrain/gui/keyboard_controller.py`（新規）
  - `katrain/__main__.py`（委譲）
- **内容**:
  - `_on_keyboard_down()`, `_on_keyboard_up()`
  - `shortcuts` プロパティ
- **依存注入**:
  ```python
  class KeyboardController:
      def __init__(
          self,
          action_dispatcher: Callable[[str, ...], None],
          popup_checker: Callable[[], Optional[Popup]],
          shortcuts_config: Dict[str, str],
      ):
  ```
- **リスク**: MEDIUM
- **受入条件**: 全ショートカットが正常動作

#### PR #125: KaTrainGuiクリーンアップ
- **ファイル**: `katrain/__main__.py`
- **内容**: 未使用インポート削除、ドキュメント追加
- **リスク**: LOW
- **受入条件**: 行数1,356→~700以下

---

### Phase B4: analysis/logic.py分割（PR #126-129）

#### PR #126: logic_loss.py作成
- **ファイル**:
  - `katrain/core/analysis/logic_loss.py`（新規）
  - `katrain/core/analysis/logic.py`（再エクスポート）
- **内容**:
  - `compute_canonical_loss()`
  - `classify_mistake()`
  - Loss関連ユーティリティ
- **リスク**: LOW

#### PR #127: logic_importance.py作成
- **ファイル**: `katrain/core/analysis/logic_importance.py`（新規）
- **内容**:
  - `compute_importance_for_moves()`
  - `pick_important_moves()`
  - 難易度評価
- **リスク**: LOW

#### PR #128: logic_quiz.py作成
- **ファイル**: `katrain/core/analysis/logic_quiz.py`（新規）
- **内容**:
  - `quiz_items_from_snapshot()`
  - Quiz生成ロジック
- **リスク**: LOW

#### PR #129: analysis/__init__.py更新
- **ファイル**: `katrain/core/analysis/__init__.py`
- **内容**: 新モジュールからの再エクスポート（後方互換）
- **リスク**: LOW

---

### Phase B5: ai.py分割（PR #130-132）

#### PR #130: ai_strategies_base.py作成
- **ファイル**: `katrain/core/ai_strategies_base.py`（新規）
- **内容**:
  - `AIStrategy` 基底クラス
  - `DefaultStrategy`, `HandicapStrategy`
- **リスク**: LOW

#### PR #131: ai_strategies_advanced.py作成
- **ファイル**: `katrain/core/ai_strategies_advanced.py`（新規）
- **内容**:
  - Ownership系戦略
  - Policy系戦略
- **リスク**: LOW

#### PR #132: ai.pyクリーンアップ
- **ファイル**: `katrain/core/ai.py`
- **内容**: ファサード化、再エクスポート
- **リスク**: LOW

---

### Phase B6: テスト・ドキュメント（PR #133-135）

#### PR #133: アーキテクチャテスト強化
- **ファイル**: `tests/test_architecture.py`（更新）
- **内容**:
  - 依存方向テスト追加
  - reports → game 方向のみ許可
  - gui → core 方向のみ許可
- **リスク**: LOW

#### PR #134: メトリクス自動生成スクリプト
- **ファイル**: `scripts/generate_metrics.py`（新規）
- **内容**:
  ```python
  """モジュール行数・テスト数の自動計測"""
  import os
  import subprocess

  def count_lines(path):
      with open(path) as f:
          return sum(1 for _ in f)

  def generate_metrics():
      metrics = {}
      for root, dirs, files in os.walk("katrain"):
          for f in files:
              if f.endswith(".py"):
                  path = os.path.join(root, f)
                  metrics[path] = count_lines(path)

      # テスト数
      result = subprocess.run(
          ["uv", "run", "pytest", "--collect-only", "-q"],
          capture_output=True, text=True
      )
      test_count = len([l for l in result.stdout.split("\n") if "::" in l])

      return {"files": metrics, "test_count": test_count}

  if __name__ == "__main__":
      import json
      print(json.dumps(generate_metrics(), indent=2))
  ```
- **リスク**: NONE

#### PR #135: ドキュメント更新
- **ファイル**:
  - `docs/02-code-structure.md`（更新）
  - `docs/phase19-architecture.md`（新規）
- **内容**: 新構造の説明、依存関係図
- **リスク**: NONE

---

## 4. PRサマリーテーブル（改訂版）

| PR | タイトル | 対象ファイル | リスク | 依存 |
|:--:|----------|--------------|:------:|:----:|
| **Phase B1: 循環依存** |
| #113 | DEFAULT_FONTをcommonに移動 | common/, lang.py, theme.py | LOW | - |
| #114 | アーキテクチャテスト基礎 | test_architecture.py | LOW | #113 |
| **Phase B2: game.py分割** |
| #115 | reports/パッケージ骨格 | reports/__init__.py, types.py | LOW | - |
| #116 | summary_report.py抽出 | reports/summary_report.py | LOW | #115 |
| #117 | quiz_report.py抽出 | reports/quiz_report.py | LOW | #115 |
| #118 | formatters.py抽出 | reports/formatters.py | LOW | #115 |
| #119 | karte_report.py抽出 | reports/karte_report.py | **MED** | #118 |
| #120 | important_moves_report.py抽出 | reports/important_moves_report.py | LOW-MED | #115 |
| **Phase B3: KaTrainGui分割** |
| #121 | LeelaManager抽出 | leela_manager.py | LOW-MED | - |
| #122 | SGFManager抽出 | sgf_manager.py | LOW-MED | - |
| #123 | DialogCoordinator抽出 | dialog_coordinator.py | MED | - |
| #124 | KeyboardController抽出 | keyboard_controller.py | MED | - |
| #125 | KaTrainGuiクリーンアップ | __main__.py | LOW | #121-124 |
| **Phase B4: analysis分割** |
| #126 | logic_loss.py作成 | logic_loss.py | LOW | - |
| #127 | logic_importance.py作成 | logic_importance.py | LOW | #126 |
| #128 | logic_quiz.py作成 | logic_quiz.py | LOW | #127 |
| #129 | analysis/__init__.py更新 | __init__.py | LOW | #128 |
| **Phase B5: ai.py分割** |
| #130 | ai_strategies_base.py作成 | ai_strategies_base.py | LOW | - |
| #131 | ai_strategies_advanced.py作成 | ai_strategies_advanced.py | LOW | #130 |
| #132 | ai.pyクリーンアップ | ai.py | LOW | #131 |
| **Phase B6: テスト・ドキュメント** |
| #133 | アーキテクチャテスト強化 | test_architecture.py | LOW | #125,#129,#132 |
| #134 | メトリクス自動生成 | scripts/generate_metrics.py | NONE | - |
| #135 | ドキュメント更新 | docs/*.md | NONE | #134 |

**合計**: 23 PR

---

## 5. リスクと緩和策（Top 10 v5改訂版）

| # | リスク | 影響度 | 緩和策 | v5改善 |
|---|--------|--------|--------|--------|
| 1 | **カルテ形式変更** | 🔴 HIGH | CI=構造テスト、手動=正規化diff | - |
| 2 | **分散God Object** | 🔴 HIGH | Manager依存を明示的に限定 | - |
| 3 | **Protocol型不一致** | 🟡 MED | 属性テスト、fixture使用、実型検証 | ✅ D: `Tuple[int,int]`修正 |
| 4 | **TYPE_CHECKING誤検出** | 🟡 MED | エイリアス追跡、Path(__file__)基準 | ✅ A: `import typing as t`対応 |
| 5 | **循環依存残存** | 🟡 MED | common/スコープ制限、副作用テスト強化 | ✅ B: Assign内Call検出 |
| 6 | **config_getter型安全性** | 🟢 LOW | FeatureContext.configと互換確認済み | ✅ C: 既存API確認 |
| 7 | **後方互換破壊** | 🟡 MED | 委譲メソッド残し段階的廃止 | - |
| 8 | **reason_tags変更漏れ** | 🟡 MED | `get_important_move_evals()`はGameに残す | - |
| 9 | **キーボードショートカット** | 🟡 MED | 全ショートカットの手動テスト | - |
| 10 | **pytest cwd依存** | 🟢 LOW | Path(__file__)基準でルート計算 | - |

---

## 5.1 common/ スコープルール（v5強化: B対応）

**原則**: `common/` は**ダンピンググラウンドにしない**

### 許可されるコンテンツ
| 種類 | 例 | 許可 |
|------|-----|:----:|
| **リテラル定数** | `DEFAULT_FONT = "..."`, `INFO_PV_COLOR = (1.0, 0.5, 0.0)` | ✅ |
| **型定義（Protocol）** | `class ConfigReader(Protocol): ...` | ✅ |
| **TypedDict** | `class KarteConfig(TypedDict): ...` | ✅ |
| **Enum** | `class ThemeMode(Enum): ...` | ✅ |

### 禁止されるコンテンツ（v5強化）
| 種類 | 例 | 理由 | 検出方法 |
|------|-----|------|----------|
| **トップレベル関数呼び出し** | `setup()`, `initialize()` | 副作用 | `ast.Expr` |
| **代入内の関数呼び出し** | `DEFAULT = os.getenv("X")` | 副作用 | `ast.Call` in Assign |
| **外部インポート** | `from katrain.core import ...` | 循環依存 | インポート検査 |
| **I/O操作** | `open()`, `Path().read_text()` | 副作用 | `ast.Call` |
| **ログ出力** | `print()`, `logging.info()` | 副作用 | `ast.Call` |

### 受入条件（PR #114で検証 v5強化）
```python
def test_common_no_side_effects(self):
    """common/に副作用コードがないことを検証（v5強化）"""
    # 1. トップレベルExpr（docstring以外）を禁止
    # 2. Assign/AnnAssign内のast.Callを禁止（os.getenv()等）
```

### 将来の拡張ルール
- 新しい定数/型を追加する場合は、**既存のファイルに追加**（新ファイル作成は慎重に）
- `common/` に追加する前に、**core/constants.py** で十分かを検討

---

## 6. 検証戦略（改訂版）

### 6.1 各PRの検証

```powershell
# 全テスト実行
uv run pytest tests -v

# 起動確認
python -m katrain

# アーキテクチャ検証（PR #114以降）
uv run pytest tests/test_architecture.py -v
```

### 6.2 カルテ出力テスト戦略（v4統一: CI vs 手動の明確化）

**v4設計方針（A対応）**:

| テストタイプ | 実行タイミング | 検証内容 | flaky リスク |
|-------------|---------------|----------|-------------|
| **構造テスト（CI）** | 全PR、自動 | セクション存在、アンカー形式 | ⭐ なし |
| **正規化diffテスト（手動）** | PR #119のみ、手動 | 完全出力一致（正規化後） | 🟢 低い |

**注意**: PR #119の「受入条件」にある「完全一致」は**正規化diff + 手動実行**を指す。CIには含めない。

```python
# tests/test_karte_output.py
"""カルテ出力テスト（v4: CI自動テスト + 手動diffユーティリティ）

v4改善:
- CI自動テスト: 構造のみ検証（flaky なし）
- 手動検証: 正規化diff関数を提供（PR #119作成時に使用）
"""
import re
import pytest
from pathlib import Path
from katrain.core.analysis.models import SkillPreset


# =============================================================================
# CI自動テスト（全PRで実行）
# =============================================================================

class TestKarteStructure:
    """カルテの構造検証（CI用: flaky なし）"""

    @pytest.fixture
    def sample_karte(self, sample_game):
        """テスト用カルテを生成"""
        return sample_game.build_karte_report(
            level=2,
            player_filter="B",
            skill_preset=SkillPreset.STANDARD,
        )

    def test_has_required_sections(self, sample_karte):
        """必須セクションが存在する"""
        required_sections = [
            "# カルテ",
            "## 対局情報",
            "## 重要局面",
        ]
        for section in required_sections:
            assert section in sample_karte, f"Missing section: {section}"

    def test_anchor_format(self, sample_karte):
        """アンカー形式が正しい（手数/座標/損失）

        非交渉事項: アンカーは必須（LLM連携の根拠として使用）
        期待形式: 「手45 D10 3.2目」のようなパターン
        """
        anchor_pattern = r"手\d+.*[A-HJ-T]\d{1,2}.*\d+\.?\d*目"
        assert re.search(anchor_pattern, sample_karte), (
            "Anchor format not found. Expected pattern like: 手45 D10 3.2目"
        )

    def test_no_template_placeholders(self, sample_karte):
        """テンプレートプレースホルダが残っていない"""
        # 明確に問題のあるプレースホルダのみチェック
        bad_placeholders = ["{{", "}}", "undefined", "{None}"]
        for ph in bad_placeholders:
            assert ph not in sample_karte, f"Placeholder found: {ph}"

    def test_markdown_format_valid(self, sample_karte):
        """Markdownとして有効な形式"""
        # 最低限のMarkdown構造
        assert sample_karte.startswith("#"), "Should start with heading"
        assert "\n" in sample_karte, "Should have multiple lines"


# =============================================================================
# 正規化ユーティリティ（手動検証用）
# =============================================================================

def normalize_floats(text: str, precision: int = 1) -> str:
    """float値を指定精度に正規化"""
    def replace_float(match):
        value = float(match.group(0))
        return f"{value:.{precision}f}"
    return re.sub(r"\d+\.\d+", replace_float, text)


def normalize_timestamps(text: str) -> str:
    """タイムスタンプをプレースホルダに置換"""
    pattern = r"\d{4}-\d{2}-\d{2}[T ]?\d{2}:\d{2}:\d{2}"
    return re.sub(pattern, "<TIMESTAMP>", text)


def normalize_karte_for_comparison(text: str) -> str:
    """カルテ比較用の完全正規化（手動検証用）

    使用タイミング: PR #119作成時のみ
    使用方法:
      1. リファクタリング前: old = normalize_karte_for_comparison(game.build_karte_report(...))
      2. リファクタリング後: new = normalize_karte_for_comparison(reports.karte_report.build_karte_report(...))
      3. assert old == new
    """
    result = text
    result = normalize_floats(result, precision=1)
    result = normalize_timestamps(result)
    result = re.sub(r"[ \t]+", " ", result)  # 連続空白を単一スペースに
    result = re.sub(r"\n{3,}", "\n\n", result)  # 連続改行を単一改行に
    return result.strip()


# =============================================================================
# 正規化ルールのテスト（CI: ユーティリティが動作することを保証）
# =============================================================================

class TestKarteNormalization:
    """正規化ユーティリティのテスト"""

    def test_normalize_floats(self):
        """float値の正規化"""
        text = "損失: 3.14159目, 勝率: 52.345%"
        normalized = normalize_floats(text, precision=1)
        assert "3.1目" in normalized
        assert "52.3%" in normalized

    def test_normalize_timestamps(self):
        """タイムスタンプの正規化"""
        text = "生成日時: 2026-01-15 14:30:45"
        normalized = normalize_timestamps(text)
        assert "2026-01-15 14:30:45" not in normalized
        assert "<TIMESTAMP>" in normalized

    def test_full_normalization_is_idempotent(self):
        """正規化は冪等（2回適用しても同じ結果）"""
        text = "手45 D10 3.14159目\n\n\n生成: 2026-01-15 10:00:00"
        once = normalize_karte_for_comparison(text)
        twice = normalize_karte_for_comparison(once)
        assert once == twice


# =============================================================================
# 手動検証スクリプト（PR #119作成時にのみ使用）
# =============================================================================

def manual_diff_check(old_karte: str, new_karte: str) -> tuple[bool, str]:
    """手動検証用: 正規化後の差分チェック

    Returns:
        (is_equal, diff_message)
    """
    old_normalized = normalize_karte_for_comparison(old_karte)
    new_normalized = normalize_karte_for_comparison(new_karte)

    if old_normalized == new_normalized:
        return True, "No differences after normalization"

    # 差分を報告
    old_lines = old_normalized.split("\n")
    new_lines = new_normalized.split("\n")

    diff_lines = []
    for i, (o, n) in enumerate(zip(old_lines, new_lines)):
        if o != n:
            diff_lines.append(f"Line {i+1}:")
            diff_lines.append(f"  OLD: {o[:80]}")
            diff_lines.append(f"  NEW: {n[:80]}")
            if len(diff_lines) > 30:  # 最大10箇所
                diff_lines.append("... (truncated)")
                break

    return False, "\n".join(diff_lines)
```

**PR #119 手動検証手順**:
```powershell
# 1. リファクタリング前の出力を保存
python -c "
from katrain.core.game import Game
# ... sample_game生成
old = sample_game.build_karte_report(level=2, player_filter='B', ...)
with open('old_karte.md', 'w') as f: f.write(old)
"

# 2. リファクタリング後の出力を取得
python -c "
from katrain.core.reports import karte_report
# ... 新API呼び出し
new = karte_report.build_karte_report(...)
with open('new_karte.md', 'w') as f: f.write(new)
"

# 3. 正規化diff確認（Pythonで）
python -c "
from tests.test_karte_output import manual_diff_check
old = open('old_karte.md').read()
new = open('new_karte.md').read()
is_eq, msg = manual_diff_check(old, new)
print(f'Equal: {is_eq}')
print(msg)
"
```

### 6.3 手動スモークテスト（Phase完了時）

| チェック項目 | 対象PR | 確認手順 |
|--------------|--------|----------|
| 循環依存解消 | #113 | `python -c "from katrain.core.lang import Lang"` |
| サマリーエクスポート | #116 | バッチ解析 → サマリー出力 |
| クイズ生成 | #117 | クイズポップアップ開始 |
| カルテエクスポート | #119 | SGF読み込み → カルテエクスポート |
| Leela解析 | #121 | Leelaモード → 解析実行 |
| SGF読み書き | #122 | SGF読み込み/保存 |
| ダイアログ | #123 | 設定/新規ゲーム/保存ダイアログ |
| ショートカット | #124 | Ctrl+Z, Space, 矢印キー |
| AI対局 | #132 | AI対局開始 |

---

## 7. 実行計画

### 前提条件
- [x] Phase 18完了（✅ 完了）
- [x] 843テスト全パス（✅ 確認済み）
- [x] ユーザー承認 → **Option B選択、game.py分割から開始**

### 実行順序（確定）
1. **Phase B1**: 循環依存解消（PR #113-114）← **最初**
2. **Phase B2**: game.py → reports/（PR #115-120）
3. **Phase B3**: KaTrainGui分割（PR #121-125）
4. **Phase B4**: analysis分割（PR #126-129）
5. **Phase B5**: ai.py分割（PR #130-132）
6. **Phase B6**: テスト・ドキュメント（PR #133-135）

### 並行実行ガイダンス（v3改善: 実践的アドバイス）

**単独開発者（sentoku870）向け推奨**:

| 状況 | 推奨 | 理由 |
|------|------|------|
| 通常作業 | **順次実行** | コンフリクト回避、レビュー品質向上 |
| 急ぎの場合 | 並行可能（下記参照） | ただしマージ順序に注意 |

**並行実行可能なPR**（理論上）:
- Phase B1完了後、Phase B2とB3は並行可能
- Phase B4とB5は並行可能

**並行実行時の注意**:
1. **マージ順序**: 依存関係のあるPRは必ず順番にマージ
2. **コンフリクト**: `__init__.py` や `__main__.py` で発生しやすい
3. **推奨**: 同じフェーズ内のPRは順次実行が安全

**実践的なワークフロー**:
```
# 推奨: 1PR完了 → 次のPRへ
PR #113 → merge → PR #114 → merge → PR #115 → ...

# 急ぎの場合のみ: ブランチ並行作成（マージは順次）
git switch -c feature/pr-116-summary  # 作業開始
git switch -c feature/pr-117-quiz     # 並行して作業開始
# マージは必ず 116 → 117 の順序で
```

---

## 8. ファイルサイズ予測

### Before（現状）
| ファイル | 行数 |
|----------|------|
| game.py | 2,883 |
| __main__.py (KaTrainGui) | 1,356 |
| analysis/logic.py | 1,770 |
| ai.py | 1,459 |

### After（予測）
| ファイル | 行数 |
|----------|------|
| game.py | ~800 |
| reports/karte_report.py | ~800 |
| reports/summary_report.py | ~400 |
| reports/quiz_report.py | ~100 |
| reports/important_moves_report.py | ~200 |
| reports/formatters.py | ~300 |
| __main__.py | ~700 |
| gui/leela_manager.py | ~160 |
| gui/sgf_manager.py | ~170 |
| gui/dialog_coordinator.py | ~350 |
| gui/keyboard_controller.py | ~150 |
| analysis/logic_loss.py | ~400 |
| analysis/logic_importance.py | ~600 |
| analysis/logic_quiz.py | ~300 |
| ai_strategies_base.py | ~400 |
| ai_strategies_advanced.py | ~800 |

**総行数は同じだが、責務ごとに分離**

---

## 変更履歴

| 日時 | 内容 |
|------|------|
| 2026-01-15 | 初版作成 - Architecture Snapshot + Option A/B/C + 20 PR計画 |
| 2026-01-15 | ユーザー承認: Option B選択、game.py分割から開始 |
| 2026-01-15 | **v2改訂** - 技術レビュー反映 |
| | - **A) 循環依存**: ui_constants.py → common/theme_constants.py活用 |
| | - **B) game.py分割**: 2ファイル → reports/サブパッケージ（5モジュール） |
| | - **C) KaTrainGui**: 分散God Object防止 → 明示的依存注入 |
| | - **D) アーキテクチャテスト**: TYPE_CHECKING許可 + 許可リスト |
| | - **E) メトリクス**: 自動生成スクリプト追加 |
| | - PR数: 20 → 23（より細分化） |
| 2026-01-15 | **v3改訂** - 実装詳細レビュー反映 |
| | - **A) ASTテスト**: ast.walk() → ast.NodeVisitor（TYPE_CHECKINGを正確にスキップ） |
| | - **B) Protocol**: 一括定義 → 段階的拡張（@runtime_checkable + 互換性テスト） |
| | - **C) カルテテスト**: ゴールデン比較 → 構造テスト + 正規化ルール（flaky防止） |
| | - **D) 並行実行**: 単独開発者向け順次実行推奨、並行時の注意点追記 |
| | - **E) common/検証**: test_common_has_no_core_or_gui_imports() 追加 |
| 2026-01-15 | **v4改訂** - アーキテクトレビュー反映 |
| | - **A) カルテテスト**: PR#119受入条件を統一（CI=構造、手動=正規化diff） |
| | - **B) ASTテスト**: TYPE_CHECKINGインポート追跡、Path(__file__)基準、相対インポート対応 |
| | - **C) Protocol互換性**: runtime_checkable廃止 → 属性テスト、sample_game fixture使用 |
| | - **D) config_getter**: `Callable[[str], Any]` → `ConfigReader` Protocol明示定義 |
| | - **E) common/スコープ**: 厳格ルール定義（定数/型のみ、副作用禁止）、テスト追加 |
| | - リスク表更新: v4改善列追加、pytest cwd依存リスク追加 |
| 2026-01-15 | **v5改訂** - 最終レビュー反映 |
| | - **A) ASTテスト強化**: `import typing as t`エイリアス対応、相対インポートテストで明示的アサート |
| | - **B) common/副作用テスト強化**: Assign/AnnAssign内の`ast.Call`検出（os.getenv()等） |
| | - **C) ConfigReader確認**: 既存FeatureContext.configと同一シグネチャ確認 → 再利用可 |
| | - **D) Protocol型修正**: `board_size: int` → `Tuple[int, int]`（実際のGame実装に合わせる） |
| | - リスク表更新: v5改善列追加、リスク#6の影響度をLOWに下げる |
