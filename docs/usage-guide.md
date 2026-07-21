# myKatrain 使い方ガイド

> このガイドは myKatrain の基本的な使い方と、LLM（生成AI）との連携方法を説明します。
> 最終更新: 2026-07-21（Phase 284 完了時点）

---

## 1. myKatrain とは

KaTrain の fork プロジェクトで、KataGo 解析結果を「カルテ（診断書）」形式で出力し、LLM を使った囲碁コーチングを効率化するツールです。

---

## 2. ユースケース4ルート

myKatrain と LLM を組み合わせる際の **4つの使い方** を整理します。

### ルート1: プロンプトのみ
- **入力**: 困りごとを文章で入力
- **用途**: 入口・方向づけ・行動ルール提示（最大3つ）
- **例**: 「序盤で打ち過ぎてしまう癖を直したい」

**特徴**:
- 最も手軽
- 一般論になりやすい
- 主観と実態のズレに気づきにくい

---

### ルート2: プロンプト + SGF or 画像
- **入力**: 困りごと + SGFファイル or 盤面画像
- **用途**: 「何が起きたか」の具体化
- **例**: 「この局面で黒が不利になった理由を知りたい」＋ SGF

**特徴**:
- 具体例があるので説明の質が 1.5〜2倍 向上
- SGF推奨（画像は補助）
- まだ「どの局面が重要か」は人間が選ぶ必要あり

---

### ルート3: プロンプト + 解析入りSGF（KataGo解析済み）
- **入力**: 困りごと + KataGo解析データ入りSGF
- **用途**: **非サポート（想定外）**

**⚠️ このルートは扱いません**

**理由**:
- 解析入りSGFは情報量が膨大（数百KB〜数MB）
- LLMに全文貼り付けると処理が重くなる
- 重要局面の抽出が手動になり、効率が悪い
- 「楽に見える」が、実際は学習効率が低い

**このルートが来たときの対応**:
> 解析入りSGFの全文は情報量が多すぎて、この手順では扱いません（想定外の入力です）。
> 代わりに次のどちらかでお願いします：
> 1) 解析なしのSGF（または盤面画像）＋困りごと1〜3行
> 2) myKatrain のカルテ（重要局面TopN＋サマリ）を貼付（最も精度が上がります）

---

### ルート4: プロンプト + カルテ（myKatrain）
- **入力**: 困りごと + myKatrain 出力のカルテ（Markdown）
- **用途**: **最推奨（想定通り）**
- **例**: 「直近10局のカルテを見て、次の5局で優先すべき課題を教えて」＋ summary.md

**特徴**:
- 相談の質が **2〜4倍以上** 向上（体感）
- 「致命点トップ3」が客観指標で確定
- 主観の悩みとデータのズレ（思い込み）を補正
- 次の5局で改善したかを検証できる（学習ループ化）

**カルテが上げる相談の質**:
- 文章のみ（ルート1） → 一般論
- SGFあり（ルート2） → 具体例が増えて 1.5〜2倍程度
- カルテあり（ルート4） → 重要局面TopN＋集計で **2〜4倍以上**

---

## 3. カルテの種類

myKatrain は2種類のカルテを出力できます。

### 3.1 単局カルテ（1局の診断書）
- **出力**: 現在の対局の重要局面・ミス分類・フェーズ別統計
- **用途**: 「この1局で何が起きたか」を振り返る
- **操作**: メニュー → Analysis → カルテ作成（予定）

### 3.2 複数局サマリー（Phase 6で実装済み）
- **出力**: 複数局の統計をまとめたレポート（summary.md）
- **用途**: 「直近N局の傾向」を把握する
- **操作**: メニュー → Analysis → 複数対局カルテ作成

---

## 4. カルテ駆動モードの推奨フロー

カルテを使ってLLMと相談する際の **短くて強い** フローです。

### Step 1: カルテから客観事実3点を抽出
例:
- 中盤に損失が集中している（序盤12.3目 / 中盤38.9目 / 終盤8.1目）
- 大悪手（blunder）が6回ある（全体の2.1%）
- 手の自由度が「狭い」局面で損失が多い（35件中12件が悪手以上）

### Step 2: 原因仮説は最大2つに絞る
例:
- 仮説1: 中盤の戦いで読み抜けが多い
- 仮説2: 形勢判断ミスで無理な攻めをしている

### Step 3: 主テーマ1つを決める（他は捨てる）
例:
- 主テーマ: 「中盤の戦いで、相手の弱点と自分の薄みを見極める」

### Step 4: 行動ルール最大3つ（次の5局で守る）
例:
1. 戦いの前に「自分の石は安全か？」を確認
2. 相手の弱点（呼吸点2以下）を見つけてから動く
3. 読みが不安なら、まず連絡・補強を優先

### Step 5: 検証指標2つ（次のカルテで確認）
例:
1. 中盤の平均損失が30目以下に減る
2. 大悪手（5目以上）が3回以下に減る

### Step 6: 主観とカルテがズレていれば指摘（質問は最大2つ）
例:
- 「序盤が弱い」と思っていたが、データでは中盤の損失が3倍多い
- 「なぜ中盤で損失が増えると思うか？」（反証質問）

---

## 5. 運用ルール（明文化）

### ルート3（解析もりもりSGF）は非サポート
- 解析入りSGFの全文貼り付けは扱わない
- 必ず **ルート2（SGF/画像）** か **ルート4（カルテ）** へ誘導する

### カルテの軽さを維持する
- カルテは「LLMに貼るための、軽くて客観的な証拠」
- 重要局面TopN + 集計だけで、PV（変化）は原則入れない（重くなるため）

### 学習ループを回す
- カルテ → 課題特定 → 行動ルール → 5局実践 → 再カルテ
- 1回の相談で「主テーマ1つ + 行動ルール最大3つ」に絞る

---

## 6. FAQ

### Q1: カルテは何局分あればいい？
- **直近10局**: 処方（次の5局で直す）に最適
- **直近50〜100局**: 傾向（癖の頻度、崩れる帯域）を把握

### Q2: カルテ無しでLLMに相談してもいい？
- はい、ルート1（プロンプトのみ）やルート2（SGF/画像）も有効です
- ただし、カルテを使うと相談の質が大幅に向上します

### Q3: 解析入りSGFを貼り付けたらダメ？
- ルート3は非サポートです
- 代わりにルート2（解析なしSGF + 困りごと）またはルート4（カルテ）を使ってください

### Q4: カルテの「importance」って何？
- 重要度スコア（損失の大きさ + 局面の難しさを加味）
- 高いほど「この手が勝敗を分けた」可能性が高い

### Q5: 複数局サマリーの「freedom」が全部UNKNOWNなのはなぜ？
- **複数局サマリー（SGF直接パース）では Freedom は計算されません**
- Freedom 計算には KataGo の候補手情報（candidate_moves）が必要
- SGF ファイルには candidate_moves が保存されていないため、復元不可能

**Freedom が使える場所**:
- 単局カルテ（リアルタイム解析時）← Phase 7 で実装予定
- KaTrain の対局中・検討中（Game オブジェクト経由）

**代替指標**:
- 複数局サマリーでは Phase × Mistake のクロス集計を使用
- 「中盤の大悪手」など、具体的な弱点を特定可能

---

## 7. 次のステップ（2026-07-21 時点 = Phase 284）

> 本セクションは Phase 6 ベース（2025-12）の古い記述です。最新の完了 Phase は **Phase 284** に到達しており、以下に主要マイルストーンを整理します。

### 完了済み主要 Phase（2026-07-04 〜 2026-07-21）

| Phase | 内容 | 状態 |
|-------|------|:----:|
| 171 | Leela エンジン完全削除（KataGo 専用化） | ✅ |
| 172 | `commands/DISPATCH_TABLE` への明示的ディスパッチ移行 | ✅ |
| 177 | 棋譜並べ（kifunarabe）機能 | ✅ |
| 225 | LLM Coach GUI 統合（手動貼付ワークフロー） | ✅ |
| 227 | LLM Coach 複数局対応（B 案フル実装） | ✅ |
| 228 | LLM Coach 実シェーマ適応 | ✅ |
| 230 | MyKatrain メニュー整理（8→4 項目）+ Leela 残滓削除 | ✅ |
| 242 | LLM Coach 品質改善統合改修（5 サブフェーズ） | ✅ |
| 246 | 候補手フィルター（PV Filter）包括改善 | ✅ |
| 250 | 重要局面 UI リファクタリング（タブ化 + 4 ボタン分割 + popup 廃止） | ✅ |
| 269 | AYAKA 完全削除 + voice 統一（TOMOKO） | ✅ |
| 270 | 複数カルテ集約 + サマリプロンプト v3.5 拡張 | ✅ |
| 272 / 272-E | `KaTrainGui.__init__` 3 ヘルパー分割 + LLM Coach popup メソッド分割 | ✅ |
| 273-276 | 依存更新 / CI 更新 / mypy 2.x / chardet 7 | ✅ |
| 277 | KivyMD 0.104.1 → 1.2.0 移行（Material Design 3） | ✅ |
| 280 | AI 戦略 17→2 スリム化 + 局面を生成タブ削除 | ✅ |
| 281 | 日本語フォント tofu fix | ✅ |
| 282 | アーキテクチャレビュー P1+P2 着手 | ✅ |
| 283 | サイドパネル文字サイズ + 新規対局 popup ボタン空白 fix | ✅ |
| 284 | PyInstaller frozen binary の `tabbedpanel` / `checkbox` 欠落 fix | ✅ |

### 直近の作業候補（Phase 286+）

- **OpenAI 互換エンドポイント連携**（Phase 224 で将来再検討予定）
- **Candidate Filter composite sort UI スライダー**（M3、Phase 247 で deferred）
- **重要局面機能 残課題**（Phase 248 の D1/D2 完了、E1 残）
- **複数カルテ集約 GUI 統合**（Phase 270 で deferred、popup の複数カルテ選択 UI）
- **CLI `aggregate` サブコマンド**（Phase 270 で deferred）

各 Phase の詳細は [`docs/01-roadmap.md`](./01-roadmap.md) §4 を参照。

---

## 8. 参考資料

- `docs/design/phase6-karte-spec.md`: カルテの設計仕様
- `docs/01-roadmap.md`: ロードマップ
- `AGENTS.md`: プロジェクト全体の概要（opencode 開発ガイド）
- `.opencode/skills/*/SKILL.md`: 細目ルール（on-demand 読み込み）

---

## 7.5 候補手フィルター（PV Filter）

KataGo 解析が出す候補手を盤面に表示する前に「ノイズ」を間引く仕組み。
**初期値は AUTO** で、`player_rank` (棋力プリセット) に応じて 4 段階の
強度が自動選択される。棋譜並べ (kifunarabe) モード中は自動 OFF。

### 7.5.1 4 段階の強度

| レベル | 最大候補手数 | 損失閾値 | PV長閾値 | 用途 |
|--------|------------|----------|----------|------|
| **緩め (weak)** | 15 | 4.0 目 | 15 手 | 激甘・甘口 (relaxed/beginner) |
| **標準 (medium)** | 8 | 2.0 目 | 10 手 | 標準 (standard) |
| **厳選 (strong)** | 4 | 1.0 目 | 6 手 | 辛口 (advanced) |
| **最厳 (expert)** | 3 | 0.5 目 | 4 手 | 激辛 (pro) ※ Phase 246-D で追加 |

「最大候補手数」は **最善手 (best_move) 以外** の上限。最善手は常に
別枠で表示される (Phase 11 からの挙動)。

### 7.5.2 AUTO モード

`pv_filter_level = auto` の場合、`general/player_rank` から自動推定。
`mykatrain` 設定画面で `AUTO → 標準 (最大 8 件まで)` のような
ステータスが表示される (Phase 246-A H2)。

棋力を変えると AUTO で選択される強度も変わる:

- 10級〜5級 → 緩め
- 4級〜1級 → 緩め〜標準
- 初段〜3段 → 標準
- 4段〜6段 → 厳選
- 7段以上 → 最厳 (expert)

### 7.5.3 盤サイズ補正 (M1)

9路 / 13路 では `max_pv_length` が線形縮小される (STRONG で 19路=6 →
9路=3)。小盤面で全候補が除外される問題を緩和。`max_candidates` と
`max_points_lost` は盤サイズに依存しない。

### 7.5.4 視点ラベル (H1)

盤面左下に「視点: B / W」の透かしが表示される (候補手がある時のみ)。
これは `pointsLost` が「次手 (次に打つプレイヤー) 視点の損失」で
計算されていることの明示。

例: 黒番の局面で `pointsLost=3.0` は「**白が打つと黒目線で 3 目損**」
ではなく「**黒が打つ手のうち最善手から 3 目損**」を意味する。

### 7.5.5 棋譜並べ (kifunarabe) 中の挙動 (H4)

棋譜並べモード中は **フィルター完全 OFF** (正解と AI 候補が必ず全件表示)。
設定画面で「※ 棋譜並べモード中は自動OFF」の注意書きが表示される。
AST ベースのテスト (`test_pv_filter_kifunarabe_skip.py`) で保証。

### 7.5.7 棋譜並べ (kifunarabe) 機能 (Phase 249-β)

Phase 177 で実装された学習モード。KataGo 解析済み SGF を「次の一手予測クイズ」として再生する。

#### 起動

- メニュー「棋譜並べ」(`Ctrl-R`) または 盤面の「棋譜並べ中断」ボタン
- SGF 選択 → 「先手/後手/両方」「ヒント数 (0-5)」「手数 (50/100/150/全部)」を選択
- セッション開始。盤上に候補マーカー (実戦手 + KataGo top N) が表示される

#### ルール

- **ユーザーが実戦手と同じマスをクリック** → 正解
- **別のマーカーをクリック** → 不正解 (WRONG_GUESS として記録)
- **マーカー外をクリック** → 不正解
- 自分の手番でない側 (`turn="B"` のとき白番の手) は **自動進行**
- `max_moves` に達するか本譜終了で **summary popup** を表示
- 候補マーカーは uniform color (デフォルト) で「KataGo のランキングを見せない」

#### 設定 (Phase 177-E / 230-C / 249-β)

設定タブ「棋譜並べ」で:

| 設定 | デフォルト | 効果 |
|------|:---------:|------|
| `kifunarabe/sgf_load` | (空) | 棋譜並べ用の SGF フォルダ (通常の SGF 読込と分離) |
| `kifunarabe/history_dir` | `~/.katrain/kifunarabe_history` | 履歴保存先 (Phase 249-β) |
| `kifunarabe/show_digits` | False | 候補マーカーに数字 (勝率/スコア/探索数) を表示 |
| `kifunarabe/show_actual_border` | False | 実戦手に枠線 |
| `kifunarabe/uniform_color` | True | 全マーカー同色 (ランキング非表示) |
| `kifunarabe/auto_toggle_markers` | True | 「次の一手」「ドット」を自動 OFF |

#### 履歴 (Phase 249-β)

棋譜並べセッションが終了するたびに JSON 形式で履歴が保存される。

- 保存先: `kifunarabe/history_dir` (デフォルト `~/.katrain/kifunarabe_history/`)
- ファイル名: `YYYY-MM-DD_HHMMSS_<sgf_stem>.json` または `_manual.json`
- 含まれる情報: 終了時刻、SGF パス、config (turn / hints / max_moves)、summary (正解/誤答/auto/skip)、Critical 3 セット

summary popup の「履歴」ボタンで **直近 50 件のサマリ**を表示。各エントリは:

```
2026-07-18T09:30:14   game01.sgf
  total 38, correct 30, wrong 6, auto 2, skip 0
  correct rate 83.3%   critical_3 2/3 (66.7%)
```

`correct rate` は **ユーザーがクリックした手** (正解 + 誤答) のうちの正解率。
`全体率 (incl. auto-advance)` は **自動進行を含めた全体** での正解率。
両者を比較することで「ユーザーは予想を試みたが、自動進行は多かった」のか
「ユーザーはたくさん予想した」のかを区別できる。

#### よくある質問

**Q. 棋譜並べ中に Critical 3 バッジが出るのは?**
A. セッション開始時に現局面から Critical 3 候補 (B / W 各最大 3 件) を抽出し、
その手番に到達すると 1.5 秒間のトーストを表示 (Phase 179-B1)。

**Q. 履歴の削除方法は?**
A. Phase 249-β では手動削除のみ。`kifunarabe/history_dir` 内の JSON ファイルを
削除すれば OK。GUI からの削除は将来タスク。

### 7.5.6 よくある質問

**Q. STRONG にしても 8 件表示されるのはなぜ?**
A. STRONG の `max_candidates=4` は「最善手**以外**」の上限です。
最強の手 + 追加で最大 4 手の合計 5 件程度は正常。最善手は常駐表示。

---

## 7.6 重要局面機能の全体像 (Phase 248)

myKatrain には複数の「重要局面を抽出する」経路があります。本節では
それぞれの違いと相互関係を一望し、「結局どれを使えばいいのか?」に
答えます。

### 7.6.1 5 つの経路とそれぞれの役割

| 経路 | 単位 | 表示/出力 | 主な用途 |
|------|------|----------|---------|
| **重要度レベル** (B1) | 抽出感度 | 内部設定 | 「大雑把に拾う / 細かく拾う」を棋力別に切替 |
| **Critical 3** (B2 / 重要局面抽出) | 棋譜 (top-N/player) | Karte JSON / 将来 popup | Karte 出力の `critical_3` セクション |
| **重要局面リスト popup** (D1) | 棋譜 (全件) | GUI popup | 棋譜全体の重要局面を一覧 |
| **Beginner Hint** (Phase 91, 179) | 現局面 1 ノード | 盤面ハイライト + コントロールパネル | 初心者向け安全手ヒント |
| **Curator profile** (Phase 186) | 棋譜横断 (弱点) | beginner hint に統合 | 自分の弱点パターンを振り返る |

これらは独立した経路ですが、**同じ raw data** (KataGo の
`scoreLead` / `scoreLoss` / `winrate` / `scoreStdev` / `policy` /
`ownership`) を異なる切り口で見ているだけです。Karte JSON の
`important_moves` セクションが共通の出発点になります。

### 7.6.2 重要度レベル (B1) — 「緩め / 標準 / 厳しめ」

`mykatrain_settings.important_moves_level` で棋力別に切替:

| レベル | 閾値 | 最大件数 | 向いている棋力 |
|--------|------|---------|----------------|
| `easy` (級位者向け) | 1.0 | 10 | 30級〜11級 (大きな損失のみ) |
| `normal` (標準) | 0.5 | 20 | 10級〜5段 (デフォルト) |
| `strict` (段位者向け) | 0.3 | 40 | 6段以上 (細かいヨセも拾う) |

設定方法: 解析タブ → **重要局面 重要度レベル** ラジオボタン。
Karte export 時にこのレベルが `pick_important_moves` の `level`
引数として伝わり、`critical_3` にも反映されます。

### 7.6.3 Critical 3 (B2) — 「手元の Karte に何件載せる?」

`mykatrain_settings.critical_3_max_moves` で 1〜10 件に調整
(デフォルト 3 = Phase 50 ベースライン)。

解析タブ → **Critical 3 件数** スピナー。

### 7.6.4 重要局面リスト popup (D1) — 「棋譜全体の俯瞰」

(Phase 248-γ-D1 で実装予定)

未実装。現在 GUI 上では **現在のノードの beginner hint のみ** が
コントロールパネルに表示されます (see §7.6.5)。
過去の重要局面を一覧する popup は計画中。

### 7.6.5 Beginner Hint — 「今の局面、危険じゃない?」

`beginner_hints.enabled` で 4 段階の優先順位 (Phase 91) と
7 系統のサマリ hint (Phase 179 + 182 + 186) を制御:

| 系統 | カテゴリ数 | 役割 |
|------|------------|------|
| 構造 (Phase 91) | 4 | self_atari / ignore_atari / missed_capture / cut_risk |
| Meaning tag (Phase 92) | 6 | low_liberties / self_capture_like / bad_shape / heavy_group / missed_defense / urgent_vs_big |
| ミス (Phase 179) | 3 | mistake_blunder / mistake_mistake / mistake_good (好手称賛) |
| 自由度 (Phase 179) | 3 | only_move / narrow / wide |
| 難易度 (Phase 179) | 2 | tricky / calm |
| KataGo 不確実 (Phase 179) | 1 | katago_uncertain |
| 所有 (Phase 182) | 1 | ownership_dominant |
| Policy (Phase 182) | 2 | policy_confident / policy_conflict |
| Curator (Phase 186) | 1 | curator_weak_axis |

**Phase 248-C4 で追加**: `compute_beginner_hint(aggregate=True)`
を使うと、全ディテクタを実行して **最高 severity** のヒントを返します
(従来は short-circuit で最初に見つかったヒントを返していた)。

### 7.6.6 Curator profile — 「自分の弱点パターン」

棋譜全体での弱点集計 (`mykatrain_settings.curator_hint`) を beginner
hint に統合。Curator が出した「よく出る mistake タグ」が現在の局面の
`meaning_tag_id` と一致すれば **CURATOR_WEAK_AXIS** ヒントが
出ます。バッチ解析 (`batch/` 配下) を 1 回回す必要あり。

### 7.6.7 上級者向けパラメータ (β3) — 「内部定数を JSON でいじる」

`mykatrain_settings.advanced_params` 配下で 6 つの感度パラメータを
オーバーライド可能。**JSON 直接編集**のみで UI からは触れません。

```json
{
  "mykatrain_settings": {
    "advanced_params": {
      "threshold_score_stdev_chaos": 25.0,
      "complexity_discount_factor": 0.5,
      "diversity_penalty_factor": 0.9,
      "min_loss_display": 0.5,
      "beginner_hint_min_visits": 200,
      "katago_uncertain_min_visits": 500
    }
  }
}
```

| キー | デフォルト | 効果 |
|------|----------|------|
| `threshold_score_stdev_chaos` | 20.0 | 複雑局面判定の閾値 (KataGo scoreStdev) |
| `complexity_discount_factor` | 0.3 | 複雑局面の重要度削減率 (0.3 = 30% 残す) |
| `diversity_penalty_factor` | 0.85 | 同タグ重複ペナルティ (3 回目で 61% に減点) |
| `min_loss_display` | 0.3 | フォールバック時の最小損失 (これ未満は無視) |
| `beginner_hint_min_visits` | 100 | beginner hint 信頼度ゲート |
| `katago_uncertain_min_visits` | 300 | katago_uncertain 専用ゲート |

範囲外の値・型違い・欠損は **自動的にデフォルトへスナップバック**
(UI を汚さない)。`get_default_internal_params()` で
デフォルトの frozen copy を取得可能 (`from katrain.core.analysis import ...`)。

### 7.6.8 よくある質問

**Q. 棋譜並べ (kifunarabe) 中は beginner hint は出る?**
A. 出ます。`beginner_hints.enabled` が ON で、かつ
`play_analyze_mode != MODE_PLAY` (棋譜並べ中は review モード)
であれば、構造的 hint は表示されます。

**Q. Beginner hint と Critical 3 は何が違いますか?**
A. **時間軸** が違います。Beginner hint は **現在のノード** を
対象に 23 カテゴリの 1 つを返します。Critical 3 は **棋譜全体**
から top-N (1〜10) のミスを抽出して Karte JSON に書き出します。

**Q. Karte を export しても critical_3 が空でした。**
A. Phase 248-F1 で `KeyError` 等の例外を INFO ログに出すように
なりました。KataGo 起動直後の未解析ノードや、SGF が壊れている
ケースで発生します。`kata.log` を確認してください。

**Q. importance_score が出てきません。**
A. KataGo 解析が完了していないノードでは
`move.importance_score = None` になります。ライブ対局中は
数手遅れることがあるので、ナビゲーション後に少し待ってください。

**Q. advanced_params を JSON で書き換えるのは怖い。**
A. 範囲外 / 型違いは自動フォールバックされるので、最悪でも
デフォルト挙動に戻ります。バックアップとして `advanced_params`
を空 dict に戻せば確実にリセットできます。

**Q. 9路で候補手が出ない**
A. 9路で STRONG は `max_pv_length=3` まで縮小。それでも出ない場合は
`pv_filter_level=off` で完全 OFF にしてみて、候補手自体があるか確認。

**Q. AUTO にしてるのに思ったより絞られる**
A. `player_rank` が高段位帯 (5d+) だと自動で STRONG / EXPERT に
マップされます。手動で `medium` を選ぶと上限 8 件で固定できます。

---

## 9. Post-54 (Phase 55–65) 新機能ガイド

### 9.1 棋風診断（Style Archetype）

**アクセス方法**: myKatrain → カルテ出力
**表示されない条件**: 解析データが不十分な場合

| タイプ | 特徴 | 推奨学習方針 |
|--------|------|-------------|
| 剛腕ファイター | 戦闘軸↑、安定性↓ | 形勢判断と収束タイミング |
| 宇宙建築家 | 序盤↑、終盤↓ | ヨセの精度向上 |
| 精密機械 | 終盤↑、戦闘↓ | 戦いの仕掛け方 |
| 忍者サバイバー | 安定性↑、序盤↓ | 布石研究 |
| AIネイティブ | 認識力↑ | バランス調整 |
| バランスマスター | 全軸均等 | 弱点軸の特定と補強 |

**Confidence値**: 上位2つのアーキタイプスコアの差から算出。値が高いほど判定が明確。

---

### 9.2 5軸レーダー（Skill Radar）

**アクセス方法**: myKatrain → スキルレーダー、またはカルテ内「Radar」セクション
**表示されない条件**: 分類データがない場合

| 軸 | 評価内容 |
|----|---------|
| Opening | 布石・定石選択 |
| Fighting | 戦闘・読み |
| Endgame | ヨセ・計算 |
| Stability | 局面安定化 |
| Awareness | 複雑局面認識 |

**Tier 1-5**:
- **Tier 5**: 最高評価
- **Tier 1**: 要改善

> ⚠️ Tierは相対的な評価バンドであり、直接的な段級位への換算ではありません。

---

### 9.3 時間分析（Pacing & Tilt）

**アクセス方法**: myKatrain → カルテ出力 →「Time Management」セクション
**表示されない条件**: SGFに時間タグ（BL/WL）がない場合

| マーク | 意味 |
|--------|------|
| 🐇 | 早打ち（メディアンより大幅に短い） |
| 🐢 | 長考（メディアンより大幅に長い） |
| 🔥 | ティルトエピソード中の手 |

**ティルトエピソード**: 大きな損失が連鎖的に発生した区間を検出します。
- トリガー手の後、一定ウィンドウ内で損失が続くとエピソードとして記録
- 正の損失データが少なすぎる場合は検出を無効化

> 閾値・ウィンドウサイズは現在のヒューリスティック値であり、将来変更される可能性があります。

---

### 9.4 リスク管理分析（Risk Context）

**アクセス方法**: myKatrain → カルテ出力 →「Game Management」セクション
**表示されない条件**: 形勢判定に十分なデータがない場合

**形勢判定**:
- **WINNING**: 優勢（勝率・リードが一定以上）
- **LOSING**: 劣勢（勝率・リードが一定以下）
- **CLOSE**: 接戦（それ以外）

**振る舞い分類**:
| 振る舞い | 意味 |
|---------|------|
| Solid | 形勢安定を優先 |
| Risk Taker | 複雑化を狙う |
| Fighter | 劣勢から積極的に戦う |
| Resigned | 劣勢で消極的 |

**(estimated) ラベル**: 一部のデータが欠落しており、代替推定を使用した場合に表示されます。

> ⚠️ 形勢判定の閾値は現在のヒューリスティックであり、置碁や序中盤では判定が不安定になることがあります。

---

### 9.5 開発者向け参照: 棋譜スコアリング（Curator）

> ⚠️ **この機能はUIが未実装です**（JSON出力のみ）。一般ユーザー向けではありません。

**生成条件**: バッチ処理をプログラム的に呼び出す（`generate_curator=True`）

**出力ファイル（例）**:
- `curator_ranking_*.json`: 棋譜適性ランキング
- `replay_guide_*.json`: 学習ガイド用ハイライト局面

> 実際のファイル名・出力先は実行ログまたは設定で確認してください。

**主要フィールド**:
- `score_percentile`: バッチ内での相対順位
- `needs_match`: ユーザー弱点軸との関連度
- `recommended_tags`: 改善ポイントのタグ

この機能の詳細については、`katrain/core/curator/` のソースコードを参照してください。
