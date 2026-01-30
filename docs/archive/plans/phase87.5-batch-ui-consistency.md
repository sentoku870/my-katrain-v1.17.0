# Phase 87.5: Batch Analysis UI & Settings UI Consistency

> 完了: 2026-01-30
> PR: #226

## Overview

Batch Analysis UIとSettings UIの一貫性・安全性を改善する。

**修正レベル**: Lv3（複数ファイル）

---

## 実装内容

### Task 0: Leela enabled 検出ヘルパー（重複排除）
- `is_leela_configured()` を `batch_core.py` に追加
- batch_ui.py と settings_popup.py から共通利用

### Task 1: analysis_engine と leela_engine を run_batch() に渡す [CRITICAL]
- 3ステップ Leela 起動ロジック:
  1. 既存エンジンが alive か確認
  2. alive でなければ起動試行
  3. 最終検証 → 失敗時は STATUS_ERROR で通知
- i18n: `mykatrain:batch:leela_start_failed` 追加

### Task 2: Variable visits 連動コントロール
- Variable visits OFF時に Jitter%/Deterministic を disabled

### Task 3: Leela選択のゲーティング
- Batch UI: Leela 未設定時は disabled + 警告ラベル
- Settings UI: Leela 未設定時は CheckBox を disabled

### Task 4: Leela設定へのショートカットボタン
- settings_popup.py に `initial_tab` パラメータ追加
- batch_ui.py に "Setup Leela" ボタン追加

### Task 5: ラベル単位の明確化
- `Visits (per move)` / `訪問数 (手毎)`
- `Timeout (sec/file)` / `タイムアウト (秒/ファイル)`

### 追加修正（Leela バッチ解析対応準備）
- `extract_game_stats()` に `snapshot` パラメータ追加
- `build_karte_report()` に `snapshot` パラメータ追加
- orchestration.py で `leela_snapshot` を渡すように修正

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|----------|----------|
| `katrain/__main__.py` | Leela gating呼び出し |
| `katrain/core/batch/orchestration.py` | leela_snapshot渡し、karte有効化 |
| `katrain/core/batch/stats/extraction.py` | snapshot パラメータ追加 |
| `katrain/core/reports/karte/builder.py` | snapshot パラメータ追加 |
| `katrain/gui/features/batch_core.py` | is_leela_configured()、3ステップLeela起動 |
| `katrain/gui/features/batch_ui.py` | Variable visits連動、Leelaゲーティング、ショートカットボタン |
| `katrain/gui/features/settings_popup.py` | initial_tab対応、Leelaゲーティング |
| `katrain/i18n/locales/*/katrain.po` | ラベル更新、エラーメッセージ追加 |
| `tests/test_batch_engine_option.py` | TestIsLeelaConfigured テスト追加 |

---

## テスト結果

- 3199 テストパス
- TestIsLeelaConfigured: 7件追加

---

## 既知の制限

Leelaバッチ解析でのkarte/summary生成は別Phaseで対応予定。
