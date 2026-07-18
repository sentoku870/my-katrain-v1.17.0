"""Phase 261 (I-14): 候補手マーカーに Mistake Severity アイコン

KataGo の ``pointsLost`` を 4 段階 (good / inaccuracy / mistake / blunder)
の severity に分類し、mistake と blunder には外周リングを描画する。
色は Theme.MISTAKE_SEVERITY_{MISTAKE,BLUNDER}_RING で決まる。

Note: ``katrain.gui.badukpan_hints`` の import には Kivy graphics が
必要で、headless CI / Windows agent で ``dp(None)`` TypeError になる。
そのためヘルパーロジックは AST 解析 + 関数のソース直接実行で検証する。
"""

import ast
import importlib
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
THEME_PATH = REPO_ROOT / "katrain" / "gui" / "theme.py"
HINTS_PATH = REPO_ROOT / "katrain" / "gui" / "badukpan_hints.py"


# -----------------------------------------------------------------------------
# AST 解析ユーティリティ
# -----------------------------------------------------------------------------


def _load_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _find_assign(tree: ast.Module, name: str) -> ast.Assign | ast.AnnAssign | None:
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return node
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return node
    return None


# -----------------------------------------------------------------------------
# ソース直接実行ヘルパー
# -----------------------------------------------------------------------------


def _exec_helper_isolated() -> dict:
    """``_resolve_mistake_severity`` を Kivy 非依存で単体ロードする。"""
    tree = _load_tree(HINTS_PATH)
    func = _find_function(tree, "_resolve_mistake_severity")
    assert func is not None, "_resolve_mistake_severity が badukpan_hints に存在すること"

    table = _find_assign(tree, "_MISTAKE_SEVERITY_THRESHOLDS")
    assert table is not None, "_MISTAKE_SEVERITY_THRESHOLDS テーブルが存在すること"

    # テーブルとヘルパー関数のソースを切り出し、隔離 namespace で実行
    ns: dict = {}
    exec(compile(ast.Module(body=[table, func], type_ignores=[]), "<test>", "exec"), ns)
    return ns


# -----------------------------------------------------------------------------
# 閾値マッピング
# -----------------------------------------------------------------------------


def test_severity_good_band() -> None:
    ns = _exec_helper_isolated()
    fn = ns["_resolve_mistake_severity"]
    assert fn(0.0) == "good"
    assert fn(0.1) == "good"
    assert fn(0.49) == "good"


def test_severity_inaccuracy_band() -> None:
    ns = _exec_helper_isolated()
    fn = ns["_resolve_mistake_severity"]
    assert fn(0.5) == "inaccuracy"
    assert fn(0.7) == "inaccuracy"
    assert fn(0.99) == "inaccuracy"


def test_severity_mistake_band() -> None:
    ns = _exec_helper_isolated()
    fn = ns["_resolve_mistake_severity"]
    assert fn(1.0) == "mistake"
    assert fn(1.5) == "mistake"
    assert fn(2.99) == "mistake"


def test_severity_blunder_band() -> None:
    ns = _exec_helper_isolated()
    fn = ns["_resolve_mistake_severity"]
    assert fn(3.0) == "blunder"
    assert fn(5.0) == "blunder"
    assert fn(100.0) == "blunder"


def test_severity_handles_invalid_input() -> None:
    ns = _exec_helper_isolated()
    fn = ns["_resolve_mistake_severity"]
    assert fn(None) == "good"
    assert fn("abc") == "good"
    assert fn([1.0]) == "good"


def test_severity_handles_negative() -> None:
    """負値 (通常は起きないが防御的に) は good 扱い。"""
    ns = _exec_helper_isolated()
    fn = ns["_resolve_mistake_severity"]
    assert fn(-1.0) == "good"


# -----------------------------------------------------------------------------
# Theme 定数の存在 (実 import)
# -----------------------------------------------------------------------------


def _load_theme_class() -> type:
    theme_mod = importlib.import_module("katrain.gui.theme")
    return getattr(theme_mod, "Theme")


def test_theme_has_severity_constants() -> None:
    Theme = _load_theme_class()
    assert hasattr(Theme, "MISTAKE_SEVERITY_MISTAKE_RING")
    assert hasattr(Theme, "MISTAKE_SEVERITY_BLUNDER_RING")
    assert hasattr(Theme, "MISTAKE_SEVERITY_RING_WIDTH")

    # 4-tuple (rgba) であること
    assert len(Theme.MISTAKE_SEVERITY_MISTAKE_RING) == 4
    assert len(Theme.MISTAKE_SEVERITY_BLUNDER_RING) == 4

    # Ring width は正の数値
    assert isinstance(Theme.MISTAKE_SEVERITY_RING_WIDTH, (int, float))
    assert Theme.MISTAKE_SEVERITY_RING_WIDTH > 0


def test_theme_severity_distinct_colors() -> None:
    """mistake と blunder のリング色が別 (混同しない)。"""
    Theme = _load_theme_class()
    assert Theme.MISTAKE_SEVERITY_MISTAKE_RING != Theme.MISTAKE_SEVERITY_BLUNDER_RING


# -----------------------------------------------------------------------------
# draw_kata_hint_marker 内の severity 描画パス (AST guard)
# -----------------------------------------------------------------------------


def test_draw_kata_hint_marker_has_severity_block() -> None:
    """draw_kata_hint_marker 内に ``_resolve_mistake_severity`` 呼び出しがある。"""
    tree = _load_tree(HINTS_PATH)
    func = _find_function(tree, "draw_kata_hint_marker")
    assert func is not None

    found = False
    for sub in ast.walk(func):
        if isinstance(sub, ast.Call) and getattr(sub.func, "id", None) == "_resolve_mistake_severity":
            found = True
            break
    assert found, "_resolve_mistake_severity が draw_kata_hint_marker から呼ばれていない"


def test_severity_ring_uses_theme_constants() -> None:
    """draw_kata_hint_marker 内で MISTAKE_SEVERITY_*_RING またはテーブル参照。"""
    tree = _load_tree(HINTS_PATH)
    func = _find_function(tree, "draw_kata_hint_marker")
    assert func is not None

    text = ast.unparse(func)
    assert "MISTAKE_SEVERITY_MISTAKE_RING" in text or "_MISTAKE_SEVERITY_RING_COLORS" in text, (
        "MISTAKE_SEVERITY_*_RING 定数または _MISTAKE_SEVERITY_RING_COLORS テーブルへの参照が必要"
    )


# -----------------------------------------------------------------------------
# _MISTAKE_SEVERITY_THRESHOLDS / RING_COLORS の整合性 (AST 解析)
# -----------------------------------------------------------------------------


def test_threshold_table_shape() -> None:
    """_MISTAKE_SEVERITY_THRESHOLDS は 4 要素タプル (threshold, label)。"""
    tree = _load_tree(HINTS_PATH)
    table = _find_assign(tree, "_MISTAKE_SEVERITY_THRESHOLDS")
    assert table is not None

    val = table.value if isinstance(table, ast.Assign) else table.value
    assert isinstance(val, ast.Tuple), "_MISTAKE_SEVERITY_THRESHOLDS はタプル"

    labels: list[str] = []
    thresholds: list[float] = []
    for elt in val.elts:
        assert isinstance(elt, ast.Tuple) and len(elt.elts) == 2
        thr, lbl = elt.elts
        # threshold は Constant (数値) または float("inf") の Call
        if isinstance(thr, ast.Constant):
            assert isinstance(thr.value, (int, float))
            thresholds.append(float(thr.value))
        elif isinstance(thr, ast.Call):
            # float("inf") のみ想定
            assert isinstance(thr.func, ast.Name) and thr.func.id == "float"
            thresholds.append(float("inf"))
        else:
            raise AssertionError(f"unexpected threshold node: {type(thr).__name__}")
        assert isinstance(lbl, ast.Constant) and isinstance(lbl.value, str)
        labels.append(lbl.value)

    assert labels == ["good", "inaccuracy", "mistake", "blunder"]
    # 閾値が昇順
    assert thresholds == sorted(thresholds)


def test_ring_color_table_shape() -> None:
    """_MISTAKE_SEVERITY_RING_COLORS は 4 ラベル・mistake/blunder のみ色あり。"""
    tree = _load_tree(HINTS_PATH)
    table = _find_assign(tree, "_MISTAKE_SEVERITY_RING_COLORS")
    assert table is not None

    # 値生成のため exec (Theme は実 import で渡す)
    Theme = _load_theme_class()
    ns: dict = {"Theme": Theme}
    mod = ast.Module(body=[table], type_ignores=[])
    exec(compile(mod, "<test>", "exec"), ns)
    colors = ns["_MISTAKE_SEVERITY_RING_COLORS"]
    assert set(colors.keys()) == {"good", "inaccuracy", "mistake", "blunder"}
    assert colors["good"] is None
    assert colors["inaccuracy"] is None
    assert colors["mistake"] is not None
    assert colors["blunder"] is not None
