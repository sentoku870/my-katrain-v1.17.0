`00-purpose-and-scope`（目的：納得できる根拠、行動の変化）および `01-roadmap`（Phase 7: カルテ品質向上）、さらに追加資料である「IGQE調査報告」「KataGo解析から教育的フィードバック生成」に基づき、**複数局まとめ（Summary）** の品質と信頼度を向上させるための詳細設計ドラフトを提示します。

---

# 機能設計書: Summary Report Extension (v2.0)

## 1. 目的

現在の `summary.md` は統計データの羅列に留まっており、「ユーザーが次に何をすべきか」という行動指針（Actionable Insight）が不明確である。
本設計では、**「5軸レーダーチャート」「意味的診断」「相対評価」** の3要素を導入し、LLMが具体的かつ説得力のあるコーチングを行うための構造化データを提供する。

---

## 改善案 1：5軸スキルレーダー指標の導入 (The 5-Axis Skill Radar)

### 1.1 概要

対局全体の平均損失（APL）だけでなく、局面の性質ごとにパフォーマンスを分解し、IGQEモデルに基づく5つの軸で「棋力の偏り」を数値化する。

### 1.2 データ定義と算出ロジック

`katrain/core/batch/stats.py` に以下の集計ロジックを追加する。

| 評価軸 (Metric)              | 定義 (Definition)    | 算出ロジック (Calculation)                           | 備考                                           |
| :--------------------------- | :------------------- | :--------------------------------------------------- | :--------------------------------------------- |
| **1. 序盤力**<br>(Opening)   | 布石の構想力         | 手数 1〜50 における平均損失 (APL)                    | 定石DBにある手は除外（純粋な構想力を測るため） |
| **2. 戦闘力**<br>(Fighting)  | 難解な局面での対応力 | `scoreStdev` (評価値分散) $> 15.0$ の局面におけるAPL | 分散が大きい＝読みが必要な混戦                 |
| **3. 終盤力**<br>(Endgame)   | ヨセの精密さ         | 手数 150以降 におけるAPL                             | ガベージタイム（勝率99%以上での着手）を除く    |
| **4. 安定性**<br>(Stability) | 大悪手の少なさ       | `100 - (Blunder率 % * 係数)`                         | Blunder: 損失>5目 または 勝率損>20%            |
| **5. 感性**<br>(Awareness)   | 第一感の良さ         | AI推奨手（Blue Spot）との一致率 (%)                  | 探索初期（Policy）の一致率を使用               |

### 1.3 出力フォーマット

Markdownのテーブルとして出力し、LLMが「あなたの戦闘力はTier 2レベルです」と解釈できるようにする。

```markdown
## Skill Radar (5-Axis)

| Axis     | Value (Avg Loss) | Estimated Tier          | Description                      |
| :------- | :--------------- | :---------------------- | :------------------------------- |
| Opening  | 0.45 pts         | Tier 4 (Advanced)       | 定石理解は十分です。             |
| Fighting | 2.10 pts         | **Tier 2 (Apprentice)** | **混戦で崩れる傾向があります。** |
| ...      | ...              | ...                     | ...                              |
```

---

## 改善案 2：ミス傾向の「意味的」自動診断 (Semantic Diagnosis)

### 2.1 概要

従来の「タグ集計（low_liberties: 26回）」という現象報告から、**「なぜそのミスが起きたのか」** という原因仮説（メタタグ）を生成する。複数のタグとフェーズの組み合わせ（クロス集計）からパターンを特定する。

### 2.2 診断ロジック（ヒューリスティック）

`katrain/core/reports/summary_report.py` に診断エンジンを実装する。

| 診断名 (Diagnosis)                               | 発生条件 (Trigger Condition)                                                | LLMへの指示 (Instruction)                                                                                          |
| :----------------------------------------------- | :-------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------- |
| **接近戦の読み不足**<br>(Close Combat Blindness) | Phase=`Middle` かつ<br>(`low_liberties` + `need_connect`) が全ミスの40%以上 | 「石が接触した際の『アタリ』や『切断』の読みが甘いです。詰碁で『ダメの数』を意識する練習を提案してください。」     |
| **方向違いの布石**<br>(Direction Error)          | Phase=`Opening` かつ<br>AIとの着手距離 $>10$ のミスが頻発                   | 「局所的な形にとらわれ、大場（広い場所）を見逃しています。盤全体を見る『手抜き』のタイミングを指導してください。」 |
| **ヨセの雑さ**<br>(Sloppy Endgame)               | Phase=`Endgame` かつ<br>損失 2.0〜5.0 のミスが多い                          | 「勝勢時の油断、または計算不足が見られます。先手・後手の価値判断を強化する提案をしてください。」                   |
| **過剰防衛**<br>(Over-Defense)                   | 勝率 $>90\%$ 時にパスに近い手（損失 $\approx 1$目）が多い                   | 「優勢時に不要な手入れをして差を詰められています。地を数える（整地）自信をつける指導が必要です。」                 |

---

## 改善案 3：棋力別「許容範囲」との相対評価 (Relative Tier Assessment)

### 3.1 概要

ユーザーの自己申告段位（例：4段）に対し、統計的な基準値（ベースライン）と比較して「実力が伴っているか」を客観的に評価する。

### 3.2 基準値テーブル (Baseline Table)

IGQE調査報告およびKataGo解析データに基づき、各ランク帯の標準的なスタッツを定義する。

| ランク帯             | 基準APL (目/手) | 許容Blunder率 |
| :------------------- | :-------------- | :------------ |
| **High Dan (5d-7d)** | < 0.4           | < 1.0%        |
| **Low Dan (1d-4d)**  | 0.4 - 0.8       | < 3.0%        |
| **SDK (1k-9k)**      | 0.8 - 1.5       | < 8.0%        |
| **DDK (10k-)**       | > 1.5           | > 10.0%       |

### 3.3 出力セクション設計

`summary.md` に **Relative Performance** セクションを追加する。

```markdown
## Relative Performance (Target: 4 Dan)

- **Average Loss**: 1.36 pts (Target: 0.4 - 0.8) -> **Underperforming (Tier 2 Level)**
- **Blunder Rate**: 5.4% (Target: < 3.0%) -> **Unstable**
- **Evaluation**: 申告段位（4段）に対し、特に「戦闘（Fighting）」における損失が大きく、実質的なパフォーマンスは **1級〜初段 (Tier 3)** 相当です。基礎的な読みの精度を上げることで、急速な改善が見込めます。
```

---

## 4. 統合された `summary.md` の出力イメージ (Draft)

上記の改善を反映した、新しいサマリーレポートの構造案です。

```markdown
# Player Summary: 仙得 (v2.0)

... (既存のMeta情報) ...

## 1. Skill Radar & Tier Assessment

_あなたの棋力を5つの軸で分析しました。_

| Axis          | Score | Tier Assessment         | Context                                              |
| :------------ | :---- | :---------------------- | :--------------------------------------------------- |
| **Opening**   | 0.31  | **Tier 5 (Elite)**      | 序盤の構想は非常に高段者レベルです。                 |
| **Fighting**  | 1.82  | **Tier 2 (Apprentice)** | ⚠️ **主要な弱点です。** 混戦で大きく損をしています。 |
| **Endgame**   | 1.02  | Tier 3 (Proficient)     | 平均的です。                                         |
| **Stability** | 5.4%  | Tier 3 (Unstable)       | 大悪手(Blunder)の頻度が4段平均(3.0%)より高いです。   |
| **Awareness** | 42%   | Tier 3 (Proficient)     | AIとの感覚一致率は標準的です。                       |

## 2. Weakness Diagnosis (Why you lost)

_ミス傾向から推測される根本原因（仮説）です。_

### 🚨 Diagnosis: Close Combat Reading Issue (接近戦の読み不足)

- **根拠**: Middle Gameにおける損失が突出しており、そのうち **38.8%** が `low_liberties`（呼吸点不足）、**25.4%** が `need_connect`（連絡不備）によるものです。
- **現象**: 石が接触した戦いにおいて、自分の石のダメが詰まっていることに気づかず、取られるケースが多発しています。
- **推奨**: 「3手〜5手の読み」を確実にする詰碁トレーニングが必要です。

## 3. Top 3 Fatal Moves (The Losing Moves)

_勝敗を分けた決定的な3手です。ここを直すだけで勝率が変わります。_

1. **[Game 3] Move 198 (T13)**: Loss 67.7 pts (Blunder)
   - **Reason**: 典型的な「死活の見落とし」です。Ownershipが反転しました。
2. **[Game 3] Move 200 (H10)**: Loss 33.2 pts (Blunder)
   - **Reason**: 救出不能な石を助けようとして被害を拡大しました（サンクコスト）。
3. **[Game 2] Move 172 (F8)**: Loss 11.1 pts (Blunder)
   - **Reason**: 相手の切断の狙いを見落としました。

<!-- LLM Instruction Block -->
<!--
Please act as a Go Coach for a 4-dan player.
Based on the data above:
1. Acknowledge their strong Opening (Tier 5).
2. Point out that their Fighting (Tier 2) is the bottleneck preventing them from reaching 5-dan.
3. Explain that "Low Liberties" mistakes imply a lack of reading precision in close combat.
4. Prescribe a specific training menu: "Solve 10 Life & Death problems daily, focusing on cutting/connecting shapes."
-->
```

## 5. 実装へのステップ

1.  **`eval_metrics.py` 拡張**: 5軸（Opening, Fighting等）のAPL算出ロジックを追加。
2.  **`summary_report.py` 改修**: タグのクロス集計から「Diagnosis」を生成するルールベースロジックを実装。
3.  **Tier基準値の実装**: `constants.py` にランク別APL基準テーブルを定義。
4.  **Prompt Injection**: Markdown末尾にLLM向けの隠しインストラクションを自動挿入する機能を追加。
