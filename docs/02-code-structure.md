# myKatrain コード構造

> 最終更新: 2026-01-24（Phase 52-B対応）

---

## 1. ディレクトリ構造

```
katrain/
├── __main__.py           # アプリ起動、KaTrainGuiクラス（~1200行）
│
├── common/               # 共有定数・ユーティリティ（Kivy非依存）
│   ├── __init__.py       # DEFAULT_FONT など
│   ├── theme_constants.py # INFO_PV_COLOR など
│   ├── platform.py       # get_platform()（Phase 20、Kivy非依存OS判定）
│   ├── config_store.py   # JsonFileConfigStore（Phase 20、Mapping実装）
│   ├── locale_utils.py   # 言語コード正規化（Phase 52-A）
│   │
│   └── lexicon/          # 囲碁用語辞書パッケージ（Phase 45）
│       ├── __init__.py     # 公開API
│       ├── models.py       # frozen dataclass（LexiconEntry等）
│       ├── validation.py   # 2段階バリデーション
│       └── store.py        # LexiconStore（スレッドセーフ）
│
├── core/                 # コアロジック（Kivy非依存）
│   ├── game.py            # Game（対局状態管理）
│   ├── game_node.py       # GameNode（手/解析結果）
│   ├── engine.py          # KataGoEngine（解析プロセス）
│   ├── errors.py          # KaTrainError例外階層（Phase 2）
│   ├── eval_metrics.py    # ファサード（後方互換、21行）
│   ├── yose_analyzer.py   # ヨセ解析
│   ├── sgf_parser.py      # SGF読み込み
│   │
│   ├── ai.py              # AI戦略実装（~1060行）
│   ├── ai_strategies_base.py  # AI戦略基底クラス（~300行）
│   │
│   ├── analysis/          # 解析基盤パッケージ
│   │   ├── __init__.py      # 再エクスポート
│   │   ├── models.py        # Enum, Dataclass, 定数
│   │   ├── logic.py         # 計算関数オーケストレーター
│   │   ├── logic_loss.py    # 損失計算関数
│   │   ├── logic_importance.py # 重要度計算関数
│   │   ├── logic_quiz.py    # クイズヘルパー関数
│   │   ├── presentation.py  # 表示/フォーマット関数
│   │   ├── skill_radar.py   # 5軸スキルレーダー（Phase 48-49）
│   │   ├── critical_moves.py # Critical 3選出（Phase 50）
│   │   │
│   │   └── meaning_tags/    # 意味タグ分類（Phase 46-47）
│   │       ├── __init__.py    # 遅延インポート
│   │       ├── models.py      # MeaningTagId, MeaningTag
│   │       ├── registry.py    # MEANING_TAG_REGISTRY
│   │       ├── classifier.py  # classify_meaning_tag()
│   │       └── integration.py # ラベル取得ヘルパー
│   │
│   ├── batch/             # バッチ処理パッケージ（Phase 42）
│   │   ├── __init__.py      # 遅延インポート
│   │   ├── models.py        # WriteError, BatchResult
│   │   ├── helpers.py       # 純粋関数群
│   │   ├── analysis.py      # 単一ファイル解析
│   │   ├── orchestration.py # run_batch()
│   │   └── stats.py         # 統計抽出、サマリ生成
│   │
│   ├── leela/             # Leela Zero統合（Phase 30-36）
│   │   ├── __init__.py      # 再エクスポート
│   │   ├── models.py        # LeelaCandidate, LeelaPositionEval
│   │   ├── engine.py        # LeelaEngine（GTPプロトコル）
│   │   ├── conversion.py    # MoveEval変換
│   │   ├── logic.py         # 損失推定計算
│   │   ├── parser.py        # lz-analyze パース
│   │   └── presentation.py  # 表示ヘルパー
│   │
│   └── reports/           # レポート生成（Phase 24+）
│       ├── __init__.py      # 再エクスポート
│       ├── karte_report.py  # カルテ生成
│       ├── summary_report.py # サマリ生成
│       ├── package_export.py # パッケージエクスポート
│       ├── quiz_report.py   # クイズレポート
│       ├── important_moves_report.py # 重要手レポート
│       └── types.py         # 型定義、例外
│
├── gui/                  # GUI（Kivy）
│   ├── controlspanel.py   # 右パネル（ControlsPanel）
│   ├── badukpan.py        # 盤面表示（BadukPanWidget）
│   ├── error_handler.py   # ErrorHandler（Phase 2）
│   ├── lang_bridge.py     # KivyLangBridge（Phase 20）
│   ├── theme_loader.py    # テーマ読み込み（Phase 43）
│   ├── popups.py          # ポップアップダイアログ
│   │
│   ├── widgets/
│   │   ├── graph.py         # ScoreGraph（勝率グラフ）
│   │   ├── movetree.py      # MoveTree（手順ツリー）
│   │   ├── helpers.py       # UIヘルパー関数
│   │   ├── radar_geometry.py # レーダー幾何計算（Phase 51）
│   │   └── radar_chart.py   # RadarChartWidget（Phase 51）
│   │
│   └── features/          # 機能モジュール（Phase 3+）
│       ├── context.py         # FeatureContext Protocol
│       ├── karte_export.py    # カルテエクスポート
│       ├── summary_*.py       # サマリ関連
│       ├── quiz_popup.py      # クイズポップアップ
│       ├── quiz_session.py    # クイズセッション
│       ├── batch_core.py      # バッチ解析コア
│       ├── batch_ui.py        # バッチ解析UI
│       ├── settings_popup.py  # 設定ポップアップ
│       ├── skill_radar_popup.py # レーダーポップアップ（Phase 51）
│       ├── engine_compare_popup.py # エンジン比較（Phase 39）
│       ├── diagnostics_popup.py # 診断（Phase 29）
│       └── report_navigator.py # レポート導線（Phase 26）
│
├── gui.kv                # Kivyレイアウト定義
├── katrain.kv            # 追加レイアウト
│
└── i18n/                 # 国際化（JP+ENのみ）
    ├── i18n.py            # 翻訳処理
    └── locales/{en,jp}/   # 英語・日本語のみ
```

---

## 2. 主要クラスの関係

```
KaTrainGui (App)
├── self.game        → Game（対局状態）
├── self.engine      → KataGoEngine（解析エンジン）
├── self.leela_engine → LeelaEngine（Leela Zero、Phase 30）
├── self.controls    → ControlsPanel（右パネル）
├── self.board_gui   → BadukPanWidget（盤面）
└── self.analysis_controls → AnalysisControls（解析トグル）
```

### 依存方向
```
KaTrainGui → Game → GameNode
          → KataGoEngine / LeelaEngine
          → ControlsPanel → ScoreGraph
                         → various widgets
```

---

## 3. データフロー

### 3.1 解析データの流れ
```
1. GameNode.analyze()
     ↓ KataGoEngine / LeelaEngine に解析リクエスト
2. Engine → KataGo / Leela Zero (subprocess)
     ↓ JSON結果 / GTP結果
3. GameNode.set_analysis(result) または conversion.py 経由
     ↓ analysis dict / MoveEval に格納
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

## 4. Phase 21-52 で追加されたモジュール

### 4.1 skill_radar（5軸スキルレーダー）

**ファイル**: `katrain/core/analysis/skill_radar.py`（~930行）
**Phase**: 48-49

5軸スキル評価モデル。Opening/Fighting/Endgame/Stability/Awarenessの5軸でプレイヤースキルを評価。

#### 主要クラス・Enum
```python
class RadarAxis(str, Enum):
    OPENING = "opening"
    FIGHTING = "fighting"
    ENDGAME = "endgame"
    STABILITY = "stability"
    AWARENESS = "awareness"

class SkillTier(str, Enum):
    TIER_1 = "TIER_1"  # int=1
    ...
    TIER_5 = "TIER_5"  # int=5
    TIER_UNKNOWN = "TIER_UNKNOWN"

@dataclass(frozen=True)
class RadarMetrics:
    axis_scores: Mapping[RadarAxis, int]  # 1-5
    overall_tier: Optional[SkillTier]
    valid_move_counts: Mapping[RadarAxis, int]
    games_aggregated: Optional[int]

@dataclass(frozen=True)
class AggregatedRadarResult:  # Phase 49
    axis_scores: Mapping[RadarAxis, Optional[float]]
    overall_tier: Optional[SkillTier]
    games_aggregated: int
```

#### 主要関数
- `compute_radar_from_moves(moves, player?)` → `RadarMetrics`
- `aggregate_radar(radar_list)` → `Optional[AggregatedRadarResult]`
- `compute_overall_tier(scores)` → `SkillTier`（偶数軸は上位median）
- `radar_from_dict()`, `round_score()`（シリアライゼーション）

#### 定数
```python
OPENING_END_MOVE = 50
ENDGAME_START_MOVE = 150
MIN_MOVES_FOR_RADAR = 10
MIN_VALID_AXES_FOR_OVERALL = 3
GARBAGE_TIME_WINRATE_HIGH = 0.99
GARBAGE_TIME_WINRATE_LOW = 0.01
```

**制約**: 19x19盤面のみ対応

---

### 4.2 critical_moves（Critical 3選出）

**ファイル**: `katrain/core/analysis/critical_moves.py`（~455行）
**Phase**: 50

LLMコーチング用の重要ミス3手を決定論的に選出。

#### 主要クラス
```python
@dataclass(frozen=True)
class CriticalMove:
    move_number: int
    player: str
    gtp_coord: str
    score_loss: Optional[float]
    delta_winrate: Optional[float]
    meaning_tag_id: Optional[str]
    meaning_tag_label: Optional[str]
    position_difficulty: str
    reason_tags: Tuple[str, ...]
    score_stdev: Optional[float]
    game_phase: str
    importance_score: float
    critical_score: float  # 最終スコア（Decimal丸め）
```

#### 主要関数
- `select_critical_moves(game, max_moves=3, lang="en")` → `List[CriticalMove]`

#### 定数
```python
MEANING_TAG_WEIGHTS = {
    "life_death_error": 1.5,
    "reading_failure": 1.2,
    ...
}
DIVERSITY_PENALTY_FACTOR = 0.5
CRITICAL_SCORE_PRECISION = 4
```

**特徴**: Decimal ROUND_HALF_UPで決定論的（同じゲーム→同じ3手）

---

### 4.3 meaning_tags（意味タグ分類）

**ディレクトリ**: `katrain/core/analysis/meaning_tags/`（~1120行）
**Phase**: 46-47

囲碁のミスを12カテゴリに分類するセマンティックシステム。

#### models.py
```python
class MeaningTagId(str, Enum):
    MISSED_TESUJI = "missed_tesuji"
    OVERPLAY = "overplay"
    SLOW_MOVE = "slow_move"
    DIRECTION_ERROR = "direction_error"
    SHAPE_MISTAKE = "shape_mistake"
    READING_FAILURE = "reading_failure"
    ENDGAME_SLIP = "endgame_slip"
    CONNECTION_MISS = "connection_miss"
    CAPTURE_RACE_LOSS = "capture_race_loss"
    LIFE_DEATH_ERROR = "life_death_error"
    TERRITORIAL_LOSS = "territorial_loss"
    UNCERTAIN = "uncertain"

@dataclass(frozen=True)
class MeaningTag:
    id: MeaningTagId
    lexicon_anchor_id: Optional[str]
    confidence: float  # 0.0-1.0
    debug_reason: str
```

#### classifier.py
```python
def classify_meaning_tag(
    move_eval: MoveEval,
    context: Optional[ClassificationContext] = None
) -> MeaningTag
```

ヒューリスティックベースの分類。損失量、ポリシー差、手の距離などから判定。

#### integration.py
```python
def normalize_lang(lang: str) -> str  # "jp" → "ja"
def get_meaning_tag_label_safe(tag_id, lang) -> str
def format_meaning_tag_with_definition(tag_id, lang, max_len=30) -> str
```

---

### 4.4 lexicon（囲碁用語辞書）

**ディレクトリ**: `katrain/common/lexicon/`（~1150行）
**Phase**: 45

Kivy非依存の囲碁用語辞書。完全イミュータブル設計。

#### models.py
```python
@dataclass(frozen=True)
class LexiconEntry:
    id: str
    level: int  # 1-3
    category: str
    ja_term: str
    en_terms: Tuple[str, ...]
    ja_one_liner: str
    en_one_liner: str
    ja_short: str
    en_short: str
    # Level 3専用フィールド
    ja_title: Optional[str]
    en_title: Optional[str]
    ja_expanded: Optional[str]
    en_expanded: Optional[str]
    ...
```

#### store.py
```python
class LexiconStore:
    def get(self, entry_id: str) -> Optional[LexiconEntry]
    def get_by_title(self, title: str, lang: str) -> Optional[LexiconEntry]
    def get_by_category(self, category: str) -> Tuple[LexiconEntry, ...]
    def get_by_level(self, level: int) -> Tuple[LexiconEntry, ...]
```

**環境変数**: `LEXICON_PATH` でパスオーバーライド可能

---

### 4.5 locale_utils（言語コード正規化）

**ファイル**: `katrain/common/locale_utils.py`（~100行）
**Phase**: 52-A

```python
def normalize_lang_code(lang: str) -> str
    """内部正規コードへ変換: "ja_JP", "ja-JP", "JA" → "jp" """

def to_iso_lang_code(lang: str) -> str
    """ISO 639-1へ変換: "jp" → "ja", "en" → "en" """
```

地域バリアント対応、大文字小文字非依存、空白トリム。

---

### 4.6 radar_geometry（レーダー幾何計算）

**ファイル**: `katrain/gui/widgets/radar_geometry.py`（~150行）
**Phase**: 51

Kivy非依存の純粋幾何関数。テスト可能、CI安全。

```python
NUM_AXES = 5
ANGLE_OFFSET_DEG = 90  # 12時方向が軸0
AXIS_ORDER = ("opening", "fighting", "endgame", "stability", "awareness")

def calculate_vertex(axis_index, score, center, max_radius) -> Tuple[float, float]
def get_label_position(axis_index, center, label_distance) -> Tuple[float, float]
def tier_to_color(tier_str) -> Tuple[float, float, float, float]  # RGBA
def build_mesh_data(scores_dict, ...) -> Tuple[list, list]  # vertices, indices
```

**座標系**: 原点左下、Y上向き（Kivy標準）。軸0=90°、時計回り。

---

### 4.7 radar_chart（レーダーチャートWidget）

**ファイル**: `katrain/gui/widgets/radar_chart.py`（~160行）
**Phase**: 51

```python
class RadarChartWidget(RelativeLayout):
    scores = DictProperty({})
    tiers = DictProperty({})
    overall_tier = StringProperty("")

    GRID_FRACTIONS = [0.2, 0.4, 0.6, 0.8, 1.0]  # 5等分グリッド
```

**特徴**:
- `Clock.create_trigger()` でデバウンス再描画
- 頂点色分け: Tier 4-5緑、3黄、1-2赤、unknown灰

---

### 4.8 batch（バッチ処理）

**ディレクトリ**: `katrain/core/batch/`（~3260行）
**Phase**: 42

Kivy非依存のバッチSGF解析。

#### models.py
```python
@dataclass
class WriteError:
    file_kind: str
    sgf_id: str
    target_path: str
    exception_type: str
    message: str

@dataclass
class BatchResult:
    success_count: int
    fail_count: int
    skip_count: int
    output_dir: str
    cancelled: bool
    ...
```

#### helpers.py（純粋関数）
- `collect_sgf_files_recursive()`
- `choose_visits_for_sgf(sgf_path, base_visits, jitter_pct?, deterministic?)`
- `sanitize_filename()`, `get_unique_filename()`
- `safe_write_file()`, `safe_read_file()`
- `get_canonical_loss()`

#### orchestration.py
```python
def run_batch(
    katrain,
    engine,
    input_dir: str,
    output_dir: Optional[str] = None,
    visits: int = 100,
    analysis_engine: str = "katago",  # or "leela"
    per_move_timeout: int = 30,
    ...
) -> BatchResult
```

#### stats.py
```python
def extract_game_stats(game, rel_path, log_cb?, target_visits?) -> Optional[dict]
def build_player_summary(stats_list, player_filter?, min_games_per_player?) -> dict
```

19x19のみRadar計算、meaning_tags統計収集。

---

### 4.9 leela（Leela Zero統合）

**ディレクトリ**: `katrain/core/leela/`（~1440行）
**Phase**: 30-36

GTPベースのLeela Zeroエンジン統合。

#### models.py
```python
@dataclass
class LeelaCandidate:
    move: str
    winrate: float  # 0.0-1.0
    visits: int
    pv: Tuple[str, ...]
    prior: float
    loss_est: Optional[float]

@dataclass
class LeelaPositionEval:
    candidates: List[LeelaCandidate]
    root_visits: int
    parse_error: Optional[str]
```

#### engine.py
```python
class LeelaEngine:
    def load_game(self, game: Game) -> None
    def analyze(self, visits: int, interval: float) -> LeelaPositionEval
    def cancel_analysis(self) -> None
    def is_idle(self) -> bool
    def shutdown(self) -> None
```

#### conversion.py
```python
def leela_position_to_move_eval(leela_eval, move_num, player, ...) -> MoveEval
def leela_sequence_to_eval_snapshot(sgf_moves, leela_evals, ...) -> EvalSnapshot
```

Winrate視点変換（手番→黒視点）、`MoveEval.leela_loss_est` フィールド設定。

---

### 4.10 reports（レポート生成）

**ディレクトリ**: `katrain/core/reports/`（~2720行）
**Phase**: 24+

カルテ・サマリ・クイズ・パッケージエクスポートのマルチフォーマット生成。

#### karte_report.py（~1470行）
```python
def build_karte_report(
    game: Game,
    lang: str = "jp",
    skill_preset: Optional[str] = None,
    target_visits: int = 100,
    ...
) -> str
```

- エンジン認識: `format_loss_with_engine_suffix()`（Leelaは「(推定)」付き）
- Critical 3セクション: `_critical_3_section_for()`
- 混合エンジン検出: `is_single_engine_snapshot()` → `MixedEngineSnapshotError`

#### summary_report.py（~630行）
```python
def build_summary_report(game_data_list, focus_player?) -> str
```

複数局のプレイヤーサマリ。Skill Profileセクション付き。

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
  - スキル評価 → `skill_radar.py`
  - 意味タグ → `meaning_tags/`
- インポートは `from katrain.core.eval_metrics import ...` でも
  `from katrain.core.analysis import ...` でも可

### 5.3 バッチ処理を触る場合
- `katrain/core/batch/` パッケージを使用
- `helpers.py` は純粋関数（テスト容易）
- `orchestration.py` の `run_batch()` がメインエントリ
- Kivy依存なし（`gui/features/batch_*.py` がUI担当）

### 5.4 翻訳を追加する場合
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

- 2026-01-24: Phase 52-B 対応（本ドキュメント更新）
  - Phase 21-52の10モジュールを追加
  - ディレクトリ構造を最新化
  - 各モジュールの詳細セクションを追加
- 2026-01-23: Phase 52-A 完了（Tofu Fix + Language Code Consistency）
  - **common/locale_utils.py**: 言語コード正規化関数を追加
  - 豆腐修正: 複数ウィジェットに`font_name=Theme.DEFAULT_FONT`追加
- 2026-01-23: Phase 51 完了（Radar UI Widget）
  - **gui/widgets/radar_geometry.py**: 純粋幾何関数（Kivy非依存）
  - **gui/widgets/radar_chart.py**: RadarChartWidget
  - **gui/features/skill_radar_popup.py**: レーダーポップアップ
- 2026-01-23: Phase 50 完了（Critical 3 Focused Review Mode）
  - **core/analysis/critical_moves.py**: Critical 3選出
  - CriticalMove dataclass、決定論的選出アルゴリズム
- 2026-01-23: Phase 49 完了（Radar Aggregation & Summary Integration）
  - **core/analysis/skill_radar.py**: AggregatedRadarResult追加
  - aggregate_radar()、サマリ統合
- 2026-01-23: Phase 48 完了（5-Axis Radar Data Model）
  - **core/analysis/skill_radar.py**: 新規作成
  - RadarAxis enum、SkillTier enum、RadarMetrics dataclass
- 2026-01-23: Phase 47 完了（Meaning Tags Integration）
  - **core/analysis/meaning_tags/integration.py**: 統合ヘルパー
  - MoveEval.meaning_tag_id フィールド追加
- 2026-01-23: Phase 46 完了（Meaning Tags System Core）
  - **core/analysis/meaning_tags/** パッケージ新規作成
  - 12タグ分類、classifier、registry
- 2026-01-23: Phase 45 完了（Lexicon Core Infrastructure）
  - **common/lexicon/** パッケージ新規作成
  - LexiconEntry frozen dataclass、LexiconStore
- 2026-01-21: Phase 44 完了（Batch Analysis Fixes）
  - 信頼性閾値の一貫性修正
  - バッチ完了チャイム追加
- 2026-01-20: Phase 43 完了（Stability Audit）
  - Config save atomic化
  - Leela shutdown改善
  - **gui/theme_loader.py**: 新規作成
- 2026-01-20: Phase 42 完了（Batch Core Package）
  - **core/batch/** パッケージ新規作成
  - models.py、helpers.py、analysis.py、orchestration.py、stats.py
- 2026-01-20: Phase 41 完了（コード品質リファクタリング）
  - AnalysisMode enum追加
  - コマンドハンドラ抽出
- 2026-01-19: Phase 40 完了（Leela Zero対戦機能）
  - LeelaStrategy実装
- 2026-01-19: Phase 39 完了（エンジン比較ビュー）
  - **core/analysis/engine_compare.py**: 比較ロジック
  - **gui/features/engine_compare_popup.py**: 比較UI
- 2026-01-18: Phase 38 完了（安定化）
  - バリデーション強化、エラーハンドリング改善
- 2026-01-18: Phase 37 完了（テスト強化）
  - MixedEngineSnapshotError導入
  - Leelaゴールデンテスト追加
- 2026-01-18: Phase 36 完了（Leelaバッチ解析）
  - analyze_single_file_leela()
  - バッチUIエンジン選択
- 2026-01-18: Phase 35 完了（Leelaカルテ統合）
  - has_loss_data()、format_loss_with_engine_suffix()
- 2026-01-18: Phase 33 完了（エンジン選択設定）
  - get_analysis_engine()
- 2026-01-18: Phase 32 完了（レポートLeela対応）
  - EngineType enum、detect_engine_type()
- 2026-01-18: Phase 31 完了（Leela→MoveEval変換）
  - **core/leela/conversion.py**: 変換モジュール
- 2026-01-18: Phase 30 完了（解析強度抽象化）
  - AnalysisStrength enum、resolve_visits()
  - **core/leela/** パッケージ新規作成
- 2026-01-17: Phase 29 完了（Diagnostics）
  - **common/sanitize.py**: サニタイズ関数
  - **core/log_buffer.py**: 循環ログバッファ
  - **core/diagnostics.py**: 診断情報収集
  - **gui/features/diagnostics_popup.py**: 診断UI
- 2026-01-17: Phase 28 完了（Smart Kifu運用強化）
  - ImportErrorCode enum
  - TrainingSetSummary dataclass
- 2026-01-17: Phase 27 完了（Settings UIスケーラブル化）
  - **common/settings_export.py**: 設定Export/Import
- 2026-01-17: Phase 26 完了（レポート導線改善）
  - **common/file_opener.py**: ファイルオープナー
  - **gui/features/report_navigator.py**: レポート導線UI
- 2026-01-17: Phase 24 完了（SGF E2E Regression Tests）
  - tests/helpers/ パッケージ
- 2026-01-16: Phase 20 完了（PR #131-135）
  - **common/platform.py**: Kivy非依存のOS判定関数
  - **common/config_store.py**: JsonFileConfigStore
  - **gui/lang_bridge.py**: KivyLangBridge
