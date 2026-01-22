`00-purpose-and-scope`（弱点の同定と矯正を最短距離で回す） および `Common Struggles of Beginner Go Players and Potential Solutions`（Focused AI Review） に基づき、**提案4：「一点集中」レビューモード（Focused "One-Mistake" Review）** の詳細設計ドラフトを提案します。

この機能は、AIが指摘する大量のミス（Inaccuracies）によって学習者が情報過多（Cognitive Overload）に陥るのを防ぎ、勝敗に直結した「決定的な敗着」のみに焦点を絞ることで、学習効率を最大化することを目的とします。

---

# 機能設計書: 「一点集中」レビューモード (Focused Review Mode)

## 1. 目的と解決する課題

- **課題:** 既存のAI解析（KaTrain/Lizzie等）は、2目損も20目損も並列に表示するため、中級者は「どれから直せばいいか分からない」または「些末なミスに拘泥して本質的な弱点を見逃す」という問題がある。
- **目的:** 解析結果からノイズ（勝敗に影響しない緩手）を徹底的にフィルタリングし、**「この手がなければ勝てた（あるいは形勢が崩れなかった）」という最大損失の一手（The Losing Move）**、またはトップ3のミスのみを提示する。これにより、`00-purpose-and-scope` の「行動の変化」を最短距離で促す。

## 2. フィルタリングと選定ロジック

### 2.1 候補手の選定アルゴリズム（"Critical 3" Selection）

全着手の中から、以下の優先順位で「修正すべき手」を最大3つまで抽出する。

1.  **Game-Ending Blunder（敗着）:**
    - **条件:** 勝率（WinRate）が `50%` 以上（接戦・優勢）の状態から、一気に `20%` 未満（敗勢）に転落した手。
    - **意味:** 「この一手がなければ勝負はわからなかった」という決定的な瞬間。
2.  **Severe Blunder（大悪手）:**
    - **条件:** 目数損（Score Loss）が `> 5.0` 目、かつ 勝率損（Winrate Loss）が `> 15%` の手。
    - **意味:** 勝敗決定後であっても、部分的に大損害（石の頓死など）を出した手。
3.  **Missed Opportunity（勝機逃し）:**
    - **条件:** 相手の大悪手に対し、評価値を `> 10.0` 目改善できる手を逃し、互角に戻してしまった場合。

### 2.2 棋力別閾値の動的調整 (Dynamic Thresholds)

ユーザーの棋力帯（Tier）に応じて、フィルタリングの感度を調整する。

| ターゲット層         | 閾値設定 (Filter Policy)             | 表示メッセージ例                                           |
| :------------------- | :----------------------------------- | :--------------------------------------------------------- |
| **DDK (級位者)**     | `Score Loss > 10.0` 以外はすべて隠蔽 | 「細かい損は気にせず、まずは石が死なないようにしましょう」 |
| **SDK (有段者手前)** | `Score Loss > 5.0` を抽出            | 「5目以上の損は致命傷になります。ここだけ直しましょう」    |
| **Dan (有段者)**     | `Score Loss > 2.0` を抽出            | 「ヨセや手順前後による損失も確認しましょう」               |

### 2.3 除外ロジック (Noise Reduction)

以下の手は、数値上の損失が大きくても「一点集中モード」では表示しない（混乱防止のため）。

- **終局間際のダメ詰め:** ガベージタイムにおけるパスや無意味な手。
- **勝率1%未満/99%以上の局面:** 勝敗が決した後の手は、学習優先度を下げる（設定で変更可能）。

## 3. UI/UX デザイン

### 3.1 ナビゲーション：「次の致命傷へ」ボタン

通常の「次のミスへ」ボタンを置き換え、選定されたトップ3のミスだけを循環するナビゲーションを提供する。

- **ボタン:** `[ ⏮️ ]` `[ Next Critical Mistake ]` `[ ⏭️ ]`
- **挙動:** クリックすると、盤面が該当の手数までジャンプし、AI推奨手との比較図（Branch）を自動展開する。

### 3.2 グラフの「フォーカス表示」

勝率/目数差グラフにおいて、選定された「重要局面」以外の変動ポイントをグレーアウト（薄く表示）し、決定的な落下点のみを赤色で強調する。

- **視覚効果:** ユーザーが一目で「ここを見るべき」と理解できるように、グラフ上に `⚠️` アイコンや「Lose Move」ラベルをオーバーレイ表示する。

### 3.3 解説オーバーレイ (Micro-Lesson)

選定された局面に対し、AI Senseiの事例を参考に、簡潔な理由付けテンプレートを表示する。

> **Mistake #1 (Move 124)**
>
> - **損失:** -15.2目 (勝率 65% $\to$ 12%)
> - **判定:** 決定的な敗着 (Game-Ending Blunder)
> - **AIの推奨:** D16 (敵の急所)
> - **解説:** 「この手で右下の大石が死にました。D16に打っていれば生きていました。」

## 4. 実装設計（Python/KataGo Integration）

`katrain/core/analysis/` にフィルタリングクラスを追加する。

```python
@dataclass
class CriticalMistake:
    node: GameNode
    score_loss: float
    winrate_loss: float
    category: str # "Blunder", "Missed Win", etc.

class FocusedReviewFilter:
    def get_top_mistakes(self, game_nodes: List[GameNode], limit: int = 3) -> List[CriticalMistake]:
        candidates = []
        for node in game_nodes:
            if not node.analysis: continue

            # 損失取得（Phase 23のget_canonical_loss活用）
            loss = node.analysis.get('scoreLoss', 0)
            wr_loss = node.analysis.get('winrateLoss', 0)

            # フィルタリング（例: 5目以上かつ15%以上）
            if loss > 5.0 and wr_loss > 0.15:
                candidates.append(CriticalMistake(node, loss, wr_loss, "Blunder"))

        # 損失の大きい順にソートしてトップNを返す
        return sorted(candidates, key=lambda x: x.score_loss, reverse=True)[:limit]
```

## 5. LLM連携 (`karte.json` への出力)

LLM（Claude/GPT）が診断を行う際、すべての悪手を羅列するのではなく、「まずこれについて解説せよ」という指示を含める。

**karte.json 出力例:**

```json
{
  "focus_mode": {
    "primary_mistake": {
      "move_number": 124,
      "loss": 15.2,
      "reason": "Game-Ending Blunder",
      "context": "Biggest drop in winrate (53% swing)."
    },
    "secondary_mistakes": [
      { "move": 45, "loss": 8.0, "reason": "Severe Blunder" },
      { "move": 88, "loss": 6.5, "reason": "Missed Opportunity" }
    ]
  },
  "llm_instruction": "Please focus your diagnosis PRIMARILY on move 124. Explain why it was fatal and what principle was violated."
}
```

## 6. 期待される教育効果

- **認知負荷の低減:** 「直すべきは3つだけ」と提示されることで、学習者の心理的ハードルが下がり、復習（Review）の習慣化が促進される。
- **優先順位の学習:** 小さなヨセよりも、石の死活や大場などの「大きなミス」を優先して修正する感覚（大局観）が養われる。
- **「納得感」の向上:** 実際に勝敗が入れ替わった瞬間を見せつけられるため、「なぜ負けたのか」に対する納得感が高まり、行動変容（次回の修正）につながりやすい。
