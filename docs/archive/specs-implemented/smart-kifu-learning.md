# my-katrain: Smart Kifu Learning / Player Profile / Viewer Level / KataGo Training  
**Spec v0.2 (Draft)**  
作成日: 2026-01-06  
対象: my-katrain (KaTrain fork / Python + Kivy) / Claude Code 参照用

---

## この仕様の読み方（段階的）
この仕様は「迷わず実装できる」ことを目的に、次の順で段階的に固めています。

1. **決定事項（v0.2で固定すること）** … 迷いが出る論点を先に潰す  
2. **データと分離方針** … 混ぜると壊れるものを混ぜない  
3. **UIとワークフロー** … ユーザー操作を最小にしつつ再現性を確保  
4. **推定・提案ロジック** … “当てる”のではなく“収束させる”  
5. **受け入れ基準（Done定義）** … 既存機能を壊さない

> 実装スコープは **Phase 1–2**（後述）を前提。Phase 3+ は将来拡張（保留）です。

---

## 0. 背景と狙い

### 0.1 背景（課題）
- 人間相手の棋譜（例: 野狐）は環境要因が多く、結果の一貫性（学習条件や推定の再現性）を保ちにくい。
- KataGo 対局は設定（モデル/visits/弱化/置石/路数）で統制でき、弱点を狙い撃ちしやすい。
- 「段位推定」よりも **“いま理解しやすい解説の粒度”** を安定して出す方が実用価値が高い。

### 0.2 本仕様の狙い（Value）
- ユーザーの棋譜から、**解説粒度（Viewer Level）** と **練習条件（置石/路数/強度）の提案**を出す。
- 結果を混ぜて壊さないために、**Context（文脈）・Bucket（条件）・Engine Profile（解析条件）**で厳密に分離する。
- my-katrain 内の利用を主対象とし、外部ソース混在による不整合を抑える。

---

## 1. 用語と概念（最重要）

### 1.1 Viewer Level（1〜10）と v0.2 の扱い
- **Viewer Level（概念）**：ユーザーが「いま」理解しやすい解説粒度（情報量/用語/数値表示/候補手提示の深さ）を表す内部指標。
- **目的**：段位を当てることではない。  
  ただし極端な誤推定を避けるため、**信頼度（Confidence）**と品質情報を併記する。

#### v0.2 での実装簡略（重要）
- v0.2 では UI/出力上のレベルは **3段階プリセット**に落とす（実装の迷いを減らす）。
  - `Lite`：用語少、数値ほぼ無し、候補手1、理由は短文
  - `Standard`：損失/勝率Δ、候補手2–3、簡単なタグ
  - `Deep`：候補手3–5、変化図/タグ詳細、数値多め
- 内部では Viewer Level 1–10 を保持してよいが、当面は `Lite/Standard/Deep` へマッピングして表示する。

### 1.2 Player Profile
- ユーザー単位の推定情報と、採用中の解説プリセットなどを保持する設定。
- 同じユーザーでも **Context** や **Bucket** が違えば別扱いにする（混ぜない）。

### 1.3 Context（文脈）※v0.2決定事項あり
- `human`：人間相手の実戦（相対的・環境要因多い）
- `vs_katago`：KataGo相手の練習/校正（統制可能）
- `generated`：生成局面や AI 進行から始めたドリル（ヨセ練習など）

> **v0.2決定**：Context は自動判定しない。保存/取り込み時にユーザーが選ぶ（Appendix C参照）。

### 1.4 Dataset Quality / Confidence
- Dataset Quality：データの一貫性・量・解析率など（「良い学習材料か」）。
- Confidence：推定がどの程度信頼できるか（低/中/高）。

### 1.5 Analysis Profile（解析プロファイル）と engine_profile_id
- 解析条件（モデル/visits/弱化/komi 等）を **スナップショット**として保持。
- 同じ棋譜でも解析条件が違うと結果が揺れるため、集計では **engine_profile_id** で分離する。

---

## 2. 全体アーキテクチャ（分離が肝）

### 2.1 分離方針（絶対ルール）
集計・推定・レポートは、次のキーで分離する。**混ぜない**。

- `context`（human / vs_katago / generated）
- `bucket`（例: 19路互先 / 置碁 / 9路 など）
- `engine_profile_id`（解析条件のスナップショットID）
- （必要なら）`training_set_id`（学習に使う棋譜集合）

### 2.2 データフロー（概略）
1. SGF を **Training Set** に取り込む（manifestに登録）
2. 各ゲームの Metadata を抽出（board/handicap/players/date等）
3. 解析済み情報があれば parsed（analyzed_ratio計算）
4. 直近N局 or フィルタ条件でサブセットを選び、Profile 推定/更新
5. プレビュー表示 → 採用/キャンセル

---

## 3. データモデル仕様（最小で強い）

### 3.1 Training Set（v0.2で導入・重要）
- Training Set は「棋譜フォルダ + manifest.json」の単位。
- 目的：
  - 野狐から50–100局の一括投入
  - KataGo対局を1局ずつ追加
  - 「直近N局」「日付範囲」などの選択を安定させる

#### 3.1.1 フォルダ例
```
user_data/smart_kifu/
  profiles/
    player_profile.json
  training_sets/
    <set_id>/
      manifest.json
      sgf/
        game_001.sgf
        game_002.sgf
```

#### 3.1.2 manifest.json（最小）
```json
{
  "version": 1,
  "set_id": "fox_2026w01",
  "name": "Fox bulk import (week01)",
  "created_at": "2026-01-06T09:00:00+09:00",
  "games": [
    {
      "game_id": "sha1:....",
      "path": "sgf/game_001.sgf",
      "added_at": "2026-01-06T09:10:00+09:00",
      "context": "human",
      "source": {"type": "import", "origin": "Fox", "note": ""},
      "tags": ["fox", "bulk"]
    }
  ]
}
```

- `added_at` を「直近N局」の基準（**実装が安定**）
- 将来、SGFのDTやファイルmtimeも補助に使ってよいが、v0.2の正は `added_at`

### 3.2 Game Metadata（SGF/ゲーム単位で保持）
最低限：
- board_size（9/13/19）
- handicap（整数）
- komi（数値）
- players（名前・色）
- result（あれば）
- move_count
- analyzed_ratio（後述）
- engine_profile_id（解析時に紐付け）

### 3.3 Player Profile（ユーザー単位）
例（概念。実装は最小でOK）：
```json
{
  "version": 1,
  "active_profile_id": "default",
  "profiles": {
    "default": {
      "updated_at": "2026-01-06T09:30:00+09:00",
      "per_context": {
        "vs_katago": {
          "19_even": {
            "viewer_level": 6,
            "viewer_preset": "Standard",
            "confidence": "medium",
            "samples": 20,
            "analyzed_ratio": 0.85,
            "engine_profile_id": "ep_12ab34",
            "use_for_reports": true
          }
        }
      }
    }
  }
}
```

### 3.4 engine_profile_id（v0.2デフォルト）
- my-katrain の engine 設定スナップショットを **canonical JSON** にして hash → 短縮ID（例: `ep_12ab34`）。
- 集計は `engine_profile_id` が一致するデータのみで行う。

---

## 4. 推定仕様（ざっくりで良い、でも壊れない）

### 4.1 推定の基本方針
- 推定は「絶対段位」ではなく **学習に最適な解説粒度** を出す。
- 性質の優先順位：
  1) 極端な誤推定を避ける  
  2) データ量が少ないときは保守的（Confidence低）  
  3) 前回推定からの変動は平滑化（急変を避ける）

### 4.2 analyzed_ratio（v0.2定義）
- `analyzed_ratio` = （メインラインのノードのうち解析情報が存在する数） / （メインライン総ノード数）
- v0.2の実装は「解析情報の有無」だけで良い（精密判定は後回し）。

### 4.3 Confidence（低/中/高）
目安：
- High：samples >= 30 かつ analyzed_ratio >= 0.7 かつ engine_profile_id一致
- Medium：samples >= 10 かつ analyzed_ratio >= 0.4
- Low：上記未満

> 追加ルール（推奨）  
> samples < 3 の場合は「集計結果を表示しない」または「参考値（Low）」のみ。

### 4.4 Viewer Preset（Lite/Standard/Deep）の決め方（v0.2）
- まずは Viewer Level 推定値を 1–10 で出す（雑でOK）
- 表示は次でマップ：
  - 1–3 → Lite
  - 4–7 → Standard
  - 8–10 → Deep

---

## 5. UI仕様（ボタン分離＋更新ワークフロー）

### 5.1 入口（ボタン分離）※必須
混ざると壊れるため、入口を分ける。

- **Human（棋譜学習）**
- **vs KataGo（練習/校正）**
- **Generated（ドリル/生成）**
- （別系統）Kifu Report（鑑賞ツアー）※Phase 4

### 5.2 Training Set Manager（v0.2で最小実装）
- Training Set 一覧
- 「新規作成」
- 「SGF一括インポート（フォルダ選択）」  
- 「追加インポート（このSetに追記）」
- 「Setの中身プレビュー（件数/日付範囲/Context内訳）」
- 「このSetを学習に使う（選択）」

### 5.3 Player Profile 更新ワークフロー（更新→プレビュー→採用/キャンセル）
**表示**
- Context別にカード表示（human / vs_katago）
- bucket別（19路互先 / 置碁 / 9路）
  - Viewer Preset（Lite/Standard/Deep）
  - Confidence（低/中/高）
  - サンプル局数、解析済み率、最終更新日
  - 「採用（use_for_reports）」トグル（1つだけ true を推奨）

**操作**
- 「更新」ボタン  
  - 対象：Context + bucket を選択
  - N局（10/20/30）選択
  - 追加フィルタ（任意）：日付範囲（added_at 기준）
  - 結果プレビュー：旧→新、差分と根拠
  - 「採用 / キャンセル」

---

## 6. 学習条件（路数/置石/強度）の推奨：正解を当てずに収束させる

### 6.1 目的
- 直近N局の結果から、勝率が **40–60%** に近づくように学習条件を提案する。
- 目的は勝率そのものではなく、**学びが最大化する難易度**に寄せること。

### 6.2 v0.2の提案ルール（シンプル固定）
- 直近N局の勝率帯を確認：
  - 70%超 → 難易度を上げる提案（置石を減らす、または路数を大きくする）
  - 30%未満 → 難易度を下げる提案（置石を増やす、または路数を小さくする）
  - 40–60% → 現状維持

#### v0.2の“変更手段”の優先順位（固定）
1) **置石 ±1**（最優先・理解しやすい）
2) 路数変更（9→13→19 など）※採用は任意  
3) weakenパラメータは v0.2 では触らない（将来）

### 6.3 提案の出力例
- 「直近20局：勝率72% → 置石を1子減らす提案（次は互先に寄せる）」  
- 「直近10局：勝率25% → 置石を1子増やす提案」

---

## 7. Yose Drill（終盤生成）仕様（Phase 3：保留）
v0.2では実装対象外。将来のための最低限の枠だけ残す。

- 入口は `generated` と分離する
- 終盤度チェックは v0.2 では **手数閾値のみ**の簡易で良い  
  - 例: 19路なら move_number >= 160 を目安

---

## 8. Kifu Report（棋譜鑑賞・学習ツアー）仕様（Phase 4：保留）
v0.2では実装対象外（別ボタン・別系統）。

---

## 9. Non-goals / リスク

### 9.1 Non-goals（v0.2では狙わない）
- 段位/レーティングを正確に当てる（推定の主目的にしない）
- ML（学習）によるプレイヤーモデリング
- 外部KataGoソフト間での完全互換・完全自動統合

### 9.2 主要リスクと対策
- **データ混在**（context/bucket/engine_profileの混在）  
  → UI入口分離＋集計キー固定で防止
- **解析不足**（analyzed_ratioが低い）  
  → Confidenceを下げる・推定を保守的にする
- **外部棋譜の条件不明**  
  → v0.2は “手動import＋手動context” に限定

---

## 10. 実装ロードマップ（v0.2のDone定義つき）

### Phase 1（最小で価値：見える化）※実装対象
Done:
- Training Set（manifest + 追加/一括インポート）
- Player Profile 画面（Context×Bucket のカード表示）
- 更新→プレビュー→採用/キャンセル
- 既存 Karte/Summary は無変更（新UIからのみ利用）

### Phase 2（KataGo専用レポート）※実装対象
Done:
- vs_katago 用の “練習課題” 表示（最小）  
- 学習条件（置石±1）提案を出せる

### Phase 3（Yose Drill）保留
### Phase 4（Kifu Report）保留

---

## Appendix C: Decisions (v0.2) — Claudeが迷わないための固定値

### C1. Supported sources
- Primary target is **my-katrain-managed workflow**.
- External SGFs are allowed only via **manual import** and must be explicitly tagged by user.

### C2. Context tagging (DECIDED)
- `context` is **user-selected** at save/import time (no auto-detection in v0.2).

### C3. Training Set & "recent N games" selection (DECIDED)
- Use Training Sets (folder + manifest).
- "Recent N games" is based on `added_at` (import time).
- Optional filter: date range on `added_at`.

### C4. engine_profile_id (DEFAULT)
- Auto-generated from my-katrain engine settings snapshot (canonical-json -> hash -> short id).
- Aggregations must never mix engine_profile_id.

### C5. Buckets (DEFAULT)
- Bucket key = `board_size` + `handicap_group`
  - examples: `19_even`, `19_handicap`, `9_even`
- Aggregation must never mix buckets.

### C6. analyzed_ratio (DEFAULT)
- analyzed_ratio = (# mainline nodes with analysis) / (# mainline nodes)

### C7. Viewer output level for v0.2 (DEFAULT)
- UI preset only: Lite / Standard / Deep
- Internal 1–10 mapping is allowed but deferred.

### C8. Persistence layout (DEFAULT)
- `user_data/smart_kifu/`
  - `profiles/*.json`
  - `training_sets/<set_id>/manifest.json`
  - `training_sets/<set_id>/sgf/*.sgf`

### C9. Adjustment loop (DEFAULT)
- Target winrate band: 40–60%.
- Primary adjustment: handicap +/- 1.
- Do not adjust engine weaken params in v0.2.

### C10. Regression safety (MUST)
- Do not change existing Karte/Summary behavior unless behind new entry points.
- Keep features separated by buttons (Human / vs_katago / Generated).
- Handle missing analysis gracefully (no crashes).
