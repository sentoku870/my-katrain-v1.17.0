ご提案いただいたアイデアの第4位、「Summaryにおける再発パターン（Recurring Patterns）の特定」の仕様ドラフトを作成しました。

現状のSummary（Phase 7）では「Phase × Mistake」の単純なクロス集計表しかありませんが、この機能は**「どの場所で」「どのような状況下で」「どんなミスを繰り返しているか」**という**複合条件（Compound Conditions）**を特定し、ユーザーの「悪癖」を言語化するものです。

---

# 仕様書: Phase 80-D 再発パターン特定 (Recurring Pattern Mining)

**作成日:** 2026-01-28
**対象:** `katrain/core/batch/stats/pattern_miner.py` (新規), `summary_report.py`
**依存:** Phase 46 (MeaningTags), Phase 80-C (Context/Area)

## 1. 概要

複数局の解析データ（Batch Result）を横断し、単なるタグの集計ではなく、**属性の組み合わせ（Tuple）**の頻度分析を行う。
これにより、「中盤のミスが多い」という漠然とした指摘ではなく、**「中盤(Middle)に、辺(Side)で、連絡(Connection)を見落として、大石が死ぬ(Group Death)」**という具体的な**負けパターン（Losing Script）**を特定し、Summaryの「Weakness Hypothesis」を具体的根拠に基づいて書き換える。

## 2. データモデル

### 2.1 パターン署名 (`MistakeSignature`)

1つのミスを構成する要素をタプル化する。

```python
@dataclass(frozen=True)
class MistakeSignature:
    phase: str          # "opening", "middle", "endgame"
    area: str           # "corner", "side", "center" (Phase 80-Cの成果物)
    primary_tag: str    # "need_connect", "life_death", "overplay" (MeaningTags)
    severity: str       # "blunder", "mistake"

    # オプション: Phase 80-AのConsequenceがあれば追加
    consequence: Optional[str] = None # "group_death", "ignored_urgent"
```

### 2.2 パターンクラスター (`PatternCluster`)

類似したミスの集合体。

```python
@dataclass
class PatternCluster:
    signature: MistakeSignature
    count: int                  # 発生回数
    total_loss: float           # 累積損失目数
    game_refs: List[str]        # 発生したゲームID/ファイル名のリスト

    @property
    def impact_score(self) -> float:
        # 重要度スコア = 損失総量 * 頻度ボーナス
        return self.total_loss * (1.0 + 0.1 * self.count)
```

## 3. ロジック・アルゴリズム

### 3.1 頻出パターンマイニング (Apriori-lite)

複雑な機械学習は使わず、決定論的なグルーピングを行う。

1.  **抽出 (Extraction):**
    - バッチ内の全ゲームの `MoveEval` から、損失が `Mistake` (2.5目) 以上の着手を抽出。
    - 各着手を `MistakeSignature` に変換する。
      - 例: `(Middle, Side, need_connect, Blunder)`

2.  **集約 (Aggregation):**
    - Signatureごとに `count` と `total_loss` を加算。
    - `count >= 2` （最低2回以上発生）のものを候補とする。

3.  **ランキング (Ranking):**
    - `impact_score` でソートし、Top 3 のパターンを特定する。
    - **フィルタリング:** 「中盤のミス」のような広すぎるカテゴリが上位に来た場合、より具体的な「中盤・辺・連絡ミス」等のサブカテゴリがあればそちらを優先表示するロジックを組む。

### 3.2 自然言語生成 (Description Generator)

特定されたSignatureを、「00-purpose-and-scope.md」にあるような**コーチング言語**に変換する。

- **Template:**
  - `{Phase}の{Area}において、「{Tag}」による{Severity}が{Count}回発生しています（計-{Loss}目）。`
- **Example:**
  - `signature`: `(Middle, Center, overplay, Blunder)`
  - **Output:** 「中盤の中央戦において、『過剰な攻め（Overplay）』による大悪手が3局中5回発生しています（計-45.2目）。」

## 4. Summaryレポートへの統合

`summary.md` の **Weakness Hypothesis** セクションを、統計的推測から「パターン指摘」へアップグレードする。

### Before (現状)

> **Weakness Hypothesis**
>
> - Middle game shows highest average loss.
> - High mistake rate in Fighting.

### After (実装後)

> **⚠️ 特定された悪癖パターン (Identified Recurring Patterns)**
>
> 複数局の分析から、以下の具体的な負けパターンが検出されました：
>
> 1.  **中盤の「連絡見逃し」 (Impact: 高)**
>     - **状況:** 辺(Side)の混戦、特に石が接触している時。
>     - **頻度:** 3局中 4回発生 (計 -52.0目)
>     - **傾向:** 相手に切断される手を放置し、両方の石が弱くなるケースが目立ちます。
>     - **参照:** Game A (Move 125), Game B (Move 88)
> 2.  **終盤の「先手逃し」 (Impact: 中)**
>     - **状況:** ヨセ(Endgame)、価値の低い後手打ち。
>     - **頻度:** 3局中 6回発生 (計 -15.5目)
>     - **傾向:** 先手を取れる場所があるのに、後手の手を打って主導権を渡しています。

## 5. 開発ステップ

この機能は、Phase 80-C (Area判定) と Phase 80-A (Consequence判定) のデータを利用するため、それらの後に実装する。

1.  **Step 1:** `katrain/core/batch/stats/pattern_miner.py` を作成し、`MistakeSignature` 生成ロジックを実装。
2.  **Step 2:** `batch/stats/aggregation.py` に `analyze_patterns(games)` 関数を追加し、全ゲームからシグネチャを集計する処理を記述。
3.  **Step 3:** `summary_report.py` のレンダリングロジックを修正し、上位パターンをMarkdown化するテンプレートを追加。
4.  **Step 4:** テストケースとして、意図的に同じミス（例：アタリ放置）を繰り返したSGFセットを用意し、正しく「アタリ放置癖」が検出されるか検証する。

## 6. 期待される効果

- **納得感の向上:** 「あなたは中盤が弱い」と言われるよりも、「辺で切断を見落とす癖がある」と言われた方が、ユーザーは具体的行動（切断の確認）に移りやすい。
- **コーチングの質の向上:** これは「00-purpose-and-scope.md」の『弱点の同定と矯正を最短距離で回す』という目的に合致し、LLMに渡す際の「診断材料」としても極めて高品質なテキストとなる。
