# myKatrain コード構造

> 最終更新: 2026-07-01（Phase 166）
>
> **⚠️ このドキュメントは古い記述を含んでいます。** 2026-01-30 (Phase 89) 以降の大規模リファクタリングが反映されていません。
> 現在の構造は `docs/02-code-structure-addendum-2026-07.md` を参照するか、
> `find katrain -name "*.py" | head -50` で実際のファイルを確認してください。

---

## 1. ディレクトリ構造（2026-01-30 時点の概要）

```
katrain/
├── __main__.py           # アプリ起動、KaTrainGui クラス（2026-07 時点: 1,128 行）
│
├── common/               # 共有定数（循環依存解消用、Kivy非依存）
│   ├── __init__.py       # DEFAULT_FONT など
│   ├── theme_constants.py # INFO_PV_COLOR など
│   ├── platform.py       # get_platform()（Kivy非依存OS判定）
│   ├── config_store.py   # JsonFileConfigStore（Mapping実装）
│   ├── locale_utils.py   # normalize_lang_code(), to_iso_lang_code()
│   ├── model_labels.py   # classify_model_strength(), get_model_basename()
│   ├── humanlike_config.py # normalize_humanlike_config()
│   ├── settings_export.py  # settings エクスポート/インポート
│   ├── sanitize.py       # ファイル名サニタイズ
│   ├── resource_utils.py # find_package_resource()（Phase 163 で core から移動）
│   ├── typed_config/     # 型付き設定読み書き（reader/writer/models）
│   └── lexicon/          # 囲碁用語辞書パッケージ
│
├── core/                 # コアロジック
│   ├── game_node.py      # GameNode（手/解析結果）
│   ├── engine.py         # KataGoEngine（解析プロセス、Phase 158 で分割）
│   ├── engine_io.py      # stdin/stdout reader threads
│   ├── engine_query.py   # query 送信/終了/pondering
│   ├── engine_cmd/       # AnalysisCommand パターン
│   ├── sgf_parser.py     # SGF読み込み
│   ├── game/             # Game クラス（Phase 141 で 4 分割）
│   │   ├── base.py            # BaseGame, IllegalMoveException, KaTrainSGF
│   │   ├── facade.py          # Game（合成クラス）
│   │   ├── analysis_orchestrator.py # AnalysisOrchestrator
│   │   ├── navigation.py      # GameNavigator
│   │   └── insert_mode.py     # InsertModeController
│   │
│   ├── ai_strategies_base.py  # AI戦略基底クラス・register_strategy
│   ├── ai_strategies/    # AI戦略実装（Phase 158 で分割: basic, pick, policy, score, human）
│   │
│   ├── analysis/         # 解析基盤パッケージ
│   │   ├── models/             # Enum, Dataclass, 定数（models/ パッケージに分割）
│   │   ├── logic.py, logic_*.py # 損失/重要度/クイズ/difficulty/reliability/skill/
│   │   │                       #   phase/phase_dynamic/pv/snapshot/quiz
│   │   ├── presentation.py     # 表示/フォーマット関数
│   │   ├── critical_moves.py   # Critical 3 選択
│   │   ├── ownership_cluster.py # ownership クラスタ抽出
│   │   ├── cluster_classifier.py
│   │   ├── engine_compare.py   # KataGo vs Leela 比較
│   │   ├── reason_generator.py
│   │   ├── meaning_tags/       # 意味タグ分類
│   │   └── time/               # 時刻・パシング解析
│   │
│   ├── batch/            # バッチ処理パッケージ（Phase 158-B で 10 モジュール分割）
│   │   ├── analysis.py
│   │   ├── discovery.py        # collect_sgf_files
│   │   ├── engine_polling.py
│   │   ├── filenames.py
│   │   ├── helpers.py          # 後方互換シム（Phase 168 で削除予定）
│   │   ├── inputs.py
│   │   ├── io_safe.py
│   │   ├── leela_gate.py
│   │   ├── loss.py
│   │   ├── markdown_fmt.py
│   │   ├── models.py
│   │   ├── orchestration.py    # run_batch()
│   │   ├── sgf_io.py
│   │   ├── visits.py
│   │   └── stats/              # stats/ パッケージに分割
│   │
│   ├── auto_setup.py     # 自動セットアップロジック
│   ├── auto_setup_controller.py  # AutoSetupController
│   ├── analysis_result.py # エラー分類・テスト解析結果
│   ├── board_analysis.py
│   ├── board_geometry.py
│   ├── beginner/         # 初級者向けヒント
│   ├── compatibility.py  # Python 3.11+ StrEnum re-export
│   ├── constants.py
│   ├── curator/          # 棋譜適合度スコアリング
│   ├── diagnostics.py
│   ├── lang.py
│   ├── leela/            # Leela Zero 対応
│   ├── state/            # StateNotifier（Phase 104）
│   ├── study/            # Active review, review session
│   ├── tsumego_frame.py
│   ├── utils.py
│   └── reports/          # レポート生成（karte/ が中心）
│       ├── karte/             # Karte report パッケージ
│       │   ├── builder.py
│       │   ├── json_export.py
│       │   ├── helpers.py
│       │   ├── models.py
│       │   ├── sections/      # セクション別ビルダー
│       │   └── ...
│       ├── summary_*.py
│       ├── quiz_report.py
│       ├── sections/
│       ├── utils/
│       └── ...
│
├── gui/                  # GUI（Kivy）
│   ├── controlspanel.py  # 右パネル
│   ├── badukpan.py       # 盤面表示（Phase 158+ で分割）
│   ├── sgf_manager.py
│   ├── lang_bridge.py    # KivyLangBridge
│   ├── theme.py
│   ├── theme_loader.py
│   ├── sound.py
│   ├── leela_manager.py
│   ├── error_handler.py
│   ├── commands/         # コマンドパターン
│   ├── kivyutils/        # Kivy ユーティリティ（app_config, mixins, buttons, _base）
│   ├── managers/         # Manager パターン（Phase 158-D+）
│   │   ├── active_review_controller.py
│   │   ├── auto_setup_controller.py
│   │   ├── config_manager.py
│   │   ├── dialog_factory.py
│   │   ├── game_state_manager.py
│   │   ├── game_state_update_manager.py
│   │   ├── gui_refresh_manager.py
│   │   ├── keyboard_manager.py
│   │   ├── message_loop_manager.py
│   │   ├── popup_manager.py
│   │   ├── scroll_handler.py
│   │   ├── summary_manager.py
│   │   └── ui_update_manager.py
│   ├── popups/           # ポップアップダイアログ（パッケージ化）
│   ├── widgets/          # カスタム Kivy ウィジェット
│   │   ├── graph.py
│   │   ├── movetree.py
│   │   ├── selection_slider.py
│   │   ├── progress_loader.py
│   │   ├── filebrowser.py
│   │   └── factory.py, helpers.py
│   ├── controllers/      # コントローラ（batch_analysis_controller 等）
│   └── features/         # 機能モジュール
│       ├── settings_popup.py  # 設定ポップアップ（オーケストレータ）
│       ├── settings_popup_state.py
│       ├── settings_popup_helpers.py
│       ├── settings_popup_tabs/  # Phase 162 で proper package 化
│       │   └── leela_tab.py
│       ├── karte_export.py
│       ├── summary_*.py
│       ├── batch_*.py
│       ├── active_review_*.py
│       ├── commands/
│       ├── diagnostics_popup.py
│       ├── recovery_actions.py
│       ├── report_navigator.py
│       ├── resign_hint_popup.py
│       └── context.py, types.py
│
├── i18n/                 # 国際化（JP+EN）
│   ├── __init__.py
│   └── locales/{en,jp}/LC_MESSAGES/katrain.{po,mo}
```

> 注: 上記のツリーは要約です。完全なリストは `find katrain -name "*.py" | sort` を参照。
> 大きな構造変更は `docs/01-roadmap.md` のフェーズ記録を確認してください。

---

## 2. 主要クラスの関係

```
KaTrainGui (Screen, KaTrainBase)
├── self.game      → Game（対局状態、Phase 141 で 4 分割）
├── self.engines   → dict[str, KataGoEngine]（解析エンジン）
├── self.controls  → ControlsPanel（右パネル）
├── self.board_gui → BadukPanWidget（盤面、Phase 158+ で 4 分割）
├── self.managers  → 13 個の Manager（active_review, config, game_state, keyboard, ...）
└── self.popup_manager / self.summary_manager / ...
```

### 依存方向
```
KaTrainGui → Game → GameNode
          → KataGoEngine (engine_io + engine_query + engine_cmd)
          → ControlsPanel → ScoreGraph
                         → various widgets
          → Managers → 各機能（state, popup, dialog, ...）
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

### 3.2 UIイベントの流れ
```
1. ユーザー操作（ボタン/盤面タップ）
     ↓
2. Kivy → root.katrain("action", args)
     ↓
3. KaTrainGui._do_<action>()（commands/ に委譲）
     ↓
4. 各 Manager が必要な処理を実行
```

---

## 4. myKatrain で追加した主な機能

詳細は `docs/01-roadmap.md` のフェーズ記録を参照してください。

### 4.1 解析基盤（analysis パッケージ）
- 損失/重要度計算、難易度メトリクス、信頼度
- 5 軸レーダーモデル（初期版は削除、現行は意味タグ分類で代替）
- Critical 3 選択、Pattern Mining
- Time/Pacing 分析

### 4.2 AI 戦略（ai_strategies）
- basic, pick, policy, score, human の 5 系統
- `register_strategy` デコレータで登録
- Strategy レジストリ: `STRATEGY_REGISTRY`

### 4.3 Karte レポート
- ビルドフロー: `build_karte_report()` → `katrain/core/reports/karte/__init__.py`
- セクション分割: `katrain/core/reports/karte/sections/`
- 意味タグ分類: `katrain/core/analysis/meaning_tags/`
- スタイル分類: `STYLE_CONFIDENCE_THRESHOLD`

### 4.4 バッチ解析
- `katrain/core/batch/orchestration.py::run_batch()` がメインエントリ
- Leela ガード: `katrain/core/batch/leela_gate.py`
- 統計抽出: `katrain/core/batch/stats/` パッケージ
- Markdown 出力: `katrain/core/batch/markdown_fmt.py`

### 4.5 Manager パターン
- 13 個の Manager クラスで UI 状態を管理
- PEP 562 `__getattr__` で遅延 import

---

## 5. 削除済み/旧ファイル（参考）

以下は過去に存在したが現在削除されている:
- `katrain/core/yose_analyzer.py`（Phase 100 付近で削除）
- `katrain/core/analysis/skill_radar.py`（意味タグに統合）
- `katrain/gui/features/radar_geometry.py`, `radar_chart.py`（同上）
- `katrain/gui/features/skill_radar_popup.py`（同上）
- `katrain/gui/features/auto_mode_popup.py`（auto_setup_controller.py に統合）
- `katrain/gui/features/quiz_popup.py`, `quiz_session.py`（quiz_manager に統合）
- `katrain/core/test_analysis.py`（`analysis_result.py` にリネーム）
- `katrain/core/reports/karte/sections/summary.py`（Phase 161 で削除）

---

## 6. アーカイブ

完了済みフェーズの詳細は `docs/archive/` を参照。

> ⚠️ このファイルは Phase 166 で部分的に更新されました。
> 残りの旧記述は `docs/02-code-structure-addendum-2026-07.md` に
> 移されるか、次のドキュメント更新サイクルで書き換えられる予定です。

- `YoseAnalyzer`: ヨセ解析のラッパー
- `YoseImportantMovesReport`: レポート出力

**使い方:**
```python
analyzer = YoseAnalyzer.from_game(game)
report = analyzer.build_important_moves_report()
```

### 4.4 gui/features パッケージ（Phase 3完了）

`katrain/__main__.py` から抽出された機能モジュール群。
FeatureContext Protocol による依存性注入パターンを使用。

#### context.py（基盤）
```python
class FeatureContext(Protocol):
    game: Optional["Game"]
    controls: "ControlsPanel"
    def config(self, setting: str, default: Any = None) -> Any: ...
    def set_config_section(self, section: str, value: Dict[str, Any]) -> None: ...
    def save_config(self, key: Optional[str] = None) -> None: ...
    def log(self, message: str, level: int = 0) -> None: ...
```

**設定アクセスパターン（推奨）:**
```python
# 読み取り
value = self.config("section/key", default)
section_dict = self.config("section") or {}

# 書き込み（Protocol準拠）
section_dict = dict(self.config("section") or {})  # コピーして変更
section_dict["key"] = new_value
self.set_config_section("section", section_dict)
self.save_config("section")
```

#### 機能モジュール一覧
| ファイル | 機能 | 行数 |
|---------|------|------|
| `karte_export.py` | カルテエクスポート | ~200 |
| `summary_stats.py` | サマリ統計計算 | ~250 |
| `summary_aggregator.py` | サマリ集計 | ~180 |
| `summary_formatter.py` | サマリMarkdown生成 | ~380 |
| `summary_ui.py` | サマリUI/ダイアログ | ~400 |
| `summary_io.py` | サマリファイル保存 | ~210 |
| `quiz_popup.py` | クイズポップアップ | ~150 |
| `quiz_session.py` | クイズセッション | ~220 |
| `batch_core.py` | バッチ解析コア | ~270 |
| `batch_ui.py` | バッチ解析UI | ~580 |
| `settings_popup.py` | 設定ポップアップ（オーケストレータ） | ~400 |
| `settings_popup_state.py` | `_SettingsPopupContext`（タブ間共有状態） | ~80 |
| `settings_popup_helpers.py` | Kivy ヘルパー（`_add_searchable_label`） | ~60 |
| `settings_popup_tabs/__init__.py` | タブビルダー（Leela） | ~220 |

### 4.5 Gameクラスへの追加（game.py）

**追加メソッド:**
- `build_eval_snapshot()`: EvalSnapshot生成
- `get_important_move_evals(level)`: 重要手リスト取得
- `get_quiz_items(config)`: クイズ候補取得
- `build_important_moves_report()`: テキストレポート生成

---

## 5. 変更時の注意点

### 5.1 UIを触る場合
- `.kv` ファイルと `.py` の両方を確認
- Kivy の id/property バインディングに注意

### 5.2 解析ロジックを触る場合
- `katrain/core/analysis/` パッケージが主な変更対象
  - データモデル → `models.py`
  - 計算ロジック → `logic.py`
  - 表示処理 → `presentation.py`
- `game.py` のヘルパーメソッドから呼び出す
- インポートは `from katrain.core.eval_metrics import ...` でも
  `from katrain.core.analysis import ...` でも可

### 5.3 翻訳を追加する場合
- 文字列を `i18n._("...")` で包む
- `uv run python i18n.py -todo` で不足をチェック
- 各言語の `.po` ファイルに追加
- `.mo` ファイルを再生成

---

## 6. テスト実行

```powershell
# テスト実行
uv run pytest tests

# 起動確認
python -m katrain

# i18nチェック
$env:PYTHONUTF8 = "1"
uv run python i18n.py -todo
```

---

## 7. 変更履歴

> 詳細な変更履歴は `AGENTS.md` セクション10を参照。
>
> 注: 2026-06-26 までは `CLAUDE.md` を使用していた。opencode 移行により `AGENTS.md` に変更。

- 2026-01-30: Phase 88 完了（KataGo Settings UI Reorg + human-like Toggle）
  - **common/model_labels.py**: モデル強度分類（classify_model_strength()）
  - **common/humanlike_config.py**: 正規化ロジック（normalize_humanlike_config()）
  - **gui/popups.py**: humanlike toggle UI、モデルラベル表示
- 2026-01-24: Phase 52 完了（Stabilization & Documentation）
  - ドキュメント更新（本ファイル、CLAUDE.md、roadmap）
  - Radar ゴールデンテスト追加（17件）
  - ベンチマークスクリプト追加（scripts/benchmark_batch.py）
- 2026-01-23: Phase 52-A 完了（Tofu Fix + Language Code Consistency）
  - **common/locale_utils.py**: 言語コード正規化関数追加
  - 豆腐表示修正（フォント指定追加）
- 2026-01-23: Phase 51 完了（Radar UI Widget）
  - **gui/widgets/radar_geometry.py**: レーダー幾何計算（Kivy非依存）
  - **gui/widgets/radar_chart.py**: RadarChartWidget
  - **gui/features/skill_radar_popup.py**: スキルレーダーポップアップ
- 2026-01-23: Phase 50 完了（Critical 3 Focused Review Mode）
  - **core/analysis/critical_moves.py**: CriticalMove dataclass、select_critical_moves()
- 2026-01-23: Phase 49 完了（Radar Aggregation & Summary Integration）
  - **core/analysis/skill_radar.py**: AggregatedRadarResult、aggregate_radar()
  - **core/batch/stats.py**: Skill Profileセクション追加
- 2026-01-23: Phase 48 完了（5-Axis Radar Data Model）
  - **core/analysis/skill_radar.py**: RadarAxis、SkillTier、RadarMetrics
- 2026-01-23: Phase 47 完了（Meaning Tags Integration）
  - **core/analysis/meaning_tags/integration.py**: normalize_lang()、format_meaning_tag_with_definition()
  - MoveEval拡張: meaning_tag_idフィールド追加
- 2026-01-23: Phase 46 完了（Meaning Tags System Core）
  - **core/analysis/meaning_tags/**: 意味タグ分類パッケージ（12タグ定義）
- 2026-01-23: Phase 45 完了（Lexicon Core Infrastructure）
  - **common/lexicon/**: 囲碁用語辞書パッケージ（Kivy非依存）
- 2026-01-21: Phase 44 完了（Batch Analysis Fixes）
  - 信頼性閾値の一貫性修正、完了チャイム追加
- 2026-01-20: Phase 43 完了（Stability Audit）
  - Config save atomic化、Leela shutdown対応、theme_loader.py新設
- 2026-01-20: Phase 42 完了（Batch Core Package）
  - **core/batch/**: バッチ処理パッケージ（Kivy非依存）
- 2026-01-20: Phase 41 完了（コード品質リファクタリング）
  - AnalysisMode enum追加、コマンドハンドラ抽出
- 2026-01-19: Phase 40 完了（Leela Zero対戦機能）
  - LeelaStrategy、AI_LEELA定数追加
- 2026-01-19: Phase 39 完了（エンジン比較ビュー）
  - **core/analysis/engine_compare.py**: 手動Spearman相関、EngineComparisonResult
- 2026-01-18: Phase 38 完了（安定化）
  - safe_int()、save_manifest()エラーハンドリング
- 2026-01-18: Phase 37 完了（テスト強化）
  - MixedEngineSnapshotError導入、Leelaゴールデンテスト
- 2026-01-18: Phase 36 完了（Leelaバッチ解析）
  - analyze_single_file_leela()、バッチUIエンジン選択
- 2026-01-18: Phase 35 完了（Leelaカルテ統合）
  - has_loss_data()、format_loss_with_engine_suffix()
- 2026-01-18: Phase 33 完了（エンジン選択設定）
  - VALID_ANALYSIS_ENGINES、get_analysis_engine()
- 2026-01-18: Phase 32 完了（レポートLeela対応）
  - EngineType enum、detect_engine_type()
- 2026-01-18: Phase 31 完了（Leela→MoveEval変換）
  - **core/leela/conversion.py**: leela_position_to_move_eval()
- 2026-01-18: Phase 30 完了（解析強度抽象化）
  - AnalysisStrength enum、resolve_visits()
- 2026-01-17: Phase 29 完了（Diagnostics + Bug Report Bundle）
  - **common/sanitize.py**, **core/log_buffer.py**, **core/diagnostics.py**
- 2026-01-17: Phase 28 完了（Smart Kifu運用強化）
  - ImportErrorCode enum、TrainingSetSummary
- 2026-01-17: Phase 27 完了（Settings UIスケーラブル化）
  - **common/settings_export.py**: 設定Export/Import/Reset
- 2026-01-17: Phase 26 完了（レポート導線改善）
  - **common/file_opener.py**, **gui/features/report_navigator.py**
- 2026-01-17: Phase 24 完了（SGF E2E Regression Tests）
  - **tests/helpers/**: mock_analysis.py, stats_extraction.py
- 2026-01-16: Phase 20 完了（PR #131-135）
  - **common/platform.py**: Kivy非依存のOS判定関数を追加
  - **common/config_store.py**: JsonFileConfigStore（Mapping実装）を追加
  - **gui/lang_bridge.py**: KivyLangBridge（i18n Kivyブリッジ）を追加
  - **core/lang.py**: Observable継承削除、コールバックベースに変更
  - **許可リスト削減**: 6エントリ → 1エントリ
- 2026-01-16: Phase B4/B5/B6 完了（PR #126-135）
  - **Phase B4**: analysis/logic.py分割
    - logic_loss.py: 損失計算関数を抽出
    - logic_importance.py: 重要度計算関数を抽出
    - logic_quiz.py: クイズヘルパー関数を抽出
    - analysis/__init__.py: 再エクスポート更新
  - **Phase B5**: ai.py分割
    - ai_strategies_base.py: 基底クラス・ユーティリティを抽出（~300行）
    - ai.py: 戦略実装のみに集中（1459→1061行）
  - **Phase B6**: テスト・ドキュメント
    - test_architecture.py: モジュール構造・依存方向テスト追加
    - scripts/generate_metrics.py: メトリクス自動生成スクリプト追加
    - docs/02-code-structure.md: 本ドキュメント更新
- 2026-01-10: Phase 2 安定性向上（PR #97）
  - エラー階層追加（katrain/core/errors.py）
  - ErrorHandler追加（katrain/gui/error_handler.py）
  - 高リスク3箇所に統合（メッセージループ、engine.on_error、load_ui_state）
- 2026-01-07: コードベース簡素化（PR #90-92）
  - Contribute Engine削除（contribute_engine.py）
  - 多言語i18n削除（JP+EN以外の9言語）
  - pygame依存削除（macOS専用）
  - 残存参照クリーンアップ（KEY_CONTRIBUTE_POPUP, FONTS, 99-worklog.md）
  - 合計~12,800行削減
- 2026-01-06: Phase 4 安定化（PR #81-89）
  - gui/features テスト追加（77件）
  - 設定管理Protocol統一（_config直接アクセス排除）
  - 型ヒント改善（types.py）
  - UIヘルパー追加（helpers.py）
- 2026-01-06: gui/features パッケージ追加（Phase 3完了）
  - __main__.py を機能別モジュールに分割
  - FeatureContext Protocol による依存性注入
  - 13モジュール、~3,290行を抽出
- 2026-01-05: analysis パッケージ構造を反映（Phase B完了）
- 2025-12-30: v1.0 作成（Claude Code移行対応、軽量版）
