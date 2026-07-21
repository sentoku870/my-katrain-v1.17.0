# myKatrain コード構造

> **最終更新**: 2026-07-21（Phase 284: pyinstaller-legacy-widgets までの実構造を反映）
> Phase 171 で Leela エンジン完全削除。Phase 187-192 で Architecture Review Follow-up 完了。
> Phase 225 で MyKatrain メニューに LLM コーチ（手動貼付）を追加。
> Phase 269 で AYAKA 完全削除 + voice 統一 (TOMOKO)。
> Phase 272 で `KaTrainGui.__init__` を 3 ヘルパー分割。Phase 277 で KivyMD 0.104.1 → 1.2.0 移行。
> Phase 280 で AI 戦略 17→2 スリム化 + 「局面を生成」タブ削除。
> Phase 282 でアーキテクチャレビュー P1+P2 着手。Phase 283 でサイドパネル文字サイズ + 新規対局 popup ボタン空白 fix。
> Phase 284 で PyInstaller frozen binary の `tabbedpanel` / `checkbox` 欠落 fix。
> 完了 Phase の詳細は [`docs/archive/specs-implemented/phase*.md`](./archive/specs-implemented/) を参照。

---

## 1. ディレクトリ構造（2026-07-21 時点 = Phase 284）

```
katrain/
├── __init__.py
├── __main__.py              # アプリ起動、KaTrainGui クラス（Phase 272-C で __init__ を 3 ヘルパー分割、本体 947 行）
├── config.json
├── py.typed
│
├── common/                  # 共有定数（循環依存解消用、Kivy非依存）
│   ├── platform.py          # get_platform()（Kivy非依存OS判定）
│   ├── config_store.py      # JsonFileConfigStore（Mapping実装）
│   ├── locale_utils.py      # normalize_lang_code(), to_iso_lang_code()
│   ├── model_labels.py      # classify_model_strength(), get_model_basename()
│   ├── humanlike_config.py  # normalize_humanlike_config()
│   ├── settings_export.py   # settings エクスポート/インポート
│   ├── sanitize.py          # ファイル名サニタイズ
│   ├── resource_utils.py    # find_package_resource()（Phase 163 で core から移動）
│   ├── theme_constants.py   # INFO_PV_COLOR など
│   ├── file_opener.py       # OS 統合ファイル opener
│   ├── short_hash.py        # 8 文字短縮ハッシュ
│   ├── rank.py              # Rank dataclass + parse logic（Phase 229-A 共有棋力型）
│   ├── typed_config/        # 型付き設定読み書き（reader/writer/models）
│   └── lexicon/             # 囲碁用語辞書パッケージ
│
├── core/                    # コアロジック（Kivy非依存）
│   ├── _engine_types.py     # TYPE_CHECKING 専用の前方参照集約（Phase 191）
│   ├── game_node.py         # GameNode（手/解析結果）
│   ├── engine.py            # KataGoEngine（解析プロセス、Phase 158 で分割）
│   ├── engine_io.py         # stdin/stdout reader threads
│   ├── engine_query.py      # query 送信/終了/pondering
│   ├── engine_cmd/          # AnalysisCommand パターン（commands.py, executor.py）
│   ├── sgf_parser.py        # SGF読み込み
│   ├── game/                # Game クラス（Phase 141 で 4 分割）
│   │   ├── base.py                # BaseGame, IllegalMoveException, KaTrainSGF
│   │   ├── facade.py              # Game（合成クラス）
│   │   ├── analysis_orchestrator.py # AnalysisOrchestrator
│   │   ├── navigation.py          # GameNavigator
│   │   └── insert_mode.py         # InsertModeController
│   │
│   ├── ai_strategies_base.py     # AI戦略基底クラス・register_strategy
│   ├── ai_strategies/            # AI戦略実装（Phase 280 で 17→2 スリム化、basic.py のみ）
│   │   └── basic.py                  # DefaultStrategy / HandicapStrategy
│   ├── ai/                       # AI 戦略の内部定数群
│   │   ├── __init__.py
│   │   └── constants.py
│   │
│   ├── analysis/             # 解析基盤パッケージ
│   │   ├── models/                # Enum, Dataclass, 定数
│   │   ├── meaning_tags/          # 意味タグ分類（classifier/context_builder/integration/models/registry）
│   │   ├── time/                  # 時刻・パシング解析（models/parser/pacing）
│   │   ├── difficulty/            # Phase 192 新設サブパッケージ（6 モジュール）
│   │   │   ├── api.py                  # 公開 4 関数
│   │   │   ├── _io.py                  # 候補手正規化、root_visits 抽出、信頼性判定
│   │   │   ├── _policy.py              # policy エントロピー fallback + top-1/top-2 gap
│   │   │   ├── _transition.py          # 評価急落度
│   │   │   ├── _state.py               # 盤面複雑度（v1 placeholder）
│   │   │   ├── _error_pressure.py      # KataGo shorttermScoreError
│   │   │   └── _lcb_gap.py             # LCB 差分
│   │   ├── internal_params.py     # 内部パラメータ JSON 露出（Phase 248-β3）
│   │   ├── logic.py               # 解析ロジック統合エントリポイント
│   │   ├── logic_loss.py
│   │   ├── logic_pv.py
│   │   ├── logic_importance.py
│   │   ├── logic_phase.py
│   │   ├── logic_phase_dynamic.py
│   │   ├── logic_reliability.py
│   │   ├── logic_skill.py
│   │   ├── logic_snapshot.py
│   │   ├── logic_difficulty.py    # 後方互換シム（Phase 192）
│   │   ├── presentation.py        # 表示/フォーマット関数
│   │   ├── critical_moves.py      # Critical 3 選択
│   │   ├── ownership_cluster.py   # ownership クラスタ抽出
│   │   ├── cluster_classifier.py
│   │   ├── cluster_detectors.py
│   │   ├── cluster_geometry.py
│   │   ├── board_context.py
│   │   ├── reason_generator.py
│   │   └── modes.py               # モード別ロジック切替
│   │
│   ├── batch/                # バッチ処理パッケージ（Phase 158-B で 10 モジュール分割、Phase 197 で orchestration サブパッケージ化）
│   │   ├── orchestration/     # Phase 158-B / 197 で 6 サブモジュール分割
│   │   │   ├── _context.py
│   │   │   ├── _curator.py
│   │   │   ├── _handle.py
│   │   │   ├── _process.py
│   │   │   ├── _setup.py
│   │   │   └── _summary.py
│   │   ├── stats/              # Phase 197 stats/ パッケージ
│   │   │   ├── aggregation.py
│   │   │   ├── extraction.py
│   │   │   ├── formatting.py
│   │   │   ├── models.py
│   │   │   └── pattern_miner.py
│   │   ├── analysis.py
│   │   ├── discovery.py        # collect_sgf_files
│   │   ├── engine_polling.py
│   │   ├── filenames.py
│   │   ├── inputs.py
│   │   ├── io_safe.py
│   │   ├── loss.py
│   │   ├── markdown_fmt.py
│   │   ├── models.py
│   │   ├── sgf_io.py
│   │   └── visits.py
│   │
│   ├── beginner/             # 初級者向けヒント（Phase 179-187 で大幅拡張、Phase 196 で hints/ サブパッケージ化）
│   │   ├── hints/             # Phase 196 hints.py サブパッケージ化
│   │   │   ├── api.py
│   │   │   ├── _cache.py
│   │   │   ├── _dispatch.py
│   │   │   ├── _extract.py
│   │   │   └── _gate.py
│   │   ├── models.py          # HintCategory enum（23 カテゴリ、Phase 186 で CURATOR_WEAK_AXIS 追加）
│   │   ├── detector.py        # Phase 248 で priority chain 統合
│   │   ├── detector_mistake.py
│   │   ├── detector_freedom.py
│   │   ├── detector_difficulty.py
│   │   ├── detector_katago.py
│   │   ├── detector_ownership.py    # Phase 182
│   │   ├── detector_policy.py       # Phase 182
│   │   └── detector_curator.py      # Phase 186 追加
│   │
│   ├── coach/                # LLM Coach 翻訳特化基盤（Phase 207-213 で完全実装）
│   │   ├── master_db.py       # CoachMode 5 種 + ToneVoice 2 種（Phase 269 で AYAKA 削除 → TOMOKO 統一）
│   │   ├── lexicon.py         # Lexicon 注入
│   │   ├── symptom_index.py   # 30 症状の ground truth
│   │   ├── tones.py           # モード×声のトーン制御
│   │   ├── prompt_builder.py  # 3 層防御付きプロンプト生成
│   │   ├── llm_validator.py   # 5 種類の検証
│   │   ├── llm_report_renderer.py  # Phase 242-D 検証レンダラ統合
│   │   ├── sgf_player_info.py # SGF BR/WR 抽出（Phase 225.6）
│   │   ├── karte_detector.py  # Karte 駆動 + streak 症状検出（Phase 215-216）
│   │   ├── karte_aggregator.py # 複数カルテ集約（Phase 270）
│   │   ├── summary_prompt_builder.py # 集約サマリプロンプト（Phase 227-A）
│   │   ├── summary_validator.py # 集約サマリ検証（Phase 227-B）
│   │   ├── json_type.py       # karte/summary 自動判別（Phase 221）
│   │   ├── popup_logic.py     # popup Pure ロジック抽出（Phase 242-E）
│   │   ├── calibration_fixtures.py # 8 golden fixtures（Phase 218）
│   │   └── cli.py             # 4 サブコマンド CLI（Phase 214-A）
│   │
│   ├── curator/              # 棋譜適合度スコアリング（Phase 116+ で拡張、Phase 186 で Beginner Hints 統合）
│   │   ├── batch.py           # バッチ集約
│   │   ├── guide_extractor.py # 学習ガイド抽出
│   │   ├── models.py          # CuratorProfile / load_curator_profile()
│   │   └── scoring.py         # スコアリング計算
│   │
│   ├── study/                # 学習モード（Phase 177 で kifunarabe 追加、Phase 249 で永続履歴）
│   │   ├── active_review.py   # 能動的レビュー
│   │   ├── review_session.py
│   │   ├── kifunarabe.py              # KifunarabeSession モデル
│   │   ├── kifunarabe_constants.py
│   │   ├── kifunarabe_history.py      # Phase 249-β 永続履歴
│   │   └── kifunarabe_weakness_export.py # Phase 249-γ 弱点自動 export
│   │
│   ├── auto_setup.py         # 自動セットアップロジック（Phase 189 で 9.8% → 97% カバレッジ）
│   ├── analysis_result.py
│   ├── board_analysis.py
│   ├── board_geometry.py
│   ├── compatibility.py      # Python 3.11+ StrEnum re-export
│   ├── constants.py
│   ├── diagnostics.py
│   ├── lang.py
│   ├── log_buffer.py
│   ├── notify_helpers.py
│   ├── error_recovery.py
│   ├── errors.py
│   ├── tsumego_frame.py
│   ├── utils.py
│   ├── state/                # StateNotifier（Phase 104）
│   │   ├── events.py
│   │   └── notifier.py
│   └── reports/              # レポート生成
│       ├── constants.py
│       ├── definitions.py
│       ├── extractors.py
│       ├── important_moves_report.py
│       ├── schema.py
│       ├── summary_json_export.py
│       ├── summary_logic.py
│       ├── summary_report.py
│       ├── types.py
│       ├── karte/                # Karte report パッケージ
│       │   ├── builder.py
│       │   ├── json_export.py
│       │   ├── helpers.py
│       │   ├── models.py
│       │   ├── llm_prompt.py
│       │   └── sections/
│       │       ├── context.py
│       │       ├── diagnosis.py
│       │       ├── important_moves.py
│       │       └── metadata.py
│       ├── sections/             # Summary セクション
│       │   ├── opponent_analysis.py
│       │   ├── time_section.py
│       │   └── win_loss.py
│       └── utils/
│           ├── game_classifier.py
│           ├── loss_progression.py
│           ├── rank_classifier.py
│           └── result_parser.py
│
├── gui/                      # GUI（Kivy）
│   ├── __init__.py
│   ├── _kivymd_kv_loader.py  # KivyMD 1.2.0 欠落 .kv 補完（Phase 277）
│   ├── app_context.py        # 19 Manager/Controller 集約 dataclass（Phase 198）
│   ├── badukpan.py           # 盤面表示（Phase 158+ で 4 分割）
│   ├── badukpan_drawing.py
│   ├── badukpan_hints.py
│   ├── badukpan_pv.py
│   ├── controlspanel.py      # 右パネル
│   ├── error_handler.py
│   ├── lang_bridge.py        # KivyLangBridge
│   ├── sgf_manager.py
│   ├── sound.py
│   ├── theme.py
│   ├── theme_loader.py
│   ├── commands/             # コマンドディスパッチ（Phase 172 全面刷新、35 エントリ DISPATCH_TABLE）
│   │   └── (各機能別 *.py)
│   ├── controllers/          # Phase 282-P1-B 切り出し
│   │   ├── analysis_controller.py
│   │   └── batch_analysis_controller.py
│   ├── features/             # 機能モジュール（settings_popup 等）
│   │   ├── settings_popup.py
│   │   ├── settings_popup_state.py
│   │   ├── settings_popup_helpers.py
│   │   ├── settings_popup_io.py
│   │   ├── settings_popup_reset.py
│   │   ├── settings_popup_savers.py
│   │   ├── settings_popup_tabs/  # KataGo 専用タブ（Phase 171 で leela_tab 削除、Phase 230-D で diagnostics_tab 追加）
│   │   ├── commands/
│   │   ├── karte_export.py
│   │   ├── llm_coach.py            # Phase 225 LLM コーチ（Kivy 非依存ロジックラッパー）
│   │   ├── batch_core.py
│   │   ├── batch_ui.py
│   │   ├── summary_*.py            # aggregator/formatter/io/pattern/stats/ui
│   │   ├── active_review_summary.py
│   │   ├── active_review_ui.py
│   │   ├── kifunarabe_summary.py
│   │   ├── diagnostics_popup.py    # Phase 230-D 診断情報
│   │   ├── recovery_actions.py
│   │   ├── report_navigator.py
│   │   ├── context.py
│   │   └── types.py
│   ├── kivyutils/            # Kivy ユーティリティ
│   │   ├── app_config.py
│   │   ├── buttons.py        # SizedButton / SizedRoundedRectangleButton / BaseButton 単一基底（Phase 277）
│   │   ├── mixins.py
│   │   ├── _base.py
│   │   ├── _clickables.py
│   │   ├── _labels.py
│   │   ├── _spinners.py
│   │   ├── _player.py
│   │   ├── _timer.py
│   │   └── _panels.py
│   ├── managers/             # Manager パターン（Phase 188 / 272 で大規模分割）
│   │   ├── active_review_controller.py
│   │   ├── auto_setup_controller.py
│   │   ├── config_manager.py
│   │   ├── dialog_factory.py
│   │   ├── engine_bootstrap.py
│   │   ├── game_state_manager.py
│   │   ├── game_state_update_manager.py
│   │   ├── gui_refresh_manager.py
│   │   ├── keyboard_manager.py
│   │   ├── kifunarabe_controller.py     # Phase 188 で 4 mixin + facade 分割
│   │   ├── kifunarabe_guess_mixin.py
│   │   ├── kifunarabe_session_mixin.py
│   │   ├── kifunarabe_summary_mixin.py
│   │   ├── kifunarabe_toggle_mixin.py
│   │   ├── message_loop_manager.py
│   │   ├── popup_manager.py
│   │   ├── scroll_handler.py
│   │   ├── summary_manager.py
│   │   └── ui_update_manager.py
│   ├── popups/               # ポップアップダイアログ
│   │   ├── _base.py
│   │   ├── config_popup.py
│   │   ├── kifunarabe_critical3_popup.py
│   │   ├── kifunarabe_history_popup.py   # Phase 249-β 履歴 popup
│   │   ├── kifunarabe_setup_popup.py
│   │   ├── llm_coach_popup.py            # Phase 225 / 227 / 228 / 272-E
│   │   ├── misc_popups.py
│   │   ├── quick_config.py
│   │   └── sgf_popups.py
│   ├── widgets/              # カスタム Kivy ウィジェット
│   │   ├── factory.py                    # Phase 281 `_sync_font_to_hint_labels` ヘルパー
│   │   ├── filebrowser.py                # Phase 282-P1-C minimum tests
│   │   ├── graph.py                      # Phase 250-D mistake_points 削除
│   │   ├── helpers.py
│   │   ├── movetree.py
│   │   ├── progress_loader.py
│   │   └── selection_slider.py
│   └── kv/                   # Kivy レイアウトファイル
│
├── i18n/                     # 国際化（JP+EN、844 entries ずつ）
│   └── locales/{en,jp}/LC_MESSAGES/katrain.{po,mo}
│
├── fonts/                    # 日本語フォント（Phase 281 で tofu fix 後の状態）
├── img/                      # 画像アセット（flags/ 国旗含む）
├── models/                   # KataGo モデル
├── sounds/                   # 効果音
├── tools/                    # 開発用 CLI ツール
└── KataGo/                   # KataGo バイナリ + 設定
    └── KataGoData/
```

> 注: 上記のツリーは要約です。完全なリストは `find katrain -name "*.py" | sort` を参照。
> 大きな構造変更は [`docs/01-roadmap.md`](./01-roadmap.md) のフェーズ記録を確認してください。

---

## 2. 主要クラスの関係（Phase 284 時点）

```
KaTrainGui (Screen, KaTrainBase) — Phase 172 で 995 → 878 行、Phase 272-C で __init__ を 3 ヘルパー分割（本体 947 行）
├── self.ctx         → AppContext（Phase 198、19 Manager/Controller 集約 dataclass）
├── self.game        → Game（対局状態、Phase 141 で 4 分割）
├── self.engines     → dict[str, KataGoEngine]（KataGo 専用、Phase 171 で Leela 削除）
├── self.controls    → ControlsPanel（右パネル）
├── self.board_gui   → BadukPanWidget（盤面、Phase 158+ で 4 分割）
├── self.managers    → 19 個の Manager（Phase 272-C で 3 ヘルパーから構築）
│   ├── active_review / auto_setup / config / dialog / engine_bootstrap
│   ├── game_state / game_state_update / gui_refresh / keyboard / message_loop
│   ├── popup / scroll_handler / summary / ui_update
│   └── kifunarabe（Phase 188 で 4 mixin + facade 分割、800 → 180 行）
└── self.controllers → analysis_controller / batch_analysis_controller（Phase 282-P1-B）

# コマンドディスパッチ（Phase 172 で全面刷新）
KaTrainGui → commands/DISPATCH_TABLE (35エントリ) → 各コマンドハンドラ
            （旧 `_do_*` ラッパーメソッド 34個は削除済み）
```

### 依存方向
```
KaTrainGui → AppContext → Manager 群
          → Game → GameNode
          → KataGoEngine (engine_io + engine_query + engine_cmd)
                          + core/_engine_types (TYPE_CHECKING 集約、Phase 191)
          → ControlsPanel → ScoreGraph
                         → various widgets
          → Popups (LLM Coach / kifunarabe / config)
```

---

## 3. データフロー

### 3.1 解析データの流れ
```
1. GameNode.analyze()
     ↓ KataGoEngine に解析リクエスト
2. KataGoEngine.send_query() → write_queue
     ↓
3. write_stdin_thread → KataGo (subprocess)
     ↓ JSON結果
4. analysis_read_thread → set_analysis(result)
     ↓ analysis dict に格納
5. StateNotifier (Phase 104) → Manager 通知
     ↓
6. UI Update (gui_refresh_manager / ui_update_manager)
     ↓
7. ControlsPanel.update_evaluation() → UI更新
```

### 3.2 UIイベントの流れ（Phase 172 反映）
```
1. ユーザー操作（ボタン/盤面タップ）
     ↓
2. Kivy → root.katrain("action", args)
     ↓
3. KaTrainGui.__call__() → commands/DISPATCH_TABLE[action]
     ↓                                  ↑ Phase 172 で旧 `_do_*` ラッパーは削除
4. 各コマンドハンドラ (commands/*.py) が必要に応じて Manager / GameNode を操作
```

### 3.3 LLM Coach データフロー（Phase 225-228）
```
1. ユーザーが Karte / Summary を生成
     ↓
2. Popup の「LLM Coach」ボタン → LLMCoachPopupContent
     ↓
3. detect_json_type() で karte / summary 自動判別
     ↓
4. build_llm_prompt() → 3 層防御付きプロンプト生成
   - Lexicon 注入
   - 症状 ID ground truth
   - System Instruction (HTML コメント式)
     ↓
5. ユーザーが手動で LLM に貼付 → 応答を受け取り
     ↓
6. validate_llm_response() で 5 種類の検証
   - 症状 ID 不在 / 着手番号範囲外 / pointsLost 外れ値 / トーン不一致 / カテゴリ整合
```

---

## 4. myKatrain で追加した主な機能

詳細は [`docs/01-roadmap.md`](./01-roadmap.md) のフェーズ記録を参照してください。

### 4.1 解析基盤（analysis パッケージ）
- 損失/重要度計算、難易度メトリクス、信頼度
- 意味タグ分類（`meaning_tags/` パッケージ）
- Critical 3 選択、Pattern Mining
- Time/Pacing 分析
- **Phase 192**: `difficulty/` サブパッケージ化（756 行 → 6 モジュール + 後方互換シム）
- **Phase 248-β3**: `internal_params.py` 新設（6 パラメータ JSON 露出）

### 4.2 Beginner Hints（初心者向けヒント）
- Phase 91-92 で MVP 構築
- Phase 179 + 179.1 + 179.2 で Summary Extension（ミス・自由度・難易度、9 カテゴリ）
- Phase 182 で Ownership / Policy 派生ヒント（3 カテゴリ追加）
- Phase 186 で Curator 集約統合（HintCategory 計 23 カテゴリ）
- Phase 187 で `hints.py` カバレッジ 16.5% → 97%（137 件追加）
- Phase 196 で `hints.py` → `hints/` サブパッケージ化
- Phase 248 で `compute_beginner_hint(aggregate=True)` priority chain 改修

### 4.3 Karte レポート
- ビルドフロー: `build_karte_json_string()` → `katrain/core/reports/karte/__init__.py` （Phase 231 で `build_karte_report` → `build_karte_json_string` リネーム）
- セクション分割: `katrain/core/reports/karte/sections/`（context / diagnosis / important_moves / metadata）
- 意味タグ分類: `katrain/core/analysis/meaning_tags/`
- **Phase 231-237**: Karte 刷新（v3.3）+ Summary（v3.4）の JSON スキーマ正本
- **Phase 270**: Karte aggregator で v3.5 拡張（area / position_difficulty / meaning_tag_label）

### 4.4 バッチ解析
- `katrain/core/batch/orchestration.py::run_batch()` がメインエントリ
- 統計抽出: `katrain/core/batch/stats/` パッケージ
- Markdown 出力: `katrain/core/batch/markdown_fmt.py`
- Phase 197 で orchestration サブパッケージ化

### 4.5 Manager パターン
- 19 個の Manager クラスで UI 状態を管理（Phase 188 で Kifunarabe Controller を mixin 分割）
- Phase 198 で AppContext に集約
- PEP 562 `__getattr__` で遅延 import

### 4.6 Kifunarabe（棋譜並べ）
- `core/study/kifunarabe.py` に KifunarabeSession モデル
- `gui/managers/kifunarabe_controller.py` に Controller（4 mixin + facade）
- Phase 178 で `_kick_root_analysis` リトライ + 終了経路統一
- Phase 249-β で `KifunarabeHistoryStore` 永続履歴
- Phase 249-γ で弱点自動 export

### 4.7 Curator（棋譜適合度スコアリング）
- `core/curator/{batch,guide_extractor,models,scoring}.py`
- Beginner Hints の最下層 priority chain に統合
- **Phase 248-γ E1**: Curator profile → Karte weak-tag boost 配線

### 4.8 LLM Coach（Phase 207-228）
- `core/coach/` パッケージ完全実装（master_db / lexicon / symptom_index / tones / prompt_builder / validator）
- Phase 225 で GUI 統合（手動貼付ワークフロー）
- Phase 227 で複数局サマリ対応（B 案フル実装）
- Phase 228 で実シェーマ適応（extractors / prompt builder / validator）
- Phase 242-E で popup Pure ロジック抽出
- Phase 269 で AYAKA 完全削除 + voice 統一（TOMOKO）
- Phase 272-E で巨大メソッド分割（`_populate_rank_and_perspective` / `_populate_summary_perspective`）

### 4.9 KivyMD 1.2.0 移行（Phase 277）
- `_kivymd_kv_loader.py` で欠落 36 個の `.kv` ファイルを runtime 補完
- `kivy.uix.tabbedpanel` / `kivy.uix.checkbox` 等の PyInstaller hiddenimports 明示（Phase 284）

### 4.10 UI 整理（Phase 230 / 271-A / 283）
- Phase 230: MyKatrain メニュー 8→4 項目集約 + 診断タブ統合
- Phase 271-A: 設定 UI 不要項目削除 + 盤面 watermark 撤去
- Phase 283: サイドパネル文字サイズ縮小 fix + 新規対局 popup 9 クイックボタン空白 fix

---

## 5. 削除済み/旧ファイル（参考）

### 5.1 Phase 171 で削除（Leela エンジン完全削除）
- `katrain/core/leela/` ディレクトリ（1459 行）
- `katrain/gui/leela_manager.py`
- `katrain/gui/features/settings_popup_tabs/leela_tab.py`
- `katrain/gui/features/resign_hint_popup.py`
- `katrain/core/batch/leela_gate.py`
- `katrain/core/analysis/engine_compare.py`
- `EngineType.LEELA`、`LeelaConfig` / `LeelaEngine`、`leela_loss_est` フィールド、`is_single_engine_snapshot` / `MixedEngineSnapshotError` / `KARTE_ERROR_CODE_NON_KATAGO`、`LEELA_*` 定数

### 5.2 過去の削除
- `katrain/core/yose_analyzer.py`（Phase 100 付近で削除）
- `katrain/core/analysis/skill_radar.py`（意味タグに統合）
- `katrain/gui/features/radar_geometry.py`, `radar_chart.py`, `skill_radar_popup.py`（同上）
- `katrain/gui/features/auto_mode_popup.py`（auto_setup_controller.py に統合）
- `katrain/gui/features/quiz_popup.py`, `quiz_session.py`（quiz_manager に統合）
- `katrain/core/reports/karte/sections/summary.py`（Phase 161 で削除）

### 5.3 Phase 172 で削除
- `KaTrainGui._do_*` ラッパーメソッド 34 個（DISPATCH_TABLE への明示的ディスパッチに置換）

### 5.4 Phase 230 で削除
- `gui/managers/quiz_manager.py`（active_review_controller に統合）
- `gui/features/quiz_session.py`
- MyKatrain メニュー「最新レポートを開く」「出力フォルダを開く」「複数局まとめ」（3 機能完全削除）
- 設定 UI の「棋譜並べ履歴フォルダ」「棋譜並べ弱点フォルダ」行（Phase 271-A）

### 5.5 Phase 250-E で削除
- `gui/popups/important_moves_popup.py` / `gui/kv/important_moves_popup.py` / `core/analysis/important_moves_popup.py`（重要局面リスト popup 完全廃止）

### 5.6 Phase 269 で削除
- `ToneVoice.AYAKA` enum 値
- `_KANSAI_DICTIONARY` / `_KANSAI_NORMALISATION_PAIRS` / `_AYAKA_MARKERS`
- `has_kansai_markers` / `is_kansai_marker` / `apply_kansai_normalisation`
- `ToneConfig.kansai_dictionary` フィールド

### 5.7 Phase 280 で削除
- AI 戦略 15 個（`ai:weak` / `ai:moderate` / `ai:strong` / `ai:advanced` / `ai:expert` / `ai:humanlike` 等）
- `setupposition` タブ / `quick_config.py` の setupposition ロジック / `game_commands.py` の `do_selfplay_setup`

---

## 6. 変更時の注意点

### 6.1 UIを触る場合
- `.kv` ファイルと `.py` の両方を確認
- Kivy の id/property バインディングに注意
- Phase 172 以降は `commands/DISPATCH_TABLE` への登録が必須（`__main__.py` 内のラッパー作成は不要）
- **Phase 277 以降**: KivyMD 1.2.0 で削除された API（`selected_color` / `unselected_color` / `helper_text_mode: "none"` 等）に注意
- **Phase 281 以降**: 日本語フォント豆腐回避のため `factory._sync_font_to_hint_labels` パターンを維持

### 6.2 解析ロジックを触る場合
- `katrain/core/analysis/` パッケージが主な変更対象
  - データモデル → `models/`
  - 計算ロジック → `logic.py` / `logic_*.py` / `difficulty/` (Phase 192)
  - 表示処理 → `presentation.py`
- `core/analysis/difficulty/` を触る場合は `api.py` の公開関数経由を推奨（後方互換シム維持）
- `internal_params.py` のパラメータは config 経由でユーザー調整可能

### 6.3 翻訳を追加する場合
- 文字列を `i18n._("...")` で包む
- `uv run python i18n.py -todo` で不足をチェック
- 各言語の `.po` ファイルに追加
- `.mo` ファイルを再生成
- **現在**: jp/en .po はそれぞれ **844 entries**（Phase 286 ドキュメント整合性回復時点、`polib.pofile()` で実測）

### 6.4 Beginner Hints を追加する場合
- `core/beginner/detector_*.py` に pure detector を追加（Kivy 非依存）
- `HintCategory` enum に追加（合計 23 カテゴリ）
- `compute_summary_hint` の priority chain に統合
- 既存テスト（`tests/test_beginner_hints_*.py`）の追加カテゴリの i18n 整合性チェックを更新

### 6.5 LLM Coach を触る場合
- `core/coach/` 配下の pure ロジック + `gui/popups/llm_coach_popup.py` の薄いラッパー
- `popup_logic.py` に Kivy 非依存ロジックを抽出済み（Phase 242-E）
- `json_type.py` の `detect_json_type()` で karte / summary 自動判別
- `validate_prompt_config()` で voice / mode / difficulty の整合性チェック

### 6.6 PyInstaller ビルド関連（Phase 284）
- `spec/KaTrain.spec` の `hiddenimports` に `kivy.uix.tabbedpanel` / `kivy.uix.checkbox` を明示
- `spec/hook-kivymd.py` で KivyMD 36 widget の `.kv` スタブ生成
- 新しい lazy import モジュールは hiddenimports 追加が必要（Clock-scheduled import 経路）

---

## 7. テスト実行

```bash
# テスト実行（逐次）
uv run pytest tests

# テスト実行（並列）
uv run pytest tests -n auto

# テスト実行（時間上位表示）
uv run pytest tests --durations=20 --durations-min=0.1

# アーキテクチャテスト
uv run pytest tests/test_architecture.py -v

# 起動確認
python -m katrain

# i18nチェック
$env:PYTHONUTF8 = "1"
uv run python i18n.py -todo
```

---

## 8. 変更履歴

> 直近 3 ヶ月の主要 Phase のみ記載。詳細は `AGENTS.md` セクション 10 を参照。

- 2026-07-21: **Phase 284 — pyinstaller-legacy-widgets** — `spec/KaTrain.spec` に `kivy.uix.tabbedpanel` / `kivy.uix.checkbox` を hiddenimports 追加、Phase 282 / 283 のドキュメント整合性回復
- 2026-07-21: **Phase 283 — side-panel-fonts-quick-buttons** — サイドパネル文字サイズ縮小 fix + 新規対局 popup の 9 クイックボタン空白 fix（`panels.kv` の `min(sp(N), …)` キャップ解除 + `widgets.kv` `<SizedButton>` padding リセット + `popup_widgets.kv` `<QuickInputButton>` size_hint 修正）
- 2026-07-21: **Phase 282 — architecture-followup** — P1+P2 着手（conftest.py 851→500 行 / 5 大ファイルスモークテスト 197 件 / filebrowser minimum tests 32 件 / summary_json_export 58 件 / defensive try/except 19 件）
- 2026-07-21: **Phase 281 — jp-font-tofu-fix** — 日本語フォント豆腐修正 包括対策（`_kivymd_kv_loader.py` Roboto フォールバック撤廃 + `factory._sync_font_to_hint_labels` ヘルパー）
- 2026-07-21: **Phase 280 — ai-setup-slimdown** — AI 戦略 17→2 スリム化（`DefaultStrategy` / `HandicapStrategy` のみ）+ 「局面を生成」タブ削除（37 ファイル変更、+6,345/-10,214 行）
- 2026-07-20: **Phase 277 — kivymd-1.2.0-migration** — KivyMD 0.104.1 → 1.2.0 移行（Material Design 3 対応 + 欠落 `.kv` ファイル runtime hook）
- 2026-07-20: **Phase 276 — chardet7** — chardet 5 → 7 移行（OSV 別系統の更新）
- 2026-07-20: **Phase 275 — mypy2** — mypy 2.x 完全移行
- 2026-07-20: **Phase 274 — ci** — GitHub Actions major 更新 + CI matrix に Python 3.13 追加
- 2026-07-20: **Phase 273 — deps** — 依存更新（OSV 解消最優先）
- 2026-07-18: **Phase 272-E — LLM Coach popup 巨大メソッド分割** — `_populate_rank_and_perspective` / `_populate_summary_perspective` を orchestrator + 9 ヘルパーに分割
- 2026-07-18: **Phase 272 — プロジェクト全体 リファクタリング** — `KaTrainGui.__init__` を 3 ヘルパー分割（228 → 61 行）+ LLM Coach popup メソッドグルーピング
- 2026-07-18: **Phase 271-A — 設定 UI 不要項目削除 + 盤面 watermark 撤去**
- 2026-07-18: **Phase 270 — 複数カルテ集約 + サマリプロンプト v3.5 拡張** — 6 集約関数で Schema 3.4 → 3.5 条件付きバンプ
- 2026-07-18: **Phase 269 — AYAKA 完全削除 + voice 統一** — `ToneVoice.AYAKA` enum 削除、TOMOKO 統一、tone 整合性チェック削除
- 2026-07-18: **Phase 250 — 重要局面 UI リファクタリング** — タブ「重要局面」追加 + Prev/Next 4 ボタン分割 + 重要局面リスト popup 完全廃止 + 大悪手ライン削除
- 2026-07-18: **Phase 249-hotfix — 起動時 AttributeError + 残存 γ リグレッション復旧**
- 2026-07-17: **Phase 230 — MyKatrain UI/UX 整理** — メニュー 8→4 項目集約、Leela 残滓削除、診断タブ統合、棋力入力統合
- 2026-07-17: **Phase 225-228 — LLM Coach 統合 (単局 + 複数局)** — Phase 225: GUI 統合、Phase 227: 複数局対応、Phase 228: 実シェーマ適応
- 2026-07-17: **Phase 207-220 — LLM Coach 基盤 完全実装** — master_db / lexicon / symptom_index / tones / prompt_builder / validator / karte_detector / calibration / CLI
- 2026-07-17: **Phase 196-198 — サブパッケージ化 + AppContext** — `beginner/hints/` / `batch/orchestration/` サブパッケージ化、`KaTrainGui AppContext` 集約基盤
- 2026-07-17: **Phase 193 — Documentation cleanup** — Leela 言及全削除、AGENTS.md / docs 整合
- 2026-07-16: **Phase 192 — `core/analysis/difficulty/` サブパッケージ新設**（6 モジュール + 後方互換シム）
- 2026-07-15: **Phase 191 — `core/_engine_types.py` 新設**（engine subsystem TYPE_CHECKING 循環解消）
- 2026-07-15: **Phase 190 — `core/engine.py` カバレッジ 48.3% → 83%**
- 2026-07-15: **Phase 189 — `core/auto_setup.py` カバレッジ 9.8% → 97%**
- 2026-07-14: **Phase 188 — `gui/managers/kifunarabe_controller.py` God Class 分割**（4 mixin + facade、800 → 180 行）
- 2026-07-14: **Phase 187 — `core/beginner/hints.py` カバレッジ 16.5% → 97%**
- 2026-07-14: **Phase 186 — `core/curator/profile.py` 新設**（CuratorProfile、Beginner Hints 統合）
- 2026-07-14: **Phase 182 — `core/beginner/detector_ownership.py` / `detector_policy.py` 新設**
- 2026-07-14: **Phase 179 + 179.1 + 179.2 — Beginner Hints Summary Extension**（9 カテゴリ追加）
- 2026-07-13: **Phase 178 — kifunarabe Root 解析堅牢化 + 終了経路統一**
- 2026-07-11: **Phase 173 — kivy import を関数内に移動**（CI exit-102 部分修正）
- 2026-07-11: **Phase 172 — `commands/DISPATCH_TABLE` への明示的ディスパッチ移行**、`KaTrainGui._do_*` メソッド 34 個削除
- 2026-07-04: **Phase 171 — Leela エンジン完全削除**（`core/leela/` 1459 行削除、KataGo 専用化）
- 2026-07-01: **Phase 166 — 設定ポップアップ partial 整理**
- 2026-06-25: **Phase 143-A/B — Kivy 違反解消 + 循環依存検出**
- 2026-06-25: **Phase 144-A/B/C — kivyutils / analysis/models / analysis/logic 分割**
- 2026-06-26: **Phase 145-A/B/C/D — badukpan / batch_ui / orchestration / settings_popup 部分抽出**
- 2026-05: **Phase 138-142 — リファクタリング**（解析基盤刷新、God module 抽出、Manager 分割）

> 注: 2026-06-26 までは `CLAUDE.md` を使用していた。opencode 移行により `AGENTS.md` に変更。