ご提案いただいたアイデアの第2位である「難解度（Complexity）フィルタ」の実装仕様ドラフトを作成しました。

この機能は、Phase 12 で導入された「局面難易度（DifficultyMetrics）」を拡張し、Phase 6.5 で整備された評価指標（`eval_metrics.py`）に「理不尽な指摘の除外ロジック」を組み込むものです。

---

# 仕様書: Phase 80-B 難解度（Complexity）フィルタによるノイズ除去

**作成日:** 2026-01-28
**対象:** `katrain/core/analysis/complexity.py` (新規), `eval_metrics.py`, `karte_report.py`

## 1. 概要

KataGoの解析データ（スコア標準偏差、Policy分布）を用いて局面の「複雑性（Complexity）」と「混沌度（Chaos）」を数値化する。
人間には制御不能な難解局面や、AIですら評価が揺れ動く局面での損失を「悪手（Blunder）」としてカウントせず、「難解（Complicated）」または「不運（Unlucky）」として分類し直すことで、カルテの納得感と信頼性を向上させる。

## 2. データモデル拡張

### 2.1 新規メトリクス: `ComplexityMetrics`

既存の `DifficultyMetrics` (Phase 12) は「次の一手を見つける難しさ」に焦点を当てていたが、今回は「局面そのものの不安定さ」を定義する。

```python
@dataclass
class ComplexityMetrics:
    # 1. スコア変動リスク (Chaos)
    # KataGoの scoreStdev (推定目数差の標準偏差)
    # 値が高い(>20.0)ほど、一手の違いで結果が激変する「混沌とした」状態。
    score_stdev: float

    # 2. 候補手の分散 (Branching Factor)
    # Policyの上位N手の確率は分散しているか？
    # エントロピーが高いほど「正解が絞りきれない（人間には難しい）」局面。
    policy_entropy: float

    # 3. 読みの深さによる評価変動 (Volatility)
    # 探索初期(visits=10)と完了時(visits=max)で評価値が大きく変わったか。
    # AIでも読み間違える局面は、人間には「理不尽」な難易度である。
    visit_volatility: float
```

### 2.2 評価分類の拡張 (`MistakeSeverity`)

`eval_metrics.py` のミス分類に新しい区分を追加、またはタグを付与する。

- **Existing:** `Good`, `Inaccuracy`, `Mistake`, `Blunder`
- **New Tag:** `Forgiven` (免責)
  - 本来は `Blunder` 相当の損失だが、局面の複雑性が高すぎるため、教育的指導の対象から除外されたもの。

## 3. フィルタリング・アルゴリズム

### 3.1 「理不尽度」の判定ロジック

以下の条件のいずれかを満たす場合、その局面は「人間には制御困難（High Complexity）」と判定する。

1.  **カオス判定 (Chaos Criterion):**
    - `scoreStdev > 20.0` (目数差の標準偏差が20目以上)
    - 意味: 巨大なコウ争い、あるいは盤全体が生死に関わる巨大な攻め合い中。AIですら読みきれていない可能性がある。

2.  **不確実性判定 (Uncertainty Criterion):**
    - `winrate` が `40% - 60%` の範囲で、かつ `scoreStdev > 15.0`
    - 意味: 勝負どころのねじり合い。ここでのミスは「悪手」というより「勝負のアヤ」。

3.  **AI迷い判定 (AI Confusion Criterion):**
    - `visit_volatility > 20%` (勝率が読みの過程で20%以上乱高下)
    - 意味: AIも最初分かっていなかった手。人間にそれを求めるのは酷（理不尽）。

### 3.2 減点緩和処理 (Severity Downgrade)

High Complexityと判定された局面でのミスに対し、以下の補正を行う。

- **損失（Loss）の割引:**
  - `Adjusted Loss = Raw Loss * 0.5`
  - 例: 10目の損をしたが、超難解局面だったため、評価上は5目の損（Mistake級）として扱う。
- **Blunderの除外:**
  - 補正後も `Blunder` 判定となる場合でも、Karteの「Critical 3（重要3局面）」からは**強制的に除外**する。
  - 理由: 復習しても再現性が低く、学習効果が薄いため。

## 4. 出力への反映 (Karte / Summary)

### 4.1 Karte (詳細レポート)

`karte_report.py` を修正し、緩和されたミスには注釈を入れる。

- **表示例:**
  - `Move 125: K10`
  - `Loss: 15.2目`
  - `Eval: 難解局面 (Chaos)` **← NEW**
  - `Note: 非常に難解な戦いのため、AI評価も揺れています。このミスは気にしすぎないでください。`

### 4.2 Summary (全体サマリー)

統計データ（Blunder数など）を集計する際、`Forgiven` フラグのついたミスを別枠で集計する。

- **Weakness Hypothesis (弱点仮説):**
  - 「中盤で悪手が多いですが、そのうち3回は**『難解なコウ争い』**によるものです。基礎的なミスは少ないため、悲観する必要はありません。」
  - このように、統計ノイズを除去して「本当の弱点」だけを指摘する。

## 5. 実装ステップ

この機能は、Phase 6.5 で確立された `eval_metrics.py` の基盤の上に実装する。

1.  **Step 1:** `analysis/complexity.py` を作成し、`scoreStdev` 等を抽出するヘルパー関数を実装。
2.  **Step 2:** `eval_metrics.py` の `MoveEval` クラスに `complexity` プロパティを追加。
3.  **Step 3:** `get_mistake_category` 関数内に「減点緩和ロジック」を注入。
4.  **Step 4:** `karte_report.py` および `batch/stats.py` を更新し、除外されたミスが「練習の優先順位」に上がらないようにフィルタリング。

## 6. 期待される効果

- **信頼性向上:** 「AIは厳しすぎて人間味がない」という不満（Phase 3の課題）を解消。
- **学習効率:** 再現性の低い「事故」のようなミスを無視し、修正可能な「単純ミス（アタリの見逃し等）」に集中できるようになる。これは「00-purpose-and-scope.md」の『弱点の同定と矯正を最短距離で回す』という目的に合致する。
