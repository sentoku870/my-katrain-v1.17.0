ご提案いただいたアイデアの第3位である「Critical 3 の Context 自動充填」の実装仕様ドラフトを作成しました。

現在 `(none)` となっている箇所に、**「どこで（Area）」「何が起きているか（Situation）」** をルールベースで記述する機能を実装します。これはPhase 46で実装された `MeaningTags` のインフラを拡張し、盤面の幾何学的情報と組み合わせることで実現します。

---

# 仕様書: Phase 80-C Critical 3 コンテキスト自動生成 (Context Filler)

**作成日:** 2026-01-28
**対象:** `katrain/core/analysis/context_classifier.py` (新規), `karte_report.py`
**依存:** Phase 46 (MeaningTags), Phase 1 (EvalMetrics)

## 1. 概要

Karteの「Critical 3（重要3局面）」において、悪手の発生した状況（コンテキスト）を自動生成する。
AIやLLMに頼らず、盤面座標、石の距離、呼吸点数などの軽量な計算を用いて、**「右下隅の接近戦」「中央のサバキ」「上辺の模様消し」** といった具体的な状況説明タグを生成し、`Context: (none)` を置き換える。

## 2. データモデル

### 2.1 新規クラス: `BoardContext`

局面のコンテキスト情報を保持するデータ構造。

```python
@dataclass
class BoardContext:
    area_id: str          # "corner_br", "side_top", "center" 等
    situation_type: str   # "fight", "joseki", "invasion", "reduction", "endgame"
    stone_status: str     # "settled", "floating", "heavy", "light"

    def to_string(self, lang="jp"):
        # 言語テンプレートに基づいて結合
        # 例: "[右下隅] の [混戦] ([弱い石]の放置)"
        pass
```

## 3. ロジック・アルゴリズム

### 3.1 エリア判定 (Area Classifier)

着手座標 $(x, y)$ に基づき、盤面を9つのゾーンに分類する（19路盤基準）。

- **Corner (隅):** $(1,1)$〜$(4,4)$ およびその周辺 ($x,y \in$)
- **Side (辺):** 隅以外の第3線・第4線 ($x \in, y \in$ 等)
- **Center (中央):** 第5線以上 ($x,y \in$)

### 3.2 状況判定 (Situation Classifier)

周囲の配石状況と `MeaningTags` を組み合わせて判定する。

| 状況 (Type)                              | 判定ロジック (Heuristics)                                                                      | 出力テキスト例       |
| :--------------------------------------- | :--------------------------------------------------------------------------------------------- | :------------------- |
| **Contact Fight**<br>(接近戦/ねじり合い) | 相手の石と直接接触 (Manhattan Dist=1) しており、かつ双方の呼吸点が少ない (liberties $\le$ 3)。 | `[Area]の接近戦`     |
| **Invasion**<br>(打ち込み/侵入)          | 相手の確定地・勢力圏（Ownership > 0.8）の内部に着手し、かつ周囲に味方の石が少ない。            | `[Area]への打ち込み` |
| **Reduction**<br>(消し/削減)             | 相手の勢力圏の境界線（Ownership 0.4〜0.6）付近への着手。                                       | `[Area]の模様消し`   |
| **Joseki**<br>(定石進行)                 | 序盤 (Move < 50) かつ隅のエリアで、互いに石が隣接せず一定の距離で進行している。※簡易判定       | `[Area]の定石`       |
| **Semeai**<br>(攻め合い)                 | `MeaningTags` に `capture_race_loss` が含まれる、または相互にアタリに近い状態。                | `[Area]の攻め合い`   |
| **Connection**<br>(連絡/切断)            | `MeaningTags` に `cut` または `connect` が含まれる。                                           | `[Area]の連絡・切断` |

### 3.3 石の状態判定 (Status Classifier)

着手した石、または周囲のグループの状態を判定する。

- **Floating (浮き石):** 根拠（眼形）がなく、中央へ逃げている状態。
- **Heavy (重い石):** 石数が多いが眼形が乏しい（凝り形）。
- **Thick (厚み):** 安定しており、外側に向かっている。

## 4. インテグレーション (karte_report.py)

`Critical 3` セクションの生成時に、以下の優先順位で `Context` フィールドを埋める。

1.  **Idea #1 (Ownership Diff) の結果があれば最優先**
    - 例: `Context: 右下の大石死 (-20目)`
2.  **Idea #3 (Context Filler) の結果を結合**
    - Idea #1がない場合、または補足情報として付与。
    - 例: `Context: 右下隅の接近戦 (Contact Fight), 弱い石の放置`

### 実装イメージ (Python)

```python
def generate_context_string(node, move_eval):
    # 1. 座標からエリア名を取得
    area_name = get_area_name(move_eval.move)

    # 2. タグと周囲の状況からシチュエーションを特定
    if "capture_race" in move_eval.tags:
        situation = "攻め合い (Semeai)"
    elif is_contact_fight(node):
        situation = "混戦 (Chaos)"
    elif is_invasion(node):
        situation = "打ち込み (Invasion)"
    else:
        situation = "折衝 (Local Trade)"

    # 3. 結合して返す
    return f"{area_name}での{situation}"
```

## 5. 期待される出力例

従来の `(none)` が以下のように具体的になります。

- **Before:**
  - `Move: 115 (B) B9`
  - `Context: (none)`
- **After:**
  - `Move: 115 (B) B9`
  - `Context: 左上隅の死活 (Corner Life/Death), 攻め合い負け`

- **Before:**
  - `Move: 139 (B) F9`
  - `Context: (none)`
- **After:**
  - `Move: 139 (B) F9`
  - `Context: 左辺の混戦 (Side Fight), 連絡の不備`

## 6. 開発ステップ

1.  **Step 1:** `katrain/core/utils.py` に `get_area_name(coords)` を実装。
2.  **Step 2:** `analysis/context_classifier.py` を作成し、`is_contact_fight`, `is_invasion` 等の判定関数を実装。
3.  **Step 3:** `karte_report.py` の `_build_critical_entry` メソッド内で上記を呼び出し、文字列を生成して代入。
4.  **Step 4:** 既存の `summary` や `karte` 生成テストを実行し、エラーが出ないことを確認（Regression Test）。
