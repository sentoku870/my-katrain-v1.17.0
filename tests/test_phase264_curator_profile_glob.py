"""Phase 264: Curator profile loader の glob 対応

PR #423 (Phase 248-γ-E1) で ``_resolve_curator_profile_path`` は
固定名 ``curator_ranking.json`` しか探さなかったが、 Batch 分析の
``generate_curator_outputs`` は ``curator_ranking_<timestamp>.json``
を生成する。 ファイル名不一致で Hint 機能の Curated weak-axis
カテゴリが活性化しない問題があった。

Phase 264 で canonical 固定名を優先しつつ、 無ければ glob で
``curator_ranking_*.json`` の最新 mtime を返すよう拡張。
"""

# ``karte_export`` の import は Kivy graphics 初期化を要求するため、
# 関数を AST 経由で隔離実行してテストする。
import ast
import os
import time
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
    assert func is not None, "_resolve_curator_profile_path が見つからない"

    # 必要な import を exec namespace に渡す
    import glob as _glob

    ns = {
        "os": os,
        "glob": _glob,
        "FeatureContext": object,
    }
    exec(compile(ast.Module(body=[func], type_ignores=[]), "<test>", "exec"), ns)
    return ns["_resolve_curator_profile_path"]


def _ctx(out_dir: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        config=lambda key, default=None: {"karte_output_directory": out_dir} if key == "mykatrain_settings" else default
    )


# -----------------------------------------------------------------------------
# ヘルパーロード
# -----------------------------------------------------------------------------


def test_resolver_loadable() -> None:
    fn = _load_resolver_isolated()
    assert callable(fn)


# -----------------------------------------------------------------------------
# canonical (固定名) が存在する場合 → それを返す
# -----------------------------------------------------------------------------


def test_canonical_file_preferred(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    canonical = tmp_path / "curator_ranking.json"
    canonical.write_text("{}")

    result = fn(_ctx(str(tmp_path)))
    assert result is not None
    # canonical と完全一致 (glob 経由ではなく canonical そのもの)
    assert os.path.normpath(result) == os.path.normpath(str(canonical))


def test_canonical_takes_precedence_over_timestamped(tmp_path: Path) -> None:
    """固定名と glob 候補が両方あっても、固定名が優先される。"""
    fn = _load_resolver_isolated()
    canonical = tmp_path / "curator_ranking.json"
    canonical.write_text("{}")
    # 別タイムスタンプのファイル
    other = tmp_path / "curator_ranking_20260101-000000.json"
    other.write_text("{}")

    result = fn(_ctx(str(tmp_path)))
    assert result is not None
    assert os.path.normpath(result) == os.path.normpath(str(canonical))


# -----------------------------------------------------------------------------
# canonical が無い場合 → glob で最新 mtime を返す
# -----------------------------------------------------------------------------


def test_timestamped_fallback_picks_latest_mtime(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    old = tmp_path / "curator_ranking_20260101-000000.json"
    new = tmp_path / "curator_ranking_20260718-125952.json"
    old.write_text("{}")
    # mtime を 1 秒以上離す (FAT/NTFS の 1秒粒度を考慮)
    time.sleep(1.1)
    new.write_text("{}")

    result = fn(_ctx(str(tmp_path)))
    assert result is not None
    assert os.path.normpath(result) == os.path.normpath(str(new))


def test_timestamped_single_file(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    only = tmp_path / "curator_ranking_20260718-125952.json"
    only.write_text("{}")

    result = fn(_ctx(str(tmp_path)))
    assert result is not None
    assert os.path.normpath(result) == os.path.normpath(str(only))


def test_timestamped_three_files_picks_latest(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    paths = []
    for i in range(3):
        p = tmp_path / f"curator_ranking_2026010{i + 1}-000000.json"
        p.write_text("{}")
        paths.append(p)
        time.sleep(1.1)  # mtime を確実に 1 秒以上離す

    result = fn(_ctx(str(tmp_path)))
    assert result is not None
    # 最後に書いたファイル (i=2) が最新
    assert os.path.normpath(result) == os.path.normpath(str(paths[-1]))


# -----------------------------------------------------------------------------
# 何も無い / 設定未定義 / ディレクトリ不在 → None
# -----------------------------------------------------------------------------


def test_no_files_returns_none(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    # 空ディレクトリ
    result = fn(_ctx(str(tmp_path)))
    assert result is None


def test_unrelated_files_returns_none(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    (tmp_path / "karte_20260101.json").write_text("{}")
    (tmp_path / "replay_guide_20260101.json").write_text("{}")
    (tmp_path / "random.txt").write_text("hello")

    result = fn(_ctx(str(tmp_path)))
    assert result is None


def test_unset_output_dir_returns_none() -> None:
    fn = _load_resolver_isolated()
    result = fn(_ctx(""))
    assert result is None


def test_nonexistent_output_dir_returns_none(tmp_path: Path) -> None:
    fn = _load_resolver_isolated()
    result = fn(_ctx(str(tmp_path / "does_not_exist")))
    assert result is None


# -----------------------------------------------------------------------------
# 防御: glob がディレクトリも拾うケース (拡張子 .json だが directory)
# -----------------------------------------------------------------------------


def test_timestamped_directory_is_skipped(tmp_path: Path) -> None:
    """``curator_ranking_xxx.json/`` のようなディレクトリは候補から除外。"""
    fn = _load_resolver_isolated()
    # ディレクトリ (拡張子 .json 付きの名前)
    bogus_dir = tmp_path / "curator_ranking_fake.json"
    bogus_dir.mkdir()
    # 通常のファイル
    real = tmp_path / "curator_ranking_20260718-125952.json"
    real.write_text("{}")

    result = fn(_ctx(str(tmp_path)))
    assert result is not None
    assert os.path.normpath(result) == os.path.normpath(str(real))
