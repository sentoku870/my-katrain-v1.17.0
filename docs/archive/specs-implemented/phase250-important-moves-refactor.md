# Phase 250: 重要局面 UI リファクタリング

**日付**: 2026-07-18
**種別**: Lv3 (UI 整理 + 機能廃止)
**コミット**: 1PR に統合
**テスト**: 11 件新規 (color_filter navigation)

## 背景 (ユーザー要望)

ユーザー報告より:

> （タブ）目差・勝率・重要局面
> グラフ
> 黒の前の重要局面・黒の次の重要局面・白の前の重要局面・白の次の重要局面
> 重要局面をタブでオン・オフを表示切替可能に勝率の横に移動
> 白黒の前と次の４ボタンに分割
> 大悪手と重要局面リストは廃止（他に影響がないかを確認後）

つまり:
1. グラフ上にタブ「目差・勝率・重要局面」を配置、重要局面ライン表示切替
2. 重要局面ナビゲーションを白黒別の 4 ボタンに分割
3. 大悪手ライン (オレンジ) 廃止
4. 重要局面リスト popup 廃止

## サブフェーズ索引

| サブ | 内容 | ファイル |
|---|---|---|
| 250-A | タブ「重要局面」追加 + 旧トグル削除 | `katrain/gui/kv/panels.kv` |
| 250-B | `GameNavigator` を `color_filter` 対応に拡張 | `katrain/core/game/navigation.py`, `katrain/core/game/facade.py` |
| 250-C | Prev/Next ボタンを 4 ボタンに置換 (黒前/黒次/白前/白次) | `katrain/gui/kv/panels.kv`, `katrain/gui/features/commands/analyze_commands.py`, `katrain/gui/managers/game_state_manager.py`, `katrain/gui/features/commands/__init__.py` |
| 250-D | 大悪手ライン (mistake_points) 削除 | `katrain/gui/widgets/graph.py` |
| 250-E | 重要局面リスト popup 廃止 (ファイル削除) | `katrain/gui/popups/important_moves_popup.py` (削除), `katrain/gui/kv/important_moves_popup.kv` (削除), `katrain/core/analysis/important_moves_popup.py` (削除), `katrain/gui/features/commands/popup_commands.py`, `katrain/gui/features/commands/__init__.py`, `katrain/gui/kv/menu.kv`, `katrain/i18n/locales/*` |
| 250-F | 棋譜並べ summary から重要局面 popup 呼び出し削除 | `katrain/gui/features/kifunarabe_summary.py` |
| 250-G | テスト削除 + 4 ボタン用テスト新規 | `tests/test_important_moves_popup.py` (削除), `tests/test_important_move_navigation.py` (削除), `tests/test_phase258_critical_popup_reason.py` (削除), `tests/test_color_filter_navigation.py` (新規) |
| 250-H | ドキュメント更新 | `AGENTS.md`, `docs/01-roadmap.md`, `docs/archive/specs-implemented/phase250-important-moves-refactor.md` (本ファイル) |

## 影響範囲

### 保持

- `MistakeCategory` enum (Karte `weaknesses` 分類で使用)
- `select_critical_moves` (Karte `critical_3` セクション + LLM Coach で使用)
- `Karte JSON` の `critical_3` セクション
- `critical_3_max_moves` 設定 (Karte JSON 用、UI 残置)
- `important_moves_level` 設定 (同上)
- `_compute_important_moves` 内部ロジック (color_filter 追加で機能拡張)
- 既存 `prev_important` / `next_important` DISPATCH キー (後方互換)

### 削除

- 大悪手ライン (graph Canvas の `[1, 0.6, 0.2, 0.9]` 縦線)
- `mistake_points` プロパティ
- 重要局面リスト popup (GUI/KV/core 3 ファイル)
- メニュー「重要局面リスト」項目
- 棋譜並べ summary の「重要局面を表示」ボタン挙動
- i18n キー 9 個 (`mykatrain:important-moves` + `mykatrain:popup:important-moves:*`)

### 追加

- 4 ボタン (黒前/黒次/白前/白次) 0.25 ずつ横一列
- タブ「重要局面」 (重要局面ライン ON/OFF)
- `color_filter` パラメータ (`GameNavigator` の 6 メソッド + facade 6 メソッド)
- DISPATCH キー 4 個 (`prev/next_important_black/white`)
- 内部メソッド 4 個 (`do_prev/next_important_black/white`)
- i18n キー 5 個 (`tab:important`, `prev/next-important-move-black/white`)

## 設計判断

### Prev/Next ロジック

`GameNavigator._compute_important_moves(max_moves=20, color_filter=None)` を拡張。
`color_filter` が `"B"` または `"W"` のとき、`node.player` でフィルタする。
`color_filter=None` は従来挙動（全プレイヤー対象）。

### 大悪手 vs 重要局面ライン

- **大悪手ライン**: `MistakeCategory.BLUNDER` 分類 + `points_lost > 閾値`
- **重要局面ライン**: 重要度 = `max(points_lost, |delta_score|)` ≥ 0.5目 上位 20件

2 系統が重なって表示されていたため、20回以上に見える現象が起きていた。
Phase 250 で大悪手ラインを廃止し、重要局面ライン単独に整理。
`show_important_line` フラグで ON/OFF 切替（タブから制御）。

### 重要局面リスト popup 廃止後の代替

4 ボタン (黒前/黒次/白前/白次) で「クリティカルな局面へのジャンプ」が代替可能。
critical_3 リスト（複数局面一覧）の閲覧は `phase249-hotfix` で追加された「重要局面リスト」メニューが消えるため、別経路を検討 → Phase 250 では未対応（必要なら次フェーズで検討）。

### `critical_3_max_moves` 設定の扱い

LLM Coach が Karte `critical_3` セクションを読むため、設定は **残す**。
重要局面リスト popup は廃止されたが、JSON 経由での利用は継続。

## テスト

| テスト | 状態 | 件数 |
|---|---|---|
| `tests/test_color_filter_navigation.py` (新規) | PASS | 11 |
| `tests/test_important_moves_popup.py` (削除) | - | -19 |
| `tests/test_important_move_navigation.py` (削除) | - | -20 |
| `tests/test_phase258_critical_popup_reason.py` (削除) | - | -5 (推定) |

**正味**: 11 件新規、計 44 件削除（累計テスト数は減少）。

## 既知の制限 / 将来課題

- 棋譜並べサマリーの「重要局面を表示」ボタンは no-op 化。完全削除は別フェーズで。
- 大悪手ラインのスコア (BLUNDER 分類) は Karte JSON には残るので、LLM 経由の分析は可能。
- 重要局面ラインの色 (`Theme.GRAPH_DOT_COLOR = [0.85, 0.3, 0.3, 1]`) は赤系で、旧大悪手ラインのオレンジとは別色。

## 動作確認手順

1. アプリ起動 (`python -m katrain`)
2. 右パネル上部のグラフを確認
3. タブ「目差 / 勝率 / **重要局面**」が 3 つ並んでいるか
4. 「重要局面」タブを OFF にすると重要局面ライン（赤系）が消える
5. グラフ下 4 ボタン「黒の前の重要局面 / 黒の次の重要局面 / 白の前の重要局面 / 白の次の重要局面」があるか
6. 各ボタンを押すと該当プレイヤーの重要局面にジャンプ
7. メニューに「重要局面リスト」が **ない** ことを確認
8. 棋譜並べサマリーを開いて「重要局面を表示」ボタンを押しても何も起きない (no-op)

## 関連 Phase

- **Phase 248-γ-D1**: 重要局面リスト popup 初版（廃止対象）
- **Phase 248-γ-D2**: prev/next 重要局面ヘルパー（廃止対象、color_filter 版に置換）
- **Phase 70**: 単一パス `_compute_important_moves`（color_filter 追加で機能拡張）
