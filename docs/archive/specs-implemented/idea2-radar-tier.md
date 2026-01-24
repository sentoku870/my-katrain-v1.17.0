`00-purpose-and-scope`（カルテ品質の向上）および、新規提供資料「IGQE囲碁能力評価システム調査報告」に基づき、提案2「5軸レーダーチャートとTier判定」の具体的な設計ドラフトを提案します。

この機能は、勝敗（Win/Loss）ではなく、着手の質（Quality of Play）を5つの側面から定量化し、LLMが「あなたの弱点は戦闘力です」と具体的根拠を持って指摘するための基盤データを作成します。

---

# 機能設計書: 5軸スキルレーダー＆Tier判定モジュール (Skill Radar & Tier Assessment)

## 1. 目的と概要

KataGoの解析データ（目数損、分散、一致率）を用い、プレイヤーの棋力を単一のランク（段級位）ではなく、5つの構成要素（序盤・中盤・終盤・安定性・感性）に分解して可視化する。
これにより、ユーザーは「自分はどこが弱いのか」を直感的に把握でき、LLMは`summary.md`や`karte.json`を通じて、数値的根拠に基づいた弱点克服カリキュラムを提案可能になる。

## 2. 5つの評価軸定義 (The 5 Dimensions)

「IGQE囲碁能力評価システム調査報告」 および 「トップアマの壁」 の分析に基づき、以下の5軸を設定する。

| 軸 (Axis)     | 英語名        | 定義・抽出ロジック                                                    | 評価対象となる手                                                  |
| :------------ | :------------ | :-------------------------------------------------------------------- | :---------------------------------------------------------------- |
| **1. 序盤力** | **Opening**   | 布石の構想力、方向感覚。<br>序盤における平均損失（APL）。             | 手数 $1 \sim 50$ の着手<br>(定石DBにある手を除く)                 |
| **2. 戦闘力** | **Fighting**  | 難解な局面での対応力。<br>「複雑な局面」における平均損失。            | `scoreStdev` (評価値分散) $> 15.0$ の局面<br>(＝読みが必要な混戦) |
| **3. 終盤力** | **Endgame**   | ヨセの精密さ。<br>終盤における平均損失。                              | 手数 $150 \sim$ 終局<br>(かつ `scoreLead` 変動がある手)           |
| **4. 安定性** | **Stability** | 大悪手を打たない堅実さ。<br>「大悪手（Blunder）」の発生頻度の低さ。   | 全手番。<br>損失 $> 5.0$ 目 または 勝率損 $> 20\%$ の逆数         |
| **5. 感性**   | **Awareness** | AI（または高段者）との感覚の一致。<br>最善手（Blue Spot）との一致率。 | 全手番。<br>Top-1 一致率 (%)                                      |

## 3. Tier（階級）判定ロジック

商標リスクを回避しつつ、一般的な段級位とリンクさせるため、独自の「Tier 1〜5」定義を採用する。「IGQE調査報告」 のAPL（平均目数損）基準をベースに設定する。

### 3.1 基準値テーブル (Baseline Table)

各軸のスコア（APL等）を以下の基準で `1.0` 〜 `5.0` のTierスコアに変換する。

| Tier       | 名称                  | 目安棋力             | 基準APL (目/手) | 安定性 (悪手率) | 一致率 (Blue%) |
| :--------- | :-------------------- | :------------------- | :-------------- | :-------------- | :------------- |
| **Tier 5** | **Elite (精鋭)**      | 五段〜 (High Dan)    | $< 0.4$         | $< 1\%$         | $> 55\%$       |
| **Tier 4** | **Advanced (上級)**   | 初段〜四段 (Low Dan) | $0.4 - 0.8$     | $< 3\%$         | $45 - 55\%$    |
| **Tier 3** | **Proficient (熟練)** | 1級〜5級 (SDK)       | $0.8 - 1.2$     | $< 5\%$         | $35 - 45\%$    |
| **Tier 2** | **Apprentice (習得)** | 6級〜14級 (DDK)      | $1.2 - 2.0$     | $< 10\%$        | $25 - 35\%$    |
| **Tier 1** | **Novice (初学)**     | 15級以下             | $> 2.0$         | $> 10\%$        | $< 25\%$       |

### 3.2 補正ロジック (Adjustments)

単純な平均値ではノイズが入るため、以下の補正を行う。

- **ガベージタイム除外:** 勝率が99%以上または1%未満の局面での「安全策（緩手）」は、損失としてカウントしない（ダンピング処理）。
- **一択局面の除外:** AIの候補手が1つしかない（他が極端に悪い）局面での一致は、「感性」のスコアに含めない（当たり前の手であるため）。

## 4. 実装イメージ (Python Class Design)

`katrain/core/analysis/skill_radar.py` として実装。

```python
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class RadarMetrics:
    opening_score: float  # 1.0-5.0
    fighting_score: float
    endgame_score: float
    stability_score: float
    awareness_score: float
    estimated_tier: str   # "Tier 3 (Proficient)"

class SkillEvaluator:
    def evaluate(self, nodes: List[GameNode]) -> RadarMetrics:
        # 1. データ抽出
        opening_moves = [n for n in nodes if n.move_number <= 50]
        fighting_moves = [n for n in nodes if n.analysis['scoreStdev'] > 15.0]
        endgame_moves = [n for n in nodes if n.move_number >= 150]

        # 2. APL計算 (Average Point Loss)
        apl_opening = self._calc_apl(opening_moves)
        apl_fighting = self._calc_apl(fighting_moves)
        apl_endgame = self._calc_apl(endgame_moves)

        # 3. 安定性・一致率計算
        blunder_rate = self._calc_blunder_rate(nodes)
        match_rate = self._calc_match_rate(nodes)

        # 4. スコア変換 (Mapping APL to 1.0-5.0 Scale)
        return RadarMetrics(
            opening_score=self._map_apl_to_tier(apl_opening),
            fighting_score=self._map_apl_to_tier(apl_fighting),
            endgame_score=self._map_apl_to_tier(apl_endgame),
            stability_score=self._map_rate_to_tier(blunder_rate, inverse=True),
            awareness_score=self._map_rate_to_tier(match_rate, inverse=False),
            estimated_tier=self._determine_overall_tier(...)
        )

    def _calc_apl(self, moves):
        # ガベージタイム除去などのロジックを含む
        valid_moves = [m for m in moves if not self._is_garbage_time(m)]
        if not valid_moves: return 0.0
        return sum(m.points_lost for m in valid_moves) / len(valid_moves)
```

## 5. 出力とLLM連携 (Output Integration)

### 5.1 JSON出力 (`karte.json`)

LLMが診断材料として使うための生データ形式。

```json
{
  "skill_assessment": {
    "overall_tier": "Tier 3",
    "radar": {
      "opening": 4.2, // Tier 4相当（得意）
      "fighting": 2.5, // Tier 2相当（弱点）
      "endgame": 3.0,
      "stability": 2.8,
      "awareness": 3.5
    },
    "weakness_analysis": {
      "primary_issue": "Fighting",
      "description": "High point loss in complex positions (stdev > 15)."
    }
  }
}
```

### 5.2 ユーザー向け表示 (`summary.md` / UI)

- **レーダーチャート:** 5角形のグラフを描画（`matplotlib` または KivyのCanvas命令）。
- **LLMプロンプトへの注入:**
  > 「このユーザーは**序盤力がTier 4**と高いですが、**戦闘力がTier 2**と低く、難解な局面で崩れる傾向があります。このデータに基づき、戦闘力を強化するためのアドバイスと練習メニューを提案してください。」

## 6. 期待される効果

- **「万年五段」の打破:** 中級者が陥りやすい「得意な序盤ばかり勉強して、苦手な戦闘から逃げる」といった偏りを、数値（戦闘力スコアの低さ）として客観的に突きつけることができる。
- **LLM診断の質向上:** LLMが「もっと慎重に打ちましょう」という精神論ではなく、「中盤の複雑な局面（分散大）での悪手率が高いので、詰碁と手筋を重点的にやりましょう」という**具体的な処方箋**を出せるようになる。
