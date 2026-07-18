"""Phase 267: Curator profile 2 ソース fallback

``_resolve_curator_profile_path`` を 2 ソースに拡張:
  1. ``karte_output_directory`` (canonical)
  2. ``batch_options.output_dir`` (fallback)

ユーザーが Batch 分析の output_dir を指定してるが
``karte_output_directory`` が空の場合、 profile が load されない
問題に対応。"""

import ast

# 重要: ``karte_export`` の import は Kivy graphics 初期化を要求するため、
# 関数を AST 経由で隔離実行してテストする。
import os
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
KARTE_EXPORT_PATH = REPO_ROOT / "katrain" / "gui" / "features" / "karte_export.py"


def _load_resolver_isolated() -> callable:
    tree = ast.parse(KARTE_EXPORT_PATH.read_text(encoding="utf-8"))
    func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_resolve_curator_profile_path":
            func = node
            break
    assert func is not None

    import glob as _glob

    ns = {
        "os": os,
        "glob": _glob,
        "FeatureContext": object,
    }
    exec(compile(ast.Module(body=[func], type_ignores=[]), "<test>", "exec"), ns)
    return ns["_resolve_curator_profile_path"]


def _ctx_with(mykatrain_settings: dict) -> SimpleNamespace:
    return SimpleNamespace(
        config=lambda key, default=None: mykatrain_settings if key == "mykatrain_settings" else default
    )


# -----------------------------------------------------------------------------
# 1. karte_output_directory のみ
# -----------------------------------------------------------------------------


def test_karte_dir_only_canonical(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    canonical = tmp_path / "curator_ranking.json"
    canonical.write_text("{}")
    result = fn(_ctx_with({"karte_output_directory": str(tmp_path)}))
    assert result is not None
    assert os.path.normpath(result) == os.path.normpath(str(canonical))


def test_karte_dir_only_timestamped(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    p = tmp_path / "curator_ranking_20260718-125952.json"
    p.write_text("{}")
    result = fn(_ctx_with({"karte_output_directory": str(tmp_path)}))
    assert result is not None
    assert os.path.normpath(result) == os.path.normpath(str(p))


# -----------------------------------------------------------------------------
# 2. batch_options.output_dir のみ (Phase 267: 新規対応)
# -----------------------------------------------------------------------------


def test_batch_dir_only_finds_profile(tmp_path: Path) -> None:
    """karte_output_directory が空で batch output_dir に profile がある。"""
    fn = _load_resolver_isolated()
    p = tmp_path / "curator_ranking_20260718-125952.json"
    p.write_text("{}")
    result = fn(
        _ctx_with(
            {
                "karte_output_directory": "",
                "batch_options": {"output_dir": str(tmp_path)},
            }
        )
    )
    assert result is not None, "batch_options.output_dir に profile がある時は load する (Phase 267 の新動作)"
    assert os.path.normpath(result) == os.path.normpath(str(p))


def test_batch_dir_only_with_canonical(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    canonical = tmp_path / "curator_ranking.json"
    canonical.write_text("{}")
    result = fn(
        _ctx_with(
            {
                "karte_output_directory": "",
                "batch_options": {"output_dir": str(tmp_path)},
            }
        )
    )
    assert result is not None
    assert os.path.normpath(result) == os.path.normpath(str(canonical))


# -----------------------------------------------------------------------------
# 3. 両方ある時は karte_output_directory を優先
# -----------------------------------------------------------------------------


def test_karte_dir_takes_precedence_over_batch_dir(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    karte_dir = tmp_path / "karte"
    karte_dir.mkdir()
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    karte_canonical = karte_dir / "curator_ranking.json"
    karte_canonical.write_text("{}")
    batch_canonical = batch_dir / "curator_ranking.json"
    batch_canonical.write_text("{}")

    result = fn(
        _ctx_with(
            {
                "karte_output_directory": str(karte_dir),
                "batch_options": {"output_dir": str(batch_dir)},
            }
        )
    )
    assert result is not None
    # karte_output_directory の方が優先
    assert os.path.normpath(result) == os.path.normpath(str(karte_canonical))


def test_karte_dir_empty_falls_back_to_batch_dir(tmp_path: Path) -> None:
    """karte が空文字 → batch にフォールバック。"""
    fn = _load_resolver_isolated()
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    batch_canonical = batch_dir / "curator_ranking.json"
    batch_canonical.write_text("{}")

    result = fn(
        _ctx_with(
            {
                "karte_output_directory": "",
                "batch_options": {"output_dir": str(batch_dir)},
            }
        )
    )
    assert result is not None
    assert os.path.normpath(result) == os.path.normpath(str(batch_canonical))


# -----------------------------------------------------------------------------
# 4. どちらにも無い
# -----------------------------------------------------------------------------


def test_no_dirs_returns_none() -> None:
    fn = _load_resolver_isolated()
    result = fn(_ctx_with({}))
    assert result is None


def test_both_dirs_empty_returns_none() -> None:
    fn = _load_resolver_isolated()
    result = fn(
        _ctx_with(
            {
                "karte_output_directory": "",
                "batch_options": {"output_dir": ""},
            }
        )
    )
    assert result is None


def test_dirs_exist_but_no_profile_returns_none(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    result = fn(
        _ctx_with(
            {
                "karte_output_directory": str(tmp_path),
                "batch_options": {"output_dir": str(tmp_path)},
            }
        )
    )
    assert result is None


# -----------------------------------------------------------------------------
# 5. 同じ dir が両方に登録されてる (重複防止)
# -----------------------------------------------------------------------------


def test_duplicate_dirs_not_searched_twice(tmp_path: Path) -> None:
    """karte_output_directory == batch_options.output_dir の場合、
    canonical 検索を 2 回しない。"""
    fn = _load_resolver_isolated()
    canonical = tmp_path / "curator_ranking.json"
    canonical.write_text("{}")
    result = fn(
        _ctx_with(
            {
                "karte_output_directory": str(tmp_path),
                "batch_options": {"output_dir": str(tmp_path)},
            }
        )
    )
    assert result is not None
    assert os.path.normpath(result) == os.path.normpath(str(canonical))
