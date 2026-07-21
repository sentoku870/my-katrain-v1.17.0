# Phase 281: 日本語フォント 豆腐修正 包括対策

**日付**: 2026-07-21
**種別**: Lv3 (バグ修正 + 包括対策 + 再発防止)
**動機**: ユーザー報告 (スクリーンショット 2 枚: KataGo 設定 popup + 新規対局 popup の hint_text が全て豆腐)

## 背景 (ユーザー要望)

スクリーンショットで確認した症状:

1. **「KataGo 設定」popup** (`<ConfigPopup>`):
   - 「KataGo実行ファイル（フルパス）」の hint_text が `□□KataGo□□□□□□□□`
   - 「エンジンコマンドの上書き」の hint_text が `□□□□□□□□□□□□□ (plink□□□□□□□□□□, -), □□□□□□□□□□□□□□□□`
   - 「分析の最大時間」の hint_text が `□`
   - 「Wide root noise」の hint_text が `0.023□0-1□□□□`

2. **「新規対局の設定」popup** (`<NewGamePopup>` / `<QuickConfigGui>` ベース):
   - 「対局者名」の hint_text が `□□`
   - 「コミ」の hint_text が `□□`
   - 「碁盤サイズ」の hint_text が `□□□□□ x,y □□□□ 19,9□`

共通する症状:
- **ラベル（`DescriptionLabel`）や Spinner / Button の選択値表示は日本語 OK**
- **入力欄の値（6.5、19、0 など）は日本語 OK**
- **`MDTextField` 内部の `TextfieldLabel`（hint text 表示用）のみ豆腐**

つまり、KivyMD 1.2.0 の `MDTextField` 内部の `TextfieldLabel` クラスが、プロジェクトで指定している `Theme.DEFAULT_FONT` (NotoSansJP) を継承せず、Kivy 組み込みの Roboto にフォールバックしている。

### 既存の対策と不完全性

Phase 277 (KivyMD 1.2.0 移行) で `_kivymd_kv_loader.py:208-220` に `TextfieldLabel` ルールが追加された:

```kv
# 既存のコード (Phase 277)
<MDTextField>:
    font_name: "Roboto" if not root.font_name else root.font_name
...
<TextfieldLabel>:
    font_name: root.font_name if root.font_name else 'Roboto'
```

この条件式の問題点:
- `root.font_name` が `None` / 空文字 / falsy のときに **Roboto にフォールバック**
- Roboto は Kivy 標準フォントで**日本語グリフがない → 豆腐**
- `MDTextField.font_name` のバインディング伝播タイミング次第で `TextfieldLabel.font_name` が評価時に未確定 → Roboto に → 豆腐

## 解決策

**Lv3: 4 つの層で包括的に対策し、再発防止のテストも追加**

### サブフェーズ索引

| サブ | 内容 | ファイル |
|---|---|---|
| 281-A | `factory.py` に `_sync_font_to_hint_labels` / `_schedule_hint_label_sync` ヘルパー追加 + Label/Button/Popup ラッパーで自動呼び出し | `katrain/gui/widgets/factory.py` |
| 281-B | `_kivymd_kv_loader.py` の TextfieldLabel/MDTextField ルールで Roboto フォールバック撤廃 + Theme import 追加 | `katrain/gui/_kivymd_kv_loader.py` |
| 281-C | `_base.py` の `LabelledTextInput` に `on_kv_post` / `on_font_name` ハンドラ追加 | `katrain/gui/popups/_base.py` |
| 281-D | `__main__.py` の `resource_find()` 戻り値が None の場合警告ログ追加 | `katrain/__main__.py` |
| 281-E | 再発防止テスト 2 ファイル追加 (15 件) | `tests/test_kivymd_hint_text_label.py`, `tests/test_factory_font_sync.py` |
| 281-F | AGENTS.md 更新 | `AGENTS.md` |

## 影響範囲

### 修正 (4 ファイル)

#### (1) `katrain/gui/widgets/factory.py`

- `_HINT_LABEL_ATTRS` リスト新設: KivyMD 1.2.0 の内部 Label attr 7 個
  - `hint_text_label` / `_hint_text_label` / `helper_text_label` / `max_length_label` / `error_label` / `counter_label`
- `_sync_font_to_hint_labels(widget)` ヘルパー新設: widget の font_name を内部 Label に伝播
- `_schedule_hint_label_sync(widget)` ヘルパー新設: 次フレームで `_sync_font_to_hint_labels` を実行
- Label / Button / Popup ラッパーの `__init__` 末尾で `_schedule_hint_label_sync(self)` を呼び出し

#### (2) `katrain/gui/_kivymd_kv_loader.py`

- TextfieldLabel/MDTextField ルールから Roboto フォールバックを撤廃
- `#:import Theme katrain.gui.theme.Theme` を KV ルール先頭に追加
- フォールバック先を `Theme.DEFAULT_FONT` に変更

```kv
# After Phase 281
font_name: root.font_name if root.font_name else Theme.DEFAULT_FONT
```

#### (3) `katrain/gui/popups/_base.py`

- `LabelledTextInput` に `on_kv_post(base_widget)` ハンドラ追加
  - KV 構築完了後に `_sync_font_to_hint_labels(self)` を呼び出し
- `LabelledTextInput` に `on_font_name(instance, value)` ハンドラ追加
  - font_name 変更時に hint_text_label にも反映

#### (4) `katrain/__main__.py`

- `resource_find(Theme.DEFAULT_FONT)` の戻り値を `resolved_font` にキャプチャ
- `resolved_font is None` の場合に `logging.getLogger(__name__).warning(...)` で警告
- PyInstaller bundle / 開発環境ミス設定の早期発見

### テスト追加 (2 ファイル / 15 件)

#### (5) `tests/test_kivymd_hint_text_label.py` (新規 / 7 件)

**Source-static regression guards** (Kivy 不要):
- `test_textfield_kv_loader_exists`: _kivymd_kv_loader.py の存在確認
- `test_textfield_kv_loader_has_no_roboto_fallback`: TextfieldLabel ルールに `'Roboto'` / `"Roboto"` が**含まれていない**ことを検証
- `test_textfield_kv_loader_imports_theme`: `#:import Theme katrain.gui.theme.Theme` の存在確認
- `test_factory_uses_helper`: factory.py に `_schedule_hint_label_sync` の呼び出しがある
- `test_labelled_textinput_overrides_kv_post`: _base.py に `on_kv_post` メソッドが存在し `_sync_font_to_hint_labels` を呼び出す
- `test_resource_find_validates_none`: __main__.py が `resource_find` の None ガードを持つ

**AST-level runtime contract check**:
- `test_labelled_textinput_overrides_defined_via_ast`: LabelledTextInput の `on_kv_post` と `on_font_name` が AST 上で `_sync_font_to_hint_labels` を呼び出すことを検証 (MDApp 初期化が不要)

#### (6) `tests/test_factory_font_sync.py` (新規 / 8 件)

**Source-static regression guards**:
- `test_factory_declares_helper`: ヘルパー 2 つの存在確認
- `test_factory_hint_label_attrs_listed`: `_HINT_LABEL_ATTRS` に必須 attr が含まれる
- `test_factory_wrappers_schedule_sync`: 3 ラッパーで `_schedule_hint_label_sync(self)` が正確に 3 回呼ばれる

**Direct unit tests** (MagicMock ベース):
- `test_no_op_when_widget_has_no_font_name`: font_name が空文字なら何もしない
- `test_no_op_when_widget_has_no_hint_attrs`: 内部 Label attr がなければ何もしない
- `test_propagates_font_name_to_hint_label`: 内部 Label に font_name が伝播する
- `test_no_change_when_already_in_sync`: 既に同期済みなら何もしない
- `test_propagates_to_all_known_internal_labels`: 全 attr に伝播する

## 検証結果

| 項目 | 結果 |
|---|---|
| `mypy katrain` | **0 issues** (310 files) |
| `ruff check katrain tests` | **All checks passed** |
| `ruff format --check katrain tests` | **551 files already formatted** |
| `pytest tests -n auto` | **5862 passed, 3 skipped** |
| 新規テスト | **15 件** (factory sync 8 + kv loader static 6 + AST 1) |
| 回帰 | なし (Phase 280 baseline 5805 + 15 + 既存で 5862) |

## 期待される効果

### 即時
- スクリーンショット 1（KataGo 設定）の 4 箇所の hint_text 豆腐が解消
- スクリーンショット 2（新規対局）の 3 箇所の hint_text 豆腐が解消
- 同パターンの KivyMD 1.2.0 派生 widget 全体にも自動対応

### 再発防止
- 15 件の test が「Roboto フォールバックを戻す」「ヘルパーを削除する」「on_kv_post を消す」などのリグレッションを CI で自動検出
- AGENTS.md に豆腐修正の経緯と再発防止ルールを明記
- PyInstaller bundle 時のフォント欠落が警告ログで可視化

## 保持 (deferred なし)

- `HintCategory` enum / Karte / Beginner Hints / 重要局面機能などへの影響なし
- 既存の `KeyValueSpinner` / `DescriptionLabel` / `SizedButton` 系の font_name 保護は温存
- 既存の `factory.Label` / `factory.Button` / `factory.Popup` の API は不変

## 動機と教訓

Phase 277 で KivyMD 1.2.0 移行時に「TextfieldLabel の font_name 継承問題」を部分的に修正していたが、`Roboto` フォールバックが真因を見えにくくしていた。本 Phase で:

1. **真因を完全除去** (Roboto fallback 撤廃)
2. **多重防御** (KV ルール + Python ハンドラ + ヘルパー自動呼び出し)
3. **自動検証** (15 件のテストで再侵入を阻止)

の 3 層で再発を防ぐ。
