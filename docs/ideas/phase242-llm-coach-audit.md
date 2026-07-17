# LLM Coach 機能 詳細調査レポート

> **調査日**: 2026-07-17
> **対象**: myKatrain PC版の LLMコーチ機能全体
> **スコープ**: `katrain/core/coach/*` + `katrain/gui/popups/llm_coach_popup.py` + `katrain/gui/features/llm_coach.py` + `katrain/gui/kv/llm_coach_popup.kv` + 関連 i18n / テスト

## 1. 全体構成の俯瞰

LLMコーチ機能は **3 層構造** で実装されている:

```
┌─────────────────────────────────────────────────────────────────┐
│  GUI 層                                                          │
│  katrain/gui/popups/llm_coach_popup.py  (1181行, BoxLayout)     │
│  katrain/gui/kv/llm_coach_popup.kv      (200行, KVレイアウト)    │
│  katrain/gui/features/llm_coach.py      (700行, 薄いラッパー)   │
├─────────────────────────────────────────────────────────────────┤
│  CLI / Validation 層                                             │
│  katrain/core/coach/cli.py              (CLI 17 テスト)          │
│  karte_detector.py + 17 テスト                                     │
│  calibration_fixtures.py + 39 テスト (golden)                     │
├─────────────────────────────────────────────────────────────────┤
│  Core 層 (Kivy 非依存)                                           │
│  master_db.py     §0+§1 (CoachMode / ToneVoice / Kansai dict)     │
│  lexicon.py       116 エントリ YAML ローダー                       │
│  symptom_index.py 40 症状定義 (21 auto / 19 llm-required)        │
│  tones.py         select_voice / Kansai markers / prohibited      │
│  prompt_builder.py Karte → LlmPrompt 変換                          │
│  llm_validator.py LLM 出力検証 (5 系統)                           │
│  json_type.py     karte / summary 自動判別 + extractor             │
│  summary_prompt_builder.py   複数局サマリ用プロンプト             │
│  summary_validator.py        複数局サマリ用検証器                 │
│  sgf_player_info.py          SGF BR/WR 抽出                       │
└─────────────────────────────────────────────────────────────────┘
```

**テストカバレッジ**: 17 ファイル / 計 1100+ ユニットテスト (全合格)
**i18n**: 42 キー使用 / 59 キー定義 (jp+en 完備, 翻訳ギャップなし, 空 msgstr なし)
**最終更新**: Phase 241 (2026-07-17)

---

## 2. 重要度別の問題一覧

### 🔴 **A. 高優先度 (実害あり / テスト失敗 / データ不整合)**

#### A-1. **popup テスト 94 件が headless 環境で失敗する**
- **症状**: `test_llm_coach_popup.py` の 96 テスト中 94 が `Kivy base.py:139 SystemExit: 1` でクラッシュ
- **原因**: KivyMD の `material_resources.py` がモジュールロード時に `dp(400)` を呼び、ヘッドレス環境でも Window を要求する。`SDL_VIDEODRIVER=dummy` だけでは不十分
- **影響**: CI で popup ロジックの大半が検証できていない。`conftest.py` の Phase 241-H 設定でも Windows + 開発環境では通らない
- **対策案**:
  - Lv1: 開発者環境のみで実行する想定で `pytest.skip` を環境変数ベースに戻す (Phase 241-H の撤回は要議論)
  - Lv2: KivyMD の `dp()` 呼び出しを遅延化 (KivyMD 側の修正待ち)
  - Lv3: popup ロジックを `core/coach/` 層に Pure Python として移植し、popup は薄いラッパーに
  - **推奨**: Lv3 一部適用 — `_populate_rank_and_perspective` などのロジックを Pure 関数化、テストは headless で実行

#### A-2. **9 件の LLM-required 症状が `related_lexicon_ids` 未設定**
- **症状**: 全 40 症状中 21 の auto-detected 症状は lexicon 紐付け済みだが、9 件の LLM-required 症状が空タプル
- **該当症状**:
  ```
  グループ7 時間:   time_pressure_loss, time_misallocation, time_drain
  グループ9 検討:   shallow_review
  グループ10 AI:    ai_overload, copy_without_understanding
  グループ11 ティルト: tilt_discouragement, tilt_chain, tilt_emotional_interference
  ```
- **影響**: プロンプトに Lexicon エントリが注入されない → LLM が標準語彙なしで解説する
- **対策案** (Phase 226-J の続編):
  ```
  time_pressure_loss       → time_management, reading_speed
  time_misallocation       → time_management, endgame_sente
  time_drain               → time_management, critical_moment
  shallow_review           → post_game_review, ai_overload
  ai_overload              → ai_overload, post_game_review
  copy_without_understand. → ai_overload, post_game_review
  tilt_discouragement      → tilt_recovery, mental_state
  tilt_chain               → tilt_recovery, mental_state
  tilt_emotional_interf.   → tilt_recovery, mental_state
  ```
  → Lexicon YAML 拡張と symptom_index 修正が必要 (Lv2)
  - AGENTS.md マーカーにより慎重を要する

#### A-3. **Kansai 3 系統辞書の同期違反 (Phase 226-E E4 が「契約」止まり)**
- **症状**: `tones.py` の docstring で「同期契約」と明言しているが、実態は乖離多数
- **乖離内容** (実データ確認済):

  | 区分 | 内容 |
  |------|------|
  | dict_keys ∉ pair_srcs | `〜ください`, `〜してた`, `〜である/〜だ`, `〜ですか？`, `〜ではない`, `良い/いい` の 6 個 — 辞書は「置換できます」と約束しているが NORM ペアに無い |
  | pair_srcs ∉ dict_keys | `だめ`, `いい`, `してください`, `本当`, `良い`, `している`, `ください` の 7 個 — NORM は置換するが user-facing 辞書に載らない |
  | pair_dsts ∉ markers | `ほんまに` 1 個 — `本当に→ほんまに` の置換は動くが `has_kansai_markers()` が検知できない |
  | dict_values ∉ pair_dsts | `〜やで/〜やねん`, `〜なん？/〜か？`, `〜ちゃう/〜やない`, `〜しとる`, `〜してな/〜しとき`, `めっちゃ/ごっつ` の 6 個 — 辞書掲載の表現が NORM で生成不能 |

- **影響**:
  - AYAKA 文体検出 (`has_kansai_markers`) が漏れる
  - LLM が `ほんま` を使うと検知されるが `ほんまに` を使うと検知されない
  - ユーザ向けドキュメント (`ModeConfig.kansai_dictionary`) と内部実装の不一致
- **対策案** (Lv1):
  - Phase 226-E の契約どおり、3 系統を generator script で自動生成 (要 YamlSchema)
  - 最低限、`ほんまに` を markers に追加 + `〜...` パターンを `_KANSAI_NORMALISATION_PAIRS` に展開

---

### 🟡 **B. 中優先度 (UX 改善 / コード品質 / 軽微バグ)**

#### B-1. `_spinner_text_to_internal` がロケール変更に脆弱
- **症状**: 比較対象が `i18n._()` 経由の文字列。ユーザが言語切替後に spinner を選ぶと "auto" フォールバック
- **対策案** (Lv1): `Spinner.values` 構築時に各値と内部値の対応表 (dict[str, str]) を持つ

#### B-2. `perspective_value` のデフォルト値と実使用値が違う
- **症状**: StringProperty デフォルトは `"auto"` (line 84) だが、spinner 連携後は `""` (空文字) を使用 (line 527, 529, 603)
- **影響**: コードリーディング時の混乱、`""` が sentinel として暗黙的に動作
- **対策案** (Lv0): 定数 `_PERSPECTIVE_AUTO_INTERNAL = "auto"` を導入し全箇所統一

#### B-3. 古い Karte を意図せず自動選択される可能性
- **症状**: `_populate_initial_karte_path` が `find_latest_llm_input_for_ctx` で最新を取得
- **対策案** (Lv1): spinner で「最新 / 過去 N 件から選択」UI 追加
  - Lv3: 直近 N 件のリストを GUI で提示

#### B-4. 検証レポートが 20,000 文字で無音 truncation
- **症状**: `_render_validation_report` が 20k 文字超を切り詰め、末尾に「…(truncated)」を追加
- **対策**: 切り詰めたことを status_label にも表示 (「⚠ 結果 12345 文字省略、原本を確認してください」)

#### B-5. popup に「プロンプトプレビュー」ボタンが無い
- **症状**: ユーザは build → clipboard 経由で LLM に渡すまで内容確認できない
- **対策案** (Lv1): 別 popup で Markdown preview (スクロール可能) ボタンを追加

#### B-6. 検証ボタン押下時の loading 表示がない
- **症状**: validate 中 (LLM 検証は通常 <100ms だが Karte が大きいと遅延)、押下後無反応に見える
- **対策**: ボタン無効化 + spinner overlay

#### B-7. response_input への巨大ペースト対策なし
- **症状**: 10MB の LLM 出力を paste → validate が遅い / UI がフリーズ
- **対策案** (Lv1): paste 時に `_MAX_RESPONSE_CHARS = 100_000` で打ち切り + 警告

#### B-8. dismiss 時のドラフト保存なし
- **症状**: ユーザが長い response を貼り、誤って dismiss すると消失
- **対策案** (Lv1): session 単位 / `output_dir` に `llm_draft.txt` を保存

#### B-9. popup 内のエラーログが貧弱
- **症状**: `ctx.log(..., OUTPUT_ERROR)` 経由でログ出力するが、ユーザに見えない
- **対策案** (Lv1): status_label にエラー詳細 + トレース省略版

#### B-10. prompt body に症状の ja_label が含まれない
- **症状**: LLM は "id: atari_blindness" だけ見て、ja_label を知らない (症状の意味が汲み取りにくい)
- **対策案** (Lv1): `_candidate_hints` を拡張して "id + ja_label + 一行説明" を出力

---

### 🟢 **C. 低優先度 (将来的検討 / 整理)**

#### C-1. `_render_validation_report` (karte) と `_render_summary_validation_report` (summary) の重複
- 共通基底レンダラに統合可能 (Lv1)

#### C-2. SymptomContext / SymptomId の dataclass 化
- frozen=True だが、Dict[str, Any] を渡している箇所が多い
- 段階的に TypedDict 化 (Lv2)

#### C-3. CLI の `cmd_validate` が issues を出力する順序が不安定
- 重大度ソート + 種別グループの追加 (Lv1)

#### C-4. Schema version の表示なし
- popup 上部に "Schema: 3.4" を表示すると デバッグ時に有用 (Lv0)

#### C-5. validation で lexicon mention の二重警告
- `mentioned_lex` (positive) と `off_injection_terms` (negative) は別 kind で出力しているが、popup ではまとめ表示すると見やすい
- グループ化レンダラ追加 (Lv1)

#### C-6. summary prompt の `pct` が per-move なのか per-game なのか曖昧
- 現状 "全体に占める割合=X.X%" と表示 → "(全NN手中)" の補足が親切 (Lv0)

#### C-7. summary_prompt_builder の `loss_progression_block` 集計粒度
- 現状 bucket 単位の合計値のみ表示。bucket 個別内訳も併記可能 (Lv1)

#### C-8. voice_summary が "あやか — 関西弁・親しみ・実利重視" のベタ書き
- i18n key 化すべき (Lv0) — `mykatrain:coach:voice-summary-ayaka`

#### C-9. summary_perspective 関連の __init__ の遅延評価
- `self.summary_players = []` 等が `__init__` で初期化されるが、karte モードでは不要
- 軽量のため影響は微小 (skip)

#### C-10. CLI の `cmd_calibrate` が summary fixture を skip する旨を stderr に出していない
- `--verbose` フラグ追加で verbose mode 化 (Lv1)

#### C-11. tone_inconsistency_tomoko の message に voice.value を埋め込み
- ハードコードされた voice 名で i18n 漏れの可能性 (Lv0)

#### C-12. Symptom.difficulty_range の比較
- `validate_prompt_config` で `mode_order.index(symptom.difficulty_range[0])` を計算しているが、Expert モードで BEGINNER 範囲の symptom が来ると警告される
- これは仕様通りだが、警告文が日本語のみで英語版 i18n なし (Lv0)

#### C-13. SymptomId 列挙体の順序に依存した処理
- Phase 226-F で `current_phase` 追加したが、phase の定義順 ("opening", "middle", "endgame") がハードコード箇所多数
- 共有定数化 (Lv1)

#### C-14. popup の I18NPopup.content が list でラップされる件
- `I18NPopup(size=[dp(900), dp(720)], content=content)` の挙動確認
- ドキュメント化 (Lv0)

#### C-15. Kivy の ObjectProperty 遅延バインド
- 過去 5 回の Phase で対策されている (225.3, 225.5, 226-B B1, 226-B B5, 241)
- 新規追加時は ids-first パターンを使うべき — ガイド化 (Lv0)

#### C-16. `get_latest_report` / `find_latest_llm_input` の内部重複
- `get_latest_report` は全 type, `find_latest_llm_input` は JSON のみ
- 統合可能 (Lv0)

#### C-17. ベンチマーク / 性能計測なし
- `_render_validation_report` / `build_translation_prompt` の実行時間が大規模 Karte で問題になる可能性
- `time.perf_counter` ログ追加 (Lv1)

#### C-18. `_pick_detected_rank` が info.get('black').get('rank') を経由
- info の型バリデーションなし — 壊れた JSON で AttributeError 可能性 (Lv0)

#### C-19. `detect_player_info_for_summary` の "matched" 判定
- `default_user_name == player_name` の厳密一致
- 同姓別人 / 表記揺れ (半角全角) 対応なし (Lv1)

#### C-20. CLI / GUI のエラーメッセージ日本語/英語の統一
- i18n._("mykatrain:llm-coach:...").format(error=str(exc)) で生 exception を埋め込み
- ユーザに stack trace 風メッセージが見える可能性 (Lv0)

#### C-21. popup の size_hint 固定
- 900x720 固定だが、画面が小さいと下部が切れる
- レスポンシブ対応 (Lv2)

#### C-22. popup の rank / perspective spinner が同じ行 (50/50)
- 画面幅 < 600dp では潰れる可能性
- 縦並びフォールバック (Lv1)

#### C-23. popup の workflow-hint が固定 (label 高さ 56dp)
- ロケール切替で文字列長が変わる
- 高さ動的化 (Lv1)

#### C-24. デフォルト user_name が空の時のエラーメッセージ
- 「視点自動判定不可: mykatrain 設定の『デフォルトユーザー名』が未設定です」
- 解決策 (Settings を開くボタン) を提示すると UX 改善 (Lv1)

#### C-25. 古い popup 状態のキャッシュ問題
- 同じ popup を 2 回開くと、`_rank_detect_retries` が引き継がれる可能性
- 対策: インスタンス生成時に明示的にリセット (確認: 現状 `__init__` で 0 リセット済 — OK)

---

## 3. 統計データ

| 項目 | 値 |
|------|---|
| ソースコード行数 (合計) | ~5,400 行 (coach core 4,200 + GUI 1,200) |
| テスト数 | 1,100+ 件 (popup 96 + cli 17 + validator 他) |
| popup テスト headless 失敗 | 94 / 96 件 |
| 症状定義数 | 40 (auto 21 / llm-required 19) |
| うち `related_lexicon_ids` 未設定 | 9 (全て llm-required) |
| i18n キー | 42 使用 / 59 定義 (jp+en 同期) |
| Kansai 同期違反 | 6 + 7 + 1 + 6 + 11 = 31 箇所 |
| 依存ファイル | 14 ファイル |
| Phase 履歴 | 207, 208, 209, 210, 211, 212, 213, 214A, 215, 216, 217, 218, 219, 220, 221, 225(.1〜.8), 226(A〜J), 227(A〜E), 228(A〜D), 229(A〜E), 241(A〜I) |

---

## 4. 推奨アクションプラン

### 短期 (Lv0-Lv1, 1〜3 PR)
1. **A-3 修正** (Lv1): Kansai 辞書を generator script で自動生成 OR `ほんまに` を markers 追加 + `〜...` パターンを NORM ペアに展開
2. **B-2 修正** (Lv0): `_PERSPECTIVE_AUTO_INTERNAL` 定数導入
3. **B-4 修正** (Lv1): truncation 時に status_label に警告表示
4. **B-7 修正** (Lv1): response_input ペースト時のサイズ制限
5. **C-4 修正** (Lv0): popup 上部に schema version 表示

### 中期 (Lv2, 1〜2 PR)
1. **A-2 修正** (Lv2): 9 症状に lexicon 紐付け追加 (AGENTS.md マーカーで慎重)
2. **A-1 対策** (Lv2): popup ロジックを `core/coach/` に Pure 移植 + 薄いラッパー化
3. **B-1 修正** (Lv1): spinner テキストと内部値のマッピング table 化
4. **B-5 修正** (Lv1): プロンプトプレビュー popup 追加
5. **B-6 修正** (Lv1): validate 中の loading インジケータ

### 長期 (Lv3, 1+ PR)
1. **A-1 完全対応**: popup ロジック全移植
2. **C-1 修正**: 検証レンダラ統合
3. **B-8 修正**: dismiss 時のドラフト保存
4. テレメトリ / 性能計測追加

---

## 5. 結論

LLMコーチ機能は **2 年近くにわたる 40+ フェーズ** で丁寧に育てられており、**コード品質は総じて高い**。

ただし、現状で以下が課題:
1. **popup テスト 94 件が headless 環境で失敗** — CI での回帰検出が機能していない
2. **9 症状が lexicon 未紐付け** — LLM 解説の語彙品質に直接影響
3. **Kansai 3 系統辞書の同期違反 31 箇所** — 文体検出の漏れ / ドキュメントとの乖離

これらは **短期 (Lv0-Lv1) で着手可能** なので、Phase 242 として 1〜2 PR で整理することを推奨。

それ以外の B / C 項目は UX 改善が中心なので、ユーザフィードバックに応じて優先度判断。
