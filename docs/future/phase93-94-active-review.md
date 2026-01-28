ご提案いただいたアイデアの中で、最も学習効果への影響力が高い**「Active Review（能動的検討）モード」**の仕様ドラフトを作成しました。

この機能は、従来の「AIの評価値を眺めるだけの受動的学習」を脱却し、学習科学で最も効果が高いとされる**「Active Recall（能動的想起）」**と**「即時フィードバック」**をシステム化するものです。既存の解析基盤（Phase 1, 46, 68）をフル活用し、Pythonコードによるロジック拡張を中心に実装します。

---

# 仕様書: Phase 81 Active Review Mode (Next Move Prediction)

**作成日:** 2026-01-29
**対象:** `katrain/core/study/active_review.py` (新規), `gui/features/play_mode.py`
**依存:** Phase 68 (Command Pattern), Phase 46 (MeaningTags), Phase 1 (EvalMetrics)

## 1. 概要

ユーザーが棋譜（SGF）を再生する際、AIの評価値や次の一手を隠蔽し、**「自分ならどこに打つか」**を予測させるモード。
ユーザーが着手した瞬間に、裏で待機していたKataGoの解析結果（Policy/ScoreLoss）と照合し、即座に「正解（Blue Spot）」「好手（Green Spot）」「疑問手（Te-loss）」などの判定と、具体的な点数（Score）をフィードバックする。

## 2. データモデル

### 2.1 予測評価クラス: `GuessEvaluation`

ユーザーの着手を評価するためのデータ構造。既存の `MoveEval` をラップして判定ロジックを追加する。

```python
class GuessGrade(Enum):
    PERFECT = "Perfect"       # AI最善手 (Blue Spot)
    EXCELLENT = "Excellent"   # 損失 < 0.5目 または Policy上位
    GOOD = "Good"             # 損失 < 2.0目 (許容範囲)
    INTERESTING = "Interesting" # 損失はあるが、Policy値が高い (人間らしい手)
    SLACK = "Slack"           # 緩手 (2.0 < 損失 < 5.0)
    BLUNDER = "Blunder"       # 悪手 (損失 > 5.0)

@dataclass
class GuessEvaluation:
    user_move: Move
    ai_best_move: Move
    score_loss: float         # 最善手との目数差
    policy_rank: int          # AI候補手の中での順位 (1位, 2位...)
    grade: GuessGrade
    feedback_text: str        # ユーザーへの表示メッセージ

    # オプション: 元の棋譜との一致判定
    matches_game_move: bool   # 実際の対局者と同じ手を打ったか
```

## 3. ロジック・アルゴリズム

### 3.1 評価判定ロジック (Grading Logic)

`eval_metrics.py` の基準をベースに、ユーザーのランク設定（Phase 4.5）に応じて閾値を動的に調整する。

1.  **解析リクエスト:**
    - ユーザーが考える前に、バックグラウンドで `EngineCommand` (Phase 68) を発行し、現在局面の解析を完了させておく。
2.  **着手比較:**
    - ユーザーの手 $(x, y)$ の `score_loss` と `policy_prob` を取得。
3.  **グレード判定 (例: 初段設定の場合):**
    - `score_loss <= 0.5`: **PERFECT** (神の一手)
    - `score_loss <= 2.0`: **GOOD** (ナイスショット)
    - `score_loss > 5.0`: **BLUNDER** (問題手)
    - **特例:** `score_loss` が大きくても、`policy` が高い（AIも迷う、あるいは人間的に自然な）手は **INTERESTING** と判定し、厳しく咎めない。

### 3.2 ゲーム化要素 (Gamification)

学習継続率を高めるため、単純な正誤判定に加え「スコア」を付与する。

- **Move Score:** `max(0, 100 - (score_loss * 10))`
  - 最善手なら100点、1目損するごとに10点減点。
- **Combo Bonus:** 連続正解（Good以上）でエフェクト変化。

## 4. UI/UX デザイン

### 4.1 モード切替

- 既存の「再生/検討タブ」に **「Active Review」スイッチ** を追加。
- ONにすると、以下の変化が発生する：
  - **Fog of War:** 盤面上のAIヒント（色付きドット）、勝率グラフ、次の一手表示が全て非表示になる。
  - **Input Ready:** 盤面クリックが「石を置く」ではなく「回答する」アクションになる。

### 4.2 フィードバック・ループ (Interaction)

1.  **Think:** ユーザーが盤面を見て次の一手をクリック。
2.  **Judge:** クリックした場所に仮石を置き、評価判定を実行。
3.  **Feedback (Instant):**
    - **Good以上:** 緑色のエフェクト＋「Excellent! (0.2目損)」のポップアップ。自動的に次の手に進む設定も可。
    - **Blunder:** 赤色のエフェクト＋「Miss... (-6.5目)」の表示。
      - **Retry:** 「もう一度考えますか？それとも正解を見ますか？」の選択肢を表示。
      - **Hint:** `MeaningTags` (Phase 46) を活用し、「ヒント: 右辺の連絡が薄いです」といったテキストヒントを出す。

### 4.3 振り返りサマリー

セッション終了後、以下のようなレポートを表示する。

- **一致率:** AI最善手との一致率、実際の棋譜との一致率。
- **平均損失:** あなたの着手の平均損失目数（APL）。
- **Weakness:** 「ヨセでの損失が目立ちました」「攻めが急ぎすぎでした」等の傾向指摘（Phase 80-Dのロジック流用）。

## 5. 実装計画

### Step 1: バックエンドロジック (`core/study`)

- `ActiveReviewer` クラスを作成。
- `katrain` インスタンスから `last_analysis` を取得し、ユーザーの手と照合するメソッド `evaluate_guess(move)` を実装。

### Step 2: GUI統合 (`gui/features`)

- `PlayMode` を拡張し、`active_review_mode` フラグを追加。
- `on_touch_down` イベントをフックし、モードON時は石を置かずに `evaluate_guess` を呼び出す。
- 評価結果のポップアップ表示（Kivyの `Popup` またはオーバーレイ）。

### Step 3: ヒント機能の強化

- Phase 46 の `MeaningTags` と連携。
- ユーザーが間違えた際、正解手のタグ（例: `defend_cut`）を参照し、「切断を防ぐ手が必要です」と自然言語でヒントを出す（Phase 80-Eの簡易版）。

## 6. 期待される学習効果

- **能動的学習:** 「漫然と眺める」ことが不可能になるため、一局の学習密度が劇的に向上する。
- **メタ認知の強化:** 「自分はここだと思ったが、AIはここだった」というギャップ（予測誤差）を毎手認識することで、自分の思考の癖（Bias）を修正できる。
- **モチベーション:** 「100点満点中何点だったか」が即座に出るため、ゲーム感覚で棋譜並べが可能になる。

---

### 補足：既存機能との整合性

この機能は、Phase 68で導入された `Command Pattern` により、UIスレッドをブロックせずに裏で解析を走らせることが容易になっているため、スムーズな実装が可能です。また、Phase 4.5 の「棋力別プリセット」設定を流用することで、「初級者には甘く、高段者には厳しく」採点するロジックも即座に実現できます。
