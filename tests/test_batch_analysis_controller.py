"""BatchAnalysisController の永続化パス回帰テスト (Phase 231)

背景:
    ``BatchAnalysisController.open_batch_analyze_popup`` は
    ``mykatrain_settings.batch_options`` から既存オプションを読み込むが、
    旧実装の ``save_batch_options`` クロージャはトップレベル ``batch_options``
    キーに書き戻していたため、読み込み経路と書き込み経路が不一致で
    ユーザーの設定が永続化されないバグがあった (Phase 231 で修正)。

このテストは、修正後の ``_persist_batch_options`` ヘルパーが以下の
不変条件を破らないことを保証する:

1. 書き戻した値が次回の read path (``mykatrain_settings.batch_options``)
   で取得できる
2. 同じ ``mykatrain_settings`` 内の他のサブ設定
   (default_user_name, karte_output_directory 等) を上書きしない
3. トップレベル ``batch_options`` キーに書かない
4. ``mykatrain_settings`` セクションが未初期化 (空) でも例外を出さず
   クラッシュしない

Kivy 不要で実行可能。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _StubBatchCtx:
    """``BatchAnalysisContext`` Protocol を満たす最小スタブ。

    config 値を dict で保持し、set_config_section / save_config の
    呼び出しを記録する。実 Kivy / 実 ConfigManager には触らない。
    """

    def __init__(self, initial_config: dict[str, Any] | None = None) -> None:
        self._config: dict[str, Any] = dict(initial_config or {})
        self.set_section_calls: list[tuple[str, Any]] = []
        self.save_config_calls: list[str | None] = []

    def config(self, section: str, default: Any = None) -> Any:
        return self._config.get(section, default)

    def set_config_section(self, section: str, value: Any) -> None:
        self.set_section_calls.append((section, value))
        self._config[section] = value

    def save_config(self, section: str | None = None) -> None:
        self.save_config_calls.append(section)

    # Protocol に存在しないがテストで便利
    def update_engine_config(self, **kwargs: Any) -> None:  # pragma: no cover
        pass

    def log(self, message: str, level: int) -> None:  # pragma: no cover
        pass


# ---------------------------------------------------------------------------
# Persistence helper import (Kivy-independent)
# ---------------------------------------------------------------------------


def _import_persist_helper():
    """``_persist_batch_options`` を import するヘルパ。

    モジュール自体は Kivy 非依存だが、import chain に
    ``katrain.gui.controllers`` があり、テスト環境では遅延 import を
    経由する必要があるため、独立した小さな経路で確認する。
    """
    from katrain.gui.controllers.batch_analysis_controller import _persist_batch_options

    return _persist_batch_options


# ---------------------------------------------------------------------------
# 1. Round-trip: write then read via the same path the popup uses
# ---------------------------------------------------------------------------


class TestPersistBatchOptionsRoundTrip:
    """保存した値が次回の popup open で読み戻せること。"""

    def test_round_trip_via_read_path(self):
        """Saved options must be visible to the read path on the next open."""
        _persist_batch_options = _import_persist_helper()

        ctx = _StubBatchCtx(initial_config={"mykatrain_settings": {}})
        saved = {
            "input_dir": "D:/sgf_collection",
            "output_dir": "D:/katrain_out",
            "visits": 500,
            "generate_karte": True,
            "generate_summary": False,
        }
        _persist_batch_options(ctx, saved)

        # Read path: open_batch_analyze_popup の line 47-48 をそのまま再現
        mykatrain_settings = ctx.config("mykatrain_settings") or {}
        batch_options = mykatrain_settings.get("batch_options", {})

        assert batch_options == saved
        # 個別フィールドも一致
        assert batch_options["input_dir"] == "D:/sgf_collection"
        assert batch_options["visits"] == 500

    def test_read_path_handles_missing_mykatrain_settings(self):
        """mykatrain_settings が config に存在しない場合もクラッシュしない。"""
        _persist_batch_options = _import_persist_helper()

        # 空 config でも save できることを確認
        ctx = _StubBatchCtx()
        _persist_batch_options(ctx, {"input_dir": "x"})

        # 読み戻せる
        mykatrain_settings = ctx.config("mykatrain_settings") or {}
        assert mykatrain_settings.get("batch_options") == {"input_dir": "x"}


# ---------------------------------------------------------------------------
# 2. Must NOT clobber other mykatrain_settings sub-keys
# ---------------------------------------------------------------------------


class TestPersistBatchOptionsPreservesOtherKeys:
    """``mykatrain_settings`` 配下の他のキー (default_user_name 等) を保持。"""

    def test_default_user_name_preserved(self):
        _persist_batch_options = _import_persist_helper()

        existing = {
            "default_user_name": "Alice",
            "karte_output_directory": "D:/out",
            "opponent_info_mode": "default",
        }
        ctx = _StubBatchCtx(initial_config={"mykatrain_settings": dict(existing)})
        _persist_batch_options(ctx, {"input_dir": "D:/in"})

        saved_my = ctx.config("mykatrain_settings")
        # batch_options は追加されている
        assert saved_my["batch_options"] == {"input_dir": "D:/in"}
        # 既存キーは保持
        assert saved_my["default_user_name"] == "Alice"
        assert saved_my["karte_output_directory"] == "D:/out"
        assert saved_my["opponent_info_mode"] == "default"

    def test_overwrite_only_batch_options(self):
        """batch_options を 2 回保存しても他のキーは影響を受けない。"""
        _persist_batch_options = _import_persist_helper()

        existing = {
            "default_user_name": "Bob",
            "karte_output_directory": "D:/karte",
        }
        ctx = _StubBatchCtx(initial_config={"mykatrain_settings": dict(existing)})

        _persist_batch_options(ctx, {"input_dir": "D:/in", "visits": 100})
        _persist_batch_options(ctx, {"input_dir": "D:/in2", "visits": 200, "output_dir": "D:/out2"})

        saved_my = ctx.config("mykatrain_settings")
        assert saved_my["batch_options"]["visits"] == 200
        assert saved_my["batch_options"]["output_dir"] == "D:/out2"
        # 既存キーはそのまま
        assert saved_my["default_user_name"] == "Bob"
        assert saved_my["karte_output_directory"] == "D:/karte"


# ---------------------------------------------------------------------------
# 3. Must NOT write to top-level "batch_options" key (regression check)
# ---------------------------------------------------------------------------


class TestPersistBatchOptionsDoesNotWriteTopLevelKey:
    """旧バグの回帰チェック: トップレベル ``batch_options`` キーに書かない。"""

    def test_no_top_level_batch_options_key(self):
        _persist_batch_options = _import_persist_helper()

        ctx = _StubBatchCtx(initial_config={"mykatrain_settings": {}})
        _persist_batch_options(ctx, {"input_dir": "D:/in"})

        # 旧バグならトップレベルにも書いてしまう
        assert "batch_options" not in ctx._config
        # set_section の呼び出しも "mykatrain_settings" 宛のみ
        sections_written = [s for s, _ in ctx.set_section_calls]
        assert "batch_options" not in sections_written
        assert sections_written == ["mykatrain_settings"]

    def test_save_config_targets_mykatrain_settings(self):
        """save_config() は "mykatrain_settings" セクションを指定する。"""
        _persist_batch_options = _import_persist_helper()

        ctx = _StubBatchCtx()
        _persist_batch_options(ctx, {"input_dir": "D:/in"})

        assert ctx.save_config_calls == ["mykatrain_settings"]


# ---------------------------------------------------------------------------
# 4. Multiple sequential saves behave correctly
# ---------------------------------------------------------------------------


class TestPersistBatchOptionsSequential:
    """連続保存でも整合性が崩れないこと。"""

    def test_sequential_saves_keep_growing(self):
        _persist_batch_options = _import_persist_helper()

        ctx = _StubBatchCtx()
        _persist_batch_options(ctx, {"input_dir": "first"})
        _persist_batch_options(ctx, {"input_dir": "second", "visits": 300})
        _persist_batch_options(ctx, {"visits": 500, "output_dir": "third"})

        final = ctx.config("mykatrain_settings")["batch_options"]
        assert final == {"visits": 500, "output_dir": "third"}

    def test_empty_options_still_persists(self):
        """空 dict を渡しても 'batch_options': {} として永続化される。"""
        _persist_batch_options = _import_persist_helper()

        ctx = _StubBatchCtx()
        _persist_batch_options(ctx, {})

        # 読み込み側でデフォルトにフォールバックせず、空 dict を取得
        batch_options = ctx.config("mykatrain_settings").get("batch_options")
        assert batch_options == {}


# ---------------------------------------------------------------------------
# 5. MagicMock 経由でも動く (Kivy スタブ環境向け)
# ---------------------------------------------------------------------------


class TestPersistBatchOptionsWithMagicMock:
    """CI での Kivy スタブ環境 (MagicMock ベース) でも動くことを確認。"""

    def test_magicmock_ctx_runs_without_error(self):
        _persist_batch_options = _import_persist_helper()

        # MagicMock はデフォルトで attr アクセスを全て受け入れる
        ctx = MagicMock()
        ctx.config.return_value = {"default_user_name": "test"}

        # 例外なく完了する
        _persist_batch_options(ctx, {"input_dir": "x"})

        # set_config_section は呼ばれている
        ctx.set_config_section.assert_called_once()
        # save_config も呼ばれている
        ctx.save_config.assert_called_once()
        # config() は少なくとも 1 回は呼ばれている
        ctx.config.assert_called_with("mykatrain_settings")


# ---------------------------------------------------------------------------
# 6. Phase 232: collect_batch_options の log_cb パラメータ動作確認
# ---------------------------------------------------------------------------


class TestCollectBatchOptionsLogCb:
    """collect_batch_options の log_cb パラメータ動作 (Phase 232).

    旧実装は run_batch_in_thread 内で同じ timeout 文字列を再パースして
    冗長だった。Phase 232 で collect_batch_options 側に log_cb を渡し、
    run_batch_in_thread 側のパースは削除された。
    """

    def _build_widgets(self, timeout_text: str = "None"):
        """Build a minimal widget stub dict for collect_batch_options.

        ``BatchWidgets`` is ``dict[str, Any]`` (see katrain.gui.features.types).
        Each value needs ``.text`` for TextInput-like widgets or ``.active``
        for CheckBox-like widgets. We use ``SimpleNamespace`` for concrete
        values — ``MagicMock`` would return 1.0 for ``.strip()`` / chained
        attribute access and break the test.
        """
        from types import SimpleNamespace

        def _ti(text: str) -> Any:
            return SimpleNamespace(text=text)

        def _cb(active: bool) -> Any:
            return SimpleNamespace(active=active)

        return {
            "input_input": _ti("/tmp/in"),
            "output_input": _ti("/tmp/out"),
            "visits_input": _ti(""),
            "timeout_input": _ti(timeout_text),
            "skip_checkbox": _cb(True),
            "save_sgf_checkbox": _cb(False),
            "karte_checkbox": _cb(True),
            "summary_checkbox": _cb(True),
            "min_games_input": _ti("3"),
            "variable_visits_checkbox": _cb(False),
            "jitter_input": _ti("10"),
            "deterministic_checkbox": _cb(True),
            "sound_checkbox": _cb(False),
            "curator_checkbox": _cb(False),
        }

    def test_log_cb_receives_warning_on_invalid_timeout(self):
        """無効な timeout 入力で log_cb が呼ばれる (Phase 232 で log 経路を統一)."""
        from katrain.gui.features.batch_core import collect_batch_options

        w = self._build_widgets(timeout_text="not-a-number")
        log_calls: list[str] = []

        options = collect_batch_options(w, lambda: None, log_cb=log_calls.append)

        # 無効入力 → DEFAULT (600.0) にフォールバック
        assert options["timeout"] == 600.0
        # log_cb には警告が出ている (旧: run_batch_in_thread 側で遅延警告)
        assert any("Invalid timeout" in msg for msg in log_calls), f"Expected warning to be logged, got: {log_calls}"

    def test_log_cb_default_silent(self):
        """log_cb 未指定時は警告サイレント (デフォルト動作)."""
        from katrain.gui.features.batch_core import collect_batch_options

        w = self._build_widgets(timeout_text="garbage")
        # log_cb を渡さない → 例外なく完了
        options = collect_batch_options(w, lambda: None)
        # フォールバック動作は変わらない
        assert options["timeout"] == 600.0

    def test_valid_timeout_unchanged(self):
        """有効 timeout はそのまま返り、log_cb は呼ばれない."""
        from katrain.gui.features.batch_core import collect_batch_options

        w = self._build_widgets(timeout_text="300")
        log_calls: list[str] = []
        options = collect_batch_options(w, lambda: None, log_cb=log_calls.append)
        assert options["timeout"] == 300.0
        assert log_calls == []

    def test_none_timeout_string_yields_none(self):
        """'None' 文字列 (大小無視) は Python の None として返る."""
        from katrain.gui.features.batch_core import collect_batch_options

        for variant in ("None", "none", "NONE"):
            w = self._build_widgets(timeout_text=variant)
            options = collect_batch_options(w, lambda: None)
            assert options["timeout"] is None, f"variant={variant!r}"
