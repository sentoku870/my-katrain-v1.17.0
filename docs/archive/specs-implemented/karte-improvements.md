`00-purpose-and-scope`（納得できる根拠、行動の変化）および `karte_sample` の現状分析に基づき、単局カルテ（Karte）の品質と信頼度を向上させるための詳細設計ドラフトを提示します。

この設計は、既存の「データの羅列」から、LLMが「コーチング」を行うための「構造化された診断書」への転換を目的とします。

---

# 機能設計書: Karte Report Extension (v2.0)

## 1. 改善案1：信頼度（Confidence）に基づく動的フィルタリング

**課題:** 現状の `karte_sample` は「信頼度: 低」と警告しつつ、不確実なデータも含めて全てのミスを表示しており、ユーザーの不信感を招いている。
**解決策:** 「信頼度が低い場合は、明白な大悪手以外を表示しない」という**Confidence Gating（信頼度によるゲート制御）**を導入し、提示する情報の確度を保証する。

### 1.1 ロジック設計 (`katrain/core/reports/confidence_filter.py`)

KataGoの訪問数（Visits）に基づき、表示するミスの閾値（Threshold）を動的に変更する。

```python
from dataclasses import dataclass

@dataclass
class ConfidenceConfig:
    min_visits: int       # 信頼に必要な最小訪問数
    display_threshold: float # 表示する損失の下限（目数）
    badge_label: str      # UI表示ラベル

class ConfidenceGater:
    def get_config(self, avg_visits: int) -> ConfidenceConfig:
        # 訪問数が少ない＝不確実＝大きなミスしか断定できない
        if avg_visits < 50:
            return ConfidenceConfig(50, 5.0, "⚠️ PRELIMINARY (Major Blunders Only)")
        # 訪問数が中程度＝悪手は断定できる
        elif avg_visits < 500:
            return ConfidenceConfig(500, 2.0, "✅ STANDARD (Mistakes & Blunders)")
        # 訪問数が多い＝細かい緩手も正確
        else:
            return ConfidenceConfig(1000, 0.5, "💎 HIGH PRECISION (All Details)")

    def filter_moves(self, moves: list, config: ConfidenceConfig):
        # 閾値以下のノイズを除去し、信頼できる指摘のみを残す
        return [m for m in moves if m.points_lost >= config.display_threshold]
```

### 1.2 出力フォーマットの変更 (`karte.md`)

ネガティブな警告文を削除し、**「現在表示されている情報は確実である」**という肯定的（Positive）なコンテキストを提供する。

```markdown
## Analysis Quality: ✅ STANDARD

_解析訪問数（Avg: 111）に基づき、2.0目以上の明確な悪手に絞って表示しています。ここにある指摘は統計的に有意です。_
```

---

## 2. 改善案2：「敗着（The Losing Move）」の特定と強調

**課題:** 現状はTop 5が並列されており、どれが勝敗を決したのか不明確である。ユーザーの認知負荷が高い。
**解決策:** 勝率（Winrate）と目数（Score）の推移から、**「勝勢から敗勢へ転落した瞬間」**または**「追いつくチャンスを逃した瞬間」**を特定し、別枠で強調する。

### 2.1 ロジック設計 (`katrain/core/analysis/losing_move_finder.py`)

`katrain/core/analysis/` に以下の判定ロジックを追加する。

```python
def identify_turning_point(game_nodes):
    losing_move = None
    max_swing = 0.0

    for node in game_nodes:
        # 勝率が 接戦(>40%) から 敗勢(<10%) へ転落したか？
        prev_wr = node.parent.analysis['winrate']
        curr_wr = node.analysis['winrate']

        wr_loss = prev_wr - curr_wr

        # クリティカルな条件:
        # 1. 元々は勝負になっていた (prev_wr > 0.4)
        # 2. この手で勝負が決まった (curr_wr < 0.2)
        # 3. 損失が大きい (wr_loss > 0.2)
        if prev_wr > 0.4 and curr_wr < 0.2 and wr_loss > max_swing:
            max_swing = wr_loss
            losing_move = node

    return losing_move
```

### 2.2 出力フォーマットの変更 (`karte.md`)

通常のリストの前に、**"The Turning Point"（本局の分岐点）** セクションを新設する。

```markdown
## 🚨 The Turning Point (本局の敗着)

**Move 124 (K13)**

- **状況**: 接戦 (勝率 48%) → 敗勢 (勝率 8%)
- **損失**: -15.2目
- **解説**: この一手が致命傷となりました。これ以前は互角の勝負でしたが、この手により右辺のグループが救出不可能となり、勝負が決まりました。
- **AI推奨手**: L18 (攻め合いに勝つ手)
```

---

## 3. 改善案3：Ownership変動の言語化（Semantic Description）

**課題:** `low_liberties` タグだけでは「具体的に何が起きたか（どの石が死んだか）」が分からず、LLMが幻覚を起こす原因になる。
**解決策:** KataGoの `Ownership`（領域支配率）データの差分を解析し、具体的な事象（石の死、地の消滅）をテキスト化して埋め込む。

### 3.1 ロジック設計 (`katrain/core/analysis/ownership_diff.py`)

`karte_report.py` 生成時に呼び出す。

```python
def describe_impact(node, prev_node):
    # Ownership配列 (-1.0 to 1.0) の差分を計算
    diff = [curr - prev for curr, prev in zip(node.ownership, prev_node.ownership)]

    # 大きな変動（符号反転など）があった座標をクラスタリング
    changed_clusters = find_clusters(diff, threshold=1.5)

    descriptions = []
    for cluster in changed_clusters:
        # 座標からエリア名（"右下隅", "天元周辺"）を取得
        area_name = get_area_name(cluster.center_coords)

        if cluster.type == "FLIP_TO_OPPONENT":
            descriptions.append(f"{area_name}の石が死にました（所有権が反転）")
        elif cluster.type == "NEUTRALIZED":
            descriptions.append(f"{area_name}の確定地が消えました")

    return "。".join(descriptions)
```

### 3.2 出力フォーマットの変更 (`karte.json` / `karte.md`)

LLMに渡すための `karte.json` および `karte.md` に `description` フィールドを追加する。

**karte.md 表示例:**

```markdown
| Move | Coord | Loss | Tags      | Semantic Impact                 |
| :--- | :---- | :--- | :-------- | :------------------------------ |
| 105  | M19   | 8.3  | `Blunder` | **上辺の黒石5個が死にました。** |
| 121  | K17   | 7.1  | `Mistake` | **右上の白地が確定しました。**  |
```

---

## 4. 統合された `karte.md` 出力イメージ

これら3つの改善を適用した、新しい単局カルテの構成です。LLMはこの情報を読むことで、より人間的で的確なアドバイスが可能になります。

```markdown
# Game Analysis: [Player] vs [Opponent]

## 1. Analysis Quality: ✅ STANDARD

_訪問数(111)に基づき、2.0目以上の確実なミスのみを表示しています。_

## 2. 🚨 The Turning Point (勝負の分かれ目)

**Move 198 (T13)**

- **Loss**: 67.7 pts (Winrate: 65% -> 1%)
- **Impact**: **右辺の白大石（約15子）が死にました。**
- **Reason**: `low_liberties` (ダメ詰まり)
- **Coach Note**: ここまでは優勢でした。この見落としさえなければ勝てた碁です。

## 3. Important Mistakes (修正すべき悪手)

_以下の手は勝敗に影響した重要なミスです。_

| #   | Move       | Loss | Type    | Detail (Impact)                                     |
| --- | ---------- | ---- | ------- | --------------------------------------------------- |
| 1   | W 160 (C7) | 10.0 | Blunder | 左下の地が大きく荒らされました。`need_connect`      |
| 2   | W 50 (P13) | 9.0  | Blunder | 上辺の攻め合いで手数を誤りました。`reading_failure` |

<!-- LLM Instruction -->
<!--
This player lost due to a specific "Life & Death" blunder at Move 198.
1. Emphasize that the game was winning until Move 198.
2. Explain the "Low Liberties" mistake at T13 implies a lack of safety check.
3. Suggest verifying the status of large groups before playing elsewhere.
-->
```

## 5. 実装ステップの優先順位

1.  **Confidence Gating (Phase 23/50適用)**: `karte_report.py` にフィルタリングロジックを追加（最優先、信頼回復のため）。
2.  **Losing Move Detection**: `eval_metrics.py` を拡張し、最大損失地点を特定するロジックを実装。
3.  **Ownership Description**: 解析エンジンのパイプラインにOwnership差分計算を追加（難易度高、Phase 7後半）。
