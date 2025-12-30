# myKatrain コード構造

> 最終更新: 2025-12-30
> 詳細な実装ガイドは別途 `KaTrain_Code_Structure_and_YoseAnalyzer_Integration.md`（参考資料）を参照。

---

## 1. ディレクトリ構造

```
katrain/
├── __main__.py           # アプリ起動、KaTrainGuiクラス
│
├── core/                 # コアロジック
│   ├── game.py            # Game（対局状態管理）
│   ├── game_node.py       # GameNode（手/解析結果）
│   ├── engine.py          # KataGoEngine（解析プロセス）
│   ├── eval_metrics.py    # 重要局面/ミス分類（myKatrain追加）
│   ├── yose_analyzer.py   # ヨセ解析（myKatrain追加）
│   └── sgf_parser.py      # SGF読み込み
│
├── gui/                  # GUI（Kivy）
│   ├── controlspanel.py   # 右パネル（ControlsPanel）
│   ├── badukpan.py        # 盤面表示（BadukPanWidget）
│   ├── popups.py          # ポップアップダイアログ
│   └── widgets/
│       ├── graph.py       # ScoreGraph（勝率グラフ）
│       └── movetree.py    # MoveTree（手順ツリー）
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

### 4.1 eval_metrics.py（Phase 1-4）

**クラス:**
- `MoveEval`: 1手の評価データ
- `EvalSnapshot`: 対局全体の評価スナップショット
- `QuizItem`: クイズ用の問題データ
- `QuizConfig`: クイズ設定
- `ImportantMoveSettings`: 重要手判定の設定

**主要関数:**
- `snapshot_from_game(game)`: GameからEvalSnapshot生成
- `pick_important_moves(snapshot, settings)`: 重要手抽出
- `quiz_items_from_snapshot(snapshot, config)`: クイズ候補抽出

**プリセット:**
- `IMPORTANT_MOVE_SETTINGS_BY_LEVEL`: easy/normal/strict
- `QUIZ_PRESETS`: beginner/standard/advanced

### 4.2 yose_analyzer.py（Phase 2）

**クラス:**
- `YoseAnalyzer`: ヨセ解析のラッパー
- `YoseImportantMovesReport`: レポート出力

**使い方:**
```python
analyzer = YoseAnalyzer.from_game(game)
report = analyzer.build_important_moves_report()
```

### 4.3 Gameクラスへの追加（game.py）

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
- `eval_metrics.py` が主な変更対象
- `game.py` のヘルパーメソッドから呼び出す

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

- 2025-12-30: v1.0 作成（Claude Code移行対応、軽量版）
