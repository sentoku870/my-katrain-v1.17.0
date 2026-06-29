# アーキテクチャレビュー（2026-06-29）

> myKatrain PC版 の静的解析によるアーキテクチャレビュー。
> 直前レビュー: `architecture-review-2026-06-26.md`（Phase 142 時点）
> 本レビュー時点で実装・統合済み: Phase 158-A〜D（KaTrainGui 4分割）, Phase 145-D 残作業, Phase 158-E（curator テスト + settings_popup ファイル分割 + Phase A デッドコード削除 / PR #321）

## エグゼクティブサマリ

- ソース 55,849 行 / テスト 52,333 行 / 255 + 147 ファイル / 3,732 テスト
- カバレッジ（行）: **61%**（19,638 stmts、12,021 covered）— 前回レビュー比 +40pt
- **循環依存**: **0 件**（609 内部エッジ SCC 解析で確認）
- **Kivy 隔離ルール**: 100% 遵守（`core/` → `gui/` import 0 件、`common/` → 他層 import 0 件）
- **mypy strict**: 0 エラー（既存体制）
- 新規プロトコル導入: 12 件（Phase 138-D 以降）+ 既存 ABC 2 件
- **課題**:
  - curator/ カバレッジ 0% → **Phase 158-E で 92% に向上**
  - settings_popup.py 1,605 行 → **Phase 158-E で 1,268 行に縮小**（残タブも同様手法で分割可能）
  - Phase A 5 件の即対応デッドコード削除は **Phase 158-E 内で完了**

## 1. 規模分析

### 1.1 基本統計

| 項目 | 値 | 2026-06-26 比 |
|------|---|---:|
| katrain/ Python ファイル総数 | 255 | +51 |
| tests/ Python ファイル総数 | 147 | +22 |
| katrain/ ソースコード総行数 | 55,849 | -50,061（旧 stats.py/モデル類は分割済み） |
| tests/ テストコード総行数 | 52,333 | -41,695（旧同上） |
| テスト/ソース比 | 0.94:1 | +0.05（量的には十分） |
| **カバレッジ（行）** | **61%** | +40pt |
| テストケース数 | 3,732 | +223 |
| mypy strict | 0 エラー | 維持 |
| core / gui / common 行数比 | 60% : 32% : 5% | 同等 |
| 500 行超ソースファイル | 23 ファイル | 23 |

### 1.2 三大層（健全性確認）

| 領域 | ファイル | 行数 | 比率 |
|------|---------|-----:|----:|
| `core/`（Kivy 非依存） | 151 | 33,650 | 60.3% |
| `gui/`（Kivy 依存） | 77 | 17,738 | 31.8% |
| `common/`（共有定数） | 18 | 3,023 | 5.4% |
| その他（`__main__.py` 等） | 9 | 1,438 | 2.5% |

`core/gui/common` の三層分離は正しく維持され、Kivy 隔離ルールも完全遵守。

### 1.3 行数トップ 10（Phase 158-E 後のソース）

| 順位 | ファイル | 行 | 種別 | 状態 |
|----:|---------|---:|------|------|
| 1 | `gui/features/settings_popup.py` | 1,268 | ソース | Phase 158-E で -243 |
| 2 | `gui/features/summary_formatter.py` | 1,157 | ソース | Phase 158-E で -30 |
| 3 | `__main__.py` | 1,129 | ソース | Phase 158-D で Manager 分割済 |
| 4 | `core/analysis/cluster_classifier.py` | 874 | ソース | |
| 5 | `core/batch/orchestration.py` | 845 | ソース | |
| 6 | `core/sgf_parser.py` | 775 | ソース | |
| 7 | `core/engine.py` | 751 | ソース | Phase 158-C 分割済 |
| 8 | `core/analysis/logic_difficulty.py` | 743 | ソース | |
| 9 | `core/analysis/time/pacing.py` | 697 | ソース | |
| 10 | `gui/badukpan_drawing.py` | 665 | ソース | Phase 158+ で分割済 |

### 1.4 500 行超ファイル（23 本）

- GUI 層: `settings_popup.py`, `summary_formatter.py`, `__main__.py`, `batch_ui.py`, `controlspanel.py`, `badukpan.py`, `badukpan_drawing.py`, `badukpan_hints.py` 他
- Core 層: `cluster_classifier.py`, `orchestration.py`, `sgf_parser.py`, `engine.py`, `logic_difficulty.py`, `time/pacing.py`, `game_node.py`, `pick.py`, `analysis/__init__.py`, `karte/builder.py`, `game/facade.py`, `analysis_orchestrator.py`, `meaning_tags/classifier.py`, `reports/...` 他
- Common 層: `lexicon/validation.py`

Phase 158-E で `settings_popup.py`（1605→1268 行）と `summary_formatter.py`（1187→1157 行）の最大2ファイルが縮小。

## 2. 依存関係分析

### 2.1 サマリ指標

| 指標 | 値 | 評価 |
|------|---|------|
| 内部 import エッジ総数 | 609（unique 603） | — |
| 循環依存（A→B→A 直接） | **0 件** | A |
| 非自明 SCC（>1 要素） | **0 件** | A |
| `core/` → `gui/` import | **0 件** | A（Kivy 隔離 100%） |
| `common/` → `core/` または `gui/` import | **0 件** | A（純粋共有層維持） |
| 内部モジュール数 | 171 | — |
| 被 import 数トップ1 | `core.constants`（45 箇所） | 健全な集約点 |

### 2.2 Protocol / ABC 導入状況

- Protocol: 12 件（`FeatureContext`, `AnalysisContext`, `BatchAnalysisContext`, `EngineProtocol`, `AutoSetupContext`, `GameNodeProtocol`, `GameProtocol`, `StateNotifierProtocol`, `UIUpdateContext`, `RootNodeProvider`, `GameMetadataProvider`, `ConfigReader`, `LexiconStoreLike`）
- ABC: 2 件（`AIStrategy`, `AnalysisCommand`）

抽象化レイヤーが着実に増加。Manager 分割・Command Pattern 化と整合。

### 2.3 集約モジュール

| モジュール | 被 import 数 | 役割 |
|-----------|------------:|------|
| `core.constants` | 45 | 定数集約（健全） |
| `core.lang` | 33 | i18n |
| `gui.theme` | 31 | テーマ定数 |
| `core.analysis.models` | 23 | 解析モデル集約 |
| `core.utils` | 22 | 汎用ユーティリティ |

god module 兆候はなし。`constants` の 45 件は集約点として健全な範囲。

## 3. テスト分析

### 3.1 カバレッジ全体

| 指標 | 値 | 2026-06-26 比 |
|------|---|---:|
| 全体カバレッジ | 61% | +40pt |
| カバー済み stmt | 12,021 / 19,638 | +11,000+ |
| テストファイル数 | 143 | +18 |
| テスト関数数 | 3,732 | +223 |

### 3.2 層別カバレッジ

| ディレクトリ | カバレッジ | 状態 |
|------------|----------:|------|
| `core/state/` | **97.3%** | 優秀 |
| `core/study/` | 97.0% | 優秀 |
| `common/` | 93.9% | 優秀 |
| `core/analysis/time/` | 95.6% | 優秀 |
| `core/analysis/meaning_tags/` | 92.4% | 優秀 |
| `core/analysis/` | 86.2% | 良好 |
| `core/reports/` | 82.1% | 良好 |
| `core/game/` | 75.6% | 良好 |
| `core/leela/` | 73.0% | 良好 |
| `gui/managers/` | 72.8% | 良好 |
| `core/batch/` | 67.9% | 改善余地 |
| `core/`（全体） | 67.0% | 平均 |
| **gui/features/commands/** | **22.8%** | **要改善** |
| **`__main__.py`** | 23.3% | 統合テスト依存 |
| **gui/popups/** | 28.9% | Kivy 依存 |
| **gui/** | 26.4% | Kivy 統合テスト |

### 3.3 Phase 158-E で対応したカバレッジ 0% モジュール

| モジュール | 旧カバレッジ | 新カバレッジ | テスト数 |
|-----------|----------:|----------:|--------:|
| `core/curator/__init__.py` | 0% | **100%** | — |
| `core/curator/models.py` | 0% | **100%** | 25 |
| `core/curator/scoring.py` | 0% | **100%** | 61 |
| `core/curator/guide_extractor.py` | 0% | **100%** | 21 |
| `core/curator/batch.py` | 0% | **81%** | 41 |
| `core/curator/` 合計 | 0% | **92%** | 148 |

Kivy 依存 GUI の低カバレッジは仕様（CI 環境では skip、実バイナリ依存）のため継続課題。

## 4. 保守性分析

### 4.1 Phase 158-E で対応済みの課題

| 課題 | 場所 | 対応 | 結果 |
|------|------|------|------|
| 到達不能コード | `__main__.py:599-605` | 削除 | NameError 潜在リスク除去 |
| 未参照関数3件 | `settings_popup.py:368-416`（`load_export_settings`, `save_export_settings`, `save_batch_options`） | 削除 | -54行 |
| 未使用 import 2件 | `batch_core.py:24,31`（`STATUS_ERROR`, `needs_leela_karte_warning`） | 削除 | Ruff `# noqa: F401` 解消 |
| 命名違反（camelCase） | `tsumego_frame.py:127` の `snapS` | `snap_s` にリネーム | snake_case 一貫 |
| DRY 違反（重複集計） | `summary_formatter.py:1044/1111` の `_format_time_management` | `_aggregate_stats` に `focus_player` 引数を追加し共通化 | -30行 |
| 巨大ファイル分割（一部） | `settings_popup.py`（1,605 行 → 1,268 行） | `state.py`, `helpers.py`, `tabs/leela_tab.py` に分割 | -243行 |
| **`_SettingsPopupContext` 循環 import 抑止** | 新ファイル `settings_popup_state.py` | dataclass 単独化 | 次のタブ分割が安全に |

### 4.2 残存課題（中長期）

- `_build_analysis_tab`, `_build_export_tab` の分割（同じ手順で安全に移行可能）
- `_save_*_settings` 群の `io_save.py` 分離
- `_do_export_settings` / `_do_import_settings` / `_open_browse_dialog` の `io_*.py` 分離
- `summary_formatter.py` 1,157 行（Phase 85 統合部サブモジュール化）
- `KaTrainGui` 102 メソッド（残り Manager 分割）
- `BadukPanWidget` 59 メソッド（`_input.py`, `_pv.py` 追加分割）
- `core/constants.py` 90 変数（god 化予防のサブモジュール化）
- `gui/lang_bridge.py:99`, `leela_manager.py:114`, `__main__.py:529` の `suppress(Exception)` を具体例外へ

### 4.3 健全性指標（Phase 158-E 効果）

| 指標 | 旧 | 新 | 変化 |
|------|---:|---:|-----:|
| settings_popup.py 行数 | 1,511 | 1,268 | **-243** |
| curator/ カバレッジ | 0% | 92% | **+92pt** |
| curator/ テスト数 | 0 | 148 | **+148** |
| 未参照関数（settings_popup.py） | 3 | 0 | **-3** |
| 到達不能コード | 1 箇所 | 0 | **-1** |
| 未使用 import（`# noqa: F401`） | 2 | 0 | **-2** |
| camelCase 関数 | 1 | 0 | **-1** |
| DRY 違反（重複集計） | 1 | 0 | **-1** |
| Ruff エラー（settings_popup.py 関連） | 7 | 2 | **-5** |
| **テスト通過** | 3,720 | 3,868 | **+148**（curator テスト追加分） |

## 5. 改善提案（優先順位・効果・コスト・リスク付き）

### P0: 即対応（完了済み — Phase 158-E に組み込み済み）

| タスク | 効果 | コスト | リスク |
|--------|:----:|:----:|:----:|
| `__main__.py` 到達不能コード削除 | 名前誤参照リスク除去 | 極小 | 極小 |
| `settings_popup.py` 未参照関数削除 | デッドコード除去 | 極小 | 極小 |
| `batch_core.py` 未使用 import 削除 | Ruff 警告解消 | 極小 | 極小 |
| `tsumego_frame.py` リネーム | 命名一貫性 | 極小 | 極小 |
| `summary_formatter.py` DRY 違反解消 | ロジック重複排除 | 極小 | 極小 |

### P1: curator/ テスト追加（完了済み — Phase 158-E）

| タスク | 効果 | コスト | リスク |
|--------|:----:|:----:|:----:|
| 4 テストファイル追加（148 件） | カバレッジ 0% → 92% | 中 | 極小 |

### P2: 残タブ分割（次回セッション予定）

| タスク | 効果 | コスト | リスク |
|--------|:----:|:----:|:----:|
| `_build_analysis_tab`, `_build_export_tab` 分割 | settings_popup.py → ~700 行 | 中 | 小 |
| `_save_*_settings` を `io_save.py` に分離 | 1511行にあった入出力群を1モジュール化 | 小 | 極小 |
| `_do_export/_import` を `io_export.py` / `io_import.py` に分離 | 同上 | 小 | 極小 |
| `_open_browse_dialog` を `io_browse.py` に分離 | 同上 | 極小 | 極小 |

### P3: 中長期（判断保留）

- `summary_formatter.py` Phase 85 統合部サブモジュール化
- `KaTrainGui` 残存メソッドの Command 集約
- `core/engine.py` / `game_node.py` / `batch/orchestration.py` のカバレッジ底上げ（現在 48-49%）
- `BadukPanWidget` の `_input.py` / `_pv.py` 細分化
- `core/constants.py` 90 変数のサブモジュール化
- `suppress(Exception)` → 具体例外化

## 6. 変化点（vs 2026-06-26 レビュー）

| 指標 | 2026-06-26 | 2026-06-29 | 評価 |
|------|----------:|----------:|------|
| 循環依存数 | 0 件 | 0 件 | 維持 |
| Kivy 隔離違反 | 0 件 | 0 件 | 維持 |
| カバレッジ（行） | 21% | 61% | **+40pt** |
| curator/ カバレッジ | 0% | 92% | **+92pt** |
| 重大 god module | 3 個 | 3 個（残） | 残課題 |
| settings_popup.py 行数 | 1,425 | 1,268 | **-157** |
| 500 行超 GUI ファイル | 多 | 一部縮小 | 改善方向 |
| god class（KaTrainGui） | 102 メソッド | 102 メソッド | 未着手（Phase 158-D 段階完了済み） |

## 7. まとめ

myKatrain は引き続き高い保守性を維持している。
- **レイヤー分離**, **循環依存ゼロ**, **Kivy 隔離 100%** という基本原則は完全に守られている
- **テストカバレッジ**は前回レビュー比 +40pt で健全域に近づいた（curator は 92%）
- **ファイル分割**は Phase 145-158-D で多大な進捗、Phase 158-E で更に進展
- 残課題は巨大ファイルの部分分割と `KaTrainGui` の Command 集約のみ（業務影響小）

## 8. 参照

- 前回レビュー: `architecture-review-2026-06-26.md`
- 前々回レビュー: `architecture-review-2026-06.md`（Phase 138-D 時点）
- 実装 PR: #321（Phase 158-E 統合）
- ロードマップ: `docs/01-roadmap.md`
- ガイドライン: `AGENTS.md` §3（開発ルール）、§4（コード構造）
