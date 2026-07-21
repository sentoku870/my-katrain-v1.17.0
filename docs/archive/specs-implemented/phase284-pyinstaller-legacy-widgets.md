# Phase 284: PyInstaller frozen binary の MyKatrain 設定 popup / Batch analyze popup ModuleNotFoundError fix

> **ステータス**: 完了（2026-07-21）
> **レベル**: Lv1
> **影響範囲**: PyInstaller ビルドのみ（開発環境では無影響）

---

## 1. 背景

Phase 283 のマージ後、PyInstaller でビルドした frozen binary を起動し、ユーザーが myKatrain 設定 popup / batch analyze popup を開くと以下のエラーが発生：

```
ModuleNotFoundError: No module named 'kivy.uix.tabbedpanel'
ModuleNotFoundError: No module named 'kivy.uix.checkbox'
```

---

## 2. 真因

`kivy.uix.tabbedpanel` と `kivy.uix.checkbox` の **2 モジュール**は、Clock-scheduled lazy import 経由でしか参照されないため、PyInstaller の static analyser がシンボルを見つけられず **frozen bundle から脱落** していた。

Kivy 2.3.1 の通常環境には標準で存在するが、PyInstaller の frozen binary にだけ欠落する問題。

---

## 3. 解決策

`spec/KaTrain.spec` の `hiddenimports` に以下を明示追加（Phase 277 の `lang_bridge` 追加と同パターン）：

```python
hiddenimports=[
    # ... 既存
    'katrain.gui.lang_bridge',  # Phase 277 で追加
    # Phase 284 で追加:
    'kivy.uix.tabbedpanel',
    'kivy.uix.checkbox',
],
```

これにより PyInstaller の static analyser が `kivy.uix.tabbedpanel` と `kivy.uix.checkbox` を frozen bundle に含めるようになる。

---

## 4. ユーザー側の追加対応（環境依存）

報告のあったエラーは frozen binary とは別原因の可能性あり：

- `.venv/Lib/site-packages/kivy/uix/` 自体が欠落しているケース
- この場合は `uv pip install --force-reinstall kivy` で修復

Kivy 2.3.1 の標準インストールであれば `kivy/uix/tabbedpanel.py` と `kivy/uix/checkbox.py` が含まれる。

---

## 5. 再発防止テスト（8 件）

`tests/test_katrain_spec_hiddenimports.py` を新規作成：

1. `spec/KaTrain.spec` の hiddenimports ブロック存在
2. Phase 277 で追加された `katrain.gui.lang_bridge` の存在
3. Phase 284 で追加された `kivy.uix.tabbedpanel` の存在
4. Phase 284 で追加された `kivy.uix.checkbox` の存在
5. Phase 284 コメントの存在（"Phase 284: ..."）
6. hiddenimports ブロック内の重複禁止
7. `katrain/gui/settings_popup.py` 内に `from kivy.uix.tabbedpanel` import 文が残っているか（import-site 整合性）
8. `katrain/gui/features/batch_ui.py` 内に `from kivy.uix.checkbox` import 文が残っているか（import-site 整合性）

---

## 6. 検証結果

```
mypy katrain: 0 issues (310 source files)
ruff check: clean
ruff format: clean
pytest tests: 6191 PASS + 3 SKIP (Phase 283 baseline 6183 → +8 件新規)
```

PyInstaller Linux bundle で上記修正後の動作確認：

- myKatrain 設定 popup: 起動 OK
- Batch analyze popup: 起動 OK
- `ModuleNotFoundError` 解消

---

## 7. 保持された概念

- 既存の `hiddenimports` ブロック（Phase 277 の `lang_bridge` 等）は全て温存
- PyInstaller の他の hook 設定（`spec/hook-kivymd.py` 等）は不変
- 開発環境（`python -m katrain`）では無影響

---

## 8. 関連 Phase

- **Phase 277**: KivyMD 0.104.1 → 1.2.0 移行（`hiddenimports` に `katrain.gui.lang_bridge` を追加した前例）
- **Phase 281**: 日本語フォント tofu fix（PyInstaller bundle でのフォント欠落早期発見の `resource_find()` 警告ログ追加）
- **Phase 283**: サイドパネル + popup fix（本 Phase の引き金、popup を新規に触ったタイミングで frozen binary 検証が発覚）

---

## 9. 関連ドキュメント

- `AGENTS.md` §1.3（直近マイルストーン）
- `docs/01-roadmap.md` §4（Phase 284 詳細）
- `docs/02-code-structure.md` §6.6（PyInstaller ビルド関連の注意点）
- `spec/KaTrain.spec`（実ファイル）
- `spec/hook-kivymd.py`（KivyMD hook）

---

## 10. 参考: PyInstaller hiddenimports の運用ガイドライン

新規 lazy import モジュールを追加する際のチェックリスト：

1. **Clock-scheduled import 経由のモジュールは PyInstaller static analyser で捕捉されない**
2. **`spec/KaTrain.spec` の hiddenimports に明示追加が必要**
3. **CI / ローカルで PyInstaller bundle を起動して popup を全種類開き、ModuleNotFoundError が発生しないことを確認**
4. **新規 popup / batch_ui 追加時は本テストの存在を意識**

今後の Phase で新規 lazy import を追加する場合は、本 Phase のテスト（`test_katrain_spec_hiddenimports.py`）に assertion を追加すること。