ご提示いただいたソース（`00-purpose-and-scope.txt`, `01-roadmap.txt`）およびこれまでの開発文脈（Phase 48のレーダーチャート、Phase 45の用語辞書）に基づき、提案1「ポジティブ・フィードバック生成機能」を**Phase 53: Style Analyzer**として実装するための詳細な仕様草案を作成しました。

この機能の核心は、**「AIが見つけた欠点（Negative Data）」を「人間の個性（Positive Identity）」に変換してLLMに伝えること**です。

---

# 仕様草案: Phase 53 - "My Style Identity" (Style Analyzer)

## 1. 概要

KataGoの解析データ（RadarMetrics, MeaningTags）に基づき、ユーザーのプレースタイルを「肯定的なアーキタイプ（原型）」として定義する。これをSummaryレポートおよびLLMプロンプトに出力し、コーチングのトーンを「欠点の指摘」から「個性の伸長」へとシフトさせる。

## 2. データ構造設計

### 2.1 新規クラス: `StyleArchetype`

`katrain/core/analysis/style/models.py` に定義。

```python
from dataclasses import dataclass
from typing import List, Dict

@dataclass(frozen=True)
class StyleArchetype:
    id: str                  # 内部ID (例: "kiai_fighter")
    name_ja: str             # 表示名 (例: "剛腕ファイター")
    name_en: str             # 表示名 (例: "The Kiai Fighter")

    # 判定ロジック用パラメータ
    required_high_axes: List[str]  # レーダーチャートで高い必要がある軸 (例: ["FIGHTING"])
    required_low_axes: List[str]   # 低くても許容（あるいは特徴となる）軸 (例: ["STABILITY"])
    dominant_tags: List[str]       # 頻出するMeaningTags (例: ["overplay", "cut"])

    # ユーザーへのフィードバック
    positive_summary: str          # 肯定的な要約文
    hero_pro: str                  # 似ているプロ棋士（イメージ）

    # Lexicon連携 (go_lexicon_master_last.yamlのID)
    related_lexicon_ids: List[str] # (例: ["kiai", "sabaki", "fight"])
```

### 2.2 アーキタイプ定義（初期セット）

既存の `RadarMetrics`（Opening, Fighting, Endgame, Stability, Awareness）の組み合わせで判定します。

| ID                      | 日本語名               | 判定ロジック (Dominant Axis)         | リフレーミング（欠点→長所）               | 関連Lexicon            |
| :---------------------- | :--------------------- | :----------------------------------- | :---------------------------------------- | :--------------------- |
| **`kiai_fighter`**      | **剛腕ファイター**     | High: `FIGHTING`<br>Low: `STABILITY` | 乱暴・自滅 → **「気合と破壊力」**         | `kiai`, `semeai`       |
| **`cosmic_architect`**  | **天空の構想家**       | High: `OPENING`<br>Low: `ENDGAME`    | 地が甘い・大風呂敷 → **「大局観と夢」**   | `moyo`, `fuseki`       |
| **`precision_machine`** | **精密機械**           | High: `ENDGAME`<br>Low: `FIGHTING`   | 消極的・戦闘回避 → **「計算と堅実」**     | `yose`, `honte`        |
| **`shinobi_survivor`**  | **シノビの達人**       | High: `STABILITY`<br>Low: `OPENING`  | 布石下手・苦しい → **「粘り腰とサバキ」** | `sabaki`, `shinogi`    |
| **`ai_native`**         | **新人類 (AI Native)** | High: `AWARENESS`<br>Low: (None)     | 機械的・味気ない → **「理知と効率」**     | `joseki`, `efficiency` |

---

## 3. ロジック設計 (`katrain/core/analysis/style/analyzer.py`)

### 3.1 判定アルゴリズム `determine_style`

Phase 48で実装された `RadarMetrics` (0.0-1.0のスコア) を入力とします。

1.  **偏差値計算:** 5軸の中で、ユーザーの平均スコアに対して「突出して高い項目 (+0.15以上)」と「低い項目」を特定する。
2.  **タグ重み付け:** Phase 46の `MeaningTags` の集計（`overplay` が多い、`endgame_loss` が多い等）を加味する。
    - 例: `FIGHTING` が高くても、`overplay` が極端に少なければ「剛腕」ではなく「精密」寄りと判定する。
3.  **マッチング:** 定義済みアーキタイプと照合し、最も適合度の高いものを返す。該当なしの場合は `balance_master` (バランス型) とする。

```python
def determine_style(radar: RadarMetrics, tag_counts: Dict[str, int]) -> StyleArchetype:
    # 1. 最もスコアが高い軸を取得
    best_axis = max(radar.axes, key=radar.axes.get)

    # 2. ルールベース判定
    if best_axis == RadarAxis.FIGHTING:
        if tag_counts.get('overplay', 0) > 3:
            return STYLES['kiai_fighter']
        return STYLES['aggressive_tactician']

    if best_axis == RadarAxis.OPENING:
        return STYLES['cosmic_architect']

    # ... (その他ロジック)

    return STYLES['balance_master']
```

---

## 4. 出力への統合仕様

### 4.1 Summary Report (`reports/summary_*.md`) への追記

`Skill Profile` セクションの直下に、**「あなたの棋風診断 (My Style Identity)」** セクションを新設します。

```markdown
## 🌀 My Style Identity: 【剛腕ファイター (The Kiai Fighter)】

> 「肉を切らせて骨を断つ。あなたの碁は、恐れを知らない気合に満ちています。」

**【スタイルの特徴】**
あなたは **Fighting (戦闘力)** のスコアが突出しています（Tier 4）。
AIの評価値が揺れ動く激しい局面でも、相手にプレッシャーを与え続ける力があります。
**Stability (安定性)** がやや低いですが、それは「リスクを恐れず勝負に行っている」証拠でもあります。

**【相性の良い概念】**

- **気合 (Kiai):** あなたの武器です。相手の緩着を咎める鋭さを持っています。
- **サバキ (Sabaki):** 攻め込まれた時に軽くかわす技術を覚えると、攻撃力がさらに輝きます。

**【憧れのプロ棋士】**

- 崔哲瀚 (Choi Cheol-han) 9段 - 「毒蛇」と呼ばれた攻撃的スタイル
```

### 4.2 LLM向けプロンプト埋め込み (`karte.md` / `coach.md`)

ここが最も重要です。LLMに対して**「このユーザーをどう扱うべきか」**というメタ指示（System Instruction）を埋め込みます。

**karte.md の末尾（非表示コメントブロック）:**

```xml
<!--
[SYSTEM INSTRUCTION: COACHING PERSONA ADAPTATION]
The user's identified style is: "Kiai Fighter" (High Fighting, Low Stability).

When giving advice, please adopt the following tone:
1. AFFIRMATION: Praise their aggressive moves and "Kiai" (fighting spirit). Do not scold them for taking risks.
2. REFRAMING: Instead of saying "Stop playing overplays", say "To make your attacks sharper, you need to prepare the shape first."
3. VOCABULARY: Use terms like "Momentum", "Pressure", and "Sabaki".
4. FOCUS: Prioritize "Life & Death" advice over "Endgame", as their games are likely decided by fights.
-->
```

---

## 5. 実装ロードマップへの配置

`01-roadmap.txt` の Phase 52 以降に以下を追加します。

### Phase 53: Style Analyzer Core

- **目的:** レーダーチャートとタグからスタイルIDを決定するロジックの実装。
- **成果物:** `core/analysis/style/` パッケージ。`StyleArchetype` 定義。ユニットテスト。
- **依存:** Phase 46 (MeaningTags), Phase 48 (Radar)。

### Phase 54: Style Integration (Summary & LLM)

- **目的:** 判定されたスタイルをMarkdownレポートとLLM用プロンプトに統合する。
- **成果物:** `summary_report.py` の改修。プロンプト生成ロジックへのスタイル情報の注入。
- **UX:** ユーザーが「自分のスタイル」を知ることで、学習のモチベーション（自己肯定感）を高める。

### Phase 55: Style-Based Kifu Recommendation (提案2の準備)

- **目的:** 判定されたスタイル（例: 剛腕ファイター）に基づいて、相性の良いプロ棋譜（例: 崔哲瀚の局）をリコメンドするデータベース接続。

---

## 6. この仕様のポイント（期待効果）

1.  **「減点法」からの脱却:**
    従来のAI解析は「ここがダメ」という減点法ですが、この機能は「ここは君の味だ」と肯定します。これは `00-purpose-and-scope.txt` にある「納得できる根拠」と「継続的な向上」に心理面から寄与します。
2.  **LLMの「コーチ人格」の安定化:**
    LLMに「このユーザーはファイターだ」と教えることで、LLMは「もっと穏やかに打ちましょう」という的外れなアドバイスを避け、「その攻撃力を活かすために、ここは引こう」という、ユーザーの性格に合った指導ができるようになります。
3.  **資産の活用:**
    既に作成済みの `go_lexicon_master_last.yaml`（気合、本手、サバキなどの定義）をフル活用し、コストを抑えて実装できます。
