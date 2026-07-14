# Phase 203: LLM「翻訳特化」導入 — 調査ドキュメント

> AGENTS.md: 1.3 節「現在のフェーズ」参照
> 作成日: 2026-07-17
> ステータス: **計画中（調査のみ完了、実装は未着手）**
> 関連: Phase 91-92（Beginner Hints MVP）、Phase 179（Summary Extension）、Phase 182（Ownership/Policy 派生）、Phase 186（Curator 統合）、Phase 128（LLM 検証テンプレート）、Phase 80-82（Ownership Consequence）、Phase 45（Lexicon Integration）

---

## 1. 背景・目的

### 1.1 問題提起：解釈可能性のギャップ

KataGo は世界最強の囲碁 AI だが、その出力（`scoreLoss: -8.3` 等）は人間にとって解釈が難しい。野狐 4-5 段程度のユーザー（sentoku870 本人）がこの数値を見ても、

- 「-8.3 目が大きいとはどの程度か」
- 「自分の石の死活ミスなのか、方向違いなのか」
- 「次の一手をどう変えるべきか」

が即座に分からず、LLM（Claude / ChatGPT 等）に「翻訳」を依頼する必要がある。

### 1.2 解決方針：LLM を「翻訳者」に特化させる

**設計思想**: LLM に盤面の戦況を「推論」させるのではなく、KataGo の出力（ScoreLoss, Ownership, PV）を **Ground Truth（絶対的事実）** として扱い、それを適切な囲碁用語やトーン（あやか / 智子）で **要約・解説** する役割に徹する。

### 1.3 期待される効果

| 観点 | 期待効果 |
|------|---------|
| **ハルシネーション抑制** | LLM が独自の盤面解析を排除し、構造化メタデータのみを根拠に回答 |
| **回答品質安定** | KataGo 数値 + Lexicon 定義 + 症状マッピング の三重 Ground Truth で再現性確保 |
| **トーン最適化** | 棋力別に「あやか（関西弁・親しみ）」⇄「智子（標準語・論理）」を自動切替 |
| **既存資産活用** | 統合マスター診断 DB v3.1（1558 行）と Lexicon YAML（116 エントリ）を動的結合 |

### 1.4 スコープ（本ドキュメント）

- **含む**: 設計原則、既存実装の対応表、症状マッピング案、ハルシネーション抑制 3 層防御、レベル判定アルゴリズム、統合ワークフロー、段階実装ロードマップ
- **含まない**: 具体的な Python 実装、テストコード、UI 統合（これらは Phase 208+ で個別スペック化）

---

## 2. 設計原則（4 つの Ground Truth）

LLM への入力は **以下の 4 層をすべて Ground Truth として扱う**。これらを LLM は「読み取る」が「反論・修正」はしない。

### 2.1 第 1 層: KataGo 数値（絶対的事実）

| フィールド | 意味 | Ground Truth として扱う範囲 |
|-----------|------|------------------------------|
| `scoreLoss` | 期待値との点差損失 | 数値そのまま（人為的補正禁止） |
| `scoreLead` | 現局面の予測点差 | 同上 |
| `winrate` | 勝率予測 | 同上 |
| `scoreStdev` | 予測の不確実性 | 同上 |
| `ownership` | 各地点の支配率（-1〜+1） | 同上 |
| `policy` | 各着手の事前確率分布 | 同上 |

### 2.2 第 2 層: 意味タグ（自動ラベル）

`katrain/core/analysis/meaning_tags/models.py:15` で定義された `MeaningTagId` 12 カテゴリ：

```
MISSED_TESUJI / OVERPLAY / SLOW_MOVE / DIRECTION_ERROR /
SHAPE_MISTAKE / READING_FAILURE / ENDGAME_SLIP /
CONNECTION_MISS / CAPTURE_RACE_LOSS / LIFE_DEATH_ERROR /
TERRITORIAL_LOSS / UNCERTAIN
```

これらは KataGo 数値 + 盤面構造から **決定論的に自動付与**される（Phase 46-47 で実装済み）。

### 2.3 第 3 層: ヒントカテゴリ（統合タグ）

`katrain/core/beginner/models.py:19` で定義された `HintCategory` **23 カテゴリ**：

- **Layer 1 Specific**（Phase 91-92、severity 2-3、構造検出）: `SELF_ATARI` / `IGNORE_ATARI` / `MISSED_CAPTURE` / `CUT_RISK` / `LOW_LIBERTIES` / `SELF_CAPTURE_LIKE` / `BAD_SHAPE` / `HEAVY_GROUP` / `MISSED_DEFENSE` / `URGENT_VS_BIG`
- **Layer 2 Summary**（Phase 179 / 182 / 186）: `MISTAKE_BLUNDER/MISTAKE/MISTAKE_GOOD` / `FREEDOM_ONLY_MOVE/NARROW/WIDE` / `DIFFICULTY_TRICKY/CALM` / `KATAGO_UNCERTAIN` / `OWNERSHIP_DOMINANT` / `POLICY_CONFLICT/POLICY_CONFIDENT` / `CURATOR_WEAK_AXIS`

これらは KataGo 数値の意味解釈を「人間語彙」に変換した中間表現。

### 2.4 第 4 層: Karte JSON（集約出力）

`katrain/core/reports/karte/json_export.py:46` で生成される schema v3.4 の JSON：

- `meta`（メタ情報: 対局者、棋力、結果、schema_hash）
- `summary`（全体統計: total_points_lost, mistake_distribution）
- `important_moves`（重要手リスト）
- `weaknesses`（Phase 149-C-2: 弱点仮説、上位 2 件）
- `weaknesses_meta`（Phase 158-I: カバレッジ指標）
- `mistake_streaks`（連続ミス検出）
- `critical_3`（最重要 3 手）
- `data_quality`（解析品質指標）
- `reason_tags_distribution`（理由タグ分布）
- `win_loss_analysis`（勝敗内訳）
- `loss_progression`（損失推移）
- `opponent_strength_loss_correlation`（相手棋力との相関）

**LLM への入力は原則この Karte JSON 全体** + 後述の §5「注入プロンプト」。

---

## 3. 既存実装の対応表

### 3.1 Ground Truth 候補の網羅状況

| 層 | 実装場所 | カバレッジ | 残作業 |
|----|---------|----------|--------|
| KataGo 数値 | `core/analysis/` 全般 | **100%**（KataGo が提供） | なし |
| 意味タグ | `core/analysis/meaning_tags/` | **100%**（12 カテゴリ） | なし |
| ヒントカテゴリ | `core/beginner/` | **23 カテゴリ**（特定 10 + 要約 13） | 統合マスター §2-0 の 30 症状と突合 |
| Karte JSON | `core/reports/karte/` | schema v3.4、全 12 セクション | なし |
| 既存 LLM プロンプト | `core/reports/karte/llm_prompt.py` | Critical 3 のみ | 汎用化が未着手 |

### 3.2 Phase 別カバレッジ（既存実装の活用状況）

| Phase | 内容 | 翻訳特化への寄与 |
|-------|------|----------------|
| Phase 46-47 | MeaningTags（12 カテゴリ） | ✅ Ground Truth 第 2 層 |
| Phase 50 | Critical 3 プロンプト | ⚠️ 限定的な LLM 連携のみ |
| Phase 80-82 | Ownership Consequence | ✅ 「Ownership を渡せば幻覚が減る」と明文化 |
| Phase 91-92 | Beginner Hints MVP | ✅ Ground Truth 第 3 層（Layer 1） |
| Phase 128 | LLM 検証テンプレート | ✅ ユーザー向けプロンプト集（docs/03-llm-validation.md） |
| Phase 148-149 | Karte JSON 化 + 弱点仮説 | ✅ Ground Truth 第 4 層 |
| Phase 156 | Dynamic Phase Detection | ⚠️ Phase 自動分類（翻訳には直接寄与せず） |
| Phase 158-I | weaknesses_meta（coverage_pct） | ✅ LLM に「弱点の網羅率」を伝達 |
| Phase 171 | Leela 完全削除 | ✅ KataGo 単一化で Ground Truth が明確に |
| Phase 179 | Summary Hint 9 カテゴリ | ✅ Ground Truth 第 3 層（Layer 2: Mistake/Freedom/Difficulty/KataGo） |
| Phase 182 | Ownership/Policy 派生 3 カテゴリ | ✅ Ground Truth 第 3 層（Layer 2: Ownership/Policy） |
| Phase 186 | Curator 統合（23 カテゴリ到達） | ✅ 棋譜全体の弱点 → `CURATOR_WEAK_AXIS` ヒント |
| Phase 187-192 | テスト拡充 + リファクタリング | ⚠️ 直接寄与は限定的、ただし保守性向上 |

### 3.3 統合マスター診断 DB v3.1（1558 行）の対応

`D:\github\myKatrain_参考資料\00_最重要_コーチング\囲碁コーチング_統合マスター_完全版_v3.1.md` のセクションと本フェーズの関連：

| master doc セクション | 内容 | 本 Phase での扱い |
|---------------------|------|-----------------|
| §0 モード選択ルーター | 棋力判定・モード切替 | §6 で実装方針決定 |
| §1 コミュニケーション・トーン | あやか / 智子 / 智子辛口の文体 | §6 で構造化案提示 |
| **§2-0 症状別クイック逆引き表** | 30 症状 × 該当エントリ候補 | **§4 で Python マッピング案提示** |
| §2 診断 DB 全体（Lv1-5、~90 エントリ） | 全エントリ定義 | 対象外（将来 Phase） |
| §3 インタラクション・フロー | Phase 1/2 テンプレート | §5 で System Instruction 案に組込 |
| §4 概念ナレッジベース | 戦略原則・手筋 | 対象外（将来 Phase） |
| 付録A 練習メニュー | レベル別練習法 | 対象外 |

---

## 4. 統合マスター §2-0 → Python マッピング案（30 症状）

ユーザー回答「**§2-0 症状別クイック逆引き表のみ（30症状）**」に基づく。master doc §2-0 の症状 × Phase 194 マッピング候補。

### 4.1 マッピング表（30 症状 × 検出条件 × 既存 / 新規）

| # | 症状（master doc 表記） | 該当エントリ候補 | 自動検出条件（KataGo 数値 + 構造） | 既存 / 新規 | LLM 委ね |
|---|---------------------|----------------|----------------------------------|-----------|---------|
| 1 | 石が取られる・大石が死ぬ | Atari Blindness | `SELF_ATARI` or `IGNORE_ATARI` ヒント発火 | 既存 | - |
| 2 | 石が取られる・大石が死ぬ | Capture Oversight | `MISSED_CAPTURE` ヒント発火 + `pointsLost > 1.0` | 既存 | - |
| 3 | 石が取られる・大石が死ぬ | Ladder/Net Oversight | `CAPTURE_RACE_LOSS` タグ + シチョウ形状検出 | 一部既存 | ✅ |
| 4 | 石が取られる・大石が死ぬ | Life/Death Misjudgment | `LIFE_DEATH_ERROR` タグ + `ownership` 大幅変動 | 既存 | - |
| 5 | 切られる・分断される | Connection Neglect | `CONNECTION_MISS` タグ + グループ分断 | 既存 | - |
| 6 | 切られる・分断される | Cut Panic | `CUT_RISK` ヒント発火 + 複数切点 | 既存 | - |
| 7 | 切られる・分断される | Weak Group Neglect | `low_liberties` + 孤立グループ | 既存 | - |
| 8 | どこに打てばいいか分からない | First Move Confusion | 序盤（move ≤ 30） + `pointsLost > 5.0` | **新規** | - |
| 9 | どこに打てばいいか分からない | Big Point Blindness | `URGENT_VS_BIG` タグ + 最大地ポイント未着手 | 既存 | - |
| 10 | どこに打てばいいか分からない | Too Many Choices | `FREEDOM_WIDE` ヒント + 序盤 | 既存 | - |
| 11 | 大場が見えない | Small Move Addiction | 中盤（30 < move ≤ 200） + `pointsLost > 2.0` 連続 | **新規** | - |
| 12 | 大場が見えない | Big Point Blindness | （#9 と統合） | - | - |
| 13 | 大場が見えない | Overconcentration | `OVERPLAY` タグ + 厚み方向への着手 | 既存 | - |
| 14 | 定石が分からない・迷う | Joseki Rote | 序盤 + 定石座標以外への着手 | **新規** | ✅ |
| 15 | 定石が分からない・迷う | Joseki Overstudy | 序盤 30 手以上同一象限 | **新規** | ✅ |
| 16 | 定石が分からない・迷う | Post-Joseki Direction | 序盤終了（move ≈ 30）+ `DIRECTION_ERROR` | 既存 | - |
| 17 | 攻めが空振り・無理攻め | Overplay/Reckless Attack | `OVERPLAY` タグ + `scoreStdev > 1.5` | 既存 | - |
| 18 | 攻めが空振り・無理攻め | Overfight | 連続 `MISTAKE_BLUNDER` (3 連以上) | 一部既存 | ✅ |
| 19 | 攻めが空振り・無理攻め | Attack with Purpose | `DIRECTION_ERROR` + 攻撃着手 | 既存 | - |
| 20 | 時間が足りない・秒読みミス | Time Pressure Loss | **時間データなし → 検出不能** | **LLM 委ね** | ✅ |
| 21 | 時間が足りない・秒読みミス | Time Misallocation | **時間データなし → 検出不能** | **LLM 委ね** | ✅ |
| 22 | 時間が足りない・秒読みミス | Time Drain | **時間データなし → 検出不能** | **LLM 委ね** | ✅ |
| 23 | ヨセで逆転される・終盤苦手 | Endgame Valuation Error | 終盤（move > 200）+ `ENDGAME_SLIP` | 既存 | - |
| 24 | ヨセで逆転される・終盤苦手 | Sente/Gote Confusion | 終盤 + `TERRITORIAL_LOSS` | 既存 | - |
| 25 | ヨセで逆転される・終盤苦手 | Endgame Precision | 終盤 + `MISTAKE_BLUNDER` 頻度 | 既存 | - |
| 26 | 同じミス繰り返し・上達しない | Same Mistake Loop | `CURATOR_WEAK_AXIS` + 3 局以上同一 Phase × Category | 既存 | - |
| 27 | 同じミス繰り返し・上達しない | Shallow Review | **ユーザー行動データなし → 検出不能** | **LLM 委ね** | ✅ |
| 28 | 同じミス繰り返し・上達しない | Stagnation Loop | 5 局以上の `weaknesses` 上位カテゴリ不変 | **新規** | - |
| 29 | 同じミス繰り返し・上達しない | Local Optimum | `FREEDOM_NARROW` 頻度 + 勝率停滞 | **新規** | ✅ |
| 30 | AI を見ても分からない | AI Overload | **ユーザー行動データなし → 検出不能** | **LLM 委ね** | ✅ |
| 31 | AI を見ても分からない | Copy Without Understanding | **ユーザー行動データなし → 検出不能** | **LLM 委ね** | ✅ |
| 32 | AI を見ても分からない | Authority Bias | **ユーザー行動データなし → 検出不能** | **LLM 委ね** | ✅ |
| 33 | 焦る・連敗・萎える | Tilt/Discouragement | 連敗（loss 3 連以上）+ `MISTAKE_BLUNDER` 頻度増 | **新規** | - |
| 34 | 焦る・連敗・萎える | Tilt Chain | 連敗中の `pointsLost` 増大パターン | **新規** | - |
| 35 | 焦る・連敗・萎える | Tilt/Emotional Interference | **ユーザー感情データなし → 検出不能** | **LLM 委ね** | ✅ |
| 36 | 形勢判断が合わない・逆転 | Evaluation Errors | `winrate_drop > 15%` + 中〜終盤 | **新規** | - |
| 37 | 形勢判断が合わない・逆転 | Position Evaluation | `scoreLead` と `winrate` の乖離大 | **新規** | - |
| 38 | 形勢判断が合わない・逆転 | Risk Miscalibration | `scoreStdev > 2.0` + ビハインド時の強攻め | **新規** | - |
| 39 | 捨て石できない・全部助けようとする | Saving Everything | `CONNECTION_MISS` + 影響圏複数 | 既存 | - |
| 40 | 捨て石できない・全部助けようとする | Sacrifice Judgment | **ユーザー意図データなし → 検出不能** | **LLM 委ね** | ✅ |
| 41 | 捨て石できない・全部助けようとする | Endowment Effect/Sunk Cost | **ユーザー行動データなし → 検出不能** | **LLM 委ね** | ✅ |

**自動検出可能**: 30 症状のうち **約 22 件**（既存 14 + 新規 8）、**LLM 委ね**: 約 11 件。

> 注: 表は master doc §2-0 の逆引き表を 1 対 1 で展開しているため、30 症状より多い（複数候補エントリを含む）。「30 症状 × 候補エントリ」の合計 41 行となっている。

### 4.2 自動検出不能な項目の扱い方針（ユーザー回答）

**ユーザー回答「案1: 『LLM に委ねる』フラグを立てて渡す」** を採用：

```json
{
  "symptom_id": "time_pressure_loss",
  "auto_detected": false,
  "llm_required": true,
  "context_hint": "KataGo 数値からは判定不能。ユーザー申告または SGF の時間データが別途必要。LLM には「症状候補」として列挙し、ユーザーに確認を促す形で回答を生成させる。"
}
```

LLM には「KataGo からは検出不能だが、ユーザーの発言・棋譜傾向から候補として検討すべき症状」をリストアップさせ、最終的な確定はユーザーが行うフローとする。

---

## 5. ハルシネーション抑制 3 層防御

ユーザー回答「**警告表示のみ**」を最終段として、3 層で LLM のハルシネーションを抑制する。

### 5.1 第 1 層: 構造化メタデータのみを入力とする

**原則**: LLM には **KataGo 数値 + Karte JSON + Lexicon エントリ** のみを入力し、**SGF 棋譜や盤面画像を入力しない**。

理由：
- SGF を入力すると LLM が独自の盤面解析を試みる → ハルシネーションの温床
- 既存 spec（common-improvements.md:107）で「`coord: P13` だけでは LLM が幻覚で補完する」と明記
- Phase 80-82 で Ownership を渡すことで「なぜ死んだか」の解説精度が向上することが実証済み

### 5.2 第 2 層: Lexicon as Ground Truth 注入

`go_lexicon_master_last.yaml` の 116 エントリ（Lv1: 60, Lv2: 56）を LLM プロンプトに **選択的に注入**：

```yaml
# 例: aji_keshi（味消し）エントリ
id: aji_keshi
ja_term: 味消し
ja_short: 自分の潜在力（味）を不要に消す悪手
ja_expanded: 早すぎる補強や確定により、相手の弱点や将来の着手点を消してしまうこと
pitfalls: 「念のため」の補強で味を取るのは典型的な味消し
contrast_with: aji_keizumi（味を残す）, sente（先手）
level: 2  # 中級
```

LLM には「`aji_keshi` という症状IDが Karte JSON に含まれる場合、以下の定義を厳密に使用して解説せよ」と指示。

### 5.3 第 3 層: HTML コメント式 System Instruction

既存 spec（common-improvements.md:73-95）の設計を踏襲し、Karte JSON 末尾に HTML コメントで LLM 専用指示を注入：

```html
<!--
[SYSTEM INSTRUCTION FOR LLM]
Role: You are a Go coach. Translate the attached Karte JSON into Japanese coaching language.
Mode: {tone_mode}  # ayaka / tomoko / tomoko_strict
Level: {user_level}

[STRICT RULES]
1. DO NOT analyze the board independently. Use ONLY the data in the JSON.
2. DO NOT invent move numbers, coordinates, or scores. Every number must match the JSON.
3. Every symptom_id you mention MUST exist in `weaknesses` or `important_moves[*].meaning_tag_id`.
4. Use the Lexicon definitions injected above verbatim for terminology.
5. End your response with "参照した症状ID: [list]" for downstream validation.
-->

<!--
[LEXICON INJECTION]
{lexicon_entries_for_detected_symptoms}
-->
```

ユーザーは Markdown レンダラでこのコメントを見ないが、LLM は読み取って厳格に守る。

### 5.4 出力検証：警告表示（ユーザー回答）

LLM 出力末尾の「参照した症状ID」リストを自動パースし、Karte JSON に存在しない tag_id が含まれていれば **警告表示**：

```
⚠️ LLM が言及した症状 ID のうち、JSON に存在しないもの:
   - shape_mistake_v2 (master doc には存在しない ID)
   - reading_failure_v3 (誤字？)

[LLM 出力は参考情報としてご利用ください]
```

- **ブロックはしない**（ユーザー回答「警告表示のみ」）
- ユーザーが無視する選択肢を残す
- 誤字・バージョン違いの切り分けにも有用

---

## 6. レベル判定アルゴリズム

ユーザー回答「**案1: KataGo BR/WR 自己申告 + 負け基準自動補正**」に基づく。

### 6.1 判定の優先順位

```
[1] KataGo BR/WR 自己申告（最優先）
        ↓ 取得できない場合
[2] SGF の BR/WR プロパティ参照
        ↓ 取得できない場合
[3] 負け基準からの自動推定（KataGo 数値から動的に逆算）
        ↓ 推定不能
[4] デフォルト = 中級モード（あやか文体）
```

### 6.2 棋力 → モードマッピング

master doc §0-1 と §0-3 を統合：

| BR/WR 表記 | 段級位 | モード | 文体 |
|-----------|--------|--------|------|
| 25k 〜 11k | 入門〜10級 | 初級 | あやか（関西弁・親しみ） |
| 10k 〜 5k | 9級〜4級 | 中級 | あやか（関西弁・現実的） |
| 4k 〜 1k | 3級〜初段 | 有段 | 智子（標準語・論理的） |
| 1d 〜 4d | 二段〜五段 | 高段 | 智子（標準語・本質重視） |
| 5d 以上 | 六段〜 | 強豪 | 智子・辛口（研究仲間・遠慮なし） |

### 6.3 負け基準による自動補正

KataGo の数値から棋力を推定する補正ロジック：

```
estimated_skill = base_skill_from_BR_WR
if avg_points_lost > 8.0: estimated_skill -= 1  # ビギナー傾向
if avg_points_lost > 15.0: estimated_skill -= 2  # 入門者傾向
if avg_winrate_drop > 20%: estimated_skill -= 0.5
if critical_move_count > 5 and avg_loss > 5.0: estimated_skill -= 1
```

補正結果は「推定」であり、Phase 208 以降の UI で「カタカナ段級位の場合は確認ダイアログを表示」する。

### 6.4 UI 統合方針（将来 Phase）

- 設定ダイアログで「あやか / 智子 / 智子辛口」を **手動上書き** 可能とする（最終手段）
- SGF の BR/WR が取得できなかった場合、ユーザー入力フォームを表示
- 推定の場合は「○○級〜○○段と推定」と明記（master doc §0-2 棋力推定時の明記テンプレートに準拠）

---

## 7. LLM 出力検証（警告表示 UI 設計）

ユーザー回答「**案1: 警告表示のみ**」に基づく。

### 7.1 検証ロジック

```
LLM 出力末尾: "参照した症状ID: [shape_mistake, overplay, foo_bar]"
                                          ^^^^^^^^
                                          JSON に存在しない
                                          ↓
警告表示:
⚠️ LLM が言及した症状 ID のうち、Karte JSON に存在しないもの:
   - foo_bar

[LLM 出力は参考情報としてご利用ください]
```

### 7.2 検証項目の優先順位

| 検証対象 | 重要度 | 失敗時の動作 |
|---------|-------|------------|
| 言及された `symptom_id` の JSON 存在 | 高 | ⚠️ 警告 |
| 言及された `move_number` の範囲（1〜N） | 高 | ⚠️ 警告 |
| 言及された `pointsLost` 値と JSON の一致 | 中 | ⚠️ 警告（差分表示） |
| Lexicon エントリの引用文字列の完全一致 | 中 | ⚠️ 警告 |
| 文体の言語一致（あやか = 関西弁） | 低 | 静的に通過 |

### 7.3 警告 UI 配置（将来 Phase）

- Karte JSON ビュワーの下部に「LLM 出力検証レポート」セクション
- 検証失敗が 0 件のときは「✅ 検証クリア」バッジのみ表示
- 失敗があるときは expand/collapse で詳細表示

### 7.4 設計の意図

- **ブロックしない**: LLM の創造性を殺さず、参考情報としての利用を維持
- **ユーザーが判断**: 検証失敗は「疑わしい」だけで「誤り」とは断定しない
- **誤字許容**: `shape_mistake` と `Shape_Mistake` のような表記揺れは LLM 側の正規化で吸収

---

## 8. 統合ワークフロー図

```
┌────────────────────────────────────────────────────────────────┐
│ Phase 1: 対局・KataGo 解析                                      │
│ - SGF 保存                                                      │
│ - KataGo: scoreLoss, winrate, ownership, policy, scoreStdev      │
└────────────────────────┬───────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ Phase 2: 構造化メタデータ生成                                    │
│ - MeaningTag 付与（core/analysis/meaning_tags/）                 │
│ - HintCategory 付与（core/beginner/、23 カテゴリ）                │
│ - Karte JSON 生成（core/reports/karte/json_export.py、schema v3.4）│
└────────────────────────┬───────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ Phase 3: 症状マッピング（Phase 208 で実装）                      │
│ - Karte JSON → 30 症状候補リスト                                │
│ - KataGo 数値から自動検出可能な症状を選別                        │
│ - LLM 委ねフラグ（auto_detected: false）付き症状を保持            │
└────────────────────────┬───────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ Phase 4: Lexicon 注入（Phase 208 で実装）                        │
│ - 検出された症状 ID に対応する Lexicon エントリを取得             │
│ - ja_short / ja_expanded / pitfalls / contrast_with を抽出       │
│ - プロンプトに挿入                                              │
└────────────────────────┬───────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ Phase 5: トーン選択（Phase 208 で実装）                          │
│ - BR/WR → 段級位 → モード（あやか / 智子 / 智子辛口）              │
│ - 負け基準による自動補正                                         │
└────────────────────────┬───────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ Phase 6: プロンプト生成（Phase 208 で実装）                      │
│ - Karte JSON（Ground Truth）                                     │
│ - + Lexicon 注入                                                │
│ - + HTML コメント式 System Instruction                         │
│ - → Markdown テキストとして出力                                  │
└────────────────────────┬───────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ Phase 7: ユーザー操作                                            │
│ - Markdown をクリップボードコピー                                 │
│ - Claude / ChatGPT / Gemini に手動で貼り付け                     │
│ - LLM が「翻訳」として回答                                       │
└────────────────────────┬───────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────┐
│ Phase 8: 出力検証（Phase 208-F で実装）                          │
│ - LLM 出力末尾の「参照した症状ID」をパース                        │
│ - Karte JSON に存在しない tag_id を検出                          │
│ - ⚠️ 警告表示（ブロックしない）                                   │
└────────────────────────────────────────────────────────────────┘
```

---

## 9. 段階実装ロードマップ（Phase 208-A〜G）

| Phase | 内容 | 規模 (Lv) | 主要ファイル | 実装可否 |
|-------|------|----------|-------------|---------|
| **198-A** | 統合マスター v3.1 → `core/coach/master_db.py` 構造化（§0/§1 のみ） | Lv2 | 新規 `katrain/core/coach/master_db.py` | 可 |
| **198-B** | Lexicon YAML → `core/coach/lexicon.py` ローダ | Lv2 | 新規 `katrain/core/coach/lexicon.py` | 可 |
| **198-C** | `core/coach/symptom_index.py`（§2-0 マッピング） | Lv2 | 新規 `katrain/core/coach/symptom_index.py` | 可 |
| **198-D** | `core/coach/tones.py`（あやか / 智子切替） | Lv1 | 新規 `katrain/core/coach/tones.py` | 可 |
| **198-E** | `core/coach/prompt_builder.py`（HTML コメント式 Instruction 注入） | **Lv3** | 新規 + `core/reports/karte/json_export.py` 改修 | 可（要アーキ確認） |
| **198-F** | LLM 出力検証（tag_id 存在チェック） | Lv2 | 新規 `katrain/core/coach/llm_validator.py` | 可 |
| **198-G** | 統合テスト（mock LLM で end-to-end） | Lv2 | 新規 `tests/test_coach_pipeline.py` | 可 |

### 9.1 Lv 判定の内訳

- **Lv0-1**（軽微）: Phase 208-D（tones.py はほぼ純粋関数の寄せ集め）
- **Lv2**（中）: Phase 208-A / B / C / F / G（単一ファイル単位の追加）
- **Lv3**（要アーキ確認）: **Phase 208-E のみ**（既存 `json_export.py` への埋め込み + 設定 UI 連動）
- **Lv4-5**（アーキ変更）: **不要**

### 9.2 実装の依存関係

```
198-A (master_db)
   ↓
198-B (lexicon) ──────┐
   ↓                   │
198-C (symptom_index)  │  ← 198-A/B/C は独立に着手可能
   ↓                   │
198-D (tones) ─────────┤
                       │
198-E (prompt_builder) ┘  ← 198-A/B/C/D 完了後に着手
   ↓
198-F (validator)  ← 198-E 完了後に着手
   ↓
198-G (e2e test)  ← すべて完了後に着手
```

### 9.3 推定工数（ユーザー手動実施の場合）

- 198-A: 約 200 行（§0 / §1 のみ抽出）／1-2 時間
- 198-B: 約 100 行（YAML ロード + インデックス）／30 分
- 198-C: 約 150 行（30 症状マッピング）／1 時間
- 198-D: 約 80 行（トーン選択関数）／30 分
- 198-E: 約 200 行（プロンプトビルダー + json_export 改修）／2-3 時間
- 198-F: 約 100 行（バリデーター）／1 時間
- 198-G: 約 200 行（mock LLM テスト）／1-2 時間

**合計: 約 1030 行、6-9 時間（Lv3 の 198-E が中心）**

---

## 10. 既存 specs との整合性確認

| 既存 spec | 主要提案 | Phase 203 との関係 |
|-----------|---------|-------------------|
| **lexicon-integration.md** (Phase 45) | Semantic Tagger / RAG Explainer / Level-Adaptive UI / Concept Overlay / Quiz Generator | §4 症状マッピング = Semantic Tagger の §2-0 特化版、§5 第 2 層 = RAG Explainer |
| **common-improvements.md** (Phase 47-50) | Context 注入 / System Instruction 注入 / Semantic Board Description | §5 第 3 層 = System Instruction 注入、Phase 80-82 = Semantic Board Description |
| **phase80-82-ownership-consequence.md** (Phase 80-82) | Ownership Consequence、LLM への「なぜ死んだか」情報付与 | §3.1 既存実装として参照 |
| **phase91-92-beginner-hints.md** (Phase 91-92) | Beginner Hints MVP（4 構造検出 + 6 MeaningTag フォールバック） | §2.3 Ground Truth 第 3 層（Layer 1 Specific）として統合済み |
| **phase179-hints-summary-extension.md** (Phase 179) | Summary Hint 9 カテゴリ（Mistake / Freedom / Difficulty / KataGo） | §2.3 Ground Truth 第 3 層（Layer 2 Summary）として統合済み |
| **phase80-82-ownership-consequence.md**（再掲） | 「Ownership 情報を LLM に渡せばハルシネーションが減る」 | §5 第 1 層の根拠 |
| **03-llm-validation.md**（Phase 128） | LLM 検証テンプレート（プロンプト集） | §5 第 3 層 System Instruction と併用するユーザー手動プロンプトの元ネタ |

**結論**: Phase 203 は既存 specs の **統合・体系化** であり、新規設計要素は少ない。最も新規性が高いのは §4「§2-0 症状マッピング」と §7「LLM 出力検証（警告表示）」。

---

## 11. リスク・非機能要件

### 11.1 リスク

| リスク | 影響 | 緩和策 |
|--------|------|--------|
| Lexicon YAML の master doc との不整合 | 中 | Phase 208-B でロード時にバリデーション、欠損フィールドは警告 |
| LLM の API 仕様変更（Claude / ChatGPT） | 低 | ユーザー手動貼り付けのため、API 仕様には依存しない |
| 検出不能症状の過剰列挙（ユーザーに不快感） | 中 | 自動検出可能 22 件を主、LLM 委ね 11 件は「候補」として控えめに提示 |
| 警告 UI の見落とし（ユーザー無視） | 低 | Karte JSON ビュー上部に「LLM 出力は参考情報」バナー常時表示 |
| i18n キー追加による既存翻訳の破壊 | 低 | 既存 i18n キーには触れず、新規追加のみ |

### 11.2 非機能要件

| 項目 | 要件 |
|------|------|
| **パフォーマンス** | Karte JSON 生成 + プロンプト生成が合計 5 秒以内（既存 Karte 生成は ~2 秒） |
| **依存ライブラリ** | 追加ゼロ（PyYAML は既存、json は標準） |
| **既存ユーザー後方互換** | Phase 203 はドキュメントのみ。実装着手後も Karte JSON schema は維持 |
| **テストカバレッジ** | Phase 208-G で mock LLM による end-to-end テスト |
| **i18n** | 日本語のみ（プロンプト・警告 UI とも）。将来英語対応は別 Phase |

### 11.3 Karte JSON Schema への影響

**Phase 203 は Karte JSON schema を変更しない**。`json_export.py` の末尾に HTML コメントを追加する処理（Phase 208-E）が schema への唯一の追加。

schema_hash（Phase 158-I）に変化があった場合は `REPORT_SCHEMA_VERSION` を 3.4 → 3.5 にバンプ予定（Phase 208-E 着手時）。

---

## 12. オープン課題

実装フェーズ（Phase 208+）着手時に解決すべき項目：

1. **新規 detector 8 件の優先順位**: §4.1 の「新規」項目（First Move Confusion / Small Move Addiction / Joseki Rote / 等）のうち、Phase 208 で実装するのは 2-3 件に絞るべきか？
2. **LLM 委ね症状のリスト形式**: §4.2 の `auto_detected: false` フラグ付き症状を、LLM プロンプトでどう提示するか？（箇条書き vs 表 vs JSON ネスト）
3. **警告 UI のトリガ**: LLM 出力を手動で貼り付けたときに自動検証するか、ユーザー明示ボタンで起動するか
4. **検出不能症状のデフォルト動作**: 検出不能症状が 0 件のときは警告を抑制、5 件以上のときは別 UI（「症状候補レビュー」）を出すか
5. **トーン判定の SGF BR/WR 書式**: 「野狐 5 段」「5d」「5段」など表記揺れをどう正規化するか
6. **負け基準の閾値**: §6.3 の閾値（8.0 / 15.0 / 20% / 5）は妥当か、Phase 208-A の実装時にゴールデン棋譜で検証
7. **Lexicon エントリの動的更新**: YAML ファイルが更新されたときのキャッシュ戦略
8. **LLM 出力検証のモーダル**: 警告 UI を Karte JSON ビューア内に出すか、別ウィンドウ（Popup）にするか

---

## 13. 用語集

| 用語 | 定義 |
|------|------|
| **Ground Truth** | LLM が「読み取るが反論・修正しない」絶対的な事実。KataGo 数値・Karte JSON・Lexicon 定義の 4 層 |
| **Translation** | 本ドキュメントでの「翻訳」は、Ground Truth を人間語彙（あやか / 智子）に変換することを指す。LLM に独自の判断はさせない |
| **Auto-detected symptom** | KataGo 数値から自動判定可能な症状（30 症状中 22 件） |
| **LLM-delegated symptom** | KataGo 数値からは判定不能で、LLM に候補列挙を委ねる症状（30 症状中 11 件） |
| **Tone Mode** | あやか（初級・中級）/ 智子（有段・高段）/ 智子・辛口（強豪）の 3 トーン |
| **HintCategory** | Beginner Hints の 23 カテゴリ（Phase 91/92/179/182/186 統合） |
| **MeaningTagId** | 意味タグの 12 カテゴリ（Phase 46） |
| **Lexicon Entry** | go_lexicon_master_last.yaml の 116 エントリ |
| **Symptom ID** | 統合マスター §2-0 の症状名（`time_pressure_loss`, `atari_blindness` 等） |

---

## 14. 変更履歴

| 版 | 日付 | 変更内容 |
|----|------|---------|
| v0.1 | 2026-07-17 | 初版作成（Phase 203 調査ドキュメント）。D案（ドキュメント整備のみ）として実装は未着手 |

---

## 15. 次フェーズへの申し送り

実装着手時（Phase 208+）の着手手順案：

1. **Phase 208-A**: `core/coach/` ディレクトリ新設、master doc §0 + §1 を `master_db.py` にロード
2. **Phase 208-B**: Lexicon YAML を `lexicon.py` で読み込み、ID インデックス作成
3. **Phase 208-C**: §4.1 の 30 症状マッピング表を `symptom_index.py` に移植（**§4.2 の LLM 委ねフラグも同時に実装**）
4. **Phase 208-D**: あやか / 智子 / 智子辛口の選択関数を `tones.py` に実装、master doc §1-3 関西弁チェックリストも定数化
5. **Phase 208-E**: `prompt_builder.py` で §5.3 の HTML コメント式 Instruction を生成、`json_export.py` 末尾に `<!-- [LLM_PROMPT_BLOCK] -->` セクション追加（**schema_version を 3.5 にバンプ**）
6. **Phase 208-F**: `llm_validator.py` で「参照した症状ID」リストをパースし、警告 UI に連携
7. **Phase 208-G**: `tests/test_coach_pipeline.py` で mock LLM（固定文字列を返すオブジェクト）による end-to-end テスト

**着手前の確認事項**:
- §6.3 負け基準の閾値が妥当か（ゴールデン棋譜での検証が必要）
- §4.1 新規 detector 8 件の優先順位
- LLM 委ね症状の最大列挙数（5 件 / 10 件 / 全件）

実装着手は本ドキュメントの §9 ロードマップ通りに進め、Phase 208-E 完了時点で Karte JSON schema v3.5 への移行を別途スペック化する。
