提供されたソース（`00-purpose-and-scope.txt`、`01-roadmap.txt`）および背景資料（`Abstract (Overview of Findings).docx`等）に基づき、**「Phase 57: Pacing & Tilt Doctor（ペース配分＆ティルト検知）」**の仕様草案を作成しました。

この機能は、`Abstract` 資料にある**「早打ち（Blitz）による浅い思考」**や**「ティルト（感情的な乱れ）による連鎖的ミス」**という、野狐有段者層の典型的な停滞要因を「時間データ」から科学的に診断するものです。

---

# 仕様草案: Phase 57 - "Pacing & Tilt Doctor"

## 1. 概要 (Concept)

SGFファイルに含まれる「消費時間データ（BL/WLタグ等）」とKataGoの「損失データ（Score Loss）」を突き合わせ、**「思考の質」**を診断する。
単に「悪手」を指摘するだけでなく、「なぜ間違えたか（早すぎたからか、悩みすぎたからか、冷静さを欠いていたか）」という**行動的要因**を特定し、カルテ（Karte）に行動指針として出力する。

## 2. データ構造設計 (Data Model)

### 2.1 `TimeMetrics` (時間分析データ)

各着手に対して、以下のメタデータを算出・保持する。

```python
@dataclass
class TimeMetrics:
    move_number: int
    time_spent: float       # 消費時間（秒）
    is_blitz: bool          # 閾値（例:5秒）未満か
    is_long_think: bool     # 閾値（例:60秒）以上か

    # 相関データ
    score_loss: float       # KataGoによる損失
    policy_entropy: float   # 局面の複雑さ（選択肢の多さ）

    # 診断フラグ
    is_impulsive: bool      # 早打ち かつ 大悪手（Impulsive Blunder）
    is_overthinking: bool   # 長考 したのに 悪手（Analysis Paralysis）
```

### 2.2 `TiltEpisode` (ティルト区間定義)

「ティルト（Tilt）」を単発の事象ではなく、**「トリガーとなるミスから始まる一連の崩壊区間」**として定義する。

```python
@dataclass
class TiltEpisode:
    start_move: int         # トリガーとなった最初の大悪手（Blunder）
    end_move: int           # 落ち着きを取り戻した（または終局）手
    duration_moves: int     # 区間の長さ
    cumulative_loss: float  # この区間で失った合計目数
    avg_time_per_move: float # この区間の平均着手速度（ティルト時は速くなる傾向）
    severity: str           # 'MILD', 'SEVERE', 'GAME_ENDING'
```

---

## 3. ロジック設計 (Core Logic)

### 3.1 時間データの正規化 (`TimeParser`)

SGFの仕様（LZ, BL, WL, Cタグなど）の揺らぎを吸収し、秒単位の消費時間を抽出する。

- **野狐/Tygem:** `BL` (Black Time Left) の差分から算出。
- **記録なし:** 時間データがない場合は本機能全体をスキップ（Graceful Degradation）。

### 3.2 診断アルゴリズム (`PacingAnalyzer`)

#### A. 「スピード違反（Speeding Ticket）」の検出

複雑な局面で時間を適正に使えていない箇所を特定する。

- **判定ロジック:**
  - `ScoreStdev`（局面の揺れ）が高い、または `Policy Entropy` が高い（候補手が多い）局面である。
  - かつ、`time_spent` < 5.0秒。
  - かつ、`score_loss` > 2.0目。
- **出力メッセージ:**
  > 「第X手：**思考放棄（Impulsive Move）**。局面が複雑（AIも迷う場面）でしたが、あなたは3秒で着手し、5目損しました。ここは『止まるべき場所』でした。」

#### B. 「ティルト（Tilt）」の検出

資料 `Abstract` にある「ミスを取り返そうとして早打ちになり、さらにミスを重ねる」 パターンを検出する。

- **判定ロジック:**
  1.  **Trigger:** `score_loss` > 5.0 の大悪手が発生。
  2.  **Reaction:** 直後の3〜5手以内で、平均消費時間が平常時より短く（焦り）、かつ連続して `score_loss` > 1.0 の悪手が出ている。
- **出力メッセージ:**
  > 「第X手〜Y手：**ティルト検知（Tilt Spiral）**。第X手のミス直後、着手ペースが急激に上がり（平均2秒）、さらに損を重ねています。ミスの後は『深呼吸（Physical Reset）』が必要です。」

---

## 4. 出力への統合 (Report Integration)

### 4.1 Summary Report (`summary.md`)

`Stats` セクションに「Time Management」項目を追加。

| 項目             | ユーザー値 | 診断                                  |
| :--------------- | :--------- | :------------------------------------ |
| **平均思考時間** | 8.2秒      | Fast (野狐平均)                       |
| **早打ち悪手率** | 15%        | **高い** (落ち着けば勝率が上がります) |
| **ティルト発生** | 2回        | 中盤(Move 85)で崩壊しました           |

### 4.2 Karte (`karte_*.md`)

個別の重要局面解説に「時間アイコン」を追加。

- 🐇 **(Rabbit):** 早打ち悪手。「もっと考えるべきでした」
- 🐢 **(Turtle):** 長考悪手。「迷いすぎて判断力が低下しました（Analysis Paralysis）」
- 🔥 **(Fire):** ティルト状態。「冷静さを欠いていました」

### 4.3 行動ルールの生成 (Action Rules)

`00-purpose-and-scope.txt` の目的に従い、具体的な矯正アクションを提示する。

- **診断:** 早打ち悪手が多い場合
  - **Action:** 「着手ボタンを押す前に、マウスから手を離して1秒数える。」
- **診断:** ティルトが検出された場合
  - **Action:** 「5目以上の損をしたと感じたら、次の手は絶対に30秒以上時間を使って『再計算』する。」

---

## 5. ロードマップへの配置

`01-roadmap.txt` のPhase 52以降に以下を配置します。これは既存のAIモデル（KataGo）の再学習を必要とせず、SGF解析のみで実装可能であるため、比較的低コストで高い教育効果（ROI）が見込めます。

### Phase 57: Pacing & Tilt Analyzer

- **目的:** 時間消費傾向とミスの相関分析エンジンの実装。
- **成果物:** `core/analysis/time_analyzer.py`
- **依存:** Phase 5 (Karte出力), Phase 48 (Radar - Stability軸に時間を加味)

### Phase 58: Tilt Integration & UI Hints

- **目的:** 解析結果をレポートに出力し、GUI上でも「早すぎた手」を可視化する。
- **UX:** 検討モードで、あまりに早く打って間違えた手に「🐇」マークを表示。

この機能は、`Abstract` 資料で強調されている「メタ認知（自分の思考状態の監視）」 をシステム的に支援する強力な武器となり、野狐有段者の「壁」を突破する鍵となります。
