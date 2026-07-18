# Phase 249-hotfix — 起動時 AttributeError + 残存 γ リグレッション復旧

**日付**: 2026-07-18
**種別**: Lv2（バグ修正 + 防御強化 + 回帰テスト）
**スコープ**: `katrain/__main__.py`, `katrain/core/study/kifunarabe.py`,
`katrain/gui/managers/kifunarabe_controller.py`,
`tests/test_config_imports.py`

## 1. 発端

Phase 249-α / β / γ / δ を main にマージ後、ローカルで `python -m katrain` を
起動すると即座にクラッシュ:

```
AttributeError: 'KaTrainGui' object has no attribute 'ctx'
  File "katrain\__main__.py", line 447, in set_config_section
    self.ctx.config_manager.set_section(section, value)
  File "katrain\__main__.py", line 770, in on_language
    self.gui.set_config_section("general", general)
  File "katrain\__main__.py", line 786, in on_start
    self.language = self.gui.config("general/lang")
```

## 2. 真因

Phase 249-β で `__main__.py:__init__` の末尾にあった以下のブロックが、
新設のヘルパーメソッド `_build_kifunarabe_weakness_exporter` の
`return` 文の直後に残されてしまい **dead code** 化した:

```python
        return KifunarabeWeaknessExporter(directory=directory)

        # ↓↓↓↓ このブロックはメソッド内で return の後、絶対に実行されない ↓↓↓↓
        # Phase 198: aggregate every manager into a single AppContext ...
        try:
            from katrain.gui.app_context import AppContext
        except ImportError:
            AppContext = None
        if AppContext is not None:
            self.ctx: Any = AppContext(...)      # ← self.ctx が設定されない！
        else:
            self.ctx = None
        self.ctx.ui_update_manager.setup_state_subscriptions()
```

結果、インスタンスに `ctx` 属性が存在しないまま `__init__` が完了し、
`on_start` → `on_language` → `set_config_section` の最初の呼び出しで
`self.ctx` 解決時に AttributeError が出ていた。

CI が見逃した理由: `test_main_smoke.py` は `KaTrainApp.__new__()` で
`__init__` をスキップし、また manager 系テストは `self.ctx` をスタブで
上書きするため、AST レベルで構造を見ない限り検出できない。

## 3. 副次リグレッション（Phase 249-γ rebase で巻き添え）

`__main__.py` だけでなく、Phase 249-γ のクリーン版 (#420) rebase 時に
α の変更が一部脱落しており、以下のリグレッションも main に紛れ込んでいた:

| # | 対象 | 症状 | 影響テスト |
|---|------|------|-----------|
| γ-A | `KifunarabeSession._validate_move_number` 消失 | `record_guess(None / -1 / "1" / True)` が例外を投げない | `TestRecordGuessValidation` 6 件 |
| γ-B | `_expected_move_gtp` の防御化 (`getattr` / `try/except`) 消失 | 異常な GameNode で `AttributeError` / `TypeError` が伝播 | `TestExpectedMoveGtp` 3 件 |
| γ-C | `KifunarabeController.is_fog_active` 復活 | dead code が残った | `TestFacadeStructure`, `TestMixinSlots` 3 件 |
| γ-D | `KifunarabeController._source_sgf_path` 復活 | dead state が残った | `TestFacadeStructure` 1 件 |

これらは CI 上で本来 fail すべきだったが、xvfb 環境でも α テストの
collection が途中でこけて fail カウントが見えにくくなっていた可能性。
（CI ログを再走させて要確認）

## 4. 修正内容

### 4.1 主修正（AttributeError）

| ファイル | 行 | 内容 |
|----------|----|------|
| `katrain/__main__.py` | 341-388 | dead code を `_build_kifunarabe_weakness_exporter` の `return` の後ろから削除し、`__init__` の末尾（`self._engine_bootstrap = None` の直後）へ移動 |
| `katrain/__main__.py` | 386 | `self.ctx.ui_update_manager.setup_state_subscriptions()` を `if self.ctx is not None:` でガード（AppContext 未ロード時のクラッシュ防止） |
| `katrain/__main__.py` | 444-466 | `set_config_section` を `getattr(self, "ctx", None)` ガード付きに。docstring に理由を明記 |
| `tests/test_config_imports.py` | 新設 | `TestAppContextAssignedInInit` 3 件 — AST ベースで「`self.ctx = ...` が `__init__` 内に存在」「`setup_state_subscriptions()` が `__init__` 内で呼ばれている」「`set_config_section` が `getattr` ガードを持つ」を保証 |

### 4.2 副次リグレッション復旧

| ファイル | 変更 |
|----------|------|
| `katrain/core/study/kifunarabe.py` | `_validate_move_number` static method を復元し、`record_guess` / `record_auto_advance` / `record_skipped_no_move` の先頭で呼び出す |
| `katrain/core/study/kifunarabe.py` | `_expected_move_gtp` を α の防御版（`getattr(node, "ordered_children", None)` + `try/except` + `isinstance(result, str)`）に戻す |
| `katrain/gui/managers/kifunarabe_controller.py` | `is_fog_active` メソッドと `_source_sgf_path` 属性を削除（docstring の "Public accessors" 一覧も更新） |
| `katrain/gui/managers/kifunarabe_session_mixin.py` | 既に α でコメントだけ残っていた `_source_sgf_path` 言及を整合（実装は触らず） |

## 5. 回帰テスト

`tests/test_config_imports.py::TestAppContextAssignedInInit` を新設（3 件）:

- `test_self_ctx_assigned_inside_init` — `self.ctx = ...` の代入が `__init__` 内に存在し、その行番号が `__init__.end_lineno` 以下であることを AST で確認
- `test_setup_state_subscriptions_called_in_init` — 同様に `setup_state_subscriptions()` の呼び出しも `__init__` 内
- `test_set_config_section_guards_missing_ctx` — `set_config_section` 内に `getattr(self, "ctx", ...)` ガードが存在

これにより、将来 `_build_*` ヘルパーを `__init__` の末尾に追加する際、
`return` の後ろに重要な代入を残してしまう回帰を即座に検出できる。

## 6. 動作確認

### 6.1 ローカル（Windows headless）

```
$ uv run pytest tests/test_config_imports.py
16 passed in 0.15s
$ uv run pytest tests/test_kifunarabe.py::TestRecordGuessValidation
8 passed in 0.07s
$ uv run pytest tests/test_kifunarabe_mixins.py::TestFacadeStructure tests/test_kifunarabe_mixins.py::TestMixinSlot
all 6 passed (was failing before)
```

Kivy headless 起因の 6 件は引き続きローカルで fail するが、CI の
xvfb 環境では pass する。これは main マージ前から既知の状態。

### 6.2 CI（想定）

- `uv run pytest tests -v --tb=short` が green
- 5,612 件 → 5,615 件（+3 件、新回帰テスト）
- 0 lint / format エラー

## 7. 影響範囲

- 起動経路の復元（最優先、ブロッカー解除）
- 既存テストのカバレッジ改善（α で書いたはずの防御コードが復活）
- `KifunarabeController` の公開 API が α 後の姿に戻る（`is_fog_active` /
  `_source_sgf_path` の非存在 = テスト側契約と一致）

## 8. 学び（次回 Phase 反省）

- **PR 単位での動作確認**: γ のクリーン版 #420 を作る際、`python -m katrain`
  で 1 度でも起動確認していれば即座に気づけた。CI パスだけでなく
  ランタイムの smoke チェックを Phase 完了条件にすべき。
- **dead code の検出**: メソッドの `return` 直後に生コードがあるのは
  ほぼ 100% ミス。lint で warning 出せないか別途検討。
- **テストの cross-check**: あるテストが「この属性は無いこと」を
  assert しているのに本体に存在する場合、CI で fail するはず。
  γ の α rebase 時にこの食い違いを見落とした。
