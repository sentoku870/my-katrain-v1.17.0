# Phase 249-β: Kifunarabe 履歴保存 (Persistent History)

> 起票日: 2026-07-18
> ステータス: 🚧 進行中
> 関連: Phase 177 仕様書 §7 / Planned 4 (棋譜並べ成績の履歴保存)

## 1. 動機

Phase 177 §7 Planned 4 として「棋譜並べ成績の履歴保存 (JSON シリアライズ)」
が 2 年近く未着手のままだった。summary popup を閉じると結果が消失し、
弱点の経過観察や複数局比較ができなかった。Phase 249-α (バグ修正) で
基盤を整備したので、本 Phase で Planned 4 を実装する。

## 2. アーキテクチャ

```
+----------------+        +-----------------------------+
| KifunarabeCtrl | append | KifunarabeHistoryStore      |
|  _end_session  |------->|  - directory: Path          |
+----------------+        |  - append(summary, config)  |
                          |  - list_entries(limit)     |
                          |  - count()                  |
                          +--------------+--------------+
                                         |
                                         v
                          +-----------------------------+
                          | JSON file:                  |
                          |  ~/.katrain/kifunarabe_     |
                          |  history/2026-07-18_*_*.json|
                          +-----------------------------+
```

## 3. 実装内容

### 3.1 コア層: `KifunarabeHistoryStore`

新規 `katrain/core/study/kifunarabe_history.py`:

- `KifunarabeHistoryEntry` dataclass: timestamp / sgf_path / config / summary / critical_3_set
- `KifunarabeHistoryStore` class:
  - `__init__(directory=None)`: デフォルト `~/.katrain/kifunarabe_history`
  - `append(summary, config, sgf_path, critical_3_set)`: 1 ファイル書き込み
  - `list_entries(limit=None)`: 全 JSON を読み込み newest-first ソート
  - `count()`: ファイル数
- ファイル名: `YYYY-MM-DD_HHMMSS_<safe_suffix>.json`
- safe_suffix: SGF 名の stem、英数字とハイフン/アンダースコア以外をアンダースコアに
- malformed JSON ファイルはスキップ (warning ログ)

### 3.2 Controller 統合

`katrain/gui/managers/kifunarabe_controller.py`:
- `__init__` に `history_store: KifunarabeHistoryStore | None` 引数追加 (DI)
- `_persist_history(summary_data)` ヘルパー新設
- `_end_session(show_summary)` から `_persist_history` を呼び出し
- SGF パスは `game.root.sgf_path` から取得 (try/except で失敗時 None)

### 3.3 GUI 統合

`katrain/gui/popups/kifunarabe_history_popup.py` 新設:
- `show_kifunarabe_history(ctx, history_store)` 関数
- 最新 50 件のサマリをスクロール可能 Label で表示
- 各エントリ: 日時 / SGF ファイル / total / correct / wrong / auto / skip / correct rate / Critical 3
- 履歴未設定 or 空のときの i18n 対応メッセージ

`katrain/gui/features/kifunarabe_summary.py`:
- summary popup に「履歴」ボタン追加 (3 ボタン構成)
- `on_show_history()` ハンドラ追加

### 3.4 設定 UI 統合

`katrain/gui/features/settings_popup_tabs/kifunarabe_tab.py`:
- SGF フォルダ行の直下に「履歴ディレクトリ」行を追加
- `kifunarabe/history_dir` config キーで永続化

### 3.5 i18n

新規 5 キー (jp / en):

| キー | JP | EN |
|------|----|----|
| `kifunarabe:history:title` | 棋譜並べ - 履歴 | Kifu Narabe - History |
| `kifunarabe:history:not_configured` | 履歴がまだ有効化されていません。 | History is not configured yet. |
| `kifunarabe:history:empty` | 履歴がまだありません。 | No history entries yet. |
| `kifunarabe:history:close` | 閉じる | Close |
| `kifunarabe:summary:history` | 履歴を見る | Show history |
| `kifunarabe:summary:overall_rate` | 全体率 (自動進行込み): {overall_rate} | Overall rate (incl. auto-advance): {overall_rate} |
| `mykatrain:settings:kifunarabe_history_dir` | 棋譜並べ履歴フォルダ | Kifu Narabe history folder |

## 4. summary popup 拡張 (β-2)

`correct_rate` (ユーザーがクリックした手の中の正解率) と
`overall_rate` (自動進行を正解扱いした全体率) を 2 値表示。
auto-advance が多い局面で「全体率が高いのに正解率が低い」場合の
誤読を防ぐ。

## 5. テスト

新規 `tests/test_kifunarabe_history.py` 12 件:

- ファイル作成 / SGF 名の safe 化 / None SGF の `manual` suffix
- summary / config / critical_3_set の round-trip
- newest-first ソート
- limit パラメータ
- malformed JSON スキップ
- count / 空ディレクトリ
- default_history_dir
- KifunarabeHistoryEntry の to_dict / from_dict

## 6. 設定

`config.json` (デフォルト):

```json
{
  "kifunarabe": {
    "history_dir": ""
  }
}
```

空文字 = デフォルト `~/.katrain/kifunarabe_history` を使用。

## 7. 影響範囲

- 新規: 3 ファイル (`kifunarabe_history.py` / `kifunarabe_history_popup.py` / `test_kifunarabe_history.py`)
- 修正: 5 ファイル (controller / session_mixin / summary popup / settings tab / __main__)
- i18n: 5 キー追加 (jp / en .po + .mo 同期)

## 8. 関連ドキュメント

- Phase 177 §7 / Planned 4
- Phase 249-α (基盤整備)
- Phase 249-γ (Karte 統合予定)

## 9. 残タスク (本 Phase スコープ外)

- 履歴の GUI からの削除
- 履歴 popup での詳細表示 (1 エントリクリックで summary を再表示)
- 履歴データからの弱点パターン分析 (LLM 入力用)
- 履歴ディレクトリ監視 (外部ツール用)
