# myKatrain コード構造

> 最終更新: 2026-01-06
> 詳細な実装ガイドは別途 `KaTrain_Code_Structure_and_YoseAnalyzer_Integration.md`（参考資料）を参照。

---

## 1. ディレクトリ構造

```
katrain/
├── __main__.py           # アプリ起動、KaTrainGuiクラス（~1200行）
│
├── common/               # 共有定数（循環依存解消用）
│   └── theme_constants.py # INFO_PV_COLOR など
│
├── core/                 # コアロジック
│   ├── game.py            # Game（対局状態管理）
│   ├── game_node.py       # GameNode（手/解析結果）
│   ├── engine.py          # KataGoEngine（解析プロセス）
│   ├── eval_metrics.py    # ファサード（後方互換、21行）
│   ├── yose_analyzer.py   # ヨセ解析（myKatrain追加）
│   ├── sgf_parser.py      # SGF読み込み
│   │
│   └── analysis/          # 解析基盤パッケージ（Phase B完了）
│       ├── __init__.py      # 明示的再エクスポート（~270行）
│       ├── models.py        # Enum, Dataclass, 定数（~900行）
│       ├── logic.py         # 計算関数（~1300行）
│       └── presentation.py  # 表示/フォーマット関数（~330行）
│
├── gui/                  # GUI（Kivy）
│   ├── controlspanel.py   # 右パネル（ControlsPanel）
│   ├── badukpan.py        # 盤面表示（BadukPanWidget）
│   ├── popups.py          # ポップアップダイアログ
│   ├── widgets/
│   │   ├── graph.py       # ScoreGraph（勝率グラフ）
│   │   └── movetree.py    # MoveTree（手順ツリー）
│   │
│   └── features/          # 機能モジュール（Phase 3で追加）
│       ├── context.py         # FeatureContext Protocol
│       ├── karte_export.py    # カルテエクスポート
│       ├── summary_stats.py   # サマリ統計計算
│       ├── summary_aggregator.py # サマリ集計
│       ├── summary_formatter.py  # サマリMarkdown生成
│       ├── summary_ui.py      # サマリUI/ダイアログ
│       ├── summary_io.py      # サマリファイル保存
│       ├── quiz_popup.py      # クイズポップアップ
│       ├── quiz_session.py    # クイズセッション
│       ├── batch_core.py      # バッチ解析コア
│       ├── batch_ui.py        # バッチ解析UI
│       └── settings_popup.py  # 設定ポップアップ
│
├── gui.kv                # Kivyレイアウト定義
├── katrain.kv            # 追加レイアウト
│
└── i18n/                 # 国際化
    ├── i18n.py            # 翻訳処理
    └── locales/*/         # 各言語のpoファイル
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

### 4.1 analysis パッケージ（Phase B完了）

`katrain/core/eval_metrics.py` は後方互換用ファサード。
実体は `katrain/core/analysis/` パッケージに分離。

#### models.py（データモデル）
**Enum:**
- `MistakeCategory`: GOOD/INACCURACY/MISTAKE/BLUNDER
- `PositionDifficulty`: EASY/NORMAL/HARD/ONLY_MOVE
- `ConfidenceLevel`: HIGH/MEDIUM/LOW

**Dataclass:**
- `MoveEval`: 1手の評価データ
- `EvalSnapshot`: 対局全体の評価スナップショット
- `SkillPreset`: 棋力別プリセット設定
- `ImportantMoveSettings`: 重要手判定の設定
- `QuizItem`, `QuizConfig`: クイズ用データ

**定数:**
- `SKILL_PRESETS`: relaxed/beginner/standard/advanced/pro
- `SCORE_THRESHOLDS`, `WINRATE_THRESHOLDS`: ミス分類閾値

#### logic.py（計算関数）
- `snapshot_from_game(game)`: GameからEvalSnapshot生成
- `pick_important_moves(snapshot, settings)`: 重要手抽出
- `classify_mistake(loss, thresholds)`: ミス分類
- `compute_confidence_level(snapshot)`: 信頼度計算
- `recommend_auto_strictness(snapshot)`: 自動プリセット推奨

#### presentation.py（表示関数）
- `get_confidence_label(level, lang)`: 信頼度ラベル
- `format_evidence_examples(moves, lang)`: 証拠フォーマット
- `SKILL_PRESET_LABELS`: 日本語ラベル（激甘/甘口/標準/辛口/激辛）

### 4.2 yose_analyzer.py（Phase 2）

**クラス:**
- `YoseAnalyzer`: ヨセ解析のラッパー
- `YoseImportantMovesReport`: レポート出力

**使い方:**
```python
analyzer = YoseAnalyzer.from_game(game)
report = analyzer.build_important_moves_report()
```

### 4.3 gui/features パッケージ（Phase 3完了）

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

### 4.4 Gameクラスへの追加（game.py）

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

- 2026-01-06: Phase 4 安定化（PR #81-88）
  - gui/features テスト追加（77件）
  - 設定管理Protocol統一（_config直接アクセス排除）
  - 型ヒント改善（types.py）
- 2026-01-06: gui/features パッケージ追加（Phase 3完了）
  - __main__.py を機能別モジュールに分割
  - FeatureContext Protocol による依存性注入
  - 13モジュール、~3,290行を抽出
- 2026-01-05: analysis パッケージ構造を反映（Phase B完了）
- 2025-12-30: v1.0 作成（Claude Code移行対応、軽量版）
