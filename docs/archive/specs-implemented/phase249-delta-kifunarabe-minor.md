# Phase 249-δ: Kifunarabe 軽微修正 (メニューアイコン / panels.kv)

> 起票日: 2026-07-18
> ステータス: 🚧 進行中
> 関連: 監査 P0 #3 + P0 #2

## 1. 動機

Phase 249-α の監査で残った軽微な問題を解消する。

- **P0 #3**: menu.kv で `Insert-Move.png` アイコンが 2 箇所 (kifunarabe と analysis:insert) で重複
- **P0 #2**: panels.kv:497 の `size_hint_x: self.width` が Kivy 違反 (`size_hint_x` は 0.0-1.0 の数値のみ受付)

## 2. 修正内容

### 2.1 メニューアイコン重複解消

`katrain/gui/kv/menu.kv:340` (analysis:insert) のアイコンを `Insert-Move.png` から `Extra.png` に変更。

- `Insert-Move.png` (move prediction) は **棋譜並べ** (`menu:kifunarabe`, menu.kv:185) で使用
- `Extra.png` (additional move) は **手動一手挿入** (`analysis:insert`, menu.kv:340) で使用
- Phase 230-A の「アイコン重複解消」時に取り残されていた項目

### 2.2 panels.kv:497 修正

`katrain/gui/kv/panels.kv:493-498` の `MDFloatLayout` (kifunarabe_abort_button の親) の width バインディングを Kivy 準拠に修正。

**修正前** (Kivy 違反):
```kv
MDFloatLayout:
    width: kifunarabe_abort_button.width
    size_hint: None, 1
    opacity: 1 if (app.gui and app.gui.kifunarabe_mode) else 0
    disabled: not (app.gui and app.gui.kifunarabe_mode)
    size_hint_x: self.width if (app.gui and app.gui.kifunarabe_mode) else 1e-9
```

**修正後**:
```kv
MDFloatLayout:
    size_hint: None, 1
    width: kifunarabe_abort_button.width if (app.gui and app.gui.kifunarabe_mode) else 0
    opacity: 1 if (app.gui and app.gui.kifunarabe_mode) else 0
    disabled: not (app.gui and app.gui.kifunarabe_mode)
    size_hint_x: None
```

`size_hint_x` は `0.0` 〜 `1.0` または `None` のみ受け付けるため、`self.width` (px 値) を渡すと coerce されて意図しない動作になる。`size_hint_x: None` を明示し、width を 0 / `kifunarabe_abort_button.width` で切り替える。

## 3. 影響範囲

- 修正 2 ファイル: `menu.kv`, `panels.kv`
- アイコン画像は変更なし（既存 `Extra.png` を使用）

## 4. テスト

- Kivy widget テストは GUI 環境必須 (CI で実行)
- 既存の `tests/test_kifunarabe*.py` は GUI 非依存のテストのみなので影響なし
- 視覚的な検証はアプリ起動後に「棋譜並べ」ボタンと「手動一手挿入」ボタンが別のアイコンで表示されることで確認

## 5. 残タスク (本 Phase スコープ外)

- なし (軽微修正のみ)
