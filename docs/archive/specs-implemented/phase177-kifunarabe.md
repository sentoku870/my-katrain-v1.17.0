# Phase 177: 棋譜並べ機能（Kifu Narabe）実装

> 起票日: 2026-07-04
> 完了: 2026-07-13（ドキュメント整備は Phase 178）
> ステータス: ✅ 完了

## 1. 概要

KataGo 解析済みの SGF を **「次の一手予測クイズ」** として再生する学習機能。
ユーザーは実戦手を当てる形式で弱点局面を反復練習できる。

機能名 `kifunarabe` はクラス名・関数名・設定キー・i18n プレフィックスなど実装全体に登場。

| 概念 | 意味 |
|------|------|
| 記録の手（actual move） | SGF に記録された実戦の手 |
| 選択肢マーカー | 盤上に表示される次の一手の候補群（実戦手 + KataGo best-N） |
| 予想的中 | ユーザーが実戦手をクリックする |
| 自動進行 | `turn="B"` または `turn="W"` 設定時、自分の手番でない側を自動進行 |

## 2. 動機と背景

ユーザーの v1 ゴール（カルテ生成 → LLM 添付）に加えて、「次点機能」として
重要局面クイズ・棋譜並べを Phase 1 完了済みの Active Review（Phase 93-94）の
発展形として実装した。

参考:
- [Phase 93-94 仕様書](./phase93-94-active-review.md)（旧 Active Review）
- [Smart Kifu Learning ドラフト](./smart-kifu-learning.md)（v0.2 仕様、未実装部分あり）

## 3. サブフェーズ実装ログ

### 3.1 A1/A2: メニュー・ショートカット統合

**意図**: メイン機能として昇格。メニュー・ショートカット・トグル同期の
単一責任者を controller に固定。

**実装**:
- `katrain/gui/kv/menu.kv:183-187` — メインメニューに「棋譜並べ」追加（`Ctrl-R`）
- `katrain/__main__.py:134` — `kifunarabe_mode = BooleanProperty(False)` 追加
- `katrain/__main__.py:319-327` — `KifunarabeController` を DI パターンで構築
- トグル同期は `KifunarabeController` が単一責任者

**検証**: メニュー / Ctrl-R 双方でセッション開始可能。

### 3.2 B1-B3: SGF 選択フロー

**意図**: 通常 SGF フォルダと専用フォルダを分離、元ファイルの上書き防止。

**実装**:
- `katrain/gui/popups/kifunarabe_setup_popup.py:269-335` — `open_kifunarabe_sgf_selector()`
- `gui._kifunarabe_fileselect_popup` という専用スロットで通常 SGF ダイアログと分離
- `_load_sgf_into_new_game()` で `sgf_filename=None` を渡し、元ファイルと切り離し
- 専用フォルダ `kifunarabe/sgf_load` を config に永続化

**検証**: Save Game で元ファイルが上書きされないことを確認。

### 3.3 C: 設定ポップアップ

**意図**: 先手/後手/両方、ヒント数、手数制限をユーザー選択。

**実装**:
- `katrain/gui/popups/kifunarabe_setup_popup.py:337-342` — `open_kifunarabe_setup_popup()`
- i18n キー: `kifunarabe:setup:*`（title, body, side_both/black/white, start, moves_50/100/150/all）

### 3.4 D: 候補マーカー描画

**意図**: 「実戦手と候補」が混在する盤面表示。

**実装**:
- `katrain/gui/badukpan_hints.py:144-183` — `prepare_hint_moves()` で kifunarabe mode を優先
- `_kifunarabe_options_to_hint_moves()`: GTP リスト → マーカー dict 変換
- `draw_kata_hint_moves()`: kifunarabe 用 text/border オーバーライド
- `draw_kata_hint_marker()`: 個別マーカー描画

### 3.5 E: 表示トグル（4 種）

**意図**: 「minimal」「KataGo詳細」の2モードを切り替え可能に。

**実装**: `katrain/core/constants.py:296-306` に設定キー定数化
- `kifunarabe/show_digits` (default `False`) — 数字表示
- `kifunarabe/show_actual_border` (default `False`) — 実戦手に枠線
- `kifunarabe/uniform_color` (default `True`) — 全マーカー同色
- `kifunarabe/auto_toggle_markers` (default `True`) — 次の一手・ドット自動 OFF

設定 UI: `katrain/gui/features/settings_popup_tabs/kifunarabe_tab.py`

### 3.6 F: 誤クリック記録（修正）

**意図**: 候補マーカー以外をクリックした場合も `WRONG_GUESS` として集計。

**修正前**: 候補外クリックで session が更新されず、統計から漏れていた。

**実装**:
- `KifunarabeController._record_wrong_guess()` を追加
- `handle_guess()` の `False` 分岐で必ず `_record_wrong_guess()` を呼ぶ

**検証**: テスト `TestWrongGuessIsRecorded` を追加。

### 3.7 G: max_moves-cap フロー分割

**意図**: 手数上限到達時に summary popup を表示しつつ、kifunarabe mode を維持。

**修正前**: 上限到達で即モード OFF → サマリも見ずに終了する UX 問題。

**実装**:
- `_end_session(show_summary: bool)` に分割
- `_show_session_summary()` 新設 — mode を維持したまま summary を出す
- `_check_session_ended()` を `handle_guess()` 末尾に追加

### 3.8 H: 解析トグル保存・復元

**意図**: 棋譜並べ中も show_children / eval のユーザー設定を保持。

**実装**:
- `_save_analysis_toggles()` / `_apply_kifu_toggle_mask()` / `_restore_analysis_toggles()`
- `kifunarabe/auto_toggle_markers = False` のときは保存/復元をスキップ

## 4. アーキテクチャ図

```
                   ┌─────────────────────────────┐
                   │  core/study/kifunarabe.py   │  ← Kivy 非依存
                   │  - KifunarabeConfig         │
                   │  - KifunarabeSession        │
                   │  - evaluate_guess()         │
                   │  - build_kifunarabe_options │
                   └────────────┬────────────────┘
                                │
                                ▼
                   ┌─────────────────────────────┐
                   │ gui/managers/               │
                   │   kifunarabe_controller.py  │  ← DI / session lifecycle
                   │  - start_session()          │
                   │  - handle_guess()           │
                   │  - disable_if_needed()      │
                   │  - abort_session()          │
                   └────────────┬────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
       ┌──────────────┐ ┌──────────────┐ ┌────────────────┐
       │ popups/      │ │ features/    │ │ badukpan_      │
       │ setup_popup  │ │ summary.py   │ │ hints.py       │
       │ (SGF + 設定) │ │ (結果表示)   │ │ (候補マーカー) │
       └──────────────┘ └──────────────┘ └────────────────┘
                │
                ▼
       ┌─────────────────────────────┐
       │  kv/menu.kv, panels.kv      │  ← UI 統合
       │  __main__.py                │
       └─────────────────────────────┘
```

## 5. 設定キー一覧（`KIFUNARABE_*` 定数）

| 定数 | キー | デフォルト | 用途 |
|------|------|:---------:|------|
| `KIFUNARABE_SHOW_DIGITS_KEY` | `kifunarabe/show_digits` | `False` | 数字表示 |
| `KIFUNARABE_SHOW_ACTUAL_BORDER_KEY` | `kifunarabe/show_actual_border` | `False` | 実戦手枠線 |
| `KIFUNARABE_UNIFORM_COLOR_KEY` | `kifunarabe/uniform_color` | `True` | 全マーカー同色 |
| `KIFUNARABE_AUTO_TOGGLE_MARKERS_KEY` | `kifunarabe/auto_toggle_markers` | `True` | 次の一手自動 OFF |
| `KIFUNARABE_SGF_LOAD_KEY` | `kifunarabe/sgf_load` | (空) | 専用 SGF フォルダ |

## 6. i18n キー一覧（en/jp 23 個）

| キー | EN | JP |
|------|----|----|
| `menu:kifunarabe` | 棋譜並べ | 棋譜並べ |
| `btn:AbortKifunarabe` | Abort Kifu Narabe | 棋譜並べ中断 |
| `kifunarabe:setup:title` | Kifu Narabe - Setup | 棋譜並べ - 設定 |
| `kifunarabe:setup:body` | Choose which side to play for and how many hints to show. | 予想する手番とヒント数を選択してください。 |
| `kifunarabe:setup:side_both/black/white` | Both sides / Black only / White only | 両方 / 黒番のみ / 白番のみ |
| `kifunarabe:setup:start` | Start | 開始 |
| `kifunarabe:setup:moves_50/100/150/all` | 50/100/150/All moves | 50/100/150/全部 |
| `kifunarabe:summary:*` | (6 個) | (6 個) |
| `mykatrain:settings:tab_kifunarabe` | Kifu Narabe | 棋譜並べ |
| `mykatrain:settings:kifunarabe_sgf_load` | Pro-game SGF folder (Kifu Narabe) | 棋譜並べ用 SGF フォルダ |
| `mykatrain:settings:kifunarabe_show_digits` | Show digit labels | 数字表示 |
| `mykatrain:settings:kifunarabe_show_actual_border` | Highlight the actual move | 実戦手に枠線 |
| `mykatrain:settings:kifunarabe_uniform_color` | Single colour markers | 全マーカー同色 |
| `mykatrain:settings:kifunarabe_auto_toggle_markers` | Auto-toggle next moves/dots | 「次の着手」「ドット」を自動切替 |
| `mykatrain:settings:kifunarabe_help` | (3 行) | (4 行) |

## 7. 既知の制約事項（Phase 178+ 候補）

| # | 内容 | Phase 178 での対応 |
|---|------|:-----------------:|
| 1 | ドキュメント未整備 | ✅ 解消（Phase 178 で spec 書 + roadmap + AGENTS 追記） |
| 2 | `_kick_root_analysis` の単発遅延 | ✅ 解消（Phase 178 でリトライ + 完了検知） |
| 3 | `disable_if_needed()` の呼び出しが 1 箇所のみ | ✅ 解消（Phase 178 で司令塔化） |
| 4 | 棋譜並べ成績の履歴保存（JSON シリアライズ） | 📋 Planned |
| 5 | カルテ/Batch 解析との統合 | 📋 Planned |
| 6 | `Active Review` との基底クラス共有 | 📋 Planned |
| 7 | 重要局面ジャンプ（`jump_to_next_important_move`）との統合 | 📋 Planned |
| 8 | 誤解析の手動報告 UI | 📋 Planned |

## 8. テスト

| ファイル | テスト数 |
|---------|:-------:|
| `tests/test_kifunarabe.py` | 48 |
| `tests/test_kifunarabe_controller.py` | 22 |
| `tests/test_kifunarabe_disable_helper.py`（Phase 178） | 3 |
| **合計** | **73** |