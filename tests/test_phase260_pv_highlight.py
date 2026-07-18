"""Phase 260 (I-13): hint highlight の PV アニメ同期

PV アニメ中はクロックコールバックが ``draw_hover_contents`` だけを再実行するため、
beginner hint highlight が消えてしまう問題があった。Phase 260 で
``draw_hover_contents`` 内の canvas.after ブロックに highlight 呼び出しを追加し、
アニメ中でも highlight が再描画されるようにする。

このテストは:
- draw_hover_contents 内の canvas.after ブロックに highlight 呼び出しがあること
- 既存呼び出し (draw_board_contents 内) が残存していること
- 呼び出し位置が draw_pass_circle の後であること
を AST ガードで検証する。
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HINTS_PATH = REPO_ROOT / "katrain" / "gui" / "badukpan_hints.py"
DRAWING_PATH = REPO_ROOT / "katrain" / "gui" / "badukpan_drawing.py"


def _load_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _with_block_calls(func: ast.FunctionDef, canvas_attr: str) -> list[ast.Call]:
    """``with widget.canvas.{canvas_attr}:`` ブロック内の全 Call を順序付きで返す。"""
    calls: list[ast.Call] = []
    for stmt in func.body:
        if not isinstance(stmt, ast.With):
            continue
        # with widget.canvas.after: / with widget.canvas:
        for item in stmt.items:
            ctx = item.context_expr
            if (
                isinstance(ctx, ast.Attribute)
                and ctx.attr == canvas_attr
                and isinstance(ctx.value, ast.Attribute)
                and ctx.value.attr == "canvas"
            ):
                for sub in stmt.body:
                    for sub_node in ast.walk(sub):
                        if isinstance(sub_node, ast.Call):
                            calls.append(sub_node)
    return calls


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


# -----------------------------------------------------------------------------
# draw_hover_contents 側の検証
# -----------------------------------------------------------------------------


def test_draw_hover_contents_calls_beginner_hint_highlight() -> None:
    """draw_hover_contents 内の canvas.after ブロックで highlight が呼ばれている。"""
    tree = _load_tree(HINTS_PATH)
    func = _find_function(tree, "draw_hover_contents")
    assert func is not None, "draw_hover_contents が badukpan_hints.py に存在すること"

    after_calls = _with_block_calls(func, "after")
    names = [_call_name(c) for c in after_calls]
    assert "draw_beginner_hint_highlight" in names, (
        f"canvas.after ブロックに draw_beginner_hint_highlight 呼び出しが必要。actual={names}"
    )


def test_draw_hover_contents_highlight_after_pass_circle() -> None:
    """highlight 呼び出しが draw_pass_circle の後にある（描画順序の保証）。"""
    tree = _load_tree(HINTS_PATH)
    func = _find_function(tree, "draw_hover_contents")
    assert func is not None

    after_calls = _with_block_calls(func, "after")
    names = [_call_name(c) for c in after_calls]

    pass_idx = names.index("draw_pass_circle")
    highlight_idx = names.index("draw_beginner_hint_highlight")
    assert highlight_idx > pass_idx, (
        f"highlight ({highlight_idx}) は draw_pass_circle ({pass_idx}) より後で呼ぶこと"
    )


# -----------------------------------------------------------------------------
# draw_board_contents 側のフォールバック保持検証
# -----------------------------------------------------------------------------


def test_draw_board_contents_still_calls_beginner_hint_highlight() -> None:
    """既存フォールバック呼び出し (テーマ変更時の赤パス用) は残っている。"""
    tree = _load_tree(DRAWING_PATH)
    func = _find_function(tree, "draw_board_contents")
    assert func is not None

    # draw_board_contents 内の任意の Call を walk
    found = False
    for sub in ast.walk(func):
        if isinstance(sub, ast.Call) and _call_name(sub) == "draw_beginner_hint_highlight":
            found = True
            break
    assert found, "draw_board_contents 内のフォールバック呼び出しは残すこと"


# -----------------------------------------------------------------------------
# ラッパー存在の確認
# -----------------------------------------------------------------------------


def test_widget_wrapper_still_exists() -> None:
    """widget.draw_beginner_hint_highlight ラッパーが badukpan.py に存在すること。"""
    badukpan_path = REPO_ROOT / "katrain" / "gui" / "badukpan.py"
    tree = _load_tree(badukpan_path)
    # BadukPanWidget クラス内のメソッドとして定義されている
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "BadukPanWidget":
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == "draw_beginner_hint_highlight":
                    return
    raise AssertionError("BadukPanWidget.draw_beginner_hint_highlight が見つからない")
