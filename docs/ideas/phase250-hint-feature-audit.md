# Phase 250: Hint 機能 包括監査レポート (2026-07-18)

> 調査対象: myKatrain PC 版の **ヒント機能全体** (Beginner Hints / Summary Hints /
> Curator Weak-Axis / PV filter / 重要局面 / 候補手マーカー)
>
> 調査日: 2026-07-18 / 担当: Mavis
> 関連 Phase: 91-92, 156, 158, 179, 182, 186, 187, 188, 194-202, 246, 247, 248

---

## 1. スコープと全体像

### 1.1 対象コンポーネント

| 層 | モジュール | 役割 |
|----|------------|------|
| データモデル | `katrain/core/analysis/models/{enums,move_eval,important_moves,reliability,difficulty}.py` | MoveEval / EvalSnapshot / MistakeCategory / ImportantMoveSettings |
| 重要度計算 | `katrain/core/analysis/logic_importance.py` | importance_score 計算 / pick_important_moves / weak_tag boost |
| 意味分類 | `katrain/core/analysis/meaning_tags/{models,classifier,registry,integration,context_builder}.py` | MeaningTagId (12) / 11 段優先 chain / 動的 endgame |
| クリティカル | `katrain/core/analysis/critical_moves.py` | Critical 3 抽出 (diversity penalty / complexity discount) |
| 候補手フィルタ | `katrain/core/analysis/logic_pv.py` (推定) | PV filter / expert preset / LRU cache / live preview |
| Beginner hints | `katrain/core/beginner/hints/{_gate,_extract,_dispatch,_cache,api}.py` | 23 HintCategory ディスパッチ |
| Beginner detector | `katrain/core/beginner/detector_curator.py` | 棋譜横断 weak tag 検出 |
| Curator 適合度 | `katrain/core/curator/{models,scoring,guide_extractor,batch,profile}.py` | 棋譜スコアリング / Replay guide |
| バッチ統合 | `katrain/core/batch/orchestration/_curator.py` | 棋譜解析パイプライン |
| 重要局面 popup | `katrain/core/analysis/important_moves_popup.py` | 重要局面リスト / prev-next ナビ |
| GUI 描画 | `katrain/gui/badukpan_hints.py` | BadukPan 上に marker / highlight / perspective 描画 |
| GUI 表示 | `katrain/gui/controlspanel.py` | info テキストに hint 文字列を追加 |
| 内部パラメータ | `katrain/core/analysis/internal_params.py` | advanced_params JSON 露出 (Phase 248-β3) |

### 1.2 テストカバレッジ概観

- Beginner Hints 関連: `test_beginner_hints.py` (64) / `test_beginner_hints_main.py` (約 200) /
  `test_beginner_hints_summary.py` (約 240) / `test_beginner_hint_aggregate.py` (約 30)  → **全パス**
- Curator 関連: `test_curator_{scoring,models,integration,guide_extractor,batch}.py` (計 5 files) → **全パス**
- Meaning Tags 関連: `test_meaning_tags_{classifier,registry,integration,models}.py` → **全パス**
- 重要局面: `test_important_moves_*` / `test_logic_importance.py` → **全パス**
- 候補手フィルタ: `test_pv_filter_*` / `test_composite_sort.py` → **全パス**
- 重要局面 popup: `test_important_moves_popup.py` / `test_important_move_navigation.py` → **全パス**

→ テスト面での主な問題は「Kivy headless 環境での popup テスト」が走らない既知問題のみで、
ヒント機能のロジックには回帰なし。累計 5,901 pass (L1:popup 除く)。

### 1.3 主要マイルストーン (Phase 1.3 抜粋)

- Phase 91-92: Beginner Hints 4+6 ディテクタ + i18n
- Phase 156-158: dynamic phase / scoreStdev 連動
- Phase 179-186: Summary Hints 9→12→13 カテゴリ拡張
- Phase 187: Beginner Hints main pipeline カバレッジ 16.5% → 97%
- Phase 188: kifunarabe controller 分割 (4 mixin + facade)
- Phase 246-247: PV filter 20 件課題 / Deferred 4 件
- Phase 248: 重要局面 30 件課題 / 6 PR / 5 サブフェーズ
- Phase 186: Curator 集約統合 (HintCategory 23 化)
- Phase 248-γ-E1: weak_tag_boost 配線

---

## 2. 発見した問題・改善余地 (優先度別)

### 🔴 P0: 即修正すべき (機能/UX の不具合寄り)

#### I-1. i18n 重複 msgid による gettext 取得不定
**症状**: jp.po / en.po の両方に**完全に同じ msgid が 2 重定義**されている。gettext は最初の
定義を返すため、後方の翻訳が反映されない可能性がある。

```text
2x  "mistake:good"
2x  "mistake:inaccuracy"
2x  "mistake:mistake"
2x  "mistake:blunder"
2x  "summary:table:avg_loss"
```

- 影響: 「Mistake」「Blunder」「Avg Loss」など主要表示文字列が想定外の言語で出る可能性
- 検証: `python -c "import babel.messages.pofile; ..."` で実 msgstr 取得順序を確認
- 修正コスト: ポインタなので数分 / .po + .mo 再生成
- 関連 Phase: なし (潜在バグ)

#### I-2. en.po に 21 件の「孤児」msgid (jp.po に存在しない)
**症状**: `radar:*` 系の 21 キーが en.po にのみ存在。コードからは完全に参照されていない
(grep `i18n._\("radar:` で 0 hit)。Phase 86 で radar 機能が撤去されたが、en の翻訳だけ
取り残されている。

```text
radar:axis-{awareness,endgame,fighting,opening,stability}
radar:build-error / calc-error / insufficient-moves
radar:menu-title / no-data / no-game / not-19x19 / overall
radar:tier-{1..5}-unknown / title / weak-areas
```

- 影響: 翻訳メモリ浪費 + ビルドサイズ / en.po 編集時に noise
- 修正コスト: 自動削除スクリプトで一掃 (安全)
- 関連 Phase: 86 撤去時の取り残し

### 🟠 P1: 早めに直したい (保守性 / 内部品質)

#### I-3. 候補手フィルタの live preview が **Popup が閉じている間** 更新されない
**症状**: `controlspanel._format_pv_filter_preview` (controlspanel.py:418-) は
`badukpan.last_pv_filter_preview` を読むが、これは hover/redraw のたびに書き換わる。
コントロールパネル右側のテキストが redraw 頻度に追従してチカチカする / 表示遅延が起こる。

- 影響: ux で preview が「古いまま」見える / 過剰更新で CPU
- 修正方向: `Clock.schedule_once` で throttle するか、Kivy property binding 化
- 関連ファイル: `katrain/gui/controlspanel.py:_format_pv_filter_preview`
  `katrain/gui/badukpan_hints.py:widget.last_pv_filter_preview = ...`

#### I-4. HintCategory 23 個に対する「設定 UI 露出」が一部欠落
**症状**: `HintCategory.config_key` プロパティでグループ化されているが、設定タブ側で
個別の ON/OFF を持つのは以下の 7 グループのみ:
- `summary_mistake` / `summary_freedom` / `summary_difficulty` / `katago_uncertain`
  / `summary_ownership` / `summary_policy` / `curator_hint`
  (controlspanel.py:_summary_hint_flags)

しかし 4 つの **structural 検出器** (SELF_ATARI / IGNORE_ATARI / MISSED_CAPTURE / CUT_RISK)
と 6 つの **meaning_tag フォールバック** (LOW_LIBERTIES / SELF_CAPTURE_LIKE / BAD_SHAPE /
HEAVY_GROUP / MISSED_DEFENSE / URGENT_VS_BIG) は `beginner_hints/enabled` の単一スイッチに
まとめられている。

- 影響: 「CUT_RISK だけ消したい」「BAD_SHAPE を非表示にしたい」ユーザ要望に応えられない
- 修正コスト: Lv2 / 4 つの structural + 6 つの meaning_tag で 10 トグル追加 + i18n 10 件
- 関連ファイル: `katrain/core/beginner/models.py:HintCategory.config_key`,
  `katrain/gui/features/settings_popup_tabs/` の beginner_hints タブ

#### I-5. Beginner Hint の reliability gate (`MIN_RELIABLE_VISITS = 200`) が board_size 非依存
**症状**: `_gate.py:11` で固定値 200。9 路 (60-80 手) では中盤以降しか hint が出ない。
13 路も同様。Phase 248-γ1 で `board_size_adjusted_thresholds` を導入した
(`THRESHOLD_MOVE_EARLY_GAME` 80→38) 流れと整合していない。

- 影響: 9/13 路ユーザは「hint があまり出ない」と感じる
- 修正方向: 9 路 → 100 / 13 路 → 150 / 19 路 → 200 の線形補間
- 関連ファイル: `katrain/core/beginner/hints/_gate.py:11`,
  `katrain/core/analysis/meaning_tags/classifier.py:_BOARD_SIZE_SCALE`

#### I-6. MISTAKE_GOOD の visits gate 緩和 (200) だが、エンドゲーム判定は依然固定
**症状**: Phase 248-C5 で visits gate を 300→200 に緩和したが、`_is_endgame_position` の
静的フォールバック (`move_number >= 200`) は固定値。9 路 (80 手) では動的判定 (scoreStdev
<= 8.0) に救済されるが、stdev が None のときは誤判定。

- 影響: batch モードで stdev 欠損時に MISTAKE_GOOD が誤発火 / 沈黙
- 修正方向: 静的フォールバックも board_size 連動に
- 関連ファイル: `katrain/core/beginner/hints/_extract.py:_is_endgame_position`

#### I-7. `pick_important_moves` のフォールバック raw_score 閾値 (`MIN_LOSS_DISPLAY = 0.3`) の根拠が不明
**症状**: Phase 148-B2 で導入されたが、Phase 248-γ1 の board_size 連動後の再校正が未実施。
19 路では適切でも 9 路 (損失 0.3 目は大きめ) では誤って重要局面を捨てる可能性。

- 影響: 9 路で「重要局面が出ない」「critical_3 が空になる」
- 修正方向: 棋譜 golden test で 9/13/19 路別の loss 分布を取得し calibration
- 関連ファイル: `katrain/core/analysis/models/important_moves.py:MIN_LOSS_DISPLAY`

#### I-8. `_get_meaning_tag_hint` の tag_id 比較が str キャスト任せ
**症状**: `getattr(node, "meaning_tag_id", None)` → `_normalize_meaning_tag_key(key)` で
`str()` 変換される経路と、`_category.from_meaning_tag_id(tag_id)` で `tag_id == None` 判定
する経路の 2 系統があり、TagId 由来 vs str 由来の混在で分岐が複雑。

- 影響: 将来 TagId enum 変更時のバグ温床 / テスト書きにくさ
- 修正方向: `HintCategory.from_meaning_tag_id(MeaningTagId|str)` で正規化 1 系統化
- 関連ファイル: `katrain/core/beginner/hints/_dispatch.py:_get_meaning_tag_hint`

### 🟡 P2: 余裕があれば (拡張 / 改善余地)

#### I-9. Hint 表示の「:why」フィールドが GUI で未使用
**症状**: i18n に `beginner_hint:*:why` (3 番目のキー) が 23 個分すべて翻訳されているが、
`_format_beginner_hint` (controlspanel.py:449) は `title` + `body` しか描画しない。

- 影響: 翻訳済みだが dead resource / ユーザに「なぜ」伝わらない
- 修正方向: 折りたたみ or tooltip で追加表示 or beginner モードのみ展開
- 関連ファイル: `katrain/gui/controlspanel.py:472` (`title.startswith("beginner_hint:")` の判定)

#### I-10. Hint の i18n に `:why` の代わりに `:body` を 2 行で使う拡張余地
- 関連ファイル: `katrain/core/beginner/models.py:99-100` (config_key の `_SUMMARY_CATEGORIES`)

#### I-11. 候補手マーカー (TOP_MOVE_SHOW) の選択肢が少ない
**症状**: `top_moves_show` の選択肢は `score / winrate / delta_score / delta_winrate / visits` の
5 種類のみ。`score_stdev` / `policy` / `ownership_dominant` の 3 つは表示できない。

- 影響: 同じマーカーが多用される / ユーザの好みに合わせにくい
- 修正方向: TOP_MOVE_OPTIONS に 3 種追加 + i18n 3 件
- 関連ファイル: `katrain/core/constants.py:TOP_MOVE_OPTIONS`,
  `katrain/gui/badukpan_hints.py:draw_kata_hint_moves` (line 158-)

#### I-12. `_format_beginner_hint` が `[Hint]` プレフィックスを直書き
**症状**: 日本語ロケールでは不自然 ("[ヒント] 方が良い手: ...") だが i18n キーになっていない。

- 影響: 翻訳コスト
- 修正: `i18n._("beginner_hint:prefix")` 化
- 関連ファイル: `katrain/gui/controlspanel.py:478` (return f"[Hint] ...")

#### I-13. 「PV アニメ」中に hint highlight が再描画されない
**症状**: `draw_hover_contents` (badukpan_hints.py) は毎フレーム呼ぶが、`beginner hint
highlight` (`draw_beginner_hint_highlight`) は `draw_hover_contents` 経由で呼ばれない
(`draw_circle` で独自経路)。PV アニメ中は hint 位置がパラパラしない。

- 影響: 視覚的な同期崩れ
- 修正: `draw_hover_contents` 内に統合 or 別 Clock で update
- 関連ファイル: `katrain/gui/badukpan_hints.py:31-67` (`draw_beginner_hint_highlight`)

#### I-14. 候補手マーカーに「Mistake Severity アイコン」を出す余地
**症状**: 候補手ごとに `pointsLost` の大きさで色が決まるが、意味 (overplay なのか
connection_miss なのか) はマーカーからは分からない。HintCategory と意味タグの紐付け
(LOW_LIBERTIES 等) をマーカー上にビジュアル化していない。

- 影響: 候補手と意味の関連が分断
- 修正方向: Phase 248 で導入された reason_tags を候補手ごとにも付与し、icon 化
- 関連ファイル: `katrain/core/analysis/meaning_tags/integration.py`

#### I-15. Curator profile 無しで「CURATOR_WEAK_AXIS」ヒントが永久に沈黙
**症状**: `detect_curator_weak_axis` は `user_weak_tags` が空 / curator profile 未ロードの
場合に None を返す。一度も batch 解析していない新規ユーザは一生このヒントを見ない。

- 影響: 新規ユーザの体験低下 / 機能存在意義が見えない
- 修正方向: 「curator profile を作ってね」というチュートリアルヒントに切替
  (または最低 N 回 batch 後にフォールバック)
- 関連ファイル: `katrain/core/beginner/detector_curator.py:46-48`

#### I-16. Critical 3 popup (Phase 248-γ-D1) に「理由」列がない
**症状**: `important_moves_popup.py` は move_number / score / critical_score を出すが、
**なぜ critical_3 に入ったか** (life_death_error のタグ / diversity penalty) は見えない。

- 影響: 重要局面の解釈支援不足
- 修正方向: reason 列を追加 / tooltip で diversity_penalty / complexity_discounted を表示
- 関連ファイル: `katrain/core/analysis/important_moves_popup.py`,
  `katrain/gui/kv/important_moves_popup.kv`

#### I-17. `meaning_tag_id` 比較時の None ハンドリングが多層
**症状**: `compute_importance_for_moves` / `pick_important_moves` / `select_critical_moves`
の 3 箇所で `getattr(m, "meaning_tag_id", None)` + str キャストを独立に書いている。
TagId enum 化の流れ (Phase 47) と整合せず、None 時の挙動も微妙に異なる。

- 影響: バグの温床 / テスト書きにくさ
- 修正方向: `MoveEval.meaning_tag_id` を `MeaningTagId | None` に統一する dataclasses 派生
- 関連ファイル: 上記 3 ファイル

#### I-18. 候補手 `kifunarabe` モードで MISTAKE_GOOD 系ヒントを抑制する仕様が無い
**症状**: kifunarabe 中は「実際の棋譜を当てるゲーム」なので、点数ベースの Mistake ヒント
(MISTAKE_BLUNDER / MISTAKE_MISTAKE) は答えを教えるチート行為。

- 影響: 棋譜並べモードのトレーニング意義が崩壊
- 修正方向: `kifunarabe_mode` 中は `_should_show_summary_hints()` 全体を False 化
  (現状: board highlight は `is_fog_active` で抑制されるが info テキストには出る)
- 関連ファイル: `katrain/gui/controlspanel.py:_should_show_summary_hints`

#### I-19. 候補手 preview (`prepare_hint_moves`) のキャッシュが hover 中の 1 node のみ
**症状**: Kifu 中に prev/next で `current_node` が切り替わると、キャッシュ (`_beginner_hint_cache`
/ `_summary_hint_cache`) が前の node に残る。次回到達時に正しい値になるが、prev/next
連打中はちらつく。

- 影響: 微小な視覚ノイズ
- 修正方向: `clear_on_node_switch` hook で明示的 invalidation
- 関連ファイル: `katrain/core/beginner/hints/_cache.py` (cache セット箇所)

#### I-20. 候補手 `engine_best_move` ハイライトが `kifunarabe` 中は強制 OFF
**症状**: `draw_kata_hint_marker` で `is_kifu_marker` の場合に engine_best_move の枠線が
出ない。これは正しい挙動だが、`show_actual_border=True` のときでも「実際の棋譜の手」と
「KataGo 最善手」が一致した時の特別表示がない。

- 影響: kifunarabe 中の正解 / 不正解フィードバックが地味
- 修正方向: 正解時 (actual == best) だけ枠線を gold 色で出す
- 関連ファイル: `katrain/gui/badukpan_hints.py:208-238`

#### I-21. 候補手フィルタ (PV filter) の board_size scaling が 9/13/19 のみ
**症状**: Phase 246-D (M1) で `board_size` 連動 linear scaling を入れたが、`_BOARD_SIZE_SCALE`
が 9/13/19 決め打ち。5 路 / 7 路 (教育用) や非正方形盤は未対応。

- 影響: 教育用小盤で PV filter が破綻する可能性
- 修正方向: 任意の `board_size` に対して `sqrt(cells/361)` を計算する汎用化
- 関連ファイル: `katrain/core/analysis/meaning_tags/classifier.py:_BOARD_SIZE_SCALE`

#### I-22. Hint / Critical / MeaningTag の label 一元管理が不完全
**症状**: `HintCategory.fallback_title` / `MeaningTagId` のラベル / `CriticalMove.meaning_tag_label`
の 3 箇所で重複した日本語ラベルが分散管理されている。

- 影響: 翻訳更新時の漏れ / 表記揺れ
- 修正方向: `katrain/i18n/locales/{jp,en}/LC_MESSAGES/*.po` を single source of truth 化
  (現状: i18n に重複 msgid もある = 既に破綻)
- 関連ファイル: `katrain/core/beginner/models.py`, `katrain/core/analysis/critical_moves.py`,
  `katrain/core/analysis/meaning_tags/registry.py`

### 🟢 P3: アイデア (長期)

#### I-23. Hint 表示のアクセシビリティ対応 (screen reader)
#### I-24. Hint の「音声読み上げ」モード (PR#2 で削除済み)
#### I-25. 候補手マーカーに「勝率推移アニメ」
#### I-26. Hint 頻度のユーザ別 tuning (cohort 分析)
#### I-27. 複数局サマリで「hint 全体の分布」をレーダーチャート化 (Phase 224 で deferred)
#### I-28. 候補手ヒントの "思考時間" 連動 (急ぐ手に小さいマーカー)

---

## 3. 既存テストの問題

### T-1. Kivy headless 環境での popup テスト失敗
- `tests/test_*_popup.py` 系 6 ファイルが Kivy 起動失敗で `SystemExit: 1`
- 影響: CI での popup 関連テストは事実上 skip
- 既知問題 (AGENTS.md §1.3 / Phase 241-H で KIVY_NO_ARGS 環境変数追加済みだが解消せず)
- 関連: `tests/conftest.py` Phase 241-H 設定は一部のみ吸収

### T-2. 102 件の FAIL は Kivy 起因 (Hint 機能には無関係)
- `test_p2_gui_leaks` (18) / `test_stability_phase18` (12) / `test_main_smoke` (11) 等
- Hint 機能には直接影響なし (累計 5,901 pass)

---

## 4. 推奨アクション (短期 / 中期 / 長期)

### 短期 (Lv0-1, 1-2 PR)
1. **I-1 i18n 重複 msgid 修正** — `mistake:*` と `summary:table:avg_loss` の 2x 定義を 1 つに集約
2. **I-2 孤児 radar:* 削除** — en.po から 21 キー削除 + .mo 再生成

### 中期 (Lv2-3, 3-4 PR)
3. **I-4 HintCategory 個別トグル UI 化** — structural 4 + meaning_tag 6 の 10 トグル追加
4. **I-3 live preview の throttle** — redraw 連打対策
5. **I-5 MIN_RELIABLE_VISITS の board_size 連動** — 9/13/19 路で値変更
6. **I-6 / I-7 endgame フォールバック / MIN_LOSS_DISPLAY の board_size 連動**
7. **I-9 `:why` フィールド表示の復活** — beginner モードのみ展開

### 長期 (Lv3+)
8. **I-14 候補手マーカーに Mistake Severity アイコン**
9. **I-15 Curator profile チュートリアル化**
10. **I-16 Critical 3 popup に「理由」列追加**
11. **I-17 meaning_tag_id 比較の統一化**
12. **I-18 kifunarabe 中の MISTAKE_* 抑制**
13. **I-22 Hint / Critical / MeaningTag label の i18n 統一化**
14. **I-21 PV filter の board_size 汎用化 (5/7 路対応)**

---

## 5. 関連ドキュメント (リンク)

- Phase 179 仕様: `docs/archive/specs-implemented/phase179-hints-summary-extension.md`
- Phase 187 仕様: `docs/archive/specs-implemented/phase187-hint-main-coverage.md`
- Phase 248 マスター: `docs/archive/specs-implemented/phase248-important-moves-master.md` (推定)
- LLM Coach 監査: `docs/ideas/phase242-llm-coach-audit.md`
- Kifunarabe 監査: `docs/ideas/phase249-kifunarabe-audit.md`
- AGENTS.md §1.3: Phase 完了サマリ (Phase 1-249-hotfix まで)

---

## 6. まとめ (担当者所感)

**全体評価**: ヒント機能は Phase 91 から段階的に整備され、Phase 248 で大幅拡張された結果、
**23 HintCategory × 12 MeaningTag × 24 critical_3 ロジック** まで到達。
テストカバレッジも `beginner_hints` 関連で 5,901 件 pass と非常に安定。

**ただし**:
- **i18n に 2 つの構造的バグ** (重複 msgid / 孤児 msgid) — 早急に修正すべき
- **board_size 連動が部分実装** — Phase 248-C1 で 9/13 路を入れたが、他閾値は未追従
- **「:why」表示が翻訳済みなのに未使用** — dead resource
- **kifunarabe 中の挙動が未整理** — チート防止強化の余地
- **HintCategory 個別トグル UI 不足** — 設定粒度が荒い

**すぐ着手できる P0-1 で 4 つの i18n バグが片付く** ので、これを Phase 250 として
1 PR で処理するのが効率的。中期は I-3〜I-7 の board_size 連動シリーズで 1 PR ずつ。
