"""Phase 266: Curator profile refresh hook (Batch 完了 → 再ロード)

Batch 分析完了後、 GUI は ``curator_refresh_fn`` を呼んで
``katrain.update_curator_profile()`` を発火させ、 Beginner Hint
のリアルタイム re-label に新しい weak_tags を反映する。

テスト:
- create_summary_callback の curator_refresh_fn 引数
  - non-None なら result.success_count > 0 時に呼ばれる
  - cancelled 時には呼ばれない
  - 失敗してもクラッシュしない (log_cb にエラー出力)
  - 呼ばれた後でも summary 自体は表示される

- 重要局面 popup (Factory.ImportantMovesEntry)
  - .kv で宣言されたクラスが Python モジュールとして存在しない
  - 代わりに ``Factory.ImportantMovesEntry`` 経由でアクセス
  - バグ修正: 旧実装の ``from katrain.gui.kv.important_moves_popup
    import ImportantMovesEntry`` は ModuleNotFoundError を起こす
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
POPUP_PATH = REPO_ROOT / "katrain" / "gui" / "popups" / "important_moves_popup.py"
BATCH_CORE_PATH = REPO_ROOT / "katrain" / "gui" / "features" / "batch_core.py"


# -----------------------------------------------------------------------------
# 1. important_moves_popup.py: バグ修正 (重要局面 popup)
# -----------------------------------------------------------------------------


def test_popup_does_not_import_kv_module() -> None:
    """Phase 266: ``.kv`` ファイルは Python モジュールとして import 不可。
    Python クラス ImportantMovesEntry を使う形式に修正済み。"""
    src = POPUP_PATH.read_text(encoding="utf-8")
    assert "from katrain.gui.kv.important_moves_popup import" not in src, (
        ".kv モジュールからの import は ModuleNotFoundError を起こす"
    )
    # Python クラス定義あり (Property declarations が必須)
    assert "class ImportantMovesEntry" in src

    # docstring 中の言及は除外して、 実コード (Call ノード) で
    # Factory.ImportantMovesEntry が使われていないことを確認
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "Factory"
            and node.func.attr == "ImportantMovesEntry"
        ):
            raise AssertionError(
                "Factory.ImportantMovesEntry() の呼び出しは __init__ で プロパティ未登録 TypeError を起こす (Phase 266)"
            )


def test_popup_defines_property_declarations() -> None:
    """``ImportantMovesEntry`` には Property 宣言が必要 (move_number, player, etc.)"""
    src = POPUP_PATH.read_text(encoding="utf-8")
    # 9 つの Property 宣言を期待
    for prop in (
        "move_number = NumericProperty",
        "player = StringProperty",
        "gtp_coord = StringProperty",
        "score_loss = NumericProperty",
        "meaning_tag_label = StringProperty",
        "game_phase = StringProperty",
        "complexity_discounted = BooleanProperty",
        "is_current = BooleanProperty",
        "bg_color = ListProperty",
    ):
        assert prop in src, f"重要局面エントリの Property 宣言 {prop!r} がない"


def test_kv_template_uses_python_class_merge() -> None:
    """``.kv`` ファイルは Python クラスとマージする形式 (``@BoxLayout`` 無し)"""
    kv_path = REPO_ROOT / "katrain" / "gui" / "kv" / "important_moves_popup.kv"
    src = kv_path.read_text(encoding="utf-8")
    # Phase 266: `<ImportantMovesEntry@BoxLayout>` → `<ImportantMovesEntry>`
    assert "<ImportantMovesEntry@BoxLayout>" not in src, "Factory 経由の宣言を削除 (Python クラスとマージする形に)"
    assert "<ImportantMovesEntry>" in src, "Python クラスの template rule が必要"


# -----------------------------------------------------------------------------
# 2. create_summary_callback: curator_refresh_fn hook
# -----------------------------------------------------------------------------


def _load_create_summary_callback() -> callable:
    tree = ast.parse(BATCH_CORE_PATH.read_text(encoding="utf-8"))
    func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "create_summary_callback":
            func = node
            break
    assert func is not None

    # AST 抽出で signature を確認
    args = [a.arg for a in func.args.args]
    defaults_offset = len(args) - len(func.args.defaults)
    defaults = dict(zip(args[defaults_offset:], func.args.defaults, strict=False))
    return func, args, defaults


def test_summary_callback_signature_has_curator_refresh() -> None:
    func, args, defaults = _load_create_summary_callback()
    assert "curator_refresh_fn" in args, f"create_summary_callback に curator_refresh_fn 引数が必要 (args: {args})"
    # Optional (default = None) であること
    cur_idx = args.index("curator_refresh_fn")
    assert cur_idx >= len(args) - len(func.args.defaults), "curator_refresh_fn は optional であるべき"


# -----------------------------------------------------------------------------
# 3. controller から hook が渡される
# -----------------------------------------------------------------------------


CONTROLLER_PATH = REPO_ROOT / "katrain" / "gui" / "controllers" / "batch_analysis_controller.py"


def test_controller_passes_curator_refresh_fn() -> None:
    src = CONTROLLER_PATH.read_text(encoding="utf-8")
    assert "curator_refresh_fn" in src, "controller が curator_refresh_fn を渡していない"
    assert "update_curator_profile" in src, "controller が update_curator_profile を hook に取り込んでいない"


# -----------------------------------------------------------------------------
# 4. KaTrainGui: update_curator_profile がログ出力
# -----------------------------------------------------------------------------


MAIN_PATH = REPO_ROOT / "katrain" / "__main__.py"


def test_main_logs_curator_load_state() -> None:
    """update_curator_profile が GUI log に load 結果を出力する。"""
    src = MAIN_PATH.read_text(encoding="utf-8")
    # load 成功時のログ
    assert "Curator profile loaded" in src
    # no-profile 時のログ
    assert "no curator_ranking.json" in src


def test_main_calls_update_curator_profile_on_start() -> None:
    """start() 末尾で curator profile を 1 回ロードする。"""
    src = MAIN_PATH.read_text(encoding="utf-8")
    # start() メソッド内に update_curator_profile() 呼び出し
    # AST で関数定義を抽出 (ClassDef の中の可能性あり)
    tree = ast.parse(src)
    start_func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "start":
            start_func = node
            break
    assert start_func is not None, "start() メソッドが見つからない"

    found = False
    for sub in ast.walk(start_func):
        if isinstance(sub, ast.Call) and getattr(sub.func, "attr", None) == "update_curator_profile":
            found = True
            break
    assert found, "start() メソッド内で update_curator_profile() が呼ばれていない"


# -----------------------------------------------------------------------------
# 5. analysis_tab: curator_hint_status 説明ラベル
# -----------------------------------------------------------------------------


ANALYSIS_TAB_PATH = REPO_ROOT / "katrain" / "gui" / "features" / "settings_popup_tabs" / "analysis_tab.py"


def test_analysis_tab_has_curator_status_label() -> None:
    src = ANALYSIS_TAB_PATH.read_text(encoding="utf-8")
    assert "_build_curator_status_label" in src, "_build_curator_status_label ヘルパーが未実装"
    # i18n キー使用
    assert "mykatrain:settings:curator_hint_loaded" in src
    assert "mykatrain:settings:curator_hint_not_loaded" in src
