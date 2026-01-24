`00-purpose-and-scope`（カルテ品質向上・弱点克服）および `KataGo人間らしい挙動設定調査`（Human-SLモデルの活用）に基づき、**提案5：Human-SL活用「次の一手」一致率クイズ（Style Matching Quiz）** の詳細設計ドラフトを提案します。

この機能は、従来の「AIの最善手（Blue Spot）を当てる」クイズではなく、**「高段者（人間）ならどう打つか（筋・形・直感）」**を当てることに主眼を置いたトレーニングモードです。「AIの手は人間離れしていて理解できない」という中級者の不満を解消し、実戦的な「筋の良さ」を養います。

---

# 機能設計書: Human-SL活用「次の一手」スタイル一致クイズ (Style Matching Quiz)

## 1. 目的と解決する課題

- **課題:** 既存のAIクイズは、人間には不可能な読みや独特な感覚に基づく「AI最善手」を正解とするため、中級者が「なぜそうなるのか」を直感的に理解しにくく、学習モチベーションが低下しやすい。
- **目的:** KataGo Human-SLモデルを用いて「人間の高段者（9d）の第一感」を正解基準とすることで、**「人間として自然で、かつ筋の良い手」**を学習させる。これにより、整った形や手筋の感覚（Shape Sense）を強化する。

## 2. コア・ロジックと判定基準

### 2.1 エンジン構成

- **推論モデル:** `b18c384nbt-humanv0.bin.gz` (Human-SL) と 標準モデル（b18/b28）のハイブリッド構成。
- **Human-SL設定:** `humanSLProfile = rank_9d` （または `proyear_2020`）。
  - これにより、アマチュア高段者〜プロレベルの「人間の着手分布」を予測させる。

### 2.2 判定アルゴリズム (The "Style" Scoring)

ユーザーが選んだ手（`UserMove`）に対し、以下の2軸で評価を行う。

1.  **人間一致度 (Human Prob):** Human-SLモデルが出力する `Policy` 値（その手を人間が選ぶ確率）。
2.  **客観的品質 (AI Loss):** 標準モデルが出力する `Score Loss`（目数損）。

| カテゴリ                     | 判定条件                                                      | フィードバック例                                                       | スコア               |
| :--------------------------- | :------------------------------------------------------------ | :--------------------------------------------------------------------- | :------------------- |
| **達人の手 (Master's Move)** | Human Policy **高** (Top 3) <br> AND Loss **低** (< 1.0目)    | 「お見事！プロ感覚の一手です。形も良く、損もありません。」             | **100点**            |
| **AIの鬼手 (AI Move)**       | Human Policy **低** (圏外) <br> AND Loss **ゼロ** (最善)      | 「AI級の鋭い手です！人間には盲点ですが、実は最強手です。」             | **120点** (ボーナス) |
| **筋が良い (Good Style)**    | Human Policy **高** (Top 3) <br> AND Loss **中** (1.0〜3.0目) | 「筋が良い手です。AI的には少し損ですが、人間同士なら十分通用します。」 | **80点**             |
| **俗筋・悪手 (Bad Style)**   | Human Policy **低** <br> AND Loss **大** (> 3.0目)            | 「形が悪く、損な手です。もっと自然な流れを探しましょう。」             | **0点**              |

## 3. 機能詳細とUI/UX

### 3.1 クイズ出題モード

対局後の解析、またはSGFライブラリから「次の一手」問題として出題する。

- **問題の選定:**
  - Human-SLのPolicy分布のエントロピーが低い（＝高段者なら意見が一致する「常識的な手」がある）局面を優先的に抽出。
  - 難解すぎる（Policyが割れている）局面は除外する。
- **ヒント機能:**
  - **「高段者の分布を見る」ボタン:** 盤面上にHuman-SLのPolicyヒートマップ（人間が打ちそうな場所）を薄く表示する。AIのBlue Spotとは異なる分布が見えることが教育的ポイント。

### 3.2 「感覚」レーダーチャートへの反映

このクイズの結果は、提案2の「5軸レーダーチャート」における**「感性 (Awareness)」**および**「基礎 (Shape/Style)」**のスコアとして蓄積する。

- AI一致率が低くても、Human-SL一致率が高ければ「筋は良い（あとは読みの精度）」と診断できる。

## 4. 実装設計ドラフト (Python/Pseudo-code)

`katrain/core/quiz/style_quiz.py` として実装。

```python
@dataclass
class StyleEvaluation:
    move: str
    human_policy: float  # Human-SLによる予測確率
    human_rank: int      # Human-SL候補手の中での順位
    ai_loss: float       # 標準モデルによる損失
    category: str        # "Master", "GoodStyle", "AI", "Bad"

class StyleQuizEngine:
    def __init__(self, katago_engine):
        self.engine = katago_engine

    def evaluate_user_move(self, board_state, user_move) -> StyleEvaluation:
        # 1. Human-SLモデルで解析 (Profile: rank_9d)
        human_analysis = self.engine.analyze_human_sl(
            board_state, profile="rank_9d"
        )
        # 2. 標準モデルで解析 (Loss計算用)
        ai_analysis = self.engine.analyze_standard(board_state)

        # 3. データ抽出
        h_policy = human_analysis.policy.get(user_move, 0.0)
        h_rank = human_analysis.policy_ranking.get(user_move, 999)
        loss = ai_analysis.score_loss.get(user_move, 0.0)

        # 4. カテゴリ判定
        if h_rank <= 3 and loss < 1.0:
            cat = "Master"
        elif h_rank > 10 and loss < 0.5:
            cat = "AI" # 人間が選ばないが最善
        elif h_rank <= 3 and loss < 3.0:
            cat = "GoodStyle"
        else:
            cat = "Bad"

        return StyleEvaluation(user_move, h_policy, h_rank, loss, cat)
```

## 5. 期待される教育効果

- **「AIアレルギー」の克服:** 「AIの言うことは絶対だが理解できない」というストレスから解放され、「人間の達人を目指す」という馴染みやすい目標設定が可能になる。
- **第一感の矯正:** 繰り返しプレイすることで、理屈抜きで「良い形」が目に馴染み、実戦での着手スピードと質が向上する（中韓の「早碁トレーニング」に近い効果を、より質の高いフィードバック付きで実現）。
- **自分の棋風の客観化:** 「あなたはAIタイプ（損はないが変な手）です」や「あなたは昭和のプロタイプ（形は良いが少し緩い）です」といった、ユニークな診断が可能になる。
