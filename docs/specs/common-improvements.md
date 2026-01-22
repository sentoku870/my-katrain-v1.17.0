`00-purpose-and-scope`（納得できる根拠、行動の変化） および `karte_sample`/`summary_sample` の現状分析に基づき、**Summary（複数局）** と **Karte（単局）** の両方に共通する根本的な課題を3つ特定し、それらを解決するための詳細な設計ドラフトを提案します。

これらは、単にデータを羅列するだけでなく、LLMが「人間のコーチ」として振る舞うために必要な「文脈（Context）」「指導（Instruction）」「視覚的意味（Semantics）」を補完する機能です。

---

# 共通機能設計書: Common Report Enhancements (v2.0)

## 1. 共通課題 A：形勢を考慮した「柔軟な評価」ロジック (Context-Aware Evaluation)

### 1.1 問題点

現在の `karte_sample` の定義（Definitions） では、目数損（Score Loss）のみで悪手を判定しています。しかし、**「優勢時の安全策（Safety Play）」と「接戦時の緩手（Slack Move）」が区別されていません**。
勝率99%の場面で2目損して安全に勝つ手は、人間的には「好手」ですが、現在のロジックでは `Inaccuracy` や `Mistake` としてタグ付けされ、学習者を混乱させます。これは「納得できる根拠」 を損なう要因です。

### 1.2 解決策：形勢連動型動的しきい値 (Dynamic Thresholding)

勝率（Winrate）の状況に応じて、悪手判定の厳しさ（Strictness）を動的に変更するロジックを導入します。

### 1.3 実装設計ドラフト (`katrain/core/analysis/eval_context.py`)

```python
from dataclasses import dataclass

@dataclass
class MoveContext:
    is_winning: bool      # 勝率 > 95%
    is_losing: bool       # 勝率 < 5%
    is_close: bool        # 勝率 40-60%
    is_complex: bool      # scoreStdev > 20.0 (難解な局面)

def classify_move_contextual(node, analysis) -> str:
    loss = node.score_loss
    wr = node.parent.analysis['winrate']

    # 1. 勝ち局面でのダンピング（厳しさを緩和）
    if wr > 0.95:
        if loss < 3.0: return "Safety_Play" # 3目以内の損は許容
        if loss > 10.0: return "Blunder"    # さすがに大損は指摘
        return "Slack"                      # その中間

    # 2. 負け局面での「勝負手」（評価値は下がるが複雑化させる手）
    if wr < 0.10 and analysis['scoreStdev'] > 25.0:
        if loss > 5.0: return "Desperate_Fight" # 暴走気味だが咎めない

    # 3. 接戦時は厳密に判定
    if 0.4 <= wr <= 0.6:
        if loss > 2.0: return "Mistake"
        if loss > 5.0: return "Blunder"

    return "Normal"
```

### 1.4 出力への反映

`karte.json` および `summary.md` に以下のタグを追加します。

- `Safety Play`: 「優勢を維持する安全な手です（AI最善手より-2.1目）」
- `Context`: LLMに対し「この手は悪手判定されていますが、勝勢なので無視して良いと伝えてください」というメタ情報を付与します。

---

## 2. 共通課題 B：LLM向け「指導プロンプト」の埋め込み (Instruction Injection)

### 2.1 問題点

現在のレポートは人間が読むことを想定した「データの羅列」であり、LLMに対して「どう振る舞うべきか」という指示が含まれていません。そのため、ユーザーが毎回「あなたはプロ棋士です。このデータを元に...」とプロンプトを入力する必要があり、「黄金ルート（添付だけで完了）」 の妨げになっています。

### 2.2 解決策：システム・インストラクションの隠し埋め込み

Markdownファイルの末尾に、HTMLコメント形式（`<!-- ... -->`）で、LLM専用の **System Instruction Block** を自動挿入します。これにより、ファイルをアップロードするだけで、LLMが自動的にコーチモードに切り替わります。

### 2.3 実装設計ドラフト (`katrain/core/reports/prompt_builder.py`)

```python
def generate_llm_instruction(player_rank: str, focus_area: str) -> str:
    """
    ランクと弱点に基づき、LLMへのメタ指示を生成する
    """
    base_prompt = f"""
<!--
[SYSTEM INSTRUCTION FOR LLM]
Role: You are a professional Go coach teaching a {player_rank} player.
Objective: Analyze the attached game data to identify ONE primary weakness.
Tone: Encouraging but analytical. Avoid generic advice; use specific move references.

[ANALYSIS GUIDELINES]
1. Focus mainly on "{focus_area}" mistakes as identified in the report.
2. If specific 'Life & Death' blunders exist, prioritize them over Endgame mistakes.
3. For 'Safety Play' tags, praise the user for maintaining the lead, even if points were lost.
4. Suggest 3 concrete actions (e.g., "Solve 5 tsumego daily").
-->
"""
    return base_prompt
```

### 2.4 出力への反映 (`karte.md` / `summary.md`)

ファイルの最下部に上記ブロックを追加します。ユーザーの目には触れず（Markdownレンダリングで消える）、LLMだけがこれを読み取って回答の質を劇的に向上させます。

---

## 3. 共通課題 C：盤面状況の「言語的」記述 (Semantic Board Description)

### 3.1 問題点

LLMは画像（盤面スクショ）がないと、「右辺の黒石」と言われても具体的な形（団子石なのか、封鎖されているのか）をイメージできません。`karte_sample` にある `coord: P13` だけでは、LLMは「P13がどんな場所か」を幻覚（Hallucination）で補完してしまうリスクがあります。「LLMの幻覚を起こしにくい入出力」 という設計原則に違反しています。

### 3.2 解決策：局所的特徴の言語化エンコーディング

KataGoのデータから、着手周辺の「意味」をテキスト化してJSON/Markdownに含めます。

### 3.3 実装設計ドラフト (`katrain/core/analysis/shape_describer.py`)

```python
def describe_move_semantics(node, board) -> dict:
    x, y = node.move

    # 1. 場所の定義 (Zone)
    if is_corner(x, y): zone = "Corner (隅)"
    elif is_side(x, y): zone = "Side (辺)"
    else: zone = "Center (中央)"

    # 2. 相対関係 (Relation)
    # 直前の相手の石に接触したか？
    if is_contact_move(node): relation = "Contact (ツケ/ハネ)"
    # 相手の石から遠いか？
    elif distance_to_nearest_stone(node) > 3: relation = "Tenuki/Large Scale (手抜き/大場)"

    # 3. 形の判定 (Shape) - 簡易パターンマッチ
    shape_quality = "Normal"
    if is_empty_triangle(board, x, y): shape_quality = "Empty Triangle (空き三角)"
    if is_dumpling_shape(board, x, y): shape_quality = "Dumpling (団子)"

    return {
        "zone": zone,
        "relation": relation,
        "shape": shape_quality,
        "description_text": f"{zone}への{relation}。形は{shape_quality}です。"
    }
```

### 3.4 出力への反映

レポート内の各悪手リストに `Context` カラムを追加します。

**karte.md 例:**
| Move | Coord | Loss | Type | **Context (状況)** |
|---|---|---|---|---|
| 50 | P13 | 9.0 | Blunder | **中央**での**接触戦**。**空き三角**の愚形になっており、効率が悪いです。 |

これにより、LLMは盤面を見なくても「50手目は中央で空き三角を打ってしまったんですね。これは形が悪く、攻め合いに弱くなります」と、驚くほど的確な解説が可能になります。

---

## 実装ロードマップへの統合

1.  **Phase 23 (カルテ品質向上)**: `Context-Aware Evaluation` (安全策の除外) を実装。ノイズを減らす。
2.  **Phase 45+ (ドキュメント/UX)**: `Instruction Injection` を実装。LLM連携のユーザー体験を完成させる。
3.  **Phase 8 (構造解析)**: `Semantic Board Description` を実装。技術的難易度が高いため、まずは「隅/辺/中央」の分類から始める。
