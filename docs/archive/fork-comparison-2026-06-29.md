# フォーク元比較レポート（myKatrain vs upstream KaTrain）

> 作成日: 2026-06-29
> 比較対象: `sanderland/katrain` @ `13f3ea9`（フォーク直前の upstream HEAD）
> 比較対象: `sentoku870/my-katrain-v1.17.0` @ `4663009`（HEAD = PR #322 マージ後）
> 独自コミット: **967 件**

このドキュメントは、現行 myKatrain が upstream KaTrain から何を追加し、何を分割・リファクタリングし、何を削除したかを一覧化したスナップショットである。

---

## A. フォーク元から追加された主要機能

### A-1. カルテ（Karte）レポートシステム【最大の新機能】
KataGo 解析結果を LLM コーチング向け JSON 診断レポートとして出力する一連の機能。

| 機能 | フェーズ | 概要 |
|------|---------|------|
| `KarteReport` (v1) | Phase 17 以前 | 初期 Karte 実装 |
| `karte_report.py` → `karte/` パッケージ化 | Phase 72 | 12 モジュールへ分割 |
| LLM Package Export | Phase 11 | karte.md + sgf + coach.md を一括出力 |
| Schema v2.1 → v3.0 拡張 | Phase 149-C | 9 セクション復活（weaknesses / practice_priorities / mistake_streaks / urgent_misses / critical_3 / data_quality / reason_tags_distribution） |
| `definitions` オプトイン化 + 不要項目削除 | Phase 153 | schema 3.1（-642 行） |
| `win_loss_analysis` / `loss_progression` | Phase 154 | 勝敗別損失 + 手数帯別推移、schema 3.2 |
| `opponent_strength_loss_correlation` | Phase 155 | 相手の BR/WR 棋力バケット別相関、schema 3.3 |
| 動的フェーズ分割 | Phase 156 | `scoreStdev` ベースの終盤自動検出 |
| Summary even/handicapped 分割 | Phase 157-C | 置き碁/対等戦レジーム別 |
| 中国語 `段`/`级` 段級位対応 | Phase 157-B | SGF 漢数字パース |
| Report Navigator（GUI） | Phase 148-D | `.json` 拡張子統一、ナビゲータ追加 |
| `GameSummaryData.outcome` 型付け | Phase 154 | forward reference で循環依存回避 |
| `report_navigator.py`, `karte_export.py`, `summary_io.py` 等 | Phase 148-D | 出力 UI 統合 |

主要ファイル: `katrain/core/reports/{karte/, sections/, utils/, schema.py, definitions.py, extractors.py, summary_logic.py, types.py, summary_json_export.py, summary_report.py, important_moves_report.py, quiz_report.py}`

### A-2. Curator スコアリングシステム
LLM に渡す棋譜の「見せどころ」を自動選定。

| 機能 | フェーズ | 概要 |
|------|---------|------|
| Curator Scoring | Phase 63 | 安定性・percentile・Game ツリー解析 |
| Curator Output | Phase 64 | `HighlightMoment` / `ReplayGuide` 生成 |
| Curator UI 統合 | Phase 126 | Batch 分析にチェックボックス追加、スレッド安全性修正 |
| Curator テストカバレッジ 92% | Phase 158-E | 148 件追加 |

主要ファイル: `katrain/core/curator/{models, scoring, guide_extractor, batch}.py`

### A-3. Leela Zero 統合
KataGo 以外の Leela Zero 解析エンジンをサポート。

| 機能 | フェーズ | 概要 |
|------|---------|------|
| Leela batch 基盤 | Phase 36 PR-1 | `core/leela/` パッケージ新設 |
| Leela batch 解析 | Phase 36 PR-2 | KataGo と並列サポート |
| Leela → MoveEval 変換 | Phase 36-37 | 統合解析 |
| Leela Play mode | Phase 40 | 後に Phase 123 で削除（Analysis のみ残す） |
| Leela golden テスト | Phase 37 PR-3 | 検証体制 |
| Leela UI 改善 | Phase 132 | 候補手表示、設定拡張、force 解析 UX |
| `MixedEngineSnapshotError` | Phase 37 | 1 手でも KataGo/Leela 混在で例外 |
| LeelaConfig.get() 修正 | Phase 150 | `exe_path=None` 時の dict 互換セマンティクス |

主要ファイル: `katrain/core/leela/{engine, logic, parser, conversion, models, presentation}.py`

### A-4. Beginner Hints（初級者向け支援）

| 機能 | フェーズ | 概要 |
|------|---------|------|
| Beginner Hints MVP | Phase 91 | セーフティネット |
| Beginner Hints Extension | Phase 92 | 翻訳テンプレ、盤上ハイライト |

主要ファイル: `katrain/core/beginner/{detector, hints, models}.py`

### A-5. Active Review Mode（能動的復習）

| 機能 | フェーズ | 概要 |
|------|---------|------|
| Active Review MVP | Phase 93 | 重要局面の反復学習 |
| Active Review Extension | Phase 94 | Retry / Hint / セッションサマリ |

主要ファイル: `katrain/core/study/{active_review, review_session}.py`

### A-6. Quiz Mode（間違い手クイズ）【後に削除】

| 機能 | フェーズ | 概要 |
|------|---------|------|
| Generate quiz (beta) | Phase 4 | 大ミスから問題生成 |
| Quiz Mode popup (beta) | Phase 4 | ポップアップ UI |
| QuizConfig / Quiz popup i18n | Phase 4 | 設定・翻訳整備 |
| QuizManager 抽出 | Phase 98 | `gui/managers/quiz_manager.py` 化 |
| **削除** | Phase 138-D | QuizManager trio + quiz_popup/session を削除（532 LOC） |

### A-7. 設定・構成管理の刷新

| 機能 | 概要 |
|------|------|
| `ConfigStore`（JsonFileConfigStore） | `katrain/common/config_store.py` |
| `TypedConfigWriter` 新 API | `update_*_config()` パターン |
| Read-side Config Migration | 既存コードの移行 |
| `update_*_config()` 移行 | 全箇所統一 |
| myKatrain Dropdown メニュー | 5 機能（open latest report / open output folder / batch analyze folder / mykatrain settings / diagnostics） |
| Recent SGF dropdown | 最近の SGF 高速ロード |
| Focus buttons | ナビゲーション強化 |

主要ファイル: `katrain/common/typed_config/`, `katrain/common/config_store.py`

### A-8. State Notifier（イベント基盤）

| 機能 | 概要 |
|------|------|
| StateNotifier 基盤 | `katrain/core/state/` |
| Notifier 統合 + 発火ポイント | 既存コードに組み込み |
| UI Subscribe MVP + KaTrainGui Subscribe | Kivy 側の購読機構 |

### A-9. Engine 抽象化・選択

| 機能 | 概要 |
|------|------|
| Engine 選択設定 | KataGo/Leela 切替 |
| UI エンジン切替 | 設定 UI 統合 |
| 解析強度抽象化 | visits/時間指定 |
| `humanlike` トグル | KataGo Settings UI Reorg |
| Auto Setup Mode | 後に Phase 128 で削除（不安定） |
| KataGo error/LCB signals | Phase 154、difficulty への統合 |

### A-10. リスク・パース・テンポ解析

| 機能 | 概要 |
|------|------|
| Risk Context Core | `core/analysis/risk/` |
| Risk 統合 | Karte/Summary 連携 |
| Time Data Parser | SGF `BL/WL` 残り時間パース |
| Pacing & Tilt Core | `core/analysis/time/` パッケージ |
| Pacing/Tilt 統合 | レポート反映 |
| Ownership クラスタ抽出 + Cluster Classifier | 陣地パターン分類 |
| Complexity Filter | PV 複雑度絞り込み |
| Recurring Pattern Mining | 頻出パターン発見 |
| Reason Generator | 弱点仮説の根拠生成 |
| Signature Player Axis | レーダー選手軸 |
| Style Archetype Core | 棋風分類 |
| Style Karte 統合 | Karte への組み込み |

### A-11. 5 軸レーダー（Radar）→【後に削除】

| 機能 | フェーズ | 概要 |
|------|---------|------|
| 10 段階 Skill Radar | Phase 134 | `core/analysis/skill_radar.py` |
| Skill Radar Batch 出力 | Phase 135 | テキスト形式 |
| AI 対応レーダー | Phase 136 | 構造化 Markdown |
| **完全削除** | Phase 137 | 1,800+ LOC 削除、JSON サマリーへ一本化 |

### A-12. カルテ補助機能

| 機能 | 概要 |
|------|------|
| Meaning Tags System Core | 局面分類タグ（critical / important / mistake 等） |
| 3-Tag 完全復活 | Phase 148-B'2 で `context_builder` に policy 供給 |
| Critical 3 Focused Review | 重要 3 局面レビュー |
| Tofu Fix + 言語コード一貫性 | Phase 52-A（日本語豆腐修正） |

### A-13. その他 UI 機能

| 機能 | 概要 |
|------|------|
| Diagnostics 機能拡張 | Phase 127（実行時状態可視化） |
| Engine Compare popup | Phase 39-2（後に Phase 138-D 削除、675 LOC） |
| Active Review Mode MVP/Extension | Phase 93-94 |
| Beginner Hints MVP/Extension | Phase 91-92 |

### A-14. バッチ処理の刷新

| 機能 | フェーズ | 概要 |
|------|---------|------|
| `core/batch/` パッケージ化 | Phase 42-A | models/helpers 分離 |
| バッチ処理を core 層へ | Phase 42-B | Kivy 隔離 |
| `batch/stats.py` → サブパッケージ | Phase 71 | 関心ごと分割 |
| `helpers.py` → 10 モジュール | Phase 158-B | visits/loss/io/sgf/discovery/polling/filenames/leela_gate/markdown_fmt |
| `Batch Core Package` 完成 | — | `batch_core.py` 統合 |
| `Leela Batch Output Fix` | Phase 87.6 | Leela 経路の出力欠落修正 |
| Batch UI 一貫性 | — | `batch_ui.py` リファクタ |

### A-15. Python 型・テスト近代化

| 機能 | フェーズ | 概要 |
|------|---------|------|
| mypy strict 移行 | Phase 112 | 222 ファイル 0 エラー |
| Python 3.11 modern syntax (PEP 604/585) | Phase 113-114/115 | 69 ファイル遅延対応 → 全ファイル |
| Forward Reference + i18n + Semantic Type Fixes | Phase 138-A | mypy 残対応 |
| pre-existing 型エラー修正 + Top Moves 色回帰 | Phase 138-C | |
| Kivy ヘッドレステスト基盤 | Phase 146 | `KivyUnitTest` モックレイヤー |
| pytest-cov 導入 | Phase 138-D | 50%→40% ゲート、61% 達成 |
| Throttle パラメータ | — | テスト時間 -44s |
| パラメトリック AI テスト | — | 19 AI 戦略 × 67 ケース |

---

## B. 分割・リファクタリングされたモジュール

### B-1. god module 解消（フェーズ 70-142）

| 元ファイル | 行数 | 分割先 | フェーズ |
|-----------|------|--------|---------|
| `core/game.py` | 1,528 | `core/game/{base, facade, navigation, analysis_orchestrator, insert_mode}.py` | Phase 142 |
| `core/analysis/models.py` | 1,230 | `models/{enums, move_eval, quiz, skill, reliability, difficulty}.py`（6 モジュール） | Phase 144-B |
| `core/analysis/logic.py` | 1,494 | `logic_{skill, reliability, phase, difficulty, snapshot, pv}.py`（6 モジュール）+ 既存 3 | Phase 144-C |
| `core/ai.py` | 1,723 | `ai_strategies/{basic, score, policy, pick, human}.py`（5 ファミリー） | Phase 158+ |
| `core/engine.py` | 1,105 | `engine_io.py`（380 行）/ `engine_query.py`（拡張） | Phase 158+ |
| `gui/badukpan.py` | 1,712 | `badukpan_{drawing, hints, pv}.py`（3 モジュール） | Phase 158+ |
| `gui/popups.py` | 1,168 | `popups/{_base, config_popup, misc_popups, quick_config, sgf_popups}.py`（5 モジュール） | Phase 140 P2 |
| `gui/kivyutils.py` | 743 | `kivyutils/{_base, mixins, buttons, widgets}.py`（4 モジュール）→ Phase 144-A でさらに widgets/ を 6 分割 | Phase 140 P2 / 144-A |
| `gui/kivyutils/widgets.py` | 512 / 23 クラス | `widgets/{_labels, _spinners, _player, _timer, _panels, _clickables}.py`（6 ファイル） | Phase 144-A |
| `gui/features/settings_popup.py` | 1,511 | `settings_popup_tabs/__init__.py`（Leela タブ）+ `settings_popup_state.py` + `settings_popup_helpers.py` | Phase 145-D / 158-E |
| `core/reports/karte_report.py` | — | `karte/{models, helpers, builder, json_export, llm_prompt}.py` + `karte/sections/{context, summary, important_moves, diagnosis, metadata}.py`（12 モジュール） | Phase 72 |
| `core/batch/stats.py` | — | `stats/{models, aggregation, extraction, formatting, pattern_miner, …}.py` | Phase 71 |
| `core/batch/helpers.py` | 966 | 10 関心ごとモジュール（visits / loss / inputs / io_safe / sgf_io / discovery / engine_polling / filenames / leela_gate / markdown_fmt） | Phase 158-B |

### B-2. KaTrainGui god class 解消
**メソッド数 102 → 50 程度** に縮小。`gui/managers/` 下に Manager 群を抽出。

| Manager | フェーズ | 責務 |
|---------|---------|------|
| `KeyboardManager` | Phase 73 | キーボードショートカット管理（104 行） |
| `ConfigManager` | Phase 74 | 設定 I/O（280 行） |
| `PopupManager` | Phase 75 | ポップアップ表示管理（150 行） |
| `GameStateManager` | Phase 76 | ゲーム状態同期（260 行） |
| `QuizManager`（後に削除） | Phase 98 | → Phase 138-D で削除 |
| `SummaryManager` | Phase 96 | サマリー状態管理 |
| `ActiveReviewController` | Phase 97 | 復習モード制御 |
| `game_state_update_manager.py` | Phase 158+ | `_do_update_state` + `request_leela_analysis` |
| `message_loop_manager.py` | Phase 158+ | `_message_loop_thread` |
| `gui_refresh_manager.py` | Phase 158+ | `update_gui` / `update_status_for_error` / `on_engine_status` |
| `scroll_handler.py` | Phase 158+ | マウススクロール処理 |

加えて `FeatureContext` Protocol を導入し、機能モジュールが具象 `KaTrainGui` に依存しない構造へ。

### B-3. 大型関数の分割

| 関数 | 元行数 | 分割 |
|------|--------|------|
| `badukpan.draw_hover_contents` | 239 | 6 メソッド（オーケストレータ + 5 ヘルパー） | Phase 145-A |
| `batch_ui.build_batch_popup_widgets` | 375 | 1 オーケストレータ + 15 ヘルパー | Phase 145-B |
| `orchestration.run_batch` | 462 | 5 関数 + 3 context dataclass | Phase 145-C |
| `settings_popup.do_mykatrain_settings_popup` | 703 | 検索/ボタン/browse/save ヘルパー化 | Phase 145-D |
| `__main__.py` の `_do_*` メソッド群 | — | `gui/features/commands/{game, analyze, export, popup}_commands.py` へ委譲 | Phase 140-141 |

### B-4. その他構造改善

| 改善 | フェーズ | 概要 |
|------|---------|------|
| `core/base_katrain.py` から Kivy Config 分離 | Phase 143-A | `gui/kivyutils/app_config.py` へ |
| `gui → __main__` 循環依存検出 | Phase 143-B | アーキテクチャテスト追加 |
| Command Pattern 導入 | — | `_do_*` → `commands/` パッケージ |
| `error_callback` / `main_thread_scheduler` コンストラクタ注入 | Phase 158-C | `KataGoEngine` の依存性注入 |
| `analysis` 公開 API から `_` プレフィックス 20 件削除 | Phase 158-D | 公開/非公開の明確化 |
| `board_geometry` 抽出 | — | badukpan から純粋幾何関数分離 |
| `normalize_humanlike_config` 抽出 | — | `ConfigPopup.update_config` から |
| `__main__.py` ロジックを Manager/Controller 群へ分散 | — | god class 解消 |

### B-5. 重複コード解消・DRY 化

| 項目 | 内容 |
|------|------|
| `_format_time_management` | `_aggregate_stats` の `focus_player` 引数で共通化（-30 行） |
| `_SKIP_NAMES` 未使用定数削除 | Phase 158-B |
| `snapS → snap_s` リネーム | snake_case 一貫性 |

---

## C. 削除されたコード

### C-1. 機能削除（全体削除されたもの）

| 削除対象 | 行数 | フェーズ | 理由 |
|---------|------|---------|------|
| `bots/` ディレクトリ全体 | — | 初期クリーンアップ | 教育用 fork に不要（KataGo 分散学習ボット） |
| `core/contribute_engine.py` + ContributePopup | ~480 | Phase 1 | Contribute Engine 機能削除、pygame 依存も削除 |
| `core/smart_kifu/` (4 ファイル) | 1,660 | Phase 138-D | UI から未接続、到達不能コード |
| `gui/features/smart_kifu_*.py` (3 ファイル) | 2,169 | Phase 138-D | 同上 |
| `gui/features/quiz_{popup,session}.py` + `quiz_manager.py` | 532 | Phase 138-D | Quiz Manager trio 到達不能 |
| `core/reports/{insertion.py, section_registry.py}` | 281 | Phase 138-D | 本番呼び出し元なし |
| `core/yose_analyzer.py` | 84 | Phase 138-D | 呼び出し元なし |
| `core/analysis/skill_radar.py` + `style/` パッケージ | 1,800+ | Phase 137 | Skill Radar 機能完全削除 |
| `gui/features/skill_radar_popup.py` | 357 | Phase 137 | 同上 |
| `gui/widgets/{radar_chart.py, radar_geometry.py}` | 342 | Phase 137 | 同上 |
| `tools/export_radar_{csv,summary}.py` | 500+ | Phase 137 | 同上 |
| `gui/features/engine_compare_popup.py` | 675 | Phase 138-D 後日 | UI 接続断絶 |
| `core/analysis/user_aggregate.py` | 168 | Phase 137 | Skill Radar と共に削除 |
| Leela Play mode | ~400 | Phase 123 | Analysis のみ残す方針 |
| Auto Setup Mode | — | Phase 128 | 不安定機能 |
| Export LLM Package（コマンド） | — | Phase 127 | ポップアップ UI に統合 |
| `from katrain.contribute_engine import …` 参照 | — | Phase 1 | 機能削除に伴う |
| `tests/test_smart_kifu*.py` (3 ファイル) | 1,400 | Phase 138-D | 機能削除に伴う |
| `tests/test_quiz_manager.py` | — | Phase 138-D | 機能削除に伴う |
| `tests/test_section_registry.py` | — | Phase 138-D | 機能削除に伴う |
| `tests/test_{skill_radar,radar_geometry,golden_radar,batch_radar_integration}.py` | — | Phase 137 | 機能削除に伴う |

**Phase 138-D 累計削除: 6,764 LOC**（Dead Code Revival の前に削除）

### C-2. フィールド・セクション削除

| 削除項目 | 場所 | フェーズ | 理由 |
|---------|------|---------|------|
| `difficulty` フィールド | `MoveExtractor.extract` | Phase 153 | 常に "unknown" で無意味 |
| `practice_priorities` | Karte v3.1 | Phase 153 | `weaknesses` と重複 |
| `common_difficult_positions` | Karte v3.1 | Phase 153 | `critical_3` で代用可能 |
| `urgent_misses` | Karte v3.1 | Phase 153 | 発動条件過敏、`mistake_streaks` に統合 |
| `meta.definitions.difficulty_levels` | `definitions.py` | Phase 153 | difficulty 削除で不要 |
| top-level `win_loss_analysis: null` | Summary | Phase 157-D | 各 player 配下に移動済みで冗長 |
| summary `practice*` i18n ラベル | jp/en po | Phase 153 | 機能削除で不要 |

**Phase 153 累計: -642 行（純減）**

### C-3. 依存関係・ビルド削除

| 削除対象 | フェーズ | 理由 |
|---------|---------|------|
| pygame 依存 | Phase 1 | macOS 専用、Windows 教育向け fork に不要 |
| `macOS` CI ビルドジョブ（`.github/workflows/osxbuild.yaml`） | Phase 150 | macOS 非サポート方針 |
| `create-release.needs: build-macos` | Phase 150 | 上記に伴い |
| release notes の macOS 行 | Phase 150 | 上記に伴い |
| `.github/workflows/release.yaml` の macOS 経路 | Phase 150 | 上記に伴い |

注: `spec/KaTrain.spec` と `__main__.py` の macOS 分岐は手動ビルド用に温存。

### C-4. 国際化（i18n）整理

| 削除対象 | フェーズ |
|---------|---------|
| JP/EN 以外の全ロケール | Phase 2 |

### C-5. 設定・マイナー削除

| 削除対象 | フェーズ | 理由 |
|---------|---------|------|
| `MyKatrainDropDown(DropDown): pass` | P3 クリーンアップ | KV 側 alias 置換で対応 |
| 7 行のコメントアウトコード | P3 クリーンアップ | `core/reports/types.py:84-90` |
| 5 件の TODO コメント | P3 クリーンアップ | 解消 |
| `do_mykatrain_settings_popup` 未使用 import | Phase 150 | `batch_analysis_controller.py:53` |
| 未参照ラッパー `load_export_settings` / `save_export_settings` / `save_batch_options` | Phase 158-E | |
| 未使用 Kivy widget 3 件（`BackgroundLabel` / `LightLabel` / `IMETextField`） | Phase 138-D | 47 LOC、外部参照なし |
| `CLAUDE.md` → `.opencode/` へ移行 | Phase 145 頃 | Claude Code から opencode への移行 |
| `.claude/{rules,settings.local.json}` | Phase 145 頃 | 同上 |
| `Pipfile` / `Pipfile.lock` | — | uv への移行で不要 |
| `CONTRIBUTORS` / `FINAL_VERIFICATION_*.md` / `PHASE116_*.md` / `TODO` | — | 完了済みドキュメント |
| KataGo サンプル cfg (`gtp_example.cfg` 等) | — | ユーザー環境個別管理 |
| `__init__.py`（bots ルート） | — | bots 削除に伴う |

### C-6. アーキテクチャ違反の解消

| 違反 | 解消 |
|------|------|
| `core/lang.py` の Kivy 依存 | Kivy import 削除 |
| `core/game.py` の未使用 `kivy.clock` import | 削除 |
| `__main__.py` の未使用 import | 削除 |
| `batch_core.py` の `# noqa: F401` 2 件 | Phase 158-E で解消 |

---

## D. 数値サマリ

| 項目 | 値 |
|------|---|
| フォーク起点からの期間 | 2026-01 〜 2026-06-29（約 6 ヶ月） |
| 独自コミット数 | 967 件 |
| 累計テスト数 | 3,868+（Phase 158-E 時点） |
| 累計削除コード（Phase 138-D 単独） | 6,764 LOC |
| Phase 153 純減 | -642 行 |
| Phase 158-E 設定ポップアップ縮小 | 1,511 → 1,268 行（-243 行） |
| 削除された機能モジュール数 | 約 13（bots/contribute/smart_kifu/quiz/skill_radar/engine_compare/yose/insertion/section_registry/auto_setup/llm_package_export/...） |
| 分割された god module 数 | 13 個超（game/ai/engine/badukpan/popups/kivyutils/widgets/analysis/models/analysis/logic/karte/stats/helpers/settings_popup） |
| KaTrainGui メソッド数 | 102 → 約 50（-50%） |
| Manager/Controller 数 | 12 個 |
| カバレッジ | 行 61%（curator 92% / meaning_tags 92.4% / analysis 86.2%） |
| mypy strict 0 エラーファイル | 222 ファイル |
| アーキテクチャテスト | 36/36 パス |
| Kivy 隔離違反 | 1 → 0 |

---

## E. 設計方針のまとめ

この fork は「KataGo 解析 → LLM コーチング」というユースケースに絞り込み、以下の原則で進化：

1. **コア層は Kivy を持たない**（`core/` は完全に Kivy 隔離、`gui/` のみ Kivy）
2. **レポート（Karte/Summary）は LLM が読みやすい JSON スキーマで v3.3 まで進化**
3. **god module を作らない**（1,000 行超のファイルは分割、Manager/Controller パターン）
4. **pygame・macOS・分散学習など教育用途外の機能を積極的に削除**
5. **mypy strict 0 エラー** を維持（Phase 112 以降）
6. **KataGo だけでなく Leela Zero も同等にサポート**（`core/leela/` パッケージ）
7. **テストは headless Kivy mock で CI 完結**（Phase 146）