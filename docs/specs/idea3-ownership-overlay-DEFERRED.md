`00-purpose-and-scope`（目的：弱点の同定と矯正）および `01-roadmap`（Phase 23以降のカルテ品質向上、または将来的なPhase 12+の難易度可視化）の文脈に基づき、**提案3：「死活・地合いの『危険度』可視化オーバーレイ」** の詳細設計ドラフトを提案します。

この機能は、単に「地」を表示するのではなく、**「確定していない（＝危険な）場所」**や**「無駄な手入れ」**を視覚的に警告することで、中級者が陥りやすい「死活の見落とし」や「過剰防衛（手入れ）」を矯正することを目的とします。

---

# 機能設計書: Ownership Volatility Overlay（危険度可視化レイヤー）

## 1. 目的と解決する課題

- **課題:** 中級者（初段〜五段）は、石の生死（Life & Death）や地の確定度を「雰囲気」で判断しがちである。「まだ死んでいない石を放置する（頓死）」や「既に生きている石に手入れをする（1目損）」が停滞の主要因となっている,。
- **目的:** KataGoの `Ownership`（領域支配率）データの「曖昧さ」や「変動」を可視化することで、**「ここは戦場である（手抜き厳禁）」**または**「ここは終戦している（手入れ不要）」**という判断基準を直感的に提供する。

## 2. 技術的アプローチ：データソース

KataGo Analysis Engineが出力する以下のデータを活用する,。

1.  **Ownership ($O_{xy}$):** 各交点の支配率（-1.0〜+1.0）。
    - $+1.0$: 黒地確定 / $-1.0$: 白地確定 / $0.0$: 係争地（中立）。
2.  **Ownership Volatility (分散/不確実性):**
    - 単純な $O_{xy}$ だけでなく、「0に近い＝誰のものか決まっていない＝危険」と解釈する。
3.  **Score Loss ($L$):** その手が何目損したか。
4.  **Score Stdev ($\sigma$):** 局面全体の不確実性。

## 3. 機能詳細（3つのサブモジュール）

### 3.1 機能A：係争地ヒートマップ（Volatility Heatmap）

「どこが急場か」を視覚化する機能。

- **ロジック:**
  - 各交点の `Ownership` の絶対値 $|O_{xy}|$ を計算。
  - $|O_{xy}| < 0.6$ （黒白どちらとも言えない領域）を「係争地（Volatile Area）」と定義。
  - 特に、**石が存在する座標**で $|O_{xy}| < 0.6$ の場合、その石は「生死不明（不安定）」な状態にある。
- **UI表示:**
  - 不安定な石グループの上に、**オレンジ色または黄色の「モヤ（Aura）」**をオーバーレイ表示。
  - ツールチップ：「このグループの生死は未確定です。手抜きは危険です。」
- **教育効果:**
  - 「なんとなく生きている」と思い込んでいる石が、AI視点では「五分五分（死ぬかもしれない）」と判定されていることを突きつけ、読みを促す。

### 3.2 機能B：過剰防衛アラート（Over-defense Warning）

「生きている石に手入れをして1目損をする」癖を矯正する機能,。

- **ロジック:**
  - プレイヤーが着手した地点 $P$ の直前の `Ownership` $O_{P(prev)}$ を参照。
  - **条件:**
    1.  $|O_{P(prev)}| > 0.95$ （既にほぼ100%自分の地である）。
    2.  着手による `Score Loss` $\approx 1.0$ （パスと同じ損をしている）。
    3.  周囲の敵石に動きがない（`Score Stdev` が低い）。
- **UI表示:**
  - 着手直後に、「⚠️ **過剰な手入れの可能性があります**」というトースト通知を表示。
  - 「この領域は既に99%確保されていました。(-1目)」と解説。
- **教育効果:**
  - 「念のため」の手が実際には悪手であることを即座にフィードバックし、形成判断の精度を高める。

### 3.3 機能C：ゾンビストーン表示（Dead Stone Visualization）

「取られている石を助けようとして傷口を広げる（サンクコスト効果）」を防ぐ機能,。

- **ロジック:**
  - 盤上に自分の石が存在するが、その座標の `Ownership` が敵側の値（例：黒石があるのに $O_{xy} \approx -1.0$）になっている場合。
- **UI表示:**
  - 死んでいる石を**半透明（グレーアウト）**にする、または小さな「💀（ドクロ）」マークや「×」印を薄く表示する,。
  - ユーザーがその石から逃げ出す手を打った場合、「AIはこの石を『救出不可能』と判断しています」と警告。
- **教育効果:**
  - 「まだ味がある」という幻想を打ち砕き、捨て石にする判断（サバキ）への転換を促す。

## 4. 実装設計ドラフト（Python/Pseudo-code）

`katrain/core/analysis/` および `katrain/gui/` への拡張を想定。

```python
@dataclass
class VolatilityMetrics:
    unsettled_groups: List[Group]  # 生死不明の石グループ
    zombie_groups: List[Group]     # 死んでいる石グループ
    over_defense_move: bool        # 直前の手が過剰防衛か

class OwnershipAnalyzer:
    def analyze_node(self, node: GameNode, prev_node: GameNode) -> VolatilityMetrics:
        board = node.board
        ownership = node.analysis['ownership'] # List[float] length 361

        # 1. 不安定グループの抽出 (Feature A)
        unsettled = []
        for group in board.groups:
            # グループ内の石のOwnership平均を計算
            avg_own = sum(ownership[p] for p in group.points) / len(group.points)
            # 0に近いほど危険（0.5以下を危険域とする）
            if abs(avg_own) < 0.5:
                unsettled.append(group)

        # 2. ゾンビ（死に石）判定 (Feature C)
        zombies = []
        for group in board.groups:
            avg_own = sum(ownership[p] for p in group.points) / len(group.points)
            # 黒石なのにOwnershipが-0.9以下（白地）なら死に石
            if (group.color == BLACK and avg_own < -0.9) or \
               (group.color == WHITE and avg_own > 0.9):
                zombies.append(group)

        # 3. 過剰防衛判定 (Feature B)
        over_defense = False
        move_point = node.move
        if move_point:
            prev_own = prev_node.analysis['ownership'][move_point]
            player = node.player
            # 既に自分の完全な地(>0.95)に打った、かつ1目損している
            if (player == BLACK and prev_own > 0.95) or \
               (player == WHITE and prev_own < -0.95):
                if 0.8 < node.score_loss < 1.5: # およそ1目の損
                    over_defense = True

        return VolatilityMetrics(unsettled, zombies, over_defense)
```

## 5. UI/UXへの統合案

myKaTrainの画面上に、以下のトグルボタンを追加する。

- **[ ☠️ Danger Mode ] (On/Off)**
  - **On時:**
    - 盤面の「地」の色塗りを非表示にし、代わりに上記A（危険）・C（死に石）のハイライトのみを表示する。「何処が地か」ではなく「何処が未解決か」にフォーカスさせるため。
    - 過剰防衛（B）が発生した瞬間、画面上部に警告バナーを表示。

## 6. 期待される学習効果（カルテへの反映）

この機能で得られたデータは、`karte.json` および `summary.md` に以下のように記録され、LLM診断の根拠となります。

- **「無駄な手入れ回数」**: 過剰防衛アラートの発生回数。
  - _LLM診断例:_ 「あなたは優勢な局面で、不要な手入れを3回行い、合計3目を失っています。地の計算（Counting）を信じる練習が必要です。」
- **「死活不感症」**: 危険（Volatility高）な石を放置して死なせた回数。
  - _LLM診断例:_ 「右下のグループは危険信号が出ていましたが、手抜きをして頓死しました。AIのOwnership変動を見て、危険な形状を覚えましょう。」

この機能は、中級者が「万年五段」を脱出するために不可欠な**「本手と緩手の区別」**および**「死活の直感」**を養うための強力な足場かけ（Scaffolding）となります,。
