ご提案いただいたアイデアの第5位、「『タグ』の自然言語化（Human-Readable Reason）」の実装仕様ドラフトを作成しました。

現状のKarteでは `Reason: low_liberties, need_connect` のように内部タグがそのまま表示されていますが、これを**「呼吸点が少なく、切断される危険がありました」**といった、コーチが語りかけるような自然な文章に変換するエンジンを設計します。

---

# 仕様書: Phase 80-E 自然言語理由生成エンジン (Reason Generator)

**作成日:** 2026-01-28
**対象:** `katrain/core/analysis/reason_generator.py` (新規), `karte_report.py`
**依存:** Phase 46 (MeaningTags)

## 1. 概要

KataGoの解析によって付与された複数の `MeaningTags`（意味タグ）を解析し、単なるタグの羅列ではなく、因果関係や優先順位を考慮した**「人間が読むための理由説明文（Human-Readable Reason）」**を生成する。
これにより、囲碁用語に詳しくないユーザーでも「なぜそれが悪手なのか」を直感的に理解できるようにする。

## 2. データモデル

### 2.1 理由テンプレート (`ReasonTemplate`)

タグの組み合わせに対応する文章テンプレートを定義する構造体。

```python
@dataclass
class ReasonTemplate:
    primary_tag: str            # メインとなるタグ (例: life_death)
    secondary_tags: Set[str]    # 組み合わせ条件 (例: {low_liberties})
    format_key: str             # i18n用のキー (例: "reason.life_death.low_liberties")
    priority: int               # 適用優先度 (高いほど優先)
```

## 3. ロジック・アルゴリズム

### 3.1 タグの階層化とフィルタリング

単純な置換ではなく、タグの**「重要度（Severity）」**と**「具体性（Specificity）」**に基づいて、最もユーザーに伝えるべき情報を選択する。

1.  **タグの分類:**
    - **Result Tags (結果):** `heavy_loss`, `small_loss`, `gote`
    - **Core Reason Tags (根本原因):** `life_death`, `connect_die`, `capture_race_loss`, `missed_kill`
    - **Shape/Tactical Tags (形・戦術):** `empty_triangle`, `atari`, `low_liberties`, `overplay`
    - **Strategic Tags (戦略):** `direction`, `slow`, `pincer`, `joseki`

2.  **優先順位ロジック:**
    - **Rule 1:** `Core Reason` があれば最優先で採用する。（「方向違い」よりも「石が死ぬ」方が重大）
    - **Rule 2:** `Core Reason` がなく、`Shape` と `Strategic` がある場合、損失が大きい (`heavy_loss`) なら `Shape`（直接的な戦闘ミス）を優先、小さければ `Strategic` を優先する。
    - **Rule 3:** `Result Tags` は単体では理由にならないため、他のタグがない場合のフォールバックとしてのみ使用する。

### 3.2 複合条件による文章生成

単一タグではなく、組み合わせによって文章を変化させる。

| Primary        | Secondary       | Output (JP Example)                                  |
| :------------- | :-------------- | :--------------------------------------------------- |
| `life_death`   | `low_liberties` | 「ダメが詰まっており、石が死ぬ形になっていました」   |
| `life_death`   | `eye_shape`     | 「眼形が不十分で、生きることができませんでした」     |
| `need_connect` | `cut`           | 「切断の弱点があり、石が分断される危険がありました」 |
| `need_connect` | `peep`          | 「ノゾキに対してツギを省略しました（薄い形）」       |
| `direction`    | `small`         | 「盤上にさらに大きな場所がありました（方向違い）」   |
| `endgame`      | `sente`         | 「先手のヨセを逃しました（手順前後）」               |

### 3.3 文脈情報の注入 (Context Injection)

Phase 80-C で実装予定の `Context` 情報がある場合、それをテンプレートに埋め込む。

- **Template:** `{context}において、{reason}`
- **Result:** 「右下隅の攻め合いにおいて、ダメが詰まっており石が取られました」

## 4. 実装詳細

### 4.1 新規モジュール: `katrain/core/analysis/reason_generator.py`

```python
class ReasonGenerator:
    def __init__(self):
        self.templates = self._load_templates()

    def generate(self, move_eval: MoveEval, context: str = None) -> str:
        tags = set(move_eval.meaning_tags)

        # 1. 最も優先度の高いテンプレートを検索
        best_template = None
        for template in self.templates:
            if template.primary_tag in tags:
                # サブタグ条件の合致を確認
                if template.secondary_tags.issubset(tags):
                    if best_template is None or template.priority > best_template.priority:
                        best_template = template

        # 2. i18nキーからテキストを取得
        if best_template:
            reason_text = i18n.get(best_template.format_key)
        else:
            # フォールバック: 最も重いタグを単独で翻訳
            reason_text = self._fallback_reason(tags)

        return reason_text
```

### 4.2 i18n リソースの拡張 (`katrain/i18n/locales/jp/katrain.po`)

既存の単語翻訳に加え、説明的な文章を追加する。

```po
msgid "reason.life_death.low_liberties"
msgstr "呼吸点が少なく、攻め合いで負ける形でした"

msgid "reason.connect.cut"
msgstr "切断される弱点を放置しました"

msgid "reason.direction.overconcentrated"
msgstr "石が密集しすぎており、効率の悪い形（凝り形）です"

msgid "reason.shape.empty_triangle"
msgstr "空き三角（愚形）になっており、石の効率が悪いです"
```

## 5. 出力への反映

### Karte / Summary

`Reason` 列の内容を、生成された自然言語に置き換える。

- **Before:**
  - `Move 125: Loss 8.2`
  - `Reason: low_liberties, need_connect`
- **After:**
  - `Move 125: Loss 8.2`
  - `Reason: 呼吸点が少なく、切断されて石が取られる危険がありました`

## 6. 開発ステップ

1.  **Step 1:** `MeaningTags` の全リストを洗い出し、優先順位マトリクスを作成。
2.  **Step 2:** `reason_generator.py` のロジック実装。
3.  **Step 3:** 主要なタグ組み合わせに対する i18n テキスト（日/英）の作成。
4.  **Step 4:** `karte_report.py` から `ReasonGenerator` を呼び出し、CSV/Markdown出力に反映。

## 7. 期待される効果

- **可読性の向上:** 専門用語（タグ）を知らないユーザーでも、ミスの原因を文章として理解できる。
- **学習効果:** 「Low Liberties」というタグを見るより、「呼吸点が少ない」と説明される方が、次の対局での意識付け（アタリの確認など）につながりやすい。
