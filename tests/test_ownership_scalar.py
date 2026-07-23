"""Phase 263 (Phase 259 follow-up): ownership のスカラー化ヘルパー

KataGo は ``current_node.analysis["ownership"]`` を ``list[float]``
(盤の各点の ownership 値) で書き出す。Phase 259 ではこれを
``move_dict.get("ownership", 0.0)`` で読もうとして
``TypeError: '>=' not supported between instances of 'list' and 'int'``
で起動時クラッシュしていた。

``_resolve_ownership_scalar`` ヘルパーで 3 形式 (move_dict scalar /
move_dict list / node-level analysis list) を全て ``[-1.0, +1.0]`` の
scalar に縮約する。
"""

import ast
from pathlib import Path
from types import SimpleNamespace

# ``badukpan_hints`` の import は Kivy graphics 初期化エラーを起こすので、
# AST 解析 + 関数のソース直接実行で検証する。

REPO_ROOT = Path(__file__).resolve().parent.parent
HINTS_PATH = REPO_ROOT / "katrain" / "gui" / "badukpan_hints.py"


class _Approx:
    def __init__(self, expected: float, tol: float) -> None:
        self.expected = expected
        self.tol = tol

    def __eq__(self, other: object) -> bool:
        return isinstance(other, (int, float)) and abs(float(other) - self.expected) <= self.tol

    def __repr__(self) -> str:
        return f"approx({self.expected} ± {self.tol})"


def _approx(value: float, abs_tol: float = 1e-9) -> _Approx:
    return _Approx(value, abs_tol)


def _load_helper_isolated() -> callable:
    tree = ast.parse(HINTS_PATH.read_text(encoding="utf-8"))
    func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_resolve_ownership_scalar":
            func = node
            break
    assert func is not None, "_resolve_ownership_scalar が badukpan_hints.py に存在すること"

    from typing import Any

    ns: dict = {"Any": Any}
    exec(compile(ast.Module(body=[func], type_ignores=[]), "<test>", "exec"), ns)
    return ns["_resolve_ownership_scalar"]


# -----------------------------------------------------------------------------
# ヘルパーロード
# -----------------------------------------------------------------------------


def test_helper_loadable() -> None:
    fn = _load_helper_isolated()
    assert callable(fn)


# -----------------------------------------------------------------------------
# move_dict["ownership"] が scalar の場合
# -----------------------------------------------------------------------------


def test_scalar_in_move_dict_positive() -> None:
    fn = _load_helper_isolated()
    assert fn({"ownership": 0.5}, SimpleNamespace(analysis={})) == 0.5


def test_scalar_in_move_dict_negative() -> None:
    fn = _load_helper_isolated()
    assert fn({"ownership": -0.3}, SimpleNamespace(analysis={})) == -0.3


def test_scalar_in_move_dict_clamped() -> None:
    fn = _load_helper_isolated()
    assert fn({"ownership": 2.5}, SimpleNamespace(analysis={})) == 1.0
    assert fn({"ownership": -2.5}, SimpleNamespace(analysis={})) == -1.0


# -----------------------------------------------------------------------------
# move_dict["ownership"] が list[float] の場合 (バグ修正対象)
# -----------------------------------------------------------------------------


def test_list_in_move_dict_averaged() -> None:
    """list[float] の場合は平均を返す。"""
    fn = _load_helper_isolated()
    # 黒 80%, 白 20% → 平均 0.6
    ownership = [1.0] * 80 + [-1.0] * 20
    assert fn({"ownership": ownership}, SimpleNamespace(analysis={})) == _approx(0.6)


def test_list_in_move_dict_empty_returns_zero() -> None:
    fn = _load_helper_isolated()
    assert fn({"ownership": []}, SimpleNamespace(analysis={})) == 0.0


def test_list_in_move_dict_clamped() -> None:
    fn = _load_helper_isolated()
    # 全ポイント +1.0 → 平均 +1.0 (clamp 境界)
    assert fn({"ownership": [1.0] * 361}, SimpleNamespace(analysis={})) == 1.0


# -----------------------------------------------------------------------------
# node.analysis["ownership"] が list[float] の場合 (KataGo の本物の shape)
# -----------------------------------------------------------------------------


def test_node_analysis_list_kata_shape() -> None:
    """KataGo の標準形式: current_node.analysis["ownership"] が list[float]。"""
    fn = _load_helper_isolated()
    node = SimpleNamespace(analysis={"ownership": [0.8] * 100 + [-0.5] * 50})
    # 平均 = (0.8*100 + -0.5*50) / 150 = (80 - 25) / 150 ≈ 0.3666...
    assert fn({}, node) == _approx(55 / 150)


def test_node_analysis_scalar() -> None:
    fn = _load_helper_isolated()
    node = SimpleNamespace(analysis={"ownership": -0.42})
    assert fn({}, node) == -0.42


# -----------------------------------------------------------------------------
# 何も無い場合 → 0.0 (クラッシュしない)
# -----------------------------------------------------------------------------


def test_no_ownership_returns_zero() -> None:
    fn = _load_helper_isolated()
    assert fn({}, SimpleNamespace(analysis={})) == 0.0
    assert fn({}, SimpleNamespace(analysis=None)) == 0.0


def test_empty_dict_and_no_node_analysis() -> None:
    fn = _load_helper_isolated()
    # current_node.analysis 属性自体が無い
    assert fn({}, SimpleNamespace()) == 0.0


# -----------------------------------------------------------------------------
# 不正入力への防御
# -----------------------------------------------------------------------------


def test_invalid_list_contents_return_zero() -> None:
    """list 内に文字列などが混じっててもクラッシュしない。"""
    fn = _load_helper_isolated()
    # 全要素 float 変換失敗 → 0.0
    node = SimpleNamespace(analysis={"ownership": ["abc", "xyz"]})
    assert fn({}, node) == 0.0


def test_non_dict_move_dict() -> None:
    """move_dict が dict でなくてもクラッシュしない。"""
    fn = _load_helper_isolated()
    assert fn(None, SimpleNamespace(analysis={})) == 0.0


def test_bool_treated_as_invalid() -> None:
    """bool は int の subclass だが、True/False は ownership として不適切。"""
    fn = _load_helper_isolated()
    # 実装では isinstance(raw, bool) で弾くので 0.0
    assert fn({"ownership": True}, SimpleNamespace(analysis={})) == 0.0
