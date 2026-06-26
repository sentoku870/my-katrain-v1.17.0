# アーキテクチャレビュー（2026-06-26）

> myKatrain PC版 の静的解析によるアーキテクチャレビュー。Phase 142 完了時点の状態。
> 前回レビュー: `architecture-review-2026-06.md`（Phase 138-D 時点）

## エグゼクティブサマリ

- ソース 105,910 行 / テスト 94,028 行 / 204 + 125 ファイル / 3,509 テスト
- ランタイム循環 import: **60 件**（特に `__main__` ↔ `gui` で 8 件、core/game/facade ハブで 38 件）
- カバレッジ: **21%**（Kivy GUI 層がほぼ 0% のため）
- **mypy strict**: 204 ファイル エラー 0 件（Kivy プロジェクトとして異例の高品質）
- TODO/FIXME/XXX/HACK: **5 件**、`NotImplementedError`: **0 件**
- Kivy 隔離ルール違反: **1 件 runtime**（`core/base_katrain.py:7`）
- デッドコード候補: **2 件確定**（`MyKatrainDropDown`, `core/reports/types.py` のコメントアウト）

## 1. 規模分析

### 1.1 基本統計

| 項目 | 値 |
|---|---|
| Python ファイル総数 | 355（ソース 204 + テスト 125 + 設定 26） |
| ソースコード総行数 | 105,910 行 |
| テストコード総行数 | 94,028 行 |
| テスト/ソース比 | 0.89:1（量的には十分） |
| **カバレッジ（行）** | **21%**（20,276 stmts / 16,029 missed） |
| テストケース数 | 3,509 |
| mypy strict | 204 ファイル エラー 0 件 |
| TODO/FIXME/XXX/HACK | 5 件のみ |
| `NotImplementedError` | 0 件 |

### 1.2 行数トップ 20

| 順位 | ファイル | 行 | 種別 |
|---|---|---:|---|
| 1 | `tests/test_eval_metrics.py` | 2316 | テスト |
| 2 | `katrain/core/ai.py` | 1723 | ソース |
| 3 | `katrain/gui/badukpan.py` | 1630 | ソース |
| 4 | `katrain/core/analysis/logic.py` | 1494 | ソース |
| 5 | `tests/test_karte_structure.py` | 1425 | テスト |
| 6 | `katrain/gui/features/settings_popup.py` | 1425 | ソース |
| 7 | `katrain/core/analysis/models.py` | 1230 | ソース |
| 8 | `katrain/gui/features/summary_formatter.py` | 1203 | ソース |
| 9 | `katrain/__main__.py` | 1180 | ソース |
| 10 | `tests/test_batch_analyzer.py` | 1158 | テスト |
| 11 | `tests/test_cluster_classifier.py` | 1075 | テスト |
| 12 | `katrain/core/engine.py` | 1035 | ソース |
| 13 | `tools/pyside_board_poc/board_poc_plus.py` | 1018 | ツール |
| 14 | `tests/test_engine_commands.py` | 994 | テスト |
| 15 | `katrain/core/batch/helpers.py` | 966 | ソース |
| 16 | `tests/test_meaning_tags_classifier.py` | 957 | テスト |
| 17 | `tests/test_beginner_hints.py` | 942 | テスト |
| 18 | `tests/conftest.py` | 930 | テスト |
| 19 | `tests/test_game_logic.py` | 923 | テスト |
| 20 | `tests/test_critical_moves.py` | 900 | テスト |

### 1.3 500行超ソースファイル（30本）

**GUI 層（12本）**:
- `gui/badukpan.py:1` (1630), `gui/features/settings_popup.py:1` (1425)
- `gui/features/summary_formatter.py:1` (1203), `__main__.py:1` (1180)
- `gui/features/batch_ui.py:1` (640), `gui/features/diagnostics_popup.py:1` (410)
- `gui/widgets/filebrowser.py:1` (497), `gui/widgets/graph.py:1` (351)
- `gui/widgets/movetree.py:1` (343), `gui/controlspanel.py:1` (514)
- `gui/kivyutils/widgets.py:1` (512), `gui/popups/quick_config.py:1` (389)

**Core 層（16本）**:
- `core/ai.py:1` (1723), `core/analysis/logic.py:1` (1494)
- `core/analysis/models.py:1` (1230), `core/engine.py:1` (1035)
- `core/batch/helpers.py:1` (966), `core/analysis/cluster_classifier.py:1` (874)
- `core/sgf_parser.py:1` (775), `core/analysis/time/pacing.py:1` (697)
- `core/batch/orchestration.py:1` (621), `core/analysis/critical_moves.py:1` (568)
- `core/game/facade.py:1` (546), `core/game/analysis_orchestrator.py:1` (521)
- `core/analysis/meaning_tags/classifier.py:1` (519)
- `core/game_node.py:1` (593), `core/board_analysis.py:1` (487)
- `core/leela/engine.py:1` (470), `core/diagnostics.py:1` (472)

**Common 層（2本）**:
- `common/lexicon/validation.py:1` (510), `common/typed_config/models.py:1` (432)

## 2. 依存関係

### 2.1 import 数ランキング（Top 10）

| 順位 | ファイル | 合計 | 内部 | 外部 |
|---|---|---:|---:|---:|
| 1 | `katrain/__main__.py:1` | **70** | 39 | 31 |
| 2 | `katrain/gui/features/settings_popup.py:12` | 41 | 20 | 21 |
| 3 | `katrain/gui/popups/quick_config.py:8` | 31 | 22 | 9 |
| 4 | `katrain/gui/badukpan.py:1` | 29 | 12 | 17 |
| 5 | `katrain/gui/kivyutils/_base.py:6` | 27 | 4 | 23 |
| 6 | `katrain/gui/popups/config_popup.py:5` | 26 | 10 | 16 |
| 7 | `katrain/core/engine.py:4` | 22 | 8 | 14 |
| 7 | `katrain/core/game/facade.py:11` | 22 | 18 | 4 |
| 7 | `katrain/gui/features/batch_ui.py:11` | 22 | 8 | 14 |
| 10 | `katrain/gui/features/diagnostics_popup.py:6` | 22 | 10 | 12 |

### 2.2 循環依存（60 件確認）

**直接 cycle（runtime・実害あり）**:

| # | Cycle |
|---|---|
| 1 | `__main__` ↔ `core/analysis_result` |
| 2 | `__main__` ↔ `gui/error_handler` |
| 3 | `__main__` ↔ `gui/features/resign_hint_popup` |
| 4 | `__main__` ↔ `gui/features/commands/*`（4 ファイル） |
| 5 | `__main__` ↔ `gui/features/active_review_summary` / `active_review_ui` |
| 6 | `core/analysis` ↔ `core/analysis/critical_moves` |
| 7 | `core/analysis/models` ↔ `core/analysis/presentation` |
| 8 | `core/game/analysis_orchestrator` ↔ `core/game/facade` |
| 9 | `core/game/facade` ↔ `core/game/insert_mode` |
| 10 | `core/analysis/logic_loss` → `models` → `presentation` → `logic_loss`（3-cycle） |

**ハブモジュール（最も多くの cycle に参加）**:

| Count | モジュール |
|---:|---|
| 38 | `core/game/facade.py` |
| 36 | `core/game`（パッケージ） |
| 35 | `core/game/analysis_orchestrator` |
| 35 | `core/reports`（パッケージ） |
| 31 | `core/analysis/critical_moves` |

### 2.3 Kivy 隔離ルール違反

| ファイル | 行 | 種類 |
|---|---|---|
| `core/base_katrain.py:7` | `from kivy import Config` | **runtime**（実害あり） |
| `core/analysis_result.py:17` | `from katrain.__main__ import KaTrainGui` | TYPE_CHECKING（safe） |

### 2.4 God Module

| ファイル | 行 | クラス/関数 | 責務混在度 |
|---|---|---|---|
| `__main__.py`（`KaTrainGui`） | 1180 | 111 メソッド | 8 領域（エンジン、ゲーム状態、AI、ポップアップ、SGF I/O、Karte/サマリ出力、設定、UI/Animation/Sound） |
| `core/ai.py` | 1723 | 18 戦略クラス | 戦略ファミリ混在（Basic/Score/Ownership/Policy/Pick/Human） |
| `gui/features/settings_popup.py` | 1425 | 7 関数（うち `do_mykatrain_settings_popup` が 1008 行） | UI 構築 + I/O + 永続化 + 検索 |
| `gui/badukpan.py`（`BadukPanWidget`） | 1630 | 52 メソッド | 幾何計算 + 描画 + タッチ + アニメーション + ヒント + PV |
| `core/analysis/models.py` | 1230 | 26 クラス | Quiz + EvalSnapshot + SummaryStats + Engine 設定混在 |
| `core/analysis/logic.py` | 1494 | 32 関数 | 12 サブ領域（Skill/Reason/Reliability/Phase/Difficulty/Loss 等） |
| `core/engine.py`（`KataGoEngine`） | 1035 | 32 メソッド | プロセス I/O + Thread + Query + Error Recovery 混在 |
| `gui/features/summary_formatter.py` | 1203 | 24 関数 + 4 クラス | ノーマライズ + Pattern + Markdown 出力混在 |
| `core/batch/helpers.py` | 966 | 29 関数 | 5+ 領域（SGF I/O + ファイル名 + 検証 + エンジン + Markdown） |

### 2.5 巨大関数（200行超）

| ファイル:行 | 関数 | 行数 |
|---|---|---:|
| `gui/features/settings_popup.py:494` | `reopen_popup`（クロージャ） | **703** |
| `core/batch/orchestration.py:86` | `run_batch` | 462 |
| `gui/features/batch_ui.py:187` | `build_batch_popup_widgets` | 375 |
| `gui/badukpan.py:1138` | `draw_hover_contents` | 239 |
| `gui/badukpan.py:653` | `draw_board_contents` | 180 |
| `core/analysis/critical_moves.py:401` | `select_critical_moves` | 167 |
| `gui/features/summary_formatter.py:458` | `build_summary_from_stats` | 164 |
| `gui/controlspanel.py:204` | `update_evaluation` | 163 |

## 3. テスト

### 3.1 カバレッジ全体

- **21%**（Kivy GUI 層がほぼ 0% のため）
- テスト 3,509 件、テストコード 94,028 行
- 量的には十分だが**カバレッジが偏在**（Kivy GUI 層で 0% 多数）

### 3.2 完全未テスト × 大型モジュール（即対応候補 Top 12）

| 順位 | ファイル | LOC | 影響度 |
|---|---|---:|---|
| 1 | `gui/badukpan.py` | 1630 | 致命的（碁盤 UI の中核） |
| 2 | `gui/features/settings_popup.py` | 1425 | 致命的 |
| 3 | `katrain/__main__.py` | 1180 | 致命的（アプリエントリ） |
| 4 | `gui/features/summary_formatter.py` | 1203 | 致命的 |
| 5 | `gui/features/batch_ui.py` | 640 | 致命的 |
| 6 | `core/batch/orchestration.py` | 621 | 致命的（バッチ制御） |
| 7 | `core/diagnostics.py` | 472 | 大（専用テスト 17KB あるが本体未実行） |
| 8 | `core/curator/scoring.py` | 363 | 致命的（Curator 本体） |
| 9 | `core/study/active_review.py` | 405 | 致命的（専用テスト 22KB あるが 0%） |
| 10 | `gui/popups/config_popup.py` | 437 | 致命的 |
| 11 | `core/base_katrain.py` | 358 | 致命的（KaTrain 基底） |
| 12 | `core/auto_setup.py` | 377 | 致命的 |

### 3.3 部分的カバレッジ（0-30%）の重要ロジック

- `core/engine.py` 13%（実害大きい：エンジン本体）
- `core/game_node.py` 38%
- `core/sgf_parser.py` 45%
- `core/analysis/cluster_classifier.py` 22%
- `core/analysis/meaning_tags/classifier.py` 25%
- `core/analysis/time/pacing.py` 35%
- `core/leela/engine.py` 13%
- `core/batch/helpers.py` 15%
- `common/typed_config/models.py` 0%（16KB テストあるが 0%）
- `common/lexicon/validation.py` 0%（510 行・テスト 20KB あるが 0%）

### 3.4 テスト偏在パターン

- **専用テスト巨大だが本体未実行**の怪しい領域: `test_active_review.py` (22KB), `test_diagnostics.py` (17KB), `test_typed_config_*.py` 等

## 4. 保守性

### 4.1 責務曖昧度（Tier 1 = 3 領域以上混在）

| ファイル | 状態 |
|---|---|
| `gui/features/settings_popup.py:494` | UI + I/O + 永続化 + 検索 混在（703 行クロージャ） |
| `gui/badukpan.py` | 幾何 + 描画 + タッチ + アニメ + ヒント + PV 混在 |
| `__main__.py` | 既に Manager/Controller 委譲済みだが `KaTrainGui` に 111 メソッド残留 |
| `core/analysis/models.py` | 26 クラスが Quiz/Eval/Summary/Engine 設定で混在 |
| `core/analysis/logic.py` | 12 サブ領域が同一モジュール |
| `core/batch/helpers.py` | 「helpers」名で 5 領域混入 |
| `core/engine.py` | プロセス/Thread/Query/Error が一クラス |

### 4.2 分割候補

- `gui/kivyutils/widgets.py`（23 クラス混在 → 6 ファイル分割）
- `core/analysis/models.py`（26 クラス → 6 モジュール分割）
- `core/ai.py`（18 戦略 → 戦略ファミリ別ファイル）
- `core/analysis/logic.py`（12 セクション → モジュール分割）

### 4.3 デッドコード候補

| 場所 | 内容 | 対応 |
|---|---|---|
| `gui/badukpan.py:1572` | `class MyKatrainDropDown(DropDown): pass` | **削除可**（KV ファイルが名前参照中。1 行 alias に置換） |
| `core/reports/types.py:84-90` | 7 行のコメントアウトされたクラス定義 | **削除** |
| `core/engine.py:930` | `# TODO: support these` | 確認・対応 |
| `core/sgf_parser.py:412` | `# TODO: better placement support` | 確認 |
| `gui/badukpan.py:1255` | `# TODO: faster if not sized?` | 確認 |
| `core/constants.py:84` | `# TODO: remove some?` | 確認 |
| `core/game/base.py:65` | `# TODO: refactor?` | 確認 |

## 5. 改善提案（優先順位付き）

各提案に **効果 / コスト / リスク** を付与します。
- 効果: H/M/L（変更による改善度）
- コスト: XS/S/M/L/XL（作業規模・Lv レベル）
- リスク: H/M/L（リグレッション・後方互換の懸念度）

### 🔴 P0（即対応・品質リスク大）

#### 提案1: `core/base_katrain.py:7` の Kivy 隔離違反を解消
- **効果**: H（architecture 原則の明示的違反・core 層のテスト容易性を破壊）
- **コスト**: M（Kivy 設定を別モジュールに分離、`Config` 設定を 1 箇所に集約）
- **リスク**: M（Kivy 起動シーケンスへの副作用可能性）
- **Lv**: Lv3

#### 提案2: `__main__` ↔ `gui` 循環依存の解消（7 ファイル）
- **影響ファイル**: `gui/error_handler.py:20`, `gui/features/active_review_summary.py:25`, `gui/features/active_review_ui.py:24`, `gui/features/resign_hint_popup.py:23`, `gui/features/commands/{analyze,export,game,popup}_commands.py`
- **効果**: H（god class 解消の第 1 歩・gui/core 境界の明確化）
- **コスト**: L（7 ファイルのリファクタリング・callback/Protocol パターン導入）
- **リスク**: M（イベント伝播の再設計が必要）
- **Lv**: Lv4

### 🟠 P1（保守性リスク大）

#### 提案3: `gui/kivyutils/widgets.py` を 6 ファイルに分割
- **効果**: H（23 クラス混在の解消・検索性↑）
- **コスト**: M（ラベル/スピナー/プレイヤー/タイマー/パネル/クリッカブル）
- **リスク**: L（import パス変更のみ・KV ファイルへの影響なし）
- **Lv**: Lv3

#### 提案4: `core/analysis/models.py` を 6 モジュールに分割
- **効果**: H（26 クラス → 6 ファミリ：enums/move_eval/snapshot/skill/reliability/difficulty）
- **コスト**: M
- **リスク**: L（re-export で後方互換維持可能）
- **Lv**: Lv3

#### 提案5: `core/analysis/logic.py` の 12 セクション分割
- **効果**: H（1494 行の flat module を 12 モジュールに）
- **コスト**: L
- **リスク**: M（`logic_importance.py`, `logic_loss.py` パターンを踏襲）
- **Lv**: Lv4

#### 提案6: 巨大関数の分割
- `gui/features/settings_popup.py:494 reopen_popup`（703 行）→ タブ別ビルダーへ
- `core/batch/orchestration.py:86 run_batch`（462 行）→ `_setup_batch` / `_process_one_file` / `_finalize_batch`
- `gui/features/batch_ui.py:187 build_batch_popup_widgets`（375 行）→ 行ビルダー
- `gui/badukpan.py:1138 draw_hover_contents`（239 行）→ オーバーレイ別
- **効果**: H（可読性・テスト容易性）
- **コスト**: L〜XL
- **リスク**: M
- **Lv**: Lv3〜Lv4

### 🟡 P2（テストカバレッジ改善）

#### 提案7: Kivy ヘッドレステスト基盤の整備
- **対象**: `gui/badukpan.py`, `gui/features/settings_popup.py`, `gui/features/batch_ui.py` 等
- **効果**: H（21% → 40-50% への引き上げ）
- **コスト**: XL（Kivy ヘッドレスモック導入・`MockKaTrainStub` パターンの拡張）
- **リスク**: M（Kivy API の互換性問題）
- **Lv**: Lv5

#### 提案8: `core/batch/orchestration.py` の統合テスト追加
- **効果**: H（運用上の中核機能の安全網）
- **コスト**: M
- **リスク**: M（KataGo モックの整備）
- **Lv**: Lv3

#### 提案9: `core/curator/scoring.py` のユニットテスト
- **効果**: M
- **コスト**: M
- **リスク**: L
- **Lv**: Lv3

#### 提案10: 「テスト大・本体未実行」の検証
- 候補: `test_active_review.py` (22KB), `test_diagnostics.py` (17KB), `test_typed_config_*.py`
- **効果**: M（テストの有効性確認）
- **コスト**: S（呼び出し箇所の追加）
- **リスク**: L
- **Lv**: Lv1

### 🟢 P3（クリーンアップ）

#### 提案11: `MyKatrainDropDown` デッドクラス削除
- **効果**: L
- **コスト**: XS（`gui/badukpan.py:1572` の削除 + `kv/menu.kv:369` の参照確認）
- **リスク**: L
- **Lv**: Lv0

#### 提案12: `core/reports/types.py:84-90` コメントアウトコード削除
- **効果**: L
- **コスト**: XS
- **リスク**: L
- **Lv**: Lv0

#### 提案13: 5 件の TODO 解消（確認または対応）
- **効果**: L
- **コスト**: XS〜S
- **リスク**: L
- **Lv**: Lv0〜Lv1

#### 提案14: `core/ai.py` の 18 戦略をファミリ別ファイルに分割
- **効果**: M
- **コスト**: L
- **リスク**: L
- **Lv**: Lv3-Lv4

## 6. 総括

### 強み
- **mypy strict 完全パス**（204 ファイル・エラー 0）: Kivy プロジェクトとしては異例の高品質
- **0 `NotImplementedError`** + TODO が 5 件のみ: 技術的負債の管理が行き届いている
- テスト量 94K 行 / 3,509 件: 量的には十分
- Manager/Controller 委譲パターン（Phase 141: game → facade/analysis_orchestrator/base/insert_mode/navigation）が整備済み
- フェーズ別テスト命名規約（`test_phase105_notify` 等）で回帰検出が容易

### 弱み
1. **Kivy GUI 層がほぼ 0% カバレッジ**（致命的）
2. **god class/class が複数残留**（`__main__.py:140 KaTrainGui` 111 メソッド、`gui/features/settings_popup.py:494 reopen_popup` 703 行）
3. **60 件の循環依存**（特に `__main__` ↔ `gui`）
4. **専用テスト巨大だが本体未実行**の疑い（`test_active_review.py` 等）

### 推奨着手順
1. **P3-11,12,13** を一掃（30 分で終わる Lv0 クリーンアップ）
2. **P0-1**: `core/base_katrain.py:7` の Kivy 違反解消
3. **P1-3,4,5**: 大型ファイルの分割（モジュラリティ回復）
4. **P0-2**: 循環依存解消（god class 解消への布石）
5. **P2-7**: テストインフラ整備（中長期投資）

## 7. 変化点（vs 2026-06-25 レビュー）

| 項目 | 2026-06-25 | 2026-06-26 | 変化 |
|---|---|---|---|
| ソース LOC | 56,792 | 105,910 | +49,118（+86%） |
| テスト LOC | 46,406 | 94,028 | +47,622（+103%） |
| ソースファイル | 202 | 204 | +2 |
| テストファイル | 130 | 125 | -5 |
| テストケース | 3,184 | 3,509 | +325 |
| カバレッジ | 未測定 | 21% | 導入済 |
| ランタイム循環 import | 0 | 60 | +60 |
| デッドコード | 6,764 行削除済 | 2 件残存 | - |

**観察**: テスト量とファイル数は Phase 138-D 後の 1 ヶ月間で約 2 倍に成長。一方、循環依存が 0 → 60 に急増（リファクタリングと並行して god class の import が増えたため）。gui/features/commands/ 分割（提案 2 の対象）が直近の直接原因。

## 8. 参照

- 前回レビュー: `docs/archive/architecture-review-2026-06.md`（Phase 138-D 時点）
- ロードマップ: `docs/01-roadmap.md`
- AGENTS.md: `/AGENTS.md`
