# Phase 249-γ: Kifunarabe Karte 連携 + 重要局面ジャンプ統合

> 起票日: 2026-07-18
> ステータス: 🚧 進行中
> 関連: Phase 177 仕様書 §7 / Planned 5 + 7

## 1. 動機

Phase 177 §7 Planned 5「カルテ/Batch 解析との統合」と
Planned 7「重要局面ジャンプ統合」が未着手のままだった。
Phase 249-β (履歴保存) で履歴を JSON 化したので、弱点の
Karte 連携が可能になった。本 Phase で Planned 5/7 を実装する。

## 2. アーキテクチャ

```
+----------------+        +-----------------------------+
| KifunarabeCtrl | append | KifunarabeHistoryStore      |
|  _end_session  |------->|  history (Phase 249-β)      |
|                |        +-----------------------------+
|                |
|                | append | KifunarabeWeaknessExporter  |  <-- Phase 249-γ
|                |------->|  (opt-in)                   |
|                |        +--------------+--------------+
+----------------+                       |
                                         v
                          +-----------------------------+
                          | ~/.katrain/                 |
                          |  kifunarabe_weaknesses/      |
                          |  2026-07-18_*_*.json        |
                          +-----------------------------+
```

summary popup からの遷移:

```
                  +-------------------+
                  | kifunarabe summary|
                  |  popup            |
                  +---+----+-----+----+
                      |    |     |
              next   |    |     |  abort
              sgf    |    |     |
                      v    v     v
              [SGF sel] [Imp] [end]
                       Moves  session
                       list
```

## 3. 実装内容

### 3.1 γ-1: 重要局面リスト統合 (Phase 248 統合)

- `kifunarabe_summary.py` の summary popup に「重要局面」ボタン追加
- 既存 `open_important_moves_popup` (Phase 248-γ-D1) を再利用
- kifunarabe 終了時に Critical 3 セット全体をレビュー → 該当局面にジャンプ可能

i18n:
- `kifunarabe:summary:important_moves`: 「重要局面」/「Important moves」

### 3.2 γ-2: 弱点自動 export (opt-in)

- 新規 `KifunarabeWeaknessExporter` (コア層、Kivy 非依存)
- 新規 `KifunarabeWeakness` dataclass
- 設定: `kifunarabe/auto_export_weaknesses` (デフォルト False)
- 設定: `kifunarabe/auto_export_dir` (デフォルト `~/.katrain/kifunarabe_weaknesses/`)
- `KifunarabeConfig.auto_export_weaknesses: bool` フィールド追加
- `_end_session` から `_export_weaknesses(sgf_path)` 呼び出し
- WRONG_GUESS 結果のみ抽出。`CRITICAL_3_WRONG` 重大度付与
- ファイル名: `YYYY-MM-DD_HHMMSS_<safe_suffix>.json`
- ペイロード形式:

```json
{
  "schema_version": 1,
  "session_summary": {
    "total_positions": 5,
    "wrong_count": 2,
    "sgf_path": "Z:/games/game.sgf",
    "config": {"turn": "B", "max_hints": 3, "max_moves": 0}
  },
  "weaknesses": [
    {
      "timestamp": "2026-07-18T09:30:14",
      "sgf_path": "Z:/games/game.sgf",
      "move_number": 2,
      "expected_gtp": "D5",
      "guessed_gtp": "E6",
      "hints_shown": 3,
      "severity": "CRITICAL_3_WRONG"
    },
    ...
  ]
}
```

i18n:
- `mykatrain:settings:kifunarabe_auto_export_weaknesses`: 「誤答局面を弱点として自動保存」
- `mykatrain:settings:kifunarabe_auto_export_dir`: 「棋譜並べ弱点フォルダ」

### 3.3 設定 UI

`kifunarabe_tab.py`:
- SGF フォルダ行 → 履歴ディレクトリ行 → 弱点ディレクトリ行の順に追加
- 「弱点自動 export」チェックボックス (Phase 249-γ で追加)
- チェックボックスとディレクトリ行を連動 (opt-in)

## 4. テスト

新規 `tests/test_kifunarabe_weakness_export.py` 14 件:
- WRONG_GUESS 抽出 (`collect_weaknesses`)
- 空セッション / 正解のみ / AUTO_ADVANCE のみの除外
- SGF パス伝播 / hints_shown 保持
- `export` のファイル作成 / ディレクトリ作成 / safe suffix / `_manual` suffix
- ペイロード shape (schema_version / session_summary / weaknesses 配列の構造)
- `default_export_dir` が `~/.katrain/kifunarabe_weaknesses` を返す

## 5. 影響範囲

- 新規: 2 ファイル (`kifunarabe_weakness_export.py` / `test_kifunarabe_weakness_export.py`)
- 修正: 5 ファイル (controller / session_mixin / summary popup / settings tab / __main__)
- コア層拡張: `KifunarabeConfig.auto_export_weaknesses` フィールド追加
- i18n: 3 キー追加 (jp / en)

## 6. 残タスク (本 Phase スコープ外)

- 弱点 JSON を直接 Karte JSON に変換
- Batch 解析で weakness JSON を一括 ingest
- 弱点 popup からの「該当局面にジャンプ」
- weakness データの可視化 (時系列、棋力別)
