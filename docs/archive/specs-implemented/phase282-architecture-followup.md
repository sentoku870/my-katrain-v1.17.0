# Phase 282: アーキテクチャレビュー P1+P2 着手

> **ステータス**: 完了（2026-07-21）
> **レベル**: Lv2
> **影響範囲**: テスト層 + アーキテクチャ健全化（コード変更なし）

---

## 1. 背景

Phase 280（AI 戦略 17→2 スリム化）完了時点で、`tests/conftest.py` に Phase 280 の影響が反映されず、以下の問題が残存していました：

1. **死蔵コード**: Phase 280 で削除された 14 AI 戦略を前提とした `MockKaTrainWithAI` クラス（103 行）+ 孤児化したヘルパー関数 14 個（103 行）が残り、合計 851 行の conftest.py のうち 351 行が死蔵
2. **スモークテスト不足**: 5 大ファイル（`core/curator/scoring.py` / `core/engine_io.py` / `gui/features/summary_pattern.py` / `gui/features/batch_ui.py` / `gui/features/diagnostics_popup.py`）に最低限のテストが存在せず、refactoring 時の regression 検知が困難
3. **i18n カウンタ不整合**: AGENTS.md §1.3 / §10 で "920 entries" と記載されているが、過去 Phase の累積削除で現状は 894 entries
4. **defensive コード未テスト**: `katrain/__main__.py` の defensive `try/except` 経路（`on_kifunarabe_mode` / `on_request_close` 等）が未テスト

これらはアーキテクチャレビューの **P1（最優先）** + **P2（高優先）** 課題として位置付けられ、本 Phase で着手しました。

---

## 2. サブフェーズ索引

| Subphase | レベル | 内容 | テスト数 |
|----------|:------:|------|:--------:|
| **P1-A** | Lv2 | `tests/conftest.py` 死蔵コード除去 851 → 500 行 | - |
| **P1-B** | Lv2 | 5 大ファイルのスモークテスト追加 | 197 |
| **P1-C** | Lv2 | `gui/widgets/filebrowser.py` minimum tests | 32 |
| **P2-A** | Lv2 | `core/reports/summary_json_export.py` `_build_*` 14 関数 unit tests | 58 |
| **P2-B** | Lv2 | `katrain/__main__.py` defensive `try/except` 経路 smoke tests | 19 |
| **P2-C** | Lv1 | AGENTS.md i18n カウンタ整合（920 → 894 entries） | - |

**合計**: 312 新規テスト（+ α、Phase 282 baseline 5805 → 6118 PASS + 3 SKIP）

---

## 3. サブフェーズ詳細

### 3.1 P1-A: `tests/conftest.py` 死蔵コード除去

**問題**: Phase 280 で AI 戦略 14 個を削除したが、`tests/conftest.py` には旧 AI 戦略を前提としたコードが残存：

- `MockKaTrainWithAI` クラス（103 行）: 削除済み戦略を `mock` する dead class
- `high/medium/low_confidence_moves` / `sparse_moves` fixture
- `mock_katrain_ai` fixture
- `make_candidate_move` / `install_node_analysis` / `is_ci_environment` / `normalize_radar_output` / `load_golden_json` / `save_golden_json` / `round_half_up` / `_stabilize_float` / `RADAR_SCHEMA_DEFAULTS` の 14 個の孤児関数

**修正**:
- `MockKaTrainWithAI` クラス削除（103 行）
- 14 個の死蔵関数 + 3 個の孤児 fixture 削除
- `conftest.py` 851 行 → 500 行（**-351 行 / -41%**）

**効果**: テストセットアップ時間が短縮、refactoring 時の影響範囲が明確に

### 3.2 P1-B: 5 大ファイルのスモークテスト追加

| ファイル | テストファイル | テスト数 | 内容 |
|----------|----------------|:--------:|------|
| `core/curator/scoring.py` | `tests/test_curator_scoring.py` | 43 | `_normalize_meaning_tag_key` / `_combine_meaning_tags` / `_extract_user_weak_tags` / `_compute_jaccard_score` / `_round_half_up` / `_wrap_debug_info` / `_compute_volatility` / `_compute_total` / `compute_batch_percentiles` |
| `core/engine_io.py` | `tests/test_engine_io.py` | 11 | `_ensure_str` 7 ケース + 4 thread 関数シグネチャ回帰検知 |
| `gui/features/summary_pattern.py` | `tests/test_summary_pattern.py` | 53 | `_normalize_board_size` / `_is_valid_player` / `_is_valid_gtp` / `_is_valid_move_number` / `_stable_sort_key` / `_filter_by_board_size` / `_format_game_refs` / `_PatternMoveEval` |
| `gui/features/batch_ui.py` | `tests/test_batch_ui_widgets.py` | 35 | pure logic + AST 構造回帰検知 (Kivy font pipeline 非依存) |
| `gui/features/diagnostics_popup.py` | `tests/test_diagnostics_popup.py` | 55 | `_collect_diagnostics` 防御経路 7 ケース + i18n キー 16 個 × 2 .po 整合性 |

### 3.3 P1-C: `gui/widgets/filebrowser.py` minimum tests

- 32 件のテストを追加
- `last_modified_first` sort / `_shorten_filenames` 4 分岐 / `get_drives` Linux 分岐 / public API 静的ガード

### 3.4 P2-A: `core/reports/summary_json_export.py` 58 tests

- `_build_*` 14 関数を unit test でカバー
- `_data_status_for` 3-state / `_build_overall_block` / `_build_mistake_distribution` / `_build_phase_distribution` (yose → endgame mapping) / `_build_reason_tags_block` 3-state / `_build_mistake_sequences_block` 3-state / `_build_empty_player_stats_block` / `_derive_basic_reason_tags` / public surface 16 関数シグネチャ

### 3.5 P2-B: `katrain/__main__.py` defensive smoke tests

- 19 件の smoke tests を追加
- `on_kifunarabe_mode` 防御 / `AppContext` lazy import / `KifunarabeHistoryStore` / `KifunarabeWeaknessExporter` lazy import / `on_request_close` engine.shutdown 失敗時 cleanup 継続 / webbrowser / `is_valid_window_position`

### 3.6 P2-C: AGENTS.md i18n カウンタ整合

- 報告の "920 entries" は過去 Phase の累積削除で現状 894 entries まで減少
- 3 箇所（§1.3 / §10 過去ログ）を「894 ずつ」に統一
- `polib` で実測した結果、jp/en .po はそれぞれ 894 entries

---

## 4. 検証結果

```
mypy katrain: 0 issues (310 source files)
ruff check: clean
ruff format: clean
pytest tests: 6118 PASS + 3 SKIP (Phase 281 baseline 5862 → +256 件)
```

---

## 5. 保持された概念

- 既存の `tests/conftest.py` の API シグネチャ・公開 fixture は全て温存
- `MockKaTrainStub` / `MockEngine` 等の legacy クラスは維持（既存テストが利用中）
- Kivy headless 環境変数のセットアップは `conftest.py` ロード時に継続（Phase 241-H で追加）
- 既存の i18n / dispatch / menu / popup テストは全て不変

---

## 6. 関連 Phase

- **Phase 241-H**: `tests/conftest.py` に Kivy headless 環境変数追加（本 Phase の前提）
- **Phase 281**: 日本語フォント tofu fix（本 Phase のスモークテスト実行環境で活用）
- **Phase 280**: AI 戦略 17→2 スリム化（本 Phase の死蔵コード削除動機）

---

## 7. 関連ドキュメント

- `AGENTS.md` §1.3（直近マイルストーン）
- `docs/01-roadmap.md` §4（Phase 282 詳細）
- `docs/02-code-structure.md` §5.7（Phase 280 削除ファイル一覧）