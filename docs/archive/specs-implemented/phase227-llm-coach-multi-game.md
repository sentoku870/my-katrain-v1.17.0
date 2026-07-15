# Phase 227 マスター仕様書 — LLM コーチ「複数局対応」

> 起票日: 2026-07-15
> ステータス: ✅ 完了（全サブフェーズ 227-A〜E）
> ユーザー選択: B案（フル実装、レイアウトタブ化）

## 1. 概要

Phase 225 で導入された LLM Coach GUI は **単局カルテ (karte)** のみを扱っていた。
Phase 227 では **複数局サマリ (summary)** JSON も同一ポップアップで扱えるようにする。

ユーザー選択（2026-07-15 確認）:
- アプローチ: **B案（フル実装）** — タブ化 + 専用 UX
- 集約サマリプロンプトの用途: **N局の弱点パターン抽出**
- summary 視点セレクタ: **default_user名選択 + 全体俯瞰**

## 2. サブフェーズ一覧

| Phase | 概要 | 主な変更 | tests |
|-------|------|---------|-------|
| 227-A | summary_prompt_builder + CLI --summary-mode | 4 ファイル新規 + 47 tests | +47 |
| 227-B | summary_validator + CLI validate --summary-mode | 2 ファイル新規 + 63 tests | +63 |
| 227-C | find_latest_llm_input + detect_player_info_for_summary | 2 ファイル拡張 + 30 tests | +30 |
| 227-D | popup タブ化 + 視点セレクタ + 集約サマリボタン | 4 ファイル拡張 + 47 tests | +47 |
| 227-E | i18n 完了 + summary calibration fixtures + ドキュメント | 5 ファイル拡張 + 16 tests | +16 |
| **合計** | | **17 ファイル + 203 新規 tests** | **+203** |

## 3. アーキテクチャ

### 3.1 データフロー

```
選択された JSON
  ↓ detect_json_type (Phase 221)
  ├─ "karte"   → build_llm_prompt / validate_llm_output  (Phase 211/212)
  └─ "summary" → build_summary_weakness_prompt / validate_summary_llm_output  (Phase 227-A/B)
  ↓
  結果 Markdown → クリップボード → LLM → ユーザー貼付 → 検証
```

### 3.2 レイヤー構造

- **core/coach/ (Kivy非依存)**:
  - `summary_prompt_builder.py` (Phase 227-A): multi-game summary 用プロンプト生成
  - `summary_validator.py` (Phase 227-B): multi-game summary 用検証
  - `json_type.py` (Phase 227-A 拡張): `extract_summary_weakness_patterns` 追加
  - `cli.py` (Phase 227-A/B 拡張): `--summary-mode` / `--player` フラグ
  - `calibration_fixtures.py` (Phase 227-E 拡張): 4 個の summary フィクスチャ追加

- **gui/ (Kivy 依存)**:
  - `features/llm_coach.py` (Phase 227-C/D 拡張):
    - `find_latest_llm_input_for_ctx`: karte/summary 両対応
    - `detect_player_info_for_summary`: summary の players ブロック解析
    - `build_summary_llm_prompt` / `validate_summary_llm_response`: popup 用ラッパー
  - `features/report_navigator.py` (Phase 227-C 拡張):
    - `find_latest_llm_input`: zip 等を除外して karte/summary のみ返す
  - `popups/llm_coach_popup.py` (Phase 227-D 拡張):
    - 型検出 + ディスパッチ（karte/summary 両対応）
    - summary 視点セレクタ（プレイヤー名 + 全体俯瞰）
    - 「集約サマリプロンプト」ボタン（generate ボタンのテキスト切替）
    - 状態: `path_type`, `summary_players`, `summary_perspective_index`
  - `kv/llm_coach_popup.kv` (Phase 227-D 拡張):
    - `type_label` ウィジェット追加
    - `karte_path_input.on_text_validate` バインディング追加

## 4. 機能仕様

### 4.1 popup UX フロー

1. ユーザーが Karte JSON パスまたは Summary JSON パスを選択（手動入力 / 参照ダイアログ / 自動入力）
2. `type_label` に「単局カルテ」または「複数局サマリ (N局)」を表示
3. summary の場合、perspective セレクタが「全体俯瞰 + 各プレイヤー」に切り替わる
4. **generate ボタン**のテキストが summary モードでは「集約サマリプロンプト」に変わる
5. クリック時に `build_summary_weakness_prompt` を呼び出し、弱点パターン抽出用 Markdown を生成
6. 検証も同じ流れで `validate_summary_llm_response` が呼ばれる

### 4.2 集約サマリプロンプトの出力形式

LLM に渡されるプロンプトの構造:

```
[SYSTEM INSTRUCTION — HTMLコメント]
Role: Go coach. Extract recurring weakness patterns, NOT single-game review.
Mode / Level / Games / Focus / Rank
[STRICT RULES]
  - DO NOT analyze the board independently
  - DO NOT invent move numbers / game IDs
  - Patterns must come from weaknesses[*].category
  - Maximum 3 patterns
  - End with: 抽出した弱点パターン: [...]

[BODY]
1. N局の集計サマリを分析
2. 弱点パターンを最大3つ挙げよ
3. 弱点名 / 該当phase / 頻度 / 改善の方向性

[入力データ]
  - Summary JSON (Markdown code block)
  - Weakness Patterns (top N) - 色/phase/category/count/頻度%/総損失
  - Phase × Mistake Buckets

[最終出力形式]
  抽出した弱点パターン: [...]
  参照したphase: [...]
```

### 4.3 検証ルール

| 重大度 | kind | 検出内容 |
|--------|------|---------|
| HIGH | `unknown_pattern_category` | 弱点パターンが summary の `weaknesses[*].category` に存在しない |
| HIGH | `forbidden_move_number` | 着手番号参照（summary には per-move 情報が無いので捏造兆候） |
| MEDIUM | `too_many_patterns` | パターン数 > MAX_PATTERNS=3 |
| MEDIUM | `phase_label_out_of_set` | 既知 phase (opening/middle/endgame) が summary に無い |
| LOW | `specific_game_id_referenced` | 特定 game ID 参照（g1, game_3 等） |
| LOW | `tone_inconsistency_ayaka/tomoko` | トーン整合性 |

## 5. i18n キー追加

合計 15 個の新規キー追加（jp/en）:

```
mykatrain:llm-coach:type-label-single
mykatrain:llm-coach:type-label-multi
mykatrain:llm-coach:type-label-unknown
mykatrain:llm-coach:type-detection-failed
mykatrain:llm-coach:summary-perspective-label
mykatrain:llm-coach:summary-perspective-birdseye
mykatrain:llm-coach:summary-perspective-summary
mykatrain:llm-coach:summary-build-button
mykatrain:llm-coach:summary-build-failed
mykatrain:llm-coach:summary-copy-success
mykatrain:llm-coach:summary-report-meta
mykatrain:llm-coach:summary-referenced-categories
mykatrain:llm-coach:summary-referenced-phases
mykatrain:llm-coach:summary-referenced-moves
mykatrain:llm-coach:summary-referenced-game-ids
```

## 6. Calibration Fixtures

合計 12 個のフィクスチャ（8 既存 + 4 新規）:

### 既存 (Karte 形状)
- `perfect_game`, `single_atari_mistake`, `reckless_overplay`, `long_mistake_streak`
- `many_small_streaks`, `tilt_chain_disaster`, `tilt_discouragement`, `strong_correlation`

### 新規 (Summary 形状, Phase 227-E)
- `summary_clean`: 3局・minimal・2パターン (black/white 各1)
- `summary_blunder_dominant`: 5局・blunder が 100% 頻度
- `summary_empty_weaknesses`: 1局・weaknesses 空（プレースホルダー分岐）
- `summary_handicapped_mix`: 6局・even/handicapped 混在

CLI calibrate コマンドは summary フィクスチャを `⏭️ skip` として扱い、per-move 症状検出器の代わりにパターン抽出を実行する。

## 7. テスト結果

| フェーズ | テスト数 | 累計テスト合格 |
|---------|---------|--------------|
| Phase 226 終了時 | - | 5,116 件 |
| Phase 227-A 完了 | +47 | 5,163 件 |
| Phase 227-B 完了 | +63 | 5,226 件 |
| Phase 227-C 完了 | +30 | 5,256 件 |
| Phase 227-D 完了 | +47 | 5,303 件 |
| Phase 227-E 完了 | +16 | 5,319 件 |
| **合計** | **+203** | **5,319 件** |

Kivy 依存テスト (Phase 227-D の popup ロジック 25件) は CI で skip。
Kivy 利用可能な環境では実行可能。

## 8. 関連ドキュメント

- `docs/archive/specs-implemented/phase225-llm-coach-gui.md` (Phase 225 詳細)
- `docs/archive/specs-implemented/phase225-master.md` (Phase 225 マスター索引)
- `docs/archive/specs-planned/phase203-llm-translator.md` (元となった LLM 翻訳仕様)
- AGENTS.md §1.3「現在のフェーズ」と §10「変更履歴」に各 Phase のログ

## 9. スコープ外（明示的に含めなかった）

- ❌ 対局支援・チート用途（AGENTS.md §7 遵守）
- ❌ API 連携（Phase 224 将来再検討、手動貼付維持）
- ❌ summary の per-move 検証（元データに存在しないため自然に skip）
- ❌ 大規模棋譜DB（non-goal）
- ❌ summary の弱点パターンを Karte 側に逆注入（Curator は別タスク）
- ❌ プレイヤー名のあいまいマッチ（完全一致のみ、フォールバックは「全体俯瞰」）
- ❌ Lexicon injection to summary prompts (Phase 227-B §6 reserved for future)
- ❌ auto-detect summary モード (Phase 227-D は `path_type` のみ使用、validate は `is_summary()`)

## 10. ユーザー操作例

### シナリオ 1: 単局カルテ（既存・回帰なし）
1. 棋譜を解析 → Karte JSON 書き出し
2. LLM コーチ popup → 既存通り動作

### シナリオ 2: 複数局サマリ（新規）
1. 棋譜フォルダ選択 → 複数局サマリ JSON 書き出し
2. LLM コーチ popup → 自動で「複数局サマリ (5局)」ラベル表示
3. デフォルトユーザー設定済み → 自動でそのプレイヤーを視点選択
4. 「集約サマリプロンプト」クリック → 弱点パターン抽出用 Markdown 生成
5. Claude に貼り付け → 弱点リスト返却
6. 「検証実行」→ per-move 警告なし、phase_x_mistake 言及チェックのみ

### シナリオ 3: 自動判定
- デフォルト動作で `detect_json_type()` が summary を検出し、`validate_summary_llm_response` が自動選択される
- ユーザーが `--summary-mode` 明示フラグで karta を渡すと exit 2 で拒否
