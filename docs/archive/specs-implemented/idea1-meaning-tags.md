`00-purpose-and-scope` の「カルテ品質の向上」および `01-roadmap` の Phase 7（カルテ品質向上）に基づき、提案1「ミスの『意味』自動タグ付け機能」の具体的な設計ドラフトを提案します。

この機能は、KataGoの数値データ（勝率・目数・Policy・Ownership）を「囲碁教育的な意味」に変換する翻訳レイヤーとして動作し、最終的にLLMが「あなたは死活のミスが多いです」といった具体的診断を行うための根拠データを提供します。

---

# 機能設計書: ミスの「意味」自動分類モジュール (Heuristic Mistake Classifier)

## 1. 目的と概要

KataGoの解析結果（Raw Data）から、ミスの性質を分類するセマンティック・タグ（Semantic Tags）を自動生成する。これにより、数値（「5目損」）だけでなく、言語的意味（「死活の見落とし」「方向違い」）をカルテに付与し、LLMによる診断精度とユーザーの納得感を飛躍的に向上させる。

## 2. 入力データ要件

KataGo Analysis Engineから以下のデータを取得・算出する。

| データ項目     | 変数名        | 説明                             | 教育的用途                 |
| :------------- | :------------ | :------------------------------- | :------------------------- |
| **目数損**     | `scoreLoss`   | 最善手との目数差                 | ミスの深刻度判定（基本）   |
| **勝率損**     | `winrateLoss` | 最善手との勝率差                 | 勝敗分岐点の判定           |
| **候補手確率** | `policy`      | その手に対するAIの推奨度         | 「形」の良悪、盲点の判定   |
| **所有権変動** | `ownFlux`     | 直前の局面とのOwnership差分総量  | 死活（石の生死）の判定     |
| **着手距離**   | `distance`    | 最善手と実戦手のマンハッタン距離 | 「方向違い」の判定         |
| **標準偏差**   | `scoreStdev`  | 目数予測のばらつき               | 局面の難解さ・混戦度の判定 |

## 3. 分類ロジック（ヒューリスティック定義）

以下の優先順位でタグ判定を行い、最も合致するカテゴリを付与する（マルチタグ可）。

### 3.1 タグ：`LIFE_DEATH`（死活・石の頓死）

石の生死が入れ替わるミスは、中級者にとって最も致命的かつ修正効果が高い。

- **判定ロジック:**
  - `scoreLoss` > 8.0 （大きな損失）
  - `ownFlux` > 15.0 （盤面上で15ポイント以上の所有権変動＝約7-8個以上の石の生死が反転）
  - **補足:** 特定の石のクラスタのOwnership符号が反転（1.0 $\to$ -1.0）した場合を検出。
- **LLMへの指示:** 「石の生死に関わる重大なミスです。詰碁の練習を推奨します。」

### 3.2 タグ：`BAD_SHAPE`（愚形・悪形）

AIが「形としてありえない」と判断する手。中級者が陥りやすい「空き三角」や「無意味なアタリ」など。

- **判定ロジック:**
  - `scoreLoss` > 2.0 （明確な損）
  - `policy` < 0.01% （AIの候補手分布において極めて確率が低い＝プロの感覚にない手）
  - **除外条件:** `ownFlux` が大きい場合（死活が絡む例外手を除く）
- **LLMへの指示:** 「石の効率が悪い『愚形』の可能性があります。手筋や形の基本を見直しましょう。」

### 3.3 タグ：`WRONG_DIRECTION`（方向違い）

局所的には打てる手だが、大局的に見て打つ場所が間違っているケース。

- **判定ロジック:**
  - `policy` > 0.1% （AIもゼロではないと認識している＝局所的にはあり得る）
  - `distance` > 10 （AIの最善手と盤上で10路以上離れている）
  - `moveNumber` < 60 （序盤・布石段階）
- **LLMへの指示:** 「局所的には悪くないですが、盤面全体を見て広い場所へ向かう『大局観』が必要です。」

### 3.4 タグ：`OVERPLAY`（打ち過ぎ・無理手）

形勢を一気に悪くするリスクの高い手。AIが「混戦（分散大）」と判断する状況で損をした場合。

- **判定ロジック:**
  - `scoreLoss` > 5.0
  - `scoreStdev` > 20.0 （AIも結果予測がばらつく難解な局面）
  - **文脈:** 自分が劣勢（`winrate` < 40%）でないのに打った場合。
- **LLMへの指示:** 「リスクが高すぎる『打ち過ぎ』です。もう少し手厚く打ち、相手のミスを待つ姿勢も重要です。」

### 3.5 タグ：`YOSE_ERROR`（ヨセの損）

終盤における計算ミス。中級者が軽視しがちなポイント。

- **判定ロジック:**
  - `moveNumber` > 150 （終盤）
  - `scoreLoss` 2.0 〜 5.0 （小さな損）
  - `isSente` 判定（AIが手抜きを推奨しているのに受けた場合など＝後手を引いた）
- **LLMへの指示:** 「終盤の細かい損です。先手・後手の価値判断（ヨセの計算）を強化しましょう。」

## 4. 実装イメージ（Python/Pseudo-code）

`analysis/mistake_classifier.py` として実装し、`Karte` 生成時に呼び出す。

```python
from enum import Enum
from dataclasses import dataclass

class MistakeType(Enum):
    LIFE_DEATH = "Life_and_Death"     # 死活
    BAD_SHAPE = "Bad_Shape"           # 愚形
    WRONG_DIRECTION = "Wrong_Direction" # 方向違い
    OVERPLAY = "Overplay"             # 打ち過ぎ
    YOSE_ERROR = "Endgame_Loss"       # ヨセ
    READING_ERROR = "Reading_Error"   # 読み抜け（Policy高いがLoss大）
    UNKNOWN = "General_Mistake"       # その他

@dataclass
class MistakeAnalysis:
    move_number: int
    score_loss: float
    tags: list[MistakeType]

def classify_move(node, prev_node, analysis_data) -> list[MistakeType]:
    tags = []
    loss = node.score_loss
    policy = node.policy_score

    # Ownership変動量の計算（簡易版）
    own_flux = sum(abs(node.ownership[i] - prev_node.ownership[i]) for i in range(361))

    # 距離の計算
    dist = calculate_manhattan_distance(node.move, analysis_data.top_move)

    # 1. 死活判定
    if loss > 8.0 and own_flux > 15.0:
        tags.append(MistakeType.LIFE_DEATH)
        return tags # 死活は最優先

    # 2. 愚形判定
    if loss > 2.0 and policy < 0.0001:
        tags.append(MistakeType.BAD_SHAPE)

    # 3. 方向違い判定（序盤）
    if node.move_number < 60 and dist > 10 and loss > 3.0:
        tags.append(MistakeType.WRONG_DIRECTION)

    # 4. 読み抜け（AIの第一感が外れた＝罠にかかった）
    if policy > 0.1 and loss > 5.0:
        tags.append(MistakeType.READING_ERROR)

    # ... 他のロジック

    if not tags and loss > 2.0:
        tags.append(MistakeType.UNKNOWN)

    return tags
```

## 5. 出力フォーマット（Markdown/JSON）

LLM（Claude/GPT）に渡す `karte.md` または `karte.json` にタグを含める。

**karte.json の例:**

```json
{
  "mistakes": [
    {
      "move": 45,
      "coords": "D4",
      "loss": 12.5,
      "tags": ["Life_and_Death"],
      "description": "Right bottom group ownership flipped (-1.0 to 1.0)."
    },
    {
      "move": 23,
      "coords": "K10",
      "loss": 4.2,
      "tags": ["Wrong_Direction"],
      "description": "Played center, AI preferred corner (Q16)."
    }
  ]
}
```

## 6. 期待される効果

この設計により、LLMは「12.5目損しました」という無味乾燥な指摘ではなく、**「45手目の右下で死活の見落としがありました。これが敗着です」**や**「23手目は方向違いです。もっと広い隅を意識しましょう」**といった、人間のコーチに近い文脈を持ったアドバイスを生成可能になります。これはロードマップPhase 7（カルテ品質向上）の目標である「納得感のある根拠」を強力にサポートします。
