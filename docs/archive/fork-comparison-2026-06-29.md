# フォーク元比較レポート（myKatrain vs upstream KaTrain）

> **作成日**: 2026-07-21（Phase 286 ドキュメント整合性回復時点）
> **比較対象 upstream**: `sanderland/katrain` @ `13f3ea9`（フォーク直前の upstream HEAD、2026-01 頃）
> **比較対象 myKatrain**: `sentoku870/my-katrain-v1.17.0` @ `a47f003d`（HEAD = Phase 286 ドキュメント整合性回復コミット後）
> **独自コミット**: **2,443 件**（upstream 起点からの累積）
> **比較期間**: 2026-01 〜 2026-07-21（約 7 ヶ月）

このドキュメントは、現行 myKatrain が upstream KaTrain から何を追加し、何を分割・リファクタリングし、何を削除したかを一覧化したスナップショットである。前回レポート（2026-06-29、Phase 158-E 時点）と比較して、**Phase 159 以降の約 130 フェーズ分の追加・削除・分割を反映**。

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
| **`Karte/Summary スキーマ刷新 v3.3 / v3.4`** | Phase 231-237 | **JSON スキーマ正本ドキュメント** + `karte-schema.md` 公開 |
| **複数カルテ集約 + v3.5 拡張** | Phase 270 | 6 集約関数（`aggregate_reason_tags_by_color` / `aggregate_area_difficulty` / `detect_loss_spike_windows` 等）+ `SummaryPromptConfig.kartes` |

主要ファイル: `katrain/core/reports/{karte/, sections/, utils/, schema.py, definitions.py, extractors.py, summary_logic.py, types.py, summary_json_export.py, summary_report.py, important_moves_report.py, quiz_report.py}`

### A-2. Curator スコアリングシステム

LLM に渡す棋譜の「見せどころ」を自動選定。

| 機能 | フェーズ | 概要 |
|------|---------|------|
| Curator Scoring | Phase 63 | 安定性・percentile・Game ツリー解析 |
| Curator Output | Phase 64 | `HighlightMoment` / `ReplayGuide` 生成 |
| Curator UI 統合 | Phase 126 | Batch 分析にチェックボックス追加、スレッド安全性修正 |
| Curator テストカバレッジ 92% | Phase 158-E | 148 件追加 |
| **Beginner Hints 統合** | Phase 186 | `core/curator/profile.py` + `HintCategory.CURATOR_WEAK_AXIS`（23 カテゴリ） |
| **Curator profile → Karte weak-tag boost** | Phase 248-γ E1 | chain 配線、`compute_importance_for_moves` に `user_weak_tags` パラメータ追加 |

主要ファイル: `katrain/core/curator/{models.py, scoring.py, guide_extractor.py, batch.py}`

### A-3. 棋譜並べ（Kifunarabe）学習モード【新規追加】

KataGo 解析済み SGF を「次の一手予測クイズ」として再生する学習モード。

| 機能 | フェーズ | 概要 |
|------|---------|------|
| 棋譜並べ MVP | Phase 177 | 棋譜からユーザが次の一手を予想 |
| Root 解析堅牢化 + 終了経路統一 | Phase 178 | `_kick_root_analysis` リトライ + `disable_kifunarabe_if_active()` |
| **永続履歴 (KifunarabeHistoryStore)** | Phase 249-β | `~/.katrain/kifunarabe_history/` に JSON 保存 |
| **弱点自動 export (KifunarabeWeaknessExporter)** | Phase 249-γ | 重要局面リスト統合 + 弱点 export |
| **Controller God Class 分割** | Phase 188 | 4 mixin + facade（800 → 180 行） |
| 設定 UI 整備 | Phase 230-C / 249-β | 可変高 RowLayout + 永続履歴設定タブ |

主要ファイル: `katrain/core/study/{kifunarabe, kifunarabe_constants, kifunarabe_history, kifunarabe_weakness_export}.py`、`katrain/gui/managers/kifunarabe_controller.py`（4 mixin + facade）

### A-4. Beginner Hints（初級者向け支援）

| 機能 | フェーズ | 概要 |
|------|---------|------|
| Beginner Hints MVP | Phase 91 | セーフティネット |
| Beginner Hints Extension | Phase 92 | 翻訳テンプレ、盤上ハイライト |
| **Summary Extension (ミス・自由度・難易度)** | Phase 179 + 179.1 + 179.2 | 9 カテゴリ追加 |
| **Ownership / Policy 派生ヒント** | Phase 182 | 3 カテゴリ追加（OWNERSHIP_DOMINANT / POLICY_CONFLICT / POLICY_CONFIDENT） |
| **Curator 集約統合** | Phase 186 | `HintCategory.CURATOR_WEAK_AXIS`（計 23 カテゴリ） |
| **`hints.py` カバレッジ 16.5% → 97%** | Phase 187 | 137 件追加 |
| **`hints.py` → `hints/` サブパッケージ化** | Phase 196 | 6 ファイル（api / _cache / _dispatch / _extract / _gate） |
| **priority chain 統合** | Phase 248 | `compute_beginner_hint(aggregate=True)` 全ディテクタ実行 → 最高 severity |
| **internal_params.py** | Phase 248-β3 | 6 パラメータ JSON 露出 |

主要ファイル: `katrain/core/beginner/{models.py, detector.py, detector_mistake.py, detector_freedom.py, detector_difficulty.py, detector_katago.py, detector_ownership.py, detector_policy.py, detector_curator.py, hints/, internal_params.py}`

### A-5. Active Review Mode（能動的復習）

| 機能 | フェーズ | 概要 |
|------|---------|------|
| Active Review MVP | Phase 93 | 重要局面の反復学習 |
| Active Review Extension | Phase 94 | Retry / Hint / セッションサマリ |

主要ファイル: `katrain/core/study/{active_review.py, review_session.py}`

### A-6. Quiz Mode（間違い手クイズ）【後に削除】

| 機能 | フェーズ | 概要 |
|------|---------|------|
| Generate quiz (beta) | Phase 4 | 大ミスから問題生成 |
| Quiz Mode popup (beta) | Phase 4 | ポップアップ UI |
| QuizConfig / Quiz popup i18n | Phase 4 | 設定・翻訳整備 |
| QuizManager 抽出 | Phase 98 | `gui/managers/quiz_manager.py` 化 |
| **削除** | Phase 138-D | QuizManager trio + quiz_popup/session を削除（532 LOC） |
| **i18n 残滓削除** | Phase 285 | quiz strings (~25 keys) 完全削除 |

### A-7. 設定・構成管理の刷新

| 機能 | 概要 |
|------|------|
| `ConfigStore`（JsonFileConfigStore） | `katrain/common/config_store.py` |
| `TypedConfigWriter` 新 API | `update_*_config()` パターン |
| Read-side Config Migration | 既存コードの移行 |
| `update_*_config()` 移行 | 全箇所統一 |
| **myKatrain メニュー集約 (Phase 230)** | 8 項目 → **4 項目**（kifu-narabe / LLM coach / diagnostics / settings） |
| **3 機能完全削除 (Phase 230-A.2)** | 「最新レポートを開く」「出力フォルダを開く」「複数局まとめ」メニュー・dispatch・handler・テストすべて削除 |
| **設定 UI 不要項目削除 (Phase 271-A)** | 「棋譜並べ履歴フォルダ」「棋譜並べ弱点フォルダ」2 行削除 + 盤面 watermark 撤去 |
| Recent SGF dropdown | 最近の SGF 高速ロード |
| Focus buttons | ナビゲーション強化 |
| **DefaultConfig 統合 (Phase 229)** | `general/player_rank` 1 入力で解析 / LLM Coach 両方反映 |

主要ファイル: `katrain/common/typed_config/`, `katrain/common/config_store.py`, `katrain/gui/features/settings_popup*.py`, `katrain/gui/features/settings_popup_tabs/{analysis,export,kifunarabe,diagnostics}_tab.py`

### A-8. State Notifier（イベント基盤）

| 機能 | 概要 |
|------|------|
| StateNotifier 基盤 | `katrain/core/state/` |
| Notifier 統合 + 発火ポイント | 既存コードに組み込み |
| UI Subscribe MVP + KaTrainGui Subscribe | Kivy 側の購読機構 |

### A-9. Engine 抽象化【KataGo 専用化】

| 機能 | フェーズ | 概要 |
|------|---------|------|
| Engine 選択設定（KataGo/Leela） | 〜 Phase 170 | KataGo/Leela 切替 |
| **Leela エンジン完全削除** | Phase 171 | `core/leela/` 1459 行 / `LeelaConfig` / `LeelaManager` / `leela_tab` / `resign_hint_popup` / `leela_gate` / `engine_compare` / `EngineType.LEELA` / `leela_loss_est` / `MixedEngineSnapshotError` / `KARTE_ERROR_CODE_NON_KATAGO` を削除し、**KataGo 専用に整理** |
| UI エンジン切替 | 設定 UI 統合（KataGo のみ） |
| 解析強度抽象化 | visits/時間指定 |
| `humanlike` トグル | KataGo Settings UI Reorg |
| Auto Setup Mode → 後に Phase 128 で削除（不安定） | |
| KataGo error/LCB signals | Phase 154、difficulty への統合 |
| **AI 戦略 17 → 2 スリム化** | Phase 280 | `DefaultStrategy`（`ai:default`）+ `HandicapStrategy`（`ai:handicap`）のみ |

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
| Signature Player Axis | レーダー選手軸（Phase 137 で Skill Radar と共に削除） |
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
| **Important Moves UI リファクタリング** | Phase 250 | タブ「重要局面」追加 + Prev/Next 4 ボタン（黒前/黒次/白前/白次）分割 + 重要局面リスト popup 完全廃止 + 大悪手ライン削除 |
| **重要局面機能 包括改善** | Phase 248 | 9路/13路対応 (`board_size_adjusted_thresholds`) + `critical_3` 件数設定 + 内部パラメータ JSON 露出 |
| **候補手フィルター（PV Filter）包括改善** | Phase 246-247 | 20 件の課題を一括改修：AUTO モード可視化 / 盤面 UX / 堅牢性 / ロジック拡張（expert preset, board_size 連動）/ cache + preview / composite sort |
| Tofu Fix + 言語コード一貫性 | Phase 52-A（日本語豆腐修正）、**Phase 281 で KivyMD 1.2.0 対応** |

### A-13. その他 UI 機能

| 機能 | フェーズ | 概要 |
|------|---------|------|
| Diagnostics 機能拡張 | Phase 127 | 実行時状態可視化 |
| **Diagnostics タブ統合** | Phase 230-D | 設定タブ内に統合、メニューから削除 |
| Engine Compare popup → Phase 138-D 削除（675 LOC） | | |
| Active Review Mode MVP/Extension | Phase 93-94 | |
| Beginner Hints MVP/Extension | Phase 91-92 | |
| **サイドパネル文字サイズ fix** | Phase 283 | `min(sp(N), …)` キャップ解除 |
| **新規対局 popup 9 クイック選択ボタン空白 fix** | Phase 283 | `SizedButton` padding リセット + `QuickInputButton` size_hint 修正 |

### A-14. バッチ処理の刷新

| 機能 | フェーズ | 概要 |
|------|---------|------|
| `core/batch/` パッケージ化 | Phase 42-A | models/helpers 分離 |
| バッチ処理を core 層へ | Phase 42-B | Kivy 隔離 |
| `batch/stats.py` → サブパッケージ | Phase 71 | 関心ごと分割 |
| `helpers.py` → 10 モジュール | Phase 158-B | visits/loss/io/sgf/discovery/polling/filenames/leela_gate/markdown_fmt |
| **`orchestration.py` → サブパッケージ化** | Phase 197 | 7 ファイル（`_context`/`_setup`/`_process`/`_handle`/`_summary`/`_curator`） |
| `Batch Core Package` 完成 | — | `batch_core.py` 統合 |
| Leela Batch Output Fix | Phase 87.6 | Leela 経路の出力欠落修正（Phase 171 で leela_gate 削除） |
| Batch UI 一貫性 | — | `batch_ui.py` リファクタ |
| **Batch UI スモークテスト** | Phase 282 | `tests/test_batch_ui_widgets.py` 35 tests |

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
| パラメトリック AI テスト | — | 19 AI 戦略 × 67 ケース（Phase 280 で 2 戦略化） |
| **mypy 2.x 移行** | Phase 275 | `enable_error_code=["deprecated","redundant-cast","unused-awaitable"]` |
| **CI matrix に Python 3.13 追加** | Phase 274 | `actions/setup-python v5→v6`, `uv 0.7→0.11` |
| **依存更新（OSV 解消）** | Phase 273 | urllib3 2.5+ / Pillow 12+ / pytest 8.3.2+ |
| **chardet 7 移行** | Phase 276 | OSV 別系統の更新 |
| **conftest.py 死蔵コード除去** | Phase 282 | 851 → 500 行（-351 行 / -41%） |
| **5 大ファイルスモークテスト追加** | Phase 282 | curator_scoring / engine_io / summary_pattern / batch_ui / diagnostics_popup = 197 tests |

### A-16. LLM Coach システム【Phase 207-228 + Phase 269】

KataGo 出力を Ground Truth とし、LLM には判断ではなく翻訳のみを担わせる一連の機能。

| 機能 | フェーズ | 概要 |
|------|---------|------|
| **`core/coach/` パッケージ完全実装** | Phase 207-213 | master_db + lexicon + symptom_index + tones + prompt_builder + llm_validator |
| **CLI tool** | Phase 214-A | 4 サブコマンド（build / validate / symptoms / lexicon）、17 unit tests |
| **Karte-aware symptom detection** | Phase 215 | 11 個の aggregator helper、30 unit tests |
| **Streak-based symptom detection** | Phase 216 | 5 個の streak aggregator、17 unit tests |
| **Aggregate helpers + CLI analyze** | Phase 217 | Pearson r ヘルパー |
| **Calibration fixtures** | Phase 218 | 8 golden fixtures、39 unit tests |
| **Calibrate CLI command** | Phase 219 | CI 親和、exit code 0/1 |
| **Trace CLI command** | Phase 220 | 検出器パイプライン可視化 |
| **Multi-game summary support** | Phase 221 | `detect_json_type()` で karte/summary 自動判別 |
| **GUI 統合（手動貼付ワークフロー）** | Phase 225 | `LLMCoachPopupContent` + メニュー「LLM コーチ（手動貼付）」 |
| **品質改善統合改修** | Phase 226-A〜J | Lexicon 検証 / 症状 ID 抽出 3 段階 / 着手番号 / pointsLost / player_color / SymptomContext.current_phase |
| **複数局対応（B 案フル実装）** | Phase 227-A〜E | summary_prompt_builder + summary_validator + popup タブ化 + 視点セレクタ + 集約サマリボタン |
| **実シェーマ適応** | Phase 228-A〜D | extractors / prompt builder / validator / real_shape fixtures |
| **棋力プリセット / LLM コーチ 統合** | Phase 229 | `common/rank.py` + `resolve_skill_preset()` 統合 + 設定 UI 刷新 |
| **サマリー機能 品質改善** | Phase 241 | weakness pattern 「good」除外 / popup unknown パス早期 return / loss_progression フォールバック / sentinel 化 / race condition 対策 |
| **LLM Coach 品質改善 統合改修** | Phase 242 | Kansai 辞書同期 / popup UI / Lexicon 紐付け / 検証レンダラ統合 / Pure ロジック抽出 |
| **popup 巨大メソッド分割** | Phase 272-E | `_populate_rank_and_perspective` / `_populate_summary_perspective` orchestrator 化 |
| **AYAKA 完全削除 + voice 統一** | Phase 269 | `ToneVoice.AYAKA` 削除、TOMOKO 統一 |
| **popup メソッドグルーピング** | Phase 272-D | 28 メソッドを 8 グループに整理 |

主要ファイル: `katrain/core/coach/{master_db, lexicon, symptom_index, tones, prompt_builder, llm_validator, llm_report_renderer, sgf_player_info, karte_detector, karte_aggregator, summary_prompt_builder, summary_validator, json_type, popup_logic, calibration_fixtures, cli}.py`、`katrain/gui/popups/llm_coach_popup.py`

### A-17. KivyMD 1.2.0 移行【Phase 277】

| 機能 | フェーズ | 概要 |
|------|---------|------|
| **KivyMD 0.104.1 → 1.2.0 移行** | Phase 277 | Material Design 3 対応、`BaseButton` 統合、`color_active`/`color_inactive` 新 API |
| **欠落 36 個の `.kv` runtime hook** | Phase 277 | `_kivymd_kv_loader.py` で tempdir に補完 |
| **日本語フォント tofu fix** | Phase 281 | `_sync_font_to_hint_labels` ヘルパー + Roboto フォールバック撤廃 |
| **PyInstaller hiddenimports** | Phase 284 | `kivy.uix.tabbedpanel` / `kivy.uix.checkbox` 明示追加 |

### A-18. ドキュメント・CI 近代化

| 機能 | フェーズ | 概要 |
|------|---------|------|
| **CLAUDE.md → AGENTS.md 移行** | Phase 145 頃 | Claude Code から opencode への移行 |
| **スキルの on-demand 化** | Phase 145 頃 | `.opencode/skills/{correction-levels, git-workflow, debug-workflow, go-domain, architecture}/` |
| **i18n テスト** | Phase 285 | `test_dead_i18n_keys.py` (回帰 guard) + `test_i18n.py` 20 tests |
| **アーキテクチャテスト 43 件** | Phase 282 | Kivy 隔離違反 / 循環依存 / deprecated シム隔離 / Phase 141+ 拡張 |
| **ドキュメント整合性回復** | Phase 285 + 286 | project audit cleanup + comprehensive doc recovery |

---

## B. 分割・リファクタリングされたモジュール

### B-1. god module 解消（フェーズ 70-282）

| 元ファイル | 行数 | 分割先 | フェーズ |
|-----------|------|--------|---------|
| `core/game.py` | 1,528 | `core/game/{base, facade, navigation, analysis_orchestrator, insert_mode}.py` | Phase 142 |
| `core/analysis/models.py` | 1,230 | `models/{enums, move_eval, quiz, skill, reliability, difficulty}.py`（6 モジュール） | Phase 144-B |
| `core/analysis/logic.py` | 1,494 | `logic_{skill, reliability, phase, difficulty, snapshot, pv, loss, importance}.py`（9 モジュール） + 既存 | Phase 144-C / Phase 192 |
| `core/ai.py` | 1,723 | `ai_strategies/{basic, score, policy, pick, human}.py`（5 ファミリー） | Phase 158+ |
| **`core/ai_strategies/` → 1 ファイル** | — | `ai_strategies/basic.py` のみ（Phase 280 で 17 → 2 スリム化） | Phase 280 |
| **`core/analysis/logic_difficulty.py` (756行) → サブパッケージ** | — | `difficulty/{api, _io, _policy, _transition, _state, _error_pressure, _lcb_gap}.py`（6 モジュール） | Phase 192 |
| **`core/beginner/hints.py` (753行) → サブパッケージ** | — | `hints/{api, _cache, _dispatch, _extract, _gate}.py`（6 ファイル） | Phase 196 |
| **`core/batch/orchestration.py` (927行) → サブパッケージ** | — | `orchestration/{__init__, _context, _setup, _process, _handle, _summary, _curator}.py`（7 ファイル） | Phase 197 |
| `core/engine.py` | 1,105 | `engine_io.py`（380 行）/ `engine_query.py`（拡張） | Phase 158+ |
| `gui/badukpan.py` | 1,712 | `badukpan_{drawing, hints, pv}.py`（3 モジュール） | Phase 158+ |
| `gui/popups.py` | 1,168 | `popups/{_base, config_popup, misc_popups, quick_config, sgf_popups, llm_coach, kifunarabe_*}.py`（多数） | Phase 140 P2 / Phase 177 / Phase 225 / Phase 249 |
| `gui/kivyutils.py` | 743 | `kivyutils/{_base, mixins, buttons, widgets}.py`（4 モジュール）→ Phase 144-A でさらに widgets/ を 6 分割 | Phase 140 P2 / 144-A |
| `gui/kivyutils/widgets.py` | 512 / 23 クラス | `widgets/{_labels, _spinners, _player, _timer, _panels, _clickables}.py`（6 ファイル） | Phase 144-A |
| `gui/features/settings_popup.py` | 1,511 | `settings_popup_tabs/`（4 タブ）+ `settings_popup_state.py` + `settings_popup_helpers.py` + `settings_popup_io.py` + `settings_popup_reset.py` + `settings_popup_savers.py` | Phase 145-D / 158-E / 230-D |
| **`tests/conftest.py`** | 851 | 500 行（-351 行 / -41%、Phase 282-P1-A で死蔵コード除去） | Phase 282 |
| `core/reports/karte_report.py` | — | `karte/{models, helpers, builder, json_export, llm_prompt}.py` + `karte/sections/{context, summary, important_moves, diagnosis, metadata}.py`（12 モジュール） | Phase 72 |
| `core/batch/stats.py` | — | `stats/{models, aggregation, extraction, formatting, pattern_miner}.py` | Phase 71 |
| `core/batch/helpers.py` | 966 | 10 関心ごとモジュール（visits / loss / inputs / io_safe / sgf_io / discovery / engine_polling / filenames / leela_gate / markdown_fmt） | Phase 158-B |
| **`kifunarabe_controller.py` (800行)** | — | 4 mixin（guess / session / summary / toggle）+ facade（180行） | Phase 188 |

### B-2. KaTrainGui god class 解消【メソッド数 102 → 約 50、19 Manager】

**`__main__.py` 行数推移**: 1,200+ → 878 (Phase 172) → 947 (Phase 272-C で __init__ を 3 ヘルパー分割、本体 61 行)
**Manager 数推移**: 0 → 12 (Phase 158-E) → **19** (Phase 282-P1-B)
**AppContext 集約**: Phase 198 で `katrain/gui/app_context.py` に 19 Manager/Controller を集約する dataclass

| Manager | フェーズ | 責務 |
|---------|---------|------|
| `KeyboardManager` | Phase 73 | キーボードショートカット管理（104 行） |
| `ConfigManager` | Phase 74 | 設定 I/O（280 行） |
| `PopupManager` | Phase 75 | ポップアップ表示管理（150 行） |
| `GameStateManager` | Phase 76 | ゲーム状態同期（260 行） |
| `QuizManager`（削除） | Phase 98 | → Phase 138-D で削除 |
| `SummaryManager` | Phase 96 | サマリー状態管理 |
| `ActiveReviewController` | Phase 97 | 復習モード制御 |
| `game_state_update_manager.py` | Phase 158+ | `_do_update_state` + `request_leela_analysis` |
| `message_loop_manager.py` | Phase 158+ | `_message_loop_thread` |
| `gui_refresh_manager.py` | Phase 158+ | `update_gui` / `update_status_for_error` / `on_engine_status` |
| `scroll_handler.py` | Phase 158+ | マウススクロール処理 |
| `auto_setup_controller.py` | Phase 158+ | Auto Setup 制御 |
| `dialog_factory.py` | Phase 158+ | ダイアログ生成ファクトリ |
| `ui_update_manager.py` | Phase 158+ | UI 更新統合 |
| `engine_bootstrap.py` | Phase 282 | KataGo 起動処理 |
| **`kifunarabe_controller.py` (4 mixin + facade)** | Phase 188 | kifunarabe 制御 |

加えて `FeatureContext` Protocol を導入し、機能モジュールが具象 `KaTrainGui` に依存しない構造へ。

### B-3. 大型関数の分割

| 関数 | 元行数 | 分割 | フェーズ |
|------|--------|------|---------|
| `badukpan.draw_hover_contents` | 239 | 6 メソッド（オーケストレータ + 5 ヘルパー） | Phase 145-A |
| `batch_ui.build_batch_popup_widgets` | 375 | 1 オーケストレータ + 15 ヘルパー | Phase 145-B |
| `orchestration.run_batch` | 462 | 5 関数 + 3 context dataclass | Phase 145-C |
| `settings_popup.do_mykatrain_settings_popup` | 703 | 検索/ボタン/browse/save ヘルパー化 | Phase 145-D |
| `__main__.py` の `_do_*` メソッド群 | — | `gui/features/commands/{game, analyze, export, popup}_commands.py` へ委譲 | Phase 140-141 |
| **`KaTrainGui.__init__` (228行)** | 228 | 3 ヘルパー（`_init_managers_core` 104 / `_init_managers_state` 50 / `_init_managers_loops` 41）+ 本体 61 行 | Phase 272-C |
| **`LLMCoachPopupContent._populate_rank_and_perspective` (178行)** | 178 | orchestrator (48行) + 7 ヘルパー | Phase 272-E |
| **`LLMCoachPopupContent._populate_summary_perspective` (143行)** | 143 | orchestrator (47行) + 8 ヘルパー | Phase 272-E |

### B-4. その他構造改善

| 改善 | フェーズ | 概要 |
|------|---------|------|
| `core/base_katrain.py` から Kivy Config 分離 | Phase 143-A | `gui/kivyutils/app_config.py` へ |
| `gui → __main__` 循環依存検出 | Phase 143-B | アーキテクチャテスト追加 |
| Command Pattern 導入 | Phase 172 | `_do_*` → `commands/` パッケージ、`_do_*` ラッパーメソッド 34 個削除 |
| `error_callback` / `main_thread_scheduler` コンストラクタ注入 | Phase 158-C | `KataGoEngine` の依存性注入 |
| `analysis` 公開 API から `_` プレフィックス 20 件削除 | Phase 158-D | 公開/非公開の明確化 |
| `board_geometry` 抽出 | — | badukpan から純粋幾何関数分離 |
| `normalize_humanlike_config` 抽出 | — | `ConfigPopup.update_config` から |
| `__main__.py` ロジックを Manager/Controller 群へ分散 | — | god class 解消 |
| **`core/_engine_types.py` 新設** | Phase 191 | TYPE_CHECKING 専用の前方参照集約（engine subsystem 循環解消） |
| **`app_context.py` 新設** | Phase 198 | 19 Manager/Controller 集約 dataclass |
| **KivyMD 1.2.0 ベースボタン整理** | Phase 277 | `BaseFlatButton` / `BasePressedButton` 削除、`BaseButton` 単一基底 |
| **`_sync_font_to_hint_labels` ヘルパー** | Phase 281 | Label/Button/Popup ラッパーで自動呼出 |
| **PyInstaller hiddenimports 明示** | Phase 284 | `kivy.uix.tabbedpanel` / `kivy.uix.checkbox` |
| **AYAKA 完全削除** | Phase 269 | `ToneVoice.AYAKA` / `_KANSAI_DICTIONARY` / `has_kansai_markers` / `apply_kansai_normalisation` 全削除 |

### B-5. 重複コード解消・DRY 化

| 項目 | 内容 |
|------|------|
| `_format_time_management` | `_aggregate_stats` の `focus_player` 引数で共通化（-30 行） |
| `_SKIP_NAMES` 未使用定数削除 | Phase 158-B |
| `snapS → snap_s` リネーム | snake_case 一貫性 |
| **popup_logic.py 新設** | Phase 242-E | spinner/perspective/type_label/truncation/paste の判定ロジックを Kivy 非依存に移植 |
| **resolve_skill_preset() 統合** | Phase 229 | GUI 6 callsite 置換 |
| **detect_player_color_for_user のキャッシュ化** | Phase 226-B | 同一 JSON の 2 回読み込み解消 |

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
| **Leela エンジン全削除** | **1,459 + 周辺** | **Phase 171** | **`core/leela/` パッケージ + `LeelaConfig` + `LeelaManager` + `leela_tab` + `resign_hint_popup` + `leela_gate` + `engine_compare` + `EngineType.LEELA` + `leela_loss_est` + `MixedEngineSnapshotError` + `KARTE_ERROR_CODE_NON_KATAGO`** |
| **MyKatrain メニュー 3 機能完全削除** | — | Phase 230-A.2 | 「最新レポートを開く」「出力フォルダを開く」「複数局まとめ」のメニュー・dispatch・handler・テストすべて削除 |
| **重要局面リスト popup 完全廃止** | — | Phase 250-E | `gui/popups/important_moves_popup.py` / `gui/kv/important_moves_popup.py` / `core/analysis/important_moves_popup.py` 削除 |
| **AI 戦略 14 個削除** | — | Phase 280 | `ai:weak` / `ai:moderate` / `ai:strong` / `ai:advanced` / `ai:expert` / `ai:humanlike` 等 |
| **「局面を生成」タブ削除** | — | Phase 280 | `NewGameModeButton` 3 → 2 個化（`setupposition` 削除） |
| **AYAKA 完全削除** | — | Phase 269 | `ToneVoice.AYAKA` / `_KANSAI_DICTIONARY` / `_KANSAI_NORMALISATION_PAIRS` / `_AYAKA_MARKERS` / `has_kansai_markers` / `apply_kansai_normalisation` / `ToneConfig.kansai_dictionary` |
| Leela Play mode | ~400 | Phase 123 | Analysis のみ残す方針 |
| Auto Setup Mode | — | Phase 128 | 不安定機能 |
| Export LLM Package（コマンド） | — | Phase 127 | ポップアップ UI に統合 |
| `from katrain.contribute_engine import …` 参照 | — | Phase 1 | 機能削除に伴う |
| `tests/test_smart_kifu*.py` (3 ファイル) | 1,400 | Phase 138-D | 機能削除に伴う |
| `tests/test_quiz_manager.py` | — | Phase 138-D | 機能削除に伴う |
| `tests/test_section_registry.py` | — | Phase 138-D | 機能削除に伴う |
| `tests/test_{skill_radar,radar_geometry,golden_radar,batch_radar_integration}.py` | — | Phase 137 | 機能削除に伴う |
| `tests/test_important_moves_popup.py` (19件) | — | Phase 250-G | popup 廃止に伴う |
| `tests/test_important_move_navigation.py` (20件) | — | Phase 250-G | popup 廃止に伴う |
| `tests/test_phase258_critical_popup_reason.py` (5件) | — | Phase 250-G | popup 廃止に伴う |
| **`tests/test_pv_filter_perspective_watermark.py`** | — | **Phase 271-A.4** | watermark 関数削除に伴う |
| **`tests/ai_strategies/` サブパッケージ** | — | Phase 280 | AI 戦略 17 → 2 スリム化に伴う |
| **Phase 285: 50 msgid 削除** | — | Phase 285 | `contribute:*` (~15) + quiz strings (~25) + mykatrain menu items (4) + Phase 250 / 229 残滓 |

**累計削除**:
- Phase 138-D 単独: 6,764 LOC
- Phase 280 単独: 約 3,940 行（純減、AI 戦略スリム化）
- Phase 171: 1,459 行（Leela）+ i18n 132 msgid + テスト 25 ファイル
- Phase 269: AYAKA 関連（複数ファイル・複数関数）

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
| **`mistake_points` プロパティ** | `graph.py` | Phase 250-D | 大悪手ライン削除 |
| **`disable_katago` チェックボックス** | settings popup | Phase 230-B | Leela 削除済みで不要 |
| **`default_user_rank`** | 出力設定 | Phase 230-E | 解析タブの `player_rank` に統合 |
| **`board:perspective` i18n キー** | jp/en po | Phase 271-A.3 | watermark 削除 |
| **`mykatrain:settings:kifunarabe_history_dir` / `kifunarabe_auto_export_dir`** | jp/en po | Phase 271-A.3 | 設定 UI 削除 |
| **Phase 229-C skill_preset radio group keys (8 keys)** | jp/en po | Phase 285 | UI 刷新 |
| **`prev-important-move` / `next-important-move` / `important-line`** | jp/en po | Phase 285 | Phase 250 リファクタリング（-black/-white バリアント使用） |
| **`contribute:*` / quiz strings / `mykatrain:export-package` 等** | jp/en po | Phase 285 | 機能削除済み |

**Phase 153 累計**: -642 行（純減）

### C-3. 依存関係・ビルド削除

| 削除対象 | フェーズ | 理由 |
|---------|---------|------|
| pygame 依存 | Phase 1 | macOS 専用、Windows 教育向け fork に不要 |
| `macOS` CI ビルドジョブ（`.github/workflows/osxbuild.yaml`） | Phase 150 | macOS 非サポート方針 |
| `create-release.needs: build-macos` | Phase 150 | 上記に伴い |
| release notes の macOS 行 | Phase 150 | 上記に伴い |
| `.github/workflows/release.yaml` の macOS 経路 | Phase 150 | 上記に伴い |
| **docutils 依存** | Phase 285 | ソースから参照なし（Kivy が transitive に持ってくる） |
| **`game/setup_move` + `game/setup_advantage`** | Phase 285 | Phase 280 setupposition 削除の残滓 |

注: `spec/KaTrain.spec` と `__main__.py` の macOS 分岐は手動ビルド用に温存。

### C-4. 国際化（i18n）整理

| 削除対象 | フェーズ |
|---------|---------|
| JP/EN 以外の全ロケール | Phase 2 |
| 50 confirmed-dead msgids | Phase 285 |

**現在のエントリ数**: jp/en .po それぞれ **844 entries**（Phase 285 削除後、Phase 286 ドキュメント整合性回復時点、`polib.pofile()` で実測）

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
| **Phase 271-A: 「棋譜並べ履歴フォルダ」「棋譜並べ弱点フォルダ」設定 UI 2 行** | Phase 271-A | ユーザー報告「ユーザに触らせる必要がない」 |
| **`draw_perspective_watermark` 関数 + 呼び出し** | Phase 271-A | 盤面左下の「B (次手損失)」watermark 撤去 |
| **`tests/test_pv_filter_perspective_watermark.py`** | Phase 271-A.4 | watermark 関数のリグレッションテスト不要 |

### C-6. アーキテクチャ違反の解消

| 違反 | 解消 |
|------|------|
| `core/lang.py` の Kivy 依存 | Kivy import 削除 |
| `core/game.py` の未使用 `kivy.clock` import | 削除 |
| `__main__.py` の未使用 import | 削除 |
| `batch_core.py` の `# noqa: F401` 2 件 | Phase 158-E で解消 |

---

## D. 数値サマリ

| 項目 | 2026-06-29 (前回レポート) | 2026-07-21 (Phase 286) |
|------|:---:|:---:|
| フォーク起点からの期間 | 2026-01 〜 2026-06-29（約 6 ヶ月） | 2026-01 〜 2026-07-21（約 7 ヶ月） |
| 独自コミット数 | 967 件 | **2,443 件**（+1,476 件 / +153%） |
| 累計テスト数 | 3,868+（Phase 158-E 時点） | **6,196+**（Phase 286 時点 / +60%） |
| 累積コード削減（純減） | 約 1,500 行 | **約 8,500 行**（Phase 280 単独で約 3,940 行） |
| Phase 138-D 単独削除 | 6,764 LOC | 6,764 LOC |
| Phase 153 純減 | -642 行 | -642 行 |
| Phase 280 AI 戦略スリム化 | — | 約 3,940 行（純減） |
| Phase 171 Leela 完全削除 | — | 1,459 行 + i18n 132 msgid + テスト 25 ファイル |
| 削除された機能モジュール数 | 約 13 | **約 18**（+ bots/contribute/smart_kifu/quiz/skill_radar/engine_compare/yose/insertion/section_registry/auto_setup/llm_package_export + Leela + 3 menu items + 重要局面 popup + AI 戦略 14 個 + AYAKA） |
| 分割された god module 数 | 13 個超 | **20 個超**（+ difficulty / hints / orchestration / ai_strategies / settings_popup_tabs / kifunarabe_controller / conftest） |
| KaTrainGui メソッド数 | 102 → 約 50（-50%） | 102 → 約 50 → **__init__ 本体 61 行**（Phase 272-C） |
| KaTrainGui 行数（`__main__.py`） | 878 行 | **947 行**（Phase 272-C で __init__ を 3 ヘルパー分割） |
| Manager/Controller 数 | 12 個 | **19 個**（+ engine_bootstrap / kifunarabe mixin x4） |
| カバレッジ | 行 61%（curator 92% / meaning_tags 92.4% / analysis 86.2%） | **行 80%+**（curator 98% / hints 97% / engine 83% / auto_setup 97%） |
| mypy strict 0 エラーファイル | 222 ファイル | **310 ファイル**（mypy 2.x 移行済み） |
| アーキテクチャテスト | 36/36 パス | **43/43 パス** |
| Kivy 隔離違反 | 1 → 0 | **0** |
| **i18n エントリ数（jp/en）** | — | **844 entries**（Phase 285 で 50 件削除後） |
| **完了 Phase** | Phase 1 〜 158-E | **Phase 1 〜 286**（+ 約 130 フェーズ） |

---

## E. 設計方針のまとめ

この fork は「KataGo 解析 → LLM コーチング」というユースケースに絞り込み、以下の原則で進化：

1. **コア層は Kivy を持たない**（`core/` は完全に Kivy 隔離、`gui/` のみ Kivy、`tests/conftest.py` で Kivy headless 環境変数管理）
2. **レポートは v3.5 まで進化**（Karte v3.3 / Summary v3.4 / Karte Aggregator v3.5 の JSON スキーマ、`karte-schema.md` 正本ドキュメント）
3. **god module を作らない**（1,000 行超のファイルは分割、Manager/Controller パターン、19 個の Manager）
4. **KataGo 専用化**（Phase 171 で Leela エンジン完全削除、1,459 行 + 関連テスト 25 ファイル + i18n 132 msgid）
5. **mypy 2.x 0 issues**（310 ファイル、`enable_error_code` 導入、`warn_unused_ignores` 有効化）
6. **AI 戦略を最小構成に**（Phase 280 で 17 → 2 スリム化、`DefaultStrategy` + `HandicapStrategy` のみ）
7. **テストは headless Kivy mock で CI 完結**（Phase 146 / 241-H、`KivyUnitTest` モックレイヤー、6,196+ tests）
8. **LLM Coach 翻訳特化**（Phase 207-228、KataGo 出力を Ground Truth とし LLM には判断ではなく翻訳のみを担わせる、3 層防御でハルシネーション抑制、TOMOKO 統一 voice）
9. **KivyMD 1.2.0 ベース**（Phase 277、Material Design 3 対応、`BaseButton` 単一基底、`color_active`/`color_inactive` 新 API）
10. **重要局面 UI はタブ + 4 ボタン**（Phase 250、`TabbedPanel` 拡張、Prev/Next 黒前/黒次/白前/白次の 0.25 分割、重要局面リスト popup 廃止）
11. **棋譜並べ学習モード**（Phase 177-249、KataGo 解析済み SGF を「次の一手予測クイズ」として再生、永続履歴 + 弱点自動 export）
12. **Python 型近代化**（PEP 604/585 union generics、forward references、i18n semantic types）
13. **OSV 解消最優先の依存更新**（Phase 273-276、urllib3 2.5+ / chardet 7 / mypy 2.x / Python 3.13 CI 追加）

---

## F. 過去の比較レポート

- **2026-06-29 版**（本ファイルの前身）: Phase 158-E 時点、967 commits、`core/leela/` パッケージ健在、5軸レーダー削除済み
- **本レポート（2026-07-21）**: Phase 286 時点、2,443 commits、Leela 完全削除、AI 戦略スリム化、LLM Coach 完全実装、KivyMD 1.2.0、PyInstaller hiddenimports 明示

---

## G. 関連ドキュメント

- `docs/01-roadmap.md` — 全 Phase 286 までの詳細
- `docs/02-code-structure.md` — `katrain/` ディレクトリ構造
- `docs/00-purpose-and-scope.md` — プロジェクト目的・スコープ
- `docs/archive/specs-implemented/` — 各 Phase のスペック文書
- `AGENTS.md` §1.3 / §10 — 直近マイルストーン / 変更履歴