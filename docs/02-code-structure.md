# myKatrain コード構造

> 最終更新: 2026-01-30（Phase 89完了）

---

## 1. ディレクトリ構造

```
katrain/
├── __main__.py           # アプリ起動、KaTrainGuiクラス（~1200行）
│
├── common/               # 共有定数（循環依存解消用）
│   ├── __init__.py       # DEFAULT_FONT など
│   ├── theme_constants.py # INFO_PV_COLOR など
│   ├── platform.py       # get_platform()（Phase 20、Kivy非依存OS判定）
│   ├── config_store.py   # JsonFileConfigStore（Phase 20、Mapping実装）
│   ├── locale_utils.py   # normalize_lang_code(), to_iso_lang_code()（Phase 52-A）
│   ├── model_labels.py   # classify_model_strength(), get_model_basename()（Phase 88）
│   ├── humanlike_config.py # normalize_humanlike_config()（Phase 88）
│   └── lexicon/          # 囲碁用語辞書パッケージ（Phase 45）
│       ├── models.py       # LexiconEntry, DiagramInfo, AIPerspective（frozen dataclass）
│       ├── validation.py   # 2段階バリデーションパイプライン
│       └── store.py        # LexiconStore（スレッドセーフ、アトミックスナップショット）
│
├── core/                 # コアロジック
│   ├── game.py            # Game（対局状態管理）
│   ├── game_node.py       # GameNode（手/解析結果）
│   ├── engine.py          # KataGoEngine（解析プロセス）
│   ├── errors.py          # KaTrainError例外階層（Phase 2で追加）
│   ├── eval_metrics.py    # ファサード（後方互換、21行）
│   ├── yose_analyzer.py   # ヨセ解析（myKatrain追加）
│   ├── sgf_parser.py      # SGF読み込み
│   │
│   ├── ai.py              # AI戦略実装（~1060行）
│   ├── ai_strategies_base.py  # AI戦略基底クラス・ユーティリティ（~300行、Phase B5）
│   │
│   ├── analysis/          # 解析基盤パッケージ（Phase B4完了）
│   │   ├── __init__.py      # 明示的再エクスポート（~500行）
│   │   ├── models.py        # Enum, Dataclass, 定数（~835行）
│   │   ├── logic.py         # 計算関数オーケストレーター（~1180行）
│   │   ├── logic_loss.py    # 損失計算関数（~105行、Phase B4）
│   │   ├── logic_importance.py # 重要度計算関数（~175行、Phase B4）
│   │   ├── logic_quiz.py    # クイズヘルパー関数（~90行、Phase B4）
│   │   ├── presentation.py  # 表示/フォーマット関数（~300行）
│   │   ├── skill_radar.py   # 5軸レーダーモデル（~570行、Phase 48-49）
│   │   ├── critical_moves.py # Critical 3選択（~455行、Phase 50）
│   │   └── meaning_tags/    # 意味タグ分類（Phase 46-47）
│   │       ├── models.py      # MeaningTagId, MeaningTag
│   │       ├── registry.py    # MEANING_TAG_REGISTRY（12タグ定義）
│   │       ├── classifier.py  # classify_meaning_tag()
│   │       └── integration.py # normalize_lang(), get_meaning_tag_label_safe()
│   │
│   ├── batch/             # バッチ処理パッケージ（Phase 42、Kivy非依存）
│   │   ├── models.py        # WriteError, BatchResult dataclass
│   │   ├── helpers.py       # 純粋関数（choose_visits_for_sgf, safe_int等）
│   │   ├── analysis.py      # analyze_single_file, analyze_single_file_leela
│   │   ├── orchestration.py # run_batch() メインエントリ
│   │   └── stats.py         # extract_game_stats, build_player_summary
│   │
│   ├── auto_setup.py       # 自動セットアップロジック（Phase 89）
│   ├── test_analysis.py    # エラー分類・テスト解析結果（Phase 89）
│   │
│   ├── leela/             # Leela Zero対応（Phase 31-36）
│   │   └── conversion.py    # leela_position_to_move_eval(), leela_sequence_to_eval_snapshot()
│   │
│   └── reports/           # レポート生成（Phase 32-37）
│       ├── types.py         # 型定義、Protocol
│       └── karte_report.py  # build_karte_report(), build_critical_3_prompt()
│
├── gui/                  # GUI（Kivy）
│   ├── controlspanel.py   # 右パネル（ControlsPanel）
│   ├── badukpan.py        # 盤面表示（BadukPanWidget）
│   ├── error_handler.py   # ErrorHandler（Phase 2で追加）
│   ├── lang_bridge.py     # KivyLangBridge（Phase 20、i18n Kivyブリッジ）
│   ├── popups.py          # ポップアップダイアログ
│   ├── widgets/
│   │   ├── graph.py         # ScoreGraph（勝率グラフ）
│   │   ├── movetree.py      # MoveTree（手順ツリー）
│   │   ├── helpers.py       # UIヘルパー関数（PR #89で追加）
│   │   ├── radar_geometry.py # レーダー幾何計算（Phase 51、Kivy非依存）
│   │   └── radar_chart.py   # RadarChartWidget（Phase 51）
│   │
│   └── features/          # 機能モジュール（Phase 3で追加）
│       ├── context.py           # FeatureContext Protocol
│       ├── karte_export.py      # カルテエクスポート
│       ├── summary_stats.py     # サマリ統計計算
│       ├── summary_aggregator.py # サマリ集計
│       ├── summary_formatter.py # サマリMarkdown生成
│       ├── summary_ui.py        # サマリUI/ダイアログ
│       ├── summary_io.py        # サマリファイル保存
│       ├── quiz_popup.py        # クイズポップアップ
│       ├── quiz_session.py      # クイズセッション
│       ├── batch_core.py        # バッチ解析コア
│       ├── batch_ui.py          # バッチ解析UI
│       ├── settings_popup.py    # 設定ポップアップ
│       ├── skill_radar_popup.py # スキルレーダーポップアップ（Phase 51）
│       └── auto_mode_popup.py   # 自動セットアップUI（Phase 89）
│
├── gui.kv                # Kivyレイアウト定義
├── katrain.kv            # 追加レイアウト
│
└── i18n/                 # 国際化（JP+ENのみ、PR #91で簡素化）
    ├── i18n.py            # 翻訳処理
    └── locales/{en,jp}/   # 英語・日本語のみ
```

---

## 2. 主要クラスの関係

```
KaTrainGui (App)
├── self.game      → Game（対局状態）
├── self.engine    → KataGoEngine（解析エンジン）
├── self.controls  → ControlsPanel（右パネル）
├── self.board_gui → BadukPanWidget（盤面）
└── self.analysis_controls → AnalysisControls（解析トグル）
```

### 依存方向
```
KaTrainGui → Game → GameNode
          → KataGoEngine
          → ControlsPanel → ScoreGraph
                         → various widgets
```

---

## 3. データフロー

### 3.1 解析データの流れ
```
1. GameNode.analyze()
     ↓ KataGoEngineに解析リクエスト
2. KataGoEngine → KataGo (subprocess)
     ↓ JSON結果
3. GameNode.set_analysis(result)
     ↓ analysis dict に格納
4. KaTrainGui.update_state()
     ↓
5. ControlsPanel.update_evaluation()
     ↓
6. UI更新（グラフ、盤面、情報パネル）
```

### 3.2 UIイベントの流れ
```
1. ユーザー操作（ボタン/盤面タップ）
     ↓
2. Kivy → root.katrain("action", args)
     ↓
3. KaTrainGui.__call__(message)
     ↓ メッセージキュー
4. KaTrainGui._do_<action>()
```

---

## 4. myKatrain で追加したファイル

### 4.1 analysis パッケージ（Phase B4完了）

`katrain/core/eval_metrics.py` は後方互換用ファサード。
実体は `katrain/core/analysis/` パッケージに分離。

#### models.py（データモデル）
**Enum:**
- `MistakeCategory`: GOOD/INACCURACY/MISTAKE/BLUNDER
- `PositionDifficulty`: EASY/NORMAL/HARD/ONLY_MOVE
- `ConfidenceLevel`: HIGH/MEDIUM/LOW
- `PVFilterLevel`: MINIMAL/NORMAL/DETAILED/FULL（Phase 11追加）

**Dataclass:**
- `MoveEval`: 1手の評価データ
- `EvalSnapshot`: 対局全体の評価スナップショット
- `SkillPreset`: 棋力別プリセット設定
- `ImportantMoveSettings`: 重要手判定の設定
- `QuizItem`, `QuizConfig`: クイズ用データ
- `DifficultyMetrics`: 難易度メトリクス（Phase 12追加）

**定数:**
- `SKILL_PRESETS`: relaxed/beginner/standard/advanced/pro
- `SCORE_THRESHOLDS`, `WINRATE_THRESHOLDS`: ミス分類閾値

#### logic.py（オーケストレーター）
Phase B4で以下のサブモジュールに分割。logic.pyは再エクスポートを担当。

**logic_loss.py（損失計算）:**
- `compute_loss_from_delta()`: delta_score/delta_winrateから損失計算
- `compute_canonical_loss()`: 正準的な損失量を計算
- `classify_mistake()`: 損失からMistakeCategoryを決定

**logic_importance.py（重要度計算）:**
- `get_difficulty_modifier()`: 難易度に応じた重要度修正値
- `get_reliability_scale()`: 訪問数に基づく信頼度スケール
- `compute_importance_for_moves()`: 各手の重要度スコアを計算
- `pick_important_moves()`: 重要局面を抽出

**logic_quiz.py（クイズヘルパー）:**
- `quiz_items_from_snapshot()`: スナップショットからクイズアイテムを生成
- `quiz_points_lost_from_candidate()`: 候補手から損失値を抽出

**logic.py（直接定義の関数）:**
- `snapshot_from_game(game)`: GameからEvalSnapshot生成
- `compute_confidence_level(snapshot)`: 信頼度計算
- `recommend_auto_strictness(snapshot)`: 自動プリセット推奨
- `compute_difficulty_metrics()`: 難易度メトリクス計算（Phase 12）

#### presentation.py（表示関数）
- `get_confidence_label(level, lang)`: 信頼度ラベル
- `format_evidence_examples(moves, lang)`: 証拠フォーマット
- `SKILL_PRESET_LABELS`: 日本語ラベル（激甘/甘口/標準/辛口/激辛）
- `format_difficulty_metrics()`: 難易度メトリクスのフォーマット（Phase 12）

### 4.2 ai_strategies_base.py（Phase B5追加）

AI戦略の基底クラスとユーティリティを提供。

**クラス:**
- `AIStrategy`: AI戦略の基底クラス（`generate_move()`を定義）

**デコレータ:**
- `@register_strategy(name)`: 戦略をSTRATEGY_REGISTRYに登録

**ユーティリティ関数:**
- `interp_ix()`, `interp1d()`, `interp2d()`: 補間関数
- `policy_weighted_move()`: ポリシー重み付け手選択
- `generate_influence_territory_weights()`: 影響力・地重み生成
- `generate_local_tenuki_weights()`: ローカル/手抜き重み生成

**使い方:**
```python
from katrain.core.ai_strategies_base import AIStrategy, register_strategy

@register_strategy("custom")
class CustomStrategy(AIStrategy):
    def generate_move_with_board_and_stone(self, cn, board_size_x, board_size_y, player):
        # カスタム戦略の実装
        ...
```

### 4.3 yose_analyzer.py（Phase 2）

**クラス:**
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
| `settings_popup.py` | 設定ポップアップ | ~400 |

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

> 詳細な変更履歴は `CLAUDE.md` セクション10を参照。

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
