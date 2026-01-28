ご提案いただいたアイデアの中で最も優先度が高い「Ownership変動によるミスの結末（Consequence）の明示」について、既存のデータ構造（`eval_metrics.py`, `karte_report.py` 等）との整合性を考慮した**仕様ドラフト**を作成しました。

この機能は、これまで「なぜ悪手なのか」が数値（Loss）とタグ（low_liberties）でしか表現されていなかったKarteに対し、**「右下の大石が死にました（-25目）」** という具体的な**意味（Semantics）**を付与するものです。

---

# 仕様書: Phase 80-A Ownership変動によるConsequence（結末）判定

**作成日:** 2026-01-28
**対象:** `katrain/core/analysis/ownership.py` (新規), `karte_report.py`

## 1. 概要

KataGoの `ownership`（領地所有確率 -1.0〜1.0）ヒートマップの「着手前後の差分（Delta）」を解析し、スコア損失の具体的な**物理的内訳（Physical Breakdown）**を特定する。
これにより、Karteの `Context` 欄に「大石死」「荒らし成功」「ヨセの手止まり」といった具体的な事象を自動記述する。

## 2. データモデル

### 2.1 新規クラス: `OwnershipDiff`

着手 $t-1$ と $t$ のOwnership比較データを保持する。

```python
@dataclass
class OwnershipDiff:
    move_number: int
    # 差分ヒートマップ (Current - Previous * perspective)
    # 値の範囲: -2.0 (自分の地が相手の地に反転) 〜 +2.0 (相手の地を奪取)
    diff_grid: List[float]

    # 検出された主要な変動エリアのリスト
    consequences: List['Consequence']
```

### 2.2 新規クラス: `Consequence`

特定された「結末」の定義。

```python
class ConsequenceType(Enum):
    GROUP_DEATH = "group_death"       # 自分の石が死んだ
    MISSED_KILL = "missed_kill"       # 相手の石を殺し損ねた
    TERRITORY_LOSS = "territory_loss" # 確定地が荒らされた
    GROUP_LIFE = "group_life"         # （好手）石が生きた/シノギ
    TERRITORY_GAIN = "territory_gain" # （好手）地が増えた

@dataclass
class Consequence:
    type: ConsequenceType
    score_drop: float         # この事象による推定損失（目数）
    area_code: str            # "Q16", "Upper Right" 等のエリア識別子
    stone_count: int          # 関与した石の数（大石かどうかの判定用）
    description: str          # 生成された説明文
```

## 3. ロジック・アルゴリズム

### 3.1 差分計算とクラスタリング (Clustering)

単純な差分ではなく、意味のある「塊」として抽出する。

1.  **差分計算:**
    - $O_{t-1}$ (着手前) と $O_t$ (着手後) のOwnershipを取得。
    - 手番視点で正規化し、差分 $\Delta = O_t - O_{t-1}$ を計算。
    - 悪手の場合、$\Delta$ は負の値（支配権の喪失）となる領域が発生する。

2.  **閾値フィルタリング:**
    - ノイズ除去のため、変動幅 $|\delta| > 0.4$ （支配権が40%以上変動）の地点のみを抽出。

3.  **領域連結 (Connected Components):**
    - 隣接する変動地点をグルーピングし、「変動クラスタ」を作成する。
    - 例: 右下隅でまとめて15箇所が反転していれば、1つのクラスタとする。

### 3.2 事象分類ロジック (Classifier)

抽出されたクラスタの特性に基づき分類を行う。

| 分類 (Type)                       | 判定条件 (Heuristics)                                                                                            | 意味                                                               |
| :-------------------------------- | :--------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------- |
| **Group Death**<br>(頓死)         | クラスタ内に**自分の石**が含まれており、<br>かつ Ownership が $+1.0 \to -1.0$ (黒地から白地) へ急変。            | 生きていた石が死んだ。<br>（最も深刻な悪手）                       |
| **Missed Kill**<br>(仕留め損ない) | クラスタ内に**相手の石**が含まれており、<br>かつ Ownership が $+1.0 \to -1.0$ (自分の地になるはずが相手の地に)。 | 殺せたはずの石に生きられた。<br>(読み抜け)                         |
| **Territory Loss**<br>(地荒れ)    | クラスタ内に石を含まず(空点のみ)、<br>Ownership が $+1.0 \to 0.0$ または $-1.0$ へ変動。                         | 確定地だと思っていた場所に入り込まれた。<br>または模様が消された。 |
| **Semeai Loss**<br>(攻め合い負け) | 変動前の Ownership が $0.0$ (中立/セキ) 付近で、<br>変動後に $-1.0$ へ急変。                                     | 攻め合いやコウ争いに負けて取られた。                               |

## 4. 出力フォーマット (Karteへの統合)

`karte_report.py` の `Critical 3` および `Important Moves` セクションの `Context` フィールドを以下のように生成する。

### テンプレート (日本語)

- **Group Death:** `「{area}」で{count}子の石が死亡 (-{loss}目)`
  - 例: 「右下隅」で12子の石が死亡 (-24.5目)
- **Missed Kill:** `「{area}」の相手の大石を仕留め損ない (-{loss}目)`
  - 例: 「左辺」の相手の大石を仕留め損ない (-15.0目)
- **Territory Loss:** `「{area}」の地が大きく荒らされました (-{loss}目)`
  - 例: 「天元付近」の地が大きく荒らされました (-8.0目)

### テンプレート (英語 - i18n対応)

- **Group Death:** `Death of {count} stones in {area} (-{loss} pts)`
- **Missed Kill:** `Missed opportunity to kill group in {area} (-{loss} pts)`
- **Territory Loss:** `Loss of territory in {area} (-{loss} pts)`

## 5. 実装計画 (Implementation Plan)

### Step 1: `analysis/ownership.py` の実装

- `compute_ownership_diff(node_prev, node_curr)` 関数の実装。
- 既存の `analysis/core.py` から呼び出せるようにする。
- **依存関係:** `scipy` (ndimage.label用) または `skimage` が必要だが、Kivy環境への影響を避けるため、シンプルな **Union-Find** アルゴリズムまたは **BFS** をPython標準ライブラリで自作実装することを推奨（依存ライブラリを増やさない）。

### Step 2: `MeaningTags` との統合

- 既存の `MeaningTags` (Phase 46) と連携させる。
- 例: `low_liberties` タグがあり、かつ `Group Death` が検出された場合 → 「アタリの見逃しによる頓死」と判定精度を強化できる。

### Step 3: レポート出力の改修

- `karte_report.py` 内で `Context` が `(none)` の場合、この `Consequence` 情報を優先的に埋め込む処理を追加。

## 6. 期待される効果 (Outcome)

- **ユーザー体験:** 「Loss: 20目」と言われるだけでは分からなかったミスが、「右下の石が死んだ」と指摘されることで、一目で理解可能になる。
- **LLM連携:** LLMに渡すプロンプトに「右下の石が死にました」という情報を付与できるため、LLMが「なぜ死んだのか（眼が無かった、ダメ詰まりだった）」を解説しやすくなり、ハルシネーション（幻覚）が減る。

---

### 技術的補足: 座標のエリア名変換

座標 $(x, y)$ を「右下隅」「天元」「左辺」等の自然言語に変換するヘルパー関数 `get_area_name(x, y)` は、`katrain/core/utils.py` 等に配置し、i18n対応とする。

- **Corner (隅):** 3x3, 4x4 周辺
- **Side (辺):** 端から3-4線かつ隅以外
- **Center (中央):** それ以外
