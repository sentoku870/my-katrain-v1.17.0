提供された`00-purpose-and-scope.txt`、`01-roadmap.txt`、および背景資料（特に『トップアマの壁』や『KataGo解析から教育的フィードバック生成』）に基づき、**Phase 58: Risk/Reward Alignments（形勢判断・リスク管理チェッカー）** の仕様草案を作成しました。

この機能は、単に「最善手か否か」ではなく、**「その局面の形勢（優勢/劣勢）に対して、適切なリスクテイク（安全策/勝負手）を選択できたか」** を評価するものです。これは野狐有段者が最も苦手とする「勝ちきり」と「逆転術」に直結します。

---

# 仕様草案: Phase 58 - "Risk/Reward Alignments" (形勢判断・リスク管理)

## 1. 概要 (Concept)

KataGoが出力する `Winrate`（勝率）だけでなく、**`ScoreLead`（目数差）** と **`ScoreStdev`（スコアの標準偏差＝局面の紛れ/複雑さ）** を組み合わせ、プレイヤーが「形勢に応じた適切な打ち回し（ギアチェンジ）」ができているかを診断する。

- **優勢時:** 「勝ちを確定させる手堅い手（本手）」を評価し、「無用な乱戦」を警告する。
- **劣勢時:** 「紛れを求める手（勝負手）」を評価し、「安易な妥協（安楽死）」を警告する。

## 2. データ構造設計 (Data Model)

### 2.1 `RiskContext` (リスク評価コンテキスト)

各着手に対し、以下のメタデータを計算・付与する。

```python
@dataclass(frozen=True)
class RiskContext:
    move_number: int

    # 局面状況 (Before Move)
    winrate_start: float      # 直前の勝率 (例: 0.95)
    score_lead_start: float   # 直前のリード目数 (例: +15.5)

    # 着手の性質 (Action)
    score_loss: float         # 悪手度
    delta_stdev: float        # 局面の複雑化度（Stdevの変化量）
                              # 正なら「紛れ」を作った、負なら「局面を単純化」した

    # 診断結果
    judgment_type: str        # 'WINNING', 'LOSING', 'CLOSE'
    risk_behavior: str        # 'SOLID', 'RECKLESS', 'RESIGNED', 'COMPLICATING'
    is_strategy_mismatch: bool # 形勢と行動が矛盾しているか（例：必勝なのに暴走）
```

## 3. ロジック設計 (Core Logic)

### 3.1 状況判定ロジック (`SituationAnalyzer`)

現在の形勢を3つのフェーズに分類する。

1.  **Winning (必勝態勢):** `Winrate` > 90% かつ `ScoreLead` > 10.0目
2.  **Losing (敗勢):** `Winrate` < 20% かつ `ScoreLead` < -10.0目
3.  **Close (接戦):** 上記以外

### 3.2 行動評価アルゴリズム (`StrategyEvaluator`)

状況と着手の性質（`ScoreStdev`の変化）を突き合わせる。

#### A. 優勢時の評価：「勝ち運搬 (Winning a Won Game)」

- **Good (勝ちきり):**
  - `delta_stdev` < 0 (局面を単純化した)
  - かつ `score_loss` < 2.0 (大きな損はしていない)
  - **評価:** 「素晴らしい**本手 (Honte)** です。紛れを消して勝利に近づきました。」
- **Bad (暴走/Overplay):**
  - `delta_stdev` > 2.0 (局面を複雑化した)
  - または、リスクのある手で `winrate` を5%以上落とした。
  - **評価:** 「**過剰な攻め (Reckless)** です。優勢なので、これほどリスクを取る必要はありませんでした。」

#### B. 劣勢時の評価：「勝負手 (Complicating)」

- **Good (勝負手):**
  - `delta_stdev` > 0 (局面を複雑化した)
  - かつ、`score_loss` は大きくても `winrate` が少しでも残る手。
  - **評価:** 「**勝負手 (Shobu-te)** です。形勢は苦しいですが、相手に間違えるチャンスを与えています。」
- **Bad (安楽死/Resignation Mode):**
  - `delta_stdev` < 0 (局面を単純化した)
  - かつ `score_lead` が改善していない。
  - **評価:** 「**安易な妥協**です。これではそのまま負けてしまいます。もっと激しく打つべきでした。」

---

## 4. 出力への統合 (Report Integration)

### 4.1 カルテ (`karte.md`) への「勝負術」セクション追加

ミスの指摘だけでなく、**「形勢判断の良し悪し」** を評価する項目を追加。

```markdown
## ⚖️ Game Management (勝負術診断)

**【形勢判断の傾向】**

- **優勢時の振る舞い:** ⚠️ **Risk Taker (遊びすぎ)**
  - リードしてからも平均して局面を複雑化させています（Stdev上昇）。「勝っている時は安全に」を意識しましょう。
- **劣勢時の振る舞い:** ✅ **Fighter (粘り腰)**
  - 苦しい局面で最も複雑な変化（勝負手）を選べています。

**【ハイライト局面】**

- **Move 124:** 🛡️ **Excellent Simplication (決め手)**
  - AI最善手（1目得）ではありませんが、変化の余地を消した「厚い手」です。この手で勝利が確定しました。
- **Move 88:** 💣 **Unnecessary Risk (暴走)**
  - 勝率95%でしたが、無理な切断を狙って逆転の隙を与えました。ここは「我慢」が正解でした。
```

### 4.2 LLM向けプロンプト拡張 (`coach.md`)

LLMに対して、スコアだけでなく**「文脈（Context）」**を理解させるための情報を注入する。

**プロンプト追加例:**

```text
[CONTEXT: RISK MANAGEMENT]
Move 88:
- Situation: User was WINNING (Lead +15.5).
- User Move: Played a complex cut (Stdev increased). Loss -2.0 pts.
- Analysis: This was strategically poor. The user should have played safely.
- Instruction: Scold the user for taking unnecessary risks when ahead. Use the proverb "A rich man shouldn't pick quarrels."
```

---

## 5. ロードマップへの配置

`01-roadmap.txt` の Phase 52 以降、Phase 57（Pacing & Tilt）の次に配置します。

### Phase 58: Risk/Reward Logic Core

- **目的:** `ScoreStdev` (標準偏差) を解析パイプラインから確実に取得し、上記ロジックを実装する。
- **実装:** `core/analysis/risk_analyzer.py`
- **依存:** `ScoreStdev` はKataGoの解析設定で出力可能（`includeScoreStdev: true`）。

### Phase 58.5: Strategy Reporting

- **目的:** サマリーとカルテに「勝負術」セクションを追加し、LLMに渡すコンテキストを生成する。

この機能により、myKatrainは単なる「正解手検索機」から、**「勝負の流れを教える参謀」**へと進化し、特に5段の壁（形勢判断の壁）に挑むユーザーにとって強力な武器となります。
