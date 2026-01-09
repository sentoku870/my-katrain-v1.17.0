# myKatrain コード構造

> 最終更新: 2026-01-09
> 詳細な実装ガイドは別途 `KaTrain_Code_Structure_and_YoseAnalyzer_Integration.md`（参考資料）を参照。
> Qt移行の詳細は `kivy-to-qt-migration-summary.md` を参照。

---

## 1. ディレクトリ構造

```
katrain/
├── __main__.py           # Qt起動へのリダイレクト
│
├── common/               # 共有定数（循環依存解消用）
│   └── theme_constants.py # INFO_PV_COLOR など
│
├── core/                 # コアロジック（GUI非依存）
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
└── i18n/                 # 国際化（JP+ENのみ、PR #91で簡素化）
    ├── i18n.py            # 翻訳処理
    └── locales/{en,jp}/   # 英語・日本語のみ

katrain_qt/               # Qt GUI（2026-01 移行）
├── __init__.py           # install_shims()
├── __main__.py           # python -m katrain_qt エントリポイント
├── app_qt.py             # MainWindow（QMainWindow、~1300行）
├── core_adapter.py       # GameAdapter（core との橋渡し）
├── settings.py           # 設定管理（JSON + QSettings）
│
├── compat/               # Kivy互換シム（移行期間用）
│   └── kivy_shim.py       # Kivy import のモック
│
├── analysis/             # KataGo解析
│   ├── models.py          # PositionSnapshot, CandidateMove, AnalysisResult
│   └── katago_engine.py   # QProcess ベースのエンジン管理
│
├── widgets/              # Qt ウィジェット
│   ├── board_widget.py    # GoBoardWidget（盤面描画）
│   ├── candidates_panel.py # CandidatesPanel（候補手一覧）
│   ├── score_graph.py     # ScoreGraph（スコアグラフ）
│   └── analysis_panel.py  # AnalysisPanel（解析詳細）
│
└── dialogs/              # ダイアログ
    └── settings_dialog.py # 設定ダイアログ
```

**注意**: `katrain/gui/` ディレクトリは削除されました（Qt移行完了）。

---

## 2. 主要クラスの関係（Qt）

```
MainWindow (QMainWindow)
├── self.adapter       → GameAdapter（core との橋渡し）
│   └── self._game     → Game（対局状態）
├── self.engine        → KataGoAnalysisEngine（QProcess）
├── self.board_widget  → GoBoardWidget（盤面）
├── self.candidates_panel → CandidatesPanel（候補手）
├── self.score_graph   → ScoreGraph（スコアグラフ）
├── self.analysis_panel → AnalysisPanel（解析詳細）
└── self._settings     → SettingsManager（設定管理）
```

### 依存方向
```
MainWindow → GameAdapter → Game → GameNode
          → KataGoAnalysisEngine (QProcess)
          → GoBoardWidget
          → CandidatesPanel
          → ScoreGraph
          → AnalysisPanel
```

### 座標系変換
```
KaTrain core (row=0 が下) ←→ Qt (row=0 が上)
                     ↑
              core_adapter.py で変換
```

---

## 3. データフロー（Qt）

### 3.1 解析データの流れ
```
1. MainWindow._start_analysis()
     ↓ エンジンにリクエスト
2. KataGoAnalysisEngine → KataGo (QProcess)
     ↓ JSON結果
3. analysis_completed シグナル発行
     ↓
4. MainWindow._on_analysis_completed()
     ↓ キャッシュに格納
5. UI更新（盤面、候補手、グラフ、解析パネル）
```

### 3.2 UIイベントの流れ
```
1. ユーザー操作（クリック/キーボード）
     ↓
2. Qt シグナル発行
     ↓
3. MainWindow のスロット（_on_xxx()）
     ↓
4. GameAdapter 経由で core 操作
     ↓
5. position_changed シグナル → UI更新
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

### 4.3 katrain_qt パッケージ（Qt移行、2026-01完了）

Qt（PySide6）ベースの新GUI。Kivyから完全に独立。

#### 主要コンポーネント
| ファイル | クラス | 機能 |
|---------|--------|------|
| `app_qt.py` | `MainWindow` | メインウィンドウ（~1300行） |
| `core_adapter.py` | `GameAdapter` | core との橋渡し、座標変換 |
| `settings.py` | `SettingsManager` | JSON + QSettings |
| `analysis/katago_engine.py` | `KataGoAnalysisEngine` | QProcess ベース |
| `analysis/models.py` | `PositionSnapshot`, `CandidateMove` | 解析データモデル |
| `widgets/board_widget.py` | `GoBoardWidget` | 盤面描画（QPainter） |
| `widgets/candidates_panel.py` | `CandidatesPanel` | 候補手一覧（QTableWidget） |
| `widgets/score_graph.py` | `ScoreGraph` | スコアグラフ（QPainter） |
| `widgets/analysis_panel.py` | `AnalysisPanel` | 解析詳細（QTextEdit） |
| `dialogs/settings_dialog.py` | `SettingsDialog` | 設定UI（QDialog） |

#### Qt シグナル/スロット パターン
```python
# シグナル定義
class GameAdapter(QObject):
    position_changed = Signal()  # 局面変更時に発行

# 接続
self.adapter.position_changed.connect(self._on_position_changed)

# スロット
def _on_position_changed(self):
    self._update_board()
    self._update_analysis_panel()
```

### 4.4 Gameクラスへの追加（game.py）

**追加メソッド:**
- `build_eval_snapshot()`: EvalSnapshot生成
- `get_important_move_evals(level)`: 重要手リスト取得
- `get_quiz_items(config)`: クイズ候補取得
- `build_important_moves_report()`: テキストレポート生成

---

## 5. 変更時の注意点

### 5.1 Qt UIを触る場合
- `katrain_qt/` パッケージ内で作業
- Qt シグナル/スロット パターンに従う
- 座標変換は `core_adapter.py` で行う（ウィジェットで直接変換しない）

### 5.2 解析ロジックを触る場合
- `katrain/core/analysis/` パッケージが主な変更対象
  - データモデル → `models.py`
  - 計算ロジック → `logic.py`
  - 表示処理 → `presentation.py`
- `game.py` のヘルパーメソッドから呼び出す
- インポートは `from katrain.core.eval_metrics import ...` でも
  `from katrain.core.analysis import ...` でも可

### 5.3 座標系に注意
| システム | row=0 の位置 | 使用場所 |
|----------|-------------|---------|
| KaTrain core | 下 | game.py, game_node.py |
| Qt | 上 | board_widget.py, candidates_panel.py |
| GTP文字列 | 1始まり、下から | KataGo JSON |

変換は `core_adapter.py` の `play_move_qt()` や `get_stones()` で行う。

### 5.4 翻訳を追加する場合
- 文字列を `i18n._("...")` で包む
- `uv run python i18n.py -todo` で不足をチェック
- 各言語の `.po` ファイルに追加
- `.mo` ファイルを再生成

---

## 6. テスト実行

```powershell
# Qt テスト実行
uv run pytest tests/katrain_qt/ -v

# 全テスト実行
uv run pytest tests -v

# Qt アプリ起動
python -m katrain_qt

# i18nチェック
$env:PYTHONUTF8 = "1"
uv run python i18n.py -todo

# Windows ビルド
.\tools\build_windows.ps1
```

---

## 7. 変更履歴

- 2026-01-09: Kivy→Qt GUI移行完了
  - `katrain/gui/` 削除（28ファイル）
  - `katrain_qt/` パッケージ追加（約4,500行）
  - ディレクトリ構造、クラス関係、データフローを Qt ベースに更新
  - 詳細: `docs/kivy-to-qt-migration-summary.md`
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
